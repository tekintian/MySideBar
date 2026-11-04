UTF8 = "UTF-8"
GB18030 = "Chinese (GB18030)"
UTF16LE = "UTF-16 LE"
UTF16BE = "UTF-16 BE"

CONVERTIBLE = (GB18030, UTF8, UTF16LE, UTF16BE)

PY_CODECS = {
    UTF8: "utf-8",
    GB18030: "gb18030",
    UTF16LE: "utf-16-le",
    UTF16BE: "utf-16-be",
}


def py_codec(name):
    return PY_CODECS.get(name)


def is_valid(name):
    return name in PY_CODECS