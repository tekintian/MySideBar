# MySideBar 技术方案

> 版本：v2.0
> 适用：Sublime Text 4（实测环境：ST build 4215 / Python 3.14.6 / osx-x64）
> 状态：待评审
> 判定基准：**ST4 编辑器内置能力**（不含任何第三方包）

---

## 0. 定位与判定原则

### 0.1 产品定位

MySideBar 吸收 `SideBarEnhancements`、`SideBarMenuAdvanced`、`sublime-gbk-support` 三个参考插件的**精华思路**，结合国内开发者使用习惯重新设计，形成全新插件。插件交付后，三个参考插件将被卸载。

**三个参考插件仅作为「思路来源」，不是功能对齐基准，也不复制其源码。** 功能取舍的唯一基准是下文「与 ST4 原生能力的重叠判定」。

### 0.2 原生重叠四类判定

对每一项候选功能，只问一个问题：**ST4 编辑器自身是否已提供该能力？**

| 判定 | 含义 | 动作 |
|---|---|---|
| **A 完全重叠** | 原生功能等价，体验无短板 | **不做**，文档注明原生命令，引导用户使用原生 |
| **B 部分重叠** | 原生有骨架，缺关键一环 | **只做缺失的那一环**，其余复用原生 |
| **C 不重叠** | 原生完全没有 | **完整自研** |
| **D 重叠但体验差** | 原生有但不可用（删除无回收站、新建文件不支持多选） | **自研替换**，可选遮蔽原生项 |

### 0.3 判定事实来源

本章所有判定均基于对 `Default.sublime-package`（ST4 Build 4215）的实际解包核对：

- `Side Bar.sublime-menu`、`Side Bar Mount Point.sublime-menu`
- `Tab Context.sublime-menu`、`Tab Sidebar Context.sublime-menu`
- `Encoding.sublime-menu`、`Main.sublime-menu`
- `side_bar.py`、`rename.py`

**不采用任何行业印象或推测。**

---

## 1. ST4 原生能力实测结论

### 1.1 原生侧边栏右键菜单

| 原生菜单项 | 原生命令 | 能力实况 |
|---|---|---|
| New File | `new_file_at` | **仅当 `len(dirs) == 1` 可见**，不支持多选，不创建父目录 |
| Rename… | `rename_path` | **`on_done` 已调用 `v.retarget(new)`**，已处理大小写变化（`is_case_change`），仅单选 |
| Delete File | `delete_file` | `prompt: false`，**直接永久删除，无二次确认、无回收站** |
| Open Folder… | `open_folder` | 完整 |
| Open Containing Folder… | `open_containing_folder` | 完整，含 Windows UNC 处理 |
| Open Terminal Here… | `open_terminal` | 完整，当前环境已启用 |
| Copy Path | `copy_path_sidebar` | **仅复制绝对路径，仅当 `len(paths) == 1` 可用** |
| Reveal Link Source | `reveal_link_source` | 完整 |
| New Folder… | `new_folder` | 完整，`os.makedirs` 自动建父目录 |
| Delete Folder | `delete_folder` | `prompt: true`，**永久删除，无回收站** |
| Find in Folder… | `find_in_folder` | 完整，复用 `find_in_files` 面板 |
| Sublime Merge 四项 | `sublime_merge_*` | 由 `sublime_merge_path` 开关控制 |

### 1.2 原生编码菜单（关键事实）

`Encoding.sublime-menu` 实测仅有 `set_encoding` 与 `reopen_with_encoding` 两组，其中**已内置**：

```
Chinese (GB18030)  →  reopen       { "encoding": "Chinese (GB18030)" }
Chinese (GB18030)  →  set_encoding { "encoding": "Chinese (GB18030)" }
```

**GB18030 是 GBK 的超集**，能正确解码全部 GBK 文件。因此：**单文件 GBK/GB18030 打开与另存，ST4 原生已完整覆盖，无需插件，也不依赖任何第三方编解码器。**

### 1.3 原生标签右键

`Tab Context.sublime-menu` 与 `Tab Sidebar Context.sublime-menu` 均真实存在，内容包括：

```
Close Tab / Close Other Tabs / Close Selected Tabs / Close Unselected Tabs
Close Tabs to the Right / Close Unmodified Tabs / Close Unmodified Tabs to the Right
Close Tabs With Deleted Files / Split View / New File / Open File
```

**结论**：标签右键只有「关闭类 + Split View + 新建/打开」，**没有任何文件定位、路径复制能力**。

### 1.4 原生项目操作

| 操作 | 原生命令 | 位置 |
|---|---|---|
| Add Folder to Project | `prompt_add_folder` | `Main.sublime-menu` |
| Remove Folder from Project | `remove_folder` | `Side Bar Mount Point.sublime-menu` |

两者均完整可用。

### 1.5 原生完全缺失的能力

- 侧边栏文件的剪切 / 复制 / 粘贴
- 复制副本（duplicate）/ 移动（move）
- 用系统程序打开
- 在右侧打开 / 在新窗口打开
- 复制相对路径 / 复制文件名
- 删除到回收站
- 批量正则改名
- 批量编码转换
- 搜索结果的可批量操作视图
- 标签页文件的定位与路径复制

---

## 2. 功能判定与需求清单

### 2.1 必须自研功能（C + D 类）

| # | 功能 | 判定 | 原生实况 | 自研理由 |
|---|---|---|---|---|
| 1 | **批量正则改名**（预览/冲突校验/撤销/含目录/递归） | C | 无 | 核心功能，最大价值点 |
| 2 | **删除到回收站**（文件与文件夹） | D | 永久删除，无确认无回收站 | 数据安全 |
| 3 | **批量编码转换**（GB18030 ↔ UTF-8 ↔ UTF-16） | C | 仅单文件 | 批量场景原生无 |
| 4 | **侧边栏文件剪贴板**（剪切/复制/粘贴） | C | 无 | 跨目录移动的核心交互 |
| 5 | **复制副本 / 移动** | C | 仅 rename | 独立功能，原生无 |
| 6 | **用系统程序打开** | C | 无 | 打开非文本文件（图片/PDF/视频） |
| 7 | **在右侧打开 / 在新窗口打开** | C | 无 | 分屏对照与独立窗口 |
| 8 | **复制相对路径 / 复制文件名** | C | 仅绝对路径、仅单选 | 项目内引用的高频需求 |
| 9 | **新建文件增强**（多选目录 + 父目录创建） | D | 仅单选、不建父目录 | 多选批量新建与深层目录 |
| 10 | **搜索结果批量操作视图** | B | Goto Anything 有列表；`find_in_files` 有面板 | 只做「结果可多选执行批量动作」这一段 |
| 11 | **标签右键增强** | B | 仅有 close / split / new / open | 追加定位与路径复制 |
| 12 | **菜单遮蔽**（可选开关，默认开启） | — | — | 中文文案统一、避免与原生重复 |

### 2.2 标签右键增强明细（第 11 项）

在 `Tab Context.sublime-menu` 与 `Tab Sidebar Context.sublime-menu` 中追加三项：

| 菜单项 | 行为 | 实现依据 |
|---|---|---|
| **在管理器中定位当前文件** | 系统文件管理器中打开并选中该文件 | `platform.reveal(file)` |
| **复制当前文件相对路径** | 相对项目根目录的路径 | `os.path.relpath(file, project_root)`，多项目取最长匹配根 |
| **打开文件所在目录** | 系统文件管理器中打开父目录（不选中文件） | `platform.reveal(dirname(file), dir_only=True)` |

