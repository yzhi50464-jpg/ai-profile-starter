"""本机对话回调。数据库只保存筛选出的条目和安装时核验的目标。"""

import base64
import hashlib
import json
import os
import re
import shlex
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

MARKER = "yzhi50464-jpg/ai-profile-starter/v1"
CLIENTS = {
    "codex": (".codex/hooks.json", "UserPromptSubmit", "Stop"),
    "claude": (".claude/settings.local.json", "UserPromptSubmit", "Stop"),
    "gemini": (".gemini/settings.json", "BeforeAgent", "AfterAgent"),
}
PRIVATE = re.compile(
    r"密码|密钥|秘钥|令牌|验证码|恢复码|不要记录|不要保存|别记|不要记|"
    r"password|credential|secret|token|api[ _-]?key|private key|recovery code|off the record|do not (?:save|record)|"
    r"-----BEGIN|https?://|@|[A-Za-z0-9_+/=-]{24,}|\b\d{1,3}(?:\.\d{1,3}){3}\b|[A-Z]:[\\/]", re.I)
TEMP = re.compile(r"今天|这次|这一次|暂时|临时|举例说|假设|例如|比如说|如果|today|this time|for now|for example|suppose", re.I)
PREF = re.compile(r"^(?:我(?:平时|一般|通常|一直|更)?(?:不喜欢|喜欢|习惯|偏好|倾向于)|我希望(?:你|以后|每次)|以后(?:都|请|默认|回答|写作)|默认(?:请|用)|I (?:usually |generally )?(?:prefer|like to)\b)", re.I)
STYLE = re.compile(r"写作|文案|文章|段落|标点|文风|语气|句子|短句|长句|writing|tone|paragraph", re.I)
DECISION = re.compile(r"^(?:我们决定|我决定|我们已经确定|这个项目决定|we (?:have )?decided\b)", re.I)
PROGRESS = re.compile(r"^(?:已(?:经)?(?:完成|通过|修复|验证|部署|实现)|测试(?:已)?通过|下一步|待确认|已决定|I (?:fixed|implemented|verified)\b|next step\b|tests passed\b)", re.I)


def blocked(message):
    return bool(PRIVATE.search(message) or len(message) > 64000)


def extract(message, role, project):
    if blocked(message):
        return []
    result = []
    fenced = False
    for line in message.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced or line.startswith(("    ", "\t")) or any(c in line for c in "<>`「」“”\"?？") or TEMP.search(line):
            continue
        for part in re.split(r"[。！？!?]|(?<=\.)\s+", line):
            part = part.strip().removeprefix("- ").strip("* ").strip()
            if not 4 <= len(part) <= 180 or TEMP.search(part):
                continue
            if role == "user" and PREF.match(part):
                dest = "STYLE.md" if STYLE.search(part) else "USER.md"
                label = "本人偏好"
            elif role == "user" and DECISION.match(part):
                dest = f"projects/{project}.md" if project else "memory/decisions.md"
                label = "本人决定"
            elif role == "assistant" and project and PROGRESS.match(part):
                dest, label = f"projects/{project}.md", "助手交接"
            else:
                continue
            result.append((dest, label, part))
    return result[:12]


def github(endpoint, payload=None, optional=False):
    args = ["gh", "api", "--hostname", "github.com", endpoint]
    if payload is not None:
        args += ["--method", "PUT", "--input", "-"]
    proc = subprocess.run(args, input=json.dumps(payload).encode() if payload else None,
                          capture_output=True, timeout=10)
    if proc.returncode:
        if optional and b"HTTP 404" in proc.stderr:
            return None
        raise RuntimeError("GitHub 请求失败，本机保留待同步条目")
    return json.loads(proc.stdout)


def verified(cfg):
    name = cfg["repository"]
    info = github("repos/" + name)
    if not (info.get("id") == cfg["id"] and info.get("private") is True
            and info.get("visibility") == "private" and info.get("full_name", "").casefold() == name.casefold()
            and github("user")["login"].casefold() == name.split("/")[0].casefold()):
        raise ValueError("档案的账号、仓库标识或私有状态不匹配")
    return info["default_branch"]


