# Sublime Text 多语言编码乱码治理：从 GBK 误判到单一注册表驱动的完整技术复盘

> 环境：Sublime Text 4（build 4215）/ Python 3.14.6 / macOS
> 项目：MySideBar 自研插件
> 版本：v1.2（由 v1.0 GBK 专项方案泛化而来）
> 状态：已实测闭环，回归校验全绿

---

## 0. 写在前面：这篇要解决的不是"乱码"，是"能力盲区"

先摆结论：**非 UTF-8 文件在 ST 里打开乱码，从来不是配置问题，也不是插件 bug。** 它是三个独立能力盲区叠加的结果，任何只针对其中一层的补丁都会留下尾巴。

| 盲区 | 表现 | 责任方 |
|---|---|---|
| **ST 自动探测缺失** | 回退 Western (Windows 1252) | ST 内置探测器 |
| **ST 编码列表参数陷阱** | 菜单写 `gb18030`，实际不生效 | ST 命令参数约定 |
| **macOS 系统编辑器不支持** | 报"UTF-8 不适用" | Apple 文本编辑 |

第三项尤其容易被误判成"文件坏了"。我在复盘时实测确认了这一点，后文给出数据。

### 0.1 v1.0 → v1.2 的演进边界

v1.0 只解决简体中文（GBK/GB18030）一个场景。v1.2 把同一套方法论扩展到 **Big5 / Shift_JIS**，并明确划出不做的部分。这次不是"加几个编码"，而是把散落的编码元数据收敛成**单一注册表**，再在它的约束下做自动探测。范围的扩大与边界的收缩，是同一件事的两面：

| 维度 | v1.0 | v1.2 |
|---|---|---|
| 覆盖编码 | GB18030 | GB18030 / Big5 / Shift_JIS（+ UTF-8 / UTF-16 系列） |
| 编码元数据 | 分散在多处常量 | 收敛为 `encodings` 单一注册表 |
| 自动探测 | 固定 GB18030 兜底 | 按 locale 精确映射，**单候选**才自动执行 |
| 状态栏 | 无 | 常驻显示当前文件编码 |
| 已知局限 | 未显式记录 | 全部固化为带 `KNOWN LIMIT` 的回归用例 |

---

## 1. 现象还原：日志说了什么

打开一个 GB18030 文件，ST 控制台依次输出：

```
unable to auto detect encoding for /path/ahead_gb18030.txt, using fallback encoding Western (Windows 1252)
[MySideBar] reopen /path/ahead_gb18030.txt as Chinese (GB18030)
reloading /path/ahead_gb18030.txt
```

这三行的顺序本身就是修复成功的证据链：

1. **第一行**证明 ST 探测失败并回退。这是 ST 的能力边界，不是我们能改的，只能接管。
2. **第二行**证明插件在探测失败后正确判定为 GB18030，并立即发起 `reopen`。
3. **第三行**证明 `reopen` 生效，且**只出现一次**，说明去重有效。

而在此之前，同样的操作会看到同一文件出现两条 `reopen` 日志，界面还会"闪一下乱码"。这两个问题的根因完全不同，下面逐个拆。

---

## 2. 方案演进：五版实现，每一版都被实测推翻

这个功能最终定型前，经历了五版实现。记录下来，因为**每一版都是被实测数据否掉的，不是被直觉否掉的**。

| 版本 | 核心技术 | 被否决原因 |
|---|---|---|
| v1 | `set_encoding` + `revert` | `revert` 让 ST 重新探测，又退回 1252 |
| v2 | `set_encoding` + `view.replace` | set_encoding 后 ST 把写入的 UTF-8 文本按 GB18030 重新解释，仍是乱码 |
| v3 | 临时文件 `.dump` 中转 | 污染目录，有误删风险（参考 `sublime-gbk-support` 的遗留问题） |
| v4 | `reopen` + `view.id()` 去重 | reopen 触发重载后 view.id 变化，绕过判断，重复 reopen |
| v5 | `reopen` + 文件路径去重 + 双入口 | **当前版本，实测定型** |

其中 v3 那次值得多说一句。`_res/sublime-gbk-support` 的思路是写临时 `.dump` 文件再重命名替换，这在国内插件里流传很广。但它有两个硬伤：临时文件会污染项目目录；进程被杀时残留的文件可能误伤真实文件。这个方案被我彻底放弃，最终走的是**纯视图级操作，磁盘字节零改动**。

---

## 3. 关键技术点一：reopen 参数必须用界面显示名

这是最容易踩、也最隐蔽的坑。

ST 的 `Encoding.sublime-menu` 里，GB18030 对应的参数写的是：

```json
{"command": "reopen", "args": {"encoding": "gb18030"}}
```

但**实测这个参数无效**。ST 真正接受的是界面显示名：

