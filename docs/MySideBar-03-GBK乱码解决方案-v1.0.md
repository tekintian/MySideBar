# Sublime Text 打开 GBK/GB18030 中文文件乱码：从误判到根治的完整技术复盘

> 环境：Sublime Text 4（build 4215）/ Python 3.14.6 / macOS
> 项目：MySideBar 自研插件
> 状态：已实测闭环，回归校验全绿

---

## 0. 写在前面：这篇要解决的不是"乱码"，是"三个能力盲区"

先摆结论：**GBK 中文文件在 ST 里打开乱码，从来不是配置问题，也不是插件 bug。** 它是三个独立能力盲区叠加的结果，任何只针对其中一层的补丁都会留下尾巴。

| 盲区 | 表现 | 责任方 |
|---|---|---|
| **ST 自动探测缺失** | 回退 Western (Windows 1252) | ST 内置探测器 |
| **ST 编码列表参数陷阱** | 菜单写 `gb18030`，实际不生效 | ST 命令参数约定 |
| **macOS 系统编辑器不支持** | 报"UTF-8 不适用" | Apple 文本编辑 |

第三项尤其容易被误判成"文件坏了"。我在复盘时实测确认了这一点，后文给出数据。

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
def detect(path):
    raw = _read(path)
    if raw is None:
        return None
    bom = _bom_encoding(raw)          # 1. BOM 优先
    if bom is not None:
        return bom
    if _looks_binary(raw):            # 2. 二进制跳过
        return None
    if _pure_ascii(raw):              # 3. 纯 ASCII 跳过（不做事倍功半的 reopen）
        return None
    if _clean_utf8(raw):              # 4. UTF-8 严格校验
        return encodings.UTF8
    return _trusted_gb18030(raw)      # 5. GB18030 兜底（带可信度仲裁）
```

对应实现：[encoding_detect.py](../src/mysidebar/encoding_detect.py)

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

---

## 7. 边界实测：Emoji 与 GB18030 四字节区

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

## 8. 另一条结论：macOS 打不开是正常现象

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

## 9. 最终架构

整套方案可以概括为五段链路，每段只做一件事：

```
识别   →  BOM / 二进制 / ASCII 前置过滤
       →  UTF-8 严格校验优先
       →  GB18030 兜底 + PUA 可信度仲裁（防 Big5 静默损坏）
       →  非 ASCII 窗口采样（防前缀盲区）

转换   →  reopen 命令 + "Chinese (GB18030)" 显示名参数
       →  纯视图级操作，磁盘字节零改动

时序   →  on_load 同步入口，抢先于首帧渲染（消除闪烁）
       →  is_loading() 判定 + SETTLE_LIMIT 重试上限

去重   →  只认文件路径 key，不看 encoding()
       →  _kick / _inspect 双入口拦截
       →  on_close 清理 + reopen 成功即清 pending

保存   →  保持 GB18030 写盘，往返字节无损
```

---

## 10. 校验与固化

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

同时清理了一批被新方案取代的死代码：

- `encoding_detect.py` 中已被取代的 `should_reopen` / `forget` / `_processed`（旧的 view.id 去重机制）
- `doctor.py` 中废弃的 `view.set_encoding()` 调用
- `doctor.py` 中硬编码的 `/Volumes/...` 绝对路径

---

## 11. 复盘：这套方案真正学到的东西

| 教训 | 说明 |
|---|---|
| **不要凭直觉加门槛** | CJK 占比门槛被标点数据一秒否掉，假阴性代价远大于假阳性 |
| **参数的"文档值"可能是错的** | `reopen` 的 `gb18030` 参数无任何文档，实测才发现要用界面显示名 |
| **时序比逻辑更容易出 bug** | 闪烁不是探测错误，是 `on_load` / `on_load_async` 的时机差 |
| **去重标识必须跨状态变化稳定** | `view.id()` 和 `encoding()` 都会在 reopen 后变，路径才是稳定 key |
| **宁可漏判，不可错判** | 短 Big5 不可分，选择不猜。错判是数据丢失，漏判只是体验回退 |
| **实测结论要固化进测试** | 只写代码不写锁定断言，下次改动就会退化 |

其中最值得记住的一条是最后一条。**"闪烁已消除"不是一个可以写进文档就完事的结论，而是一条必须被测试锁住的行为契约。** 否则三个月后有人重构 listener，这个坑会原样复现，而且没人记得为什么当时要拆双入口。

---

## 附：涉及的关键文件

| 文件 | 职责 |
|---|---|
| [encoding_detect.py](../src/mysidebar/encoding_detect.py) | 编码探测、可信度仲裁、采样窗口 |
| [listener.py](../src/mysidebar/listener.py) | 双入口时序、路径去重、状态清理 |
| [encodings.py](../src/mysidebar/encodings.py) | reopen 参数映射、统一调用入口 |
| [doctor.py](../src/mysidebar/cmds/doctor.py) | 诊断报告 |
| `tests/_listener_case.py` | listener 单元测试与锁定断言 |
| `tests/_check.py` | 架构约束断言 |
| `t.sh` | 一键回归入口 |