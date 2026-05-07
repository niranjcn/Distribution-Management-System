import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def clear_old_distributions():
    """Clear old distribution data from database"""
    client = AsyncIOMotorClient('mongodb+srv://danishali0610:lWCc0V8aVZ0okQd9@cluster0.kgvnb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
    db = client['distribution-management-system']
    
    # Delete old distributions that have the old schema (with from_user_id, to_user_id)
    result = await db.distributions.delete_many({
        'from_user_id': {'$exists': True}
    })
    print(f'Deleted {result.deleted_count} old distribution records')
    
    client.close()

if __name__ == '__main__':
    asyncio.run(clear_old_distributions())