**技术要点**：

- 标签右键的 `args` 由 ST 动态注入 `group` 与 `index`（原生菜单项均写 `{"group": -1, "index": -1}`）。
- **T0-3 已实测**：`window.sheets_in_group(group)` 返回 `TextSheet` 对象，**不是 `sublime.View`**，`isinstance(sheet, sublime.View)` 恒为 `False`。取 View 必须调用 `sheet.view()`；再对 View 做 `is_valid()` 与 `file_name()` 校验。实测同时确认 `sheets_in_group(g)[i]` 与 `views()` 在单组窗口下顺序一致（9 个 sheet 与 9 个 view 一一对应），且 `get_view_index(view)` 返回 `(group, index)` 元组。`window.active_view_index()`、`sublime.Encoding` 在 ST4 **均不存在**。
- 取当前活动视图在组内的位置用 `window.get_view_index(view)`；ST4 **不存在** `window.active_view_index()`。
- **禁止**用 `window.active_view()` 替代：它指向当前聚焦标签，对被右键的非活动标签会取错文件。
- 三项命令均为 `WindowCommand`，签名为 `run(self, group=-1, index=-1)`。

**边界**：

| 场景 | 处理 |
|---|---|
| 右键的是非文件标签（输出面板、图片预览、无标题新文件） | `is_visible()` 返回 False |
| 文件未保存（无 `file_name()`） | 同上 |
| 文件不在任何项目文件夹内 | 「复制相对路径」不显示，其余两项仍显示 |
| 文件已被删除但标签仍存在 | 「定位」与「打开目录」不显示 |

### 2.3 明确不做（A 类，共 7 项）

| 功能 | 原生命令 | 说明 |
|---|---|---|
| 新建文件夹 | `new_folder` | 已自动建父目录 |
| 单文件重命名 | `rename_path` | 已含 retarget 与大小写处理 |
| 在终端打开 | `open_terminal` | 已启用 |
| 在文件夹中查找 | `find_in_folder` | 已复用 `find_in_files` |
| 打开所在目录 | `open_containing_folder` | 含 UNC 处理 |
| **单文件 GBK/GB18030 打开与另存** | 原生 `Chinese (GB18030)` | **卸载 sublime-gbk-support 后不会出现真空** |
| 加入项目 / 从项目移除 | `prompt_add_folder` / `remove_folder` | 两者均完整 |

### 2.4 与参考插件的关系澄清

| 参考插件 | 处理方式 |
|---|---|
| SideBarEnhancements | 只保留经判定为 C/D/B 的功能，A 类一律不做 |
| SideBarMenuAdvanced | 借鉴遮蔽思路，但**默认开启**，遮蔽清单缩到 3 项 |
| sublime-gbk-support | **单文件 GBK 不做**（原生已含 GB18030），只做批量转换 |

**为何卸载 `sublime-gbk-support` 不产生真空**：该插件核心价值是为 ST 提供 GBK 编解码器。ST4 已内置 `Chinese (GB18030)`，GB18030 覆盖 GBK 全部字符，单文件 GBK 场景卸载后仍由原生菜单完整支持。

---

## 3. 总体架构

### 3.1 目录结构

```
MySideBar/
├── .no-sublime-package        # 空文件：以求目录形式安装（子目录可被 import）
├── .python-version            # 仅本地开发提示，以 ST 实际 sys.version 为准
├── MySideBar.py               # 包根入口：ST 只加载包根 *.py，plugin_loaded 必须在此
├── mysidebar/
│   ├── __init__.py            # 包初始化：设置加载、语言询问、菜单应用、遮蔽装配（由根入口调用）
│   ├── i18n.py                # 中英文案表、语言读写（无区域探测）
│   ├── platform.py            # 三平台：reveal、open_with_default、路径处理
│   ├── api.py                 # Selection / Project / Item
│   ├── clipboard.py           # 会话内剪切/复制状态（不 import sublime_plugin）
│   ├── trash.py               # send2trash 三平台（BSD 协议保留）
│   ├── batch/
│   │   ├── __init__.py
│   │   ├── patterns.py        # rel_new 生成器：正则 / 序号
│   │   ├── plan.py            # collect / compute / validate
│   │   ├── execute.py         # 执行引擎（目录批 → 文件批 → 中间名）
│   │   └── rollback.py        # 回滚日志与撤销
│   ├── cmds/
│   │   ├── __init__.py
│   │   ├── file_ops.py        # 新建文件 / 复制副本 / 移动
│   │   ├── trash_cmd.py       # 移入回收站 / 在文件管理器中定位
│   │   ├── open.py            # 系统程序打开 / 右侧打开 / 新窗口打开
│   │   ├── clipboard.py       # cut / copy / paste / 复制路径系列
│   │   ├── tab.py             # 标签右键增强：定位 / 相对路径 / 打开目录
│   │   ├── search.py          # 搜索结果批量操作视图
│   │   ├── encoding.py        # 批量编码转换
│   │   ├── settings.py        # 语言切换与菜单重应用命令
│   │   ├── batch_rename.py    # 批量改名命令层
│   │   └── shadow.py          # 菜单遮蔽空壳命令（默认开启，独立模块）
│   └── ui/
│       ├── __init__.py
│       ├── preview.py         # 改名预览视图
│       └── input.py           # InputHandler 链式封装
├── Side Bar.sublime-menu              # 侧边栏右键（英文唯一源，必须在包根）
├── Tab Context.sublime-menu           # 标签右键增强（必须在包根）
├── Tab Sidebar Context.sublime-menu   # 侧边标签列表右键增强（必须在包根）
├── Main.sublime-menu                  # 主菜单：Preferences → MySideBar（必须在包根）
├── Commands.sublime-commands          # 命令面板（必须在包根）
├── MySideBar.sublime-settings         # 必须在包根
├── MySideBar Rename Preview.sublime-syntax   # 预览语法（必须在包根）
├── messages/install.txt
└── docs/
```

**资源文件名与位置事实**：

- ✅ `Side Bar.sublime-menu`、`Tab Context.sublime-menu`、`Tab Sidebar Context.sublime-menu` 均真实存在，可直接作为追加目标。
- ⚠️ **ST 只在包根目录扫描资源文件**：`*.sublime-menu`、`*.sublime-commands`、`*.sublime-settings`、`*.sublime-syntax` 若放入子目录（如 `menus/`、`syntaxes/`）**不会被加载，且无任何报错**（静默失效）。因此全部资源文件必须位于包根。
- ⚠️ **ST 只把包根目录下的 `.py` 文件作为插件模块加载**，`mysidebar/__init__.py` 的 `plugin_loaded` 不会被自动调用。必须由包根入口 `MySideBar.py` 承担生命周期函数并导入子包。
- ❌ **不存在** `Side Bar.zh-CN.sublime-menu` 之类语言后缀机制，中文菜单只能靠同名文件写入 `Packages/User/MySideBar/` 覆盖。
- 本插件**不提供** `Side Bar Mount Point.sublime-menu`（原生已含 `remove_folder`，无需增强）。

### 3.2 包根入口约定

