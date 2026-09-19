import os
import gzip
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone


# ============================================================
# KONFIGURATION
# ============================================================

SOURCE_URL = "https://ext.greektv.app/epg/epg.xml"

OUTPUT_DIR = "public"

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "epg_ssiptv.xml"
)

# Maximale erlaubte Dateigröße:
#
# SS IPTV empfiehlt XMLTV-Dateien unter 5 MB.
# Wir verwenden deshalb 4,9 MB als Sicherheitsgrenze.
#
MAX_OUTPUT_SIZE = 4_900_000


# ============================================================
# START ZEITMESSUNG
# ============================================================

total_start = time.perf_counter()


# ============================================================
# EPG HERUNTERLADEN
# ============================================================

print("Lade originale EPG herunter...")

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)

download_start = time.perf_counter()

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

with urllib.request.urlopen(
    request,
    timeout=120
) as response:

    data = response.read()

    if response.headers.get(
        "Content-Encoding"
    ) == "gzip":

        data = gzip.decompress(data)


download_time = (
    time.perf_counter() -
    download_start
)

print(
    f"Originalgröße: "
    f"{len(data) / 1_000_000:.2f} MB"
)

print(
    f"EPG Download: "
    f"{download_time:.2f} Sekunden"
)


# ============================================================
# XML EINLESEN
# ============================================================

parse_start = time.perf_counter()

try:

    root = ET.fromstring(data)

except ET.ParseError as error:

    raise RuntimeError(
        f"EPG-XML konnte nicht gelesen werden: {error}"
    )

parse_time = (
    time.perf_counter() -
    parse_start
)

print(
    f"XML Parsing: "
    f"{parse_time:.2f} Sekunden"
)


# ============================================================
# AKTUELLE UTC-ZEIT
# ============================================================

now_utc = datetime.now(timezone.utc)

print("")
print(
    "Aktuelle UTC-Zeit: "
    f"{now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}"
)


# ============================================================
# 30-STUNDEN-FENSTER
# ============================================================
#
# Das Fenster ist immer:
#
#   aktuelle UTC-Zeit - 3 Stunden
#   bis
#   aktuelle UTC-Zeit + 27 Stunden
#
# Dadurch entstehen exakt 30 Stunden.
#
# Bei jedem Workflow-Lauf verschiebt sich das Fenster
# entsprechend der aktuellen Uhrzeit.
#
# ============================================================

window_start = (
    now_utc -
    timedelta(hours=3)
)

window_end = (
    now_utc +
    timedelta(hours=27)
)


print("")
print(
    "========== EPG ZEITFENSTER =========="
)

print(
    "Von:            "
    f"{window_start.strftime('%Y-%m-%d %H:%M:%S UTC')}"
)

print(
    "Bis:            "
    f"{window_end.strftime('%Y-%m-%d %H:%M:%S UTC')}"
)

print(
    "Dauer:          30 Stunden"
)

print(
    "====================================="
)


# ============================================================
# NEUE XMLTV-DATEI
# ============================================================

filter_start = time.perf_counter()

new_root = ET.Element(
    "tv",
    root.attrib
)


# ============================================================
# ALLE CHANNELS ÜBERNEHMEN
# ============================================================
#
# Es gibt KEINE Senderliste mehr.
#
# Jeder <channel>-Eintrag aus dem Original-EPG
# wird übernommen.
#
# ============================================================

channel_count = 0

output_channel_ids = set()

for channel in root.findall("channel"):

    channel_id = channel.get("id")

    if channel_id:

        output_channel_ids.add(
            channel_id
        )

    new_root.append(
        channel
    )

    channel_count += 1


print("")
print(
    "========== SENDER =========="
)

print(
    f"Übernommene Sender: "
    f"{channel_count}"
)

print(
    "Alle Sender des Original-EPG "
    "werden übernommen."
)

print(
    "============================"
)


# ============================================================
# XMLTV ZEITSTEMPEL PARSEN
# ============================================================