```python
REOPEN_ARGS = {
    GB18030: "Chinese (GB18030)",
    UTF8: "UTF-8",
    UTF16LE: "UTF-16 LE",
    UTF16BE: "UTF-16 BE",
}
```

这个差异没有任何文档说明，只能靠实测发现。写错参数的表现是：`reopen` 命令执行成功、无报错、但编码没变。

对应实现：[encodings.py](../src/mysidebar/encodings.py)

```python
def reopen_view(view, name):
    if view is None or name is None:
        return False
    arg = reopen_arg(name)
    if arg is None:
        return False
    try:
        if not view.is_valid():
            return False
        view.run_command("reopen", {"encoding": arg})
    except Exception:
        return False
    return True
```

把所有 reopen 调用收敛到这一个入口，避免各处参数不一致——这个教训来自 doctor 命令：它的诊断代码里还留着早已废弃的 `view.set_encoding()`，属于典型的死逻辑残留，后来一并清理。

---

## 4. 关键技术点二：闪烁是时序问题，不是探测问题

这是整个方案里最有价值的发现。

### 4.1 两个回调的严格时序

ST 的视图加载有两个回调，先后顺序是硬约束：

| 回调 | 时机 | 能否避免闪烁 |
|---|---|---|
| `on_load` | **同步**阶段，早于首次渲染 | ✅ 可以 |
| `on_load_async` | **异步**阶段，晚于首次渲染 | ❌ 必然闪 |

旧实现只挂在 `on_load_async`，并 `set_timeout` 延迟 60ms。这就意味着：1252 乱码文本**先渲染上屏**，60ms 后才 reopen 修正。视觉上就是"闪一下"。

### 4.2 修复：同步入口抢先

拆成双入口，`on_load` 阶段如果视图已加载完毕，**同步立即 reopen，不等任何定时器**：

```python
def on_load(self, view):
    self._kick(view, immediate=True)

def on_load_async(self, view):
    self._kick(view, immediate=False)

def _kick(self, view, immediate):
    ...
    if immediate and not view.is_loading():
        self._inspect(view, key, 0)
        return
    sublime.set_timeout(lambda: self._inspect(view, key, 0), SETTLE_DELAY)
```

对应实现：[listener.py](../src/mysidebar/listener.py)

这个判断的关键前提是 `view.is_loading()`。如果 `on_load` 阶段仍在加载，就不能同步操作，得退回延迟重试。而**实测结果证实**：在 ST 4215 打开本地文件时，`on_load` 阶段 `is_loading()` 已为 False，同步 reopen 成立，闪烁消除。

即便仍有少量情况下 `is_loading()` 为 True，还有 `SETTLE_LIMIT = 20` 的重试上限兜底，不会因反复重试栈溢出。

---

## 5. 关键技术点三：去重的三轮迭代

`reopen` 会触发文件重新载入，而重新载入**又会再次触发 `on_load_async`**。这是一个天然的循环陷阱。

三代去重实现对照：

| 版本 | 去重依据 | 为什么失败 |
|---|---|---|
| 1 | `view.id()` | reopen 重载后 id 变化，旧 id 失效，判断被绕过 |
| 2 | 路径 key + `view.encoding()` 比对 | reopen 未完成时 `encoding()` 仍是旧值，比对落空 |
| 3 | **只认路径 key** | 稳定，实测定型 |

**最终实现的关键决策：去重只看路径，不看 `encoding()`。**

原因很直接：`reopen` 是异步生效的，刚发起时 `view.encoding()` 还没变。如果拿它做判断依据，就会出现"我以为已经处理好了，其实还没生效"的假象。路径是唯一在 reopen 前后保持稳定的标识。

双重拦截点：

```python
# _kick 入口
if key in _handled:
    return

# _inspect 入口
if key in _handled:
    _clear_pending(key)
    return
```

此外还有三个配套的清理点，缺任何一个都会出问题：

| 清理点 | 缺失后果 |
|---|---|
| `on_close` → `_forget(key)` | 关档后重新打开，因旧 key 残留被跳过，永远不再处理 |
| reopen 成功后**立即** `_clear_pending` | 若等 verify 结束才清，verify 被阻断会让该文件永久卡住 |
| `VERIFY_LIMIT` 校验上限 | 校验重试无上限 |

---

## 6. 关键技术点四：探测逻辑与一个被数据推翻的设计

### 6.1 探测优先级

```python
def _detect_uncached(path, locale):
    raw = _read(path)
    if raw is None:
        return None
    bom = encodings.bom(raw)          # 1. BOM 优先
    if bom is not None:
        return bom
    if _looks_binary(raw):            # 2. 二进制跳过
        return None
    if _pure_ascii(raw):              # 3. 纯 ASCII 跳过（不做事倍功半的 reopen）
        return None
    if _clean_utf8(raw):              # 4. UTF-8 严格校验
        return encodings.UTF8
    candidates = encodings.auto_candidates(locale)   # 5. 单候选兜底
    return _trusted(raw, candidates[0]) if len(candidates) == 1 else None
```

