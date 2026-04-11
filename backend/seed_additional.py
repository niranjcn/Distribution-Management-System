#!/usr/bin/env python3
"""
Comprehensive seeding script for:
1. Additional users (MD Director and Sub Distribution Managers)
2. Devices in all devices table
3. External inventory items
"""

import asyncio
from datetime import datetime, timezone
from app.config import settings
from app.database import get_db
from app.utils.security import get_password_hash
import uuid

PASSWORD = "TempPass@1234"

# Additional users to create
ADDITIONAL_USERS = [
    # Top-level MD Director
    {
        "email": "md_director@dms.com",
        "name": "MD Director",
        "role": "md_director",
        "phone": "+8801799999999",
        "department": "Executive",
        "location": "Head Office",
        "parent_id": None,
    },
    # Sub Distribution Managers (one for each subdistributor)
    {
        "email": "subdist_mgr1@dms.com",
        "name": "Sub Distribution Manager 1",
        "role": "sub_distribution_manager",
        "phone": "+8801791111111",
        "department": "Sub Distribution",
        "location": "Area 1",
        "parent_id": "subdist1@dms.com",
    },
    {
        "email": "subdist_mgr2@dms.com",
        "name": "Sub Distribution Manager 2",
        "role": "sub_distribution_manager",
        "phone": "+8801792222222",
        "department": "Sub Distribution",
        "location": "Area 2",
        "parent_id": "subdist2@dms.com",
    },
    {
        "email": "subdist_mgr3@dms.com",
        "name": "Sub Distribution Manager 3",
        "role": "sub_distribution_manager",
        "phone": "+8801793333333",
        "department": "Sub Distribution",
        "location": "Area 3",
        "parent_id": "subdist3@dms.com",
    },
]

# Devices to seed (various types with proper serial/mac/nuid)
DEVICES = [
    # ONUs
    {"type": "ONU", "model": "HG8145V5", "manufacturer": "Huawei", "serial": "ONU-SN-001", "mac": "00:11:22:33:44:01"},
    {"type": "ONU", "model": "HG8145V5", "manufacturer": "Huawei", "serial": "ONU-SN-002", "mac": "00:11:22:33:44:02"},
    {"type": "ONU", "model": "HG8145V5", "manufacturer": "Huawei", "serial": "ONU-SN-003", "mac": "00:11:22:33:44:03"},
    {"type": "ONU", "model": "HG8145V5", "manufacturer": "Huawei", "serial": "ONU-SN-004", "mac": "00:11:22:33:44:04"},
    
    # ONTs
    {"type": "ONT", "model": "GPON-204", "manufacturer": "FiberHome", "serial": "ONT-SN-001", "mac": "00:11:22:33:55:01"},
    {"type": "ONT", "model": "GPON-204", "manufacturer": "FiberHome", "serial": "ONT-SN-002", "mac": "00:11:22:33:55:02"},
    
    # Routers
    {"type": "Router", "model": "TPLINK-AC1200", "manufacturer": "TP-LINK", "serial": "RTR-SN-001", "mac": "00:11:22:33:66:01"},
    {"type": "Router", "model": "TPLINK-AC1200", "manufacturer": "TP-LINK", "serial": "RTR-SN-002", "mac": "00:11:22:33:66:02"},
    {"type": "Router", "model": "CISCO-2911", "manufacturer": "CISCO", "serial": "RTR-SN-003", "mac": "00:11:22:33:66:03"},
    
    # Switches
    {"type": "Switch", "model": "TP-LINK-24-PORT", "manufacturer": "TP-LINK", "serial": "SW-SN-001", "mac": "00:11:22:33:77:01"},
    {"type": "Switch", "model": "TP-LINK-24-PORT", "manufacturer": "TP-LINK", "serial": "SW-SN-002", "mac": "00:11:22:33:77:02"},
    
    # Modems
    {"type": "Modem", "model": "DOCSIS-3.1", "manufacturer": "ARRIS", "serial": "MDM-SN-001", "mac": "00:11:22:33:88:01"},
    {"type": "Modem", "model": "DOCSIS-3.1", "manufacturer": "ARRIS", "serial": "MDM-SN-002", "mac": "00:11:22:33:88:02"},
    
    # Access Points
    {"type": "Access Point", "model": "AP-2.4GHZ", "manufacturer": "UBIQUITI", "serial": "AP-SN-001", "mac": "00:11:22:33:99:01", "band": "single_band"},
    {"type": "Access Point", "model": "AP-DUAL-BAND", "manufacturer": "UBIQUITI", "serial": "AP-SN-002", "mac": "00:11:22:33:99:02", "band": "dual_band"},
    
    # Set-top boxes
    {"type": "Set-top box", "model": "HD-BOX", "manufacturer": "LOCAL", "nuid": "NU-ID-001", "box_type": "HD"},
    {"type": "Set-top box", "model": "OTT-BOX", "manufacturer": "LOCAL", "nuid": "NU-ID-002", "box_type": "OTT"},
    {"type": "Set-top box", "model": "HD-BOX", "manufacturer": "LOCAL", "nuid": "NU-ID-003", "box_type": "HD"},
    {"type": "Set-top box", "model": "OTT-BOX", "manufacturer": "LOCAL", "nuid": "NU-ID-004", "box_type": "OTT"},
]