```python
# 包根 MySideBar.py
import mysidebar

def plugin_loaded():
    mysidebar.on_plugin_loaded()

def plugin_unloaded():
    mysidebar.on_plugin_unloaded()
```

- 只有包根 `MySideBar.py` 承担 `plugin_loaded` / `plugin_unloaded`。
- 所有 `sublime_plugin` 命令类定义在 `mysidebar/cmds/` 内，由 ST 通过 `sublime_plugin` 模块扫描导入后自动注册；因 `mysidebar` 子包需被显式 import，由 `MySideBar.py` 的 `import mysidebar` 触发整包模块加载，从而完成命令注册。
- `.no-sublime-package` 只保证以目录形式安装；它**不改变**上述“只加载包根 `.py`”的事实。

### 3.3 分层

```
菜单资源 → 命令层 cmds/ → 领域层 api.py / batch/ → 平台层 platform.py / trash.py
                              ↑
                         ui/ 仅由命令层调用
```

约束：`batch/` 与 `api.py` 不 import `sublime_plugin`；`platform.py` 不 import 业务模块。

---

## 4. 国际化方案

### 4.1 事实依据

ST4 **不提供界面语言 API**，原生界面固定英文。因此本插件采用：

- 插件默认英文
- **不做任何区域自动探测**（不用 `locale`、`LANG`、`LC_ALL`、注册表）
- 仅首次安装询问一次语言，之后固定
- **不用独立 `first_run` 字段**，用 `ui_language` 的 `null` 表达「尚未选择」

### 4.2 语言策略

`ui_language` 取值：`null`（默认，未选择）| `"en"` | `"zh_CN"` | `"zh_TW"`

| 时机 | 行为 |
|---|---|
| 首次安装（`ui_language == null`） | 弹出一次性选择：`English` / `简体中文` / `繁體中文` |
| 用户选择 | 写入具体值，此后永不询问 |
| 用户取消 | 写入 `"en"`，不重复弹出 |
| 无窗口启动 | 跳过询问，保持 `null` |
| 手动切换 | `Preferences → MySideBar → Language` |

### 4.3 菜单实现

- 包内只提供**英文菜单**（唯一事实源）。
- 中文时由 `plugin_loaded` 渲染后写入 `Packages/User/MySideBar/` 下**与包内完全同名**的文件，ST 以 User 层覆盖包内资源。
- **菜单生效时机已由 T0-4 实测确认：即时生效**。切换语言后立即重写 `Packages/User/MySideBar/` 下菜单文件，菜单即时更新，**不需要重启 ST，也不需要重载按钮**。界面只提示「菜单已切换」，禁止出现任何「请重启」文案。
- 标记文件 `.applied_lang` 记录已应用语言与版本号；一致则跳过写入。
- 降级：覆盖未生效时菜单保持英文，运行期提示仍按 `ui_language` 显示。

### 4.4 文案规范

- key 命名 `模块.动作.状态`
- 英文首字母大写无句号；中文用全角标点
- 禁止硬编码用户可见字符串，必须经 `i18n.t()`

---

## 5. 核心模块设计

### 5.1 api.py

| 类 | 职责 |
|---|---|
| `SideBarSelection` | 解析 `paths`，提供 `files` / `dirs` / `items` / `without_child_items` |
| `SideBarProject` | `folders()`、`project_data()`、`find_root(path)`（最长匹配根） |
| `SideBarItem` | `join`、`dirname`、`exists`、`create`、`copy`、`move`、`retarget_views`、`reveal` |
| `ViewResolver` | `resolve_tab_view`、`retarget_views`、`close_views_for_paths`、`set_encoding_checked`、`count_views_for_file` |

关键实现要求：

1. 不用全局缓存与哨兵命令，按调用实时计算。
2. 父子包含判断用 `os.path.commonpath`，不用字符串前缀。
3. `retarget_views` 用 `os.path.normcase` 统一比较。
4. 所有异常捕获具体类型并上报，禁止 `except: pass`。
5. `find_root(path)`：遍历 `window.folders()`，取能包含 `path` 的最长根，用于计算相对路径。

### 5.2 cmds/tab.py（标签右键增强，第 11 项）

```python
class MySidebarTabRevealCommand(sublime_plugin.WindowCommand):
    def run(self, group=-1, index=-1)
    def is_visible(self, group=-1, index=-1)

class MySidebarTabCopyRelativePathCommand(sublime_plugin.WindowCommand):
    def run(self, group=-1, index=-1)
    def is_visible(self, group=-1, index=-1)

class MySidebarTabOpenDirCommand(sublime_plugin.WindowCommand):
    def run(self, group=-1, index=-1)
    def is_visible(self, group=-1, index=-1)
```

**取目标 View 的唯一正确方式**（已按 T0-3 实测结论修正）：

```
sheets = window.sheets_in_group(group)
若 index < 0 或 index >= len(sheets) → 无效
sheet = sheets[index]
sheet 的类型是 TextSheet，不是 sublime.View
view = sheet.view()          # 必须再取一次
若 view 为 None 或 view.is_valid() 为 False → 无效
若 view.file_name() 为空 → 无效（未保存的临时标签）
```

**禁止**使用 `window.active_view()`：它返回当前聚焦标签，对被右键的非活动标签会取错文件。
**禁止**使用 `window.active_view_index()`：ST4 不存在该 API，应改用 `window.get_view_index(view)`。
**禁止**使用 `sublime.Encoding`：ST4 不存在该类；编码以字符串名（如 `Chinese (GB18030)`）通过 `view.encoding()` 与 `view.set_encoding(name)` 传递。

**T0-6 编码 API 实测结论**（实现必须严格遵守）：
- `view.encoding()` 返回 **字符串**名（实测为 `'UTF-8'`、`'Chinese (GB18030)'`），类型为 `str`。
- `view.set_encoding()` **只接受字符串**，传数字（如 `0` / `1` / `256`）抛 `TypeError: String required`。禁止出现任何数字编码常量。
- 编码名字符串必须与 ST 内部名**完全一致**（含空格与大小写）。实测 `'Chinese (GB18030)'` 设置成功并可原样回读。
- **`'GBK'` 不被 ST 识别**：设置时控制台报 `Unknown encoding: GBK`，且 `view.encoding()` 保持原值不变。因此插件内**禁止**使用 `GBK` 作为编码名，统一使用 `Chinese (GB18030)`（GBK 的超集）。
- `set_encoding` 失败时**不报异常、不回滚**，`view.encoding()` 仍是旧值。因此每次设置后必须**回读校验** `view.encoding()` 是否等于目标名，不等则视为失败并中止，不得继续后续保存流程。

**三项命令行为**：

| 命令 | 行为 |
|---|---|
| Reveal | `platform.reveal(file)`：在系统文件管理器中定位并选中该文件 |
| CopyRelativePath | 写入剪贴板 `relpath(file, project_root)`；`project_root` 由 `find_root()` 求得 |
| OpenDir | `platform.reveal(dirname(file), dir_only=True)`：打开父目录不选中文件 |

**`is_visible` 判定**：

| 条件 | Reveal | CopyRelativePath | OpenDir |
|---|---|---|---|
| `sheets[index]` 是有效 View 且 `file_name()` 非空 | ✅ 必需 | ✅ 必需 | ✅ 必需 |
| 文件在磁盘上存在 | ✅ 必需 | — | ✅ 必需 |
| 文件位于某个项目根内 | — | ✅ 必需（否则无相对路径基准） | — |

