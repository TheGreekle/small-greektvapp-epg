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

# Maximale erlaubte Dateigröße:
# 460.000 Bytes = 0,46 MB
MAX_OUTPUT_SIZE = 460_000

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

print(f"Originalgröße: {len(data) / 1_000_000:.2f} MB")


# ============================================================
# XML EINLESEN
# ============================================================

try:
    root = ET.fromstring(data)
except ET.ParseError as error:
    raise RuntimeError(
        f"EPG-XML konnte nicht gelesen werden: {error}"
    )


# ============================================================
# AKTUELLE ZEIT
# ============================================================

now_utc = datetime.now(timezone.utc)

print(f"Aktuelle UTC-Zeit: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")


# ============================================================
# 24-STUNDEN-FENSTER
# ============================================================
#
# Der Workflow läuft um:
#
# 03:00 UTC
# 15:00 UTC
#
# Gewünschte Fenster:
#
# 03:00-Lauf:
# 00:00 heute -> 00:00 morgen
#
# 15:00-Lauf:
# 12:00 heute -> 12:00 morgen
#
# Die Entscheidung basiert auf der aktuellen UTC-Zeit.
# ============================================================

today = now_utc.date()

if now_utc.hour < 12:
    # --------------------------------------------------------
    # Vormittags-Lauf
    #
    # EPG:
    # heute 00:00
    # bis
    # morgen 00:00
    # --------------------------------------------------------

    window_start = datetime.combine(
        today,
        datetime.min.time(),
        tzinfo=timezone.utc
    )

    window_end = window_start + timedelta(days=1)

    window_name = "00:00 bis 24:00 UTC"

else:
    # --------------------------------------------------------
    # Nachmittags-/Abendlauf
    #
    # EPG:
    # heute 12:00
    # bis
    # morgen 12:00
    # --------------------------------------------------------

    window_start = datetime.combine(
        today,
        datetime.min.time(),
        tzinfo=timezone.utc
    ) + timedelta(hours=12)

    window_end = window_start + timedelta(days=1)

    window_name = "12:00 bis 12:00 UTC"


print("")
print("========== EPG ZEITFENSTER ==========")
print(f"Fenster:        {window_name}")
print(
    "Von:            "
    f"{window_start.strftime('%Y-%m-%d %H:%M:%S UTC')}"
)
print(
    "Bis:            "
    f"{window_end.strftime('%Y-%m-%d %H:%M:%S UTC')}"
)
print("Dauer:          24 Stunden")
print("=====================================")


# ============================================================
# NEUE XMLTV-DATEI
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
# XMLTV-ZEITSTEMPEL PARSEN
# ============================================================

def parse_xmltv_datetime(value):
    """
    Wandelt einen XMLTV-Zeitstempel in einen timezone-aware
    datetime-Wert um.

    Beispiele:

    20260819120000 +0300
    20260819120000 +0200
    20260819120000
    """

    if not value:
        return None

    value = value.strip()

    if len(value) < 14:
        return None

    try:
        date_part = value[:14]

        naive_datetime = datetime.strptime(
            date_part,
            "%Y%m%d%H%M%S"
        )

    except ValueError:
        return None


    # Rest des XMLTV-Zeitstempels
    offset_part = value[14:].strip()


    # --------------------------------------------------------
    # Zeitzonenoffset vorhanden?
    # --------------------------------------------------------

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

        return naive_datetime.replace(
            tzinfo=timezone(offset)
        )


    # Falls kein Offset vorhanden ist:
    # als UTC behandeln.
    return naive_datetime.replace(
        tzinfo=timezone.utc
    )


# ============================================================
# PROGRAMME FILTERN
# ============================================================

program_count = 0
skipped_programs = 0

