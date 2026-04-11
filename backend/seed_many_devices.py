#!/usr/bin/env python3
"""Seed about 4,000 devices across all supported device types."""

import asyncio
import json
from collections import Counter
from datetime import datetime, timezone

from app.database import get_db


def build_device_specs():
    """Build exactly 4,000 device specs across all supported types."""
    specs = []

    def add_many(device_type, model, manufacturer, count, band_type=None):
        for _ in range(count):
            specs.append(
                {
                    "device_type": device_type,
                    "model": model,
                    "manufacturer": manufacturer,
                    "band_type": band_type,
                    "nuid": None,
                    "box_type": None,
                }
            )

    type_plan = [
        ("ONU", "HG8245Q2", "Huawei", 900, None),
        ("ONT", "AN5506-04", "FiberHome", 700, None),
        ("Router", "Archer C6", "TP-LINK", 600, None),
        ("Switch", "CBS110-24T", "Cisco", 500, None),
        ("Modem", "CM500", "NETGEAR", 400, None),
        ("Access Point", "UniFi UAP-AC-Lite", "Ubiquiti", 500, None),
        ("Set-top box", "DMS-TV-BOX", "SkyStream", 350, None),
        ("Other", "Custom CPE Unit", "Generic", 50, None),
    ]

    for device_type, model, manufacturer, count, band_type in type_plan:
        if device_type == "Access Point":
            for idx in range(count):
                specs.append(
                    {
                        "device_type": device_type,
                        "model": model,
                        "manufacturer": manufacturer,
                        "band_type": "dual_band" if idx % 2 == 0 else "single_band",
                        "nuid": None,
                        "box_type": None,
                    }
                )
            continue

        if device_type == "Set-top box":
            for idx in range(count):
                specs.append(
                    {
                        "device_type": device_type,
                        "model": model,
                        "manufacturer": manufacturer,
                        "band_type": None,
                        "nuid": f"NUID-BULK-{idx + 1:04d}",
                        "box_type": "HD" if idx % 2 == 0 else "OTT",
                    }
                )
            continue

        add_many(device_type, model, manufacturer, count, band_type=band_type)

    return specs


async def seed_many_devices():
    specs = build_device_specs()
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    token = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    inserted = 0
    skipped = 0

    type_counts = Counter(item["device_type"] for item in specs)

    async with get_db() as db:
        await db.execute("DELETE FROM device_history")
        await db.execute("DELETE FROM devices")
        await db.commit()

        for idx, spec in enumerate(specs, start=1):
            dtype = spec["device_type"]
            prefix = {
                "ONU": "ONU",
                "ONT": "ONT",
                "Router": "RTR",
                "Switch": "SWT",
                "Modem": "MDM",
                "Access Point": "AP",
                "Set-top box": "STB",
                "Other": "OTH",
            }[dtype]

            device_id = f"{prefix}-{token}-{idx:03d}"
            serial_number = f"{prefix}-SN-{token}-{idx:03d}"
            mac_address = f"02:50:{idx:02X}:{(idx + 16) % 256:02X}:{(idx + 32) % 256:02X}:{(idx + 48) % 256:02X}"

            # Skip any accidental duplicate in reruns.
            dup_cursor = await db.execute(
                "SELECT id FROM devices WHERE device_id = ? OR serial_number = ? OR mac_address = ?",
                (device_id, serial_number, mac_address),
            )
            if await dup_cursor.fetchone():
                skipped += 1
                continue

            metadata = {}
            if spec["box_type"]:
                metadata["box_type"] = spec["box_type"]

            await db.execute(
                """INSERT INTO devices (
                    device_id, device_type, model, serial_number, mac_address,
                    manufacturer, band_type, nuid, status,
                    current_location, current_holder_id, current_holder_name,
                    current_holder_type, registered_by_name,
                    purchase_date, warranty_expiry, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    device_id,
                    dtype,
                    spec["model"],
                    serial_number,
                    mac_address,
                    spec["manufacturer"],
                    spec["band_type"],
                    spec["nuid"],
                    "available",
                    "PDIC",
                    None,
                    "PDIC (Distribution)",
                    "noc",
                    "Bulk Seeder",
                    None,
                    None,
                    json.dumps(metadata) if metadata else None,
                    now,
                    now,
                ),
            )
            inserted += 1

        await db.commit()

    print("Device type counts:")
    for device_type in sorted(type_counts):
        print(f"  {device_type}: {type_counts[device_type]}")
    print(f"Requested: {len(specs)}")
    print(f"Inserted: {inserted}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(seed_many_devices())
