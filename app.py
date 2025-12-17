# programm_2_word_output.py
import os
import json
from datetime import datetime, timedelta
from docxtpl import DocxTemplate

import config
from programm_1_ki_input import KI_ANTWORT_ORDNER, BASE_DIR  # deine Namen bleiben wie gehabt

AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")
JSON_START_MARKER = "JSON_START"
JSON_END_MARKER = "JSON_END"


def json_aus_ki_antwort_parsen(ki_text: str) -> dict:
    """
    Erwartet JSON zwischen JSON_START und JSON_END.
    Robust gegen Codefences/zusätzlichen Text, solange Marker vorhanden sind.
    """
    start_idx = ki_text.find(JSON_START_MARKER)
    end_idx = ki_text.find(JSON_END_MARKER)

    if start_idx == -1 or end_idx == -1:
        raise ValueError("JSON_START oder JSON_END nicht gefunden.")

    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()

    # Falls die KI ```json ... ``` drumrum packt: entfernen
    json_roh = json_roh.replace("```json", "").replace("```JSON", "").replace("```", "").strip()

    first_brace = json_roh.find("{")
    last_brace = json_roh.rfind("}")
    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
        raise ValueError("Kein gültiger JSON-Block in KI-Antwort.")

    json_clean = json_roh[first_brace:last_brace + 1]

    try:
        return json.loads(json_clean)
    except json.JSONDecodeError as e:
        # Letzter Rettungsanker: häufige KI-Fehler entschärfen
        # (z.B. trailing commas)
        json_clean2 = json_clean.replace(",\n}", "\n}").replace(",}", "}")
        return json.loads(json_clean2)


def euro_zu_float(text) -> float:
    """
    Konvertiert typische deutsche/englische Geldformate in float.
    Beispiele:
      "1.234,56 €" -> 1234.56
      "1234,56"    -> 1234.56
      "1234.56"    -> 1234.56
      "" / None    -> 0.0
    """
    if isinstance(text, (int, float)):
        return float(text)

    if not text:
        return 0.0

    t = str(text)
    t = t.replace("€", "").replace("EUR", "").replace("Euro", "")
    t = t.replace("\u00a0", " ").strip()  # NBSP
    t = t.replace(" ", "")

    # Nur Ziffern/.,- behalten (Minus/Komma/Punkt)
    # (Alles andere raus, z.B. "netto", "brutto", etc.)
    cleaned = []
    for ch in t:
        if ch.isdigit() or ch in [".", ",", "-", "+"]:
            cleaned.append(ch)
    t = "".join(cleaned)

    if not t:
        return 0.0

    # Heuristik:
    # - Wenn sowohl '.' als auch ',' vorkommen: '.' = Tausender, ',' = Dezimal
    # - Wenn nur ',' vorkommt: ',' = Dezimal
    # - Wenn nur '.' vorkommt: '.' = Dezimal
    if "." in t and "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    # else: '.' bleibt als Dezimalpunkt

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
    # Nur wenn die Vorlage den Platzhalter wirklich hat, berechnen wir ihn
    if "WIEDERBESCHAFFUNGSWERTAUFWAND" in platzhalter:
        wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", 0))
        restwert = euro_zu_float(daten.get("RESTWERT", 0))
        wiederbeschaffungsaufwand = wbw - restwert
        daten["WIEDERBESCHAFFUNGSWERTAUFWAND"] = float_zu_euro(wiederbeschaffungsaufwand)
    return daten


def daten_nachbearbeiten(daten, platzhalter):
    # Standardfelder ergänzen (deine Keys bleiben exakt wie in deinem Prompt)
    alle_keys = [
        "MANDANT_VORNAME", "MANDANT_NACHNAME", "MANDANT_NAME",
        "MANDANT_STRASSE", "MANDANT_PLZ_ORT", "UNFALL_DATUM",
        "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE",
        "FAHRZEUGTYP", "KENNZEICHEN", "FAHRZEUG_KENNZEICHEN",
        "POLIZEIAKTE_NUMMER", "SCHADENSNUMMER", "AKTENZEICHEN",
        "SCHADENHERGANG", "REPARATURKOSTEN", "WERTMINDERUNG",
        "KOSTENPAUSCHALE", "GUTACHTERKOSTEN", "KOSTENSUMME_X",
        "FRIST_DATUM", "HEUTDATUM"
    ]
    for k in alle_keys:
        daten.setdefault(k, "")

    # Totalschaden-Logik (nur wenn Platzhalter existiert)
    daten = baue_totalschaden(daten, platzhalter)

    # Geldfelder formatieren + Summe rechnen
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


def main(pfad_ki_txt: str = None, vorlage_pfad: str = None) -> str:
    # Ordner wie gehabt sicherstellen
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)

    # Vorlage MUSS von app.py übergeben werden (damit die Auswahl wirkt)
    if vorlage_pfad is None:
        raise ValueError("vorlage_pfad muss übergeben werden (Word-Vorlage .docx).")

    if pfad_ki_txt is None:
        # Suche neueste KI-Datei
        dateien = [
            os.path.join(KI_ANTWORT_ORDNER, f)
            for f in os.listdir(KI_ANTWORT_ORDNER)
            if f.endswith("_ki.txt")
        ]
        if not dateien:
            raise FileNotFoundError("Keine KI-Datei gefunden.")
        pfad_ki_txt = max(dateien, key=os.path.getmtime)

    if not os.path.isfile(pfad_ki_txt):
        raise FileNotFoundError(f"KI-Datei existiert nicht: {pfad_ki_txt}")

    if not os.path.isfile(vorlage_pfad):
        raise FileNotFoundError(f"Vorlage existiert nicht: {vorlage_pfad}")

    return ki_datei_verarbeiten(pfad_ki_txt, vorlage_pfad)


if __name__ == "__main__":
    main()
