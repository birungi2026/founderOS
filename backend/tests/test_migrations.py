import os
import subprocess
import sys
from pathlib import Path


def test_migrations_round_trip(tmp_path):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path}/migration.db"}
    cwd = Path(__file__).parents[1]
    for command in [
        ("upgrade", "head"),
        ("check",),
        ("downgrade", "base"),
        ("upgrade", "head"),
    ]:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *command],
            env=env,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
