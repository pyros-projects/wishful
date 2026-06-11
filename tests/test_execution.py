"""Direct unit tests for core/execution.py — the shared compile/exec seam."""

from __future__ import annotations

import pytest

from wishful.core.execution import compile_and_exec, run_user_callable


class TestCompileAndExec:
    def test_returns_named_callable(self):
        fn = compile_and_exec("def f(x):\n    return x + 1\n", "f")
        assert fn(1) == 2

    def test_missing_symbol_raises_valueerror(self):
        with pytest.raises(ValueError, match="g"):
            compile_and_exec("def f():\n    return 1\n", "g")

    def test_non_callable_symbol_raises_valueerror(self):
        with pytest.raises(ValueError, match="f"):
            compile_and_exec("f = 42\n", "f")

    def test_on_executed_fires_after_success(self):
        seen = {}

        def hook(source, namespace):
            seen["source"] = source
            seen["has_fn"] = callable(namespace.get("f"))

        compile_and_exec("def f():\n    return 1\n", "f", on_executed=hook)
        assert seen["has_fn"] is True
        assert "def f" in seen["source"]

    def test_on_executed_not_fired_on_failure(self):
        fired = []
        with pytest.raises(ValueError):
            compile_and_exec("x = 1\n", "f", on_executed=lambda s, n: fired.append(1))
        assert not fired

    def test_validation_happens_before_exec(self):
        """Dangerous source must be rejected BEFORE its top level runs."""
        from wishful.safety.validator import SecurityError

        canary = []
        import builtins

        builtins._wishful_exec_canary = canary  # reachable from generated code
        try:
            with pytest.raises(SecurityError):
                compile_and_exec(
                    "import builtins\n"
                    "builtins._wishful_exec_canary.append('ran')\n"
                    "import subprocess\n"
                    "def f():\n    return 1\n",
                    "f",
                )
            assert canary == []  # the module body never executed
        finally:
            del builtins._wishful_exec_canary

    def test_systemexit_at_module_level_contained(self):
        """`raise SystemExit` needs no imports; it must not kill the host."""
        with pytest.raises(ValueError, match="SystemExit"):
            compile_and_exec("raise SystemExit(3)\n", "f")


class TestRunUserCallable:
    def test_ok_value(self):
        ok, value, error = run_user_callable(lambda: 41 + 1, timeout=5.0)
        assert (ok, value, error) == (True, 42, None)

    def test_none_return_is_ok(self):
        ok, value, error = run_user_callable(lambda: None, timeout=5.0)
        assert ok is True and value is None and error is None

    def test_base_exception_contained(self):
        class Weird(BaseException):
            pass

        def boom():
            raise Weird("odd")

        ok, value, error = run_user_callable(boom, timeout=5.0)
        assert ok is False and "Weird" in error