对应实现：[encoding_detect.py](../src/mysidebar/encoding_detect.py)

### 6.1.1 第 5 级为什么要"单候选守卫"

v1.0 的第 5 级是硬编码的 `_trusted_gb18030(raw)`。要在不引入第三方依赖的前提下支持多种语言，最直觉的做法是"把所有候选都试一遍，选可信度最高的"。**这个做法被实测否掉了**，因为它必然会遇到多候选同时可信的场面，那时无论怎么选都在赌。

于是把策略反过来：**只有当 locale 映射恰好给出 1 个 auto 候选时才执行，多候选直接返回 `None`。** 这样把"裁决"这个不可靠环节从代码里彻底删除了。

locale 到编码的映射必须**精确到编码名**，不能按"语言家族"泛化：

```python
LOCALE_CODECS = {
    "zh_CN": (GB18030,),
    "zh_SG": (GB18030,),
    "zh_TW": (BIG5,),
    "zh_HK": (BIG5,),
    "ja_JP": (SHIFT_JIS,),
    "ko_KR": (),
}

LOCALE_ALIASES = {
    "zh": "zh_CN",
    "zh_hans": "zh_CN",
    "zh_hant": "zh_TW",
    "ja": "ja_JP",
    "ko": "ko_KR",
}
```

这里踩过一个真实的坑：最初 `zh_CN` 写成"中文家族"（GB18030 + Big5），结果候选数恒为 2，`len == 1` 永假，**自动选码对所有简体中文用户完全失效**。改成按编码名精确命中后恢复正常。

`ko_KR` 显式给空元组，而不是留空回落到默认值——否则会莫名其妙地拿 GB18030 去猜韩文，属于典型的有害兜底。

`LOCALE_ALIASES` 处理的是 ST 实际给出的 locale 形态。ST 在小写、带 script 后缀等写法上并不统一（`zh_hans`、`zh_hant`），若只做精确匹配就会静默落回默认值。**静默回落是最危险的一类失败**：用户看到的是"功能没反应"，而不是"配置写错了"，排查成本极高。

### 6.2 一个被数据推翻了的设计（重要）

我最初给 GB18030 兜底加了一条"CJK 汉字占比 ≥ 30%"的门槛，想法是顺便解决 Big5 误判。**实测数据把这个设计直接否掉了：**

| 样本 | CJK 占比 | 结果 |
|---|---|---|
| 纯标点 GB18030（`—— … ・ 　`） | **0.0** | 被误杀 |

GB18030 文件里合法但不含汉字的内容太多了：全角标点、数学符号、制表符、装饰符号。加 CJK 门槛会漏判这批文件，而且立刻让既有回归测试挂掉。

**这说明一个道理：门槛加得越"聪明"，假阴性就越多。** 判别逻辑应该只否决那些**确定是坏解码**的情况，而不是要求内容"看起来像中文"。

### 6.3 真正有效的判别量：PUA 占比

用真实样本做数据标定，得到：

| 组合 | PUA 占比 | 未命名占比 |
|---|---|---|
| 标点 / 符号（真 GB18030） | 0.0 | 0.0 |
| 中文句子（GB18030） | 0.0 | 0.0 |
| **Big5 长句误按 GB18030** | **0.182** | 0.0 |
| Big5 短词误按 GB18030 | 0.0 | 无法区分 |

两个结论：

1. **PUA（私有区 U+E000–F8FF）占比是唯一有效的判别量**，阈值定 2%。
2. **"未命名占比"完全无效**，对 Big5 恒为 0，删掉。

最终判据只有一个：

```python
def _text_is_plausible(text):
    ...
    return pua / float(total) <= _PUA_RATIO_MAX
```

### 6.4 为什么这一步关乎数据安全，而不只是显示效果

这是整个方案里最容易被低估的一点。

Big5 文件被误判成 GB18030 后，**不会显示成一堆乱码**，而是显示成**看起来像中文、但内容完全错乱的文字**。用户完全察觉不到，一旦保存，原文件就**永久损坏**，且不可逆。

用 PUA 判据挡住这类**静默损坏**，比修乱码本身更有价值。

至于 4 个汉字以内的短 Big5，在字节层面与 GBK **本质不可分**，任何字节级算法都做不到。这种情况我们选择**不猜**，返回 `None` 交给 ST 原生处理。**宁可漏判，也不错判**——错判是数据丢失，漏判只是体验回退。

### 6.5 一个隐蔽的采样盲区

