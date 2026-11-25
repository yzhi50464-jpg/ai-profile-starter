"""在当前档案中索引、搜索笔记，或启动本地 Basic Memory MCP。"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECTS = {"profile-projects": "projects", "profile-memory": "memory"}


def basic_memory_command() -> list[str]:
    binary = "Scripts/bm.exe" if os.name == "nt" else "bin/bm"
    local = ROOT / ".tools" / "basic-memory" / binary
    if local.is_file():
        return [str(local)]
    installed = shutil.which("basic-memory")
    if installed:
        return [installed]
    launcher = ROOT / ".tools" / "launcher" / ("Scripts/uvx.exe" if os.name == "nt" else "bin/uvx")
    uvx = str(launcher) if launcher.is_file() else shutil.which("uvx")
    if uvx:
        return [
            uvx, "--python", "3.13", "--prerelease", "allow",
            "--from", "basic-memory==1.0.0", "basic-memory",
        ]
    raise FileNotFoundError("搜索需要 Basic Memory 1.0 或 uvx，安装方式见 docs/access.md")


def local_environment() -> dict[str, str]:
    projects = {}
    for name, folder in PROJECTS.items():
        path = ROOT / folder
        if not path.is_dir() or path.resolve() != path:
            raise ValueError(f"笔记目录应位于当前仓库内：{folder}")
        projects[name] = {"path": str(path), "mode": "local"}
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("BASIC_MEMORY_")}
    env.update(
        BASIC_MEMORY_CONFIG_DIR=str(ROOT / ".tools" / "basic-memory-data"),
        BASIC_MEMORY_PROJECTS=json.dumps(projects),
        BASIC_MEMORY_DEFAULT_PROJECT="profile-projects",
        BASIC_MEMORY_FORCE_LOCAL="true",
        PYTHONUTF8="1",
    )
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("index", help="重建项目卡与主题笔记的全文索引")
    search = commands.add_parser("search", help="跨两个目录搜索")
    search.add_argument("query")
    commands.add_parser("mcp", help="以标准输入输出启动本地 MCP")
    commands.add_parser("mcp-config", help="输出此电脑可用的 MCP 连接配置")
    args = parser.parse_args()

    if args.action == "mcp-config":
        server = {"command": sys.executable, "args": [str(Path(__file__).resolve()), "mcp"]}
        print(json.dumps({"mcpServers": {"personal-notes": server}}, indent=2, ensure_ascii=False))
        return 0

    try:
        command = basic_memory_command()
        env = local_environment()
        if args.action == "index":
            actions = [["reindex", "--search", "--project", name] for name in PROJECTS]
        elif args.action == "search":
            actions = [["tool", "search", "--local", "--mode", "text", "--all-projects", "--", args.query]]
        else:
            actions = [["mcp", "--transport", "stdio"]]
        for action in actions:
            result = subprocess.run(command + action, cwd=ROOT, env=env)
            if result.returncode:
                return result.returncode
        return 0
    except (OSError, ValueError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