# External inventory items
EXTERNAL_INVENTORY = [
    {"item_id": "EXT-ONU-001", "name": "ONU HG8145V5 - Batch 1", "serial": "ONU-EXT-001", "mac_id": "00:11:22:44:01:01", "device_type": "ONU", "price": 150.00, "supplier": "Huawei Direct"},
    {"item_id": "EXT-ONU-002", "name": "ONU HG8145V5 - Batch 2", "serial": "ONU-EXT-002", "mac_id": "00:11:22:44:01:02", "device_type": "ONU", "price": 150.00, "supplier": "Huawei Direct"},
    
    {"item_id": "EXT-ONT-001", "name": "ONT GPON-204 - Batch 1", "serial": "ONT-EXT-001", "mac_id": "00:11:22:44:02:01", "device_type": "ONT", "price": 120.00, "supplier": "FiberHome"},
    {"item_id": "EXT-ONT-002", "name": "ONT GPON-204 - Batch 2", "serial": "ONT-EXT-002", "mac_id": "00:11:22:44:02:02", "device_type": "ONT", "price": 120.00, "supplier": "FiberHome"},
    
    {"item_id": "EXT-RTR-001", "name": "Router TP-LINK AC1200", "serial": "RTR-EXT-001", "mac_id": "00:11:22:44:03:01", "device_type": "Router", "price": 80.00, "supplier": "TP-LINK Distributor"},
    {"item_id": "EXT-RTR-002", "name": "Router CISCO 2911", "serial": "RTR-EXT-002", "mac_id": "00:11:22:44:03:02", "device_type": "Router", "price": 250.00, "supplier": "CISCO Direct"},
    
    {"item_id": "EXT-SW-001", "name": "Switch 24-Port TP-LINK", "serial": "SW-EXT-001", "mac_id": "00:11:22:44:04:01", "device_type": "Switch", "price": 200.00, "supplier": "TP-LINK Distributor"},
    
    {"item_id": "EXT-MDM-001", "name": "Modem DOCSIS 3.1 ARRIS", "serial": "MDM-EXT-001", "mac_id": "00:11:22:44:05:01", "device_type": "Modem", "price": 110.00, "supplier": "ARRIS"},
    
    {"item_id": "EXT-AP-001", "name": "Access Point 2.4GHz Ubiquiti", "serial": "AP-EXT-001", "mac_id": "00:11:22:44:06:01", "device_type": "Access Point", "price": 95.00, "supplier": "Ubiquiti Systems"},
    
    {"item_id": "EXT-SB-001", "name": "Set-top Box HD Local", "serial": "SB-EXT-001", "mac_id": "NU-ID-EXT-001", "device_type": "Set-top box", "price": 75.00, "supplier": "Local Manufacturer"},
    {"item_id": "EXT-SB-002", "name": "Set-top Box OTT Local", "serial": "SB-EXT-002", "mac_id": "NU-ID-EXT-002", "device_type": "Set-top box", "price": 80.00, "supplier": "Local Manufacturer"},
]


