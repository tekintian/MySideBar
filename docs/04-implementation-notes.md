# MySideBar 实现说明

本文档按**当前代码的实际实现**编写，用于说明插件由哪些文件构成、每个命令的真实行为、配置项语义、运行时产生的数据位置，以及本地校验方式。

- 方案与需求取舍见：[01-technical-design.md](./01-technical-design.md)
- 编码相关设计见：[03-encoding-strategy.md](./03-encoding-strategy.md)

---

## 1. 插件定位

Sublime Text 4 侧边栏增强插件，在侧边栏右键菜单、标签右键菜单中提供文件操作、剪贴板操作、批量编码转换等能力。所有命令均通过 `WindowCommand` / `ApplicationCommand` 实现，不修改 ST 原生功能，只追加命令。

运行时要求：ST 4（Python 3.8+ 运行时），无第三方依赖。

---

## 2. 目录结构

```
MySideBar/
├── MySideBar.py                     包根入口（唯一被 ST 直接加载的文件）
├── *.sublime-menu                   菜单定义（英文原文）
├── *.sublime-commands               命令面板条目
├── Default.sublime-keymap           快捷键绑定
├── MySideBar.sublime-settings       默认配置
└── mysidebar/                       实际实现包
    ├── __init__.py                  生命周期：加载命令模块、初始化语言、首次运行选语言
    ├── api.py                       领域模型：SideBarItem / SideBarSelection / SideBarProject / ViewResolver
    ├── strings.py                   多语言文案表（en / zh_CN / zh_TW）
    ├── i18n.py                      语言状态、文案取值、菜单动态翻译与覆盖层写入
    ├── encodings.py                 编码注册表（名称、Python codec、分组、优先级、BOM）
    ├── encoding_detect.py           编码探测（BOM → 二进制 → ASCII → UTF-8 → 单候选可信度判定）
    ├── trash.py                     跨平台回收站（macOS objc / Windows SHFileOperationW / Linux gio）
    ├── clipboard.py                 会话内剪贴板状态（剪切/复制队列）
    ├── platform.py                  跨平台工具（路径规范化、reveal、系统打开）
    ├── listener.py                  编码自动检测监听器 + 重开校验
    └── cmds/                        命令实现
        ├── open.py                  新窗口打开、系统默认程序打开
        ├── clipboard.py             剪切/复制/粘贴/复制相对路径/复制文件名
        ├── file_ops.py              创建副本（Duplicate）、移动到目录
        ├── trash_cmd.py             移入回收站
        ├── list_files.py            文件递归列表视图及其批量操作
        ├── encoding.py              批量编码转换
        ├── tab.py                   标签右键：定位、复制路径、单文件转换编码
        ├── settings.py              语言切换、手动重新应用菜单
        └── doctor.py                编码诊断报告
```

### 2.1 包根入口的特殊处理

`MySideBar.py` 不能直接 `from .mysidebar import ...`，因为 ST 以文件而非包的方式加载插件。实现方式是：

1. `_purge_stale_modules()` 清空 `sys.modules` 中残留的 `mysidebar*`，保证热重载不读到旧模块；
2. `_load_package()` 用 `importlib.util.spec_from_file_location` 以子模块搜索路径方式构造包；
3. `_export_command_classes()` 递归 `pkgutil.walk_packages`，把每个模块内**自定义来源**的 `WindowCommand`/`ApplicationCommand`/`EventListener` 等子类注入到模块全局命名空间，ST 才能识别命令；
4. 单个模块导入失败只打印堆栈并继续（`[MySideBar] failed to import ...`），不会拖垮整个插件。

因此新增命令时：在 `mysidebar/cmds/` 下新建模块并定义 `MySidebarXxxCommand(sublime_plugin.WindowCommand)` 即可自动注册，无需改入口文件。

---

## 3. 命令清单

所有命令名以 `my_sidebar_` 为前缀。

