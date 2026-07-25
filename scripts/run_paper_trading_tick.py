#!/usr/bin/env python3
from __future__ import annotations

from tradingos.db.models import Base
from tradingos.db.session import SessionLocal, engine
from tradingos.paper_trading.tick import run_all_active


def main() -> None:
    Base.metadata.create_all(bind=engine)  # idempotente, mismo criterio que api/main.py

    db = SessionLocal()
    try:
        processed = run_all_active(db)
    finally:
        db.close()

    print(f"paper trading: {processed} sesión(es) activa(s) procesada(s)")


if __name__ == "__main__":
    main()
