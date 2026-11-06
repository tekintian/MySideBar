# MySideBar

Sublime Text 4 侧边栏增强插件。

在侧边栏右键菜单、标签右键菜单中补齐 ST 原生缺失的文件操作能力：中文编码自动识别与乱码修复、跨平台回收站删除、会话内剪切/复制/粘贴、批量编码转换、递归文件列表等。

[English](./README.md) | 简体中文

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

## 发布流程

`dev` 是唯一的开发分支，`main` 是由 CI 单向生成的产品分支，不承载任何手工改动。

### 分支与职责

| 分支 | 内容 | 谁写入 |
|---|---|---|
| `dev` | 开发分支。插件源码在 `src/`，另有 `docs/`、`tests/`、`tools/` 与完整开发文档 | 开发者手工提交 |
| `main` | 产品分支。`src/` 的内容扁平化到仓库根，外加 CI 生成的 `packages.json` | 仅 CI，每次发版强制覆盖 |

### 发版步骤

1. **同步版本号**。两处必须与即将打的 tag 一致（tag 去掉 `v` 前缀）：

   | 文件 | 内容 |
   |---|---|
   | `src/meta.py` | `__version__ = '1.0.1'` |
   | `src/messages/install.txt` | 首行 `MySideBar 1.0.1 - Installation` |

   CI 会校验这两处，不一致直接失败，不会产出错误的发布包。

2. **提交并推送 dev**：

   ```bash
   git add -A && git commit -m "chore: 版本号 1.0.1"
   git push origin dev
   ```

3. **打 tag 并推送**。tag 必须带 `v` 前缀且为三段数字：

   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```

4. **等待 CI 完成两个 job**：

   | Job | 做什么 |
   |---|---|
   | `release` | 校验版本号 → 校验发布文档 → 打包（排除 `.DS_Store`、`__pycache__`）→ 发布 Release（zip + `SHA256SUMS.txt`） |
   | `sync-main` | 把 `src/` 镜像到 `main` 根目录 → 用 `SHA256SUMS.txt` 里的 hash 生成 `packages.json` → `git push --force origin HEAD:main` |

5. **验证 main**。`packages.json` 的几个字段是 ST 能否正确安装的关键：

   | 字段 | 必须是 |
   |---|---|
   | `details` | `https://github.com/tekintian/MySideBar/blob/main/packages.json`（不能是仓库主页） |
   | `version` | 纯数字 `1.0.1`，**不带** `v` |
   | `url` | 指向该项 Release 的 zip，与资产名完全一致 |
   | `sha256` | 取自 `SHA256SUMS.txt`，与用户下载的 zip 一致 |

### 关键约束

- **tag 必须带 `v`**。GitHub Actions 的 `tags` 匹配是 glob 通配符而非正则，glob 无法表达"恰好三段数字"，所以 workflow 用 `v*` 触发，再在脚本里用正则 `v[0-9]+\.[0-9]+\.[0-9]+$` 精确校验。非法 tag（如 `v1.0`、`v1.0.1-beta`）会让 job 明确报错退出，不会静默跳过。
- **`version` 字段不带 `v`**。ST 的版本比较对 `v` 前缀不友好，所以 tag 是 `v1.0.1`，而包内版本号、zip 文件名、`packages.json` 的 `version` 都是 `1.0.1`。
- **不要手工改 `main`**。`sync-main` 用 `--force` 推送，且每次都在干净目录里新建仓库、全量复制，任何手工提交都会在下次发版时被完整覆盖。
- **历史 tag 不要混用格式**。旧的 `1.0.0`（无 `v`）已删除并重打为 `v1.0.0`，后续一律 `v` 前缀。
- **补发某个版本**可用手动触发，无需重打 tag：

  ```bash
  gh workflow run release --ref dev -f tag=v1.0.1
  ```

---

## 安装

> **注意**：插件包根是仓库的 `src/` 目录，`MySideBar.py` 等入口文件直接位于 `src/` 根层。仓库根另有 `tools/`（打包与发版脚本）、`tests/`（校验脚本）与 `docs/`（开发文档），这些都不属于插件运行时文件。
>
> 仓库根的 `packages.json` 是**过期的历史残留**，不要使用也不要修改：真正生效的清单由 CI 在每次发版时生成到 `main` 分支根目录。
>
> 本 README 是面向开发者的完整文档。面向用户的精简文档随插件发布，位于 [`src/README.md`](./src/README.md)（English）与 [`src/README_CN.md`](./src/README_CN.md)（中文）——用户在 `main` 分支和 release 压缩包里看到的就是它。改动用户可见行为时，两处需同步更新。
>
> 发布布局：`dev` 是开发分支，`main` 是由 CI 生成的产品分支。每次 release 时 CI 会把 `src/` 镜像到 `main` 并扁平化到仓库根目录，强制覆盖整条分支。请勿直接向 `main` 提交。

推荐的安装方式是 Package Control（`Add Repository` + `Install Package`），或使用下述手动方式。

### 方式一：Package Control 安装

1. `Ctrl+Shift+P` → `Package Control: Add Repository`，填入下面的清单地址（注意是 `packages.json`，不是仓库地址）
2. `Ctrl+Shift+P` → `Package Control: Install Package`，搜索并选择 `MySideBar`

```
https://raw.githubusercontent.com/tekintian/MySideBar/main/packages.json
```

Package Control 订阅的版本固定指向该 tag 的 Release 压缩包，压缩包顶层就是插件根，不会产生嵌套层级。

### 方式二：手动安装

把 `src/` 目录下的内容复制到 `Packages/MySideBar/`（`tests/`、`docs/`、`tools/` 不需要复制）：

```bash
# macOS / Linux 示例，路径按实际情况调整
rsync -av --exclude=__pycache__ \
  src/ "<Packages>/MySideBar"
```

安装后的目录结构必须是：

```
<Packages>/MySideBar/
├── MySideBar.py                  ← 必须在 MySideBar/ 根层
├── MySideBar.sublime-settings
├── Commands.sublime-commands
├── Side Bar.sublime-menu
├── Tab Context.sublime-menu
├── Tab Sidebar Context.sublime-menu
├── Main.sublime-menu
├── Default.sublime-keymap
├── meta.py
├── messages.json
├── .no-sublime-package           ← 必须存在，否则菜单翻译的覆盖层机制失效
├── .python-version               ← 内容必须是 3.8
├── messages/
│   └── install.txt
└── mysidebar/
    ├── api.py
    ├── i18n.py
    ├── cmds/
    └── ...
```

判断是否装对的标准：`<Packages>/MySideBar/MySideBar.py` 必须直接存在。如果变成了 `<Packages>/MySideBar/src/MySideBar.py`，则装错了层级，插件不会加载。

`Packages` 目录位置可通过 `Preferences` → `Browse Packages...` 查看。

### 方式三：开发方式（软链接到 `src/`）

适合需要跟随本仓库持续更新代码的场景，把 `src/` 软链为插件目录：

```bash
ln -s "/path/to/MySideBar/src" "<Packages>/MySideBar"
```

修改代码后，在 Sublime Text 中执行 `Ctrl+Shift+P` → `Sublime Text: Reload Plugin Host`（或直接在控制台执行 `sublime_plugin.reload_plugin("MySideBar.MySideBar")`）即可生效。

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

## 许可

见 [LICENSE](./LICENSE)。