import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.database import Base

BACKEND = Path(__file__).resolve().parents[1]


def test_alembic_upgrade_matches_models(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'm.db'}"
    env = {"DATABASE_URL": db_url, "DATA_DIR": str(tmp_path), "PATH": ""}
    for cmd in (["upgrade", "head"], ["downgrade", "base"], ["upgrade", "head"]):
        subprocess.run([sys.executable, "-m", "alembic", *cmd], cwd=BACKEND, env=env, check=True, capture_output=True)

    insp = inspect(create_engine(db_url))
    for table in Base.metadata.sorted_tables:
        migrated = {c["name"] for c in insp.get_columns(table.name)}
        assert migrated == set(table.columns.keys()), table.name
