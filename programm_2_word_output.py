# programm_2_word_output.py
# Aufgabe:
# - Eine KI-Antwort-Textdatei mit JSON-Block verarbeiten
# - JSON-Daten nachbearbeiten (KOSTENSUMME_X, FRIST_DATUM, SCHADENHERGANG, etc.)
# - Word-Vorlage füllen
# - Pfad zur erzeugten .docx zurückgeben

import os
import json
from datetime import datetime, timedelta
from docxtpl import DocxTemplate

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

KI_ANTWORT_ORDNER = os.path.join(BASE_DIR, "ki_antworten")
AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")
VORLAGE_PFAD = os.path.join(BASE_DIR, "vorlage_schreiben.docx")

JSON_START_MARKER = "JSON_START"
JSON_END_MARKER = "JSON_END"


def json_aus_ki_antwort_parsen(ki_text: str) -> dict:
    start_idx = ki_text.find(JSON_START_MARKER)
    end_idx = ki_text.find(JSON_END_MARKER)

    if start_idx == -1 or end_idx == -1:
        raise ValueError("JSON_START oder JSON_END nicht gefunden in KI-Antwort.")

    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()
    json_roh = json_roh.strip("` \n")

    try:
        daten = json.loads(json_roh)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON konnte nicht geparst werden: {e}\nAuszug: {json_roh[:500]}"
        ) from e

    return daten


def euro_zu_float(text: str) -> float:
    if not text:
        return 0.0
    t = text.strip()
    t = t.replace("€", "").replace("EUR", "").strip()
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return 0.0


def float_zu_euro(betrag: float) -> str:
    s = f"{betrag:,.2f}"   # '6,580.00'
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"


def baue_standard_schadenhergang(daten: dict) -> str:
    """
    Neutraler Fallback-Schadenhergang, falls das Feld komplett leer ist.
    """
    datum = (daten.get("UNFALL_DATUM") or "").strip()
    ort = (daten.get("UNFALLORT") or "").strip()
    strasse = (daten.get("UNFALL_STRASSE") or "").strip()

    if datum:
        s1 = f"Am {datum} ereignete sich"
    else:
        s1 = "Es ereignete sich"

    if ort and strasse:
        s1 += f" in {ort}, {strasse} ein Verkehrsunfall, an dem unser Mandant beteiligt war."
    elif ort:
        s1 += f" in {ort} ein Verkehrsunfall, an dem unser Mandant beteiligt war."
    elif strasse:
        s1 += f" in der {strasse} ein Verkehrsunfall, an dem unser Mandant beteiligt war."
    else:
        s1 += " ein Verkehrsunfall, an dem unser Mandant beteiligt war."

    s2 = (
        "Die näheren Umstände des Schadenhergangs ergeben sich aus dem beigefügten "
        "Kfz-Schadengutachten."
    )
    s3 = (
        "Zur Vermeidung von Wiederholungen nehmen wir auf die dortigen Ausführungen "
        "vollumfänglich Bezug."
    )

    return " ".join([s1, s2, s3])