`_read` 最多读 512KB，但采样窗口只取 64KB。这就制造了一个盲区：**"前缀纯 ASCII + 后段全 Big5"** 的文件，前缀采样 PUA 为 0，会被误判。

修复思路是定位第一个非 ASCII 字节，回退到连续多字节段起点作为采样窗口：

```python
def _non_ascii_window(raw):
    if len(raw) <= _AMBIGUOUS_SAMPLE:
        return raw
    for index, byte in enumerate(raw):
        if byte >= 128:
            start = index
            while start > 0 and raw[start - 1] >= 128:
                start -= 1
            return raw[start : start + _AMBIGUOUS_SAMPLE]
    return raw[:_AMBIGUOUS_SAMPLE]
```

这里有个细节：不能简单按奇偶对齐（`index - index % 2`），因为无法从单点确定多字节字符的起始位。回退到「连续非 ASCII 段起点」才是稳妥做法，否则窗口起点落在字符中间，`strict` 解码会失败，进而把整个文件误拒。

### 6.6 唯一在新语言上生效的新判据：半角片假名占比

扩展到 Shift_JIS 时，我尝试了三种判据，两种被数据否掉：

| 判据 | 标定结果 | 结论 |
|---|---|---|
| 假名（全角）占比 | 真日文 0.00，Big5 误判也 0.00~0.18 | ❌ 无区分度 |
| 未分配码位占比 | 恒为 0 | ❌ 无效 |
| **半角片假名占比** | **真日文 0.00，Big5 误判 0.50 / 0.75** | ✅ 有效 |

原因是 Big5 双字节区大量码位会落到 Unicode 的 `U+FF66–FF9D`（半角片假名区，不含标点部分），而真正的日文源码/文档里几乎不会出现半角片假名。判据因此对 **Shift_JIS 独有生效**，阈值 0.30：

```python
def _half_kana_ratio(text):
    total = 0
    half = 0
    for char in text:
        if char in "\n\r\t":
            continue
        total += 1
        if 0xFF66 <= ord(char) <= 0xFF9D:
            half += 1
    if total == 0:
        return 0.0
    return half / float(total)


def _script_is_plausible(text, spec):
    if spec.py_codec == "shift_jis_2004":
        return _half_kana_ratio(text) <= _HALF_KANA_MAX
    return True
```

注意区间取 `0xFF66–FF9D` 而非整个 `FF61–FF9F`：后者包含半角标点（`｡｢｣､･`），而标点在正常日文中是常见的，纳入统计会抬高正常日文的误判率。

关键设计：**这条判据只挂在 Shift_JIS 分支上，不污染 GB18030 与 Big5 的主流程。** 这样它的收益是纯增量的，风险为零——即便阈值判断有偏差，也不会影响已验证的中文路径。

代价是**纯半角片假名日文**（如 `ﾃｽﾄﾃﾞｰﾀ`）会被自身判据拒绝，无法自动识别。这是刻意的取舍：这类文本在真实工程里极少，而放宽它会让所有 Big5 文件重新面临误判。

### 6.7 探测缓存

每次 `on_activated` 都读盘探测会产生明显 IO 开销，因此按 `(路径, locale)` 缓存结果，并用 mtime + size 做失效校验，上限 512：

```python
def detect(path, locale=None):
    key = os.path.normcase(os.path.abspath(path))
    stat = os.stat(key)
    cached = _cached((key, locale or ""), stat.st_mtime, stat.st_size)
    if cached is not _UNKNOWN:
        return cached
    result = _detect_uncached(key, locale)
    _remember((key, locale or ""), stat.st_mtime, stat.st_size, result)
    return result
```

三个配套点缺一不可：

| 配套点 | 缺失后果 |
|---|---|
| mtime + size 失效校验 | 保存后文件已变，仍返回旧结论 |
| `_UNKNOWN` 哨兵 | 用 `None` 表示"未缓存"时，无法区分"缓存了 None"和"没缓存"，会反复重算 |
| `forget(path)` 按路径批量清 | 文件关闭后缓存常驻，内存只增不减 |

`forget` 按**路径**而非 `(path, locale)` 清理：一个文件可能在多个 locale 下被探测过，只清当前 locale 会留下其他条目。路径统一做 `normcase + abspath`，避免同一文件因相对/绝对路径写法不同而命中两个缓存项。

---

## 7. 关键技术点五：状态栏常驻编码

用户需要随时知道"我现在看到的这堆字符，是按什么编码解释的"。实现挂在四个时机：

| 事件 | 动作 |
|---|---|
| `on_activated` | 切换标签页时刷新 |
| `on_post_save` | 保存后刷新（编码可能已被转换） |
| `on_load` | 加载完成后刷新 |
| 转换命令执行后 | 立即刷新 |

