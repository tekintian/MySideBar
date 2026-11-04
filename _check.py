import ast
import os
import shutil
import sys
import tempfile
import types


class PatchedOS(object):
    pass


def load_module(path, name):
    tree = ast.parse(open(path, encoding="utf-8").read())
    module = types.ModuleType(name)
    exec(compile(tree, path, "exec"), module.__dict__)
    return module


pkg = types.ModuleType("mysidebar")
pkg.__path__ = [os.path.abspath("mysidebar")]
sys.modules["mysidebar"] = pkg

i18n_stub = types.ModuleType("mysidebar.i18n")
i18n_stub.t = lambda key, **kw: key
sys.modules["mysidebar.i18n"] = i18n_stub
pkg.i18n = i18n_stub

platform_stub = types.ModuleType("mysidebar.platform")
platform_stub.normalize = lambda p: os.path.normpath(os.path.abspath(p))
sys.modules["mysidebar.platform"] = platform_stub
pkg.platform = platform_stub

batch = types.ModuleType("mysidebar.batch")
batch.__path__ = [os.path.abspath("mysidebar/batch")]
sys.modules["mysidebar.batch"] = batch
pkg.batch = batch

options = load_module("mysidebar/batch/options.py", "mysidebar.batch.options")
sys.modules["mysidebar.batch.options"] = options
batch.options = options

patterns = load_module("mysidebar/batch/patterns.py", "mysidebar.batch.patterns")
sys.modules["mysidebar.batch.patterns"] = patterns
batch.patterns = patterns

plan_mod = load_module("mysidebar/batch/plan.py", "mysidebar.batch.plan")
sys.modules["mysidebar.batch.plan"] = plan_mod
batch.plan = plan_mod

opt = options.RenameOptions
failures = list()


def check(name, actual, expected):
    if actual != expected:
        failures.append("%s: got %r expected %r" % (name, actual, expected))


def _pick(log, label, plan, wanted):
    for item in plan.items:
        if item.rel_old == wanted:
            return item
    log.append("%s: missing %s in %r" % (label, wanted, [i.rel_old for i in plan.items]))
    return None


class _Fallback(object):
    rel_old = ""
    rel_new = ""
    status = "missing"
    reason = "missing"
    needs_temp = None
    new_abs = ""


def _attr(item, name):
    if item is None:
        return getattr(_Fallback, name)
    return getattr(item, name)