def get_note(name, branch, dest):
    endpoint = f"repos/{name}/contents/{quote(dest)}"
    doc = github(endpoint + "?ref=" + quote(branch, safe=""), optional=True)
    if doc is None:
        return endpoint, "", None
    if doc.get("type") != "file" or doc.get("encoding") != "base64":
        raise ValueError("档案条目不是可读的普通文件")
    return endpoint, base64.b64decode(doc["content"]).decode("utf-8"), doc["sha"]


def flush(db, cfg, branch):
    for (dest,) in db.execute("SELECT DISTINCT dest FROM pending").fetchall():
        rows = db.execute("SELECT id, date, label, body FROM pending WHERE dest=? ORDER BY rowid", (dest,)).fetchall()
        endpoint, content, sha = get_note(cfg["repository"], branch, dest)
        additions = [f"- {day} · {label} · {body} <!-- profile:{key} -->" for key, day, label, body in rows
                     if f"<!-- profile:{key} -->" not in content]
        if additions:
            content = content or f"# {Path(dest).stem}\n"
            if "\n## 自动整理\n" not in content:
                content = content.rstrip() + "\n\n## 自动整理\n"
            pos = content.index("\n## 自动整理\n") + len("\n## 自动整理\n")
            content = content[:pos] + "\n" + "\n".join(reversed(additions)) + "\n" + content[pos:]
            payload = {"branch": branch, "message": "自动整理协作档案", "content": base64.b64encode(content.encode()).decode()}
            if sha:
                payload["sha"] = sha
            github(endpoint, payload)
        with db:
            db.executemany("DELETE FROM pending WHERE id=?", [(row[0],) for row in rows])


def handle(state, binding, data):
    cfg = json.loads((state / "target.json").read_text(encoding="utf-8"))
    scope, project = cfg["bindings"][binding]
    cwd = Path(data["cwd"]).resolve()
    if not cwd.is_relative_to(Path(scope)):
        return {}
    for parent in (cwd, *cwd.parents):
        if parent == Path(scope):
            break
        if (parent / ".git").exists() or (parent / ".ai-profile-template").exists():
            return {}
    event = data["hook_event_name"]
    if event not in {"SessionStart", "UserPromptSubmit", "BeforeAgent", "Stop", "AfterAgent"}:
        return {}
    session = str(data.get("session_id") or "")
    if not session:
        return {}
    with sqlite3.connect(state / "queue.db", timeout=8) as db:
        db.executescript("""CREATE TABLE IF NOT EXISTS pending(id TEXT PRIMARY KEY,dest TEXT,date TEXT,label TEXT,body TEXT);
            CREATE TABLE IF NOT EXISTS muted(session TEXT PRIMARY KEY);""")
        dialog = binding + "/" + session
        prompt = data.get("prompt") or ""
        if event in ("UserPromptSubmit", "BeforeAgent"):
            db.execute("DELETE FROM muted WHERE session=?", (dialog,))
            if blocked(prompt):
                db.execute("INSERT INTO muted VALUES (?)", (dialog,))
            items = extract(prompt, "user", project)
        elif event in ("Stop", "AfterAgent"):
            if blocked(prompt) or db.execute("SELECT 1 FROM muted WHERE session=?", (dialog,)).fetchone():
                items = []
            else:
                items = extract(data.get("last_assistant_message") or data.get("prompt_response") or "", "assistant", project)
        else:
            items = []
        for dest, label, body in items:
            key = hashlib.sha256(json.dumps([dest, label, body]).encode()).hexdigest()[:24]
            db.execute("INSERT OR IGNORE INTO pending VALUES(?,?,?,?,?)",
                       (key, dest, datetime.now(timezone.utc).date().isoformat(), label, body))
        db.commit()
        if event in ("UserPromptSubmit", "BeforeAgent"):
            return {}
        pending = db.execute("SELECT 1 FROM pending LIMIT 1").fetchone()
        if not pending and event != "SessionStart":
            return {}
        branch = verified(cfg)
        if pending:
            flush(db, cfg, branch)
        if event == "SessionStart":
            docs = []
            for dest in ["USER.md", "STYLE.md"] + ([f"projects/{project}.md"] if project else []):
                _, content, _ = get_note(cfg["repository"], branch, dest)
                content = re.sub(r" <!-- profile:[0-9a-f]+ -->", "", content)
                if content and not PRIVATE.search(content):
                    docs.append(content[:2400])
            return {"hookSpecificOutput": {"hookEventName": event, "additionalContext":
                    "以下是档案中的个人偏好和项目交接，当前用户要求优先。\n" + "\n".join(docs)}}
    return {}


