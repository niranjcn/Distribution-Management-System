#!/usr/bin/env python3
"""
Seed script to populate users with the structure:
- 2 Managers
- 1 Staff
- 3 Subdistributors (each with 2 clusters and 1 operator per cluster)
"""

import asyncio
import sys
from datetime import datetime, timezone
from app.config import settings
from app.database import get_db
from app.utils.security import get_password_hash

# Users to seed
USERS_TO_CREATE = [
    # Managers
    {
        "email": "manager1@dms.com",
        "name": "Manager One",
        "role": "manager",
        "phone": "+8801711111111",
        "department": "Management",
        "location": "Head Office",
        "parent_id": None,
    },
    {
        "email": "manager2@dms.com",
        "name": "Manager Two",
        "role": "manager",
        "phone": "+8801722222222",
        "department": "Management",
        "location": "Head Office",
        "parent_id": None,
    },
    # Staff
    {
        "email": "staff1@dms.com",
        "name": "Staff One",
        "role": "pdic_staff",
        "phone": "+8801733333333",
        "department": "Operations",
        "location": "Head Office",
        "parent_id": None,
    },
    # Subdistributors (3)
    {
        "email": "subdist1@dms.com",
        "name": "Subdistributor One",
        "role": "sub_distributor",
        "phone": "+8801744444444",
        "department": "Distribution",
        "location": "Area 1",
        "parent_id": None,
    },
    {
        "email": "subdist2@dms.com",
        "name": "Subdistributor Two",
        "role": "sub_distributor",
        "phone": "+8801755555555",
        "department": "Distribution",
        "location": "Area 2",
        "parent_id": None,
    },
    {
        "email": "subdist3@dms.com",
        "name": "Subdistributor Three",
        "role": "sub_distributor",
        "phone": "+8801766666666",
        "department": "Distribution",
        "location": "Area 3",
        "parent_id": None,
    },
    # Clusters for Subdist 1
    {
        "email": "cluster11@dms.com",
        "name": "Cluster 1-1",
        "role": "cluster",
        "phone": "+8801777777711",
        "department": "Cluster",
        "location": "Cluster 1-1",
        "parent_id": "subdist1@dms.com",
    },
    {
        "email": "cluster12@dms.com",
        "name": "Cluster 1-2",
        "role": "cluster",
        "phone": "+8801777777712",
        "department": "Cluster",
        "location": "Cluster 1-2",
        "parent_id": "subdist1@dms.com",
    },
    # Clusters for Subdist 2
    {
        "email": "cluster21@dms.com",
        "name": "Cluster 2-1",
        "role": "cluster",
        "phone": "+8801777777721",
        "department": "Cluster",
        "location": "Cluster 2-1",
        "parent_id": "subdist2@dms.com",
    },
    {
        "email": "cluster22@dms.com",
        "name": "Cluster 2-2",
        "role": "cluster",
        "phone": "+8801777777722",
        "department": "Cluster",
        "location": "Cluster 2-2",
        "parent_id": "subdist2@dms.com",
    },
    # Clusters for Subdist 3
    {
        "email": "cluster31@dms.com",
        "name": "Cluster 3-1",
        "role": "cluster",
        "phone": "+8801777777731",
        "department": "Cluster",
        "location": "Cluster 3-1",
        "parent_id": "subdist3@dms.com",
    },
    {
        "email": "cluster32@dms.com",
        "name": "Cluster 3-2",
        "role": "cluster",
        "phone": "+8801777777732",
        "department": "Cluster",
        "location": "Cluster 3-2",
        "parent_id": "subdist3@dms.com",
    },
    # Operators for Subdist 1 clusters
    {
        "email": "operator11@dms.com",
        "name": "Operator 1-1",
        "role": "operator",
        "phone": "+8801788888811",
        "department": "Operations",
        "location": "Operator 1-1",
        "parent_id": "cluster11@dms.com",
    },
    {
        "email": "operator12@dms.com",
        "name": "Operator 1-2",
        "role": "operator",
        "phone": "+8801788888812",
        "department": "Operations",
        "location": "Operator 1-2",
        "parent_id": "cluster12@dms.com",
    },
    # Operators for Subdist 2 clusters
    {
        "email": "operator21@dms.com",
        "name": "Operator 2-1",
        "role": "operator",
        "phone": "+8801788888821",
        "department": "Operations",
        "location": "Operator 2-1",
        "parent_id": "cluster21@dms.com",
    },
    {
        "email": "operator22@dms.com",
        "name": "Operator 2-2",
        "role": "operator",
        "phone": "+8801788888822",
        "department": "Operations",
        "location": "Operator 2-2",
        "parent_id": "cluster22@dms.com",
    },
    # Operators for Subdist 3 clusters
    {
        "email": "operator31@dms.com",
        "name": "Operator 3-1",
        "role": "operator",
        "phone": "+8801788888831",
        "department": "Operations",
        "location": "Operator 3-1",
        "parent_id": "cluster31@dms.com",
    },
    {
        "email": "operator32@dms.com",
        "name": "Operator 3-2",
        "role": "operator",
        "phone": "+8801788888832",
        "department": "Operations",
        "location": "Operator 3-2",
        "parent_id": "cluster32@dms.com",
    },
]

