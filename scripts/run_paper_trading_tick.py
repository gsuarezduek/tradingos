#!/usr/bin/env python3
from __future__ import annotations

from tradingos.db.migrate import run_migrations
from tradingos.db.session import SessionLocal
from tradingos.paper_trading.tick import run_all_active


def main() -> None:
    run_migrations()

    db = SessionLocal()
    try:
        processed = run_all_active(db)
    finally:
        db.close()

    print(f"paper trading: {processed} sesión(es) activa(s) procesada(s)")


if __name__ == "__main__":
    main()