def atomic(path, raw):
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(raw)
    try:
        Path(tmp.name).replace(path)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def save(path, value):
    atomic(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def install(profile, info, scope, clients):
    profile, scope = profile.resolve(), scope.resolve(strict=True)
    if not scope.is_dir() or (profile / ".ai-profile-template").read_text().strip() != MARKER:
        raise ValueError("请核对档案和项目目录")
    if scope != profile and any((p / ".ai-profile-template").exists() for p in [scope, *scope.parents]):
        raise ValueError("其他模板或个人档案目录不能作为业务项目接入")
    gitdir = Path(subprocess.check_output(["git", "-C", str(profile), "rev-parse", "--absolute-git-dir"], encoding="utf-8").strip())
    state = gitdir / "personal-profile-hooks"
    script = state / "profile_hook.py"
    target = state / "target.json"
    cfg = json.loads(target.read_bytes()) if target.exists() else {"bindings": {}}
    if cfg.get("id", info["id"]) != info["id"]:
        raise ValueError("本机队列已绑定其他档案")
    cfg.update(repository=info["full_name"], id=info["id"])
    binding = hashlib.sha256(str(scope).encode()).hexdigest()[:16]
    slug = re.sub(r"[^\w-]", "-", scope.name).strip("-")[:60] or "project"
    if binding in cfg["bindings"]:
        slug = cfg["bindings"][binding][1]
    elif any(key.casefold() == slug.casefold() for _, key in cfg["bindings"].values()):
        slug += "-" + binding[:8]
    cfg["bindings"][binding] = [str(scope), slug if scope != profile else ""]
    atomic(script, Path(__file__).read_bytes())
    save(target, cfg)
    # Call a bare executable on Windows so the same command works in cmd, PowerShell and Git Bash.
    if os.name == "nt":
        if re.search(r'["$`%!\r\n]', script.as_posix()):
            raise ValueError("请选择路径中不含 shell 展开字符的档案目录")
        command = f'python -I -X utf8 "{script.as_posix()}" {binding}'
    else:
        command = shlex.join([sys.executable, "-I", "-X", "utf8", str(script), binding])
    local_git = subprocess.run(["git", "-C", str(scope), "rev-parse", "--absolute-git-dir"],
                               capture_output=True, encoding="utf-8")
    for client in clients:
        filename, before, after = CLIENTS[client]
        path = scope / filename
        if path.resolve() != path:
            raise ValueError("客户端配置路径包含重定向")
        config = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
        for event in ("SessionStart", before, after):
            groups = config.setdefault("hooks", {}).setdefault(event, [])
            existing = [h.get("command", "") for g in groups for h in g.get("hooks", [])]
            if command in existing:
                continue
            if any("personal-profile-hooks" in cmd for cmd in existing):
                raise ValueError("这个工作区已经绑定其他档案，请先核对其回调")
            groups.append({"hooks": [{"type": "command", "command": command}]})
        save(path, config)
        if local_git.returncode == 0 and subprocess.run(
            ["git", "-C", str(scope), "ls-files", "--error-unmatch", "--", filename], capture_output=True
        ).returncode != 0:
            exclude = Path(local_git.stdout.strip()) / "info" / "exclude"
            exclude.parent.mkdir(exist_ok=True)
            patterns = exclude.read_bytes() if exclude.exists() else b""
            prefix = subprocess.check_output(["git", "-C", str(scope), "rev-parse", "--show-prefix"], encoding="utf-8").strip()
            pattern = ("/" + prefix + filename).encode("utf-8")
            if pattern not in patterns.splitlines():
                atomic(exclude, patterns + b"\n" + pattern + b"\n")
    print("已配置自动读写：" + str(scope) + "（" + ", ".join(clients) + "）。重开客户端并按提示信任回调。")


if __name__ == "__main__":
    try:
        payload = json.loads(sys.stdin.buffer.read(2_000_000))
        response = handle(Path(__file__).resolve().parent, sys.argv[1], payload)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, sqlite3.Error, subprocess.TimeoutExpired):
        response = {"systemMessage": "个人档案回调未完成。已入队条目将在下次开始或完成一轮时重试。"}
    print(json.dumps(response))
