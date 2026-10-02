import os
import subprocess
import sys


def test_main_module_import_is_safe():
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"

    result = subprocess.run(
        [sys.executable, "-c", "import main"],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )

    assert result.returncode == 0, result.stderr or result.stdout
