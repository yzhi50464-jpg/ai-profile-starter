# 公开项目与本仓库的设计

2026-11-25 核对项目作者发布的说明。下表记录各项目影响了本仓库的哪一项决定。Basic Memory 用于本机检索，Rulesync 用于生成 Cursor 规则，其余项目提供结构参考。

| 借鉴的做法 | 在本仓库的落点 | 项目原文 |
| --- | --- | --- |
| 用私有 Git 仓库同步，每个设备单独起草候选记忆 | 项目卡、候选目录和换设备流程。核对时两个公开入口均指向提交 `52d7837` | [Shared AI Memory](https://github.com/CodyQin/shared-ai-memory) · [Gitee 镜像](https://gitee.com/codyqin17/shared-ai-memory) |
| 按信息变化速度整理档案，由人决定哪些偏好长期有效 | 稳定偏好写进 USER.md，项目卡写核对日期 | [personal-context-spec](https://github.com/jiayuewangjavy/personal-context-spec) |
| 主档案可生成工具专用副本，也能检测副本过期 | 原文按职责维护，网页导出提供 `--check` | [you.md](https://github.com/brainsparker/you.md) |
| 区分可携带的 Markdown 与网页平台上传的资料 | 网页版明确列出收录范围，按任务选择项目 | [own-your-ai-memory](https://github.com/jrverdes/own-your-ai-memory) |
| 通过具体场景询问、核对生成的个人描述 | 候选条目记录场景、来源和待确认的推断 | [Meport](https://github.com/zmrlk/meport) |
| 按本地目录建立可重建的索引，通过 MCP 检索原文 | 搜索只配置项目卡和主题笔记两处资料 | [Basic Memory](https://github.com/basicmachines-co/basic-memory) |
| 从规则源生成客户端需要的格式 | Cursor 的生效方式在规则源里定义，读取流程统一指向 AGENTS.md | [Rulesync](https://github.com/dyoshikawa/rulesync) |
| 把用户级信息与会话级信息放在不同范围 | 单次对话的要求只在本次生效，长期偏好单独维护 | [Mem0](https://github.com/mem0ai/mem0) |
| 回答时结合稳定的用户资料和与任务相关的近期上下文 | 基础网页档案可按需加上一张项目卡 | [Supermemory](https://github.com/supermemoryai/supermemory) |
| 用一份普通 Markdown 在多种助手间传递个人资料 | 导出单个可独立阅读的文件 | [PortableAI](https://github.com/portable-ai/portable-ai) |
| 用内容校验值核对可携带副本 | 网页档案末尾显示由正文算出的版本 | [Portable Memory](https://github.com/MacPaw/portable-memory) |
| 根据任务读取已保存的上下文，单独提炼长期事实 | 接手项目直接读卡，值得长期保留的经验写回主题笔记 | [Memcrate](https://github.com/memcrate/memcrate) |
