import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'device_bulk_upload_5000.csv'
OUT = ROOT / 'device_bulk_upload_4000.csv'
NUM = 4000

vendors = ['Huawei','ZTE','Nokia','TP-Link','Cisco','D-Link','MikroTik','Ubiquiti']
types = ['ONT','ONU','Router','Modem','Switch','Access Point']
models = ['HG8546M','F601','G-140W-C','AX1800','Archer C6','EAP225','MB8600','SG108']
bands = ['single_band','dual_band']

# Read header from existing file if present, else use default
if SRC.exists():
    with SRC.open('r', encoding='utf-8', newline='') as f:
        rdr = csv.reader(f)
        header = next(rdr)
else:
    header = ['Vendor','device_type','model','mac_address','serial_number','band_type']

with OUT.open('w', encoding='utf-8', newline='') as f:
    w = csv.writer(f)
    w.writerow(header)
    for i in range(1, NUM+1):
        vendor = vendors[i % len(vendors)]
        device_type = types[i % len(types)]
        model = models[i % len(models)]
        # Build a unique MAC using the index (ensures no duplicates up to large counts)
        mac = 'AA:DE:{:02X}:{:02X}:{:02X}:{:02X}'.format((i>>24)&0xFF, (i>>16)&0xFF, (i>>8)&0xFF, i&0xFF)
        serial = f'SN-NEW-{i:05d}'
        band = bands[i % len(bands)]
        w.writerow([vendor, device_type, model, mac, serial, band])

print(f'Wrote {OUT} with {NUM} unique devices')