**`is_enabled` 与 `is_visible` 一致**：`is_visible` 返回 `False` 时菜单项隐藏，但命令面板与键绑定仍会调用 `run`，因此三项命令必须同时实现 `is_enabled` 并返回相同的 bool，避免「菜单隐藏但命令面板可执行」的不一致。

**多项目相对路径基准**：`CopyRelativePath` 遍历 `window.folders()`，取「包含该文件且路径最长」的项目根为基准（最近项目根），不取首个文件夹；不在任何项目根内时输出 `tab.no_root`，不写剪贴板。

**失败反馈**：`platform.reveal()` 返回 `False` 时输出 `tab.reveal_failed` 状态栏提示，禁止静默失败。

### 5.3 batch/patterns.py 与 batch/options.py

```python
class RenameOptions:            # batch/options.py，frozen dataclass
    mode: str          # "regex" | "sequence"
    pattern: str
    replacement: str
    prefix: str
    start: int
    digits: int
    suffix: str
    scope: str         # "name"（仅末段文件名）| "path"（整个相对路径）
    recursive: bool
    include_dirs: bool

def apply(rel_old, options, index=0) -> str
def validate_options(options) -> RenameOptions
```

- `RenameOptions.normalized()` 归一化：`digits` 收敛到 1..10、`start` 非负、`mode`/`scope` 非法值回落默认值，保证后续逻辑不重复校验。
- 正则模式：`$n` / `${n}` 转 Python `\g<n>`；替换串中的反斜杠先转义为字面量，避免用户输入 `\d` 被当作正则转义；残留 `$\d` 判 `PatternError`。
- `scope="name"` 只替换末段文件名，父目录原样保留；`scope="path"` 作用于整个相对路径，可改写父目录段。
- 序号模式：`prefix + str(start + index).zfill(digits) + suffix`，序号模式恒非空，不设空结果校验。
- `PatternError(reason_key)` 携带 i18n 键，`message()` 经 `i18n.t("rename.pattern_error")` 包装；错误分类：
  - `rename.error.empty_pattern`：正则模式pattern为空
  - `rename.error.bad_regex`：正则语法错误
  - `rename.error.group_out_of_range`：替换串引用分组越界（由 `re.sub` 抛出的 `invalid group reference` 归类，而非笼统判为正则错误）
  - `rename.error.bad_result`：替换结果含 `\x00` 等不可用字符
  - `rename.error.empty_result`：替换后末段文件名为空
- 纯函数，无任何 `sublime` 依赖，可离线单测。

### 5.4 batch/plan.py

```python
@dataclass
class PlanItem:
    old_abs, rel_old, rel_new, new_abs
    kind              # "dir" | "file"
    status            # "ok" | "skipped" | "invalid" | "conflict"
    reason            # i18n 键，空串表示无原因
    needs_temp        # 需经中间名落盘
    depth             # rel_old 的 "/" 数量

@dataclass
class RenamePlan:
    base              # 计划根，永不进入 items
    items: list
    skipped_symlinks  # 跳过的 symlink 计数
    error             # 整体失败时携带 i18n 键，非空表示 plan 不可用
    actionable()      # 仅 status == ok
    counts()          # 四状态计数

def collect(selected_paths, options) -> RenamePlan
def compute(plan, options) -> RenamePlan
def validate(plan) -> RenamePlan
```

**collect**：`base` = 选中项最深公共父（选中单目录时即该目录本身，选中单文件时为其父目录）；`base` 永不进入计划，但**选中目录等于 base 时仍要列举其内容**；按 `recursive` / `include_dirs` 收集；symlink 一律跳过并计数；`base` 不可写时 `error = rename.error.base_readonly` 提前返回。

**compute**：`rel_old = relpath(path, base)`（**不对相对路径做 abspath/normalize**，否则会被拼回绝对路径）→ `rel_new = patterns.apply(...)` → `new_abs = normalize(join(base, rel_new))`。序号模式的 `index` 按 `items` 收集顺序递增，保证预览与执行一致。

**validate 顺序（不可颠倒）**：

1. `unchanged` → `rel_old == rel_new` 直接判 `skipped`，**先从 ok 集合中摘出**，否则未改名项会参与后续重名与占用判定，把正常批次误判为冲突
2. `shape` → 空名 / `..` 逃逸 / 绝对路径 / 越出 base / 非法字符 / 超长（255 字节）/ 父目录不可写 → `invalid`
3. `unique` → 同批 `_key(new_abs)` 重复 → `conflict`
4. `disk` → 磁盘已存在且不属本批将移走的项 → `conflict`；`lexists` 为真但 `os.path.samefile(old, new)` 成立（大小写不敏感卷上 `X.tXt` 与 `x.txt` 同 inode）时放行
5. `cycle` → 纯大小写变化或改名链回环 → `needs_temp = True`，status 保持 `ok`

**`_key(path)`** = `normcase(normalize(path))`，全模块统一用它做路径等价比较；**禁止**在 macOS/Linux 上依赖 `normcase` 折叠大小写（`normcase` 在这两个平台是恒等函数）。

### 5.5 batch/execute.py

**数据结构**：

```python
@dataclass
class RenameRecord:
    source, target, kind      # kind ∈ {"temp_in", "dir", "file", "temp_out"}

@dataclass
class ExecutionResult:
    status                    # "ok" | "aborted" | "empty"
    records: list             # 按执行顺序追加，回滚时逆序消费
    failure_path, failure_error, failure_reason
    temp_root                 # 中间名区，结束时置空
    done()                    # status == "ok"
    moved_pairs()             # 过滤 kind == "temp_in" 的 (source, target)

def build_steps(plan) -> list      # [(step_kind, PlanItem)]
def execute(plan, retarget=None) -> ExecutionResult
def rollback(result) -> int
def undo(records) -> (reverted, failed_path)
```

**步骤顺序（`build_steps` 产出，不可调整）**：

```
阶段 A  temp_in   全部 needs_temp 项 → base/.mysidebar_tmp/{uuid}
阶段 B  dir       非 needs_temp 目录项，按 depth 逆序
阶段 C  file      非 needs_temp 文件项
阶段 D  temp_out  needs_temp 项从中间名落到终态
```

**正确性论证**：

- `needs_temp` 集合包含两类：改名链回环项、纯大小写变化项。它们先整体沉入中间名区，使「旧名已腾空」，后续落终态时才不会撞上自身旧路径
- 目录批按 `depth` 逆序 → 子目录先改名，父目录改名时整树搬移，子项自动到终态
- 文件批在目录批之后 → 所有目录已终态，source 必有效、target 必终态
- `temp_out` 置于最后 → 中间名项的目标名此时才被腾空，避免与普通项争抢
- 目标落点用 `dir_final[rel_old] = 最终绝对路径` 查表：以**相对路径为键**，子项父目录改名后自动跟随，无需从绝对路径反推祖先

**字段命名一致性**：`PlanItem.rel_old` 与 `RenameRecord.source/target` 均为**绝对路径**，`rel_*` 只用于建键与展示，执行层不做路径拼接以外的推断。

**失败处理（原子性）**：

