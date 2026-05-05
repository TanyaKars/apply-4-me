from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session

DATA_DIR = Path.home() / ".apply4me"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR}/apply4me.db"
engine = create_engine(DATABASE_URL, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session


def migrate_db():
    """Add any missing columns to existing tables (safe to run on every startup)."""
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(__import__("sqlalchemy").text("PRAGMA table_info(job)"))}
        for col, ddl in [
            ("match_score",  "ALTER TABLE job ADD COLUMN match_score INTEGER"),
            ("match_reason", "ALTER TABLE job ADD COLUMN match_reason TEXT"),
        ]:
            if col not in existing:
                conn.execute(__import__("sqlalchemy").text(ddl))
        conn.commit()
