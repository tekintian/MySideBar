import os
import subprocess

import sublime


def platform_name():
    return sublime.platform()


def reveal(path, dir_only=False):
    if not os.path.exists(path):
        return False
    name = sublime.platform()
    try:
        if name == "osx":
            if dir_only and os.path.isdir(path):
                _run(["/usr/bin/open", path])
            else:
                _run(["/usr/bin/open", "-R", path])
            return True
        if name == "windows":
            if dir_only and os.path.isdir(path):
                _run(["explorer", path])
            else:
                _run(["explorer", "/select,", path])
            return True
        if name == "linux":
            parent = path if (dir_only and os.path.isdir(path)) else os.path.dirname(path)
            _run(["xdg-open", parent])
            return True
    except (OSError, subprocess.SubprocessError) as exc:
        print("[MySideBar] reveal failed: %s" % exc)
    return False


def open_with_default(path):
    if not os.path.exists(path):
        return False
    name = sublime.platform()
    try:
        if name == "osx":
            _run(["/usr/bin/open", path])
            return True
        if name == "windows":
            os.startfile(path)
            return True
        if name == "linux":
            _run(["xdg-open", path])
            return True
    except (OSError, subprocess.SubprocessError) as exc:
        print("[MySideBar] open failed: %s" % exc)
    return False


def open_terminal(path):
    target = path if os.path.isdir(path) else os.path.dirname(path)
    name = sublime.platform()
    try:
        if name == "osx":
            _run(["/usr/bin/open", "-a", "Terminal", target])
            return True
        if name == "windows":
            _run(["cmd", "/c", "start", "cmd", "/K", "cd /d %s" % target])
            return True
        if name == "linux":
            _run(["xdg-open", target])
            return True
    except (OSError, subprocess.SubprocessError) as exc:
        print("[MySideBar] terminal failed: %s" % exc)
    return False


def _run(argv):
    subprocess.Popen(argv, shell=False, close_fds=True)


def normalize(path):
    return os.path.normpath(os.path.abspath(path))


def is_within(child, parent):
    child_norm = normalize(child)
    parent_norm = normalize(parent)
    if os.path.normcase(child_norm) == os.path.normcase(parent_norm):
        return False
    try:
        return os.path.commonpath([child_norm, parent_norm]) == parent_norm
    except ValueError:
        return False


def same_path(a, b):
    return os.path.normcase(normalize(a)) == os.path.normcase(normalize(b))


def is_symlink(path):
    return os.path.islink(path)


def leaf_name(path):
    return os.path.basename(normalize(path))


def parent_dir(path):
    return os.path.dirname(normalize(path))


def join_path(base, rel):
    return os.path.normpath(os.path.join(base, rel))


def rel_path(path, base):
    try:
        rel = os.path.relpath(normalize(path), normalize(base))
    except ValueError:
        return None
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return None
    return rel.replace(os.sep, "/")


def unique_path(path):
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    index = 1
    while True:
        candidate = "%s (%d)%s" % (root, index, ext)
        if not os.path.exists(candidate):
            return candidate
        index += 1


def duplicate_target(path):
    root, ext = os.path.splitext(path)
    candidate = "%s copy%s" % (root, ext)
    if not os.path.exists(candidate):
        return candidate
    index = 2
    while True:
        candidate = "%s copy %d%s" % (root, index, ext)
        if not os.path.exists(candidate):
            return candidate
        index += 1