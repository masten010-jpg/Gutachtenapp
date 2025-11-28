# programm_2_word_output.py
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

    # KI kann sowas schreiben wie:
    # JSON_START
    # ```json
    # { ... }
    # ```
    # JSON_END
    # → wir extrahieren nur den Teil zwischen der ersten und letzten Klammer
    first_brace = json_roh.find("{")
    last_brace = json_roh.rfind("}")

    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
        raise ValueError(
            "Kein gültiger JSON-Block ({}-Klammern) in KI-Antwort gefunden.\n"
            f"Auszug: {json_roh[:300]}"
        )

    json_clean = json_roh[first_brace:last_brace + 1]

    try:
        daten = json.loads(json_clean)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON konnte nicht geparst werden: {e}\nAuszug: {json_clean[:500]}"
        ) from e

    return daten


import re

def euro_zu_float(text: str) -> float:
    if not text:
        return 0.0

    t = text.strip()
    # Erste Zahl im Text finden (inkl. Tausenderpunkt und Komma)
    match = re.search(r'-?[\d\.\,]+', t)
    if not match:
        return 0.0

    number_str = match.group(0)

    # Tausenderpunkte entfernen, Komma in Punkt umwandeln
    number_str = number_str.replace("€", "").replace("EUR", "").strip()
    number_str = number_str.replace(".", "").replace(",", ".")

    try:
        return float(number_str)
    except ValueError:
        return 0.0



def float_zu_euro(betrag: float) -> str:
    s = f"{betrag:,.2f}"   # '6,580.00'
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"


def baue_standard_schadenhergang(daten: dict) -> str:
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
    alle_keys = [
        "MANDANT_VORNAME", "MANDANT_NACHNAME", "MANDANT_NAME",
        "MANDANT_STRASSE", "MANDANT_PLZ_ORT",
        "UNFALL_DATUM", "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE",
        "FAHRZEUGTYP", "KENNZEICHEN", "FAHRZEUG_KENNZEICHEN",
        "POLIZEIAKTE_NUMMER", "SCHADENSNUMMER", "AKTENZEICHEN",
        "SCHADENHERGANG",
        "REPARATURKOSTEN", "WERTMINDERUNG", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN",
        "KOSTENSUMME_X",
        "FRIST_DATUM", "HEUTDATUM",
    ]
    for k in alle_keys:
        daten.setdefault(k, "")

    text_felder_mit_fallback = [
        "MANDANT_VORNAME", "MANDANT_NACHNAME", "MANDANT_NAME",
        "MANDANT_STRASSE", "MANDANT_PLZ_ORT",
        "UNFALL_DATUM", "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE",
        "FAHRZEUGTYP", "KENNZEICHEN",
        "POLIZEIAKTE_NUMMER", "SCHADENSNUMMER", "AKTENZEICHEN",
    ]
    for feld in text_felder_mit_fallback:
        if not (daten.get(feld) or "").strip():
            daten[feld] = "nicht bekannt"

    if not (daten.get("FAHRZEUG_KENNZEICHEN") or "").strip():
        daten["FAHRZEUG_KENNZEICHEN"] = daten.get("KENNZEICHEN", "nicht bekannt")

    geld_felder = ["REPARATURKOSTEN", "WERTMINDERUNG", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]
    geld_werte = {}
    for feld in geld_felder:
        roh = (daten.get(feld) or "").strip()
        betrag = euro_zu_float(roh)
        geld_werte[feld] = betrag
        daten[feld] = float_zu_euro(betrag)

    gesamt = sum(geld_werte.values())
    daten["KOSTENSUMME_X"] = float_zu_euro(gesamt)
    daten["GESAMTSUMME"] = daten["KOSTENSUMME_X"]

    jetzt = datetime.now()
    frist = jetzt + timedelta(days=14)
    daten["FRIST_DATUM"] = frist.strftime("%d.%m.%Y")
    daten["HEUTDATUM"] = jetzt.strftime("%d.%m.%Y")

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
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)

    if pfad_ki_txt is None:
        pfad_ki_txt = neueste_ki_datei_finden()
        if pfad_ki_txt is None:
            return None

    if not os.path.isfile(pfad_ki_txt):
        raise FileNotFoundError(f"Angegebene KI-Datei existiert nicht: {pfad_ki_txt}")

    return ki_datei_verarbeiten(pfad_ki_txt)


if __name__ == "__main__":
    main()

