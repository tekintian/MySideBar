import datetime
import os
import traceback

import sublime
import sublime_plugin

from .. import encoding_detect
from .. import encodings
from .. import i18n

REPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "tmp",
)


def _report_path():
    try:
        os.makedirs(REPORT_DIR, exist_ok=True)
    except Exception:
        pass
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(REPORT_DIR, "encoding_report_%s.txt" % stamp)


def _supported_encodings():
    fn = getattr(sublime, "list_encodings", None)
    if fn is None:
        return None
    try:
        return sorted(fn())
    except Exception:
        return []


def _describe_view(lines, view, tag):
    lines.append("[%s]" % tag)
    try:
        lines.append("  is_valid           = %s" % view.is_valid())
        lines.append("  file_name          = %s" % view.file_name())
        lines.append("  view id            = %s" % view.id())
        lines.append("  encoding           = %r" % view.encoding())
        lines.append("  is_dirty           = %s" % view.is_dirty())
        lines.append("  is_loading         = %s" % view.is_loading())
        lines.append("  size               = %s" % view.size())
        lines.append("  window             = %s" % view.window())
    except Exception:
        lines.append("  ERROR: %s" % traceback.format_exc().replace("\n", " | "))
    _probe_roundtrip(lines, view)


def _probe_roundtrip(lines, view):
    try:
        text = view.substr(sublime.Region(0, view.size()))
    except Exception:
        lines.append("  substr             FAILED")
        return
    lines.append("  substr             = %r" % text[:60])
    for codec in ("utf-8", "cp1252", "latin-1"):
        try:
            payload = text.encode(codec)
            lines.append("  encode %-10s   = %r" % (codec, payload[:48]))
        except Exception as exc:
            lines.append("  encode %-10s   FAILED %s" % (codec, exc))
            continue
        path = view.file_name()
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as fp:
                disk = fp.read()
        except Exception:
            continue
        lines.append("  disk bytes           = %r" % disk[:48])
        matched = payload == disk
        lines.append("  %s roundtrip == disk = %s" % (codec, matched))
        if matched:
            try:
                restored = payload.decode("gb18030")
                lines.append("  restored via gb18030 = %r" % restored[:40])
            except Exception as exc:
                lines.append("  restore gb18030      FAILED %s" % exc)


def _probe_file(lines, path):
    lines.append("[file] %s" % path)
    try:
        size = os.path.getsize(path)
        lines.append("  size = %s" % size)
    except Exception:
        lines.append("  size read failed")
    try:
        with open(path, "rb") as fp:
            head = fp.read(64)
        lines.append("  head bytes = %r" % head)
    except Exception:
        lines.append("  read failed")
    detected = encoding_detect.detect(path)
    lines.append("  detect()   = %r" % detected)
    try:
        with open(path, "rb") as fp:
            raw = fp.read()
        lines.append("  utf8 clean = %s" % encoding_detect._clean_utf8(raw))
        lines.append("  binary     = %s" % encoding_detect._looks_binary(raw))
        for codec in ("utf-8", "gb18030", "gbk", "big5", "shift_jis"):
            try:
                raw.decode(codec, "strict")
                lines.append("  decode %-10s OK" % codec)
            except Exception:
                lines.append("  decode %-10s FAIL" % codec)
    except Exception:
        lines.append("  full read failed")
    return detected


class MysidebarEncodingDoctorCommand(sublime_plugin.WindowCommand):
    def run(self):
        path = _report_path()
        lines = []
        lines.append("MySideBar encoding doctor")
        lines.append("=" * 60)
        lines.append("sublime version : %s" % sublime.version())
        try:
            lines.append("platform        : %s" % sublime.platform())
            lines.append("arch            : %s" % sublime.arch())
        except Exception:
            pass
        lines.append("report time     : %s" % datetime.datetime.now().isoformat())
        lines.append("")

        lines.append("[settings]")
        try:
            settings = sublime.load_settings("MySideBar.sublime-settings")
            lines.append("  auto_detect_encoding = %r" % settings.get("auto_detect_encoding"))
            lines.append("  encoding_max_bytes   = %r" % settings.get("encoding_max_bytes"))
        except Exception:
            lines.append("  settings load failed")
        lines.append("")

        lines.append("[encoding_detect]")
        lines.append("  MAX_BYTES = %r" % getattr(encoding_detect, "MAX_BYTES", None))
        lines.append("")

        lines.append("[sublime.list_encodings]")
        encodings = _supported_encodings()
        if encodings is None:
            lines.append("  API NOT AVAILABLE in this build")
        else:
            lines.append("  count = %s" % len(encodings))
            for name in encodings:
                lines.append("    %s" % name)
        lines.append("")

        lines.append("[target files]")
        tmp_dir = REPORT_DIR
        if os.path.isdir(tmp_dir):
            for name in sorted(os.listdir(tmp_dir)):
                full = os.path.join(tmp_dir, name)
                if not os.path.isfile(full):
                    continue
                if name.startswith("encoding_report_"):
                    continue
                lines.append("")
                detected = _probe_file(lines, full)
                reopened = self._try_reopen(full, detected)
                lines.append("  preview reopen = %s" % reopened)
        lines.append("")

        lines.append("[open views]")
        for window in sublime.windows():
            lines.append("  window %s" % window.id())
            for view in window.views():
                _describe_view(lines, view, "view")
        lines.append("")

        content = "\n".join(lines) + "\n"
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(content)
        print("[MySideBar] encoding report written to %s" % path)
        if self.window is not None:
            self.window.status_message(i18n.t("doctor.report_written", path=path))
        self._open_report(path)

    def _try_reopen(self, path, detected):
        if detected is None:
            return "skip: detect returned None"
        window = self.window or sublime.active_window()
        if window is None:
            return "skip: no window"
        try:
            view = window.find_open_file(path)
        except Exception:
            view = None
        if view is None:
            return "skip: file not open"
        try:
            arg = encodings.reopen_arg(detected)
            if arg is None:
                return "skip: no reopen arg for %r" % detected
            view.run_command("reopen", {"encoding": arg})
            return "reopen(%r) issued, view.encoding()=%r" % (arg, view.encoding())
        except Exception:
            return "reopen failed: %s" % traceback.format_exc().replace("\n", " | ")

    def _open_report(self, path):
        window = self.window or sublime.active_window()
        if window is None:
            return
        window.open_file(path)

    def is_enabled(self):
        return True