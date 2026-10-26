"""Run the Blender builder as a subprocess, streaming its log (PRD/06 §2)."""

import re
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

BUILDER = Path(__file__).resolve().parents[1] / "builder" / "build.py"
TIMEOUT_EXIT = 124
_PROGRESS = re.compile(r"^@@PROGRESS (\d{1,3}) ?(.*)$")


def parse_progress(line: str) -> tuple[int, str] | None:
    m = _PROGRESS.match(line.strip())
    return (int(m[1]), m[2]) if m else None


def run_blender(build_input: Path, out_dir: Path, blender_bin: str, timeout_s: int = 300,
                on_line: Callable[[str], None] | None = None,
                on_start: Callable[[subprocess.Popen], None] | None = None) -> int:
    """Stream stdout+stderr line by line to `on_line` and out_dir/blender.log; return the exit code (124 = timeout)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [blender_bin, "-b", "--factory-startup", "--python-exit-code", "1", "-P", str(BUILDER), "--",
           str(build_input), str(out_dir)]
    with open(out_dir / "blender.log", "w") as log:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except OSError as e:
            log.write(f"cannot start blender: {e}\n")
            return 127
        if on_start:  # lets a caller cancel the build (terminate the process)
            on_start(proc)
        timer = threading.Timer(timeout_s, proc.kill)
        timer.start()
        try:
            for line in proc.stdout:
                log.write(line)
                if on_line:
                    on_line(line.rstrip("\n"))
            rc = proc.wait()
        finally:
            timed_out = not timer.is_alive()
            timer.cancel()
    return TIMEOUT_EXIT if timed_out and rc != 0 else rc
