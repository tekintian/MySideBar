# MySideBar 任务计划

> 版本：v2.0（与《MySideBar 技术方案 v2.0》配套）
> 前置：技术方案 v2.0 经评审确认后执行
> 判定基准：ST4 编辑器内置能力

---

## 1. 任务总览

| 阶段 | 任务 | 产出 | 依赖 |
|---|---|---|---|
| P0 验证 | T0 | 5 项真风险实测结论 | 无 |
| P1 骨架 | T1-T4 | 可加载的插件骨架、i18n、平台层、api | T0 |
| P2 基础能力 | T5-T9 | 文件操作、打开方式、剪贴板、编码批量、搜索 | T4 |
| P3 标签增强 | T10 | 标签右键 3 项 | T4 |
| P4 收尾 | T16-T18 | 菜单、遮蔽、设置、文档 | 全部 |

---

## 2. 任务明细

### T0 前置验证（5 项，全部为真实不确定点）

| 编号 | 验证内容 | 通过标准 |
|---|---|---|
| **T0-1** | 标签右键 `group`/`index` 注入行为 | 分别在「活动标签右键」「非活动标签右键」「侧边标签列表右键」三种场景下，用一个临时命令打印 `group` 与 `index`，确认能准确取到被右键的标签；**非活动标签不得取到 active_view** |
| **T0-2** | macOS 回收站 API 可用性 | **已实测通过**：`Foundation` 与 `objc` 均可加载，`NSFileManager.defaultManager` 可用，回收站方案成立 |
| **T0-3** | `sheets_in_group` 返回对象的真实类型 | **已实测完成**：返回 `TextSheet`，`isinstance(sheet, sublime.View)` 恒为 `False`；须 `sheet.view()` 转 View。`get_view_index(view)` 返回 `(group, index)`。`active_view_index()`、`sublime.Encoding` 均不存在 |
| **T0-4** | User 层菜单覆盖的生效时机 | **已实测完成：即时生效**。写入 `Packages/User/MySideBarT0/Main.sublime-menu` 后未重启 ST，菜单项即可点击并触发命令；`find_resources` 立即命中，`decode_value` 解析为 `list` |
| **T0-5** | ST 实际 Python 版本 | **已实测完成**：ST build 4215，Python 3.14.6，osx-x64，`plugin_host-3.14`，`.python-version` 标注 `3.14` 正确 |

> 注：「菜单覆盖优先级」「`Tab Context.sublime-menu` 是否存在」「原生是否内置 GB18030」均已由技术方案第 1 章实测确认，**不再列为验证项**。
> 结论必须回写技术方案 V1、V2、V8、V9。

---

### T1 插件骨架

| 项 | 内容 |
|---|---|
| 创建 | `.no-sublime-package`（空文件）、`.python-version`（以 T0-5 实测为准）、**包根入口 `MySideBar.py`**、`mysidebar/__init__.py` |
| 包根入口 | `MySideBar.py` 承担 `plugin_loaded()` / `plugin_unloaded()`，内部调用 `mysidebar.on_plugin_loaded()`；同时负责 `import mysidebar` 触发子包全部模块加载（命令类由此完成注册） |
| 资源位置 | 全部 `*.sublime-menu`、`*.sublime-commands`、`*.sublime-settings`、`*.sublime-syntax` **必须位于包根**，禁止放入 `menus/`、`syntaxes/` 等子目录（子目录不会被 ST 扫描，且无报错） |
| `plugin_loaded` | 加载设置 → 若 `ui_language == null` 且存在窗口则询问语言 → 调用 `i18n.apply_menu()` |
| `plugin_unloaded` | 清理标记文件、不残留 |
| 通过标准 | ST 控制台无报错；`view.run_command` 能调到占位命令；`Preferences → Package Settings` 出现 MySideBar 项；包根菜单文件被实际加载（右键可见） |

---

### T2 i18n

| 项 | 内容 |
|---|---|
| 文件 | `mysidebar/i18n.py` |
| 内容 | `t(key, **kw)`、`set_language(lang)`、`get_language()`、`apply_menu()`、`clear_applied_menu()` |
| 约束 | **禁止**任何区域自动探测；`null` 表示未选择；取消询问写入 `"en"` |
| 菜单生效 | T0-4 已确认即时生效：切语言后立即重写 User 层菜单即刷新，提示「菜单已切换」。**禁止任何「请重启」文案** |
| 通过标准 | 三种语言切换后菜单文案正确；标记文件版本一致时跳过重写；无窗口启动不询问且不报错；切语言后的提示与实际行为一致 |

