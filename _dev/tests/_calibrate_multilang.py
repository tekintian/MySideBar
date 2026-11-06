import unicodedata

W = (
    0x3040, 0x309F,
    0x30A0, 0x30FF,
    0x31F0, 0x31FF,
)


def _is_kana(ch):
    code = ord(ch)
    for lo, hi in (W[0:2], W[2:4], W[4:6]):
        if lo <= code <= hi:
            return True
    return False


def ratio(text):
    total = pua = kana = cjk = 0
    for ch in text:
        if ch in "\n\r\t ":
            continue
        total += 1
        code = ord(ch)
        if 0xE000 <= code <= 0xF8FF or 0xF0000 <= code <= 0x10FFFF:
            pua += 1
        if _is_kana(ch):
            kana += 1
        if 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF:
            cjk += 1
    if not total:
        return 0.0, 0.0, 0.0
    return pua / float(total), kana / float(total), cjk / float(total)


SAMPLES = {
    "gb_sentence": "这是一个简体中文的句子，用来测试编码判断是否正确。",
    "gb_long": (
        "编码判定是一个需要谨慎处理的问题，因为一旦判断错误，"
        "用户往往无法察觉，保存之后原文件就会永久损坏，且不可恢复。"
        "所以我们的策略是宁可漏判，也不可错判，把不确定的情况交还给用户。"
    ),
    "gb_punct": "—— … ・ 　",
    "big5_sentence": "這是一個繁體中文的長句子，用來測試編碼判斷是否正確。",
    "big5_long": (
        "編碼判定是一個需要謹慎處理的問題，因為一旦判斷錯誤，"
        "使用者往往無法察覺，儲存之後原檔案就會永久損壞，且無法復原。"
    ),
    "big5_short": "繁體測試",
    "sjis_sentence": "これは日本語の長い文章です。エンコーディングの判定が正しいかどうかをテストします。",
    "sjis_long": (
        "文字コードの判定は慎重に扱う必要があります。"
        "誤って判定した場合、利用者は気づかないまま保存してしまい、"
        "元のファイルが永久に壊れることがあります。"
    ),
    "sjis_short": "日本語テスト",
    "sjis_kana_only": "これはテストです",
}

PAIRS = (
    ("gb18030", "gb18030"),
    ("gb18030", "big5hkscs"),
    ("gb18030", "shift_jis_2004"),
    ("big5hkscs", "gb18030"),
    ("big5hkscs", "shift_jis_2004"),
    ("shift_jis_2004", "gb18030"),
    ("shift_jis_2004", "big5hkscs"),
)

print("legend: src=真实编码 cand=候选解码 pua/kana/cjk 均为占比")
print("")
print("%-14s %-16s %-16s %-6s %-6s %-6s %s" % ("sample", "src", "cand", "pua", "kana", "cjk", "status"))
for name, text in SAMPLES.items():
    for src, cand in PAIRS:
        try:
            raw = text.encode(src)
        except Exception:
            continue
        try:
            dec = raw.decode(cand, "strict")
        except Exception:
            continue
        pua, kana, cjk = ratio(dec)
        status = "OK" if src == cand else ("INTERCEPT" if pua > 0.02 else "PASS-THROUGH")
        print(
            "%-14s %-16s %-16s %-6.3f %-6.3f %-6.3f %s"
            % (name, src, cand, pua, kana, cjk, status)
        )
    print("")