### 3.1 侧边栏菜单（`Side Bar.sublime-menu`）

| 菜单项 | 命令 | 参数 | 行为 |
|---|---|---|---|
| Open In New Window | `my_sidebar_open_in_new_window` | `paths` | 在 ST 新窗口打开选中路径 |
| Open With Default Application | `my_sidebar_open_with_default` | `paths` | 交由操作系统默认程序打开 |
| Cut | `my_sidebar_cut` | `paths` | 记录到会话内剪切队列 |
| Copy | `my_sidebar_copy` | `paths` | 记录到会话内复制队列 |
| Copy Relative Path | `my_sidebar_copy_relative_path` | `paths` | 计算相对项目根路径并写入系统剪贴板 |
| Copy File Name | `my_sidebar_copy_file_name` | `paths` | 仅复制文件名 |
| Duplicate | `my_sidebar_duplicate` | `paths` | 生成副本（自动避免重名） |
| Move To | `my_sidebar_move` | `paths` | 移动到选定目录 |
| Move To Trash | `my_sidebar_move_to_trash` | `paths` | 移入系统回收站 |
| List Files | `my_sidebar_list_files` | `paths` | 递归列出文件到只读视图 |
| Convert Encoding | `my_sidebar_convert_encoding` | `paths` | 批量转换编码 |

菜单分隔符均带 `id`（`my_sidebar_open` / `my_sidebar_clipboard` / `my_sidebar_file_ops` / `my_sidebar_tools`），便于被其他插件通过 `children` 引用扩展。

### 3.2 标签右键菜单（`Tab Context.sublime-menu` / `Tab Sidebar Context.sublime-menu`）

| 菜单项 | 命令 | 参数 |
|---|---|---|
| Reveal In File Manager | `my_sidebar_tab_reveal` | `group`、`index` |
| Copy Path | `my_sidebar_tab_copy_path` | `group`、`index` |
| Convert Encoding | `my_sidebar_tab_convert_encoding` | `group`、`index` |

两个菜单文件内容一致：ST 在不同入口（普通标签页右键、侧边栏文件标签右键）会分别读取它们，缺一即对应入口无菜单。

### 3.3 命令面板（`Commands.sublime-commands`）与列表视图内命令

| 命令面板条目 | 命令 |
|---|---|
| MySideBar: List Files | `my_sidebar_list_files` |
| MySideBar: Move Listed To Trash | `my_sidebar_list_files_trash` |
| MySideBar: Copy Listed Paths | `my_sidebar_list_files_copy` |
| MySideBar: Open Listed File | `my_sidebar_list_files_open` |
| MySideBar: Convert Encoding | `my_sidebar_convert_encoding` |
| MySideBar: UI Language - English / 简体中文 / 繁體中文 | `my_sidebar_set_language` |

另有 `my_sidebar_apply_menus`（手动重新应用菜单）与 `my_sidebar_encoding_doctor`（编码诊断报告）。

`my_sidebar_list_files_*` 系列均实现 `is_enabled()`：仅当当前视图是本插件生成的列表视图且存在可映射行时才可用，因此命令面板中会自动灰显。

### 3.4 快捷键（`Default.sublime-keymap`）

| 按键 | 命令 | 上下文条件 |
|---|---|---|
| `enter` | `my_sidebar_list_files_open` | `my_sidebar_list_files_result == true` |

该上下文键由 `cmds/list_files.py` 中的 `MySidebarListFilesContextListener.on_query_context()` 提供，值来自列表视图的 `settings["my_sidebar_list_files_result"]`。

---

## 4. 核心实现要点

### 4.1 领域模型（`api.py`）

- `SideBarItem`：单个文件/目录的属性（是否目录、是否项目内、扩展名等）与操作封装。
- `SideBarSelection`：封装侧边栏选中项；`without_child_items()` 过滤父子同时选中的重复项，避免递归删除/复制时对子项重复操作。
- `SideBarProject`：项目根目录管理，`folders()` 返回所有项目根，`relative_path()` 计算相对路径（不在任何根下时返回 `None`）。
- `ViewResolver`：根据路径找到已打开的视图，并在文件移动/删除后做视图重定向、关闭已失效标签。

