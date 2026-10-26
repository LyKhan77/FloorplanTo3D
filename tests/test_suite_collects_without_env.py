import os
import subprocess
import sys


def test_suite_collects_without_env_file():
    # A newcomer running plain `uv run pytest` must not lose the whole suite to a dlopen error.
    env = {k: v for k, v in os.environ.items() if k != "DYLD_FALLBACK_LIBRARY_PATH"}
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
        env=env, capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stdout[-1500:]
