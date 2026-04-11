#!/usr/bin/env python3
"""Seed external inventory items across all device types."""

import asyncio
from datetime import datetime, timezone

from app.database import get_db


def build_items(run_token: str):
    items = []
    global_seq = 1

    def add_many(prefix, label, device_type, supplier, unit_price, count):
        nonlocal global_seq
        for i in range(1, count + 1):
            oct3 = global_seq % 256
            oct4 = (global_seq + 40) % 256
            oct5 = (global_seq + 80) % 256
            oct6 = (global_seq + 120) % 256
            items.append(
                {
                    "item_id": f"{prefix}-{run_token}-{i:03d}",
                    "name": f"{label} Batch {i}",
                    "serial_number": f"{prefix}-SER-{run_token}-{i:03d}",
                    "mac_id": f"02:60:{oct3:02X}:{oct4:02X}:{oct5:02X}:{oct6:02X}",
                    "device_type": device_type,
                    "price": unit_price,
                    "supplier_name": supplier,
                }
            )
            global_seq += 1

    add_many("EXT-ONU", "ONU HG8245Q2", "ONU", "Huawei Supply", 145.0, 5)
    add_many("EXT-ONT", "ONT AN5506-04", "ONT", "FiberHome Supply", 135.0, 5)
    add_many("EXT-RTR", "Router Archer C6", "Router", "TP-LINK Supply", 95.0, 4)
    add_many("EXT-SWT", "Switch CBS110-24T", "Switch", "Cisco Supply", 180.0, 4)
    add_many("EXT-MDM", "Modem CM500", "Modem", "NETGEAR Supply", 105.0, 4)
    add_many("EXT-AP", "Access Point UAP-AC-Lite", "Access Point", "Ubiquiti Supply", 120.0, 4)

    # Set-top box uses NU/identifier in mac_id field as supported by model.
    for i in range(1, 5):
        items.append(
            {
                "item_id": f"EXT-STB-{run_token}-{i:03d}",
                "name": f"Set-top Box DMS-TV-BOX Batch {i}",
                "serial_number": f"EXT-STB-SER-{run_token}-{i:03d}",
                "mac_id": f"NUID-EXT-{run_token}-{i:03d}",
                "device_type": "Set-top box",
                "price": 88.0 if i % 2 == 0 else 84.0,
                "supplier_name": "SkyStream Supply",
            }
        )

    return items


async def seed_external_inventory():
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    run_token = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    items = build_items(run_token)

    inserted = 0
    skipped = 0

    async with get_db() as db:
        for idx, item in enumerate(items, start=1):
            inventory_id = f"INV-{run_token}-{idx:03d}"

            dup = await db.execute(
                "SELECT id FROM external_inventory_items WHERE inventory_id = ? OR item_id = ? OR serial_number = ? OR mac_id = ?",
                (inventory_id, item["item_id"], item["serial_number"], item["mac_id"]),
            )
            if await dup.fetchone():
                skipped += 1
                continue

            await db.execute(
                """INSERT INTO external_inventory_items (
                    inventory_id, item_id, name, serial_number, mac_id, device_type,
                    price, unit, quantity_on_hand, reorder_level, unit_cost,
                    supplier_name, location, status, notes, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    inventory_id,
                    item["item_id"],
                    item["name"],
                    item["serial_number"],
                    item["mac_id"],
                    item["device_type"],
                    item["price"],
                    "pcs",
                    0,
                    5,
                    item["price"],
                    item["supplier_name"],
                    "Main External Store",
                    "active",
                    "Bulk seeded for testing",
                    "bulk-seeder",
                    now,
                    now,
                ),
            )
            inserted += 1

        await db.commit()

    print(f"Requested: {len(items)}")
    print(f"Inserted: {inserted}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(seed_external_inventory())
