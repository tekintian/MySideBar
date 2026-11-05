import codecs
import os

from . import encodings

SAMPLE_BYTES = 512 * 1024
MAX_BYTES = 20 * 1024 * 1024

_BOMS = (
    (codecs.BOM_UTF8, encodings.UTF8),
    (codecs.BOM_UTF16_LE, encodings.UTF16LE),
    (codecs.BOM_UTF16_BE, encodings.UTF16BE),
)


def _read(path):
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size <= 0 or size > MAX_BYTES:
        return None
    try:
        with open(path, "rb") as fp:
            return fp.read(SAMPLE_BYTES)
    except OSError:
        return None


def _bom_encoding(raw):
    for bom, name in _BOMS:
        if raw.startswith(bom):
            return name
    return None


def _looks_binary(raw):
    sample = raw[:4096]
    if not sample:
        return False
    control = 0
    for byte in sample:
        if byte in (9, 10, 13):
            continue
        if byte < 32 or byte == 127:
            control += 1
    return control * 100 > len(sample)


def _clean_utf8(raw):
    try:
        raw.decode("utf-8", "strict")
        return True
    except UnicodeDecodeError:
        return False


def _pure_ascii(raw):
    try:
        return len(raw) > 0 and max(raw) < 128
    except ValueError:
        return False


def detect(path):
    if not path:
        return None
    raw = _read(path)
    if raw is None:
        return None
    bom = _bom_encoding(raw)
    if bom is not None:
        return bom
    if _looks_binary(raw):
        return None
    if _pure_ascii(raw):
        return None
    if _clean_utf8(raw):
        return encodings.UTF8
    try:
        raw.decode("gb18030", "strict")
        return encodings.GB18030
    except (UnicodeDecodeError, LookupError, ValueError):
        return None


_processed = {}


def should_reopen(view):
    if view is None or not view.is_valid():
        return None
    path = view.file_name()
    if not path:
        return None
    name = detect(path)
    if name is None:
        return None
    if view.encoding() == name:
        return None
    vid = view.id()
    if _processed.get(vid) == name:
        return None
    _processed[vid] = name
    return name


def forget(view):
    if view is None:
        return
    try:
        vid = view.id()
    except Exception:
        return
    _processed.pop(vid, None)