def parse_xmltv_datetime(value):
    """
    XMLTV-Zeitstempel in timezone-aware datetime umwandeln.

    Beispiele:

    20260819120000 +0300
    20260819120000 +0200
    20260819120000

    Bei fehlendem Offset wird UTC angenommen.
    """

    if not value:
        return None

    value = value.strip()

    if len(value) < 14:
        return None

    try:

        naive_datetime = datetime.strptime(
            value[:14],
            "%Y%m%d%H%M%S"
        )

    except ValueError:

        return None


    offset_part = value[14:].strip()


    # --------------------------------------------------------
    # Zeitzonenoffset
    # --------------------------------------------------------

    if (
        len(offset_part) >= 5
        and offset_part[0] in ("+", "-")
        and offset_part[1:5].isdigit()
    ):

        sign = (
            1
            if offset_part[0] == "+"
            else -1
        )

        offset_hours = int(
            offset_part[1:3]
        )

        offset_minutes = int(
            offset_part[3:5]
        )

        offset = (
            timedelta(
                hours=offset_hours,
                minutes=offset_minutes
            )
            *
            sign
        )

        return naive_datetime.replace(
            tzinfo=timezone(offset)
        )


    # --------------------------------------------------------
    # Kein Offset:
    # als UTC behandeln
    # --------------------------------------------------------

    return naive_datetime.replace(
        tzinfo=timezone.utc
    )


# ============================================================
# PROGRAMME FILTERN
# ============================================================
#
# Alle Programme werden geprüft.
#
# Übernommen werden nur Programme, die das
# 24-Stunden-Fenster zumindest teilweise überschneiden.
#
# ============================================================

program_count = 0
skipped_programs = 0

programs_without_stop = 0


for programme in root.findall("programme"):

    # --------------------------------------------------------
    # CHANNEL-ID
    # --------------------------------------------------------
    #
    # Da ALLE Sender übernommen werden, gibt es hier
    # keine CHANNELS-Whitelist mehr.
    #
    channel_id = programme.get(
        "channel"
    )

    if not channel_id:

        skipped_programs += 1

        print(
            "WARNUNG: Programm ohne "
            "channel-ID übersprungen."
        )

        continue


    # --------------------------------------------------------
    # STARTZEIT
    # --------------------------------------------------------

    start = programme.get(
        "start"
    )

    if not start:

        skipped_programs += 1

        print(
            "WARNUNG: Programm ohne "
            "Startzeit übersprungen."
        )

        continue


    programme_start = (
        parse_xmltv_datetime(start)
    )

    if programme_start is None:

        print(
            "WARNUNG: Ungültiger "
            f"Startzeitpunkt übersprungen: {start}"
        )

        skipped_programs += 1

        continue


    # --------------------------------------------------------
    # START IN UTC
    # --------------------------------------------------------

    programme_start_utc = (
        programme_start.astimezone(
            timezone.utc
        )
    )


    # --------------------------------------------------------
    # STOPZEIT
    # --------------------------------------------------------

    stop = programme.get(
        "stop"
    )

    programme_stop_utc = None

    if stop:

        programme_stop = (
            parse_xmltv_datetime(stop)
        )

        if programme_stop is not None:

            programme_stop_utc = (
                programme_stop.astimezone(
                    timezone.utc
                )
            )


    # --------------------------------------------------------
    # Kein Stop vorhanden
    # --------------------------------------------------------

    if programme_stop_utc is None:

        programs_without_stop += 1


    # ========================================================
    # ZEITFENSTER-ÜBERSCHNEIDUNG
    # ========================================================
    #
    # Ein Programm wird übernommen, wenn es das
    # 24-Stunden-Fenster zumindest teilweise überschneidet.
    #
    # Mit Start + Stop:
    #
    #     stop <= window_start
    #     oder
    #     start >= window_end
    #
    # bedeutet:
    #
    #     keine Überschneidung
    #
    # ========================================================

    if programme_stop_utc is not None:

        if (
            programme_stop_utc <= window_start
            or
            programme_start_utc >= window_end
        ):

            continue

    else:

        if not (
            window_start
            <= programme_start_utc
            <
            window_end
        ):

            continue


    # --------------------------------------------------------
    # Programm übernehmen
    # --------------------------------------------------------

    new_root.append(
        programme
    )

    program_count += 1