root = tempfile.mkdtemp(prefix="mysidebar_t12_")
try:
    os.makedirs(os.path.join(root, "a", "b"))
    for rel in ("a/one.txt", "a/two.txt", "a/b/three.txt", "keep.txt"):
        with open(os.path.join(root, rel), "w", encoding="utf-8") as fp:
            fp.write("x")

    p = plan_mod.collect([root], opt(pattern="o", replacement="0", recursive=True))
    check("collect base", p.base, root)
    check("collect recursive count", len(p.items), 4)
    check("collect has subdir file", any(i.rel_old == "a/b/three.txt" for i in p.items), True)
    check("collect sample", sorted(i.rel_old for i in p.items), ["a/b/three.txt", "a/one.txt", "a/two.txt", "keep.txt"])

    p2 = plan_mod.collect([root], opt(pattern="o", replacement="0", recursive=False))
    check("collect non recursive count", len(p2.items), 1)

    p3 = plan_mod.collect([root], opt(pattern="o", replacement="0", recursive=True, include_dirs=True))
    check("collect include dirs", any(i.kind == "dir" for i in p3.items), True)

    p4 = plan_mod.compute(p3, opt(pattern="o", replacement="0", recursive=True, include_dirs=True))
    plan_mod.validate(p4)
    check("validate ok statuses", p4.counts()[plan_mod.STATUS_OK] > 0, True)

    esc = plan_mod.collect([root], opt(pattern="one", replacement="../escape", recursive=True))
    plan_mod.compute(esc, opt(pattern="one", replacement="../escape", recursive=True))
    plan_mod.validate(esc)
    hit = _pick(failures, "esc", esc, "a/one.txt")
    check("escape invalid", _attr(hit, "status"), plan_mod.STATUS_INVALID)
    check("escape reason", _attr(hit, "reason"), "rename.reason.escape")

    dup = plan_mod.collect([root], opt(pattern=r"(one|two)", replacement="same", recursive=True))
    plan_mod.compute(dup, opt(pattern=r"(one|two)", replacement="same", recursive=True))
    plan_mod.validate(dup)
    duped = [i for i in dup.items if i.rel_old.startswith("a/") and i.rel_new == "a/same.txt"]
    if not duped:
        failures.append("duplicate lookup: %r" % [(i.rel_old, i.rel_new, i.status) for i in dup.items])
    check("duplicate conflict count", len([i for i in duped if i.status == plan_mod.STATUS_CONFLICT]), 2)
    check("duplicate reason", duped[0].reason if duped else "", "rename.reason.duplicate_target")

    with open(os.path.join(root, "a", "taken.txt"), "w", encoding="utf-8") as fp:
        fp.write("x")
    disk = plan_mod.collect([root], opt(pattern="one", replacement="taken", recursive=True))
    plan_mod.compute(disk, opt(pattern="one", replacement="taken", recursive=True))
    plan_mod.validate(disk)
    hit2 = _pick(failures, "disk", disk, "a/one.txt")
    check("disk exists conflict", _attr(hit2, "status"), plan_mod.STATUS_CONFLICT)
    check("disk exists reason", _attr(hit2, "reason"), "rename.reason.exists_on_disk")

    skip = plan_mod.collect([root], opt(pattern="zzz", replacement="q", recursive=True))
    plan_mod.compute(skip, opt(pattern="zzz", replacement="q", recursive=True))
    plan_mod.validate(skip)
    hit3 = _pick(failures, "skip", skip, "keep.txt")
    check("unchanged skipped", _attr(hit3, "status"), plan_mod.STATUS_SKIPPED)

    cyc_root = tempfile.mkdtemp(prefix="mysidebar_cyc_")
    try:
        for name in ("x.txt", "y.txt"):
            with open(os.path.join(cyc_root, name), "w", encoding="utf-8") as fp:
                fp.write("x")
        swap = plan_mod.collect([cyc_root], opt(pattern="^x\.txt$", replacement="y.txt"))
        plan_mod.compute(swap, opt(pattern="^x\.txt$", replacement="y.txt"))
        plan_mod.validate(swap)
        sitem = _pick(failures, "swap", swap, "x.txt")
        check("swap one-way conflict", _attr(sitem, "status"), plan_mod.STATUS_CONFLICT)
        check("swap one-way reason", _attr(sitem, "reason"), "rename.reason.exists_on_disk")

        ring = plan_mod.collect([cyc_root], opt(pattern="x|y", replacement="__"))
        plan_mod.compute(ring, opt(pattern="x|y", replacement="__"))
        plan_mod.validate(ring)
        for name in ("x.txt", "y.txt"):
            ritem = _pick(failures, "ring %s" % name, ring, name)
            check("ring duplicate conflict %s" % name, _attr(ritem, "status"), plan_mod.STATUS_CONFLICT)

    finally:
        shutil.rmtree(cyc_root)

    case_root = tempfile.mkdtemp(prefix="mysidebar_case_")
    try:
        with open(os.path.join(case_root, "x.txt"), "w", encoding="utf-8") as fp:
            fp.write("x")
        ci = plan_mod.collect([case_root], opt(pattern="x\.txt", replacement="X.txt"))
        plan_mod.compute(ci, opt(pattern="x\.txt", replacement="X.txt"))
        plan_mod.validate(ci)
        citem = _pick(failures, "case", ci, "x.txt")
        check("case variant status", _attr(citem, "status"), plan_mod.STATUS_OK)
        check("case variant needs_temp", _attr(citem, "needs_temp"), True)
    finally:
        shutil.rmtree(case_root)

    sym_root = tempfile.mkdtemp(prefix="mysidebar_sym_")
    try:
        with open(os.path.join(sym_root, "real.txt"), "w", encoding="utf-8") as fp:
            fp.write("x")
        os.symlink(os.path.join(sym_root, "real.txt"), os.path.join(sym_root, "link.txt"))
        sp = plan_mod.collect([sym_root], opt(pattern="t", replacement="T", recursive=True))
        check("symlink skipped count", sp.skipped_symlinks, 1)
        check("symlink not in plan", any(i.rel_old == "link.txt" for i in sp.items), False)
    finally:
        shutil.rmtree(sym_root)

    single = plan_mod.collect([os.path.join(root, "a", "one.txt")], opt(pattern="one", replacement="uno"))
    check("single file base", single.base, os.path.join(root, "a"))
    check("single file rel", single.items[0].rel_old, "one.txt")

    seq = plan_mod.collect([os.path.join(root, "a")], opt(mode=options.MODE_SEQUENCE, prefix="f_", start=1, digits=2, recursive=True))
    plan_mod.compute(seq, opt(mode=options.MODE_SEQUENCE, prefix="f_", start=1, digits=2, recursive=True))
    names = [i.rel_new for i in seq.items]
    check("sequence unique", len(set(names)), len(names))
