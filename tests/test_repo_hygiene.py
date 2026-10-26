import subprocess


def test_server_info_is_ignored_and_untracked():
    assert subprocess.run(["git", "check-ignore", "-q", "server-info.txt"], check=False).returncode == 0
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.split()
    assert "server-info.txt" not in tracked and ".env" not in tracked