async def seed_additional_users():
    """Seed MD Director and Sub Distribution Managers."""
    async with get_db() as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        created_count = 0

        # First, get all existing emails to build email->id map
        email_to_id = {}
        cursor = await db.execute("SELECT id, email FROM users")
        for row in await cursor.fetchall():
            email_to_id[row["email"]] = row["id"]

        print("\n" + "="*60)
        print("SEEDING ADDITIONAL USERS")
        print("="*60)

        for user_data in ADDITIONAL_USERS:
            email = user_data["email"]

            # Check if user already exists
            if email in email_to_id:
                print(f"  ⊘ Skipped {email} (already exists)")
                continue

            # Get parent user ID if specified
            parent_user_id = None
            if user_data["parent_id"]:
                parent_email = user_data["parent_id"]
                if parent_email in email_to_id:
                    parent_user_id = email_to_id[parent_email]

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
        print(f"\nAdditional Users Created: {created_count}")


async def seed_devices():
    """Seed devices in the devices table."""
    async with get_db() as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        created_count = 0

        print("\n" + "="*60)
        print("SEEDING DEVICES")
        print("="*60)

        for idx, device_data in enumerate(DEVICES, 1):
            device_type = device_data["type"]
            device_id = f"{device_type[0].upper()}-2026-{idx:04d}"
            
            # Prepare device-specific fields
            serial_number = device_data.get("serial", f"{device_type}-SN-{idx}")
            mac_address = device_data.get("mac", f"00:11:22:33:44:{idx:02x}")
            nuid = device_data.get("nuid", None)
            box_type = device_data.get("box_type", None)
            
            # Build metadata with box_type if present
            metadata = {}
            if box_type:
                metadata["box_type"] = box_type

            try:
                cursor = await db.execute(
                    """INSERT INTO devices 
                    (device_id, device_type, model, serial_number, mac_address, 
                     manufacturer, band_type, nuid, status, 
                     current_location, created_at, updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        device_id,
                        device_type,
                        device_data["model"],
                        serial_number,
                        mac_address,
                        device_data["manufacturer"],
                        device_data.get("band", None),
                        nuid,
                        "available",
                        None,
                        now,
                        now,
                        str(metadata).replace("'", '"'),  # Convert dict to JSON string
                    ),
                )

                if cursor.rowcount > 0:
                    print(f"  ✓ Created {device_id} ({device_type} - {device_data['model']})")
                    created_count += 1
                else:
                    print(f"  ✗ Failed to create {device_id}")
            except Exception as e:
                print(f"  ✗ Error creating {device_id}: {str(e)}")

        await db.commit()
        print(f"\nDevices Created: {created_count}")


async def seed_external_inventory():
    """Seed items in external inventory."""
    async with get_db() as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        created_count = 0

        print("\n" + "="*60)
        print("SEEDING EXTERNAL INVENTORY")
        print("="*60)

        for item_data in EXTERNAL_INVENTORY:
            try:
                # Generate unique inventory_id
                inventory_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
                
                cursor = await db.execute(
                    """INSERT INTO external_inventory_items 
                    (inventory_id, item_id, name, serial_number, mac_id, device_type, 
                     price, unit, supplier_name, location, status, notes, 
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        inventory_id,
                        item_data["item_id"],
                        item_data["name"],
                        item_data["serial"],
                        item_data["mac_id"],
                        item_data["device_type"],
                        item_data["price"],
                        "pcs",
                        item_data["supplier"],
                        None,
                        "active",
                        None,
                        now,
                        now,
                    ),
                )

                if cursor.rowcount > 0:
                    print(f"  ✓ Created {item_data['item_id']} ({item_data['name']})")
                    created_count += 1
                else:
                    print(f"  ✗ Failed to create {item_data['item_id']}")
            except Exception as e:
                print(f"  ✗ Error creating {item_data['item_id']}: {str(e)}")

        await db.commit()
        print(f"\nExternal Inventory Items Created: {created_count}")


async def main():
    """Run all seeding operations."""
    print("\n" + "╔" + "="*58 + "╗")
    print("║  COMPREHENSIVE DATABASE SEEDING                          ║")
    print("╚" + "="*58 + "╝")

    try:
        await seed_additional_users()
        await seed_devices()
        await seed_external_inventory()

        print("\n" + "="*60)
        print("✓ SEEDING COMPLETE!")
        print("="*60)
        print(f"All items seeded with password: {PASSWORD}")
    except Exception as e:
        print(f"\n✗ SEEDING FAILED: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
