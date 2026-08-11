from sqlalchemy import Column, Integer, String, Text, BigInteger, DateTime, Index
from sqlalchemy import Boolean as SqlBool
from app.db_models.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Backs role-scoped hierarchy lookups ('role = X AND parent_id IN (...)').
        Index("idx_users_role_parent", "role", "parent_id"),
        # Backs the recursive descendant CTE that resolves scope purely by parent_id.
        Index("idx_users_parent_id", "parent_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(64), nullable=False)
    status = Column(String(32), default="active")
    force_email_change = Column(SqlBool, default=False)
    force_password_change = Column(SqlBool, default=False)
    phone = Column(String(64), unique=True)
    designation = Column(String(255))
    address = Column(String(255))
    pincode = Column(String(255))
    network_name = Column(String(255))
    parent_id = Column(Integer)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    last_login = Column(DateTime)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)
    created_by = Column(Integer)

    def to_dict(self):
        """Serialize for API output.

        ``password_hash`` is deliberately excluded so it can never leak into
        an API response or client-side storage. Authentication code that needs
        the hash reads ``self.password_hash`` directly from the ORM instance.
        """
        d = super().to_dict()
        d.pop("password_hash", None)
        return d


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    token_hash = Column(String(255), primary_key=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(128), unique=True, nullable=False)
    requested_by = Column(Integer, nullable=False)
    requested_by_name = Column(String(255), nullable=False)
    requested_by_role = Column(String(64), nullable=False)
    request_type = Column(String(64), nullable=False)
    new_email = Column(String(255))
    new_password = Column(String(255))
    device_id = Column(Text)
    requested_status = Column(String(64))
    reason = Column(String(500))
    status = Column(String(32), default="pending")
    reviewed_by = Column(Integer)
    reviewed_by_name = Column(String(255))
    review_note = Column(String(500))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class ReassignmentRequest(Base):
    __tablename__ = "reassignment_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(128), unique=True, nullable=False)
    deleted_user_id = Column(Integer, nullable=False)
    deleted_user_name = Column(String(255))
    deleted_user_role = Column(String(64), nullable=False)
    status = Column(String(32), default="pending")
    reassigned_to_id = Column(Integer)
    reassigned_to_name = Column(String(255))
    reassigned_to_role = Column(String(64))
    children_json = Column(Text)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