for programme in root.findall("programme"):

    channel_id = programme.get("channel")

    # --------------------------------------------------------
    # Nur gewünschte Sender
    # --------------------------------------------------------

    if channel_id not in CHANNELS:
        continue


    # --------------------------------------------------------
    # Startzeit
    # --------------------------------------------------------

    start = programme.get("start")

    if not start:
        skipped_programs += 1
        continue


    programme_start = parse_xmltv_datetime(start)

    if programme_start is None:
        print(
            "Warnung: Ungültiger Startzeitpunkt "
            f"übersprungen: {start}"
        )

        skipped_programs += 1
        continue


    # --------------------------------------------------------
    # Startzeit in UTC umwandeln
    # --------------------------------------------------------

    programme_start_utc = programme_start.astimezone(
        timezone.utc
    )


    # --------------------------------------------------------
    # Endzeit ermitteln
    #
    # Wir berücksichtigen auch Programme, die über eine
    # Grenze des 24-Stunden-Fensters hinauslaufen.
    # --------------------------------------------------------

    stop = programme.get("stop")

    if stop:

        programme_stop = parse_xmltv_datetime(stop)

        if programme_stop is not None:

            programme_stop_utc = programme_stop.astimezone(
                timezone.utc
            )

        else:
            programme_stop_utc = None

    else:
        programme_stop_utc = None


    # --------------------------------------------------------
    # PROGRAMM-FILTER
    # --------------------------------------------------------
    #
    # Ein Programm wird übernommen, wenn es das 24-Stunden-
    # Fenster zumindest teilweise überschneidet.
    #
    # Beispiel:
    #
    # Fenster:
    # 00:00 -> 24:00
    #
    # Programm:
    # 23:30 -> 01:30
    #
    # -> wird übernommen
    #
    # Programm:
    # 23:00 gestern -> 00:30 heute
    #
    # -> wird ebenfalls übernommen
    #
    # --------------------------------------------------------

    if programme_stop_utc is not None:

        # Keine Überschneidung?
        if (
            programme_stop_utc <= window_start
            or programme_start_utc >= window_end
        ):
            continue

    else:

        # Falls keine Endzeit vorhanden ist, wird nur die
        # Startzeit geprüft.
        if not (
            window_start
            <= programme_start_utc
            < window_end
        ):
            continue


    # --------------------------------------------------------
    # Programm übernehmen
    # --------------------------------------------------------

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
# SENDERKONTROLLE
# ============================================================

output_channel_ids = {
    channel.get("id")
    for channel in new_root.findall("channel")
}

missing_channels = CHANNELS - output_channel_ids
extra_channels = output_channel_ids - CHANNELS


# ============================================================
# DATEIGRÖSSE
# ============================================================

size = os.path.getsize(OUTPUT_FILE)

size_mb = size / 1_000_000


# ============================================================
# KONTROLLE
# ============================================================

print("")
print("========== EPG KONTROLLE ==========")

print(f"Gewünschte Sender: {len(CHANNELS)}")
print(f"Gefundene Sender:  {len(output_channel_ids)}")
print(f"Programme:         {program_count}")

if skipped_programs:
    print(
        f"Übersprungene ungültige Programme: "
        f"{skipped_programs}"
    )

print("")

if missing_channels:

    print(
        "FEHLER: Folgende gewünschte Sender fehlen:"
    )

    for channel in sorted(missing_channels):
        print(f"  - {channel}")

else:

    print(
        "Alle gewünschten Sender sind vorhanden."
    )


if extra_channels:

    print("")
    print(
        "FEHLER: Folgende unerwartete Sender sind enthalten:"
    )

    for channel in sorted(extra_channels):
        print(f"  - {channel}")

else:

    print(
        "Keine unerwünschten Sender enthalten."
    )


print("")
print(f"Originalgröße:      {len(data) / 1_000_000:.2f} MB")
print(f"Neue EPG-Größe:     {size_mb:.3f} MB")
print(f"Maximal erlaubt:    {MAX_OUTPUT_SIZE / 1_000_000:.2f} MB")
print(
    f"Ausgabedatei:       {OUTPUT_FILE}"
)

print("")
print("====================================")


# ============================================================
# SENDERFEHLER
# ============================================================

if missing_channels or extra_channels:

    raise RuntimeError(
        "EPG-Senderkontrolle fehlgeschlagen."
    )


# ============================================================
# DATEIGRÖSSEN-KONTROLLE
# ============================================================

if size > MAX_OUTPUT_SIZE:

    print("")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("FEHLER: EPG-DATEI IST ZU GROSS!")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("")
    print(
        f"Dateigröße:       {size_mb:.3f} MB"
    )
    print(
        f"Maximal erlaubt:  "
        f"{MAX_OUTPUT_SIZE / 1_000_000:.2f} MB"
    )
    print("")
    print(
        "Der GitHub-Workflow wird abgebrochen."
    )
    print(
        "Die zu große EPG wird NICHT veröffentlicht."
    )
    print("")

    raise RuntimeError(
        "EPG-Datei überschreitet das "
        "Limit von 0,46 MB."
    )


# ============================================================
# ERFOLGREICH
# ============================================================

print("")
print("EPG-Kontrolle erfolgreich.")
print(
    f"Dateigröße liegt unter "
    f"{MAX_OUTPUT_SIZE / 1_000_000:.2f} MB."
)
print(
    f"Neue EPG-Größe: {size_mb:.3f} MB"
)
print(
    f"EPG-Fenster: "
    f"{window_start.strftime('%Y-%m-%d %H:%M')} UTC "
    f"bis "
    f"{window_end.strftime('%Y-%m-%d %H:%M')} UTC"
)
print("")
print(f"Fertig: {OUTPUT_FILE}")
