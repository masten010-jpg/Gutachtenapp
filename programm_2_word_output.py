# programm_2_word_output.py
import os
import json
import re
from datetime import datetime, timedelta
from docxtpl import DocxTemplate
from programm_1_ki_input import KI_ANTWORT_ORDNER, BASE_DIR, VORLAGE_PFAD

AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")
JSON_START_MARKER = "JSON_START"
JSON_END_MARKER = "JSON_END"

def json_aus_ki_antwort_parsen(ki_text: str) -> dict:
    start_idx = ki_text.find(JSON_START_MARKER)
    end_idx = ki_text.find(JSON_END_MARKER)
    if start_idx == -1 or end_idx == -1:
        raise ValueError("JSON_START oder JSON_END nicht gefunden.")
    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()
    first_brace = json_roh.find("{")
    last_brace = json_roh.rfind("}")
    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
        raise ValueError("Kein gültiger JSON-Block in KI-Antwort.")
    json_clean = json_roh[first_brace:last_brace + 1]
    return json.loads(json_clean)

def euro_zu_float(text) -> float:
    if isinstance(text, (int, float)):
        return float(text)
    if not text:
        return 0.0
    t = str(text).replace("€", "").replace("EUR", "").replace("Euro", "").replace(" ", "")
    t = t.replace(".", "").replace(",", ".") if "," in t else t
    try:
        return float(t)
    except ValueError:
        return 0.0

def float_zu_euro(betrag: float) -> str:
    s = f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"

def extrahiere_platzhalter(vorlage_pfad):
    doc = DocxTemplate(vorlage_pfad)
    return doc.get_undeclared_template_variables()

def baue_totalschaden(daten, platzhalter):
    if "WIEDERBESCHAFFUNGSWERTAUFWAND" in platzhalter:
        wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", 0))
        restwert = euro_zu_float(daten.get("RESTWERT", 0))
        wiederbeschaffungsaufwand = wbw - restwert
        daten["WIEDERBESCHAFFUNGSWERTAUFWAND"] = float_zu_euro(wiederbeschaffungsaufwand)
    return daten

def daten_nachbearbeiten(daten, platzhalter):
    # Standardfelder ergänzen
    alle_keys = ["MANDANT_VORNAME", "MANDANT_NACHNAME", "MANDANT_NAME",
                 "MANDANT_STRASSE", "MANDANT_PLZ_ORT", "UNFALL_DATUM",
                 "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE",
                 "FAHRZEUGTYP", "KENNZEICHEN", "FAHRZEUG_KENNZEICHEN",
                 "POLIZEIAKTE_NUMMER", "SCHADENSNUMMER", "AKTENZEICHEN",
                 "SCHADENHERGANG", "REPARATURKOSTEN", "WERTMINDERUNG",
                 "KOSTENPAUSCHALE", "GUTACHTERKOSTEN", "KOSTENSUMME_X",
                 "FRIST_DATUM", "HEUTDATUM"]
    for k in alle_keys:
        daten.setdefault(k, "")

    # Totalschaden-Logik
    daten = baue_totalschaden(daten, platzhalter)

    # Nachbearbeitung von Geldfeldern
    geld_felder = ["REPARATURKOSTEN", "WERTMINDERUNG", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]
    gesamt = 0.0
    for feld in geld_felder:
        wert = euro_zu_float(daten.get(feld, 0))
        daten[feld] = float_zu_euro(wert)
        gesamt += wert
    daten["KOSTENSUMME_X"] = float_zu_euro(gesamt)

    jetzt = datetime.now()
    daten["FRIST_DATUM"] = (jetzt + timedelta(days=14)).strftime("%d.%m.%Y")
    daten["HEUTDATUM"] = jetzt.strftime("%d.%m.%Y")

    return daten

def word_aus_vorlage_erstellen(daten: dict, vorlage_pfad: str, ziel_pfad: str):
    doc = DocxTemplate(vorlage_pfad)
    # Nur Platzhalter einsetzen, die auch in der Vorlage existieren
    platzhalter = doc.get_undeclared_template_variables()
    daten_fuer_vorlage = {k: v for k, v in daten.items() if k in platzhalter}
    doc.render(daten_fuer_vorlage)
    os.makedirs(os.path.dirname(ziel_pfad), exist_ok=True)
    doc.save(ziel_pfad)

def ki_datei_verarbeiten(pfad_ki_txt: str, vorlage_pfad: str) -> str:
    with open(pfad_ki_txt, "r", encoding="utf-8") as f:
        ki_text = f.read()
    daten = json_aus_ki_antwort_parsen(ki_text)
    platzhalter = extrahiere_platzhalter(vorlage_pfad)
    daten = daten_nachbearbeiten(daten, platzhalter)

    basisname = os.path.splitext(os.path.basename(pfad_ki_txt))[0]
    datum_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    ausgabe_name = f"{basisname}_schreiben_{datum_str}.docx"
    ausgabe_pfad = os.path.join(AUSGANGS_ORDNER, ausgabe_name)

    word_aus_vorlage_erstellen(daten, vorlage_pfad, ausgabe_pfad)
    print(f"Fertiges Schreiben gespeichert: {ausgabe_pfad}")
    return ausgabe_pfad

def main(pfad_ki_txt: str = None, vorlage_pfad: str = VORLAGE_PFAD) -> str:
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)

    if pfad_ki_txt is None:
        # Suche neueste KI-Datei
        dateien = [os.path.join(KI_ANTWORT_ORDNER, f) for f in os.listdir(KI_ANTWORT_ORDNER) if f.endswith("_ki.txt")]
        if not dateien:
            raise FileNotFoundError("Keine KI-Datei gefunden.")
        pfad_ki_txt = max(dateien, key=os.path.getmtime)

    if not os.path.isfile(pfad_ki_txt):
        raise FileNotFoundError(f"KI-Datei existiert nicht: {pfad_ki_txt}")

    return ki_datei_verarbeiten(pfad_ki_txt, vorlage_pfad)

if __name__ == "__main__":
    main()
