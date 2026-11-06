> **本文档是发布副本。**
>
> 你当前所在的是 `main` 分支。该分支由 CI 自动生成：每次 release 时，CI 会把插件源码目录（`dev` 分支的 `src/`）镜像到 `main` 并扁平化到仓库根目录，**整条分支被完全覆盖**。任何直接提交到这里的改动，都会在下一次发版时被静默丢弃。
>
> 要修改插件请编辑 `dev` 分支。反馈问题或提需求请走 [Issues](https://github.com/tekintian/MySideBar/issues)。

---

# MySideBar

Sublime Text 4 侧边栏增强插件。

在侧边栏右键菜单、标签右键菜单中补齐 ST 原生缺失的文件操作能力：中文编码自动识别与乱码修复、跨平台回收站删除、会话内剪切/复制/粘贴、批量编码转换、递归文件列表等。

[English](./README.md) | 简体中文

---

## 安装

需要 Sublime Text 4（build 4000 及以上）。零外部依赖，无需 `pip install` 任何东西。

### Package Control 安装

1. `Ctrl+Shift+P` → `Package Control: Add Repository`，填入：

```
https://raw.githubusercontent.com/tekintian/MySideBar/main/packages.json
```

2. `Ctrl+Shift+P` → `Package Control: Install Package`，搜索并选择 `MySideBar`。

### 手动安装

从 [Releases](https://github.com/tekintian/MySideBar/releases) 下载最新的 `MySideBar-<version>.zip`，解压到 `Packages/MySideBar/`。压缩包顶层**就是**插件根，因此 `MySideBar.py` 必须直接落在 `Packages/MySideBar/MySideBar.py`。

`Packages` 目录位置可通过 `Preferences` → `Browse Packages...` 查看。

安装后重启 Sublime Text，首次运行会自动弹出语言选择面板。

---

## 菜单项

### 侧边栏右键菜单

| 菜单项 | 说明 |
|---|---|
| Open In New Window | 在新窗口中打开选中的文件/目录 |
| Open With Default Application | 用系统默认程序打开 |
| Cut / Copy / Paste | 会话内剪切、复制、粘贴（可跨目录粘贴整个目录树） |
| Copy Relative Path | 复制相对于项目根目录的路径 |
| Copy File Name | 复制文件名 |
| Duplicate | 创建副本，自动避免重名 |
| Move To | 移动到指定目录 |
| Move To Trash | 移入系统回收站，绝不永久删除 |
| List Files | 递归列出目录下所有文件到只读视图 |
| Convert Encoding | 批量转换文件编码 |

### 标签右键菜单

| 菜单项 | 说明 |
|---|---|
| Reveal In File Manager | 在文件管理器中定位该文件 |
| Copy Path | 复制该标签的完整路径 |
| Convert Encoding | 转换当前文件编码 |

---

## 命令面板

| 命令 | 说明 |
|---|---|
| `MySideBar: List Files` | 递归列出文件 |
| `MySideBar: Open Listed File` | 打开列表选中行对应的文件 |
| `MySideBar: Copy Listed Paths` | 复制列表中选中项的完整路径 |
| `MySideBar: Move Listed To Trash` | 将列表中选中项移入回收站 |
| `MySideBar: Convert Encoding` | 批量转换编码 |
| `MySideBar: UI Language - ...` | 切换界面语言 |
| `MySideBar: Encoding Doctor` | 诊断文件为何显示乱码 |

列表视图中选中某行后按 `Enter` 即可打开该文件。

---

## 编码修复

以 GB18030、Big5、Shift JIS、EUC-KR 或 Windows 1252 保存的文件，在 Sublime Text 中打开时常显示为乱码方块。本插件在文件加载时识别真实编码并静默重开，无需逐个文件手动切换编码。

- 只有唯一候选编码时才自动识别，候选由 locale 决定，因此 GB18030 与 Big5 不会互相误判；存在歧义时宁可不处理，也不猜测。
- 二进制文件与纯 ASCII 文件直接跳过。
- 重开结果会轮询校验；失败会记录日志并明确放弃，不留半处理状态。
- 已打开且有未保存修改的文件，绝不会被批量转换覆盖。
- 超过 `encoding_max_bytes`（默认 20 MB）的文件会被跳过并记录原因。

可通过 `"auto_detect_encoding": false` 整体关闭该功能。

---

## 界面语言

`English` / `简体中文` / `繁體中文`。切换立即生效，无需重启，也无需重装。

三种等效方式：

1. `Preferences` → `Settings` 中将 `ui_language` 设为 `en` / `zh_CN` / `zh_TW`
2. `Preferences` → `Package Settings` → `MySideBar` → `Language`
3. 命令面板执行 `MySideBar: UI Language - ...`

菜单未及时刷新时，执行 `Preferences` → `Package Settings` → `MySideBar` → `Reapply Menus`。

译文不会改写包内任何文件，而是写入 ST 官方覆盖层 `<Packages>/User/MySideBar/`；切回英文时会被清理干净。因此插件升级不会破坏任何内容，你的配置也永远不会被覆盖。

---

## 配置

通过 `Preferences` → `Package Settings` → `MySideBar` → `Settings` 打开：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `ui_language` | `null` | 界面语言；`null` 表示未选择（首次运行弹窗） |
| `auto_detect_encoding` | `true` | 打开文件时是否自动识别并修复编码 |
| `encoding_auto_locales` | `"zh_CN"` | 决定唯一候选编码的 locale：`zh_CN`→GB18030，`zh_TW`→Big5，`ja_JP`→Shift JIS |
| `encoding_max_bytes` | `20971520` | 参与转换的单文件大小上限（字节） |
| `encoding_status_bar` | `true` | 是否在状态栏提示编码处理结果 |
| `confirm_before_trash` | `true` | 移入回收站前是否确认 |
| `list_files_result_limit` | `5000` | 文件列表最大行数，超出截断 |
| `list_files_exclude_dirs` | `[".git", "node_modules", "vendor", "dist", "build"]` | 列表时跳过的目录名 |
| `list_files_exclude_files` | `[".DS_Store", "Thumbs.db", "desktop.ini", "._*"]` | 列表时跳过的文件名，支持前缀通配 |
| `list_files_result_format` | `"relative"` | 列表展示格式；`relative` 显示相对项目根目录的路径 |

列表有意设上限：达到上限即停止遍历并明确提示，而不是在超大目录下把编辑器卡死。

---

## 平台说明

| 平台 | 回收站实现 |
|---|---|
| macOS | 通过 `ctypes` 调用 `NSFileManager.trashItemAtURL:`，无需 PyObjC |
| Windows | 调用 `SHFileOperationW`（`FO_DELETE` + `FOF_ALLOWUNDO`） |
| Linux | 调用 `gio trash`；未安装 `gio` 时不可用 |

回收站能力不可用时会给出明确失败原因，绝不静默降级为永久删除。

`Cut` / `Copy` / `Paste` 是插件会话内的队列：不写入系统剪贴板，跨会话不保留。这是有意设计，保证在项目内移动文件与目录始终安全可回退。

---

## 许可

MIT，见 [LICENSE](./LICENSE)。