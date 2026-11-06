

# MySideBar 开发与发布指南

用于本机开发调试的仓库地址（仅在开发机临时添加，不对外公布）：

```
https://raw.githubusercontent.com/tekintian/MySideBar/main/packages.json
```

开发过程中常用的 GitHub API：

```
# 分支列表
https://api.github.com/repos/tekintian/MySideBar/branches

# 仓库某个目录的内容
https://api.github.com/repos/tekintian/MySideBar/contents/src?ref=main
```


## 文档

开发文档位于 `docs/`（不随发布版本分发）：

| 文档 | 内容 |
|---|---|
| `04-implementation-notes.md` | 按代码实际实现编写的架构、命令、配置、数据目录说明 |
| `01-technical-design.md` | 设计取舍与 ST4 原生能力实测结论 |
| `02-task-plan.md` | 分阶段实施计划 |
| `03-encoding-strategy.md` | 编码探测与转换的专项设计 |

---


## 开发

插件源码位于 src目录，直接将 `src/` 目录下的所有文件复制到 `Packages/MySideBar/` 即可运行。新增命令的方式：

1. 在 `src/mysidebar/cmds/` 下新建模块
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

脚本内部会自动切换到 `src/` 作为工作目录，因此只支持在仓库根目录执行，不能单独拷贝到别处运行。开发期间建议直接在 `Packages/MySideBar` 放软链接指向 `src/`：

```bash
ln -s "/path/to/MySideBar/src" "<Packages>/MySideBar"
```

### 目录职责

| 路径 | 职责 | 是否进发布包 |
|---|---|---|
| `src/` | 插件包根，所有随包分发的文件都在这里 | 是（内容直接成为 zip 顶层） |
| `packages.json` | Package Control 仓库清单，必须位于**仓库根** | 否 |
| `tools/` | `build.py` 本地预检打包脚本 | 否 |
| `tests/` | 校验脚本 | 否 |
| `docs/` | 开发文档 | 否 |
| `dist/` | 打包产物，已被 `.gitignore` 排除 | 否 |

### 发布

Package Control 不支持从仓库子目录读取 `packages.json`，也不支持直接以 `src/` 作为包根做 tag 发布：tag 归档会以整个仓库为根，解压后落到 `Packages/MySideBar/src/`，插件无法加载。因此本项目采用**自建 zip + 显式版本记录**的方式发布。

发布流程：

1. 修改 `src/meta.py` 的 `__version__`，同时把 `src/messages/install.txt` 首行的版本号改成同一版本
2. （可选）本地预检：`python3 tools/build.py`，确认 zip 结构无误
3. 提交代码并打 tag 推送，tag 名与版本号一致、不带 `v` 前缀：

```bash
git tag 1.0.0
git push origin HEAD --tags
```

推送 tag 后，GitHub Actions 流水线 `.github/workflows/release.yml` 自动完成全部发布动作：

- 校验 `src/meta.py` 的 `__version__`、`src/messages/install.txt` 首行、`src/.python-version`（必须是 `3.8`）与本 tag 一致
- 在 `src/` 目录内执行 `zip`，产物顶层直接是插件根（不含 `src/` 前缀）
- 计算 sha256 并重写仓库根的 `packages.json` 后自动提交回 `main`
- 把 `MySideBar-<version>.zip` 与 `SHA256SUMS.txt` 上传到该 tag 的 Release

`packages.json` 的 `url` 恒为 `https://github.com/tekintian/MySideBar/releases/download/<version>/MySideBar-<version>.zip`。注意 `raw.githubusercontent.com` 有 CDN 缓存，清单更新后用户侧可能延迟几分钟才拿到新版本。

包内必须同时包含 `.no-sublime-package`（否则会被压成 `.sublime-package`，插件把菜单写入 `Packages/User/` 的覆盖层机制就会失效）与 `.python-version`（内容必须是 `3.8`，写入更高的版本会让 ST4 的插件宿主直接启动失败）。

Package Control 的 `sublime_text` 声明为 `>=4000`，因为插件入口直接导入了 ST4 才有的 `ApplicationCommand` 与 `ViewEventListener`，在 ST3 下会导入失败。若将来仓库地址变更，`packages.json` 的 `details`、流水线里生成 `url`/`details` 用的 `GITHUB_REPOSITORY` 与 `meta.py` 的 `__url__` 会自动同步，但仓库迁移后仍需确认 Package Control 侧登记的清单地址已更新。

首次安装提示由 `src/messages.json` 驱动：键 `install` 对应新用户，键为版本号（如 `1.1.0`）时对应从低版本升级的用户。新增升级提示时，在 `src/messages/` 下新建 txt 并在 `src/messages.json` 里按版本号登记，Package Control 只会展示高于用户原有版本的提示。

---