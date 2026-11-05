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
        for spec in encodings.specs():
            try:
                raw.decode(spec.py_codec, "strict")
                lines.append("  decode %-22s OK   (%s)" % (spec.py_codec, spec.group))
            except Exception:
                lines.append("  decode %-22s FAIL (%s)" % (spec.py_codec, spec.group))
    except Exception:
        lines.append("  full read failed")
    return detected


CALIBRATION_SAMPLES = (
    ("gb_sentence", "这是一个简体中文的句子，用来测试编码判断是否正确。", "gb18030"),
    ("gb_long", "编码判定是一个需要谨慎处理的问题，因为一旦判断错误，"
                "用户往往无法察觉，保存之后原文件就会永久损坏，且不可恢复。", "gb18030"),
    ("gb_punct", "—— … ・ 　", "gb18030"),
    ("big5_sentence", "這是一個繁體中文的長句子，用來測試編碼判斷是否正確。", "big5hkscs"),
    ("big5_long", "編碼判定是一個需要謹慎處理的問題，因為一旦判斷錯誤，"
                  "使用者往往無法察覺，儲存之後原檔案就會永久損壞，且無法復原。", "big5hkscs"),
    ("big5_short", "繁體測試", "big5hkscs"),
    ("sjis_long", "これは日本語の長い文章です。エンコーディングの判定が正しいかどうかをテストします。", "shift_jis_2004"),
    ("sjis_short", "日本語テスト", "shift_jis_2004"),
)

CALIBRATION_CODECS = ("gb18030", "big5hkscs", "shift_jis_2004")


def _calibration_ratios(text):
    total = 0
    pua = 0
    for char in text:
        if char in "\n\r\t":
            continue
        total += 1
        code = ord(char)
        if 0xE000 <= code <= 0xF8FF or 0xF0000 <= code <= 0x10FFFF:
            pua += 1
    if total == 0:
        return 0.0
    return pua / float(total)


def _append_calibration(lines):
    lines.append("[calibration] PUA ratio matrix, runs inside Sublime Text")
    for name, text, real in CALIBRATION_SAMPLES:
        lines.append("  %s (real=%s)" % (name, real))
        try:
            raw = text.encode(real)
        except Exception as exc:
            lines.append("    encode failed: %s" % exc)
            continue
        for cand in CALIBRATION_CODECS:
            try:
                decoded = raw.decode(cand, "strict")
            except Exception:
                lines.append("    -> %-16s STRICT-FAIL" % cand)
                continue
            ratio = _calibration_ratios(decoded)
            if cand == real:
                verdict = "CORRECT"
            elif ratio > encoding_detect._PUA_RATIO_MAX:
                verdict = "INTERCEPT"
            else:
                verdict = "PASS-THROUGH"
            lines.append("    -> %-16s pua=%.3f %s" % (cand, ratio, verdict))
    lines.append("")


def _append_registry(lines, locale):
    lines.append("[encoding registry]")
    for spec in encodings.specs():
        lines.append(
            "  %-24s codec=%-18s family=%-8s group=%-6s priority=%s"
            % (spec.name, spec.py_codec, spec.family, spec.group, spec.priority)
        )
    lines.append("  locale             = %r" % locale)
    candidates = encodings.auto_candidates(locale)
    lines.append("  auto candidates    = %s" % [spec.name for spec in candidates])
    if len(candidates) != 1:
        lines.append("  verdict            = SKIP auto reopen (needs exactly 1 candidate)")
    else:
        lines.append("  verdict            = auto reopen as %s" % candidates[0].name)
    lines.append("")


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
        locale = encodings.DEFAULT_LOCALE
        try:
            settings = sublime.load_settings("MySideBar.sublime-settings")
            lines.append("  auto_detect_encoding = %r" % settings.get("auto_detect_encoding"))
            lines.append("  encoding_max_bytes   = %r" % settings.get("encoding_max_bytes"))
            lines.append("  encoding_auto_locales= %r" % settings.get("encoding_auto_locales"))
            lines.append("  encoding_status_bar  = %r" % settings.get("encoding_status_bar"))
            raw_locale = settings.get("encoding_auto_locales", encodings.DEFAULT_LOCALE)
            if isinstance(raw_locale, str) and raw_locale.strip():
                locale = raw_locale
        except Exception:
            lines.append("  settings load failed")
        lines.append("")

        lines.append("[encoding_detect]")
        lines.append("  MAX_BYTES = %r" % getattr(encoding_detect, "MAX_BYTES", None))
        lines.append("  PUA_RATIO_MAX = %r" % encoding_detect._PUA_RATIO_MAX)
        lines.append("  cache size = %d" % len(encoding_detect._cache))
        lines.append("")

        _append_registry(lines, locale)
        _append_calibration(lines)

        lines.append("[sublime.list_encodings]")
        supported = _supported_encodings()
        if supported is None:
            lines.append("  API NOT AVAILABLE in this build")
        else:
            lines.append("  count = %s" % len(supported))
            for name in supported:
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