"""M7c: the image must never carry secrets (.env and server-info.txt stay on the host)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dockerignore_keeps_secrets_out():
    patterns = {line.strip() for line in (ROOT / ".dockerignore").read_text().splitlines()}
    assert {".env", ".env.*", "server-info.txt"} <= patterns


def test_dockerfile_copies_named_paths_only():
    copies = [line.split() for line in (ROOT / "docker" / "Dockerfile").read_text().splitlines()
              if line.startswith("COPY") and "--from=" not in line]
    assert copies
    assert not any(src in {".", "./"} for c in copies for src in c[1:-1])


def test_runtime_code_imports_no_dev_only_package():
    """The image installs with --no-dev: a dev-group package imported by core/server/builder crashes startup."""
    import re
    import tomllib

    dev = tomllib.loads((ROOT / "pyproject.toml").read_text())["dependency-groups"]["dev"]
    names = {re.split(r"[<>=\[ ]", d)[0].replace("-", "_") for d in dev}
    pattern = re.compile(rf"^\s*(?:import|from) ({'|'.join(names)})\b", re.MULTILINE)
    hits = [str(p.relative_to(ROOT)) for d in ("core", "server", "builder") for p in (ROOT / d).rglob("*.py")
            if pattern.search(p.read_text())]
    assert hits == []