PASSWORD = "TempPass@1234"


async def seed_users():
    """Seed all users with parent-child hierarchy."""
    async with get_db() as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        created_count = 0
        skipped_count = 0

        # First pass: Create users without parent_id dependencies
        # Then resolve parent_ids to user IDs for hierarchy
        email_to_id = {}

        print("Starting user seeding...")

        for user_data in USERS_TO_CREATE:
            email = user_data["email"]

            # Check if user already exists
            cursor = await db.execute(
                "SELECT id FROM users WHERE email = ?",
                (email,),
            )
            existing = await cursor.fetchone()

            if existing:
                print(f"  ⊘ Skipped {email} (already exists)")
                email_to_id[email] = existing["id"]
                skipped_count += 1
                continue

            # Get parent user ID if parent_id is specified
            parent_user_id = None
            if user_data["parent_id"]:
                parent_email = user_data["parent_id"]
                if parent_email in email_to_id:
                    parent_user_id = email_to_id[parent_email]
                else:
                    # Try to fetch from DB
                    cursor = await db.execute(
                        "SELECT id FROM users WHERE email = ?",
                        (parent_email,),
                    )
                    parent = await cursor.fetchone()
                    if parent:
                        parent_user_id = parent["id"]
                        email_to_id[parent_email] = parent["id"]

            # Insert the user
            cursor = await db.execute(
                """INSERT INTO users 
                (email, password_hash, name, role, phone, department, location, 
                 parent_id, status, permissions, theme, compact_mode, 
                 email_notifications, push_notifications, is_verified, 
                 force_password_change, force_email_change, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    email,
                    get_password_hash(PASSWORD),
                    user_data["name"],
                    user_data["role"],
                    user_data["phone"],
                    user_data["department"],
                    user_data["location"],
                    parent_user_id,
                    "active",
                    "{}",
                    "light",
                    False,
                    True,
                    True,
                    True,
                    False,
                    False,
                    now,
                    now,
                ),
            )

            if cursor.rowcount > 0:
                # Get the created user ID
                cursor = await db.execute(
                    "SELECT id FROM users WHERE email = ?",
                    (email,),
                )
                new_user = await cursor.fetchone()
                email_to_id[email] = new_user["id"]
                print(f"  ✓ Created {email} ({user_data['role']})")
                created_count += 1
            else:
                print(f"  ✗ Failed to create {email}")

        await db.commit()

        print(f"\nSeeding complete!")
        print(f"  Created: {created_count}")
        print(f"  Skipped: {skipped_count}")
        print(f"  Total:   {created_count + skipped_count}")
        print(f"\nAll users have password: {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed_users())
