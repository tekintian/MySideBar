import json
import os
import shutil
import tempfile
import time

from .. import platform as plat
from .execute import STEP_TEMP_IN

UNDO_OK = "ok"
UNDO_EMPTY = "empty"
UNDO_BLOCKED = "blocked"
UNDO_PARTIAL = "partial"

LOG_VERSION = 1
LOG_DIR_NAME = "MySideBar"
LOG_FILE_NAME = "rename_log.json"

MAX_AGE_SECONDS = 7 * 24 * 3600

RESULT_KEY_NONE = "rename.undo_none"
RESULT_KEY_CONFLICT = "rename.undo_conflict"
RESULT_KEY_FAILED = "rename.error.rename_failed"


class UndoOutcome(object):
    def __init__(self, status=UNDO_EMPTY, reverted=0, blocked_path="", reason_key="", reason_param=""):
        self.status = status
        self.reverted = reverted
        self.blocked_path = blocked_path
        self.reason_key = reason_key
        self.reason_param = reason_param

    def done(self):
        return self.status == UNDO_OK

    def moves(self):
        return list(getattr(self, "pairs", []))


def log_dir():
    base = _user_dir()
    path = os.path.join(base, LOG_DIR_NAME)
    try:
        os.makedirs(path)
    except OSError:
        if not os.path.isdir(path):
            return ""
    return path


def log_path():
    directory = log_dir()
    if not directory:
        return ""
    return os.path.join(directory, LOG_FILE_NAME)


def _user_dir():
    try:
        return plat.user_dir()
    except AttributeError:
        return os.path.join(tempfile.gettempdir(), LOG_DIR_NAME + "_user")


def build_entry(result, base, timestamp=None):
    ops = []
    for record in result.records:
        if record.kind == STEP_TEMP_IN:
            continue
        ops.append({"old": record.source, "new": record.target, "kind": record.kind})
    return {
        "version": LOG_VERSION,
        "timestamp": time.time() if timestamp is None else timestamp,
        "base": base,
        "ops": ops,
    }


def save_log(entry, path=None):
    if not entry or not entry.get("ops"):
        return False
    target = path or log_path()
    if not target:
        return False
    parent = os.path.dirname(target)
    try:
        if parent:
            os.makedirs(parent)
    except OSError:
        if not os.path.isdir(parent):
            return False
    tmp = target + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(entry, fp, ensure_ascii=False, indent=2)
        os.replace(tmp, target)
    except (OSError, TypeError, ValueError):
        _safe_remove(tmp)
        return False
    return True


def load_log(path=None, now=None):
    target = path or log_path()
    if not target or not os.path.isfile(target):
        return None
    try:
        with open(target, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    ops = data.get("ops")
    if not isinstance(ops, list) or not ops:
        return None
    for op in ops:
        if not isinstance(op, dict):
            return None
        if not op.get("old") or not op.get("new"):
            return None
    stamp = data.get("timestamp")
    if not isinstance(stamp, (int, float)):
        return None
    current = time.time() if now is None else now
    if current - stamp > MAX_AGE_SECONDS:
        return None
    return data


def clear_log(path=None):
    target = path or log_path()
    if not target:
        return False
    try:
        os.remove(target)
    except OSError:
        return False
    return True


def undo_last(path=None, retarget=None, now=None):
    entry = load_log(path, now=now)
    if not entry:
        return UndoOutcome(UNDO_EMPTY, reason_key=RESULT_KEY_NONE)
    ops = entry["ops"]
    blocked = _preflight(ops)
    if blocked:
        return UndoOutcome(
            UNDO_BLOCKED,
            blocked_path=blocked[0],
            reason_key=RESULT_KEY_CONFLICT,
            reason_param=blocked[0],
        )
    outcome = _run_undo(ops)
    if outcome.status == UNDO_OK:
        clear_log(path)
        if retarget is not None and outcome.pairs:
            retarget(outcome.pairs)
    return outcome


def _preflight(ops):
    for op in reversed(ops):
        old = op["old"]
        new = op["new"]
        if not os.path.lexists(new):
            return (new, RESULT_KEY_CONFLICT)
        if os.path.lexists(old) and not _same_entry(old, new):
            return (old, RESULT_KEY_CONFLICT)
    return None


def _same_entry(left, right):
    try:
        return os.path.samefile(left, right)
    except OSError:
        return plat.same_path(left, right)


def _run_undo(ops):
    reverted = 0
    pairs = []
    for op in reversed(ops):
        old = op["old"]
        new = op["new"]
        try:
            os.rename(new, old)
        except OSError as exc:
            outcome = UndoOutcome(
                UNDO_PARTIAL,
                reverted=reverted,
                blocked_path=new,
                reason_key=RESULT_KEY_FAILED,
                reason_param=str(getattr(exc, "strerror", "") or exc),
            )
            outcome.pairs = pairs
            return outcome
        reverted += 1
        pairs.append((new, old))
    outcome = UndoOutcome(UNDO_OK, reverted=reverted)
    outcome.pairs = pairs
    return outcome


def _safe_remove(path):
    try:
        os.remove(path)
    except OSError:
        return