import mysidebar


def plugin_loaded():
    mysidebar.on_plugin_loaded()


def plugin_unloaded():
    mysidebar.on_plugin_unloaded()