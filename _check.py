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
    return plan_mod.PlanItem("", "", "", "", "")


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
    check("escape invalid", hit.status, plan_mod.STATUS_INVALID)
    check("escape reason", hit.reason, "rename.reason.escape")

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
    check("disk exists conflict", hit2.status, plan_mod.STATUS_CONFLICT)
    check("disk exists reason", hit2.reason, "rename.reason.exists_on_disk")

    skip = plan_mod.collect([root], opt(pattern="zzz", replacement="q", recursive=True))
    plan_mod.compute(skip, opt(pattern="zzz", replacement="q", recursive=True))
    plan_mod.validate(skip)
    hit3 = _pick(failures, "skip", skip, "keep.txt")
    check("unchanged skipped", hit3.status, plan_mod.STATUS_SKIPPED)

    cyc_root = tempfile.mkdtemp(prefix="mysidebar_cyc_")
    try:
        for name in ("x.txt", "y.txt"):
            with open(os.path.join(cyc_root, name), "w", encoding="utf-8") as fp:
                fp.write("x")
        swap = plan_mod.collect([cyc_root], opt(pattern="^x\.txt$", replacement="y.txt"))
        plan_mod.compute(swap, opt(pattern="^x\.txt$", replacement="y.txt"))
        plan_mod.validate(swap)
        sitem = _pick(failures, "swap", swap, "x.txt")
        check("swap one-way conflict", sitem.status, plan_mod.STATUS_CONFLICT)
        check("swap one-way reason", sitem.reason, "rename.reason.exists_on_disk")

        ring = plan_mod.collect([cyc_root], opt(pattern="x|y", replacement="__"))
        plan_mod.compute(ring, opt(pattern="x|y", replacement="__"))
        plan_mod.validate(ring)
        for name in ("x.txt", "y.txt"):
            ritem = _pick(failures, "ring %s" % name, ring, name)
            check("ring duplicate conflict %s" % name, ritem.status, plan_mod.STATUS_CONFLICT)

        ci = plan_mod.collect([cyc_root], opt(pattern="^x\.txt$", replacement="X.txt"))
        plan_mod.compute(ci, opt(pattern="^x\.txt$", replacement="X.txt"))
        plan_mod.validate(ci)
        citem = _pick(failures, "case", ci, "x.txt")
        check("case variant needs_temp", citem.needs_temp, True)
    finally:
        shutil.rmtree(cyc_root)

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

print("failures", len(failures))
for item in failures:
    print(item)