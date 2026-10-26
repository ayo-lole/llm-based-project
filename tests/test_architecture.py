import subprocess
import sys
from pathlib import Path


def test_import_linter_contract():
    root = Path(__file__).resolve().parents[1]
    exe = Path(sys.executable).with_name("lint-imports.exe")
    if not exe.exists():
        exe = Path(sys.executable).with_name("lint-imports")
    proc = subprocess.run([str(exe)], cwd=root, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
