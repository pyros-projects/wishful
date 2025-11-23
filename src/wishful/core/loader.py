from __future__ import annotations

import importlib.abc
import importlib.util
import sys
from types import ModuleType
from typing import Optional, Sequence

from wishful.cache import manager as cache
from wishful.config import settings
from wishful.core.discovery import discover
from wishful.llm.client import GenerationError, generate_module_code
from wishful.safety.validator import SecurityError, validate_code
from wishful.ui import spinner


class MagicLoader(importlib.abc.Loader):
    """Loader that returns dynamic modules backed by cache + LLM generation."""

    def __init__(self, fullname: str):
        self.fullname = fullname

    def create_module(self, spec):  # pragma: no cover - default works
        return None

    def exec_module(self, module: ModuleType) -> None:
        context = discover(self.fullname)
        functions = context.functions

        source = cache.read_cached(self.fullname)
        from_cache = source is not None

        if source is None:
            source = self._generate_and_cache(functions, context)

        self._exec_source(source, module)

        # If cached code is missing requested symbols, regenerate once.
        if functions:
            missing = [name for name in functions if name not in module.__dict__]
            if missing:
                if from_cache:
                    desired = sorted(set(functions) | self._declared_symbols(module))
                    cache.delete_cached(self.fullname)
                    source = self._generate_and_cache(desired, context)
                    self._exec_source(source, module, clear_first=True)
                else:
                    raise GenerationError(
                        f"Generated module for {self.fullname} lacks symbols: {', '.join(missing)}"
                    )

        self._attach_dynamic_getattr(module)

        if settings.review:
            print(f"Generated code for {self.fullname}:\n{source}\n")
            answer = input("Run this code? [y/N]: ")
            if answer.lower().strip() not in {"y", "yes"}:
                cache.delete_cached(self.fullname)
                raise ImportError("User rejected generated code.")

    def _generate_and_cache(self, functions, context):
        with spinner(f"Generating {self.fullname}"):
            source = generate_module_code(self.fullname, functions, context.context)
        cache.write_cached(self.fullname, source)
        return source

    def _exec_source(self, source: str, module: ModuleType, clear_first: bool = False) -> None:
        try:
            validate_code(source, allow_unsafe=settings.allow_unsafe)
        except SecurityError:
            raise
        if clear_first:
            module.__dict__.clear()
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
            module.__getattr__ = _dynamic_getattr
            if name in module.__dict__:
                return module.__dict__[name]
            raise AttributeError(name)

        module.__getattr__ = _dynamic_getattr

    @staticmethod
    def _declared_symbols(module: ModuleType) -> set[str]:
        return {k for k in module.__dict__ if not k.startswith("__")}


class MagicPackageLoader(importlib.abc.Loader):
    """Loader for the root 'wishful' package to enable namespace imports."""

    def create_module(self, spec):  # pragma: no cover - default create
        return None

    def exec_module(self, module: ModuleType) -> None:
        module.__path__ = [str(cache.ensure_cache_dir())]
        module.__package__ = "wishful"
        module.__file__ = str(cache.ensure_cache_dir() / "__init__.py")
