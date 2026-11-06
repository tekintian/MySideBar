# MySideBar

Sublime Text 4 侧边栏增强插件。

在侧边栏右键菜单、标签右键菜单中补齐 ST 原生缺失的文件操作能力：中文编码自动识别与乱码修复、跨平台回收站删除、会话内剪切/复制/粘贴、批量编码转换、递归文件列表等。

---

## 亮点

### 1. 中文乱码自动修复，打开即正确显示

GB18030 / Big5 编码的中文文件在 ST 中打开常显示为乱码方块。本插件在文件加载时自动识别真实编码并静默重开，**无需手动逐个切换编码**。

难点在于中文编码极易互判——同一段字节用 GB18030 和 Big5 解码都能"成功"，但只有一个是对的。插件的做法：

- **只做单候选判定**：`locale` 决定唯一候选编码（`zh_CN`→GB18030、`zh_TW`→Big5、`ja_JP`→Shift JIS）。存在多个候选时直接放弃，从机制上杜绝误判，而不是靠"分数高低"去猜。
- **可信度校验**：解码结果还要过三道关卡才不会误判——PUA（私用区）字符占比必须低于 2%，Shift JIS 的半角片假名占比必须低于 30%（用于识破错误解码产生的大片半角片假名），并校验脚本族是否与编码匹配。
- **先判二进制与纯 ASCII**：二进制文件不误判，纯 ASCII 文件直接跳过，不做无意义的编码折腾。
- **重开结果二次验证**：不是发起重开就完事，而是延迟轮询校验（120ms 间隔、最多 30 次），确认编码真的切换成功；失败会明确放弃并记录日志，不会留下半处理状态。

### 2. 不产生 dump 废文件，不污染包目录，升级不丢配置

很多插件做菜单本地化时会改写包内文件或到处落地临时文件，结果留下 `xxx.bak`、`xxx.orig` 这类垃圾，或者被 `Package Control` 升级覆盖后文案错乱。本插件在这点上做了严格约束：

- **包内文件永不改写**：`Side Bar.sublime-menu` 等文件始终是英文原文，插件升级覆盖包内容不会损坏任何东西。
- **译文只落在 ST 官方覆盖层**：译文写入 `<Packages>/User/MySideBar/`，这是 ST 自身支持的机制，不额外产生文件。
- **切换即清理，不留残渣**：切回英文时直接删除覆盖层文件，包内英文原文自动生效；插件卸载时同步清理覆盖层与标记文件。
- **唯一持久产物是有意义的备份**：只有 `<Packages>/tmp/menu_backup/` 一个目录，用于在小语种之间来回切换时复用原文，且写入前先做幂等性校验，源文件被改动过就拒绝备份，避免脏数据污染后续所有切换。

### 3. 三个平台都进系统回收站，且零第三方依赖

删除文件不该是不可逆的。插件不使用 `os.remove`，而是真正调用系统的回收站能力，并且**不依赖任何第三方包**：

| 平台 | 实现方式 |
|---|---|
| macOS | 通过 `ctypes` 直接调用 Objective-C 运行时与 `NSFileManager`，无需安装 PyObjC |
| Windows | 调用 `SHFileOperationW`（`FOF_ALLOWUNDO`），文件进回收站而非直接消失 |
| Linux | 调用 `gio trash` |

能力不可用时（如 Linux 未装 `gio`、某些环境无 objc 运行时）会给出明确失败原因，而不是静默失败或降级成永久删除。

### 4. 批量操作不卡界面，也不会冲掉你的未保存修改

- **列表视图的批量操作**：递归遍历在异步线程执行，分批写入视图，不阻塞界面；大目录有结果条数上限保护（默认 5000 条，可配置），达到上限时停止遍历并明确提示已截断。
- **批量编码转换串行执行**：逐个文件处理，不会一次性打开几十个文件把编辑器拖死。
- **脏文件直接跳过**：已打开且**有未保存修改**的文件不会被编码转换覆盖，宁可跳过也不吞掉你的改动。
- **大文件保护**：超过 `encoding_max_bytes`（默认 20MB）的文件自动跳过并记录原因。
- **结果可追溯**：每个文件成功/跳过/失败及原因汇总到结果面板，不成功也让你知道为什么。

