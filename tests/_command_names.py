import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CMDS = os.path.join(ROOT, "mysidebar", "cmds")

CLASS_RE = re.compile(r"class (MySidebar[A-Za-z]+?Command)[:(]")
COMMAND_RE = re.compile(r'"command"\s*:\s*"([^"]+)"')


def snake(name):
    return re.sub(r"([A-Z])", r"_\1", name).lower().lstrip("_")


registered = set()
for fn in sorted(os.listdir(CMDS)):
    if not fn.endswith(".py"):
        continue
    path = os.path.join(CMDS, fn)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = CLASS_RE.match(line.strip())
            if m:
                tail = m.group(1)[len("MySidebar"):-len("Command")]
                if tail:
                    registered.add("my_sidebar_" + snake(tail))

print("registered (%d)" % len(registered))
for c in sorted(registered):
    print("  " + c)

suffixes = (".sublime-menu", ".sublime-keymap", ".sublime-commands")
referenced = {}
for fn in sorted(os.listdir(ROOT)):
    if not fn.endswith(suffixes):
        continue
    with open(os.path.join(ROOT, fn), encoding="utf-8") as fh:
        for m in COMMAND_RE.finditer(fh.read()):
            referenced.setdefault(m.group(1), set()).add(fn)

print("\nreferenced (%d)" % len(referenced))
missing = [(c, sorted(f)) for c, f in sorted(referenced.items())
           if c.startswith("my_sidebar_") and c not in registered]
if missing:
    print("\nFAIL unresolved:")
    for c, f in missing:
        print("  %-42s %s" % (c, ", ".join(f)))
else:
    print("\nPASS every my_sidebar_* reference resolves")

unused = sorted(c for c in registered if c not in referenced)
if unused:
    print("\nregistered but unreferenced:")
    for c in unused:
        print("  " + c)