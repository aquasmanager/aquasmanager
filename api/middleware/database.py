"""
Connexion à la base (SQLite ou MySQL selon la configuration) : moteur,
sessions et dépendance FastAPI get_db.
"""

from settings import settings
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

db_conf = settings.database

if db_conf.type == "mysql":
    # Pilote PyMySQL (licence MIT) ; URL.create échappe les caractères spéciaux du mot de passe
    DATABASE_URL = URL.create(
        "mysql+pymysql",
        username=db_conf.user,
        password=db_conf.password,
        host=db_conf.host,
        port=db_conf.port,
        database=db_conf.name,
        query={"charset": "utf8mb4"},
    )
else:
    DATABASE_URL = f"sqlite:///{db_conf.sqlite_path}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if db_conf.type == "sqlite" else {})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Session de base de données d'une requête, fermée à la fin."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
