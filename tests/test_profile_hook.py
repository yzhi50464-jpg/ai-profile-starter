"""用临时 Git 私库和本地 GitHub Contents 接口替身验证原生回调。"""

import base64
import hashlib
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import profile_hook as hook


class AutomationTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name).resolve()
        self.repo = root / "private"
        self.project = root / "reading"
        self.project.mkdir()
        self.git("init", "-b", "main", self.repo)
        (self.repo / ".ai-profile-template").write_text(hook.MARKER)
        (self.repo / "USER.md").write_text("# 协作偏好\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "blank")
        self.info = dict(id=10, full_name="reader/profile", private=True, visibility="private", default_branch="main")
        hook.install(self.repo, self.info, self.project, hook.CLIENTS)
        self.state = self.repo / ".git/personal-profile-hooks"
        self.binding = next(iter(json.loads((self.state / "target.json").read_bytes())["bindings"]))
        self.addCleanup(patch.stopall)
        patch.object(hook, "github", side_effect=self.api).start()

    def git(self, *args):
        return subprocess.check_output(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                                        *map(str, args)], cwd=self.repo if self.repo.exists() else self.repo.parent,
                                       stderr=subprocess.STDOUT).strip()

    def api(self, endpoint, payload=None, optional=False):
        if endpoint == "repos/reader/profile":
            return self.info
        if endpoint == "user":
            return {"login": "reader"}
        prefix = "repos/reader/profile/contents/"
        self.assertTrue(endpoint.startswith(prefix))
        path = self.repo / endpoint[len(prefix):].split("?")[0]
        raw = path.read_bytes() if path.exists() else None
        sha = hashlib.sha256(raw).hexdigest() if raw is not None else None
        if payload is None:
            return dict(type="file", encoding="base64", sha=sha, content=base64.b64encode(raw)) if sha else None
        self.assertEqual(payload.get("sha"), sha)
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(base64.b64decode(payload["content"]))
        self.git("add", path)
        self.git("commit", "-m", payload["message"])

    def event(self, event, **fields):
        return hook.handle(self.state, self.binding, dict(cwd=str(self.project), session_id="dialog",
                                                         hook_event_name=event, **fields))

    def test_turn_sync_and_next_client(self):
        self.event("UserPromptSubmit", prompt="我习惯先看例子。写完再说。\n我喜欢文案用短句。\n我们决定使用纸质原型。")
        self.event("Stop", last_assistant_message="已完成首页草图。下一步是访谈。")
        head = self.git("rev-parse", "HEAD")
        self.event("BeforeAgent", prompt="我习惯先看例子。")
        self.event("AfterAgent", prompt_response="已完成首页草图。")
        self.assertEqual(head, self.git("rev-parse", "HEAD"))
        self.assertIn("先看例子", self.git("show", "HEAD:USER.md").decode())
        self.assertIn("文案用短句", self.git("show", "HEAD:STYLE.md").decode())
        card = self.git("show", "HEAD:projects/reading.md").decode()
        for phrase in ("本人决定", "纸质原型", "助手交接", "首页草图", "下一步"):
            self.assertIn(phrase, card)
        context = self.event("SessionStart")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("纸质原型", context)
        self.assertIn("先看例子", context)

    def test_recovery_and_scope(self):
        self.event("BeforeAgent", prompt="我习惯先看例子。")
        self.info["private"] = False
        with self.assertRaises(ValueError):
            self.event("AfterAgent", prompt_response="好。")
        self.assertNotIn("先看例子", (self.repo / "USER.md").read_text(encoding="utf-8"))
        self.info["private"] = True
        self.event("SessionStart")
        head = self.git("rev-parse", "HEAD")
        self.event("BeforeAgent", prompt="我喜欢短句，但这次要写长文。")
        self.event("AfterAgent", prompt_response="好。")
        self.event("BeforeAgent", prompt="不要记录。服务器密钥是 fixture-only。")
        self.event("AfterAgent", prompt_response="已验证 fixture-only。")
        self.assertEqual(head, self.git("rev-parse", "HEAD"))
        self.assertEqual(hook.handle(self.state, self.binding, {"cwd": str(self.repo)}), {})

    def test_repeat_install_keeps_other_hooks(self):
        path = self.project / ".codex/hooks.json"
        config = json.loads(path.read_bytes())
        config["hooks"]["Stop"].append({"hooks": [{"type": "command", "command": "fixture-command"}]})
        hook.save(path, config)
        hook.install(self.repo, self.info, self.project, ["codex"])
        self.assertEqual(json.loads(path.read_bytes()), config)

    def test_installed_command_reads_real_stdin(self):
        config = json.loads((self.project / ".codex/hooks.json").read_bytes())
        cmd = config["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        payload = dict(session_id="ordinary", cwd=str(self.project), hook_event_name="UserPromptSubmit",
                       prompt="我习惯先看例子。")
        proc = subprocess.run(cmd, shell=True, cwd=self.project, input=json.dumps(payload).encode(),
                              capture_output=True, check=True)
        self.assertEqual(json.loads(proc.stdout), {})
        with sqlite3.connect(self.state / "queue.db") as db:
            self.assertEqual(db.execute("SELECT dest,body FROM pending").fetchall(), [("USER.md", "我习惯先看例子")])