filter_time = (
    time.perf_counter() -
    filter_start
)


# ============================================================
# PROGRAMM-KONTROLLE
# ============================================================

print("")
print(
    "========== PROGRAMME =========="
)

print(
    f"Übernommene Programme: "
    f"{program_count}"
)

print(
    f"Übersprungene Programme: "
    f"{skipped_programs}"
)

if programs_without_stop:

    print(
        f"Programme ohne Stopzeit: "
        f"{programs_without_stop}"
    )

print(
    "==============================="
)


# ============================================================
# XML SCHREIBEN
# ============================================================

write_start = time.perf_counter()

tree = ET.ElementTree(
    new_root
)

tree.write(
    OUTPUT_FILE,
    encoding="UTF-8",
    xml_declaration=True
)

write_time = (
    time.perf_counter() -
    write_start
)


# ============================================================
# DATEIGRÖSSE
# ============================================================

size = os.path.getsize(
    OUTPUT_FILE
)

size_mb = (
    size /
    1_000_000
)


# ============================================================
# AUSGABEDATEI KONTROLLE
# ============================================================

print("")
print(
    "========== EPG KONTROLLE =========="
)

print(
    f"Sender:             "
    f"{channel_count}"
)

print(
    f"Programme:          "
    f"{program_count}"
)

if skipped_programs:

    print(
        f"Übersprungene:      "
        f"{skipped_programs}"
    )

print(
    f"Originalgröße:      "
    f"{len(data) / 1_000_000:.2f} MB"
)

print(
    f"Neue EPG-Größe:     "
    f"{size_mb:.3f} MB"
)

print(
    f"Maximal erlaubt:    "
    f"{MAX_OUTPUT_SIZE / 1_000_000:.2f} MB"
)

print(
    f"Ausgabedatei:       "
    f"{OUTPUT_FILE}"
)

print(
    f"XML Filterung:      "
    f"{filter_time:.2f} Sekunden"
)

print(
    f"XML Schreiben:      "
    f"{write_time:.2f} Sekunden"
)

print(
    "====================================="
)


# ============================================================
# DATEIGRÖSSEN-KONTROLLE
# ============================================================

if size > MAX_OUTPUT_SIZE:

    print("")
    print(
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    )

    print(
        "FEHLER: EPG-DATEI IST ZU GROSS!"
    )

    print(
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    )

    print("")

    print(
        f"Dateigröße:       "
        f"{size_mb:.3f} MB"
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
        "EPG-Datei überschreitet "
        "das Limit von 4,90 MB."
    )


# ============================================================
# GESAMTZEIT
# ============================================================

total_time = (
    time.perf_counter() -
    total_start
)


# ============================================================
# ERFOLGREICH
# ============================================================

print("")
print(
    "EPG-Kontrolle erfolgreich."
)

print(
    "Die EPG wird veröffentlicht."
)

print(
    f"Sender: "
    f"{channel_count}"
)

print(
    f"Programme: "
    f"{program_count}"
)

print(
    f"Neue EPG-Größe: "
    f"{size_mb:.3f} MB"
)

print(
    f"EPG-Fenster: "
    f"{window_start.strftime('%Y-%m-%d %H:%M')} UTC "
    f"bis "
    f"{window_end.strftime('%Y-%m-%d %H:%M')} UTC"
)

print("")

print(
    "========== ZEITMESSUNG =========="
)

print(
    f"Download:       "
    f"{download_time:.2f} Sekunden"
)

print(
    f"XML Parsing:    "
    f"{parse_time:.2f} Sekunden"
)

print(
    f"XML Filterung:  "
    f"{filter_time:.2f} Sekunden"
)

print(
    f"XML Schreiben:  "
    f"{write_time:.2f} Sekunden"
)

print(
    f"Gesamt:         "
    f"{total_time:.2f} Sekunden"
)

print(
    "================================="
)

print("")
print(
    f"Fertig: {OUTPUT_FILE}"
)
