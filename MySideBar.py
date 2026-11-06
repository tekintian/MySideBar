import importlib.util
import os
import pkgutil
import sys


_PKG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mysidebar")
_MODULE_NAME = "mysidebar"


def _purge_stale_modules():
    for name in list(sys.modules):
        if name == _MODULE_NAME or name.startswith(_MODULE_NAME + "."):
            del sys.modules[name]


def _load_package():
    _purge_stale_modules()
    spec = importlib.util.spec_from_file_location(
        _MODULE_NAME,
        os.path.join(_PKG_DIR, "__init__.py"),
        submodule_search_locations=[_PKG_DIR],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[_MODULE_NAME]
        raise
    return module


def _export_command_classes(package):
    from sublime_plugin import (
        ApplicationCommand,
        EventListener,
        TextCommand,
        ViewEventListener,
        WindowCommand,
    )

    base_classes = (
        ApplicationCommand,
        WindowCommand,
        TextCommand,
        EventListener,
        ViewEventListener,
    )

    exported = {}
    for info in pkgutil.walk_packages(package.__path__, _MODULE_NAME + "."):
        if info.ispkg:
            continue
        try:
            module = importlib.import_module(info.name)
        except Exception:
            import traceback

            traceback.print_exc()
            print("[MySideBar] failed to import %s" % info.name)
            continue
        for attr_name, attr_value in vars(module).items():
            if attr_name.startswith("_"):
                continue
            if not isinstance(attr_value, type):
                continue
            if attr_value.__module__ != info.name:
                continue
            if not issubclass(attr_value, base_classes):
                continue
            exported[attr_name] = attr_value
    return exported


def _bootstrap():
    package = _load_package()
    exported = _export_command_classes(package)
    globals().update(exported)
    return package


try:
    mysidebar = _bootstrap()
except Exception:
    import traceback

    traceback.print_exc()
    print("[MySideBar] package load failed")
    mysidebar = None


def plugin_loaded():
    if mysidebar is not None:
        mysidebar.on_plugin_loaded()


def plugin_unloaded():
    if mysidebar is not None:
        mysidebar.on_plugin_unloaded()