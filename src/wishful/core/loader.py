from __future__ import annotations

import ast
import importlib
import importlib.abc
import importlib.util
import sys
from types import ModuleType


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
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                return True
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return True
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return True
    return False

from wishful.cache import manager as cache
from wishful.config import settings
from wishful.core.discovery import discover
from wishful.llm.client import GenerationError, generate_module_code
from wishful.logging import logger
from wishful.safety.validator import SecurityError, validate_code
from wishful.ui import spinner

def _resolve_generate_module_code():
    """Use the generate_module_code function from the live loader module.

    MagicLoader instances can outlive module reloads during tests; looking up
    the function each time keeps monkeypatches effective while preferring any
    patched version over the original default.
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
    """Module proxy that regenerates the underlying module on each attribute access."""

    _SAFE_ATTRS = {
        "__class__",
        "__dict__",
        "__doc__",
        "__loader__",
        "__name__",
        "__package__",
        "__path__",
        "__spec__",
        "__file__",
        "__builtins__",
        "_wishful_loader",
    }

    def __getattribute__(self, name):
        # Underscore-prefixed names (dunders, _private, IPython repr probes) must
        # never trigger a paid regeneration — resolve them normally so a probe
        # gets a plain AttributeError instead of a generation.
        if name.startswith("_") or name in DynamicProxyModule._SAFE_ATTRS:
            return super().__getattribute__(name)

        loader = super().__getattribute__("_wishful_loader")
        loader._regenerate_for_proxy(self, name)

        attr = super().__getattribute__(name)

        if callable(attr):
            def _wrapped(*args, **kwargs):
                return loader._call_with_runtime(self, name, args, kwargs)

            _wrapped.__name__ = name
            _wrapped.__doc__ = getattr(attr, "__doc__", None)
            return _wrapped

        return attr


class MagicLoader(importlib.abc.Loader):
    """Loader that returns dynamic modules backed by cache + LLM generation.
    
    Supports two modes:
    - 'static': Traditional cached behavior (default)
    - 'dynamic': Regenerates with runtime context on every access
    """

    def __init__(self, fullname: str, mode: str = "static"):
        self.fullname = fullname
        self.mode = mode  # 'static' or 'dynamic'

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
        self._exec_source(source, module, context, file_path=file_path)
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
            gen_fn = _resolve_generate_module_code()
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

        # Validated. Ask for approval BEFORE executing so the gate actually
        # guards execution (it used to run after exec — the code had already run).
        self._maybe_review(source)
        preserved_loader = module.__dict__.get("_wishful_loader")
        if clear_first:
            module.__dict__.clear()
            if preserved_loader is not None:
                module.__dict__["_wishful_loader"] = preserved_loader
        module.__file__ = filename
        module.__package__ = self.fullname.rpartition('.')[0]
        exec(code_obj, module.__dict__)

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

    def _maybe_review(self, source: str) -> None:
        if not settings.review:
            return
        self._ensure_review_possible()
        print(f"Generated code for {self.fullname}:\n{source}\n")
        try:
            answer = input("Run this code? [y/N]: ")
        except EOFError:
            answer = "n"  # fail closed: no input means no approval
        if answer.lower().strip() not in {"y", "yes"}:
            cache.delete_cached(self.fullname)
            raise ImportError("User rejected generated code.")

    def _missing_symbols(self, module: ModuleType, requested: list[str]) -> list[str]:
        return [name for name in requested if name not in module.__dict__]

    def _regenerate_with(self, module: ModuleType, context) -> None:
        desired = sorted(set(context.functions) | self._declared_symbols(module))
        cache.delete_cached(self.fullname)
        source, path = self._generate_and_cache(desired, context)
        self._exec_source(source, module, context, clear_first=True, file_path=str(path))

    def _regenerate_for_proxy(self, module: ModuleType, requested: str) -> None:
        ctx = discover(self.fullname)
        desired = set(ctx.functions or []) | {requested} | self._declared_symbols(module)
        ctx.functions = sorted(desired)
        source, path = self._generate_and_cache(ctx.functions, ctx)
        self._exec_source(source, module, ctx, clear_first=True, file_path=str(path))

    def _call_with_runtime(self, module: ModuleType, func_name: str, args, kwargs):
        ctx = discover(self.fullname, runtime_context={"function": func_name, "args": args, "kwargs": kwargs})
        desired = set(ctx.functions or []) | {func_name} | self._declared_symbols(module)
        ctx.functions = sorted(desired)

        source, path = self._generate_and_cache(ctx.functions, ctx)
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
