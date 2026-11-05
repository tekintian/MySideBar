import re

from .. import i18n
from .options import SCOPE_PATH


class PatternError(Exception):
    def __init__(self, reason_key, **kwargs):
        super().__init__(reason_key)
        self.reason_key = reason_key
        self.kwargs = kwargs

    def message(self):
        return i18n.t("rename.pattern_error", reason=i18n.t(self.reason_key, **self.kwargs))


_GROUP_TOKEN = re.compile(r"\$(\d+|\{(\d+)\})")
_LEFTOVER_TOKEN = re.compile(r"\$(\d+)")


def _translate_replacement(replacement):
    if not replacement:
        return ""
    out = []
    last = 0
    for match in _GROUP_TOKEN.finditer(replacement):
        out.append(replacement[last:match.start()].replace("\\", "\\\\"))
        index = match.group(1)
        if match.group(2) is not None:
            index = match.group(2)
        out.append("\\g<%s>" % index)
        last = match.end()
    out.append(replacement[last:].replace("\\", "\\\\"))
    return "".join(out)


def _compile(pattern):
    if not pattern:
        raise PatternError("rename.error.empty_pattern")
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise PatternError("rename.error.bad_regex", detail=str(exc))


def _split_leaf(rel_old, scope):
    if scope == SCOPE_PATH:
        return "", rel_old
    index = rel_old.rfind("/")
    if index < 0:
        return "", rel_old
    return rel_old[:index], rel_old[index + 1 :]


def _join_leaf(head, leaf):
    if not head:
        return leaf
    return "%s/%s" % (head, leaf)


def apply_regex(rel_old, options, index=0):
    opts = options.normalized()
    head, leaf = _split_leaf(rel_old, opts.scope)
    compiled = _compile(opts.pattern)
    replacement = _translate_replacement(opts.replacement)
    try:
        new_leaf = compiled.sub(replacement, leaf)
    except re.error as exc:
        reason = _classify_sub_error(str(exc))
        raise PatternError(reason, detail=str(exc))
    if _LEFTOVER_TOKEN.search(new_leaf):
        raise PatternError("rename.error.group_out_of_range")
    if "\x00" in new_leaf:
        raise PatternError("rename.error.bad_result")
    if not new_leaf:
        raise PatternError("rename.error.empty_result")
    return _join_leaf(head, new_leaf)


def _classify_sub_error(detail):
    if "invalid group reference" in detail:
        return "rename.error.group_out_of_range"
    return "rename.error.bad_regex"


def apply_sequence(rel_old, options, index=0):
    opts = options.normalized()
    head, leaf = _split_leaf(rel_old, opts.scope)
    number = str(opts.start + index).zfill(opts.digits)
    new_leaf = "%s%s%s" % (opts.prefix, number, opts.suffix)
    return _join_leaf(head, new_leaf)


def apply(rel_old, options, index=0):
    opts = options.normalized()
    if opts.is_sequence():
        return apply_sequence(rel_old, opts, index)
    return apply_regex(rel_old, opts, index)


def validate_options(options):
    opts = options.normalized()
    if opts.is_sequence():
        return opts
    _compile(opts.pattern)
    replacement = _translate_replacement(opts.replacement)
    if _LEFTOVER_TOKEN.search(replacement):
        raise PatternError("rename.error.group_out_of_range")
    return opts