统一写入固定的 status key，避免重复堆叠：

```python
STATUS_KEY = "mysidebar_encoding"

def refresh_status(view):
    if view is None or not view.is_valid():
        return
    if _is_widget(view):
        return
    if not _status_bar_enabled():
        view.erase_status(STATUS_KEY)      # 关掉配置项时要主动清理残留
        return
    name = view.encoding()
    if not name:
        view.erase_status(STATUS_KEY)
        return
    view.set_status(STATUS_KEY, i18n.t("encoding.status_bar", encoding=name))
```

三个必须处理的边界：

1. **widget 视图**必须跳过。`find_in_files` 输出面板、输入框都不是真实文件，挂状态只会有害。
2. **`encoding()` 为空**时用 `erase_status` 清除，而不是写入空串——否则会残留一个空 status 项。
3. **配置项被关闭**时同样要 `erase_status`。这是最容易漏的一条：如果只在"开启"路径里写、在"关闭"时不清理，用户关掉开关后旧编码会一直挂在状态栏上，看起来像功能失效。

展示名直接取 `view.encoding()`，即 ST 自己的界面显示名（如 `Chinese (GB18030)`）。**不自己造一套命名**，好处是状态栏与实际生效的编码绝对一致，不可能出现"状态栏说 A、实际是 B"。

对应实现：[listener.py](../src/mysidebar/listener.py)


---

## 8. 边界实测：Emoji 与 GB18030 四字节区

这里有个意料之外的收获。

`ahead_gb18030.txt` 里有两个"扩展区字符"，实测发现它们是：

```
0x1f389  🎉
0x1f7e1  🟡
```

不是扩展汉字，而是 **Emoji**。它们走 GB18030 的**四字节编码区**（`0x81-0xFE 0x30-0x39 0x81-0xFE 0x30-0x39`）。

这一点很重要——很多实现只处理双字节区，遇到四字节区就会截断或漏判。而实测确认 `gb18030` 严格解码全程通过，四字节区完整覆盖。文件 76KB，往返编码无损。

这也修正了一个认知：**GB18030 不只是"GBK 的超集"，它是包含四字节扩展的完整编码体系**，连 Emoji 都能装进去。

---

## 9. 另一条结论：macOS 打不开是正常现象

这是复盘时顺手验证的一点，但值得单独说明，因为容易被误判为"文件坏了"。

用 macOS「文本编辑」打开 `ahead_gbk.txt`，报：

```
未能打开文稿"ahead_gbk.txt"。文本编码 Unicode (UTF-8) 不适用。
```

实测文件本身完全正确：

```
size = 9432
utf-8   -> 解码失败
gbk     -> 失败（第 315 字节，说明含 GB18030 扩展字符）
gb18030 -> 解码成功，首行「阿什拉夫科技阿德射流风机阿达算啦开发」
roundtrip_lossless = True
```

**结论：文件没问题，是 macOS「文本编辑」只支持 UTF-8 / UTF-16，根本不支持 GB18030。**

这里有一条必须守住的底线：**绝不能为了让系统编辑器能打开，就把文件改存成 UTF-8。** 那样会让 Windows 侧的 GBK 生态链（老旧系统、政务软件、报表工具）全部读成乱码。如果需要 macOS 侧也能用的版本，正确做法是**另存 UTF-8 副本**，原文保持 GB18030。

---

## 10. 最终架构

整套方案可以概括为六段链路，每段只做一件事：

```
注册表 →  encodings 单一事实来源（编码属性 / 分组 / locale 映射 / BOM）
       →  消费者只读接口，禁止各自定义常量

识别   →  BOM / 二进制 / ASCII 前置过滤
       →  UTF-8 严格校验优先
       →  locale 精确映射 + 单候选守卫（多候选一律返回 None）
       →  PUA 占比仲裁（防 Big5 静默损坏，全编码生效）
       →  半角片假名占比仲裁（防 Big5 误判 Shift_JIS，仅日文生效）
       →  非 ASCII 窗口采样（防前缀盲区）

转换   →  reopen 命令 + 界面显示名参数
       →  纯视图级操作，磁盘字节零改动
       →  目标编码列表由注册表驱动（含 Auto Detect 源编码项）

时序   →  on_load 同步入口，抢先于首帧渲染（消除闪烁）
       →  is_loading() 判定 + SETTLE_LIMIT 重试上限

去重   →  只认文件路径 key，不看 encoding()
       →  _kick / _inspect 双入口拦截
       →  on_close 清理 + reopen 成功即清 pending

缓存   →  (path, locale, mtime, size) 键 + LRU 512
       →  forget(path) 按路径批量清理

展示   →  on_activated / on_post_save / on_load 刷新状态栏
       →  widget 视图排除，空编码用 erase_status
```

