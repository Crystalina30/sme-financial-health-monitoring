"""Build a clean, source-only ZIP of the project for sharing or submission.

    python scripts/make_source_zip.py            # writes release/FYP-source-<date>.zip
    python scripts/make_source_zip.py --list     # show what would be included

Excluded, whatever .gitignore says:
* secrets: .env and every .env.* except .env.example, *.pem, *.key
* version control and tooling: .git, .claude, .vscode, .idea
* dependencies and builds: node_modules, dist, build, __pycache__, *.pyc,
  .pytest_cache, .venv, coverage output
* personal and unrelated files: PDF, Word, PowerPoint and spreadsheet
  documents anywhere except docs/ (for example the reports in Sample/),
  desktop.ini, Thumbs.db
* this script's own output folder (release/)

Configuration is described by .env.example; whoever runs the project creates
their own .env from it.
"""

import argparse
import fnmatch
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "release"

EXCLUDED_DIRS = {
    ".git", ".claude", ".vscode", ".idea", "node_modules", "dist", "build", "__pycache__",
    ".pytest_cache", ".venv", "venv", "htmlcov", ".mypy_cache", ".ruff_cache", "release",
}
EXCLUDED_FILES = ["*.pyc", "*.pyo", "*.pem", "*.key", "desktop.ini", "Thumbs.db", ".DS_Store",
                  ".coverage", "*.sqlite3", "*.db"]
DOCUMENTS = ["*.pdf", "*.docx", "*.doc", "*.pptx", "*.xlsx", "*.zip"]


def is_secret(name: str) -> bool:
    return (name == ".env" or name.startswith(".env.")) and name != ".env.example"


def included_files() -> list[Path]:
    files = []
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in relative.parts) or not path.is_file():
            continue
        name = path.name
        if is_secret(name) or any(fnmatch.fnmatch(name, pattern) for pattern in EXCLUDED_FILES):
            continue
        if relative.parts[0] != "docs" and any(fnmatch.fnmatch(name, p) for p in DOCUMENTS):
            continue
        files.append(relative)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="only list the files")
    args = parser.parse_args()

    files = included_files()
    leaked = [f for f in files if is_secret(f.name)]
    if leaked:  # a safety net; is_secret already filters these
        print("Refusing to package secrets:", ", ".join(map(str, leaked)))
        return 1
    if args.list:
        print("\n".join(str(f) for f in files))
        print(f"\n{len(files)} files")
        return 0

    OUTPUT_DIR.mkdir(exist_ok=True)
    target = OUTPUT_DIR / f"FYP-source-{date.today().isoformat()}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            archive.write(ROOT / relative, Path("FYP") / relative)
    print(f"Wrote {target} ({len(files)} files, {target.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