- `_rename` 前置校验源存在、父目录存在；父目录缺失**直接抛 `OSError`**，禁止 `makedirs` 兜底（那会掩盖 plan 缺陷）
- 任一 `OSError` → `status = aborted` → `rollback(result)` 逆序 rename 回原名 → `_cleanup_temp` → 返回
- `rollback` 逐条逆序回退，跳过「target 已不存在」或「source 已被占用」的条目，容忍部分失败但不中断
- `_cleanup_temp` 递归删除 uuid 目录，空父目录一并移除，不泄漏临时区

**视图重定向**：`moved_pairs()` 过滤掉 `temp_in` 记录，只暴露「原始路径 → 终态路径」，中间名永不进入 retarget 输入。

**中间名链路的记录折叠（实测缺陷修复）**：

`needs_temp` 项的记录链是 `temp_in(abc.txt → staged)` + `temp_out(staged → ABC.txt)`。若撤销按记录**原样逆序回放**，会先尝试 `ABC.txt → staged`，而临时区已在 `_cleanup_temp` 中被删除，路径不存在，撤销立即中断。

因此 `RenameRecord` 增加 `origin` 字段：

- `temp_in` 记录保持 `source=原路径`、`target=staged`（保留真实执行轨迹，供回滚使用）
- `temp_out` 记录写入 `origin=原路径`，即该链路的**逻辑起点**
- `moved_pairs()` 与 `undo()` 统一按 `(origin or source, target)` 折叠，**一组中间名项只呈现一次逻辑移动**，临时路径永不外泄

**跨文件系统大小写还原（实测缺陷修复）**：

macOS 默认 APFS 大小写不敏感，`abc.txt` 与 `ABC.txt` 指向同一 inode、共享目录项。撤销时的「源已存在」守卫必须区分两种情形：

| 情形 | 判定 | 处理 |
|---|---|---|
| 源路径与终态路径规范化后**字符串相同** | `os.path.normpath` 相等 | 无需 rename，直接计入还原数 |
| 源路径与终态路径**同实体但大小写不同** | `os.path.samefile` 为真 | **必须执行 `os.rename`**，借此改写目录项大小写；跳过会让文件名停留在新的大小写 |
| 源路径存在且确为**不同文件** | `samefile` 为假 | 判为冲突，中止撤销并保留日志 |

推论：`lexists(origin)` 为真**不能**直接判为冲突；必须叠加 `samefile` 判定，否则大小写改名永远无法撤销。

**规模策略**：上限 `batch_rename_max_items`（默认 5000），**同步执行**；超 2000 项时确认框提示预估耗时。不做异步，避免视图 retarget 时序竞态。

### 5.6 batch/rollback.py

**职责边界**：`execute.rollback()` 是**执行期内部回滚**（内存态，只消费本次 `ExecutionResult.records`）；`rollback.py` 是**事后撤销**（持久化日志 + 预检 + 跨进程可用）。两者不互相替代，`rollback.py` 单向依赖 `execute` 的 `STEP_TEMP_IN` 常量。

**数据结构**：

```python
class UndoOutcome:
    status            # "ok" | "empty" | "blocked" | "partial"
    reverted: int
    blocked_path: str
    reason_key: str
    reason_param: str
    pairs: [...]
    done()            # status == "ok"

def build_entry(result, base, timestamp=None) -> dict
def log_dir() / log_path() -> str
def save_log(entry, path=None) -> bool
def load_log(path=None, now=None) -> dict | None
def clear_log(path=None) -> bool
def undo_last(path=None, retarget=None, now=None) -> UndoOutcome
```

**日志位置与结构**：

- 路径：`Packages/User/MySideBar/rename_log.json`，经 `platform.user_dir()` 取得，**不落在项目目录**
- 结构：`{"version": 1, "timestamp": float, "base": str, "ops": [{"old": abs, "new": abs, "kind": ...}]}`
- **`ops` 只记录非 `temp_in` 的 records**：中间名是执行期产物，撤销时若参与逆序会出现「先 rename 回 uuid 名」的错乱
- `ops` 为空时 `save_log` 直接返回 `False`，不允许空条目占据「最近一次」槽位
- 写入用 `临时文件 + os.replace` 原子替换，避免中途崩溃留下半截 JSON

**有效性判定（`load_log`）**：

- JSON 解析失败、非 dict、`ops` 非列表或为空、任一条目缺 `old`/`new`、`timestamp` 非数值 → 返回 `None`
- 超过 `MAX_AGE_SECONDS`（7 天）→ 视为过期返回 `None`，避免撤销跨越太久、现场已面目全非的批次

**撤销原子性（两阶段）**：

1. **preflight 预检（一个文件都不动）**：逆序遍历 `ops`，要求 `lexists(new)` 为真且 `old` 未被占用。`old` 存在时用 `samefile` 兜底——macOS 大小写不敏感卷上 `lexists(old)` 可能恒真，`_same_entry` 命中才放行。任一不满足 → 返回 `blocked`，携带冲突路径与 `rename.undo_conflict` 文案键
2. **execute 执行**：逐条逆序 `os.rename(new, old)`；中途 `OSError` → `partial`，保留已回退计数与失败路径

- 成功才 `clear_log`；`blocked` / `partial` 一律**保留日志**，用户修复现场后可重试
- 成功后对 `pairs`（`new → old` 方向）调用 `retarget`，视图随之回到原名

**跨层接口适配（必须遵守）**：`execute.moved_pairs()` 与 `rollback` 的 `pairs` 都是 **`[(source, target)]` 列表**，而 `api.ViewResolver.retarget_views()` 接收 **dict（键为 `normcase(normalize(path))`）**。命令层**禁止**直接 `retarget_views(pairs)`（`dict.get` 会失败且静默无效），必须经 `ViewResolver.retarget_pairs(pairs)` 归一化转换。

**保留策略**：只保留最近一次，`save_log` 直接覆盖。

### 5.7 batch_rename 输入链、预览与执行入口（T15）

**输入形态的事实依据（已实测，不可回退）**：

- ST 4215 的 `show_panel` 只接受 **7 个硬编码面板名**：`console_panel` / `find_in_files_panel` / `find_panel` / `input_panel` / `output_panel` / `replace_panel` / `switch_project_panel`
- 二进制中**不存在** `SideBarInputHandler`、`sublime-panel` 或任何自定义面板注册机制 → **无法借原生查找面板的外观承载自定义表单**
- `sublime_plugin.CommandInputHandler` 只服务于**命令面板单行输入**，无法生成 Find/Where/Replace 三行并排布局
- 结论：采用 **预设列表 + 分段 `show_input_panel`**，不追求三行并排

**交互链（3 步）**：

1. `show_quick_panel` 选**预设**（7 项：正则/编号 × 仅文件名/含子目录/仅目录/相对路径）
2. 正则模式 → `show_input_panel` 输入 pattern（回填上次值）
3. 正则模式 → `show_input_panel` 输入 replacement（回填上次值）
4. 编号模式跳过 2/3，直接构建 plan
5. 打开预览视图 → 视图内执行全部 / 仅执行选中 / 撤销

**预设 → RenameOptions 映射**（`PRESETS` 元组，顺序即面板顺序）：

| 预设键 | mode | scope | recursive | include_dirs |
|---|---|---|---|---|
| `rename.preset_regex_files` | regex | name | False | False |
| `rename.preset_regex_files_all` | regex | name | True | False |
| `rename.preset_regex_path` | regex | path | True | False |
| `rename.preset_regex_dirs` | regex | name | True | True |
| `rename.preset_sequence_files` | sequence | name | False | False |
| `rename.preset_sequence_files_all` | sequence | name | True | False |
| `rename.preset_sequence_dirs` | sequence | name | True | True |

