import sys
import types

import pytest
from fastapi import FastAPI

from app.core.registry import ModuleInfo, ModuleRegistryError, load_modules, resolve_order

FAKE_PACKAGE = "fakepkg"


@pytest.fixture
def fake_modules(monkeypatch):
    """Install throwaway modules under `fakepkg` and record the registration order."""
    registered: list[str] = []
    package = types.ModuleType(FAKE_PACKAGE)
    package.__path__ = []
    monkeypatch.setitem(sys.modules, FAKE_PACKAGE, package)

    def add(name, depends_on=(), **overrides):
        module = types.ModuleType(f"{FAKE_PACKAGE}.{name}")
        module.MODULE_INFO = ModuleInfo(name=name, version="0.1.0", depends_on=depends_on)
        module.register = lambda app: registered.append(name)
        for key, value in overrides.items():
            if value is None:
                delattr(module, key)
            else:
                setattr(module, key, value)
        monkeypatch.setitem(sys.modules, module.__name__, module)

    return add, registered


def test_registers_modules_in_dependency_order(fake_modules):
    add, registered = fake_modules
    add("protocols", depends_on=("gear", "nutrition"))
    add("gear", depends_on=("auth",))
    add("nutrition", depends_on=("auth",))
    add("auth")

    infos = load_modules(FastAPI(), ["protocols", "nutrition", "gear", "auth"], FAKE_PACKAGE)

    assert registered == [info.name for info in infos]
    assert registered.index("auth") < registered.index("gear") < registered.index("protocols")
    assert registered.index("nutrition") < registered.index("protocols")


def test_only_enabled_modules_are_registered(fake_modules):
    add, registered = fake_modules
    add("auth")
    add("gear", depends_on=("auth",))

    load_modules(FastAPI(), ["auth", "auth"], FAKE_PACKAGE)

    assert registered == ["auth"]


def test_missing_dependency_is_rejected(fake_modules):
    add, registered = fake_modules
    add("auth")
    add("gear", depends_on=("auth",))

    with pytest.raises(ModuleRegistryError, match="depends on 'auth'"):
        load_modules(FastAPI(), ["gear"], FAKE_PACKAGE)
    assert registered == []


def test_dependency_cycle_is_rejected(fake_modules):
    add, registered = fake_modules
    add("gear", depends_on=("protocols",))
    add("protocols", depends_on=("gear",))

    with pytest.raises(ModuleRegistryError, match="cycle"):
        load_modules(FastAPI(), ["gear", "protocols"], FAKE_PACKAGE)
    assert registered == []


def test_unknown_module_is_rejected():
    with pytest.raises(ModuleRegistryError, match="Unknown module"):
        load_modules(FastAPI(), ["does_not_exist"])


@pytest.mark.parametrize("name", ["../etc", "auth.models", "Auth", ""])
def test_invalid_module_name_is_rejected(name):
    with pytest.raises(ModuleRegistryError, match="Invalid module name"):
        load_modules(FastAPI(), [name])


@pytest.mark.parametrize("missing", ["MODULE_INFO", "register"])
def test_module_without_interface_is_rejected(fake_modules, missing):
    add, _ = fake_modules
    add("broken", **{missing: None})

    with pytest.raises(ModuleRegistryError, match="must export"):
        load_modules(FastAPI(), ["broken"], FAKE_PACKAGE)


def test_module_with_wrong_declared_name_is_rejected(fake_modules):
    add, _ = fake_modules
    add("gear", MODULE_INFO=ModuleInfo(name="other", version="0.1.0"))

    with pytest.raises(ModuleRegistryError, match="declares the name"):
        load_modules(FastAPI(), ["gear"], FAKE_PACKAGE)


def test_resolve_order_keeps_given_order_without_dependencies():
    infos = {name: ModuleInfo(name=name, version="1") for name in ["b", "a", "c"]}

    assert resolve_order(infos) == ["b", "a", "c"]


def test_app_loads_modules_from_settings(client):
    response = client.get("/api/v1/modules")

    assert response.status_code == 200
    assert [module["name"] for module in response.json()] == ["auth", "gear"]


def test_app_without_modules_has_no_auth_routes(monkeypatch):
    from app.core.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("ENABLED_MODULES", "")
    get_settings.cache_clear()

    paths = create_app().openapi()["paths"]

    assert "/healthz" in paths
    assert not any(path.startswith("/api/v1/auth") for path in paths)
