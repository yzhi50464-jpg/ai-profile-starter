"""验证网页副本的收录范围、版本与原有命令入口。"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class WebExportTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "档案 copy"
        self.root.mkdir()
        self.script = self.root / "export_profile.py"
        shutil.copyfile(Path(__file__).resolve().parents[1] / self.script.name, self.script)
        for name, content in {
            "USER.md": "已确认的偏好",
            "STYLE.md": "写作样本",
            "projects/练习.md": "---\npermalink: internal-metadata\n---\n\n# 练习进度",
            "projects/other.md": "其他项目",
            "projects/test.local.md": "本地条目",
            "ops/ACCOUNTS.local.md": "本机索引标记",
            "inbox/candidate.md": "等待确认的提议",
        }.items():
            path = self.root / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(self.script), *args],
            cwd=self.root.parent, capture_output=True, encoding="utf-8",
        )

    def test_default_and_one_named_project(self):
        default = self.cli()
        self.assertEqual(default.returncode, 0, default.stderr)
        base = (self.root / "exports/网页AI个人档案.md").read_text(encoding="utf-8")
        project = self.cli("--project", "练习.md")
        self.assertEqual(project.returncode, 0, project.stderr)
        handoff = (self.root / "exports/projects/练习.md").read_text(encoding="utf-8")
        for text in (base, handoff):
            self.assertIn("已确认的偏好", text)
            self.assertIn("写作样本", text)
            for excluded in ("其他项目", "本机索引标记", "等待确认的提议", "本地条目", "internal-metadata"):
                self.assertNotIn(excluded, text)
        self.assertNotIn("练习进度", base)
        self.assertIn("练习进度", handoff)
        self.assertEqual(self.cli("--check").returncode, 0)
        self.assertEqual(self.cli("--project", "练习", "--check").returncode, 0)

    def test_check_is_read_only_and_detects_edits(self):
        self.assertEqual(self.cli("--check").returncode, 1)
        self.assertFalse((self.root / "exports").exists())
        self.assertEqual(self.cli().returncode, 0)
        path = self.root / "exports/网页AI个人档案.md"
        first = path.read_bytes()
        (self.root / "STYLE.md").write_text("新样本", encoding="utf-8")
        self.assertEqual(self.cli("--check").returncode, 1)
        self.assertEqual(path.read_bytes(), first)
        self.assertEqual(self.cli().returncode, 0)
        self.assertNotEqual(first.splitlines()[-1], path.read_bytes().splitlines()[-1])
        self.assertEqual(self.cli("--check").returncode, 0)

    def test_private_paths_cannot_be_selected_as_projects(self):
        for name in ("../ops/ACCOUNTS.local", r"..\inbox\candidate", "test.local.md", "missing"):
            with self.subTest(name=name):
                self.assertEqual(self.cli("--project", name).returncode, 2)
        self.assertFalse((self.root / "exports").exists())
