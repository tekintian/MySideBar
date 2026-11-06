import ast
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(os.path.dirname(HERE))


def load_module(path, name, pkg_path=None):
    tree = ast.parse(open(path, encoding="utf-8").read())
    module = types.ModuleType(name)
    if pkg_path is not None:
        module.__path__ = [pkg_path]
    exec(compile(tree, path, "exec"), module.__dict__)
    sys.modules[name] = module
    return module


sys.modules["sublime"] = types.ModuleType("sublime")
sys.modules["sublime_plugin"] = types.ModuleType("sublime_plugin")

pkg = types.ModuleType("mysidebar")
pkg.__path__ = [os.path.join(SRC, "mysidebar")]
sys.modules["mysidebar"] = pkg

strings = load_module(os.path.join(SRC, "mysidebar", "strings.py"), "mysidebar.strings")
pkg.strings = strings

i18n = types.ModuleType("mysidebar.i18n")
i18n.STRINGS = strings.STRINGS
i18n.t = lambda key, **kw: strings.STRINGS.get("en", {}).get(key, key)
sys.modules["mysidebar.i18n"] = i18n
pkg.i18n = i18n

encodings = load_module(os.path.join(SRC, "mysidebar", "encodings.py"), "mysidebar.encodings")
pkg.encodings = encodings

failures = []


def check(label, got, expected):
    if got != expected:
        failures.append("%s: got %r expected %r" % (label, got, expected))


LANGS = ("en", "zh_CN", "zh_TW")

EXTRA_KEYS = (
    "encoding.target.auto",
    "encoding.group.unicode",
    "encoding.group.zh",
    "encoding.group.ja",
    "encoding.group.ko",
    "encoding.group.western",
    "encoding.status_bar",
    "encoding.auto_failed",
    "encoding.detect_ambiguous",
)

for lang in LANGS:
    table = strings.STRINGS[lang]
    for spec in encodings.specs():
        if spec.i18n_key not in table:
            failures.append("missing %s in %s" % (spec.i18n_key, lang))
    for key in EXTRA_KEYS:
        if key not in table:
            failures.append("missing %s in %s" % (key, lang))

check("zh_CN candidates", [s.name for s in encodings.auto_candidates("zh_CN")], [encodings.GB18030])
check("zh_TW candidates", [s.name for s in encodings.auto_candidates("zh_TW")], [encodings.BIG5])
check("ja_JP candidates", [s.name for s in encodings.auto_candidates("ja_JP")], [encodings.SHIFT_JIS])
check("ko_KR no auto candidate", [s.name for s in encodings.auto_candidates("ko_KR")], [])
check("bad locale falls back", [s.name for s in encodings.auto_candidates("xx_YY")], [encodings.GB18030])
check("alias zh", [s.name for s in encodings.auto_candidates("zh")], [encodings.GB18030])
check("cp1252 convertible", encodings.CP1252 in encodings.convertible(), True)
check("shift_jis in auto", encodings.SHIFT_JIS in encodings.convertible("auto"), True)
check("euc_kr not in auto", encodings.EUC_KR in encodings.convertible("auto"), False)
check("cp1252 not in auto", encodings.CP1252 in encodings.convertible("auto"), False)
check("utf8 is convertible", encodings.UTF8 in encodings.convertible(), True)
check("utf16le has bom", encodings.bom(encodings.UTF16LE), b"\xff\xfe")
check("utf16be has bom", encodings.bom(encodings.UTF16BE), b"\xfe\xff")
check("gb18030 no bom", encodings.bom(encodings.GB18030), None)
check("big5 family", encodings.family(encodings.BIG5), encodings.FAMILY_ZH)
check("shift_jis family", encodings.family(encodings.SHIFT_JIS), encodings.FAMILY_JA)
check("gb18030 codec", encodings.py_codec(encodings.GB18030), "gb18030")
check("big5 codec", encodings.py_codec(encodings.BIG5), "big5hkscs")
check("shift_jis codec", encodings.py_codec(encodings.SHIFT_JIS), "shift_jis_2004")
check("reopen arg is display name", encodings.reopen_arg(encodings.GB18030), encodings.GB18030)
check("reopen arg invalid", encodings.reopen_arg("GBK"), None)
check("is_valid gbk", encodings.is_valid("GBK"), False)
check("is_valid gb18030", encodings.is_valid(encodings.GB18030), True)

print("I18N_FAILURES %d" % len(failures))
for item in failures:
    print("  " + item)
sys.exit(1 if failures else 0)