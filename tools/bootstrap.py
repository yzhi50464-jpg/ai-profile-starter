"""在当前 GitHub 用户的账号下创建或接回一个私有 AI 个人档案。"""

import argparse
import base64
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

if __package__:
    from . import profile_hook
else:
    import profile_hook


TEMPLATE = "yzhi50464-jpg/ai-profile-starter"
MARKER = TEMPLATE + "/v1"
SOURCE = Path(__file__).resolve().parents[1]
GH_HELPER = "credential.https://github.com.helper=!gh auth git-credential"
GIT_AUTH = ["git", "-c", "credential.helper=", "-c", GH_HELPER]


class GitHubError(RuntimeError):
    pass


def api(endpoint, *args, missing_ok=False):
    result = subprocess.run(
        ["gh", "api", "--hostname", "github.com", endpoint, *args],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    if result.returncode:
        match = re.search(r"HTTP (\d{3})", result.stderr)
        status = match.group(1) if match else ""
        if missing_ok and status == "404":
            return None
        if endpoint == "user":
            raise GitHubError("无法读取 GitHub 登录账号。请检查网络或完成 gh auth login --web。")
        raise GitHubError(f"GitHub 请求失败（{status or '连接或授权错误'}）：{endpoint}")
    return json.loads(result.stdout)


def require_private(info, full_name):
    if not info or info.get("full_name", "").casefold() != full_name.casefold():
        raise ValueError(f"无法核对仓库归属：{full_name}")
    if info.get("visibility") != "private" or info.get("private") is not True:
        raise ValueError(f"目标仓库的可见性必须是 private：{full_name}")
    if (info.get("permissions") or {}).get("push") is False:
        raise ValueError(f"当前身份需要这个私有仓库的内容写入权限：{full_name}")


def has_marker(full_name, branch):
    path = f"repos/{full_name}/contents/.ai-profile-template?ref={quote(branch, safe='')}"
    record = api(path, missing_ok=True)
    return bool(record and record.get("type") == "file" and
                base64.b64decode(record.get("content", "")).strip() == MARKER.encode())


def is_template_copy(full_name, info):
    parent_name = (info.get("template_repository") or {}).get("full_name")
    if parent_name:
        return parent_name.casefold() == TEMPLATE.casefold()
    return has_marker(full_name, info["default_branch"])


def numbered_names(base):
    yield base
    for number in itertools.count(2):
        yield f"{base}-{number}"


def select_repository(login, base):
    for name in numbered_names(base):
        full_name = f"{login}/{name}"
        info = api(f"repos/{full_name}", missing_ok=True)
        if info is None:
            return full_name, None
        if (info.get("visibility") == "private" and info.get("private") is True
                and is_template_copy(full_name, info)):
            require_private(info, full_name)
            return full_name, info


def generate_repository(full_name):
    owner, name = full_name.split("/")
    try:
        api(f"repos/{TEMPLATE}/generate", "--method", "POST", "-f", "owner=" + owner,
            "-f", "name=" + name, "-F", "private=true")
    except GitHubError:
        # A second installer or a lost response can leave a successfully created copy.
        existing = api(f"repos/{full_name}", missing_ok=True)
        if existing is None:
            raise
        require_private(existing, full_name)
        if not is_template_copy(full_name, existing):
            raise ValueError("创建期间仓库名已被占用。请重新运行以重新选择名称。")


def ready_repository(full_name):
    for attempt in range(12):
        info = api(f"repos/{full_name}", missing_ok=True)
        if info:
            require_private(info, full_name)
            if has_marker(full_name, info["default_branch"]):
                root_files = api(f"repos/{full_name}/contents?ref={quote(info['default_branch'], safe='')}")
                required = {"AGENTS.md", "USER.md", "STYLE.md", "projects", "memory", "ops", "tools", "export_profile.py"}
                missing = required.difference(item["name"] for item in root_files)
                if missing:
                    raise ValueError("私有副本缺少运行文件，请核对已有改动：" + ", ".join(sorted(missing)))
                return info
        if attempt < 11:
            time.sleep(2)
    raise RuntimeError("GitHub 中的模板文件还未就绪。稍后使用同一命令接续搭建。")


def prepare_private_home(info):
    """只替换未经编辑的模板首页，使用 GitHub 的文件 SHA 检测并发修改。"""
    name = info["full_name"]
    endpoint = f"repos/{name}/contents/README.md"
    branch = info["default_branch"]
    read_path = f"{endpoint}?ref={quote(branch, safe='')}"
    current = api(read_path, missing_ok=True)
    if current is None or current["sha"] != api(f"repos/{TEMPLATE}/contents/README.md")["sha"]:
        return
    home = f"""# 我的 AI 个人档案

把下面这句话发给下一位有读写权限的助手。

> 请读取我的私有档案 https://github.com/{name} 中的 AGENTS.md。开始时按任务读档，结束时更新并同步本次进展。

我的[协作偏好](USER.md)和[表达风格](STYLE.md)可以随时编辑。换助手接手工作时读[项目卡](projects/)，查旧决定时读[长期笔记](memory/)。[候选记忆](inbox/README.md)留给我确认，[账号目录](ops/ACCOUNTS.md)记录选定的服务别名。

给网页 AI 导出资料、配置本机搜索和 MCP 的步骤见[接入指南](docs/access.md)。
"""
    encoded = base64.b64encode(home.encode("utf-8")).decode("ascii")
    require_private(api(f"repos/{name}"), name)
    try:
        api(endpoint, "--method", "PUT", "-f", "message=建立个人档案首页", "-f", f"branch={branch}",
            "-f", f"sha={current['sha']}", "-f", f"content={encoded}")
    except GitHubError:
        latest = api(read_path)
        if latest["sha"] == current["sha"]:
            raise
        print("私有首页已由另一项操作更新，保留其版本。")
        return
    if base64.b64decode(api(read_path)["content"]) != home.encode("utf-8"):
        raise ValueError("私有首页回读与写入内容不同，请核对并发修改。")
    print("已写入并回读个人首页。", flush=True)


def git_read(path, *args):
    result = subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True,
        encoding="utf-8", errors="replace",
    )
    return result.stdout.strip() if result.returncode == 0 else None


