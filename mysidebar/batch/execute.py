import os
import shutil
import uuid
from dataclasses import dataclass, field

from .plan import KIND_DIR, KIND_FILE, TEMP_DIR_NAME


STEP_TEMP_IN = "temp_in"
STEP_DIR = "dir"
STEP_FILE = "file"
STEP_TEMP_OUT = "temp_out"

RESULT_OK = "ok"
RESULT_ABORTED = "aborted"
RESULT_EMPTY = "empty"


@dataclass
class RenameRecord:
    source: str
    target: str
    kind: str


@dataclass
class ExecutionResult:
    status: str = RESULT_OK
    records: list = field(default_factory=list)
    failure_path: str = ""
    failure_error: str = ""
    failure_reason: str = ""
    temp_root: str = ""

    def done(self):
        return self.status == RESULT_OK

    def moved_pairs(self):
        return [(r.source, r.target) for r in self.records if r.kind != STEP_TEMP_IN]


def build_steps(plan):
    steps = []
    temp_items = []
    for item in plan.actionable():
        if item.needs_temp:
            temp_items.append(item)
            steps.append((STEP_TEMP_IN, item))
    dir_items = [i for i in plan.actionable() if not i.needs_temp and i.kind == KIND_DIR]
    dir_items.sort(key=lambda i: i.depth, reverse=True)
    for item in dir_items:
        steps.append((STEP_DIR, item))
    for item in plan.actionable():
        if item.needs_temp or item.kind != KIND_FILE:
            continue
        steps.append((STEP_FILE, item))
    for item in temp_items:
        steps.append((STEP_TEMP_OUT, item))
    return steps


def execute(plan, retarget=None):
    result = ExecutionResult()
    steps = build_steps(plan)
    if not steps:
        result.status = RESULT_EMPTY
        return result
    dir_final = {}
    try:
        for kind, item in steps:
            if kind == STEP_TEMP_IN:
                if not result.temp_root:
                    result.temp_root = _make_temp_root(plan.base)
                staged = os.path.join(result.temp_root, uuid.uuid4().hex)
                _rename(item.old_abs, staged)
                result.records.append(RenameRecord(staged, item.old_abs, STEP_TEMP_IN))
                continue
            if kind == STEP_TEMP_OUT:
                source = _staged_of(result, item)
                if not source:
                    raise OSError("staged item missing")
                target = _target_of(item, plan.base, dir_final)
                _rename(source, target)
                result.records.append(RenameRecord(source, target, STEP_TEMP_OUT))
                continue
            source = _source_of(item, plan.base, dir_final)
            target = _target_of(item, plan.base, dir_final)
            _rename(source, target)
            result.records.append(RenameRecord(source, target, kind))
            if kind == STEP_DIR:
                dir_final[item.rel_old] = target
    except OSError as exc:
        result.status = RESULT_ABORTED
        result.failure_path = getattr(exc, "filename", "") or ""
        result.failure_error = str(getattr(exc, "strerror", "") or exc)
        result.failure_reason = "rename.error.rename_failed"
        rollback(result)
        _cleanup_temp(result.temp_root)
        result.temp_root = ""
        return result
    _cleanup_temp(result.temp_root)
    result.temp_root = ""
    if retarget is not None:
        retarget(result.moved_pairs())
    return result


def rollback(result):
    reverted = 0
    for record in reversed(result.records):
        if not os.path.lexists(record.target):
            continue
        if os.path.lexists(record.source):
            continue
        try:
            os.rename(record.target, record.source)
            reverted += 1
        except OSError:
            continue
    return reverted


def undo(records):
    reverted = 0
    failed = ""
    for record in reversed(records):
        if not os.path.lexists(record.target):
            failed = record.target
            break
        if os.path.lexists(record.source):
            failed = record.source
            break
        try:
            os.rename(record.target, record.source)
        except OSError:
            failed = record.target
            break
        reverted += 1
    return reverted, failed


def _parent_final(item, base, dir_final):
    rel_parent = _rel_parent(item.rel_old)
    if not rel_parent:
        return base
    mapped = dir_final.get(rel_parent)
    if mapped:
        return mapped
    return os.path.join(base, rel_parent.replace("/", os.sep))


def _rel_parent(rel):
    if "/" not in rel:
        return ""
    return rel.rsplit("/", 1)[0]


def _source_of(item, base, dir_final):
    parent = _parent_final(item, base, dir_final)
    return os.path.join(parent, item.old_leaf)


def _target_of(item, base, dir_final):
    parent = _parent_final(item, base, dir_final)
    return os.path.join(parent, item.new_leaf)


def _staged_of(result, item):
    for record in result.records:
        if record.kind == STEP_TEMP_IN and record.target == item.old_abs:
            return record.source
    return ""


def _rename(source, target):
    parent = os.path.dirname(target)
    if parent and not os.path.isdir(parent):
        raise OSError(2, "target parent missing")
    os.rename(source, target)


def _make_temp_root(base):
    root = os.path.join(base, TEMP_DIR_NAME, uuid.uuid4().hex)
    os.makedirs(root)
    return root


def _cleanup_temp(temp_root):
    if not temp_root:
        return
    shutil.rmtree(temp_root, ignore_errors=True)
    parent = os.path.dirname(temp_root)
    try:
        if parent and os.path.isdir(parent) and not os.listdir(parent):
            os.rmdir(parent)
    except OSError:
        pass