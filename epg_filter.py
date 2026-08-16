import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

SOURCE_URL = "https://ext.greektv.app/epg/epg.xml"
OUTPUT_DIR = "public"
OUTPUT_FILE = "public/epg_ssiptv.xml"

CHANNELS = {
    "ert1",
    "ert2",
    "ert3",
    "mega",
    "ant1",
    "alfa",
    "skai",
    "open",
    "star",
    "starint",
    "tv100",
    "onetv",
    "vouli",
    "ertworld",
    "ertnews",
    "meganews",
    "pronews",
    "ertsports",
    "ertsports2",
    "riksat",
    "rik1",
    "rik2",
    "rikhd",
    "omega",
    "ant1cy",
    "sigma",
    "berginacy",
    "4e",
    "starke",
    "astratv",
    "action24",
    "alert",
    "kontra",
    "neatvcrete",
    "corfutv",
    "creta",
    "krititv1",
    "ionian",
    "Naftemporikitv",
    "topchannel",
    "aigaiotv",
    "eurotv",
    "kostv",
    "lepanto",
    "pellatv",
    "centertv",
    "syrostv1",
    "trt",
    "berginatv",
    "egnatia",
    "besttv",
    "starttv",
    "gnomitv",
    "mtv",
}

print("Lade originale EPG herunter...")

import os
os.makedirs(OUTPUT_DIR, exist_ok=True)

request = urllib.request.Request(
    SOURCE_URL,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/xml,text/xml,*/*",
        "Accept-Encoding": "gzip, deflate",
    }
)

with urllib.request.urlopen(request, timeout=120) as response:
    data = response.read()

    if response.headers.get("Content-Encoding") == "gzip":
        import gzip
        data = gzip.decompress(data)

print(f"Originalgröße: {len(data) / 1024 / 1024:.2f} MB")

root = ET.fromstring(data)

# Heute nach UTC
today = datetime.now(timezone.utc).date()

# Gestern bis einschließlich heute + 2 Tage
date_from = today - timedelta(days=1)
date_to = today + timedelta(days=2)

print(f"EPG-Zeitraum: {date_from} bis {date_to}")
print(f"Sender: {len(CHANNELS)}")

# Neue XMLTV-Datei erzeugen
new_root = ET.Element("tv", root.attrib)

# Nur gewünschte Channels übernehmen
for channel in root.findall("channel"):
    channel_id = channel.get("id")

    if channel_id in CHANNELS:
        new_root.append(channel)

# Nur Programme der gewünschten Sender und des gewünschten Zeitraums
program_count = 0

for programme in root.findall("programme"):
    channel_id = programme.get("channel")

    if channel_id not in CHANNELS:
        continue

    start = programme.get("start")

    if not start:
        continue

    try:
        # XMLTV-Zeitformat:
        # 20260816120000 +0300
        start_date = datetime.strptime(
            start[:14],
            "%Y%m%d%H%M%S"
        ).date()
    except ValueError:
        continue

    if date_from <= start_date <= date_to:
        new_root.append(programme)
        program_count += 1

tree = ET.ElementTree(new_root)

ET.indent(tree, space="  ")

tree.write(
    OUTPUT_FILE,
    encoding="UTF-8",
    xml_declaration=True
)

print(f"Programme übernommen: {program_count}")

size = os.path.getsize(OUTPUT_FILE)

print(
    f"Neue EPG-Größe: {size / 1024 / 1024:.2f} MB"
)

print(f"Fertig: {OUTPUT_FILE}")
