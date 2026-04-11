#!/usr/bin/env python3
"""Append devices until the devices table reaches 8,000 rows."""

import asyncio
import json
from collections import Counter
from datetime import datetime, timezone

from app.database import get_db


TARGET_TOTAL = 8000


def build_device_specs(count: int):
    """Build device specs for the requested count across supported types."""
    specs = []

    def add_many(device_type, model, manufacturer, count_value):
        for _ in range(count_value):
            specs.append(
                {
                    "device_type": device_type,
                    "model": model,
                    "manufacturer": manufacturer,
                    "band_type": None,
                    "nuid": None,
                    "box_type": None,
                }
            )

    base_plan = [
        ("ONU", "HG8245Q2", "Huawei", 9),
        ("ONT", "AN5506-04", "FiberHome", 7),
        ("Router", "Archer C6", "TP-LINK", 6),
        ("Switch", "CBS110-24T", "Cisco", 5),
        ("Modem", "CM500", "NETGEAR", 4),
        ("Access Point", "UniFi UAP-AC-Lite", "Ubiquiti", 5),
        ("Set-top box", "DMS-TV-BOX", "SkyStream", 3),
        ("Other", "Custom CPE Unit", "Generic", 1),
    ]

    if count <= 0:
        return specs

    full_cycles, remainder = divmod(count, sum(item[3] for item in base_plan))
    expanded_plan = []
    for _ in range(full_cycles):
        expanded_plan.extend(base_plan)

    if remainder:
        remaining = remainder
        for device_type, model, manufacturer, cycle_count in base_plan:
            if remaining <= 0:
                break
            take = min(cycle_count, remaining)
            expanded_plan.append((device_type, model, manufacturer, take))
            remaining -= take

    plan = expanded_plan or base_plan

    for device_type, model, manufacturer, count_value in plan:
        if device_type == "Access Point":
            for idx in range(count_value):
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
            for idx in range(count_value):
                specs.append(
                    {
                        "device_type": device_type,
                        "model": model,
                        "manufacturer": manufacturer,
                        "band_type": None,
                        "nuid": f"NUID-ADD-{idx + 1:04d}",
                        "box_type": "HD" if idx % 2 == 0 else "OTT",
                    }
                )
            continue

        add_many(device_type, model, manufacturer, count_value)

    return specs


def int_to_mac(value: int) -> str:
    """Turn an integer into a deterministic unique MAC address."""
    value &= (1 << 32) - 1
    return f"02:{(value >> 24) & 0xFF:02X}:{(value >> 16) & 0xFF:02X}:{(value >> 8) & 0xFF:02X}:{value & 0xFF:02X}:{(value ^ 0xA5) & 0xFF:02X}"


async def seed_additional_devices():
    async with get_db() as db:
        existing = await db.execute("SELECT COUNT(*) FROM devices")
        existing_total = (await existing.fetchone())[0]

    remaining_needed = max(0, TARGET_TOTAL - existing_total)
    specs = build_device_specs(remaining_needed)
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    token = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    start_offset = existing_total + 1

    inserted = 0
    skipped = 0
    type_counts = Counter(item["device_type"] for item in specs)

    async with get_db() as db:
        for idx, spec in enumerate(specs, start=start_offset):
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

            device_id = f"{prefix}-{token}-{idx:04d}"
            serial_number = f"{prefix}-SN-{token}-{idx:04d}"
            mac_address = int_to_mac(idx)

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

    print(f"Existing before insert: {existing_total}")
    print("Additional device type counts:")
    for device_type in sorted(type_counts):
        print(f"  {device_type}: {type_counts[device_type]}")
    print(f"Remaining needed to reach {TARGET_TOTAL}: {remaining_needed}")
    print(f"Requested: {len(specs)}")
    print(f"Inserted: {inserted}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(seed_additional_devices())