def daten_nachbearbeiten(daten: dict) -> dict:
    # SCHADENSNUMMER sicherstellen (falls KI-Feld fehlt oder leer ist)
    daten.setdefault("SCHADENSNUMMER", "")

    # SCHADENHERGANG-Feld sicherstellen
    daten.setdefault("SCHADENHERGANG", "")

    # Wichtige Unfall-Felder nicht blank lassen: Fallback "nicht bekannt"
    for feld in ["UNFALL_DATUM", "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE"]:
        if not daten.get(feld):
            daten[feld] = "nicht bekannt"

    # Falls FAHRZEUG_KENNZEICHEN nicht gesetzt ist, fallback auf KENNZEICHEN
    if not daten.get("FAHRZEUG_KENNZEICHEN"):
        daten["FAHRZEUG_KENNZEICHEN"] = daten.get("KENNZEICHEN", "")

    # KOSTENSUMME_X berechnen, falls leer
    if not daten.get("KOSTENSUMME_X"):
        rep = euro_zu_float(daten.get("REPARATURKOSTEN", ""))
        wm = euro_zu_float(daten.get("WERTMINDERUNG", ""))
        pausch = euro_zu_float(daten.get("KOSTENPAUSCHALE", ""))
        gut = euro_zu_float(daten.get("GUTACHTERKOSTEN", ""))

        gesamt = rep + wm + pausch + gut
        daten["KOSTENSUMME_X"] = float_zu_euro(gesamt)

    # FRIST_DATUM = heute + 14 Tage (falls nicht von der KI gesetzt)
    if not daten.get("FRIST_DATUM"):
        frist = datetime.now() + timedelta(days=14)
        daten["FRIST_DATUM"] = frist.strftime("%d.%m.%Y")

    # SCHADENHERGANG: nur Fallback, wenn komplett leer
    sh = (daten.get("SCHADENHERGANG") or "").strip()
    if not sh:
        print("[WARNUNG] SCHADENHERGANG fehlt – Standardtext wird verwendet.")
        daten["SCHADENHERGANG"] = baue_standard_schadenhergang(daten)

    return daten


def word_aus_vorlage_erstellen(daten: dict, vorlage_pfad: str, ziel_pfad: str):
    if not os.path.isfile(vorlage_pfad):
        raise FileNotFoundError(f"Word-Vorlage nicht gefunden: {vorlage_pfad}")

    doc = DocxTemplate(vorlage_pfad)
    try:
        doc.render(daten)
    except Exception as e:
        raise RuntimeError(f"Fehler beim Rendern der Word-Vorlage: {e}")

    os.makedirs(os.path.dirname(ziel_pfad), exist_ok=True)
    doc.save(ziel_pfad)


def ki_datei_verarbeiten(pfad_ki_txt: str) -> str:
    print(f"Verarbeite KI-Antwort: {pfad_ki_txt}")

    with open(pfad_ki_txt, "r", encoding="utf-8") as f:
        ki_text = f.read()

    daten = json_aus_ki_antwort_parsen(ki_text)
    daten = daten_nachbearbeiten(daten)

    basisname = os.path.splitext(os.path.basename(pfad_ki_txt))[0]
    datum_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    ausgabe_name = f"{basisname}_schreiben_{datum_str}.docx"
    ausgabe_pfad = os.path.join(AUSGANGS_ORDNER, ausgabe_name)

    word_aus_vorlage_erstellen(daten, VORLAGE_PFAD, ausgabe_pfad)

    print(f"Fertiges Schreiben gespeichert: {ausgabe_pfad}")
    return ausgabe_pfad


def neueste_ki_datei_finden() -> str | None:
    if not os.path.isdir(KI_ANTWORT_ORDNER):
        print("KI-Antwort-Ordner existiert nicht.")
        return None

    dateien = [
        os.path.join(KI_ANTWORT_ORDNER, d)
        for d in os.listdir(KI_ANTWORT_ORDNER)
        if d.endswith("_ki.txt")
    ]

    if not dateien:
        print("Keine *_ki.txt-Dateien gefunden.")
        return None

    neueste = max(dateien, key=os.path.getmtime)
    print(f"Neueste KI-Datei: {neueste}")
    return neueste


def main(pfad_ki_txt: str | None = None) -> str | None:
    """
    Wenn pfad_ki_txt angegeben ist, wird GENAU diese KI-Antwort verarbeitet.
    Wenn nicht, wird die neueste *_ki.txt im Ordner verwendet.
    Gibt den Pfad der erzeugten .docx zurück.
    """
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)

    if pfad_ki_txt is None:
        pfad_ki_txt = neueste_ki_datei_finden()
        if pfad_ki_txt is None:
            return None

    if not os.path.isfile(pfad_ki_txt):
        raise FileNotFoundError(f"Angegebene KI-Datei existiert nicht: {pfad_ki_txt}")

    docx_pfad = ki_datei_verarbeiten(pfad_ki_txt)
    return docx_pfad


if __name__ == "__main__":
    main()
