from datetime import datetime

from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models with dict serialization."""

    def to_dict(self):
        """Convert ORM instance to dict matching row_to_dict format.

        - Adds _id as string copy of id
        - Coerces TINYINT(1) bool columns to Python bools
        - Serializes datetime columns to ISO strings
        """
        d = {}
        for c in inspect(self).mapper.column_attrs:
            val = getattr(self, c.key)
            if isinstance(val, datetime):
                val = val.isoformat()
            d[c.key] = val

        if "id" in d and d["id"] is not None:
            d["_id"] = str(d["id"])
            d["id"] = str(d["id"])

        for key in [
            "is_verified", "is_read", "force_email_change", "force_password_change",
        ]:
            if key in d and d[key] is not None:
                d[key] = bool(d[key])

        return d
