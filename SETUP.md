# 为发来链接的人搭建个人档案

**完成条件**是当前用户拥有一份可读写的 GitHub 私有仓库，并拿到自己的链接。本机接入还应能导出网页档案，完整模式应能使用本机笔记索引。公开模板只提供空白结构和程序。

## 能使用本机终端的 Agent

1. 在用户可写的工作区检查 Git、GitHub CLI 和 Python 3.10 或更高版本。缺工具时，可按宿主权限使用 [Git](https://git-scm.com/downloads)、[GitHub CLI](https://cli.github.com/) 和 [Python](https://www.python.org/downloads/) 的官方安装方式。使用 `gh api user --jq .login` 核对当前身份。未登录时发起 `gh auth login --hostname github.com --git-protocol https --web`，让用户在 GitHub 官方页面输入自己终端显示的一次性代码，授权后继续。
2. 把公开模板克隆到新目录，阅读 [搭建程序](tools/bootstrap.py)，用 Python 运行它。以下命令假定终端位于用来存放项目的工作区。若已有模板副本，直接使用它的脚本路径。已有同名无关目录时，为模板选择另一个本地目录名。

   ```sh
   git clone --depth 1 https://github.com/yzhi50464-jpg/ai-profile-starter.git ai-profile-starter
   python ai-profile-starter/tools/bootstrap.py --workspace .
   ```

   macOS 或 Linux 上可用 `python3`。程序使用 GitHub 原生模板接口，以当前登录用户为所有者创建私有仓库。默认名称为 `ai-personal-profile`。已是本模板生成的私有副本时接回使用，名称被其他仓库占用时选择带数字后缀的新名字。
3. 读取程序返回的**私有副本**中的 `AGENTS.md`。程序核对远端私有状态，在原样复制的模板首页写入这个人的私有接入链接并回读，随后克隆，生成并校验网页档案，建立 Basic Memory 索引。已有个人修改的首页按原样保留。首次使用搜索可能需要下载 Python 运行时和依赖。下载中断后重新运行同一命令即可接续。需要连接 MCP 的客户端时，运行 `python tools/notes.py mcp-config`，将该设备的命令和参数加入所选客户端。
4. 用户已给出要长期保存的偏好或项目资料时，在**私有副本**里填入，并按其 `AGENTS.md` 提交、推送和回读。用户暂未提供资料时，空白档案即可交付，可以问一句「你最希望新的 AI 记住哪条协作偏好？」。交付时给出私有仓库地址、实际完成的功能和可复制的下一位助手接入语。
5. 向当前助手接入时，可直接以新私有副本作为工作区。用户需要跨项目自动读档，且宿主已授权常驻指令写入时，将返回的**私有链接**和接入语追加到所选助手的常驻指令。交付时说明接入范围是本次对话、当前工作区，还是该助手的所有新对话。

程序也支持 `--plan` 只读预览，`--remote-only` 仅建远程私有档案，`--skip-search` 先完成 Git 和网页导出。用户需要完整本机接入时使用默认模式。

## 只有 GitHub 连接器的 Agent

1. 查询已授权用户身份及公开源 `yzhi50464-jpg/ai-profile-starter` 的模板状态。对候选目标使用其实际所有者、可见性及模板来源进行核对。已有本模板的私有副本可接回，同名其他仓库使用新名字。
2. 有模板建库能力时使用 GitHub 的 `POST /repos/yzhi50464-jpg/ai-profile-starter/generate`。请求中显式指定当前用户的 `owner`、目标 `name` 和布尔值 `private: true`。创建后回读仓库属性，验证所有者和 `private` 可见性，再读默认分支上的 `.ai-profile-template`、`AGENTS.md`、`USER.md` 和 `STYLE.md`。完整参数见 [GitHub 模板接口](https://docs.github.com/en/rest/repos/repos#create-a-repository-using-a-template)。
3. 如果私有 README 的文件 SHA 与公开模板 README 相同，把私有首页改为「我的 AI 个人档案」，写入当前私有仓库链接和下一位助手的接入语，回读确认。已经自行编辑过的首页继续使用。写入资料时使用私库的当前文件版本，发生并发更新就重新读取并合并。把私有仓库地址交给用户。此路径完成远程读写，本机搜索和导出可在有终端的设备上接入。

如果工具缺少建库权限，把[官方模板创建页面](https://github.com/yzhi50464-jpg/ai-profile-starter/generate)交给用户，让用户选择自己的账号和 **Private**。取得新地址后核实并继续可完成的步骤。登录、密码、令牌和验证码只通过平台官方授权流程处理。