- 预设一次表达 mode/scope/recursive/include_dirs 四个维度，**解决了 `ListInputHandler` 一次只能返回一个值、无法表达多布尔开关的问题**
- 上次输入记忆存 `MySideBar.sublime-settings` 的 `mysidebar_rename_last_pattern` / `mysidebar_rename_last_replacement`

**分层职责**：

- `mysidebar/ui/preview_model.py`：**纯逻辑，不 import sublime**。`line_for` / `lines_for` / `summary_text` / `selected_indexes` / `subset_plan`，可离线单测
- `mysidebar/ui/preview.py`：ST 视图层。复用已有预览 view（`PREVIEW_FLAG` 标记），`set_read_only(True)`，plan 存于 `view.settings()[PLAN_SESSION]`
- `mysidebar/cmds/batch_rename.py`：命令层，负责 i18n 与用户交互；UI 层只接收已翻译字符串

**预览文本与行号映射（必须保持一致）**：

- 布局：第 0 行 = 汇总，第 1 行 = 空行，第 2 行起 = 逐项数据
- `HEADER_BLANK_LINES = 1` 同时驱动 `render()` 的分隔符与 `header_lines()` 的偏移，**禁止两处独立硬编码**，否则选区行号会整体错位
- `selected_indexes(view)` 由选区行号反查 `plan.items` 索引，**只保留 `status == ok`** 的项；冲突项必须由用户修正模式后重跑，不能被“选中执行”绕过

**执行与撤销入口**：

- 执行前 `show_ok_cancel_dialog` 二次确认
- 执行调用 `execute.execute(plan, retarget=ViewResolver.retarget_pairs)`；撤销调用 `rollback.undo_last(retarget=ViewResolver.retarget_pairs)`
- **禁止**传裸 `pairs` 给 `retarget_views`（见 5.6 接口适配约束）

**`is_enabled` 性能约束**：

- `MySidebarRenameUndoCommand.is_enabled()` 会被 ST 高频调用（菜单弹出、命令面板过滤），**禁止在其中读盘**
- 改为内存缓存 `_undo_cache`，插件加载后由 `mysidebar.on_plugin_loaded()` → `_refresh_rename_undo()` 预热，`run()` 时刷新

### 5.8 cmds/encoding.py（批量编码转换）

**范围**：仅批量转换。单文件场景由原生 `Chinese (GB18030)` / UTF-8 覆盖，**不实现**。

**已核实的关键 API 事实**：

- `sublime` 模块**不存在** `load_file_with_encoding`（`load_resource` 只能读 Packages 虚拟 FS，无法读用户文件）
- `View.set_encoding(name)` 仅设置「下次保存使用编码」，**不重读文件内容**

**单文件处理流程（实现口径，必须严格按序）**：

```
0  选择目标编码（show_quick_panel，仅 4 项：GB18030 / UTF-8 / UTF-16 LE / UTF-16 BE）
0b 二次确认：本操作以「整体重写缓冲区」方式实现，会清空该视图的 undo 历史，
   且不可撤销；确认框为「转换编码将重写文件内容且无法撤销，是否继续？」
   （i18n 文案；默认按钮为取消）
1  定位视图：本 window 内已有该文件视图则直接复用；否则 open_file 后用
   set_timeout 轮询 is_loaded()（上限 100 次 × 50ms），超限则该项记失败并继续下一项
   —— 禁止把「刚打开尚未加载」误判为「文件无法加载」
2  W_OK 不可写            → failed
3  文件大小超 encoding_max_bytes（默认 20 MB） → failed
4  view.encoding() == 目标编码 → skipped，不写盘
5  多视图检测：ViewResolver.count_views_for_file(path, exclude_view=view) > 0
   → failed，提示先关闭其余视图
   - 理由：select_all + insert 只作用于当前 view，其余视图缓冲区不同步，
     保存会造成内容覆盖与数据丢失
6  view.is_dirty() 为 True → 三选一：保存后继续 / 放弃修改继续 / 取消
   - 取消 → 记 skipped（不计失败）
   - 保存失败 → 记 failed
7  text = view.substr(Region(0, view.size()))
   **必须复用视图缓冲区文本，禁止 open(path, "rb").read() 后二次 decode**
   - 理由：ST 已按源编码完成一次解码，再读盘解码属重复解码，源编码检测不准时
     会二次错误解码并破坏内容；同时视图缓冲区的未保存改动也不会被丢弃
8  select_all + insert(text)  → 整体重写缓冲区
9  set_encoding_checked(target)：set_encoding 后回读 view.encoding() 校验，
   不一致 → failed，且此时**不执行 save**，避免以错误编码落盘
10 save 后回查 view.is_dirty()，仍为 True → failed
```

**状态机约束（实现要点）**：

- 批处理是**异步串行推进**：每一项完成后显式调用 `_advance()`，禁止用递归裸调用推进
- 任一「需要用户交互」的分支必须**立即 return**，不可继续循环，否则会叠加多个对话框
- 用户取消二次确认 → 整批不执行，状态栏提示 cancelled
- 结果汇总到 `create_output_panel`（`output.my_sidebar_encoding`），只读；
  同时状态栏输出 `encoding.result_summary`

**破坏性说明（必须在实现与文档中体现）**：

- 第 7 步用 `run_command` 整体替换缓冲区，会**清空该视图 undo 历史**、**重建光标与选区**，属不可撤销操作，因此第 0 步强制二次确认。
- 第 9 步必须紧接第 8 步执行，禁止在转换完成与保存之间插入任何用户交互，避免用户在半转换状态下编辑后保存。

**批量流程**：

1. 收集目标（复用 `SideBarSelection`），过滤 symlink 与 `W_OK` 不可写项
2. 逐项执行，失败**不中断整批**，记入结果表
3. 汇总到 `window.create_output_panel`：成功 / 跳过 / 失败 + 原因
4. 单文件超 `encoding_max_bytes`（默认 20 MB）拒绝，提示改用命令行工具

### 5.9 cmds/search.py（搜索结果批量操作视图）

**定位**：不做第二个 Goto Anything。原生 `super+p` 已提供递归列表 + 模糊匹配 + `文件:行:列` 语法。

本模块唯一增量：**把搜索结果变成可多选执行批量动作的文件清单**。

1. 结果渲染 scratch 视图（`set_scratch(True)` + `set_read_only(True)`），每行一个相对路径
2. 支持对选中行执行：送回收站 / 转批量改名 / 整列复制
3. 支持 `exclude_dirs_for_search` 自定义排除（原生受 `index_exclude_patterns` 与 `.gitignore` 约束，粒度不可控）
4. 遍历在 `set_timeout_async` 中执行，结果分批 insert，避免阻塞 UI
5. 上限 `search_result_limit`（默认 5000）

### 5.10 cmds/shadow.py（菜单遮蔽，默认开启）
**`menu_shadow_default_items` 默认 `true`**。

理由：`delete_file`、`delete_folder`、`new_file_at` 被判定为 **D 类（原生有但体验差，自研替换）**。D 类的定义要求替换必须真正发生；若默认不遮蔽，原生永久删除与单选新建仍暴露在菜单中，与自研项并存，D 类判定形同虚设。此外原生删除为无确认永久删除，默认遮蔽可直接避免用户误用。

