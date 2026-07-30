from datetime import datetime, timezone
import os
import secrets
import string

from app.config import settings
from app.database_sqlalchemy import async_session_factory
from app.utils.security import get_password_hash
from sqlalchemy import text


def generate_secure_password(length: int = 16) -> str:
    """Generate a strong random password for initial admin provisioning."""
    if length < 12:
        length = 12

    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%^&*()"
    alphabet = lowercase + uppercase + digits + symbols

    # Ensure minimum complexity, then fill remaining chars randomly.
    password_chars = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]
    password_chars.extend(secrets.choice(alphabet) for _ in range(length - 4))
    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)


async def seed_initial_data():
    """Seed initial super admin account"""
    async with async_session_factory() as session:
        # Check if a super admin role or reserved admin email already exists.
        result = await session.execute(
            text("SELECT id, email, role FROM users WHERE role IN ('super_admin', 'super_admin') OR email = :email LIMIT 1"),
            {"email": "admin@dms.com"},
        )
        existing_admin = result.mappings().first()
        if existing_admin:
            # Normalize legacy elevated role values from previous deployments.
            if (
                existing_admin["email"] == "admin@dms.com"
                and existing_admin["role"] != "super_admin"
            ):
                now = datetime.now().replace(tzinfo=None)
                await session.execute(
                    text("""UPDATE users
                    SET role = :role, force_email_change = 1, force_password_change = 1, phone = :phone, updated_at = :now
                    WHERE id = :id"""),
                    {"role": "super_admin", "phone": "1111111111", "now": now, "id": existing_admin["id"]},
                )
                await session.commit()
                print("Existing seeded account normalized to super_admin")
            else:
                print("Super admin seed skipped (account already exists)")
            return
        
        print("Creating default super admin account...")
        admin_password = os.getenv("ADMIN_INITIAL_PASSWORD") or "Admin@123"
        
        now = datetime.now().replace(tzinfo=None)
        
        result = await session.execute(
            text("""INSERT INTO users (email, password_hash, name, role, status, force_email_change, force_password_change, phone,
                location, is_verified, created_at, updated_at)
            VALUES (:email, :password_hash, :name, :role, :status, :force_email_change, :force_password_change, :phone,
                :location, :is_verified, :created_at, :updated_at)"""),
            {
                "email": "admin@dms.com",
                "password_hash": get_password_hash(admin_password),
                "name": "System Super Admin",
                "role": "super_admin",
                "status": "active",
                "force_email_change": 1,
                "force_password_change": 1,
                "phone": "1111111111",
                "location": "Head Office",
                "is_verified": 1,
                "created_at": now,
                "updated_at": now
            }
        )

        if result.rowcount == 0:
            print("Super admin seed skipped (record already present)")
            await session.rollback()
            return

        await session.commit()
        
        print("Default super admin account created")
        if settings.ENVIRONMENT == "development":
            print("\nDefault Super Admin Credentials:")
            print("=" * 45)
            print(f"{'Role':<15} {'Email':<25} {'Password'}")
            print("-" * 45)
            print(f"{'Super Admin':<15} {'admin@dms.com':<25} {admin_password}")
            print("=" * 45)
            print("First login requires email and password update.")
        else:
            print("Initial super admin account created. Set ADMIN_INITIAL_PASSWORD to override default password.")
        print("Super admin account setup complete")
        print("Login as super admin to create users.")


async def reset_and_seed():
    """Drop all tables and re-seed default super admin account"""
    async with async_session_factory() as session:
        print("Clearing all database tables...")
        
        tables = [
            "inventory_stock_movements",
            "inventory_receipt_lines",
            "inventory_receipts",
            "inventory_po_lines",
            "inventory_purchase_orders",
            "external_inventory_items",
            "change_requests",
            "notifications",
            "approvals",
            "operators",
            "returns",
            "defects",
            "distributions",
            "device_history",
            "devices",
            "users",
        ]
        
        for table in tables:
            await session.execute(text(f"DELETE FROM {table}"))
            print(f"   Cleared: {table}")
        
        await session.commit()
        print("All tables cleared")
    
    # Re-seed super admin
    await seed_initial_data()
    
    return {
        "message": "Database reset and seeded successfully",
        "users_created": 1,
        "tables_cleared": len(tables)
    }

