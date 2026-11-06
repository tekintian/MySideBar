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


_AMBIGUOUS_SAMPLE = 64 * 1024
_PUA_RATIO_MAX = 0.02
_HALF_KANA_MAX = 0.30
_CACHE_LIMIT = 512
_UNKNOWN = object()

_cache = {}


def _non_ascii_window(raw):
    if len(raw) <= _AMBIGUOUS_SAMPLE:
        return raw
    for index, byte in enumerate(raw):
        if byte >= 128:
            start = index
            while start > 0 and raw[start - 1] >= 128:
                start -= 1
            return raw[start : start + _AMBIGUOUS_SAMPLE]
    return raw[:_AMBIGUOUS_SAMPLE]


def _text_is_plausible(text):
    if not text:
        return False
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
        return True
    return pua / float(total) <= _PUA_RATIO_MAX


def _half_kana_ratio(text):
    total = 0
    half = 0
    for char in text:
        if char in "\n\r\t":
            continue
        total += 1
        if 0xFF66 <= ord(char) <= 0xFF9D:
            half += 1
    if total == 0:
        return 0.0
    return half / float(total)


def _script_is_plausible(text, spec):
    if spec.py_codec == "shift_jis_2004":
        return _half_kana_ratio(text) <= _HALF_KANA_MAX
    return True


def _trusted(raw, spec):
    sample = _non_ascii_window(raw)
    if not sample:
        return None
    try:
        text = sample.decode(spec.py_codec, "strict")
    except (UnicodeDecodeError, LookupError, ValueError):
        return None
    if not _text_is_plausible(text):
        return None
    if not _script_is_plausible(text, spec):
        return None
    return spec.name


def _cache_key(path, locale):
    return (path, locale or "")


def _cached(key, mtime, size):
    entry = _cache.get(key)
    if entry is None:
        return _UNKNOWN
    if entry[0] != mtime or entry[1] != size:
        return _UNKNOWN
    return entry[2]


def _remember(key, mtime, size, name):
    if len(_cache) >= _CACHE_LIMIT:
        _cache.clear()
    _cache[key] = (mtime, size, name)


def forget(path):
    if not path:
        return
    target = os.path.normcase(os.path.abspath(path))
    stale = [key for key in _cache if key[0] == target]
    for key in stale:
        _cache.pop(key, None)


def detect(path, locale=None):
    if not path:
        return None
    key = os.path.normcase(os.path.abspath(path))
    try:
        stat = os.stat(key)
        mtime = stat.st_mtime
        size = stat.st_size
    except OSError:
        return None
    cached = _cached(_cache_key(key, locale), mtime, size)
    if cached is not _UNKNOWN:
        return cached
    result = _detect_uncached(key, locale)
    _remember(_cache_key(key, locale), mtime, size, result)
    return result


def _detect_uncached(path, locale):
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
    candidates = encodings.auto_candidates(locale)
    if len(candidates) != 1:
        return None
    return _trusted(raw, candidates[0])