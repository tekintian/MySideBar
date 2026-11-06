import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

failures = []


def check(label, condition, detail=""):
    if condition:
        print("  PASS %s" % label)
    else:
        print("  FAIL %s %s" % (label, detail))
        failures.append(label)


SAMPLES = {
    "common": "中文测试内容\n第二行\n",
    "quotes": "他说：“你好”，还有‘引号’\n",
    "punct": "—— … ・ 　\n",
    "rare": "镕堃喆昇淼犇骉\n",
    "mixed": "abc123 中文 mixed 内容 456\n",
    "crlf": "第一行\r\n第二行\r\n",
}

work = tempfile.mkdtemp(prefix="mysidebar_roundtrip_")
print("workdir %s" % work)

for name, text in SAMPLES.items():
    path = os.path.join(work, name + ".txt")
    raw = text.encode("gb18030")
    with open(path, "wb") as fp:
        fp.write(raw)

    view_text = raw.decode("latin-1")

    recovered = view_text.encode("latin-1")
    check("%s latin1 byte channel" % name, recovered == raw)

    restored = recovered.decode("gb18030")
    check("%s decoded text" % name, restored == text, "%r != %r" % (restored, text))

    utf8_payload = restored.encode("utf-8")
    with open(path + ".utf8", "wb") as fp:
        fp.write(utf8_payload)

    with open(path + ".utf8", "rb") as fp:
        back_text = fp.read().decode("utf-8")
    reencoded = back_text.encode("gb18030")
    check("%s write back bytes" % name, reencoded == raw, "%r != %r" % (reencoded, raw))

    with open(path + ".gbk", "wb") as fp:
        fp.write(reencoded)
    with open(path, "rb") as a, open(path + ".gbk", "rb") as b:
        check("%s file identical after cycle" % name, a.read() == b.read())

import importlib.util
import types

pkg = types.ModuleType("mysidebar")
pkg.__path__ = [os.path.join(ROOT, "mysidebar")]
sys.modules["mysidebar"] = pkg


def _load(name, filename):
    path = os.path.join(ROOT, "mysidebar", filename)
    spec = importlib.util.spec_from_file_location("mysidebar." + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["mysidebar." + name] = module
    spec.loader.exec_module(module)
    return module


encodings_mod = _load("encodings", "encodings.py")
encoding_detect = _load("encoding_detect", "encoding_detect.py")

for name in SAMPLES:
    path = os.path.join(work, name + ".txt")
    detected = encoding_detect.detect(path)
    check("%s detect" % name, detected == "Chinese (GB18030)", repr(detected))

utf8_path = os.path.join(work, "utf8.txt")
with open(utf8_path, "wb") as fp:
    fp.write("中文 UTF-8\n".encode("utf-8"))
check("utf8 detect", encoding_detect.detect(utf8_path) == "UTF-8", repr(encoding_detect.detect(utf8_path)))

ascii_path = os.path.join(work, "ascii.txt")
with open(ascii_path, "wb") as fp:
    fp.write(b"plain ascii\n")
check("ascii detect", encoding_detect.detect(ascii_path) is None, repr(encoding_detect.detect(ascii_path)))

shutil.rmtree(work, ignore_errors=True)
print("LISTENER_RT_FAILURES %d" % len(failures))
sys.exit(1 if failures else 0)