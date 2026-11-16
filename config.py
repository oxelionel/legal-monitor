"""Configuração central do Legal Monitor.

Lê variáveis de ambiente (opcionalmente a partir de um arquivo ``.env`` na raiz
do projeto) sem depender de bibliotecas externas. Nenhuma credencial deve ser
escrita diretamente no código.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Carrega pares CHAVE=valor de um arquivo .env sem sobrescrever o ambiente."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

APP_NAME = "Legal Monitor"
APP_SLOGAN = "Inteligência jurídica. Monitoramento estratégico."
APP_VERSION = "1.0.0"

DATABASE_URL = os.environ.get(
    "LEGAL_MONITOR_DATABASE_URL",
    f"sqlite:///{(BASE_DIR / 'data' / 'legal_monitor.db').as_posix()}",
)
DEFAULT_USER = os.environ.get("LEGAL_MONITOR_USER", "Operador local")
AUTO_SEED_DEMO = os.environ.get("LEGAL_MONITOR_AUTO_SEED_DEMO", "true").lower() in {"1", "true", "yes", "sim"}
DEADLINE_ALERT_DAYS = int(os.environ.get("LEGAL_MONITOR_DEADLINE_ALERT_DAYS", "7"))