**可遮蔽清单（仅 3 项）**：

| 命令名 | 遮蔽理由 |
|---|---|
| `delete_file` | 插件提供回收站删除（D 类替换） |
| `delete_folder` | 同上 |
| `new_file_at` | 插件提供多选 + 父目录创建（D 类替换） |

**不再遮蔽 `rename_path`**：原生已含 retarget 与大小写处理，遮蔽等于用更差的实现替换更好的实现。

**禁止遮蔽清单**（原生已足够，遮蔽会造成不可逆缺失）：

```
copy_path_sidebar          new_folder              open_folder
open_containing_folder     open_terminal           find_in_folder
reveal_link_source         prompt_add_folder       remove_folder
refresh_folder_list        paste 相关
```

**硬约束**：

- `shadow.py` 完全独立，不 import 业务模块；加载异常必须捕获记录，不影响主功能
- 遮蔽依据是命令名，与菜单语言无关
- 空壳 `is_visible()` / `is_enabled()` 返回严格 `False`

### 5.11 clipboard.py 与 cmds/clipboard.py（第 4 项）

**分层**：`mysidebar/clipboard.py` 只维护「本次 ST 会话内」的剪贴板状态，不 import `sublime_plugin`，便于单测；`mysidebar/cmds/clipboard.py` 只做参数解析、文件操作与提示。

| 函数（`clipboard.py`） | 语义 |
|---|---|
| `set_cut(paths)` / `set_copy(paths)` | 覆盖写入本次剪贴板，记录模式与去重后的绝对路径 |
| `has_clipboard()` | 是否有待粘贴内容 |
| `consume()` | 取出 `(mode, paths)` 并**立即清空**，保证一次粘贴只消费一次 |
| `set_clipboard_text(text)` | 写系统剪贴板，异常上报后返回 False |

**命令行为**：

| 命令 | 行为 |
|---|---|
| Cut / Copy | 收集 `without_child_items()`，写入会话剪贴板，状态栏提示数量 |
| Paste | `consume()` → 目标目录 = 选中项（目录取自身，文件取父目录）→ `precheck` → 执行 → 一次性 `retarget_views` → 刷新侧边栏 |
| CopyRelativePath | 逐项 `SideBarProject.relative_path()`，多行写剪贴板；不在任何项目根内的项计入 skipped 并上报 |
| CopyFileName | 逐项 `SideBarItem.name`，多行写剪贴板 |

**粘贴语义（唯一自洽口径）**：

- **剪切**：每个源移动到「目标目录列表中第一个与源目录不同的目录」；无可用目标则计失败。剪切为**移动语义**，一个源只能落一个目的地。
- **复制**：每个源复制到**全部**目标目录，跳过与源目录相同的目标。
- `copytree` 使用 `dirs_exist_ok=True`（仅复制阶段；剪切阶段仍有同名存在性校验），避免目标目录已存在时半途失败。

**`precheck`（整批前置校验，任一源不通过则跳过该源并计失败）**：

| 场景 | 处理 |
|---|---|
| 源已不存在 | 上报 `clipboard.paste.missing` |
| 把目录粘贴到其自身内部（`is_within`） | 上报 `clipboard.paste.into_self` |
| 目标位置已有同名项（与源目录相同者除外） | 上报 `clipboard.paste_conflict` |

**`is_visible`**：Cut / Copy / CopyFileName 需 `paths` 非空；Paste 需 `paths` 非空**且** `has_clipboard()`；CopyRelativePath 需**至少一项**位于某个项目根内（`find_root()` 非空）。

**`reveal` 与回收站（T5 补齐项，落在 `cmds/trash_cmd.py`）**：

| 命令 | 行为 |
|---|---|
| `MySidebarRevealInFileManagerCommand` | `platform.reveal(path, dir_only=is_dir)`，失败项计数上报 |
| `MySidebarMoveToTrashCommand` | 确认（受 `confirm_before_trash` 控制）→ `trash.send()` → 失败项回落「永久删除确认」→ 成功后 `ViewResolver.close_views_for_paths()` 关闭已删除文件视图并刷新 |

**`close_views_for_paths` 实现约束**：必须先**收集全部目标视图**再逐个 `focus_view` + `close_file`；不可在遍历 `window.views()` 的同时调用 `focus_view`（会改变活动视图，导致相邻标签被漏关）。`is_dirty()` 的视图不关闭，避免丢失未保存内容。

---

## 6. 数据流（批量改名）

```
右键「批量改名…」
 → collect paths
 → TextInputHandler：正则
 → TextInputHandler：替换
 → ListInputHandler：选项（含目录 / 递归 / 仅文件名）
 → collect() → compute() → validate()
 → preview() 渲染预览视图
 → [确认] execute() Step0~5
 → rollback log → retarget views
 → 结果提示
```

输入链错误回到上一步用 `sublime_plugin.BackInputHandler()`，**不用 `show_input_panel`**。

---

## 7. 错误与边界清单

### 7.1 批量改名（1-18）

| # | 场景 | 处理 |
|---|---|---|
| 1 | 正则非法 | `validate()` 返回 False，留在当前输入步 |
| 2 | 正则为空 | 拒绝 |
| 3 | `$n` 引用越界 | 残留检查判非法 |
| 4 | 目标指向父路径外 | invalid |
| 5 | 同批重名 | conflict |
| 6 | 磁盘已有同名 | conflict |
| 7 | 换名 / 大小写变化 | 中间名 |
| 8 | 文件未保存 | 执行前 `is_dirty` 提示 |
| 9 | 只读文件 | `W_OK` 检查 → invalid |
| 10 | 超长路径 | 逐项检查 → invalid |
| 11 | 递归遇 symlink | 跳过并计数 |
| 12 | 只执行选中行 | `whole=False` |
| 13 | 中途失败 | 停止 + 逆序回滚 |
| 14 | 项目根 / mount point | `is_visible` 拒绝 |
| 15 | 基准根为空或根盘符 | 拒绝 |
| 16 | 超 `batch_rename_max_items` | 拒绝并提示缩小范围 |
| 17 | 无变化项 | skipped |
| 18 | 撤销时目标已存在 | 中止并提示 |

### 7.2 标签右键（19-23）

| # | 场景 | 处理 |
|---|---|---|
| 19 | `sheets_in_group(group)` 越界 | 命令无效，`is_visible` 返回 False |
| 20 | 目标 sheet 不是 `sublime.View`（ImagePreview 等） | `is_visible` 返回 False |
| 21 | 无 `file_name()`（未保存新文件） | `is_visible` 返回 False |
| 22 | 文件不在任何项目根内 | CopyRelativePath 不显示；其余两项正常 |
| 23 | 文件已被删除但标签仍存在 | Reveal 与 OpenDir 不显示 |

### 7.3 编码转换（24-29）

