import os
import shutil
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sublime_stub = types.ModuleType("sublime")
sublime_stub.version = lambda: "4173"
sys.modules["sublime"] = sublime_stub

pkg = types.ModuleType("mysidebar")
pkg.__path__ = [os.path.join(ROOT, "mysidebar")]
sys.modules["mysidebar"] = pkg


def load(name, filename=None):
    filename = filename or name
    path = os.path.join(ROOT, "mysidebar", filename + ".py")
    mod = types.ModuleType("mysidebar." + name)
    exec(compile(open(path, encoding="utf-8").read(), path, "exec"), mod.__dict__)
    sys.modules["mysidebar." + name] = mod
    setattr(pkg, name, mod)
    return mod


enc_mod = load("encodings")
detect_mod = load("encoding_detect")

failures = []


def check(label, got, expected):
    if got != expected:
        failures.append("%s: got %r expected %r" % (label, got, expected))


tmp = tempfile.mkdtemp(prefix="mysidebar_detect_")


def write(name, payload):
    path = os.path.join(tmp, name)
    with open(path, "wb") as fp:
        fp.write(payload)
    return path


try:
    sample = "中文测试内容\n第二行 abc\n特殊符号：— “引号”\n"

    utf8_path = write("utf8.txt", sample.encode("utf-8"))
    check("detect utf8", detect_mod.detect(utf8_path), enc_mod.UTF8)

    gb_path = write("gb.txt", sample.encode("gb18030"))
    check("detect gb18030", detect_mod.detect(gb_path), enc_mod.GB18030)

    gbk_path = write("gbk.txt", "简体中文测试".encode("gbk"))
    check("detect gbk as gb18030", detect_mod.detect(gbk_path), enc_mod.GB18030)

    bom_path = write("bom.txt", b"\xef\xbb\xbf" + sample.encode("utf-8"))
    check("detect bom utf8", detect_mod.detect(bom_path), enc_mod.UTF8)

    u16_path = write("u16.txt", sample.encode("utf-16-le"))
    detected = detect_mod.detect(u16_path)
    check("utf16 without bom not misread as gb", detected in (None, enc_mod.GB18030), True)

    u16bom = write("u16bom.txt", b"\xff\xfe" + sample.encode("utf-16-le"))
    check("detect utf16 bom", detect_mod.detect(u16bom), enc_mod.UTF16LE)

    bin_path = write("binary.dat", bytes([0, 1, 2, 3, 4, 5, 6, 7] * 200))
    check("skip binary", detect_mod.detect(bin_path), None)

    empty_path = write("empty.txt", b"")
    check("skip empty", detect_mod.detect(empty_path), None)

    ascii_path = write("ascii.txt", b"hello world\n")
    check("skip ascii", detect_mod.detect(ascii_path), None)

    check("missing file", detect_mod.detect(os.path.join(tmp, "nope.txt")), None)
    check("none path", detect_mod.detect(None), None)

    big_path = write("big.txt", b"a" * (detect_mod.MAX_BYTES + 1))
    check("skip oversize", detect_mod.detect(big_path), None)

    gbk_text = "中文".encode("gb18030")
    check("gb18030 not utf8-clean", detect_mod._clean_utf8(gbk_text), False)
    check("utf8 clean", detect_mod._clean_utf8("中文".encode("utf-8")), True)

    gb_long = "这是一个简体中文的句子，用来测试编码判断是否正确。" * 4
    zh_tw_long = "這是一個繁體中文的長句子，用來測試編碼判斷是否正確。" * 4
    sjis_long = "これは日本語の長い文章です。エンコーディングの判定が正しいかどうかをテストします。" * 4

    zh_long_path = write("zh_long.txt", gb_long.encode("gb18030"))
    check("zh_CN detects gb18030", detect_mod.detect(zh_long_path, "zh_CN"), enc_mod.GB18030)

    punct_path = write("punct.txt", "—— … ・ 　".encode("gb18030"))
    check("zh_CN keeps punctuation file", detect_mod.detect(punct_path, "zh_CN"), enc_mod.GB18030)

    big5_path = write("big5_long.txt", zh_tw_long.encode("big5hkscs"))
    check("zh_CN rejects big5 as pua noise", detect_mod.detect(big5_path, "zh_CN"), None)
    check("zh_TW detects big5", detect_mod.detect(big5_path, "zh_TW"), enc_mod.BIG5)

    sjis_path = write("sjis_long.txt", sjis_long.encode("shift_jis_2004"))
    check("ja_JP detects shift_jis", detect_mod.detect(sjis_path, "ja_JP"), enc_mod.SHIFT_JIS)
    check("KNOWN LIMIT: zh_CN misreads shift_jis", detect_mod.detect(sjis_path, "zh_CN"), enc_mod.GB18030)

    gb_on_big5_path = write("gb_on_big5.txt", zh_tw_long.encode("gb18030"))
    check("zh_TW rejects gb18030", detect_mod.detect(gb_on_big5_path, "zh_TW"), None)

    half_kana_path = write("big5_short.txt", "繁體測試的檔案".encode("big5hkscs"))
    check("ja_JP rejects big5 half-kana noise", detect_mod.detect(half_kana_path, "ja_JP"), None)
    check("zh_TW still detects short big5", detect_mod.detect(half_kana_path, "zh_TW"), enc_mod.BIG5)
    check("zh_CN rejects short big5 as pua noise", detect_mod.detect(half_kana_path, "zh_CN"), None)

    tiny_path = write("big5_tiny.txt", "繁體".encode("big5hkscs"))
    check(
        "KNOWN LIMIT: zh_CN misreads tiny big5",
        detect_mod.detect(tiny_path, "zh_CN"),
        enc_mod.GB18030,
    )

    kata_path = write("sjis_kata.txt", "テストデータです".encode("shift_jis_2004"))
    check("ja_JP keeps katakana japanese", detect_mod.detect(kata_path, "ja_JP"), enc_mod.SHIFT_JIS)

    half_kana_real = write("sjis_half_kana.txt", "ﾃｽﾄﾃﾞｰﾀ".encode("shift_jis_2004"))
    check("KNOWN LIMIT: half-kana japanese rejected", detect_mod.detect(half_kana_real, "ja_JP"), None)

    ko_path = write("ko.txt", "한국어 테스트 문장입니다.".encode("euc_kr"))
    check("ko_KR has no candidate", detect_mod.detect(ko_path, "ko_KR"), None)

    cache_path = write("cache.txt", gb_long.encode("gb18030"))
    first = detect_mod.detect(cache_path, "zh_CN")
    second = detect_mod.detect(cache_path, "zh_CN")
    check("cache stable", (first, second), (enc_mod.GB18030, enc_mod.GB18030))
    check("cache entry stored", (cache_path, "zh_CN") in detect_mod._cache, True)
    detect_mod.forget(cache_path)
    check("cache forget", (cache_path, "zh_CN") in detect_mod._cache, False)
    check("cache is locale scoped", detect_mod.detect(cache_path, "zh_CN"), enc_mod.GB18030)
    check("cache locale independence", detect_mod.detect(cache_path, "zh_TW"), None)

    check("ambiguous set refuses", len(enc_mod.auto_candidates("zh_TW")), 1)
    check("ko candidate set empty", len(enc_mod.auto_candidates("ko_KR")), 0)

finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("DETECT_FAILURES", len(failures))
for item in failures:
    print(item)