### 4.2 剪贴板（会话内，`clipboard.py`）

剪贴板状态**不写系统剪贴板**，只在插件内保存 `(mode, paths)`：

- `Cut` 记录剪切队列，`Paste` 成功后清空队列；`Copy` 记录复制队列，粘贴后保留。
- 粘贴目标目录规则：目标为目录则粘到目录内；目标为文件则粘到其父目录；无有效目标时报 `clipboard.paste.no_target`。
- 冲突处理：目标已存在 → `clipboard.paste_conflict`；源不存在 → `clipboard.paste.missing`；目录粘进自身 → `clipboard.paste.into_self`。
- 结束时按成功/失败数量分别汇总提示。

### 4.3 回收站（`trash.py`）

无第三方依赖，按平台直接调用原生能力：

| 平台 | 实现 | 说明 |
|---|---|---|
| macOS | `ctypes` 加载 `libobjc`，`NSFileManager.trashItemAtURL:resultingItemURL:error:` | 不依赖 PyObjC；返回实际回收站位置 |
| Windows | `shell32.SHFileOperationW` + `FO_DELETE` | 带 `FOF_ALLOWUNDO` 进回收站、`FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI` 静默 |
| Linux | `gio trash <path>` | 未安装 `gio` 时返回明确的失败原因 |

`is_available()` 用于判断当前平台能力是否可用（macOS 看 objc 运行时是否可加载、Linux 看 `gio` 是否存在、Windows 恒为可用），避免在不支持的平台暴露不可用功能。

### 4.4 编码注册表与探测（`encodings.py` / `encoding_detect.py`）

编码以 ST 显示名作为唯一键，内部映射到 Python codec：

| ST 名称 | codec | 分组 | 优先级 |
|---|---|---|---|
| UTF-8 | `utf-8` | auto | 100 |
| UTF-16 LE | `utf-16-le` | auto | 99（BOM） |
| UTF-16 BE | `utf-16-be` | auto | 98（BOM） |
| Chinese (GB18030) | `gb18030` | auto | 60 |
| Chinese (Big5) | `big5hkscs` | auto | 59 |
| Japanese (Shift JIS) | `shift_jis_2004` | auto | 50 |
| Korean (EUC-KR) | `euc_kr` | manual | 40 |
| Western (Windows 1252) | `cp1252` | manual | 10 |

- 加载时校验 codec 可用性，缺失则**降级为 manual**并打印告警，不在运行时崩溃。
- `auto` 分组参与自动探测；`manual` 分组只能手动指定，防止东亚多编码互相误判。

探测顺序（`_detect_uncached`）：BOM → 二进制判定（命中则放弃）→ 纯 ASCII（命中返回 `None`，无需处理）→ 严格 UTF-8 校验 → 取 locale 的单候选编码做可信度判定。

`auto_candidates(locale)` 必须**恰好返回一个候选**才会判定，多于一个直接放弃，从设计上规避 GB18030/Big5 互判。locale 到候选的映射见 `LOCALE_CODECS`，并在 `LOCALE_ALIASES` 中归一化 `zh` / `zh_hans` / `zh_hant` / `ja` / `ko`。

可信度判定（`_trusted`）包含：文本合理性、半角片假名比例（`_half_kana_ratio`，用于识别 Shift_JIS 误判）、PUA 占比、脚本族匹配（`_script_is_plausible`）。

探测结果按 `(路径, locale)` 缓存，并以 `mtime + size` 做失效判断，文件变更后自动重算。

### 4.5 编码自动检测监听器（`listener.py`）

