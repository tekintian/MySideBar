import ast
import os
import sys
import tempfile
import types


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

root = tempfile.mkdtemp(prefix="mini_")
for name in ("x.txt", "y.txt"):
    with open(os.path.join(root, name), "w", encoding="utf-8") as fp:
        fp.write("x")

opts = options.RenameOptions(pattern="^x\\.txt$", replacement="X.txt")
p = plan_mod.collect([root], opts)
plan_mod.compute(p, opts)
print("before", [(i.rel_old, i.rel_new, i.status, i.needs_temp) for i in p.items])
plan_mod.validate(p)
print("after", [(i.rel_old, i.rel_new, i.status, i.needs_temp, i.reason) for i in p.items])
print("same_variant", plan_mod._same_name_case_variant(p.items[0]) if p.items else "no items")