---

### T3 平台层

| 项 | 内容 |
|---|---|
| 文件 | `mysidebar/platform.py`、`mysidebar/trash.py` |
| `platform.py` | `reveal(path, dir_only=False)`、`open_with_default(path)`；macOS 用 `open -R` / `open`，Windows 用 `explorer /select,` / `start`，Linux 用 `xdg-open`；**全部列表传参，禁 `shell=True`** |
| `trash.py` | `send2trash(path)`；macOS 走 Foundation，Windows 走 `SHFileOperation`，Linux 走 `gio trash`；失败回落「确认后永久删除」 |
| 通过标准 | 三平台分支可单独测；中文路径与空格路径均正常；macOS 回收站能力 T0-2 已确认 |

---

### T4 api 层

| 项 | 内容 |
|---|---|
| 文件 | `mysidebar/api.py` |
| 类 | `SideBarSelection`（`files`/`dirs`/`items`/`without_child_items`）、`SideBarProject`（`folders`/`project_data`/`find_root`）、`SideBarItem`（`join`/`dirname`/`exists`/`create`/`copy`/`move`/`retarget_views`/`reveal`） |
| 硬约束 | 父子判断用 `os.path.commonpath`；`retarget_views` 用 `os.path.normcase`；**禁止 `except: pass`** |
| 通过标准 | 可脱离 ST 用伪 `paths` 单测；`find_root` 在多项目工作区返回最长匹配根 |

---

### T5 文件操作（新建 / 复制副本 / 移动）

| 项 | 内容 |
|---|---|
| 文件 | `mysidebar/cmds/file_ops.py`、`mysidebar/cmds/trash_cmd.py` |
| 命令 | `MySidebarDuplicateCommand`、`MySidebarMoveCommand`、`MySidebarMoveToTrashCommand` |
| 说明 | **不实现单文件重命名**（A 类，用原生 `rename_path`）；**不实现新建文件**（A 类，原生 `new_file_at` 已覆盖，已删除插件版避免重复）；**侧边栏不提供「定位」菜单项**（与原生 `Reveal in Finder` 完全等价，属 A 类重复，仅保留标签右键的定位能力） |
| 回收站 | `confirm_before_trash` 为真时先 `show_ok_cancel_dialog`；`trash.is_available()` 为假或单项失败时回落「永久删除确认」；成功后关闭已删除文件的视图并刷新侧边栏 |
| `is_visible` | 带 `paths` 参数，严格返回 bool |
| 通过标准 | 多选 2 个目录分别新建成功；对 `a/b/c/x.txt` 路径的新建自动建 `a/b/c`；复制副本自动命名 `x copy.txt` 并递增；移动后视图 retarget 正确；删除后进入系统回收站且标签被关闭 |

---

### T6 打开方式扩展

| 项 | 内容 |
|---|---|
| 文件 | `mysidebar/cmds/open.py` |
| 命令 | `MySidebarOpenWithDefaultCommand`、`MySidebarOpenInNewWindowCommand` |
| 不做 | 打开所在目录（原生 `open_containing_folder`）、在终端打开（原生 `open_terminal`）、在文件夹中查找（原生 `find_in_folder`）；**不做「在另一分组打开」**（分屏拖拽与 `View → Layout` 已覆盖，且 `open_file(group=)` 无法处理目录与单分组场景） |
| 通过标准 | 图片/PDF 用系统程序打开；新窗口打开后原窗口不变；目录在新窗口中成为项目根 |

---

### T7 剪贴板与路径复制

| 项 | 内容 |
|---|---|
| 文件 | `mysidebar/cmds/clipboard.py`（命令层）、`mysidebar/clipboard.py`（会话内剪切/复制状态） |
| 命令 | `MySidebarCutCommand`、`MySidebarCopyCommand`、`MySidebarPasteCommand`、`MySidebarCopyRelativePathCommand`、`MySidebarCopyFileNameCommand` |
| 约束 | 剪切状态在本次 ST 会话内维护，**粘贴后立即清空**（剪切与复制均消费一次）；粘贴目标同名冲突走 `conflict` 提示并计入失败数 |
| 状态层 | `clipboard.py` 独立于命令层，提供 `set_cut` / `set_copy` / `consume` / `has_clipboard` / `set_clipboard_text`，不 import `sublime_plugin` |
| 粘贴语义 | 剪切：多选源按「目标目录列表的第一个非源目录」逐个移动；复制：源逐个复制到**全部**目标目录；两种情况均先整批 `precheck`（自身内部 / 同名已存在），任一源冲突即跳过该源并计失败 |
| 相对路径 | 以 `SideBarProject.find_root()` 最长匹配根为基准；不在任何根内的项计入 skipped 并不写入剪贴板 |
| 不做 | 复制绝对路径（原生 `copy_path_sidebar`） |
| 通过标准 | 剪切 A 粘贴到 B 后 A 消失、B 出现；复制粘贴不删除源；相对路径在多项目下取最长匹配根；多选复制文件名输出多行 |