### 5. 界面语言即时切换，无需重启

`English` / `简体中文` / `繁體中文` 三语，切换后菜单立刻更新，不需要重启 Sublime Text，也不需要重新安装。文案表 key 三语完全对齐（各 111 项），缺 key 时逐级回退英文原文，不会显示空白或 `key` 字面量。

### 6. 纯 Python · 零依赖 · 三平台一致

只使用 ST4 内置 Python 运行时与标准库，没有外部依赖，不需要 pip 安装任何东西，macOS / Windows / Linux 行为一致。

---

## 功能


### 侧边栏右键菜单

| 菜单项 | 说明 |
|---|---|
| Open In New Window | 在 Sublime Text 新窗口中打开选中的文件/目录 |
| Open With Default Application | 用系统默认程序打开 |
| Cut / Copy / Paste | 会话内剪切、复制、粘贴（可跨目录粘贴整个目录树） |
| Copy Relative Path | 复制相对于项目根目录的路径 |
| Copy File Name | 复制文件名 |
| Duplicate | 创建副本（自动避免重名） |
| Move To | 移动到指定目录 |
| Move To Trash | 移入系统回收站（非永久删除） |
| List Files | 递归列出目录下所有文件到只读视图 |
| Convert Encoding | 批量转换文件编码 |

### 标签右键菜单

| 菜单项 | 说明 |
|---|---|
| Reveal In File Manager | 在文件管理器中定位该文件 |
| Copy Path | 复制该标签的完整路径 |
| Convert Encoding | 转换当前标签文件编码 |

### 文件列表视图

`List Files` 生成的只读列表视图支持：

- 选中行后按 `Enter` 打开对应文件
- 命令面板执行 `MySideBar: Copy Listed Paths` 批量复制路径
- 命令面板执行 `MySideBar: Move Listed To Trash` 批量移入回收站
- 支持排除目录/文件、结果条数上限、相对路径展示格式

### 编码处理

- 支持 UTF-8、UTF-16 LE/BE、GB18030、Big5、Shift JIS、EUC-KR、Windows 1252
- 打开文件时自动识别编码并静默修正乱码（可关闭）
- 自动识别仅在单候选编码时生效，避免 GB18030 与 Big5 互相误判
- 批量转换异步串行执行，不阻塞界面；已打开且有未保存修改的文件会被跳过
- 提供 `Encoding Doctor` 编码诊断报告，用于排查乱码问题

---

## 安装

### 通过 Package Control（GitHub 仓库方式）

1. `Preferences` → `Package Control` → `Add Repository`，填入本仓库地址
2. `Package Control` → `Install Package`，搜索 `MySideBar`

### 手动安装

将整个插件目录放入 Sublime Text 的 `Packages` 目录：

```
<Packages>/MySideBar/
├── MySideBar.py
├── MySideBar.sublime-settings
├── Side Bar.sublime-menu
├── ...
└── mysidebar/
```

`Packages` 目录位置可通过 `Preferences` → `Browse Packages...` 查看。

安装后重启 Sublime Text；首次运行会自动弹出语言选择面板。

---

## 使用

### 语言切换

三种方式，效果一致且立即生效：

1. `Preferences` → `Settings` 中将 `ui_language` 设为 `en` / `zh_CN` / `zh_TW`
2. `Preferences` → `Package Settings` → `MySideBar` → `Language` 子菜单
3. 命令面板执行 `MySideBar: UI Language - ...`

菜单未及时更新时，可执行 `Preferences` → `Package Settings` → `MySideBar` → `Reapply Menus` 强制重新应用。

### 配置

