from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
from app.config import settings

class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None


database = Database()


async def connect_to_mongodb():
    """Connect to MongoDB Atlas"""
    try:
        database.client = AsyncIOMotorClient(settings.MONGODB_URL)
        database.db = database.client[settings.DATABASE_NAME]
        # Verify connection
        await database.client.admin.command('ping')
        print(f"✅ Connected to MongoDB: {settings.DATABASE_NAME}")
        
        # Create indexes
        await create_indexes()
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        raise e


async def close_mongodb_connection():
    """Close MongoDB connection"""
    if database.client:
        database.client.close()
        print("MongoDB connection closed")


async def create_indexes():
    """Create database indexes for performance"""
    db = database.db
    
    # Users indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("role")
    
    # Devices indexes
    await db.devices.create_index("device_id", unique=True)
    await db.devices.create_index("serial_number", unique=True)
    await db.devices.create_index("status")
    await db.devices.create_index("current_holder_id")
    
    # Distributions indexes
    await db.distributions.create_index("distribution_id", unique=True)
    await db.distributions.create_index("status")
    await db.distributions.create_index("from_user_id")
    await db.distributions.create_index("to_user_id")
    
    # Defects indexes
    await db.defects.create_index("report_id", unique=True)
    await db.defects.create_index("device_id")
    await db.defects.create_index("status")
    await db.defects.create_index("reported_by")
    
    # Returns indexes
    await db.returns.create_index("return_id", unique=True)
    await db.returns.create_index("device_id")
    await db.returns.create_index("status")
    
    # Operators indexes
    await db.operators.create_index("operator_id", unique=True)
    await db.operators.create_index("assigned_to")
    
    # Notifications indexes
    await db.notifications.create_index("user_id")
    await db.notifications.create_index("is_read")
    await db.notifications.create_index([("created_at", -1)])
    
    # Device history indexes
    await db.device_history.create_index("device_id")
    await db.device_history.create_index([("timestamp", -1)])
    
    # Approvals indexes
    await db.approvals.create_index("entity_id")
    await db.approvals.create_index("status")
    
    print("✅ Database indexes created")


def get_database() -> AsyncIOMotorDatabase:
    """Get database instance"""
    return database.db
