from __future__ import annotations

import ast
import importlib
import importlib.abc
import importlib.util
import sys
from types import ModuleType

from wishful.cache import manager as cache
from wishful.config import settings
from wishful.core.discovery import discover
from wishful.llm.client import GenerationError, generate_module_code
from wishful.logging import logger
from wishful.safety.validator import SecurityError, validate_code
from wishful.ui import spinner


def _is_promptable() -> bool:
    """True when ``input()`` can reach a human: a real TTY or an interactive kernel.

    Jupyter/IPython route ``input()`` to the notebook frontend even though stdin
    is not a TTY, so they count as promptable. CI, pytest capture, and /dev/null
    do not — review must fail closed there rather than hang.
    """
    try:
        if sys.stdin is not None and sys.stdin.isatty():
            return True
    except (ValueError, AttributeError):
        pass
    if "ipykernel" in sys.modules:
        return True
    try:
        from IPython import get_ipython  # type: ignore
    except Exception:
        return False
    shell = get_ipython()
    return shell is not None and shell.__class__.__name__ == "ZMQInteractiveShell"


def _source_defines(source: str, name: str) -> bool:
    """Return True if ``source`` defines ``name`` at module top level.

    Used to decide whether a regeneration triggered by an attribute miss is worth
    committing: if the model did not actually produce the requested symbol we must
    leave the existing module and cache untouched rather than clobber them.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    def _target_binds(target: ast.AST) -> bool:
        if isinstance(target, ast.Name):
            return target.id == name
        if isinstance(target, (ast.Tuple, ast.List)):
            return any(_target_binds(elt) for elt in target.elts)
        if isinstance(target, ast.Starred):
            return _target_binds(target.value)
        return False

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                return True
        elif isinstance(node, ast.Assign):
            if any(_target_binds(t) for t in node.targets):
                return True
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return True
    return False


def _resolve_generate_module_code():
    """Resolve the effective generate_module_code across module churn.

    MagicLoader instances can outlive module reloads (the meta-path finder
    keeps the original module's classes alive while tests re-import fresh
    copies). A monkeypatch may therefore land on either the live module in
    sys.modules or on this instance's own module globals — check both and
    prefer whichever differs from the canonical default. Prefer injecting
    ``MagicLoader.generate_fn`` in new code; this fallback exists so plain
    monkeypatching keeps working.
    """
    default_fn = importlib.import_module("wishful.llm.client").generate_module_code

    mod = sys.modules.get(__name__)
    candidates = []
    if mod is not None and hasattr(mod, "generate_module_code"):
        candidates.append(getattr(mod, "generate_module_code"))
    # Always consider the function bound in this module too
    candidates.append(generate_module_code)

    for fn in candidates:
        if fn is not default_fn:
            return fn
    return default_fn


class DynamicProxyModule(ModuleType):
    """Module proxy whose public attributes are call-time-regenerating wrappers.

    The attribute contract (intentional, pinned by tests):

    - Accessing any public (non-underscore) attribute returns a fresh callable
      wrapper and never costs an LLM call; generation happens only when the
      wrapper is *invoked*, with the real runtime arguments as context.
    - Consequently ``hasattr(mod, name)`` is True for every public name and
      ``dir(mod)`` cannot enumerate what the model would generate.
    - Dynamic modules expose *functions only*. A name the model generates as a
      non-callable (a constant, say) raises AttributeError at call time — use
      static mode for modules that carry data attributes.
    """

    def __getattribute__(self, name):
        # Underscore-prefixed names (dunders, _private, _wishful_loader, IPython
        # repr probes) must never trigger a paid regeneration — resolve them
        # normally so a probe gets a plain AttributeError instead of a generation.
        if name.startswith("_"):
            return super().__getattribute__(name)

        loader = super().__getattribute__("_wishful_loader")

        # Lazy: do NOT generate on attribute access. Return a callable that
        # regenerates exactly once — with the real runtime arguments — when it is
        # invoked. Accessing the attribute (or probing it via hasattr/dir) costs
        # no LLM call; only calling the function does.
        def _wrapped(*args, **kwargs):
            return loader._call_with_runtime(self, name, args, kwargs)

        _wrapped.__name__ = name
        return _wrapped


class MagicLoader(importlib.abc.Loader):
    """Loader that returns dynamic modules backed by cache + LLM generation.

    Supports two modes:
    - 'static': Traditional cached behavior (default)
    - 'dynamic': Regenerates with runtime context on every access

    ``generate_fn`` is the injection seam (spec 003, tests): when set — on the
    instance via the constructor, or on the class (wrap in ``staticmethod`` to
    dodge bound-method binding) — it replaces the default LLM client for every
    generation this loader performs. When None, the module-global
    ``generate_module_code`` is resolved at call time, so monkeypatching the
    loader module keeps working.
    """

    generate_fn = None  # type: ignore[var-annotated]

    def __init__(self, fullname: str, mode: str = "static", generate_fn=None):
        self.fullname = fullname
        self.mode = mode  # 'static' or 'dynamic'
        if generate_fn is not None:
            self.generate_fn = generate_fn

    def create_module(self, spec):  # pragma: no cover - default works
        return None

    def exec_module(self, module: ModuleType) -> None:
        context = discover(self.fullname)
        source, from_cache, file_path = self._load_source(context)

        logger.debug(
            "exec_module fullname={} mode={} from_cache={} file={} functions={}",
            self.fullname,
            self.mode,
            from_cache,
            file_path,
            context.functions,
        )

        if self.mode == "dynamic":
            self._attach_dynamic_proxy(module)

        # _exec_source runs validate -> review -> exec, so approval gates real
        # execution on every path (including the syntax-retry and regen paths).
        self._exec_source(source, module, context, file_path=file_path, from_cache=from_cache)
        self._ensure_symbols(module, context, from_cache)
        if self.mode != "dynamic":
            self._attach_dynamic_getattr(module)

    def _generate_and_cache(self, functions, context):
        source = self._generate_validated(functions, context)
        path = self._write_source(source)
        logger.debug("generate done fullname={} path={}", self.fullname, path)
        return source, path

    def _generate_validated(self, functions, context) -> str:
        # Validate BEFORE the caller writes anything, so a failed generation can
        # never survive as a cache entry. A malformed (SyntaxError) generation is
        # retried once; a policy violation (SecurityError) is raised immediately.
        last_syntax_exc: SyntaxError | None = None
        for _ in range(2):
            source = self._invoke_generator(functions, context)
            try:
                validate_code(source, allow_unsafe=settings.allow_unsafe)
            except SyntaxError as exc:
                last_syntax_exc = exc
                logger.warning(
                    "Generated {} has invalid syntax; regenerating once", self.fullname
                )
                continue
            return source
        raise GenerationError(
            f"Generated code for {self.fullname} has invalid syntax after a retry"
        ) from last_syntax_exc

    def _ensure_review_possible(self) -> None:
        """Fail closed before any LLM call when review is on but stdin can't prompt."""
        if settings.review and not _is_promptable():
            raise ImportError(
                "review=True requires an interactive terminal or notebook, but "
                "stdin is not interactive. Use configure(review=False) or "
                "WISHFUL_REVIEW=0 for headless/CI runs."
            )

    def _invoke_generator(self, functions, context) -> str:
        # Refuse to spend an LLM call we'd only reject at the review prompt.
        self._ensure_review_possible()
        logger.info("Generating {}", self.fullname)
        logger.debug(
            "generate start fullname={} mode={} functions={}", self.fullname, self.mode, functions
        )
        with spinner(f"Generating {self.fullname}"):
            # Injection seam first; otherwise the monkeypatch-tolerant resolver.
            gen_fn = self.generate_fn or _resolve_generate_module_code()
            return gen_fn(
                self.fullname,
                functions,
                context.context,
                type_schemas=context.type_schemas,
                function_output_types=context.function_output_types,
                mode=self.mode,
            )

    def _write_source(self, source: str):
        if self.mode == "static":
            return cache.write_cached(self.fullname, source)
        return cache.write_dynamic_snapshot(self.fullname, source)

    def _exec_source(
        self,
        source: str,
        module: ModuleType,
        context,
        clear_first: bool = False,
        file_path: str | None = None,
        allow_retry: bool = True,
        from_cache: bool = False,
    ) -> None:
        filename = file_path or str(cache.module_path(self.fullname))
        try:
            # Compile first so a malformed generation is caught uniformly,
            # whether or not safety validation is enabled, then run the safety
            # checks.
            code_obj = compile(source, filename, "exec")
            validate_code(source, allow_unsafe=settings.allow_unsafe)
        except SyntaxError:
            logger.warning("SyntaxError while loading {}; retrying once", self.fullname)
            if not allow_retry:
                raise
            # Regenerate once on syntax errors, then run the new source through
            # the full compile -> validate -> review -> exec gate.
            if self.mode == "static":
                cache.delete_cached(self.fullname)
            source2, path2 = self._generate_and_cache(context.functions, context)
            self._exec_source(
                source2,
                module,
                context,
                clear_first=True,
                file_path=str(path2),
                allow_retry=False,
            )
            return
        except SecurityError:
            # A rejected static cache file (e.g. written under allow_unsafe and
            # later loaded with safety on) must not persist and permanently break
            # the import — delete it so a later run can regenerate cleanly.
            if self.mode == "static":
                cache.delete_cached(self.fullname)
            raise

        # Validated. Ask for approval BEFORE executing so the gate actually
        # guards execution (it used to run after exec — the code had already run).
        self._maybe_review(source, from_cache=from_cache)
        # Preserve the module machinery across a clear+re-exec — the generated
        # source doesn't define these, so without this the module would lose its
        # name/spec/loader identity after the first dynamic regeneration.
        if clear_first:
            preserved = {
                key: module.__dict__[key]
                for key in (
                    "_wishful_loader", "__name__", "__spec__", "__loader__",
                    "__package__", "__file__", "__builtins__",
                )
                if key in module.__dict__
            }
            module.__dict__.clear()
            module.__dict__.update(preserved)
        module.__file__ = filename
        module.__package__ = self.fullname.rpartition('.')[0]
        try:
            exec(code_obj, module.__dict__)
        except Exception:
            # A freshly generated module that compiled and validated but raises at
            # exec must not survive in the cache — otherwise the cache-hit path
            # re-execs it and the import breaks permanently. A cache-hit (or
            # user-edited) file is left alone; surfacing its error beats silently
            # deleting the user's data.
            if self.mode == "static" and not from_cache:
                cache.delete_cached(self.fullname)
            raise

    def _attach_dynamic_getattr(self, module: ModuleType) -> None:
        def _dynamic_getattr(name: str):
            # Underscore-prefixed names (dunders, _private, IPython repr probes)
            # are never worth a paid generation.
            if name.startswith("_"):
                raise AttributeError(name)

            ctx = discover(self.fullname)
            functions = set(ctx.functions or [])
            declared = self._declared_symbols(module)
            desired = sorted(declared | functions | {name})

            source = self._generate_validated(desired, ctx)
            # Only commit (write cache + re-exec the module) if the regeneration
            # actually produced the requested symbol. Otherwise the existing
            # module and cache stay untouched and the probe gets AttributeError.
            if not _source_defines(source, name):
                raise AttributeError(name)

            path = self._write_source(source)
            self._exec_source(source, module, ctx, clear_first=True, file_path=str(path))
            # Re-attach for future misses after reload
            setattr(module, "__getattr__", _dynamic_getattr)  # type: ignore[assignment]
            if name in module.__dict__:
                return module.__dict__[name]
            raise AttributeError(name)

        setattr(module, "__getattr__", _dynamic_getattr)  # type: ignore[assignment]

    def _attach_dynamic_proxy(self, module: ModuleType) -> None:
        if not isinstance(module, DynamicProxyModule):
            module.__class__ = DynamicProxyModule  # type: ignore[misc]
        setattr(module, "_wishful_loader", self)

    @staticmethod
    def _declared_symbols(module: ModuleType) -> set[str]:
        return {
            k
            for k in module.__dict__
            if not k.startswith("__") and not k.startswith("_wishful_")
        }

    def _load_source(self, context) -> tuple[str, bool, str]:
        # Dynamic mode: always regenerate, never use cache
        if self.mode == "dynamic":
            source, path = self._generate_and_cache(context.functions, context)
            return source, False, str(path)

        # Static mode: use cache if available
        source = cache.read_cached(self.fullname)
        if source is not None:
            logger.debug("cache hit fullname={}", self.fullname)
            return source, True, str(cache.module_path(self.fullname))
        logger.debug("cache miss fullname={}", self.fullname)
        source, path = self._generate_and_cache(context.functions, context)
        return source, False, str(path)

    def _ensure_symbols(self, module: ModuleType, context, from_cache: bool) -> None:
        if not context.functions:
            return

        missing = self._missing_symbols(module, context.functions)
        if not missing:
            return

        if not from_cache:
            raise GenerationError(
                f"Generated module for {self.fullname} lacks symbols: {', '.join(missing)}"
            )

        self._regenerate_with(module, context)

    def _maybe_review(self, source: str, from_cache: bool = False) -> None:
        if not settings.review:
            return
        self._ensure_review_possible()
        print(f"Generated code for {self.fullname}:\n{source}\n")
        try:
            answer = input("Run this code? [y/N]: ")
        except EOFError:
            answer = "n"  # fail closed: no input means no approval
        if answer.lower().strip() not in {"y", "yes"}:
            # Only discard a *freshly generated* rejection. A cache-hit file was
            # approved before (or hand-edited by the user); rejecting it now means
            # "don't run it this time", not "delete my file".
            if not from_cache:
                cache.delete_cached(self.fullname)
            raise ImportError("User rejected generated code.")

    def _missing_symbols(self, module: ModuleType, requested: list[str]) -> list[str]:
        return [name for name in requested if name not in module.__dict__]

    def _regenerate_with(self, module: ModuleType, context) -> None:
        # Do NOT delete the existing cache first: a transient generation failure
        # would then destroy the working module. write_cached (via os.replace) is
        # atomic, so the new source overwrites the old on success and the previous
        # file survives untouched when generation raises.
        desired = sorted(set(context.functions) | self._declared_symbols(module))
        source, path = self._generate_and_cache(desired, context)
        self._exec_source(source, module, context, clear_first=True, file_path=str(path))

    def _call_with_runtime(self, module: ModuleType, func_name: str, args, kwargs):
        ctx = discover(self.fullname, runtime_context={"function": func_name, "args": args, "kwargs": kwargs})
        desired = set(ctx.functions or []) | {func_name} | self._declared_symbols(module)
        ctx.functions = sorted(desired)

        source = self._generate_validated(ctx.functions, ctx)
        # Same commit-guard as _dynamic_getattr: a generation that failed to
        # produce the called symbol must not replace the module namespace or the
        # snapshot — the caller gets AttributeError and the module stays intact.
        if not _source_defines(source, func_name):
            raise AttributeError(func_name)

        path = self._write_source(source)
        self._exec_source(source, module, ctx, clear_first=True, file_path=str(path))

        target = module.__dict__.get(func_name)
        if callable(target):
            return target(*args, **kwargs)
        raise AttributeError(func_name)


class MagicPackageLoader(importlib.abc.Loader):
    """Loader for the root 'wishful' package to enable namespace imports."""

    def create_module(self, spec):  # pragma: no cover - default create
        return None

    def exec_module(self, module: ModuleType) -> None:
        module.__path__ = [str(cache.ensure_cache_dir())]
        module.__package__ = "wishful"
        module.__file__ = str(cache.ensure_cache_dir() / "__init__.py")