在 `on_load` 中对有文件路径的视图执行探测；仅当探测结果与当前视图编码不一致时才发起 `reopen`。重开后会以延迟轮询方式校验（`VERIFY_DELAY` / `VERIFY_LIMIT`）：

- 校验期间若仍在 loading 或编码未切到目标，则继续轮询；
- 超过上限仍不一致则放弃并打印 `reopen did not take effect for <file>`；
- `on_close` 清理该视图的待验证状态，避免内存残留。

### 4.6 批量编码转换（`cmds/encoding.py`）

流程为**异步串行**，逐个文件处理，避免阻塞 UI 与同时触发大量 IO：

1. 过滤路径（非文件、超 `encoding_max_bytes` 的跳过并记录）；
2. 对已打开的文件，若缓冲区为脏则直接跳过（不覆盖用户未保存内容）；
3. `window.open_file` 后轮询等待加载完成；
4. 以目标编码**整体重写缓冲区**并保存；
5. 汇总成功/跳过/失败原因，输出到结果面板。

单文件转换（`my_sidebar_tab_convert_encoding`）复用同一套编码注册表与重写逻辑。

### 4.7 文件列表（`cmds/list_files.py`）

- 无 `paths` 参数时默认取所有项目根目录；
- 递归遍历在异步线程（`set_timeout_async`）执行，分批写入视图，避免大目录卡顿；
- 排除规则：`list_files_exclude_dirs`（按目录名精确匹配与前缀）、`list_files_exclude_files`（支持 `._*` 这类前缀通配）；
- 结果上限 `list_files_result_limit`，达到上限后停止遍历并标记截断；
- 视图为 `scratch` + 只读，视图名通过 i18n 取值；
- 关键设计：视图 `settings` 中保存 `{行号: 绝对路径}` 映射（`LINES_KEY`），列表命令通过映射把选中行还原成路径，因此**列表内容本身可以是相对路径、可加表头、可被排序而不影响操作**；
- 每次生成列表前会清空并复用上一次的列表视图（`_source_view`），不会堆积大量 scratch 视图。

### 4.8 国际化（`i18n.py` + `strings.py`）

文案表为扁平 key 结构，三种语言各 111 个 key，key 完全对齐（缺 key 时回退英文表，再回退 key 本身）。

**菜单实时翻译的实现机制**（关键，容易误解）：

1. 备份：首次应用前，把包内英文菜单原文复制到 `<Packages>/tmp/menu_backup/`；
2. 校验：备份前先做一次幂等性校验（同一份内容连续两次“规范化转换”结果必须一致），不通过的源文件视为已被手工改动，拒绝建立备份，避免用脏备份覆盖后续生成结果；
3. 生成：以备份内容为输入，递归翻译 `caption`，**输出到 `<Packages>/User/MySideBar/<原名>`**——即 ST 的用户覆盖层，而不是改写包内文件；
4. 清理：切换语言时可安全覆盖写入；切回英文时直接**删除用户覆盖文件**，包内英文原文自动生效；
5. 幂等：`<Packages>/User/MySideBar/.applied` 记录 `语言:ST版本:目标菜单列表` 签名，签名一致则跳过重复生成；
6. 卸载：`plugin_unloaded` 调用 `clear_applied_menu()`，清理覆盖文件与标记，避免卸载后残留过期译文。

**分隔符处理**：`_transform_menu` 在列表层会剔除原分隔符并在需要处补回标准 `{"caption": "-"}`，因此输出菜单不含 `id`。这是有意为之——译文菜单属于覆盖层，不应被其他插件当作扩展锚点引用；扩展锚点应始终引用包内英文菜单。

**首次运行**：`ui_language` 为 `null` 时，`plugin_loaded` 延时 100ms 弹出语言选择面板；选择后持久化并提示生效。

### 4.9 编码诊断（`cmds/doctor.py`）

生成一份纯文本报告，包含：ST 版本/平台/架构、当前相关设置项、编码注册表内容、每个编码的校准样本判定结果、以及指定文件的探测结果与已打开视图的实际编码对比。用于排查“文件打开后仍乱码”类问题，报告路径按 config 生成后可直接打开。