| # | 场景 | 处理 |
|---|---|---|
| 24 | 未二次确认 | 默认取消，不执行 |
| 25 | 视图轮询超限仍未 `is_loaded()` | 拒绝该项并继续下一项（不误判为文件损坏） |
| 26 | `view.is_dirty()` 为 True | 三选一确认；取消记 skipped，保存失败记 failed |
| 27 | 同一文件在多个视图中打开 | 中止该项并提示先关闭其余视图 |
| 28 | 源编码 == 目标编码 | skipped |
| 29 | 视图缓冲区文本读取异常 | 计入失败表，不写盘 |
| 30 | 超 `encoding_max_bytes` | 拒绝 |
| 31 | 目标文件只读 | 跳过计入失败表 |
| 32 | `set_encoding` 未生效 | 计入失败表，**不执行 save**，避免以错误编码落盘 |
| 33 | 转换后保存失败 | 计入失败表，提示编码已设置但未落盘 |

### 7.4 通用（34-38）

| # | 场景 | 处理 |
|---|---|---|
| 34 | macOS 回收站 API 不可用 | 回落永久删除确认 |
| 35 | Windows 网络盘回收站失败 | 同上 |
| 36 | 中文路径 + subprocess | 一律列表传参，禁 `shell=True` |
| 37 | 首次语言选择被取消 | 写入 `"en"`，不重复弹出 |
| 38 | 无窗口启动 | 跳过询问，保持 `null` |

---

## 8. 设置项

```json
{
  "ui_language": null,
  "encoding_max_bytes": 20971520,
  "menu_shadow_default_items": true,
  "batch_rename_max_items": 5000,
  "search_result_limit": 5000,
  "exclude_dirs_for_search": [".git", "node_modules", "vendor", "dist", "build"]
}
```

---

## 9. 复盘校验结论

### 9.1 第一轮复盘（需求遗漏 / 边界）

| 检查 | 结论 |
|---|---|
| 原生能力判定是否有事实依据 | 全部解包 `Default.sublime-package` 实测 |
| A 类功能是否都有原生命令指向 | 7 项全部标注对应命令，用户可在原菜单找到 |
| B 类是否只做缺失段 | 搜索只做批量操作视图；标签右键只加 3 项 |
| 标签右键取错文件风险 | 已约束必须用 `sheets_in_group(group)[index]`，禁用 `active_view()`；**T0-3 实测后追加修正**：sheet 为 `TextSheet`，须 `sheet.view()` 转 View |
| 编码流程是否会清空文件 | 已加 `is_loaded()` 前置校验，并新增二次确认、多视图检测、转换后立即保存 |
| 卸载三插件后是否真空 | 单文件 GBK 由原生 GB18030 覆盖，其余 A 类由原生命令覆盖 |
| **资源文件能否被 ST 加载** | 已修正：全部菜单/命令面板/设置/语法文件必须位于包根，子目录不会被扫描 |
| **插件生命周期能否被调用** | 已修正：新增包根入口 `MySideBar.py`，`mysidebar/__init__.py` 的 `plugin_loaded` 不会被自动调用 |
| **D 类替换是否真正发生** | 已修正：`menu_shadow_default_items` 默认改为 `true`，与 D 类判定一致 |
| **菜单生效时机表述是否统一** | 已闭环：T0-4 实测为即时生效，全文档统一为「即时生效、无需重启、无重载按钮」 |

### 9.2 第二轮复盘（架构 / 兼容性 / 迭代成本）

| 维度 | 结论 |
|---|---|
| 架构 | 四层清晰；`batch/`、`api.py` 无 ST UI 依赖，可独立单测 |
| 资源文件名 | 全部经实测确认存在，无虚构文件名 |
| 技术债 | 无 TODO、无 `except: pass`、无 `.dump`、无哨兵命令、无虚构 API |
| 迭代成本 | 功能收敛到 11 项 + 1 个可选开关，体量较 v1.x 减少约一半 |
| 国际化成本 | 英文唯一源 + 运行时覆盖，首次不引入生成脚本 |

### 9.3 v1.x → v2.0 判定变更记录

| 功能 | v1.x 结论 | v2.0 结论 | 依据 |
|---|---|---|---|
| 单文件 GBK 打开/另存 | 必做 | **A，不做** | 原生已内置 `Chinese (GB18030)` |
| 单文件重命名 | 必做 | **A，不做** | `rename_path` 已含 `v.retarget()` |
| 新建文件夹 | 必做 | **A，不做** | `new_folder` 已建父目录 |
| 在终端打开 | 必做 | **A，不做** | `open_terminal` 已启用 |
| 在文件夹中查找 | 必做 | **A，不做** | `find_in_folder` 复用 `find_in_files` |
| 打开所在目录 | 必做 | **A，不做** | `open_containing_folder` 含 UNC 处理 |
| 加入/从项目移除 | 必做 | **A，不做** | `prompt_add_folder` / `remove_folder` 均存在 |
| 复制路径 | 必做（绝对+相对） | **C，只做相对路径与文件名** | 原生 `copy_path_sidebar` 仅绝对路径单选 |
| 标签右键增强 | 未规划 | **B，新增 3 项** | `Tab Context.sublime-menu` 实测存在 |
| 遮蔽 `rename_path` | 在清单内 | **移出清单** | 原生实现更优 |
| `Tab Context.sublime-menu` | v1.1 误判为不存在 | **确认存在** | 解包实测纠正 |

---

## 10. 风险与待验证项

| 编号 | 风险 | 影响 | 应对 |
|---|---|---|---|
| V1 | 标签右键 `group`/`index` 注入行为在不同 ST 版本可能有差异 | 取错标签 | **T0-3 已实测**：`sheets_in_group` 返回 `TextSheet`，须经 `sheet.view()` 转 View；`active_view_index()` 不存在，改用 `get_view_index(view)`。注入的具体值待 T0-1 实测补全 |
| V2 | macOS `find_library('Foundation')` 可能返回 None | 插件加载崩溃 | **T0-2 已实测通过**：`Foundation` 与 `objc` 均可加载，`NSFileManager.defaultManager` 可用，回收站方案成立；保留 try/except 与失败回落永久删除确认 |
| V3 | 目录改名后 ST 索引与侧边栏刷新不一致 | 侧边栏显示旧名 | 改名后调用 `refresh_folder_list` |
| V4 | 单批接近上限（2000~5000）UI 短暂无响应 | 用户误判卡死 | 确认框提示预估耗时 + 状态栏进度 |
| V5 | 中文菜单文案随迭代增长 | 启动变慢 | 英文时完全不渲染；标记文件含版本号，仅在版本变更时重渲染 |
| V6 | 与第三方语言包共存时菜单项重名 | 出现两个同类项 | `menu_shadow_default_items` 默认 `true` 已遮蔽 3 项原生项；其余重复项由用户在设置中自行处理 |
| V7 | 卸载三插件后用户找不到某些功能 | 体验断裂 | README 提供「原插件功能 → 原生命令」对照表 |
| V8 | User 层菜单覆盖的生效时机不确定（即时 / 需重启） | 语言切换后菜单不更新 | **T0-4 已实测确认：即时生效**。写入 `Packages/User/.../Main.sublime-menu` 后未重启 ST，点击该菜单项即触发命令（日志出现「T0 标记命令被点击」）；`find_resources` 立即命中新文件，`decode_value` 解析为 `list`。结论：切语言后可立即刷新菜单，**不需要重启，也不需要重载按钮** |
| V9 | ST 实际 Python 版本与本地方案标注不一致 | 本地单测环境与运行时行为不符 | **T0-5 已实测确认**：ST build 4215，`Python 3.14.6`，`arch=x64`，`platform=osx`，`plugin_host-3.14`；本地 `.python-version` 标注 `3.14` 与运行时一致 |