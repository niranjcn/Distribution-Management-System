import logging
from pathlib import Path


audit_logger = logging.getLogger("audit")


if not audit_logger.handlers:
    logs_dir = Path(__file__).resolve().parents[2] / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(logs_dir / "audit.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

    audit_logger.addHandler(handler)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