---

## 11. 已知局限：显式记录，不静默兼容

一个探测方案的价值，不取决于它判对了多少，而取决于它有没有把判不了的情况说清楚。下列场景会返回 None（不自动转换，交回 ST 原生处理），或给出已知错误结论。它们不是待修 bug，而是宁可漏判、不错判原则在无有效判据时的必然取舍：

| # | 场景 | 行为 | 根因 |
|---|---|---|---|
| L1 | zh_CN 下打开 Shift_JIS 文件 | 误判为 GB18030 | 码位重合产生合法二级汉字；唯一有效判据因误杀生僻字而主动弃用 |
| L2 | zh_CN 下打开 2-4 字符的极小 Big5 | 误判为 GB18030 | PUA 统计样本不足，占比恰为 0 |
| L3 | ja_JP 下打开纯半角片假名日文 | 拒绝识别 | 被半角片假名判据自身拒绝 |
| L4 | ko_KR 下打开韩文文件 | 不识别 | 注册表显式留空，无可靠自动判据 |
| L5 | 任意语言下打开极短多字节文件 | 可能不识别 | 采样不足以构成统计判据 |

### L1 的结论是弃用，不是无解

zh_CN 下 Shift_JIS 被判为 GB18030。这个结论经过三轮完整复核，**「不自动修正」的结论成立，但必须先纠正一个错误的论证**：原文称「没有任何字面特征可以区分」，这个说法是**错的**。

**成因是码位空间重合。** Shift_JIS 的双字节区与 GBK 二级汉字区（`0xD8–0xF7`）大面积重叠，所以 Shift_JIS 日文被 GB18030 解码后，产物**100% 落在 GBK 二级汉字区**——13 组日文样本实测，一级汉字 0 个、二级汉字 196 个，无一例外：

| 样本 | 按 GB18030 解码结果 | PUA | 全角假名 | 半角假名 | 二级汉字占比 |
|---|---|---|---|---|---|
| これは日本語のテキストです。 | 偙傟偼擔杮岅偺僥僉僗僩偱偡丅 | 0.000 | 0.000 | 0.000 | **1.000** |
| 設定ファイルの説明を書いています | 愝掕僼傽僀儖偺愢柧傪彂偄偰偄傑偡 | 0.000 | 0.000 | 0.000 | **1.000** |

**「二级汉字占比」是一个真实有效的强判据**，而这正是原文漏测的一项：

| 样本类别 | 二级汉字占比 |
|---|---|
| 13 组 Shift_JIS 日文（zh_CN 视角误判产物） | **1.000（全部，无一例外）** |
| 10 类真实中文（技术文档 / 日志 / JSON / 新闻 / 古籍 / 成语 / 人名） | 0.000 ~ **0.298** |
| 繁体与简体混杂中文（较极端） | 0.500 |
| 纯生僻字字典（龘齉齾爩麤龗犇猋骉） | **1.000，与日文完全重合** |

存在 0.50 → 1.00 的清晰空档，阈值取 0.80 时：日文误判从 8/8 降为 0/8（收益），但纯生僻字中文会从「识别正确」变成「拒绝识别」（代价）。

### 为什么不采用这条判据

**否决理由是代价不可接受，不是没有信号。** 这条判据会误杀生僻字字典、古籍拓片、人名索引这类真实中文文件。本项目原则是「宁可漏判、不错判」，而更关键的是这两种错误的方向不对称：

- 错判 = 静默损坏：日文被当成中文显示，看着像正常中文，用户察觉不到，一旦保存源文件不可逆损坏；
- 漏判 = 体验回退：只是没自动转换，用户可用手动菜单修正。

若采用该判据，日文文件会从「错判」转为「漏判」——这是改善。但它同时把一类真实中文从「正确」打成「漏判或错判」，用确定的误伤换不确定的收益，**不划算，故主动放弃**。记录在此，是为了让后人知道这里有信号但不要采信，而不是因为这里没有信号。

### 已证伪的判据清单

为得到这个结论，下列判据被逐一实测。**必须区分「无区分度」与「有区分度但代价不可接受」两类**，否则后人会误以为汉字级判据全部无效而重复投入：

| 判据 | 日文误判样本 | 真实中文 | 否决类型 | 否决原因 |
|---|---|---|---|---|
| PUA 占比 | 0.000 | 0.000 | 无区分度 | 码位重合，产物不落 PUA |
| 全角假名占比 | 0.000 | 0.000 | 无区分度 | 产物全是汉字，无假名 |
| 半角片假名占比 | 0.000 | 0.000 | 无区分度 | 同上 |
| 一级汉字占比 | 0.000 | 0.000 ~ 1.000 | 误杀 | 与中文生僻字重叠，实测误杀 |
| GBK 可编码汉字占比 | 1.000 | 1.000 | 无区分度 | 一级二级合并后信号消失 |
| **二级汉字占比** | **1.000** | **0.000 ~ 0.298** | **误杀** | **有强区分度，但纯生僻字字典同为 1.000，采用即误伤真中文** |