---

### T8 批量编码转换

| 项 | 内容 |
|---|---|
| 文件 | `mysidebar/cmds/encoding.py` |
| 范围 | **仅批量**。单文件请用原生 `Chinese (GB18030)` / UTF-8 菜单 |
| 目标编码 | 4 项：`Chinese (GB18030)` / `UTF-8` / `UTF-16 LE` / `UTF-16 BE`，取自 `mysidebar/encodings.py`，**禁止**出现 `GBK` 字样 |
| 流程 | 严格按技术方案 5.7 的 11 步：选目标 → **二次确认** → 定位/轮询 `is_loaded` → 只读 → 大小 → 同编码 skipped → **多视图检测** → `is_dirty` 三选一 → `view.substr` 取文本 → 重写缓冲区 → `set_encoding_checked` → `save` 后回查 |
| 关键修正 | 文本**必须取自视图缓冲区**（`view.substr`），不得读盘再 `decode`，避免重复解码破坏内容 |
| 破坏性 | 转换以整体重写缓冲区实现，**清空 undo 历史且不可撤销**；二次确认文案必须明示 |
| 多视图 | 同一 `file_name` 在多个视图中打开时**中止该项**，提示先关闭其余视图 |
| 批量 | 异步串行推进，逐项执行不中断整批；结果汇总到 `create_output_panel`（`output.my_sidebar_encoding`） |
| 通过标准 | GB18030 文件批量转 UTF-8 后内容可读且无乱码；取消二次确认后不执行任何写盘；未加载文件不会被误判为失败；同一文件双视图打开时该项被跳过并给出原因；同编码文件不计入成功数；`set_encoding` 未生效时不以错误编码落盘 |

---

### T9 搜索结果批量操作视图

| 项 | 内容 |
|---|---|
| 文件 | `mysidebar/cmds/search.py` |
| 定位 | **不做第二个 Goto Anything**。只把搜索结果变成可多选的批量操作清单 |
| 命令 | `MySidebarSearchFilesCommand`（生成结果 scratch 视图）、`MySidebarSearchTrashCommand`、`MySidebarSearchCopyCommand` |
| 约束 | 遍历在 `set_timeout_async`；结果分批 append（每批 200 行），避免一次大 insert 卡 UI；上限 `search_result_limit`；排除 `exclude_dirs_for_search`；多根目录时每根按自身为基准生成相对路径 |
| 行到路径映射 | 结果视图只存文本行，行→绝对路径映射存于视图设置 `my_sidebar_search_lines`；批量动作按选中行查表，重名行追加 `  (n)` 后缀保证唯一 |
| 通过标准 | 5000 文件目录不卡 UI；结果视图只读且为 scratch；选中 3 行送回收站后 3 个文件均进回收站 |

---

### T10 标签右键增强（3 项）

| 项 | 内容 |
|---|---|
| 文件 | `mysidebar/cmds/tab.py` |
| 命令 | `MySidebarTabRevealCommand`、`MySidebarTabCopyPathCommand`、`MySidebarTabConvertEncodingCommand` |
| 统一取视图 | `_resolve_tab_view(window, group, index)`：`sheets_in_group(group)` → 越界返回 None → `isinstance(sheet, sublime.View)` → `file_name()` 非空 → 返回 |
| **禁止** | 使用 `window.active_view()`（会取到当前聚焦标签而非被右键标签） |
| `is_visible` | 三命令均带 `group`/`index` 参数并返回严格 bool；三项均要求文件存在；ConvertEncoding 额外排除 scratch 视图 |
| 菜单 | 包根 `Tab Context.sublime-menu`、`Tab Sidebar Context.sublime-menu` 追加三项，`args` 为 `{"group": -1, "index": -1}` |
| `is_enabled` | 与 `is_visible` 返回同一 bool，防止菜单隐藏而命令面板仍可执行 |
| 转换编码 | 委托 `window.run_command("my_sidebar_convert_encoding", {"paths": [file]})`，不复制编码转换逻辑 |
| 通过标准 | 在**非活动标签**上右键，定位到的是该标签的文件而不是当前活动文件；图片预览标签上三项不显示；未保存新标签上三项不显示；scratch 标签上转换编码不显示 |

