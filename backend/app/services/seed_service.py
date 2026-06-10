from datetime import datetime, timezone
import os
import secrets
import string

from app.config import settings
from app.database import get_db
from app.utils.security import get_password_hash


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
    async with get_db() as db:
        # Check if a super admin role or reserved admin email already exists.
        cursor = await db.execute(
            "SELECT id, email, role FROM users WHERE role IN ('super_admin', 'super_admin') OR email = ? LIMIT 1",
            ("admin@dms.com",),
        )
        existing_admin = await cursor.fetchone()
        if existing_admin:
            # Normalize legacy elevated role values from previous deployments.
            if (
                existing_admin.get("email") == "admin@dms.com"
                and existing_admin.get("role") != "super_admin"
            ):
                now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
                await db.execute(
                    """UPDATE users
                    SET role = ?, force_email_change = 1, force_password_change = 1, updated_at = ?
                    WHERE id = ?""",
                    ("super_admin", now, existing_admin.get("id")),
                )
                await db.commit()
                print("Existing seeded account normalized to super_admin")
            else:
                print("Super admin seed skipped (account already exists)")
            return
        
        print("Creating default super admin account...")
        admin_password = os.getenv("ADMIN_INITIAL_PASSWORD") or "Admin@123"
        
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        
        insert_cursor = await db.execute(
            """INSERT OR IGNORE INTO users (email, password_hash, name, role, force_email_change, force_password_change, phone, department, location,
                status, permissions, theme, compact_mode, email_notifications,
                push_notifications, is_verified, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "admin@dms.com",
                get_password_hash(admin_password),
                "System Super Admin",
                "super_admin",
                1,
                1,
                "",
                "IT",
                "Head Office",
                "active",
                "{}",
                "light",
                0,
                1,
                1,
                1,
                now,
                now
            )
        )

        if insert_cursor.rowcount == 0:
            print("Super admin seed skipped (record already present)")
            await db.rollback()
            return

        await db.commit()
        
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
    async with get_db() as db:
        print("🗑️  Clearing all database tables...")
        
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
            await db.execute(f"DELETE FROM {table}")
            print(f"   Cleared: {table}")
        
        await db.commit()
        print("✅ All tables cleared")
    
    # Re-seed super admin
    await seed_initial_data()
    
    return {
        "message": "Database reset and seeded successfully",
        "users_created": 1,
        "tables_cleared": len(tables)
    }