finally:
    shutil.rmtree(root)

execute_mod = load_module("mysidebar/batch/execute.py", "mysidebar.batch.execute")
sys.modules["mysidebar.batch.execute"] = execute_mod
batch.execute = execute_mod


def _run_plan(targets, opts):
    p = plan_mod.collect(targets, opts)
    plan_mod.compute(p, opts)
    plan_mod.validate(p)
    return p


def _listdir_rel(base):
    found = []
    for dirpath, dirnames, filenames in os.walk(base):
        for name in dirnames + filenames:
            full = os.path.join(dirpath, name)
            found.append(os.path.relpath(full, base).replace(os.sep, "/"))
    return sorted(found)


ex_root = tempfile.mkdtemp(prefix="mysidebar_t13_")
try:
    os.makedirs(os.path.join(ex_root, "sub"))
    for rel in ("a.txt", "b.txt", "sub/c.txt"):
        with open(os.path.join(ex_root, rel), "w", encoding="utf-8") as fp:
            fp.write("x")

    mixed = _run_plan([ex_root], opt(pattern="^(a|b)", replacement="z_$1", recursive=True))
    plan_mod.validate(mixed)
    steps = execute_mod.build_steps(mixed)
    kinds = [k for k, _ in steps]
    check("steps files only", kinds, [execute_mod.STEP_FILE, execute_mod.STEP_FILE])
    captured = {}
    res = execute_mod.execute(mixed, lambda pairs: captured.setdefault("pairs", pairs))
    check("execute status", res.status, execute_mod.RESULT_OK)
    check("execute records", len(res.records), 2)
    check("execute moved pairs", len(captured.get("pairs", [])), 2)
    check("execute tree", _listdir_rel(ex_root), ["sub", "sub/c.txt", "z_a.txt", "z_b.txt"])
    zpath = os.path.join(ex_root, "z_a.txt")
    check("execute contents kept", open(zpath, encoding="utf-8").read() if os.path.exists(zpath) else "missing", "x")
    check("execute temp cleaned", os.path.isdir(os.path.join(ex_root, plan_mod.TEMP_DIR_NAME)), False)

    back, failed = execute_mod.undo(res.records)
    check("undo reverted", back, 2)
    check("undo no failure", failed, "")
    check("undo tree", _listdir_rel(ex_root), ["a.txt", "b.txt", "sub", "sub/c.txt"])

    dirp = _run_plan([ex_root], opt(pattern="^sub$", replacement="s2", recursive=True, include_dirs=True))
    plan_mod.validate(dirp)
    steps2 = execute_mod.build_steps(dirp)
    check("dir before file", [k for k, _ in steps2][0], execute_mod.STEP_DIR)
    res2 = execute_mod.execute(dirp)
    check("dir execute status", res2.status, execute_mod.RESULT_OK)
    check("dir execute tree", _listdir_rel(ex_root), ["a.txt", "b.txt", "s2", "s2/c.txt"])

    ring2 = _run_plan([os.path.join(ex_root, "a.txt"), os.path.join(ex_root, "b.txt")], opt(pattern="", replacement=""))
    plan_mod.validate(ring2)
    check("ring plan actionable empty", len(ring2.actionable()), 0)

    swap_root = tempfile.mkdtemp(prefix="mysidebar_t13swap_")
    try:
        for name in ("x.txt", "y.txt"):
            with open(os.path.join(swap_root, name), "w", encoding="utf-8") as fp:
                fp.write(name)
        ringopts = opt(mode=options.MODE_REGEX, pattern="^(x|y)\\.txt$", replacement="$1_swapped.txt", recursive=True)
        rp = _run_plan([swap_root], ringopts)
        plan_mod.validate(rp)
        check("swap plan ok", len(rp.actionable()), 2)
        rres = execute_mod.execute(rp)
        check("swap execute status", rres.status, execute_mod.RESULT_OK)
        check("swap tree", _listdir_rel(swap_root), ["x_swapped.txt", "y_swapped.txt"])
        xpath = os.path.join(swap_root, "x_swapped.txt")
        check("swap x content", open(xpath, encoding="utf-8").read() if os.path.exists(xpath) else "missing", "x.txt")
    finally:
        shutil.rmtree(swap_root)

    case_root = tempfile.mkdtemp(prefix="mysidebar_t13case_")
    try:
        with open(os.path.join(case_root, "readme.md"), "w", encoding="utf-8") as fp:
            fp.write("body")
        copts = opt(pattern="^readme\\.md$", replacement="README.md", recursive=True)
        cp = _run_plan([case_root], copts)
        plan_mod.validate(cp)
        check("case needs temp", cp.actionable()[0].needs_temp, True)
        cres = execute_mod.execute(cp)
        check("case execute status", cres.status, execute_mod.RESULT_OK)
        check("case tree", _listdir_rel(case_root), ["README.md"])
        upath = os.path.join(case_root, "README.md")
        check("case content", open(upath, encoding="utf-8").read() if os.path.exists(upath) else "missing", "body")
        check("case temp cleaned", os.path.isdir(os.path.join(case_root, plan_mod.TEMP_DIR_NAME)), False)
    finally:
        shutil.rmtree(case_root)

    fail_root = tempfile.mkdtemp(prefix="mysidebar_t13fail_")
    try:
        for name in ("m1.txt", "m2.txt"):
            with open(os.path.join(fail_root, name), "w", encoding="utf-8") as fp:
                fp.write(name)
        fopts = opt(pattern="m", replacement="n", recursive=True)
        fp_plan = _run_plan([fail_root], fopts)
        plan_mod.validate(fp_plan)
        orig_rename = os.rename
        state = {"calls": 0}

        def fake_rename(src, dst):
            state["calls"] += 1
            if state["calls"] == 2:
                raise OSError(13, "denied")
            return orig_rename(src, dst)

        os.rename = fake_rename
        try:
            fres = execute_mod.execute(fp_plan)
        finally:
            os.rename = orig_rename
        check("fail aborted", fres.status, execute_mod.RESULT_ABORTED)
        check("fail reason", fres.failure_reason, "rename.error.rename_failed")
        check("fail rolled back tree", _listdir_rel(fail_root), ["m1.txt", "m2.txt"])
        check("fail temp cleaned", os.path.isdir(os.path.join(fail_root, plan_mod.TEMP_DIR_NAME)), False)
    finally:
        shutil.rmtree(fail_root)