---

### T16 菜单资源（已完成）

| 项 | 内容 |
|---|---|
| 文件 | 包根：`Side Bar.sublime-menu`、`Tab Context.sublime-menu`、`Tab Sidebar Context.sublime-menu`、`Main.sublime-menu`、`Context.sublime-menu`、`Commands.sublime-commands` |
| 约束 | **全部必须在包根**，禁止放入 `menus/` 子目录（不会被加载且无报错）；**不提供** `Side Bar Mount Point.sublime-menu`（原生已含 `remove_folder`）；**不提供** 任何语言后缀菜单文件名（该机制不存在） |
| 菜单项 | 仅列 C/D/B 类功能；A 类不出现 |
| 通过标准 | 侧边栏右键出现新增项且与原生命中不重复；标签右键出现 3 项；命令面板可搜到全部命令；**确认 ST 实际加载了包根菜单文件** |

**落地结论**：

1. `Context.sublime-menu` 内容为空数组 `[]`，即编辑器右键不注入任何自定义菜单项。该文件保留是为了让 `i18n._MENU_TARGETS` 的翻译机制维持完整文件名集合，避免切换语言时报告源文件缺失。
2. `Context.sublime-menu` 已加入 `i18n._MENU_TARGETS`；其内容为空时 `apply_menu()` 走「空菜单跳过」分支，不写入 User 层也不报错。
3. `Commands.sublime-commands` 只登记实际存在的命令，caption 统一 `MySideBar: ...` 前缀，便于命令面板聚合检索；已随功能下线同步移除失效入口。
4. 三语文案表只保留仍在使用中的键，功能下线后对应的 `*_caption` 与错误提示键须同步删除，避免残留死文案。

**自测覆盖（`_check.py` 菜单段）**：JSON 可解析、`Context.sublime-menu` 必须为空数组、三语文案不得残留已下线功能的键、设置项不得残留已下线功能的项、`i18n._MENU_TARGETS` 已注册 `Context.sublime-menu`。

**遗留说明**：菜单文件**实际加载效果**属 ST 运行时行为（需重启 ST 后人工确认右键菜单出现），离线自测只校验资源结构与翻译键完整性。

---

### T17 菜单遮蔽（默认开启）

| 项 | 内容 |
|---|---|
| 文件 | `mysidebar/cmds/shadow.py` |
| 默认值 | `menu_shadow_default_items: true` |
| 理由 | 2 项均判定为 **D 类（原生体验差，自研替换）**；D 类要求替换真正发生，否则原生永久删除仍暴露在菜单中，与自研回收站删除并存 |
| 可遮蔽 | **仅 2 项**：`delete_file`、`delete_folder` |
| 禁止遮蔽 | `copy_path_sidebar`、`new_file_at`（插件版已删，遮蔽会导致无法新建文件）、`new_folder`、`open_folder`、`open_containing_folder`、`open_terminal`、`find_in_folder`、`reveal_link_source`、`prompt_add_folder`、`remove_folder`、`refresh_folder_list`、`rename_path` |
| 硬约束 | `shadow.py` 独立，不 import 业务模块；加载异常必须捕获记录，**不得导致原生命令消失**；用户可在设置中关闭以恢复原生项 |
| 通过标准 | 默认状态下 2 项被替换且其余与原生命中一致；设置关闭后菜单与原生完全一致；人为让 shadow.py 抛异常，原生命令仍正常显示 |

---

### T18 设置与文档

| 项 | 内容 |
|---|---|
| 文件 | `MySideBar.sublime-settings`、`messages/install.txt`、`README.md` |
| 设置项 | `ui_language`（null）、`encoding_max_bytes`（20971520）、`menu_shadow_default_items`（false）、`search_result_limit`（5000）、`exclude_dirs_for_search` |
| README | **必须包含「原插件功能 → 原生命令」对照表**，列出 7 项 A 类功能去向，避免用户卸载后找不到功能 |
| 通过标准 | 设置全部有默认值与注释；README 对照表覆盖 7 项 A 类 |

---

## 3. 质量门禁（全部任务通用）

