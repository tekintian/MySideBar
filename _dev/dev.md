
## 文档

开发文档位于 `_dev/docs/`（不随发布版本分发）：

| 文档 | 内容 |
|---|---|
| `_dev/docs/MySideBar-04-实现说明-v1.0.md` | 按代码实际实现编写的架构、命令、配置、数据目录说明 |
| `_dev/docs/MySideBar-01-技术方案-v2.0.md` | 设计取舍与 ST4 原生能力实测结论 |
| `_dev/docs/MySideBar-02-任务计划-v2.0.md` | 分阶段实施计划 |
| `_dev/docs/MySideBar-03-多语言编码兼容方案-v1.2.md` | 编码探测与转换的专项设计 |

---


## 开发

插件由仓库根目录的 `MySideBar.py` 与 `mysidebar/` 包构成，直接部署到 `Packages/MySideBar/` 即可运行。新增命令的方式：

1. 在 `mysidebar/cmds/` 下新建模块
2. 定义 `MySidebarXxxCommand(sublime_plugin.WindowCommand)` 等命令类
3. 在对应 `*.sublime-menu` 中引用命令名

包根入口会递归发现所有命令类并自动注册，无需修改 `MySideBar.py`。命令名规则由 ST 自动转换：类名去掉 `Command` 后缀后转为下划线命名。

校验脚本位于 `_dev/tests/`（`_` 前缀文件不会被 ST 加载），在项目根目录执行：

```bash
python3 _dev/tests/_check.py
python3 _dev/tests/_menu_roundtrip.py
python3 _dev/tests/_i18n_keys.py
python3 _dev/tests/_entry_export.py
```



### 发布

版本号以 `meta.py` 的 `__version__` 为唯一来源。Package Control 只按**语义化版本 tag** 分发（分支发布已被官方废弃），因此每次发版必须同时更新版本号并打同名 tag，tag 名不带 `v` 前缀：

```bash
# 1. 更新 meta.py 的 __version__
# 2. 提交后打 tag 并推送
git tag 1.0.0
git push origin main --tags
```

Package Control 的渠道提交配置见 `_dev/package-control-submission.json`（该文件仅作留档，不会被插件分发给用户）。其中 `sublime_text` 声明为 `>=4000`，因为插件入口直接导入了 ST4 才有的 `ApplicationCommand` 与 `ViewEventListener`，在 ST3 下会导入失败。若将来仓库地址变更，`details` 字段与 `meta.py` 的 `__url__` 必须同步修改。

首次安装提示由根目录的 `messages.json` 驱动：键 `install` 对应新用户，键为版本号（如 `1.1.0`）时对应从低版本升级的用户。新增升级提示时，在 `messages/` 下新建 txt 并在 `messages.json` 里按版本号登记，Package Control 只会展示高于用户原有版本的提示。

---
