

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

开发期间建议直接在 `Packages/MySideBar` 放软链接指向 `src/`：

```bash
ln -s "/path/to/MySideBar/src" "<Packages>/MySideBar"
```

### 分支模型

本仓库采用两条分支：`dev` 是唯一开发分支，`main` 是由 CI 单向生成的发布分支。

| 分支 | 内容 | 谁写入 |
|---|---|---|
| `dev` | 开发分支。插件源码在 `src/`，根目录另有 `docs/`、`_res/` 与完整的开发者 README | 开发者手工提交 |
| `main` | 发布分支。`src/` 内容扁平化到仓库根，外加 CI 生成的 `packages.json` | 仅 CI，每次发版 `--force` 全量覆盖 |

### 目录职责

| 路径 | 职责 | 是否进发布包 |
|---|---|---|
| `src/` | 插件包根，所有随包分发的文件都在这里 | 是（内容直接成为 zip 顶层，并成为 `main` 的根目录） |
| `src/README.md` / `src/README_CN.md` | 面向用户的精简文档，随包发布 | 是 |
| `README.md` / `README_CN.md` | 面向开发者的完整文档（仅存在于 `dev`） | 否 |
| `_res/` | 第三方国际化资源参考（ChineseLocalization 原文与译文），不入包 | 否 |
| `docs/` | 开发文档 | 否 |
| `.github/workflows/release.yml` | 发布流水线 | 否 |
| `dist/` | 打包产物，已被 `.gitignore` 排除 | 否 |

`dev` 根目录不再维护 `packages.json`。仓库根若仍存在该文件，属于过期的历史残留，不要修改也不要提交新的版本，真正生效的清单由 CI 生成到 `main`。

### 发布

Package Control 不支持从仓库子目录读取 `packages.json`，也不支持直接以 `src/` 作为包根做 tag 发布：tag 归档会以整个仓库为根，解压后落到 `Packages/MySideBar/src/`，插件无法加载。因此本项目采用**自建 zip + 显式版本记录 + CI 生成发布分支**的方式发布。

发布链路为：`dev` 打 tag → `release` job 打包并发布 Release → `sync-main` job 把 `src/` 镜像到 `main` 并生成 `packages.json`。

#### 1. 同步版本号

两处必须与即将打的 tag 完全一致（tag 去掉 `v` 前缀）：

| 文件 | 内容 |
|---|---|
| `src/meta.py` | `__version__ = '1.0.1'` |
| `src/messages/install.txt` | 首行 `MySideBar 1.0.1 - Installation` |

`src/.python-version` 必须保持 `3.8`，`src/.no-sublime-package` 必须存在。

#### 2. 提交并推送 dev

```bash
git add -A && git commit -m "chore: 版本号 1.0.1"
git push origin dev
```

#### 3. 打 tag 并推送

tag 必须带 `v` 前缀且为三段纯数字（`v1.0.1`），`v1.0`、`v1.0.1-beta` 都会被流水线拒绝：

```bash
git tag v1.0.1
git push origin v1.0.1
```

#### 4. 流水线动作

`.github/workflows/release.yml` 由 `v*` 触发，随后在脚本内用正则 `v[0-9]+\.[0-9]+\.[0-9]+$` 做精确校验（GitHub Actions 的 `tags` 只支持 glob 通配，无法表达"恰好三段数字"）。

`release` job：

- 校验 `src/meta.py` 的 `__version__`、`src/messages/install.txt` 首行与 tag 一致
- 校验 `src/.python-version`、`src/.no-sublime-package`、两份用户版 README 存在，且互相链接、各自带有"发布副本"提示
- 在 `src/` 内执行 `zip`（排除 `.DS_Store`、`__pycache__`），并断言 `MySideBar.py` 位于 zip 顶层，防止产生嵌套层级
- 生成 `SHA256SUMS.txt`，把 zip 与校验文件上传到该 tag 的 Release

`sync-main` job：

- 检出 `dev`，在独立目录 `main/` 中 `git init` 全新建仓（不用 orphan 分支，避免旧文件残留）
- `cp -R ../dev/src/. .` 把 `src/` 内容扁平化到根目录
- 清理 `__pycache__`、`*.pyc`、`.DS_Store`，并断言没有 `src/` 嵌套泄漏
- 用 `SHA256SUMS.txt` 中的 hash 生成 `packages.json`
- 断言 `MySideBar.py`、`meta.py`、`messages.json`、`README.md`、`README_CN.md`、`.no-sublime-package`、`.python-version`、`packages.json` 全部存在
- `git commit` 后 `git push --force origin HEAD:main`

推送使用内嵌 token 的 remote URL，因为 `git init` 新建的仓库不在 `actions/checkout` 的凭据管辖范围内：

```bash
git remote add origin "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git"
```

#### 5. 校验 main

`packages.json` 的关键字段：

| 字段 | 必须是 |
|---|---|
| `details` | `https://github.com/tekintian/MySideBar/blob/main/packages.json`（不能是仓库主页） |
| `version` | 纯数字 `1.0.1`，**不带** `v` |
| `url` | `https://github.com/tekintian/MySideBar/releases/download/1.0.1/MySideBar-1.0.1.zip` |
| `sha256` | 取自 `SHA256SUMS.txt`，与用户下载的 zip 一致 |

注意 `raw.githubusercontent.com` 有 CDN 缓存，清单更新后用户侧可能延迟几分钟才拿到新版本。

#### 补发某个版本

无需重打 tag，手动触发即可：

```bash
gh workflow run release --ref dev -f tag=v1.0.1
```

#### 硬性约束

- **`main` 禁止手工提交**。`sync-main` 用 `--force` 推送且每次全量重建，任何手工改动都会在下一次发版时被完整覆盖。
- **tag 一律 `v` 前缀**。旧的无 `v` 前缀 tag 已删除并重打为 `v1.0.0`，后续不再混用格式。
- **`version` 字段不带 `v`**。ST 的版本比较对 `v` 前缀不友好：tag 是 `v1.0.1`，而包内版本号、zip 文件名、`packages.json` 的 `version` 都是 `1.0.1`。
- **两份 README 要同步**。用户可见行为变更时，`src/README.md`、`src/README_CN.md` 必须一起改；否则 `release` job 会因检查失败而中止。

包内必须同时包含 `.no-sublime-package`（否则会被压成 `.sublime-package`，插件把菜单写入 `Packages/User/` 的覆盖层机制就会失效）与 `.python-version`（内容必须是 `3.8`，写入更高的版本会让 ST4 的插件宿主直接启动失败）。

Package Control 的 `sublime_text` 声明为 `>=4000`，因为插件入口直接导入了 ST4 才有的 `ApplicationCommand` 与 `ViewEventListener`，在 ST3 下会导入失败。若将来仓库地址变更，`packages.json` 的 `details`、流水线里生成 `url`/`details` 用的 `GITHUB_REPOSITORY` 与 `meta.py` 的 `__url__` 会自动同步，但仓库迁移后仍需确认 Package Control 侧登记的清单地址已更新。

首次安装提示由 `src/messages.json` 驱动：键 `install` 对应新用户，键为版本号（如 `1.1.0`）时对应从低版本升级的用户。新增升级提示时，在 `src/messages/` 下新建 txt 并在 `src/messages.json` 里按版本号登记，Package Control 只会展示高于用户原有版本的提示。

---