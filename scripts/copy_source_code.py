"""Copies clean project source code into SkillSprint_Submission/4. Source Code/."""
import shutil
from pathlib import Path

SRC_DIR = Path(".")
DST_DIR = Path("SkillSprint_Submission/4. Source Code")
DST_DIR.mkdir(parents=True, exist_ok=True)

DIRECTORIES = [
    "src", "config", "prompt_templates", "schemas", "sample_documents",
    "tests", "migrations", "scripts", "docker"
]

FILES = [
    "README.md", "requirements.txt", "alembic.ini", "Dockerfile",
    "docker-compose.yml", "docker-compose.gpu.yml", "railway.toml",
    "api-console.html", ".env.example", "pytest.ini",
    "generate_sample_docs.py", "generate_extended_docs.py"
]

for d in DIRECTORIES:
    s = SRC_DIR / d
    t = DST_DIR / d
    if s.exists():
        if t.exists():
            shutil.rmtree(t)
        shutil.copytree(s, t, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".venv"))
        print(f"Copied directory: {d}")

for f in FILES:
    s = SRC_DIR / f
    t = DST_DIR / f
    if s.exists():
        shutil.copy2(s, t)
        print(f"Copied file: {f}")

# Also copy frontend (excluding node_modules and dist)
front_src = SRC_DIR / "frontend"
front_dst = DST_DIR / "frontend"
if front_src.exists():
    if front_dst.exists():
        shutil.rmtree(front_dst)
    shutil.copytree(front_src, front_dst, ignore=shutil.ignore_patterns("node_modules", "dist", ".oxlint-cache", ".vite"))
    print("Copied frontend codebase (clean)")

print("Source code successfully mirrored into 4. Source Code!")
