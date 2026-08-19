import os
import gzip
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone


# ============================================================
# KONFIGURATION
# ============================================================

SOURCE_URL = "https://ext.greektv.app/epg/epg.xml"

OUTPUT_DIR = "public"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "epg_ssiptv.xml")

# Nur diese Sender werden übernommen
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
    "mtv",
}


# ============================================================
# EPG HERUNTERLADEN
# ============================================================

print("Lade originale EPG herunter...")

os.makedirs(OUTPUT_DIR, exist_ok=True)

request = urllib.request.Request(
    SOURCE_URL,
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/xml,text/xml,*/*",
        "Accept-Encoding": "gzip, deflate",
    }
)

with urllib.request.urlopen(request, timeout=120) as response:
    data = response.read()

    if response.headers.get("Content-Encoding") == "gzip":
        data = gzip.decompress(data)

print(f"Originalgröße: {len(data) / 1024 / 1024:.2f} MB")


# ============================================================
# XML EINLESEN
# ============================================================

try:
    root = ET.fromstring(data)
except ET.ParseError as error:
    raise RuntimeError(f"EPG-XML konnte nicht gelesen werden: {error}")


# ============================================================
# ZEITRAUM
# ============================================================
#
# Es werden ausschließlich HEUTE und MORGEN übernommen.
#
# Beispiel:
# Heute    = 2026-08-19
# Morgen   = 2026-08-20
#
# Die Berechnung erfolgt anhand von UTC.
# ============================================================

today = datetime.now(timezone.utc).date()
tomorrow = today + timedelta(days=1)

date_from = today
date_to = tomorrow

print(f"EPG-Zeitraum: {date_from} bis {date_to}")
print(f"Sender: {len(CHANNELS)}")


# ============================================================
# NEUE XMLTV-DATEI ERSTELLEN
# ============================================================

new_root = ET.Element("tv", root.attrib)


# ============================================================
# CHANNELS FILTERN
# ============================================================

channel_count = 0

for channel in root.findall("channel"):
    channel_id = channel.get("id")

    if channel_id in CHANNELS:
        new_root.append(channel)
        channel_count += 1


# ============================================================
# PROGRAMME FILTERN
# ============================================================

program_count = 0

for programme in root.findall("programme"):

    channel_id = programme.get("channel")

    # Nur gewünschte Sender
    if channel_id not in CHANNELS:
        continue

    start = programme.get("start")

    if not start:
        continue

    # --------------------------------------------------------
    # XMLTV-Zeitstempel auswerten
    #
    # Typisches Format:
    #
    # 20260819120000 +0300
    #
    # oder:
    #
    # 20260819120000 +0200
    #
    # Wir berücksichtigen den vorhandenen UTC-Offset.
    # --------------------------------------------------------

    try:
        start_clean = start.strip()

        # Die ersten 14 Zeichen enthalten:
        # YYYYMMDDHHMMSS
        date_part = start_clean[:14]

        # Rest enthält normalerweise den Zeitzonenoffset
        offset_part = start_clean[14:].strip()

        naive_start = datetime.strptime(
            date_part,
            "%Y%m%d%H%M%S"
        )

        # ----------------------------------------------------
        # Zeitzonenoffset aus XMLTV übernehmen
        # ----------------------------------------------------

        if (
            len(offset_part) >= 5
            and offset_part[0] in ("+", "-")
            and offset_part[1:5].isdigit()
        ):
            sign = 1 if offset_part[0] == "+" else -1

            offset_hours = int(offset_part[1:3])
            offset_minutes = int(offset_part[3:5])

            offset = timedelta(
                hours=offset_hours,
                minutes=offset_minutes
            ) * sign

            programme_start = naive_start.replace(
                tzinfo=timezone(offset)
            )

        else:
            # Falls kein Offset vorhanden ist:
            # Zeit als UTC behandeln.
            programme_start = naive_start.replace(
                tzinfo=timezone.utc
            )

    except (ValueError, IndexError):
        print(
            f"Warnung: Ungültiger Startzeitpunkt "
            f"übersprungen: {start}"
        )
        continue


    # --------------------------------------------------------
    # Für die Tagesauswahl wird die im XML angegebenen
    # lokale Zeit verwendet.
    #
    # Dadurch bleibt z.B.:
    #
    # 20260819233000 +0300
    #
    # am 19.08. und wird nicht versehentlich durch UTC
    # auf den 20.08. verschoben.
    # --------------------------------------------------------

    programme_date = programme_start.date()


    # --------------------------------------------------------
    # Nur HEUTE und MORGEN
    # --------------------------------------------------------

    if date_from <= programme_date <= date_to:
        new_root.append(programme)
        program_count += 1


# ============================================================
# XML SCHREIBEN
# ============================================================

tree = ET.ElementTree(new_root)

ET.indent(tree, space="  ")

tree.write(
    OUTPUT_FILE,
    encoding="UTF-8",
    xml_declaration=True
)


# ============================================================
# KONTROLLE DER ENTHALTENEN SENDER
# ============================================================

output_channel_ids = {
    channel.get("id")
    for channel in new_root.findall("channel")
}

missing_channels = CHANNELS - output_channel_ids
extra_channels = output_channel_ids - CHANNELS


# ============================================================
# AUSGABE / KONTROLLE
# ============================================================

print("")
print("========== EPG KONTROLLE ==========")

print(f"Gewünschte Sender: {len(CHANNELS)}")
print(f"Gefundene Sender:  {len(output_channel_ids)}")
print(f"Programme:         {program_count}")

print("")

if missing_channels:
    print("FEHLER: Folgende gewünschte Sender fehlen:")

    for channel in sorted(missing_channels):
        print(f"  - {channel}")

else:
    print("Alle gewünschten Sender sind vorhanden.")


if extra_channels:
    print("")
    print("FEHLER: Folgende unerwartete Sender sind enthalten:")

    for channel in sorted(extra_channels):
        print(f"  - {channel}")

else:
    print("Keine unerwünschten Sender enthalten.")


# ============================================================
# DATEIGRÖSSE
# ============================================================

size = os.path.getsize(OUTPUT_FILE)

print("")
print(f"Originalgröße:      {len(data) / 1024 / 1024:.2f} MB")
print(f"Neue EPG-Größe:     {size / 1024 / 1024:.2f} MB")
print(f"Zeitraum:           {date_from} bis {date_to}")
print(f"Ausgabedatei:       {OUTPUT_FILE}")
print("====================================")


# ============================================================
# WORKFLOW BEI FEHLERN ABBRECHEN
# ============================================================

if missing_channels or extra_channels:
    raise RuntimeError(
        "EPG-Senderkontrolle fehlgeschlagen."
    )


print("EPG-Kontrolle erfolgreich.")
print(f"Fertig: {OUTPUT_FILE}")
