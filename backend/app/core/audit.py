import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


audit_logger = logging.getLogger("audit")


if not audit_logger.handlers:
    logs_dir = Path(__file__).resolve().parents[2] / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        logs_dir / "audit.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

    audit_logger.addHandler(handler)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