def same_checkout(path, full_name):
    if path.resolve() != path or not path.is_dir():
        return False
    top = git_read(path, "rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != path:
        return False
    forms = {f"https://github.com/{full_name}", f"git@github.com:{full_name}",
             f"ssh://git@github.com/{full_name}"}
    forms = {url.casefold() for url in forms}
    for args in (("--all",), ("--push", "--all")):
        url = git_read(path, "remote", "get-url", *args, "origin")
        if not url or url.casefold().removesuffix(".git") not in forms:
            return False
    return True


def checkout(workspace, info):
    full_name = info["full_name"]
    branch = info["default_branch"]
    workspace.mkdir(parents=True, exist_ok=True)
    for name in numbered_names(full_name.split("/")[1]):
        path = workspace / name
        if not os.path.lexists(path):
            subprocess.run(GIT_AUTH + ["clone", "--config", "credential.https://github.com.helper=",
                           "--config", GH_HELPER, "--branch", branch,
                           f"https://github.com/{full_name}.git", str(path)], check=True)
            return path, True
        if same_checkout(path, full_name):
            if git_read(path, "status", "--porcelain") == "" and git_read(
                path, "branch", "--show-current"
            ) == branch:
                subprocess.run(GIT_AUTH + ["-C", str(path), "pull", "--ff-only",
                                           "origin", branch], check=True)
                return path, True
            print("已接回本机副本。本地有改动或位于其他分支，本次仅核对远程档案。")
            return path, False


def prepare_local(path, user, with_search):
    marker = path / ".ai-profile-template"
    if marker.read_text(encoding="utf-8").strip() != MARKER:
        raise ValueError("本地模板标识不一致，请核对副本。")
    for field, value in (("user.name", user["login"]),
                         ("user.email", f"{user['id']}+{user['login']}@users.noreply.github.com")):
        if not git_read(path, "config", "--get", field):
            subprocess.run(["git", "-C", str(path), "config", "--local", field, value], check=True)

    subprocess.run([sys.executable, "export_profile.py"], cwd=path, check=True)
    subprocess.run([sys.executable, "export_profile.py", "--check"], cwd=path, check=True)
    if not with_search:
        return

    bin_dir = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    local_bm = path / ".tools" / "basic-memory" / bin_dir / ("bm" + suffix)
    launcher = path / ".tools" / "launcher"
    uvx = launcher / bin_dir / ("uvx" + suffix)
    if not (local_bm.is_file() or uvx.is_file() or shutil.which("basic-memory") or shutil.which("uvx")):
        subprocess.run([sys.executable, "-m", "venv", str(launcher)], check=True)
        python = launcher / bin_dir / ("python" + suffix)
        subprocess.run([str(python), "-m", "pip", "install", "uv==0.13.10"], check=True)
    subprocess.run([sys.executable, "tools/notes.py", "index"], cwd=path, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="ai-personal-profile", help="私有仓库的首选名称")
    parser.add_argument("--workspace", type=Path, help="存放私有副本的工作目录")
    parser.add_argument("--plan", action="store_true", help="只读检查并显示拟使用的仓库")
    parser.add_argument("--remote-only", action="store_true", help="只在 GitHub 建立或接回私有档案")
    parser.add_argument("--skip-search", action="store_true", help="本次仅接入 Git 和网页导出")
    parser.add_argument("--client", action="append", choices=profile_hook.CLIENTS, help="为指定客户端安装对话回调，可重复")
    parser.add_argument("--project-dir", type=Path, help="额外接入当前使用的业务项目目录")
    parser.add_argument("--skip-automation", action="store_true", help="仅搭建档案和资料工具")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}", args.name):
        parser.error("仓库名请使用字母、数字、点、下划线或短横线")
    location = Path.cwd().resolve()
    if location == SOURCE or SOURCE in location.parents:
        location = SOURCE.parent
    workspace = (args.workspace or location).expanduser().resolve()
    if not args.remote_only and (workspace == SOURCE or SOURCE in workspace.parents):
        parser.error("请指定公开模板目录以外的工作区")
    try:
        if not shutil.which("gh") or (not (args.remote_only or args.plan) and not shutil.which("git")):
            raise RuntimeError("请按 SETUP.md 准备 GitHub CLI 和 Git。")
        user = api("user")
        template = api(f"repos/{TEMPLATE}")
        if (template.get("full_name", "").casefold() != TEMPLATE.casefold()
                or template.get("visibility") != "public" or template.get("is_template") is not True):
            raise ValueError("不能核对公开模板状态，请检查模板地址。")
        full_name, existing = select_repository(user["login"], args.name)
        verb = "接回" if existing else "创建"
        url = f"https://github.com/{full_name}"
        if args.plan:
            print(f"只读预览：将{verb}私有档案 {url}")
            return 0
        print(f"正在{verb}私有档案：{url}", flush=True)
        if existing is None:
            generate_repository(full_name)
        info = ready_repository(full_name)
        print(f"已核验私有仓库：{url}", flush=True)
        prepare_private_home(info)
        if not args.remote_only:
            path, can_prepare = checkout(workspace, info)
            print(f"私有副本：{path}", flush=True)
            if can_prepare:
                if not args.skip_automation:
                    clients = args.client or [c for c in profile_hook.CLIENTS if shutil.which(c)]
                    if clients:
                        profile_hook.install(path, info, path, clients)
                        if args.project_dir and args.project_dir.resolve() != path:
                            profile_hook.install(path, info, args.project_dir, clients)
                    else:
                        print("未识别本机客户端。可用 --client 指定 codex、claude 或 gemini。")
                prepare_local(path, user, not args.skip_search)
                print("网页档案已校验。" if args.skip_search else "网页档案已校验，本机全文索引已建立。")
        print(f"交给下一位助手：请读取我的私有档案 {url} 中的 AGENTS.md，开始时按任务读档，结束时更新并同步本次进展。")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"搭建未完成：{error}\n可用同一命令接续搭建。\n")


if __name__ == "__main__":
    raise SystemExit(main())
