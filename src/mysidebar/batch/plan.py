import os
from dataclasses import dataclass, field

from .. import platform as plat
from . import patterns
from .patterns import PatternError


STATUS_OK = "ok"
STATUS_SKIPPED = "skipped"
STATUS_INVALID = "invalid"
STATUS_CONFLICT = "conflict"

KIND_DIR = "dir"
KIND_FILE = "file"

TEMP_DIR_NAME = ".mysidebar_tmp"

MAX_LEAF_BYTES = 255
ILLEGAL_CHARS = '<>:"|?*'


@dataclass
class PlanItem:
    old_abs: str
    rel_old: str
    rel_new: str
    new_abs: str
    kind: str
    status: str = STATUS_OK
    reason: str = ""
    needs_temp: bool = False
    depth: int = 0

    @property
    def old_leaf(self):
        return os.path.basename(self.old_abs)

    @property
    def new_leaf(self):
        return os.path.basename(self.new_abs)

    @property
    def changeable(self):
        return self.status in (STATUS_OK, STATUS_CONFLICT)


@dataclass
class RenamePlan:
    base: str
    items: list = field(default_factory=list)
    skipped_symlinks: int = 0
    error: str = ""

    def actionable(self):
        return [i for i in self.items if i.status == STATUS_OK]

    def counts(self):
        result = {STATUS_OK: 0, STATUS_SKIPPED: 0, STATUS_INVALID: 0, STATUS_CONFLICT: 0}
        for item in self.items:
            if item.status in result:
                result[item.status] += 1
        return result


def _is_symlink(path):
    try:
        return os.path.islink(path)
    except OSError:
        return False


def collect(selected_paths, options):
    opts = options.normalized()
    plan = RenamePlan(base="")
    paths = [plat.normalize(p) for p in (selected_paths or []) if p]
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        plan.error = "rename.error.no_items"
        return plan
    base = _common_base(paths)
    if base is None:
        plan.error = "rename.error.no_base"
        return plan
    plan.base = base
    if not os.access(base, os.W_OK):
        plan.error = "rename.error.base_readonly"
        return plan
    for path in paths:
        if _is_symlink(path):
            plan.skipped_symlinks += 1
            continue
        if os.path.isdir(path):
            _walk_dir(path, base, opts, plan)
            if opts.include_dirs and path != base:
                plan.items.append(_blank_item(path, base, KIND_DIR))
            continue
        plan.items.append(_blank_item(path, base, KIND_FILE))
    if not plan.items:
        plan.error = "rename.error.no_items"
    return plan


def _common_base(paths):
    if len(paths) == 1:
        single = paths[0]
        return single if os.path.isdir(single) else os.path.dirname(single)
    try:
        common = os.path.commonpath(paths)
    except ValueError:
        return None
    if os.path.isdir(common):
        return common
    return os.path.dirname(common)


def _blank_item(path, base, kind):
    rel_old = _rel(path, base)
    return PlanItem(
        old_abs=path,
        rel_old=rel_old,
        rel_new=rel_old,
        new_abs=path,
        kind=kind,
        depth=_depth(rel_old),
    )


def _walk_dir(root, base, opts, plan):
    if not opts.recursive:
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if _is_symlink(path):
                plan.skipped_symlinks += 1
                continue
            if os.path.isdir(path):
                if opts.include_dirs:
                    plan.items.append(_blank_item(path, base, KIND_DIR))
                continue
            plan.items.append(_blank_item(path, base, KIND_FILE))
        return
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        kept = []
        for name in sorted(dirnames):
            path = os.path.join(dirpath, name)
            if _is_symlink(path):
                plan.skipped_symlinks += 1
                continue
            kept.append(name)
        dirnames[:] = kept
        if opts.include_dirs:
            for name in kept:
                path = os.path.join(dirpath, name)
                plan.items.append(_blank_item(path, base, KIND_DIR))
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if _is_symlink(path):
                plan.skipped_symlinks += 1
                continue
            plan.items.append(_blank_item(path, base, KIND_FILE))


def _rel(path, base):
    try:
        return os.path.relpath(path, base).replace(os.sep, "/")
    except (OSError, ValueError):
        return path.replace(os.sep, "/")


def _depth(rel):
    return rel.count("/")


def compute(plan, options):
    opts = options.normalized()
    sequence_index = 0
    for item in plan.items:
        try:
            item.rel_new = _apply_one(item.rel_old, opts, sequence_index)
        except PatternError as exc:
            item.rel_new = item.rel_old
            item.status = STATUS_INVALID
            item.reason = exc.reason_key
            item.new_abs = item.old_abs
            continue
        item.new_abs = _abs_join(plan.base, item.rel_new)
        if opts.is_sequence():
            sequence_index += 1
    return plan