| # | 门禁 |
|---|---|
| 1 | 无 TODO、无 `except: pass`、无注释屏蔽代码 |
| 2 | 用户可见字符串一律经 `i18n.t()`，禁止硬编码 |
| 3 | `subprocess` 一律列表传参，禁止 `shell=True` |
| 4 | 文件操作前必须校验存在性、可写性与父子边界（`commonpath`） |
| 5 | 批量操作必须有回滚路径 |
| 6 | **所有 `is_visible` / `is_enabled` / `is_checked` / `description` 签名必须与 `run()` 参数一致，且返回严格 bool**，否则菜单项静默失效 |
| 7 | **所有 `*.sublime-menu` / `*.sublime-keymap` / `*.sublime-settings` / `*.sublime-commands` / `*.sublime-syntax` 文件名必须与 ST 实际资源名逐字一致，且必须位于包根**（子目录不会被扫描且无报错） |
| 8 | `api.py`、`platform.py`、`clipboard.py`、`encodings.py`、`encoding_detect.py`、`trash.py` 不得 import `sublime_plugin`，必须可脱离 ST 单测 |
| 9 | 标签相关命令禁止使用 `window.active_view()` 取被右键标签 |
| 10 | 编码转换前必须校验 `view.is_loaded()`，禁止对未加载视图写盘 |
| 11 | **插件生命周期函数只能定义在包根 `.py` 入口文件**，子包 `__init__.py` 的 `plugin_loaded` 不会被 ST 调用 |
| 12 | **编码转换必须依次满足：二次确认 → 多视图检测 → 转换后立即 save**，三者缺一不可 |
| 13 | **文档与实践不得出现互相矛盾结论**：菜单生效时机、遮蔽默认值等须以 T0 实测结论为唯一口径 |

---

## 4. 执行顺序与验收

```
T0 → T1 → T2 → T3 → T4
                  ├── T5 → T6 → T7 → T8 → T9
                  └── T10
                                    T16 → T17 → T18
```

| 阶段验收 | 标准 |
|---|---|
| P0 完成 | 5 项验证均有明确结论，V1/V2/V8/V9 风险降级或关闭，结论回写技术方案 |
| P1 完成 | 插件可加载、可切换语言、api 可单测；包根入口与包根资源均被 ST 实际加载 |
| P2 完成 | 文件操作、打开方式、剪贴板、编码、搜索全部可用 |
| P3 完成 | 非活动标签右键定位正确 |
| P4 完成 | 菜单与原生无重复；遮蔽默认开启且可安全关闭；README 含 A 类对照表 |

---

## 5. 复盘校验结论

### 5.1 第一轮复盘（需求遗漏 / 边界）

| 检查 | 结论 |
|---|---|
| 11 项自研功能是否都有对应任务 | T5(新建/副本/移动)、T6(三种打开)、T7(剪贴板+路径)、T8(批量编码)、T9(搜索)、T10(标签 3 项) 全覆盖 |
| 7 项 A 类功能是否被误实现 | T5 明确不实现重命名；T6 明确不实现打开目录/终端/查找；T8 明确仅批量 |
| 标签 3 项是否各自有边界 | 技术方案 7.2 的 19-23 与 T10 通过标准一一对应 |
| 是否有无效验证项 | 已删除菜单覆盖、Tab Context 是否存在、GB18030 是否存在三项（已被方案实测确认） |
| 遮蔽是否会造成不可逆缺失 | 默认开启（D 类替换要求），但设置可关闭；仅遮蔽 3 项，`rename_path` 已移出清单，并加了「shadow 异常不影响原生」的验收 |
| 编码转换是否可撤销 | 已确认不可撤销，因此新增二次确认 + 多视图检测 + 转换后立即保存三道防线 |

### 5.2 第二轮复盘（架构 / 兼容性 / 迭代成本）

| 维度 | 结论 |
|---|---|
| 任务粒度 | 13 个任务，T5~T9 可并行，T10 独立，T16~T18 收尾 |
| 依赖关系 | 全部依赖 T4；无循环依赖 |
| 可测试性 | `api.py`（T4）、`platform.py` / `clipboard.py` / `encodings.py` / `encoding_detect.py` / `trash.py` 可脱离 ST 单测，覆盖核心逻辑 |
| 迭代成本 | 功能收敛后任务数较 v1.x 减少；无「后续再优化」类任务 |
| 风险覆盖 | 9 项风险（V1-V9）均有对应验证或验收手段 |
| 包结构正确性 | 已修正：包根入口 `MySideBar.py` 承担生命周期；全部资源文件位于包根 |
| 菜单生效口径 | T0-4 已判定为即时生效，门禁 13 校验回写文案不得出现「请重启」 |
| 遮蔽默认值 | 与 D 类判定一致改为 `true`，并在 T17 增加「设置可关闭」与「异常不吞原生命令」双重保障 |