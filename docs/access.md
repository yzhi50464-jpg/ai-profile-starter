# 我的档案怎么用

## 新对话与交接

将**自己的私有仓库地址**发给能读取它的助手，并让它按根目录的 [AGENTS.md](../AGENTS.md) 开工。希望每段新对话都读档时，可将这句话和实际地址加入该助手的常驻指令或项目指令。结束时说「更新项目卡并同步」。只读连接器需要获得对该私库的写权限才能写回。

日常偏好放在 [USER.md](../USER.md)，表达习惯和经本人确认的样本放在 [STYLE.md](../STYLE.md)。从 [项目卡](../templates/project.md) 和 [主题笔记](../templates/memory.md) 模板填写后分别放进 `projects/` 和 `memory/`。候选项的处理方式见 [inbox/](../inbox/README.md)。

## 网页聊天

从私有副本根目录运行 `python export_profile.py`，将生成的 `exports/网页AI个人档案.md` 上传至相应平台。基础版收录 USER.md 和 STYLE.md 的全文。需要项目进度时，使用 `python export_profile.py --project 项目文件名`，程序会在 `exports/projects/` 生成包含该项目卡的交接版。已经生成的副本可用相同参数加 `--check` 核对版本，更新后在网页端替换。

## 本机搜索和 MCP

```sh
python tools/notes.py index
python tools/notes.py search "要查的主题"
python tools/notes.py mcp-config
```

Basic Memory 的本机索引只配置 `projects/` 和 `memory/`。空白档案索引到零份笔记是正常结果。程序按当前副本路径建立索引，配置和数据库位于 Git 已忽略的 `.tools/`。拉取新资料后运行 `index` 可刷新全文搜索。

支持 MCP 的客户端可使用 `mcp-config` 输出的 `personal-notes` 服务。把它合并进现有设置，或在表单里填写命令和参数。换设备时重新生成路径。使用 `--skip-search` 搭建的副本，可以在原工作区再次运行完整的搭建命令补上检索。

## 维护规则

Codex 读取 [AGENTS.md](../AGENTS.md)，Claude Code、Gemini CLI 和 Cursor 的仓库入口都指向它。只在调整 Cursor 自身的生效方式时，编辑 [.rulesync/rules/profile.md](../.rulesync/rules/profile.md) 并运行 `npx --yes rulesync@43.14.0 generate --targets cursor --features rules`。