通过 `Preferences` → `Package Settings` → `MySideBar` → `Settings` 打开用户配置：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `ui_language` | `null` | 界面语言，`null` 表示未选择（首次运行弹窗） |
| `encoding_max_bytes` | `20971520` | 参与批量编码转换的单文件大小上限（字节） |
| `auto_detect_encoding` | `true` | 打开文件时是否自动检测编码 |
| `encoding_auto_locales` | `"zh_CN"` | 自动检测使用的 locale，决定唯一候选编码：`zh_CN`→GB18030，`zh_TW`→Big5，`ja_JP`→Shift JIS |
| `encoding_status_bar` | `true` | 是否在状态栏提示编码处理结果 |
| `list_files_result_limit` | `5000` | 文件列表最大行数，超出截断 |
| `list_files_exclude_dirs` | `[".git", "node_modules", "vendor", "dist", "build"]` | 列表时跳过的目录名 |
| `list_files_exclude_files` | `[".DS_Store", "Thumbs.db", "desktop.ini", "._*"]` | 列表时跳过的文件名，支持前缀通配 |
| `list_files_result_format` | `"relative"` | 列表展示格式，`relative` 显示相对项目根目录的路径 |
| `confirm_before_trash` | `true` | 移入回收站前是否确认 |

### 命令面板

| 命令 | 说明 |
|---|---|
| `MySideBar: List Files` | 递归列出文件 |
| `MySideBar: Move Listed To Trash` | 将列表中选中项移入回收站 |
| `MySideBar: Copy Listed Paths` | 复制列表中选中项的完整路径 |
| `MySideBar: Open Listed File` | 打开列表中选中的文件 |
| `MySideBar: Convert Encoding` | 批量转换编码 |
| `MySideBar: UI Language - ...` | 切换界面语言 |

---

## 平台说明

| 平台 | 回收站实现 |
|---|---|
| macOS | 通过 `ctypes` 调用 `NSFileManager.trashItemAtURL:`，无需安装 PyObjC |
| Windows | 调用 `SHFileOperationW`（`FO_DELETE` + `FOF_ALLOWUNDO`） |
| Linux | 调用 `gio trash`，未安装 `gio` 时该功能不可用 |

剪贴板（`Cut` / `Copy` / `Paste`）为插件会话内队列，不写入系统剪贴板，跨会话不保留，这是有意设计，用于安全地在项目内移动文件或目录。

---

## 快捷键

| 按键 | 作用范围 |
|---|---|
| `Enter` | 仅在 `List Files` 生成的列表视图中，打开当前行对应文件 |

---

## 文档

| 文档 | 内容 |
|---|---|
| [实现说明](./docs/MySideBar-04-实现说明-v1.0.md) | 按代码实际实现编写的架构、命令、配置、数据目录说明 |
| [技术方案](./docs/MySideBar-01-技术方案-v2.0.md) | 设计取舍与 ST4 原生能力实测结论 |
| [任务计划](./docs/MySideBar-02-任务计划-v2.0.md) | 分阶段实施计划 |
| [多语言编码兼容方案](./docs/MySideBar-03-多语言编码兼容方案-v1.2.md) | 编码探测与转换的专项设计 |

---

## 开发

插件由 `src/` 下的文件构成，直接部署到 `Packages/MySideBar/` 即可运行。新增命令的方式：

1. 在 `mysidebar/cmds/` 下新建模块
2. 定义 `MySidebarXxxCommand(sublime_plugin.WindowCommand)` 等命令类
3. 在对应 `*.sublime-menu` 中引用命令名

包根入口会递归发现所有命令类并自动注册，无需修改 `MySideBar.py`。命令名规则由 ST 自动转换：类名去掉 `Command` 后缀后转为下划线命名。

校验脚本位于 `tests/`（`_` 前缀文件不会被 ST 加载），在项目根目录执行：

```bash
python3 tests/_check.py
python3 tests/_menu_roundtrip.py
python3 tests/_i18n_keys.py
python3 tests/_entry_export.py
```

---

## 许可

见 [LICENSE](./LICENSE)。