from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Index
from app.db_models.base import Base


class Distribution(Base):
    __tablename__ = "distributions"
    __table_args__ = (
        # Backs the "sent by scope" (from_user_id) counts and the
        # received / pending_receipt counts (to_user_id + status).
        Index("idx_distributions_from_user_id", "from_user_id"),
        Index("idx_distributions_to_user_status", "to_user_id", "status"),
        # Backs the distribution status breakdown (GROUP BY status) and
        # status-filtered lists used by the management dashboard.
        Index("idx_distributions_status", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    distribution_id = Column(String(128), unique=True, nullable=False)
    device_count = Column(Integer, default=0)
    from_user_id = Column(Integer, nullable=False)
    from_user_name = Column(String(255))
    from_user_type = Column(String(32))
    to_user_id = Column(Integer, nullable=False)
    to_user_name = Column(String(255))
    to_user_type = Column(String(32))
    status = Column(String(32), default="pending")
    request_date = Column(DateTime, nullable=False)
    date_of_distribution = Column(Date)
    confirmed_at = Column(Date)
    delivery_date = Column(Date)
    notes = Column(String(500))
    manifest_file = Column(String(255))
    confirmed_by = Column(Integer)
    confirmed_by_name = Column(String(255))
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


# NOTE: The `distribution_devices` junction table was removed (migration 0017).
# Distribution <-> device membership is now derived from:
#   - `devices.current_distribution_id` (current / locked-in distribution)
#   - `device_history.distribution_id` (historical membership)
