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


def test_upgrade_preserves_existing_campaign_drafts(tmp_path):
    import sqlite3

    database = tmp_path / "existing.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{database}"}
    cwd = Path(__file__).parents[1]
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "df26d956b488"],
        env=env,
        cwd=cwd,
        check=True,
        capture_output=True,
    )
    with sqlite3.connect(database) as db:
        db.execute(
            "INSERT INTO organizations (id,name) VALUES (?,?)", ("org", "Existing workspace")
        )
        db.execute(
            "INSERT INTO projects (id,organization_id,data,created_at) VALUES (?,?,?,?)",
            ("project", "org", '{"goal_customers":10}', "2026-11-18"),
        )
        db.execute(
            "INSERT INTO drafts (id,project_id,channel,content,status,generation) VALUES (?,?,?,?,?,?)",
            ("draft", "project", "linkedin", "Previously approved content", "approved", "{}"),
        )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        cwd=cwd,
        check=True,
        capture_output=True,
    )
    with sqlite3.connect(database) as db:
        row = db.execute(
            "SELECT content,status,revision_number FROM drafts WHERE id='draft'"
        ).fetchone()
        assert row == ("Previously approved content", "approved", 1)
        import json

        data = json.loads(db.execute("SELECT data FROM projects WHERE id='project'").fetchone()[0])
        assert data["goal_customers"] == 50