---

## 5. 配置项（`MySideBar.sublime-settings`）

| 配置项 | 默认值 | 语义 |
|---|---|---|
| `ui_language` | `null` | `null` 表示未选择（首次运行弹窗）；可选 `en` / `zh_CN` / `zh_TW` |
| `encoding_max_bytes` | `20971520` | 参与批量编码转换的单文件大小上限（20MB），超出跳过 |
| `auto_detect_encoding` | `true` | 是否启用 `on_load` 编码自动检测 |
| `encoding_auto_locales` | `"zh_CN"` | 自动探测的 locale，决定唯一候选编码（`zh_CN`→GB18030、`zh_TW`→Big5、`ja_JP`→Shift_JIS） |
| `encoding_status_bar` | `true` | 是否在状态栏提示编码相关结果 |
| `list_files_result_limit` | `5000` | 列表结果最大行数，超出截断 |
| `list_files_exclude_dirs` | `.git`/`node_modules`/`vendor`/`dist`/`build` | 递归时跳过的目录名 |
| `list_files_exclude_files` | `.DS_Store`/`Thumbs.db`/`desktop.ini`/`._*` | 递归时跳过的文件名（支持前缀通配） |
| `list_files_result_format` | `"relative"` | 列表展示格式：`relative` 显示相对项目根路径并加表头 |
| `confirm_before_trash` | `true` | 移入回收站前是否需要确认 |

---

## 6. 运行时数据位置

| 路径 | 用途 | 生命周期 |
|---|---|---|
| `<Packages>/User/MySideBar/*.sublime-menu` | 当前语言的菜单覆盖层 | 切回英文或插件卸载时删除 |
| `<Packages>/User/MySideBar/.applied` | 已应用语言 + ST 版本签名 | 同上 |
| `<Packages>/tmp/menu_backup/` | 包内英文菜单原始备份 | 持久保留，供反复切换复用 |

设计要点：**包内文件始终是英文原文，任何语言状态下都不会被改写**，因此插件升级覆盖包内容不会丢失或错乱文案。

---

## 7. 本地校验

`_dev/tests/` 下为一次性校验脚本（`_` 前缀，不会被 ST 加载），在仓库根目录执行，可按需单独运行：

| 脚本 | 校验内容 |
|---|---|
| `_check.py` | 主要断言集合（含入口守卫、菜单结构等） |
| `_i18n_keys.py` | 三语言文案 key 对齐 |
| `_menu_roundtrip.py` | 菜单翻译/还原幂等性 |
| `_encoding_detect.py` | 探测算法用例 |
| `_encoding_roundtrip.py` | 编码读写往返一致性 |
| `_calibrate_multilang.py` | 多语言样本校准 |
| `_listener_case.py` / `_listener_roundtrip.py` | 监听器重开与校验逻辑 |
| `_import_order.py` | 包内模块导入顺序与独立性 |
| `_entry_export.py` | 包根命令类导出正确性 |
| `_smoke.py` | 冒烟检查 |
| `_probe1252.py` | CP1252 专项探测 |

这些脚本依赖 `import sublime` 的桩（部分脚本自带），运行前请确认脚本内的桩路径与本机一致。

---

## 8. 已知边界

- 编码自动检测只在 `auto` 分组、且 locale 单候选时生效；多候选场景（如同时存在 GB18030 与 Big5 需求）必须手动切换编码。
- `list_files` 结果视图为只读的 scratch 视图，关闭不提示保存；视图内容与行号映射在重新生成时整块重置。
- 剪贴板队列仅存在于当前 ST 会话，跨会话不保留（与系统剪贴板行为不同，属设计取舍）。
- 回收站支持依赖平台原生能力；Linux 无 `gio` 时该功能不可用，命令会给出明确失败原因。