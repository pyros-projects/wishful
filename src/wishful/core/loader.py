from __future__ import annotations

import importlib.abc
import importlib.util
from types import ModuleType

from wishful.cache import manager as cache
from wishful.config import settings
from wishful.core.discovery import discover
from wishful.llm.client import GenerationError, generate_module_code
from wishful.safety.validator import SecurityError, validate_code
from wishful.ui import spinner


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
        if name.startswith("__") or name in DynamicProxyModule._SAFE_ATTRS:
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
        source, from_cache = self._load_source(context)

        if self.mode == "dynamic":
            self._attach_dynamic_proxy(module)

        self._exec_source(source, module)
        self._ensure_symbols(module, context, from_cache)
        if self.mode == "dynamic":
            self._maybe_review(source)
            return

        self._attach_dynamic_getattr(module)
        self._maybe_review(source)

    def _generate_and_cache(self, functions, context):
        with spinner(f"Generating {self.fullname}"):
            source = generate_module_code(
                self.fullname,
                functions,
                context.context,
                type_schemas=context.type_schemas,
                function_output_types=context.function_output_types,
                mode=self.mode,
            )
        # Only write to cache in static mode
        if self.mode == "static":
            cache.write_cached(self.fullname, source)
        return source

    def _exec_source(self, source: str, module: ModuleType, clear_first: bool = False) -> None:
        try:
            validate_code(source, allow_unsafe=settings.allow_unsafe)
        except SecurityError:
            raise
        preserved_loader = module.__dict__.get("_wishful_loader")
        if clear_first:
            module.__dict__.clear()
            if preserved_loader is not None:
                module.__dict__["_wishful_loader"] = preserved_loader
        module.__file__ = str(cache.module_path(self.fullname))
        module.__package__ = self.fullname.rpartition('.')[0]
        exec(compile(source, module.__file__, "exec"), module.__dict__)

    def _attach_dynamic_getattr(self, module: ModuleType) -> None:
        def _dynamic_getattr(name: str):
            if name.startswith("__"):
                raise AttributeError(name)

            ctx = discover(self.fullname)
            functions = set(ctx.functions or [])
            declared = self._declared_symbols(module)
            desired = sorted(declared | functions | {name})

            source = self._generate_and_cache(desired, ctx)
            self._exec_source(source, module, clear_first=True)
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

    def _load_source(self, context) -> tuple[str, bool]:
        # Dynamic mode: always regenerate, never use cache
        if self.mode == "dynamic":
            return self._generate_and_cache(context.functions, context), False
        
        # Static mode: use cache if available
        source = cache.read_cached(self.fullname)
        if source is not None:
            return source, True
        return self._generate_and_cache(context.functions, context), False

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
        print(f"Generated code for {self.fullname}:\n{source}\n")
        answer = input("Run this code? [y/N]: ")
        if answer.lower().strip() not in {"y", "yes"}:
            cache.delete_cached(self.fullname)
            raise ImportError("User rejected generated code.")

    def _missing_symbols(self, module: ModuleType, requested: list[str]) -> list[str]:
        return [name for name in requested if name not in module.__dict__]

    def _regenerate_with(self, module: ModuleType, context) -> None:
        desired = sorted(set(context.functions) | self._declared_symbols(module))
        cache.delete_cached(self.fullname)
        source = self._generate_and_cache(desired, context)
        self._exec_source(source, module, clear_first=True)

    def _regenerate_for_proxy(self, module: ModuleType, requested: str) -> None:
        ctx = discover(self.fullname)
        desired = set(ctx.functions or []) | {requested} | self._declared_symbols(module)
        ctx.functions = sorted(desired)
        source = self._generate_and_cache(ctx.functions, ctx)
        self._exec_source(source, module, clear_first=True)

    def _call_with_runtime(self, module: ModuleType, func_name: str, args, kwargs):
        ctx = discover(self.fullname, runtime_context={"function": func_name, "args": args, "kwargs": kwargs})
        desired = set(ctx.functions or []) | {func_name} | self._declared_symbols(module)
        ctx.functions = sorted(desired)

        source = self._generate_and_cache(ctx.functions, ctx)
        self._exec_source(source, module, clear_first=True)

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
