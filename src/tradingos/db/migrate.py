from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config

# No se puede derivar de __file__: bajo una instalación no editable (como en la
# imagen Docker) el paquete vive en site-packages, desconectado del checkout del
# repo (mismo problema que TRADINGOS_DATA_DIR en api/main.py). Se resuelve contra el
# directorio de trabajo (la raíz del repo, tanto localmente como en el WORKDIR del
# contenedor), con override explícito disponible para otros layouts.
ALEMBIC_INI = Path(os.environ.get("TRADINGOS_ALEMBIC_INI", "alembic.ini")).resolve()


def run_migrations() -> None:
    """Aplica todas las migraciones pendientes (alembic upgrade head). Reemplaza a
    Base.metadata.create_all(): a diferencia de create_all, sí altera tablas ya
    existentes cuando el modelo cambió."""
    config = Config(str(ALEMBIC_INI))
    command.upgrade(config, "head")