其中「一级汉字占比」这条最值得记录，因为它一度看起来极其可行：

| 样本 | 一级占比 |
|---|---|
| Shift_JIS 误判产物 | 0.000 |
| 普通中文 | 0.909 ~ 1.000 |

表面上完美分离。但一测合法生僻字立刻崩掉——「魑魅魍魉饕餮麒麟」一级占比为 **0.000**，与日文重合。若采用它，会误杀古文、人名、专业术语、生僻字字典这类正常文件。**这是"宁可漏判"原则明确禁止的方向。**

进一步分析揭示了上表为什么必然全为 0：Shift_JIS 误判产物落的是 **GBK 二级区**，不是 GBK 之外。所以把一级、二级合并为「可编码汉字占比」后就变成 1.000 vs 1.000，信号消失。

**但这恰好指出了「二级汉字占比」为什么反方向有效**：反向统计——只算二级区占比——就能把「产物全落二级区」与「正常中文以一级区为主」区分开，这正是上表 1.000 vs 0.298 的来源。同一个码位事实，顺着看是噪声，反过来看是强信号；而它的致命弱点也来自同一处：真实的纯生僻字文件同样全落二级区。**信号与误伤来自同一个成因，因此无法用调阈值的方式把它们分开。**

### 什么情况下 L1 才有解

必须引入**超越字面统计的外部信息**，只有两类可能：

1. **字频/语言模型**（如日语或汉语词频表），用「这些二级汉字是否以任何自然语言中都不可能的形式组合出现」来判定。
2. **语义语境**，如依据文件扩展名、路径、项目语言标记做旁证。

两者都意味着新增第三方数据或显著复杂度。在当前「不引入第三方依赖 + 宁可漏判」的约束下，**L1 不可自动修复，且不应尝试用字面统计强行修复**——「二级汉字占比」就是这条路走到尽头的样子：判得准，但会误杀真中文。若将来放宽约束，本文档列出的证伪清单可直接作为起点，不必再测 PUA、假名、汉字级别这三类判据。

最后强调这一点为什么危险：**这种误判不会显示成乱码。** 它会显示成看起来像中文、但内容错乱的文字，用户很难察觉；一旦保存，原文件即不可逆损坏。这正是本方案宁可返回 `None` 的原因。**漏判只是体验回退，错判是数据丢失。**

### L2 的边界是靠标定定出来的

最初想给判据加最小样本量 12 字符门槛来消除 L2，被标定数据否掉了：

| Big5 字符数 | 按 GB18030 解码的 PUA 占比 | 判据表现 |
|---|---|---|
| 2 | 0.000 | 误判 |
| 3 | 0.000 | 误判 |
| 4 | 0.000 | 误判 |
| 5 | 0.200 | 正确拒绝 |
| 8 | 0.250 | 正确拒绝 |
| 12 | 0.250 | 正确拒绝 |
| 13 | 0.308 | 正确拒绝 |

从 5 个字符起占比就远超 0.02 阈值。若加 12 字符门槛，5-12 字符区间会被强行改判为兜底编码，反而让正常的 8 字符 GBK 文件（如中文测试内容）漏判，等于用一个真问题换一个更常见的问题。因此门槛不设。

### 局限如何被锁住

这些局限全部写成带 KNOWN LIMIT 标记的断言，让它们失败时能被立刻发现，而不是被误当成缺陷修掉：

```python
check("KNOWN LIMIT: zh_CN misreads tiny big5", detect(tiny_path, "zh_CN"), enc_mod.GB18030)
```

反直觉的好处是：若未来真的实现了 Shift_JIS 区分能力，这条断言会失败，从而强制更新文档，局限清单不会悄悄过时。

---

## 12. 校验与固化

所有设计决策最终都要落到回归校验上，否则下次改动会悄悄退化。

在 `t.sh` 一键回归中，以下子项全绿：

```
COMPILE=0  SMOKE=0  CHECK=0  ROUNDTRIP=0  ENCODING=0
DETECT=0   ENTRY=0  IMPORT=0  LISTENER=0   LISTENER_RT=0
TOTAL_EXIT=0
```

针对本次最关键的时序行为，额外加了两条**锁定断言**，防止后续维护者把同步入口改回延迟式：

```python
check("sync load reopens before any timeout", v1.reopened, [...])   # 不经过任何定时器
check("sync load leaves no queued work", len(_pending), 1)          # 同步路径不留残留任务
```