finally:
    shutil.rmtree(ex_root)

rb_mod = load_module("mysidebar/batch/rollback.py", "mysidebar.batch.rollback")
sys.modules["mysidebar.batch.rollback"] = rb_mod
batch.rollback = rb_mod

rb_root = tempfile.mkdtemp(prefix="mysidebar_t14_")
try:
    log_file = os.path.join(rb_root, "rename_log.json")
    work = os.path.join(rb_root, "work")
    os.makedirs(work)
    for name in ("a.txt", "b.txt"):
        with open(os.path.join(work, name), "w", encoding="utf-8") as fp:
            fp.write(name)

    uopts = opt(pattern="\\.txt$", replacement=".md", recursive=True)
    up = _run_plan([work], uopts)
    plan_mod.validate(up)
    ures = execute_mod.execute(up, record_log=False)
    check("undo exec status", ures.status, execute_mod.RESULT_OK)
    check("undo exec tree", _listdir_rel(work), ["a.md", "b.md"])

    entry = rb_mod.build_entry(ures, up.base, timestamp=1000.0)
    check("undo entry ops count", len(entry["ops"]), 2)
    check("undo entry no temp op", any(o["kind"] == execute_mod.STEP_TEMP_IN for o in entry["ops"]), False)
    check("undo entry old first", entry["ops"][0]["old"], os.path.join(work, "a.txt"))
    check("undo save", rb_mod.save_log(entry, log_file), True)

    loaded = rb_mod.load_log(log_file, now=1000.0)
    check("undo load ok", isinstance(loaded, dict), True)
    check("undo load ops", len(loaded["ops"]) if loaded else 0, 2)

    check("undo stale dropped", rb_mod.load_log(log_file, now=1000.0 + rb_mod.MAX_AGE_SECONDS + 10), None)

    grabbed = []
    out = rb_mod.undo_last(log_file, retarget=lambda pairs: grabbed.append(pairs), now=1000.0)
    check("undo outcome status", out.status, rb_mod.UNDO_OK)
    check("undo outcome count", out.reverted, 2)
    check("undo tree restored", _listdir_rel(work), ["a.txt", "b.txt"])
    check("undo content kept", open(os.path.join(work, "a.txt"), encoding="utf-8").read(), "a.txt")
    check("undo retarget pairs", sorted(grabbed[0]) if grabbed else [], [(os.path.join(work, "a.md"), os.path.join(work, "a.txt")), (os.path.join(work, "b.md"), os.path.join(work, "b.txt"))])
    check("undo log cleared", rb_mod.load_log(log_file, now=1000.0), None)

    check("undo none", rb_mod.undo_last(log_file, now=1000.0).status, rb_mod.UNDO_EMPTY)

    for name in ("c.txt", "d.txt"):
        with open(os.path.join(work, name), "w", encoding="utf-8") as fp:
            fp.write(name)
    bp = _run_plan([os.path.join(work, "c.txt"), os.path.join(work, "d.txt")], opt(pattern="\\.txt$", replacement=".md"))
    plan_mod.validate(bp)
    bres = execute_mod.execute(bp, record_log=False)
    check("undo block exec", bres.status, execute_mod.RESULT_OK)
    bentry = rb_mod.build_entry(bres, bp.base, timestamp=2000.0)
    rb_mod.save_log(bentry, log_file)
    with open(os.path.join(work, "c.txt"), "w", encoding="utf-8") as fp:
        fp.write("squatter")
    before_tree = _listdir_rel(work)
    bout = rb_mod.undo_last(log_file, now=2000.0)
    check("undo blocked status", bout.status, rb_mod.UNDO_BLOCKED)
    check("undo blocked path", bout.blocked_path, os.path.join(work, "c.txt"))
    check("undo blocked reason", bout.reason_key, "rename.undo_conflict")
    check("undo blocked untouched", _listdir_rel(work), before_tree)
    check("undo blocked keeps log", rb_mod.load_log(log_file, now=2000.0) is not None, True)

    check("undo corrupt log", rb_mod.load_log(os.path.join(rb_root, "missing.json"), now=2000.0), None)
    broken = os.path.join(rb_root, "broken.json")
    with open(broken, "w", encoding="utf-8") as fp:
        fp.write("{not json")
    check("undo broken parsed", rb_mod.load_log(broken, now=2000.0), None)

    check("undo empty entry rejected", rb_mod.save_log({"ops": []}, os.path.join(rb_root, "empty.json")), False)
    check("undo clear log", rb_mod.clear_log(log_file), True)
