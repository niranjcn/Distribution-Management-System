from sqlalchemy.dialects.mysql import TINYINT, BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db_models.base import Base


class CacheVersion(Base):
    """Single-row table tracking the global data version for HTTP caching.

    `id` is always 1; `version` is bumped inside the same transaction as every
    application data change. Cacheable GET endpoints expose it as an ETag.
    """

    __tablename__ = "cache_version"

    id: Mapped[int] = mapped_column(TINYINT, primary_key=True)
    version: Mapped[int] = mapped_column(BIGINT, nullable=False, default=1)
