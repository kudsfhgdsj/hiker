"""Module registry: loads the feature modules named in ENABLED_MODULES.

Core never imports a module directly. Each module package exports `MODULE_INFO`
and `register(app)`; dependencies between modules are declared in
`MODULE_INFO.depends_on` and checked here.
"""

import importlib
import importlib.util
import pkgutil
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from fastapi import FastAPI

MODULES_PACKAGE = "app.modules"

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class ModuleRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    version: str
    depends_on: tuple[str, ...] = ()


def resolve_order(infos: Mapping[str, ModuleInfo]) -> list[str]:
    """Order modules so that each one comes after its dependencies."""
    order: list[str] = []
    visiting: list[str] = []

    def visit(name: str) -> None:
        if name in order:
            return
        if name in visiting:
            cycle = " -> ".join([*visiting[visiting.index(name) :], name])
            raise ModuleRegistryError(f"Dependency cycle between modules: {cycle}")
        visiting.append(name)
        for dependency in infos[name].depends_on:
            if dependency not in infos:
                raise ModuleRegistryError(
                    f"Module '{name}' depends on '{dependency}', which is not enabled"
                )
            visit(dependency)
        visiting.pop()
        order.append(name)

    for name in infos:
        visit(name)
    return order


def _import_module(name: str, package: str):
    if not _NAME_RE.match(name):
        raise ModuleRegistryError(f"Invalid module name: '{name}'")
    full_name = f"{package}.{name}"
    try:
        module = importlib.import_module(full_name)
    except ModuleNotFoundError as exc:
        if exc.name != full_name:
            raise
        raise ModuleRegistryError(f"Unknown module: '{name}'") from exc
    info = getattr(module, "MODULE_INFO", None)
    if not isinstance(info, ModuleInfo) or not callable(getattr(module, "register", None)):
        raise ModuleRegistryError(f"Module '{name}' must export MODULE_INFO and register(app)")
    if info.name != name:
        raise ModuleRegistryError(f"Module '{name}' declares the name '{info.name}'")
    return module


def load_modules(
    app: FastAPI, names: Iterable[str], package: str = MODULES_PACKAGE
) -> list[ModuleInfo]:
    """Import the given modules and register them in dependency order."""
    modules = {name: _import_module(name, package) for name in dict.fromkeys(names)}
    infos = {name: module.MODULE_INFO for name, module in modules.items()}
    order = resolve_order(infos)
    for name in order:
        modules[name].register(app)
    return [infos[name] for name in order]


def import_all_models(package: str = MODULES_PACKAGE) -> None:
    """Import the models of every installed module so that the metadata is complete.

    Used by Alembic. The schema covers all installed modules, independent of
    ENABLED_MODULES, so that disabling a module never orphans its migrations.
    """
    importlib.import_module("app.core.files")
    root = importlib.import_module(package)
    for found in pkgutil.iter_modules(root.__path__):
        models = f"{package}.{found.name}.models"
        if found.ispkg and importlib.util.find_spec(models) is not None:
            importlib.import_module(models)
