from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DB_DIR = Path(__file__).resolve().parent.parent / "database"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "database.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import backend.models  # noqa: F401 ensures models are registered

    Base.metadata.create_all(bind=engine)
