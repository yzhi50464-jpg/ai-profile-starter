"""生成可上传至网页 AI 的 Markdown 档案。"""

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path


def read_section(path: Path) -> str:
    if path.resolve(strict=True) != path or not path.is_file():
        raise ValueError(f"请选择仓库中的普通 Markdown 文件：{path.name}")
    return path.read_text(encoding="utf-8-sig").strip()


def build_export(root: Path, project: str | None) -> tuple[Path, str]:
    root = root.resolve()
    sections = [read_section(root / name) for name in ("USER.md", "STYLE.md")]
    output = root / "exports" / "网页AI个人档案.md"
    if project is not None:
        name = project.removesuffix(".md")
        if (
            not name or name.startswith(".") or name.casefold().endswith(".local")
            or any(char in name for char in "/\\:")
        ):
            raise ValueError("请用 projects 目录中可共享的项目文件名，例如 reading-notes")
        note = read_section(root / "projects" / f"{name}.md")
        if note.startswith("---\n"):
            _, delimiter, body = note[4:].partition("\n---\n")
            if not delimiter:
                raise ValueError(f"{name}.md 的笔记元数据缺少结束行")
            note = body.strip()
        sections.append(note)
        output = root / "exports" / "projects" / f"{name}.md"

    if output.resolve() != output:
        raise ValueError("导出位置应在本仓库的 exports 目录中")
    body = "\n\n".join(sections)
    version = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    return output, f"{body}\n\n---\n档案内容版本 {version}\n"


def save_export(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = tempfile.NamedTemporaryFile(dir=path.parent, delete=False)
    temp_path = Path(temp.name)
    try:
        with temp:
            temp.write(text.encode("utf-8"))
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="额外包含一份项目卡，例如 reading-notes")
    parser.add_argument("--check", action="store_true", help="只检查对应副本是否为最新版")
    args = parser.parse_args()
    try:
        path, text = build_export(Path(__file__).resolve().parent, args.project)
        current = path.is_file() and path.read_bytes() == text.encode("utf-8")
        if args.check and not current:
            print(f"副本缺失或已过期：{path}", file=sys.stderr)
            return 1
        if not current:
            save_export(path, text)
        print(path)
        return 0
    except (OSError, ValueError) as error:
        parser.exit(2, f"导出失败：{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
