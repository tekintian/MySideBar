import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
TMP = os.path.join(ROOT, "tmp", "_probe1252")
shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP)

SAMPLES = {
    "gbk_common": "中文测试内容\n第二行\n特殊符号\n",
    "gbk_quotes": "他说：“你好”，还有‘引号’\n",
    "gbk_rare": "镕堃喆昇淼犇骉\n",
    "gbk_punct": "—— … ・ 　\n",
    "gbk_mixed": "abc123 中文 mixed 内容 456\n",
}

lines = []

for name, text in SAMPLES.items():
    raw = text.encode("gb18030")
    path = os.path.join(TMP, name + ".txt")
    with open(path, "wb") as fp:
        fp.write(raw)

    lines.append("[%s] raw=%r" % (name, raw[:40]))

    try:
        via1252 = raw.decode("cp1252")
    except Exception as exc:
        lines.append("  decode cp1252 -> FAIL %s" % exc)
        lines.append("  ROUNDTRIP_IMPOSSIBLE (1252 undefined byte)")
        continue

    lines.append("  decoded cp1252 = %r" % via1252[:40])

    try:
        back = via1252.encode("cp1252")
    except Exception as exc:
        lines.append("  encode back cp1252 -> FAIL %s" % exc)
        continue

    if back == raw:
        try:
            restored = back.decode("gb18030")
            ok = restored == text
        except Exception:
            ok = False
        lines.append("  ROUNDTRIP bytes identical = True, text restored = %s" % ok)
    else:
        lines.append("  ROUNDTRIP bytes identical = False")

shutil.rmtree(TMP, ignore_errors=True)
print("\n".join(lines))