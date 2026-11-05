import codecs

UTF8 = "UTF-8"
GB18030 = "Chinese (GB18030)"
BIG5 = "Chinese (Big5)"
SHIFT_JIS = "Japanese (Shift JIS)"
EUC_KR = "Korean (EUC-KR)"
UTF16LE = "UTF-16 LE"
UTF16BE = "UTF-16 BE"
CP1252 = "Western (Windows 1252)"

AUTO = "auto"
MANUAL = "manual"

FAMILY_UNICODE = "unicode"
FAMILY_ZH = "zh"
FAMILY_JA = "ja"
FAMILY_KO = "ko"
FAMILY_WESTERN = "western"


class EncodingSpec(object):
    __slots__ = ("name", "py_codec", "i18n_key", "family", "group", "priority", "bom")

    def __init__(self, name, py_codec, i18n_key, family, group, priority, bom=None):
        self.name = name
        self.py_codec = py_codec
        self.i18n_key = i18n_key
        self.family = family
        self.group = group
        self.priority = priority
        self.bom = bom

    def __repr__(self):
        return "EncodingSpec(%r, %r, %r)" % (self.name, self.py_codec, self.group)


_SOURCE = (
    (UTF8, "utf-8", "encoding.target.utf8", FAMILY_UNICODE, AUTO, 100, None),
    (UTF16LE, "utf-16-le", "encoding.target.utf16le", FAMILY_UNICODE, AUTO, 99, codecs.BOM_UTF16_LE),
    (UTF16BE, "utf-16-be", "encoding.target.utf16be", FAMILY_UNICODE, AUTO, 98, codecs.BOM_UTF16_BE),
    (GB18030, "gb18030", "encoding.target.gb18030", FAMILY_ZH, AUTO, 60, None),
    (BIG5, "big5hkscs", "encoding.target.big5", FAMILY_ZH, AUTO, 59, None),
    (SHIFT_JIS, "shift_jis_2004", "encoding.target.shift_jis", FAMILY_JA, AUTO, 50, None),
    (EUC_KR, "euc_kr", "encoding.target.euc_kr", FAMILY_KO, MANUAL, 40, None),
    (CP1252, "cp1252", "encoding.target.cp1252", FAMILY_WESTERN, MANUAL, 10, None),
)

_BY_NAME = {}
_ORDER = []

for _raw in _SOURCE:
    _name, _codec, _key, _family, _group, _priority, _bom = _raw
    try:
        codecs.lookup(_codec)
        _ok = True
    except LookupError:
        _ok = False
    if not _ok:
        print("[MySideBar] codec unavailable: %s -> %s, downgraded to manual" % (_name, _codec))
        _group = MANUAL
    _spec = EncodingSpec(_name, _codec, _key, _family, _group, _priority, _bom)
    _BY_NAME[_name] = _spec
    _ORDER.append(_spec)

LOCALE_CODECS = {
    "zh_CN": (GB18030,),
    "zh_SG": (GB18030,),
    "zh_TW": (BIG5,),
    "zh_HK": (BIG5,),
    "ja_JP": (SHIFT_JIS,),
    "ko_KR": (),
}

LOCALE_ALIASES = {
    "zh": "zh_CN",
    "zh_hans": "zh_CN",
    "zh_hant": "zh_TW",
    "ja": "ja_JP",
    "ko": "ko_KR",
}

DEFAULT_LOCALE = "zh_CN"


def _locale_names(locale):
    key = (locale or "").strip()
    if not key:
        return LOCALE_CODECS[DEFAULT_LOCALE]
    if key in LOCALE_CODECS:
        return LOCALE_CODECS[key]
    alias = LOCALE_ALIASES.get(key.lower())
    if alias is not None:
        return LOCALE_CODECS[alias]
    return LOCALE_CODECS[DEFAULT_LOCALE]


def _locale_families(locale):
    names = _locale_names(locale)
    result = []
    for name in names:
        spec = _BY_NAME.get(name)
        if spec is not None and spec.family not in result:
            result.append(spec.family)
    return tuple(result)


def specs(group=None):
    if group is None:
        return list(_ORDER)
    return [spec for spec in _ORDER if spec.group == group]


def convertible(group=None):
    return tuple(spec.name for spec in specs(group))


def spec_for(name):
    return _BY_NAME.get(name)


def auto_candidates(locale=None):
    result = []
    for name in _locale_names(locale):
        spec = _BY_NAME.get(name)
        if spec is None:
            continue
        if spec.group != AUTO:
            continue
        result.append(spec)
    result.sort(key=lambda item: item.priority, reverse=True)
    return result


def family(name):
    spec = _BY_NAME.get(name)
    if spec is None:
        return None
    return spec.family


def py_codec(name):
    spec = _BY_NAME.get(name)
    if spec is None:
        return None
    return spec.py_codec


def bom(name):
    spec = _BY_NAME.get(name)
    if spec is None:
        return None
    return spec.bom


def is_valid(name):
    return name in _BY_NAME


def reopen_arg(name):
    if name not in _BY_NAME:
        return None
    return name


def reopen_view(view, name):
    if view is None or name is None:
        return False
    arg = reopen_arg(name)
    if arg is None:
        return False
    try:
        if not view.is_valid():
            return False
        view.run_command("reopen", {"encoding": arg})
    except Exception:
        return False
    return True