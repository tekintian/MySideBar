import ctypes
import ctypes.util
import os
import shutil
import subprocess

import sublime


def is_available():
    name = sublime.platform()
    if name == "osx":
        return _osx_runtime() is not None
    if name == "linux":
        return shutil.which("gio") is not None
    if name == "windows":
        return True
    return False


def send(path):
    if not os.path.exists(path):
        return False, "not found"
    name = sublime.platform()
    if name == "osx":
        return _send_osx(path)
    if name == "windows":
        return _send_windows(path)
    if name == "linux":
        return _send_linux(path)
    return False, "unsupported platform"


def _osx_runtime():
    key = "_cache"
    cached = globals().get(key)
    if cached is not None:
        return cached or None
    try:
        objc_path = ctypes.util.find_library("objc")
        if objc_path is None:
            globals()[key] = False
            return None
        objc = ctypes.cdll.LoadLibrary(objc_path)
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        runtime = {"objc": objc}
        globals()[key] = runtime
        return runtime
    except (OSError, AttributeError) as exc:
        print("[MySideBar] objc runtime unavailable: %s" % exc)
        globals()[key] = False
        return None


def _msg(runtime, receiver, selector, *args):
    objc = runtime["objc"]
    sel = objc.sel_registerName(selector.encode("utf-8"))
    func = objc.objc_msgSend
    argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    for arg in args:
        if isinstance(arg, ctypes.c_char_p):
            argtypes.append(ctypes.c_char_p)
        else:
            argtypes.append(ctypes.c_void_p)
    func.argtypes = argtypes
    func.restype = ctypes.c_void_p
    recv = receiver if isinstance(receiver, ctypes.c_void_p) else ctypes.c_void_p(receiver)
    normalized = []
    for arg in args:
        if arg is None:
            normalized.append(ctypes.c_void_p(0))
        elif isinstance(arg, int):
            normalized.append(ctypes.c_void_p(arg))
        else:
            normalized.append(arg)
    return func(recv, sel, *normalized)


def _send_osx(path):
    runtime = _osx_runtime()
    if runtime is None:
        return False, "objc runtime unavailable"
    objc = runtime["objc"]
    created = []
    try:
        ns_url = objc.objc_getClass(b"NSURL")
        ns_string = objc.objc_getClass(b"NSString")
        ns_file_manager = objc.objc_getClass(b"NSFileManager")
        if not ns_url or not ns_string or not ns_file_manager:
            return False, "objective-c class missing"

        raw = path.encode("utf-8")
        ns_str = _msg(runtime, ns_string, "alloc")
        if not ns_str:
            return False, "string alloc failed"
        created.append(ns_str)

        ns_str = _msg(runtime, ns_str, "initWithUTF8String:", ctypes.c_char_p(raw))
        if not ns_str:
            return False, "string init failed"
        created.append(ns_str)

        file_url = _msg(runtime, ns_url, "fileURLWithPath:", ns_str)
        if not file_url:
            return False, "url create failed"
        created.append(file_url)

        manager = _msg(runtime, ns_file_manager, "defaultManager")
        if not manager:
            return False, "file manager unavailable"

        ok = _msg(runtime, manager, "trashItemAtURL:resultingItemURL:error:", file_url, None, None)
        if ok:
            return True, ""
        return False, "trashItemAtURL failed"
    except (OSError, ctypes.ArgumentError) as exc:
        return False, "objc call failed: %s" % exc
    finally:
        for handle in reversed(created):
            try:
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                objc.objc_msgSend.restype = ctypes.c_void_p
                objc.objc_msgSend(ctypes.c_void_p(handle), objc.sel_registerName(b"release"))
            except (OSError, ctypes.ArgumentError):
                pass


def _send_windows(path):
    try:
        import ctypes.wintypes
        from ctypes import Structure, byref, c_uint32, c_void_p, windll
    except ImportError as exc:
        return False, str(exc)

    class SHFILEOPSTRUCTW(Structure):
        _fields_ = [
            ("hwnd", c_void_p),
            ("wFunc", c_uint32),
            ("pFrom", c_void_p),
            ("pTo", c_void_p),
            ("fFlags", ctypes.wintypes.WORD),
            ("fAnyOperationsAborted", ctypes.wintypes.BOOL),
            ("hNameMappings", c_void_p),
            ("lpszProgressTitle", c_void_p),
        ]

    FO_DELETE = 3
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400

    try:
        source = os.path.normpath(path) + "\0"
        op = SHFILEOPSTRUCTW()
        op.wFunc = FO_DELETE
        op.pFrom = ctypes.cast(ctypes.create_string_buffer(source.encode("utf-16-le")), c_void_p)
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
        ret = windll.shell32.SHFileOperationW(byref(op))
        if ret == 0:
            return True, ""
        return False, "SHFileOperationW code %d" % ret
    except (OSError, AttributeError) as exc:
        return False, "shell32 call failed: %s" % exc


def _send_linux(path):
    gio = shutil.which("gio")
    if gio is None:
        return False, "gio not found"
    try:
        proc = subprocess.run([gio, "trash", path], shell=False,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, "gio failed: %s" % exc
    if proc.returncode == 0:
        return True, ""
    message = proc.stderr.decode("utf-8", "replace").strip()
    return False, message or "gio exit %d" % proc.returncode


def permanent_delete(path):
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True, ""
    except OSError as exc:
        return False, str(exc)