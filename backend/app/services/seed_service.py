from datetime import datetime
from app.database import get_database
from app.utils.security import get_password_hash


async def seed_initial_data():
    """Seed initial admin account"""
    db = get_database()
    
    # Check if admin already exists
    existing_admin = await db.users.find_one({"role": "admin"})
    if existing_admin:
        print("📦 Admin account already exists, skipping seed")
        return
    
    print("🌱 Creating admin account...")
    
    now = datetime.utcnow()
    
    # Create admin user
    admin_user = {
        "email": "admin@dms.com",
        "password_hash": get_password_hash("admin123"),
        "name": "System Administrator",
        "role": "admin",
        "phone": "+1234567890",
        "department": "IT",
        "location": "Head Office",
        "status": "active",
        "is_verified": True,
        "created_at": now,
        "updated_at": now,
        "last_login": None
    }
    
    result = await db.users.insert_one(admin_user)
    print(f"✅ Admin account created: admin@dms.com / admin123")
    
    # Get admin for reference
    admin = await db.users.find_one({"email": "admin@dms.com"})
    
    print("🎉 Admin account setup complete!")
