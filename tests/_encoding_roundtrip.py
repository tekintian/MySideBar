import os
import shutil
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sublime_stub = types.ModuleType("sublime")
sublime_stub.version = lambda: "4173"
sublime_stub.Region = lambda a, b: (a, b)
sys.modules["sublime"] = sublime_stub

pkg = types.ModuleType("mysidebar")
pkg.__path__ = [os.path.join(ROOT, "mysidebar")]
sys.modules["mysidebar"] = pkg

enc_src = open(os.path.join(ROOT, "mysidebar", "encodings.py"), encoding="utf-8").read()
enc_mod = types.ModuleType("mysidebar.encodings")
exec(compile(enc_src, "encodings.py", "exec"), enc_mod.__dict__)
sys.modules["mysidebar.encodings"] = enc_mod
pkg.encodings = enc_mod

failures = []


def check(label, got, expected):
    if got != expected:
        failures.append("%s: got %r expected %r" % (label, got, expected))


SAMPLE = "中文测试内容\n第二行 abc 123\n特殊符号：— “引号” ·\n"


def simulate(source_name, target_name, raw):
    source_codec = enc_mod.py_codec(source_name)
    target_codec = enc_mod.py_codec(target_name)
    if not source_codec or not target_codec:
        return None, "no codec"
    try:
        text = raw.decode(source_codec)
    except Exception as exc:
        return None, "decode: %s" % exc
    try:
        payload = text.encode(target_codec)
    except Exception as exc:
        return None, "encode: %s" % exc
    return payload, text


cases = [
    (enc_mod.UTF8, enc_mod.GB18030),
    (enc_mod.GB18030, enc_mod.UTF8),
    (enc_mod.UTF8, enc_mod.UTF16LE),
    (enc_mod.UTF16LE, enc_mod.UTF8),
]

for source_name, target_name in cases:
    raw = SAMPLE.encode(enc_mod.py_codec(source_name))
    payload, text = simulate(source_name, target_name, raw)
    check("simulate %s->%s" % (source_name, target_name), payload is not None, True)
    if payload is None:
        continue
    check("text preserved %s->%s" % (source_name, target_name), text, SAMPLE)
    back = payload.decode(enc_mod.py_codec(target_name))
    check("roundtrip text %s->%s" % (source_name, target_name), back, SAMPLE)

payload, _ = simulate(enc_mod.UTF8, enc_mod.GB18030, SAMPLE.encode("utf-8"))
check("gb18030 distinct bytes", payload != SAMPLE.encode("utf-8"), True)

payload, err = simulate(enc_mod.UTF8, enc_mod.GB18030, SAMPLE.encode("utf-16-le"))
check("wrong source rejected", payload is None, True)

wrong_target = simulate("nonexistent", enc_mod.UTF8, b"x")
check("unknown source rejected", wrong_target[0], None)

tmp = tempfile.mkdtemp(prefix="mysidebar_enc_")
path = os.path.join(tmp, "sample.txt")
try:
    open(path, "wb").write(SAMPLE.encode("utf-8"))
    payload, _ = simulate(enc_mod.UTF8, enc_mod.GB18030, open(path, "rb").read())
    open(path, "wb").write(payload)
    reopened = open(path, "rb").read().decode("gb18030")
    check("file roundtrip gb18030", reopened, SAMPLE)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("ENCODING_FAILURES", len(failures))
for item in failures:
    print(item)