finally:
    shutil.rmtree(rb_root)

ui_pkg = types.ModuleType("mysidebar.ui")
ui_pkg.__path__ = [os.path.abspath("mysidebar/ui")]
sys.modules["mysidebar.ui"] = ui_pkg
pkg.ui = ui_pkg

pv_mod = load_module("mysidebar/ui/preview_model.py", "mysidebar.ui.preview_model")
sys.modules["mysidebar.ui.preview_model"] = pv_mod
ui_pkg.preview_model = pv_mod

pv_root = tempfile.mkdtemp(prefix="mysidebar_t15_")
try:
    work = os.path.join(pv_root, "work")
    os.makedirs(work)
    for name in ("a.txt", "b.txt", "c.log"):
        with open(os.path.join(work, name), "w", encoding="utf-8") as fp:
            fp.write(name)

    pp = _run_plan([work], opt(pattern="^a\\.txt$", replacement="a.txt"))
    plan_mod.validate(pp)
    check("preview unchanged status", _pick(failures, "pv-unchanged", pp, "a.txt").status, plan_mod.STATUS_SKIPPED)

    qp = _run_plan([work], opt(pattern="\\.txt$", replacement=".log"))
    plan_mod.validate(qp)
    rows = pv_mod.lines_for(qp, i18n_stub.t)
    check("preview row count", len(rows), 3)
    check("preview row ok label", rows[0].endswith("[ok]"), True)
    check("preview all ok", [i.status for i in qp.items], [plan_mod.STATUS_OK, plan_mod.STATUS_OK, plan_mod.STATUS_SKIPPED])

    clashing = _run_plan([work], opt(pattern="^\\.(txt|log)$", replacement=".same"))
    plan_mod.validate(clashing)
    cstatus = [i.status for i in clashing.items]
    check("preview clash has dup", plan_mod.STATUS_CONFLICT in cstatus or plan_mod.STATUS_SKIPPED in cstatus, True)
    check("preview clash skipped summary", pv_mod.summary_text(clashing, "total={total}").startswith("total=3"), True)

    summ = pv_mod.summary_text(qp, "total={total} ok={ok} skipped={skipped} conflict={conflict} invalid={invalid}")
    counts = qp.counts()
    check("preview summary total", "total=%d" % len(qp.items), summ.split()[0])
    check("preview summary skipped", "skipped=%d" % counts.get(plan_mod.STATUS_SKIPPED, 0), summ.split()[2])

    pick_all = pv_mod.selected_indexes(qp, [0, 1, 2])
    check("preview select all actionable", len(pick_all), len(qp.actionable()))
    pick_none = pv_mod.selected_indexes(qp, [])
    check("preview select none", pick_none, [])
    pick_one = pv_mod.selected_indexes(qp, [0])
    check("preview select single", len(pick_one), 1 if qp.items[0].status == plan_mod.STATUS_OK else 0)

    sub = pv_mod.subset_plan(qp, pick_all)
    check("preview subset base", sub.base, qp.base)
    check("preview subset items", len(sub.items), len(pick_all))
    check("preview subset symlinks", sub.skipped_symlinks, qp.skipped_symlinks)

    fixed = _run_plan([work], opt(pattern="^a\.txt$", replacement="z_a.txt"))
    plan_mod.validate(fixed)
    frow = pv_mod.line_for(_pick(failures, "pv-fixed", fixed, "a.txt"), "rename.reason.unchanged")
    check("preview reason suffix", frow.endswith("rename.reason.unchanged"), True)
    check("preview arrow shape", " -> " in frow, True)
finally:
    shutil.rmtree(pv_root)

print("failures", len(failures))
for item in failures:
    print(item)