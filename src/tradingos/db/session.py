from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Local/dev por default: sqlite en un archivo del repo. En Railway, DATABASE_URL apunta
# al servicio de Postgres vía variable de referencia.
_RAW_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./tradingos.db")


def _normalize_database_url(url: str) -> str:
    # Railway (y Heroku antes) suelen exponer "postgres://"; SQLAlchemy 2.0 con el
    # driver psycopg3 necesita el dialecto explícito "postgresql+psycopg://".
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = _normalize_database_url(_RAW_DATABASE_URL)

if DATABASE_URL == "sqlite:///:memory:":
    # sqlite en memoria abre una DB nueva por conexión salvo que se fuerce un único
    # pool compartido: sin esto, cada request de los tests vería una DB vacía distinta.
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
elif DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