这样一旦有人把 `immediate=True` 改掉，测试立刻失败，**闪烁问题不会悄悄回来**。

v1.2 新增的锁定断言分三类：

| 类别 | 断言内容 | 锁住什么 |
|---|---|---|
| 单候选守卫 | 多候选时 `target_encoding` 返回 `None` | 防止有人把「只在无歧义时行动」改回「选最优」 |
| 已知局限 | 5 条 `KNOWN LIMIT` 用例 | 能力提升时强制同步文档 |
| 状态栏 | widget 视图不写 status、空编码用 erase_status | 防止状态栏污染非文件视图 |

状态栏用例示例：

```python
check("widget view has no encoding status", v_widget.status, {})
check("empty encoding removes status", v_empty.status.get(STATUS_KEY), None)
```

同时清理了一批被新方案取代的死代码：

- `encoding_detect.py` 中已被取代的 `should_reopen` / `_processed`（旧的 view.id 去重机制）
- `encodings.py` 中旧的 `CONVERTIBLE` / `PY_CODECS` / `REOPEN_ARGS` 三处分散常量（合并进注册表）
- `doctor.py` 中废弃的 `view.set_encoding()` 调用
- `doctor.py` 中硬编码的 `/Volumes/...` 绝对路径

---

## 13. 复盘：这套方案真正学到的东西

| 教训 | 说明 |
|---|---|
| **不要凭直觉加门槛** | CJK 占比门槛被标点数据一秒否掉，假阴性代价远大于假阳性 |
| **参数的"文档值"可能是错的** | `reopen` 的 `gb18030` 参数无任何文档，实测才发现要用界面显示名 |
| **时序比逻辑更容易出 bug** | 闪烁不是探测错误，是 `on_load` / `on_load_async` 的时机差 |
| **去重标识必须跨状态变化稳定** | `view.id()` 和 `encoding()` 都会在 reopen 后变，路径才是稳定 key |
| **宁可漏判，不可错判** | 短 Big5 不可分，选择不猜。错判是数据丢失，漏判只是体验回退 |
| **实测结论要固化进测试** | 只写代码不写锁定断言，下次改动就会退化 |
| **多候选裁决是不可靠的，要从结构上删掉它** | 与其"选最优"，不如"只在无歧义时行动"，单候选守卫把赌博变成确定 |
| **map 要精确到编码名，不能按语言家族泛化** | zh_CN 写成家族后候选恒为 2，自动选码对所有简体用户静默失效 |
| **空值要显式表达，不能靠默认兜底** | ko_KR 留空会回落 GB18030 去猜韩文，必须显式给空元组 |
| **新判据要隔离在单一编码分支上** | 半角片假名判据只挂 Shift_JIS，收益纯增量，不影响已验证的中文路径 |
| **局限要写成会失败的断言** | 局限断言的作用不是"证明对"，而是"一旦能力提升就强制更新文档" |

其中 v1.0 时代最值得记住的是**「实测结论要固化进测试」**。**"闪烁已消除"不是一个可以写进文档就完事的结论，而是一条必须被测试锁住的行为契约。** 否则三个月后有人重构 listener，这个坑会原样复现，而且没人记得为什么当时要拆双入口。

v1.2 补充一条同等重要的：**局限清单也必须被测试锁住。** 本文档列出的 5 条局限，每一条都有对应的 KNOWN LIMIT 断言。它们的存在不是为了证明"我们知道哪里不行"，而是为了让"不行"这件事在代码层面有痕迹——一旦某个局限被意外修好，测试会红，文档必须同步更新。**这比局限本身更有价值。**

---

## 附：涉及的关键文件

| 文件 | 职责 |
|---|---|
| [encodings.py](../src/mysidebar/encodings.py) | 单一编码注册表：编码属性、分组、locale 映射、BOM、只读接口 |
| [encoding_detect.py](../src/mysidebar/encoding_detect.py) | 编码探测、单候选守卫、PUA/半角片假名仲裁、缓存、采样窗口 |
| [listener.py](../src/mysidebar/listener.py) | 双入口时序、路径去重、状态清理、状态栏刷新 |
| [cmds/encoding.py](../src/mysidebar/cmds/encoding.py) | 转换命令：注册表驱动的目标列表、Auto Detect 源编码项、UTF-16 BOM |
| [cmds/doctor.py](../src/mysidebar/cmds/doctor.py) | 诊断报告：注册表段、标定矩阵段 |
| `tests/_encoding_detect.py` | 探测回归与 KNOWN LIMIT 断言 |
| `tests/_listener_case.py` | listener 单元测试、状态栏用例、时序锁定断言 |
| `tests/_i18n_keys.py` | 注册表与三语 key 完整性校验 |
| `tests/_check.py` | 架构约束断言 |
| `t.sh` | 一键回归入口 |