def _apply_one(rel_old, opts, index):
    if opts.is_sequence():
        return patterns.apply_sequence(rel_old, opts, index)
    return patterns.apply_regex(rel_old, opts, 0)


def _abs_join(base, rel_new):
    normalized = rel_new.replace("/", os.sep)
    return plat.normalize(os.path.join(base, normalized))


def validate(plan):
    _validate_unchanged(plan)
    _validate_shape(plan)
    _validate_unique(plan)
    _validate_disk(plan)
    _validate_cycle(plan)
    return plan


def _validate_unchanged(plan):
    for item in plan.items:
        if item.status == STATUS_OK and item.rel_old == item.rel_new:
            item.status = STATUS_SKIPPED
            item.reason = "rename.reason.unchanged"


def _validate_shape(plan):
    for item in plan.items:
        if item.status != STATUS_OK:
            continue
        rel = item.rel_new
        if not rel:
            item.status = STATUS_INVALID
            item.reason = "rename.reason.empty"
            continue
        if os.path.isabs(rel) or rel.startswith("..") or "/../" in rel or rel == "..":
            item.status = STATUS_INVALID
            item.reason = "rename.reason.escape"
            continue
        if not _within(item.new_abs, plan.base):
            item.status = STATUS_INVALID
            item.reason = "rename.reason.escape"
            continue
        reason = _leaf_problem(item.new_leaf)
        if reason:
            item.status = STATUS_INVALID
            item.reason = reason
            continue
        if not _parent_writable(item.old_abs):
            item.status = STATUS_INVALID
            item.reason = "rename.reason.readonly"


def _parent_writable(path):
    parent = os.path.dirname(path)
    if not parent or not os.path.isdir(parent):
        return True
    return os.access(parent, os.W_OK)


def _leaf_problem(leaf):
    if not leaf.strip():
        return "rename.reason.empty"
    for char in ILLEGAL_CHARS:
        if char in leaf:
            return "rename.reason.illegal_char"
    try:
        if len(leaf.encode("utf-8")) > MAX_LEAF_BYTES:
            return "rename.reason.too_long"
    except UnicodeError:
        return "rename.reason.illegal_char"
    return ""


def _within(path, base):
    try:
        return os.path.commonpath([plat.normalize(path), plat.normalize(base)]) == plat.normalize(base)
    except ValueError:
        return False


def _validate_unique(plan):
    buckets = {}
    for item in plan.items:
        if item.status != STATUS_OK:
            continue
        key = _key(item.new_abs)
        buckets.setdefault(key, []).append(item)
    for group in buckets.values():
        if len(group) < 2:
            continue
        for item in group:
            item.status = STATUS_CONFLICT
            item.reason = "rename.reason.duplicate_target"


def _validate_disk(plan):
    leaving = set()
    for item in plan.items:
        if item.status == STATUS_OK:
            leaving.add(_key(item.old_abs))
    for item in plan.items:
        if item.status != STATUS_OK:
            continue
        if not os.path.lexists(item.new_abs):
            continue
        target_key = _key(item.new_abs)
        if target_key in leaving:
            continue
        if _same_file(item.old_abs, item.new_abs):
            continue
        item.status = STATUS_CONFLICT
        item.reason = "rename.reason.exists_on_disk"


def _key(path):
    return os.path.normcase(plat.normalize(path))


def _same_file(left, right):
    try:
        return os.path.samefile(left, right)
    except OSError:
        return os.path.normcase(plat.normalize(left)) == os.path.normcase(plat.normalize(right))


def _validate_cycle(plan):
    pending = {}
    for item in plan.items:
        if item.status != STATUS_OK:
            continue
        pending[_key(item.old_abs)] = item
    targets = {}
    for item in plan.items:
        if item.status != STATUS_OK:
            continue
        targets[_key(item.old_abs)] = _key(item.new_abs)
    for item in plan.items:
        if item.status != STATUS_OK:
            continue
        if _same_name_case_variant(item):
            item.needs_temp = True
            continue
        if _reaches_cycle(item, targets, pending):
            item.needs_temp = True


def _reaches_cycle(item, targets, pending):
    key = _key(item.old_abs)
    seen = set()
    current = targets.get(key)
    while current is not None:
        if current == key:
            return True
        if current in seen:
            return False
        seen.add(current)
        if current not in pending:
            return False
        current = targets.get(current)
    return False


def _same_name_case_variant(item):
    if item.rel_old == item.rel_new:
        return False
    return item.rel_old.lower() == item.rel_new.lower()