"""用临时 Git 远端演练建库、跨设备读写和重复接入。GitHub API 使用本机替身。"""

import base64
import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import bootstrap


def git(*args, cwd=None):
    return subprocess.check_output(
        ["git", "-c", "user.name=Template Test", "-c", "user.email=test@example.invalid",
         *map(str, args)], cwd=cwd, encoding="utf-8", stderr=subprocess.STDOUT,
    ).strip()


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.scratch = Path(temp.name).resolve()
        self.seed = self.scratch / "seed"
        self.bare = self.scratch / "private.git"
        self.primary = "reader/ai-personal-profile"
        self.target = self.primary + "-2"
        self.created = 0
        git("init", "-b", "main", self.seed)
        for name in (".ai-profile-template", ".gitignore", "AGENTS.md", "README.md", "USER.md", "STYLE.md",
                     "ops/ACCOUNTS.md", "projects/.gitkeep", "memory/.gitkeep",
                     "export_profile.py", "tools/notes.py"):
            path = self.seed / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bootstrap.SOURCE / name, path)
        git("add", ".", cwd=self.seed)
        git("commit", "-m", "Blank template", cwd=self.seed)

    def api(self, endpoint, *args, missing_ok=False):
        if endpoint == "user":
            return {"id": 1001, "login": "reader"}
        source = "repos/" + bootstrap.TEMPLATE
        if endpoint == source:
            return {"full_name": bootstrap.TEMPLATE, "visibility": "public", "is_template": True}
        if endpoint == source + "/contents/README.md":
            return {"sha": git("rev-parse", "main:README.md", cwd=self.seed)}
        if endpoint == source + "/generate":
            self.assertIn("POST", args)
            self.assertIn("owner=reader", args)
            self.assertIn("name=ai-personal-profile-2", args)
            self.assertIn("private=true", args)
            git("clone", "--bare", self.seed, self.bare)
            self.created += 1
            return {}
        if endpoint == "repos/" + self.primary:
            return {"full_name": self.primary, "private": True, "visibility": "private",
                    "default_branch": "main"}
        target = "repos/" + self.target
        if self.bare.exists():
            if endpoint == target:
                return {"full_name": self.target, "private": True, "visibility": "private",
                        "default_branch": "main", "template_repository": {"full_name": bootstrap.TEMPLATE}}
            if endpoint == target + "/contents/README.md?ref=main":
                sha = git("--git-dir", self.bare, "rev-parse", "main:README.md")
                raw = subprocess.check_output(["git", "--git-dir", str(self.bare), "cat-file", "blob", sha])
                return {"sha": sha, "content": base64.b64encode(raw).decode()}
            if endpoint == target + "/contents/README.md" and "PUT" in args:
                self.assertIn("sha=" + git("--git-dir", self.bare, "rev-parse", "main:README.md"), args)
                encoded = next(x.removeprefix("content=") for x in args if x.startswith("content="))
                edit = self.scratch / "api-edit"
                git("clone", self.bare, edit)
                (edit / "README.md").write_bytes(base64.b64decode(encoded))
                git("add", "README.md", cwd=edit)
                git("commit", "-m", "Private homepage", cwd=edit)
                git("push", "origin", "main", cwd=edit)
                return {}
            if endpoint == target + "/contents/.ai-profile-template?ref=main":
                marker = git("--git-dir", self.bare, "show", "main:.ai-profile-template")
                return {"type": "file", "content": base64.b64encode(marker.encode()).decode()}
            if endpoint == target + "/contents?ref=main":
                names = git("--git-dir", self.bare, "ls-tree", "--name-only", "main").splitlines()
                return [{"name": name} for name in names]
        if missing_ok:
            return None
        self.fail(f"Unexpected API call: {endpoint}")

    def run_setup(self, workspace, *args):
        real_which = shutil.which
        def executable(name):
            return "mock-gh" if name == "gh" else real_which(name)
        rewrite = f"url.{self.bare.as_uri()}.insteadOf=https://github.com/{self.target}.git"
        with (
            mock.patch.object(bootstrap, "api", side_effect=self.api),
            mock.patch.object(bootstrap, "GIT_AUTH", ["git", "-c", "protocol.file.allow=always", "-c", rewrite]),
            mock.patch.object(shutil, "which", side_effect=executable),
            mock.patch.object(sys, "argv", ["bootstrap.py", "--workspace", str(workspace), "--skip-search", *args]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(bootstrap.main(), 0)

    def test_create_write_resume_and_read_on_second_device(self):
        first = self.scratch / "device-one"
        self.run_setup(first, "--plan")
        self.assertFalse(self.bare.exists())
        self.assertFalse(first.exists())
        occupied = first / "ai-personal-profile-2"
        occupied.mkdir(parents=True)
        (occupied / "existing.txt").write_text("keep", encoding="utf-8")
        self.run_setup(first)
        local = first / "ai-personal-profile-2-2"
        self.assertEqual((occupied / "existing.txt").read_text(), "keep")
        self.assertIn("https://github.com/" + self.target, (local / "README.md").read_text(encoding="utf-8"))
        self.assertEqual(git("remote", "get-url", "origin", cwd=local), "https://github.com/" + self.target + ".git")
        (local / "USER.md").write_text("# Preferences\n\nTest preference.\n", encoding="utf-8")
        (local / "README.md").write_text("# My custom homepage\n", encoding="utf-8")
        self.run_setup(first)
        self.assertIn("Test preference.", (local / "USER.md").read_text())
        git("add", "USER.md", "README.md", cwd=local)
        git("commit", "-m", "Save fixture preference", cwd=local)
        git("push", self.bare, "main", cwd=local)
        self.run_setup(first)
        second = self.scratch / "device-two"
        self.run_setup(second)
        exported = second / "ai-personal-profile-2/exports/网页AI个人档案.md"
        self.assertIn("Test preference.", exported.read_text(encoding="utf-8"))
        self.assertEqual((exported.parents[1] / "README.md").read_text().strip(), "# My custom homepage")
        self.assertEqual(self.created, 1)

    def test_reject_public_or_wrong_owner_after_generate(self):
        for name, visibility in ((self.target, "public"), ("somebody/other", "private")):
            info = {"full_name": name, "visibility": visibility, "private": visibility == "private"}
            with self.subTest(info=info), mock.patch.object(bootstrap, "api", return_value=info):
                with self.assertRaises(ValueError):
                    bootstrap.ready_repository(self.target)

    def test_permission_failure_is_not_treated_as_available_name(self):
        denied = subprocess.CompletedProcess(["gh"], 1, "", "gh: Forbidden (HTTP 403)")
        with mock.patch.object(subprocess, "run", return_value=denied):
            with self.assertRaises(bootstrap.GitHubError):
                bootstrap.select_repository("reader", "test")

    def test_a_different_template_origin_is_never_reused(self):
        elsewhere = {"template_repository": {"full_name": "reader/some-other-template"}}
        with mock.patch.object(bootstrap, "has_marker", side_effect=AssertionError("unneeded lookup")):
            self.assertFalse(bootstrap.is_template_copy(self.primary, elsewhere))
