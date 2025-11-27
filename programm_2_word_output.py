# programm_2_word_output.py
# Aufgabe:
# - Alle *_ki.txt in "ki_antworten" verarbeiten
# - JSON-Block extrahieren
# - Daten nachbearbeiten (Kennzeichen-Fallback, Kostensumme X)
# - Word-Vorlage füllen
# - fertige Datei in "ausgang_schreiben" speichern

import os
import json
from datetime import datetime
from docxtpl import DocxTemplate

# -------------------------
# BASISPFAD & ORDNER
# -------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

KI_ANTWORT_ORDNER = os.path.join(BASE_DIR, "ki_antworten")
AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")
VORLAGE_PFAD = os.path.join(BASE_DIR, "vorlage_schreiben.docx")

JSON_START_MARKER = "JSON_START"
JSON_END_MARKER = "JSON_END"


# -------------------------
# HILFSFUNKTIONEN
# -------------------------

def json_aus_ki_antwort_parsen(ki_text: str) -> dict:
    """
    Sucht in der KI-Antwort nach dem Bereich zwischen JSON_START und JSON_END
    und parst diesen Bereich als JSON in ein Python-Dict.
    """
    start_idx = ki_text.find(JSON_START_MARKER)
    end_idx = ki_text.find(JSON_END_MARKER)

    if start_idx == -1 or end_idx == -1:
        raise ValueError("JSON_START oder JSON_END nicht gefunden. KI-Ausgabe prüfen.")

    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()
    json_roh = json_roh.strip("` \n")

    daten = json.loads(json_roh)
    return daten


def euro_zu_float(text: str) -> float:
    """
    Wandelt einen Euro-String wie '5.200,00 €' in eine Zahl (float) um.
    Wenn nichts Sinnvolles drinsteht, wird 0.0 zurückgegeben.
    """
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
    """
    Wandelt eine Zahl (float) zurück in ein deutsches Euro-Format,
    z.B. 6580.0 -> '6.580,00 €'
    """
    s = f"{betrag:,.2f}"   # z.B. '6,580.00'
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"


def daten_nachbearbeiten(daten: dict) -> dict:
    """
    Ergänzt / korrigiert Felder nach der KI:
    - FAHRZEUG_KENNZEICHEN setzen, falls leer -> KENNZEICHEN verwenden
    - KOSTENSUMME_X berechnen, falls leer
    """
    if not daten.get("FAHRZEUG_KENNZEICHEN"):
        daten["FAHRZEUG_KENNZEICHEN"] = daten.get("KENNZEICHEN", "")

    if not daten.get("KOSTENSUMME_X"):
        rep = euro_zu_float(daten.get("REPARATURKOSTEN", ""))
        wm = euro_zu_float(daten.get("WERTMINDERUNG", ""))
        pausch = euro_zu_float(daten.get("KOSTENPAUSCHALE", ""))
        gut = euro_zu_float(daten.get("GUTACHTERKOSTEN", ""))

        gesamt = rep + wm + pausch + gut
        daten["KOSTENSUMME_X"] = float_zu_euro(gesamt)

    return daten


def word_aus_vorlage_erstellen(daten: dict, vorlage_pfad: str, ziel_pfad: str):
    """
    Füllt die Word-Vorlage mit den Werten aus 'daten'.
    Die Keys im Dict müssen den Platzhaltern im Word entsprechen.
    Beispiel:
      daten["KENNZEICHEN"] -> {{KENNZEICHEN}} in der Vorlage.
    """
    doc = DocxTemplate(vorlage_pfad)
    doc.render(daten)
    doc.save(ziel_pfad)


def ki_datei_verarbeiten(pfad_ki_txt: str):
    """
    Verarbeitet EINE KI-Antwort:
    - KI-Text lesen
    - JSON-Daten extrahieren
    - Daten nachbearbeiten
    - Word-Dokument erstellen
    """
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


# -------------------------
# MAIN
# -------------------------

def main(pfad_ki_txt=None):
    """
    Wenn pfad_ki_txt angegeben ist, wird NUR diese eine KI-Antwort verarbeitet.
    Wenn nicht, werden wie bisher alle *_ki.txt im Ordner verarbeitet.
    """
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)

    # Fall 1: App hat eine konkrete KI-Datei übergeben
    if pfad_ki_txt is not None:
        if not os.path.isfile(pfad_ki_txt):
            print(f"Angegebene KI-Datei existiert nicht: {pfad_ki_txt}")
            return

        try:
            ki_datei_verarbeiten(pfad_ki_txt)
        except Exception as e:
            print(f"FEHLER bei {pfad_ki_txt}: {e}")
        return

    # Fall 2: Standard – alle *_ki.txt im Ordner verarbeiten
    print("Suche KI-Antworten in:", KI_ANTWORT_ORDNER)
    dateien = os.listdir(KI_ANTWORT_ORDNER)
    ki_files = [d for d in dateien if d.endswith("_ki.txt")]

    if not ki_files:
        print("Keine *_ki.txt-Dateien gefunden. Erst Programm 1 ausführen.")
        return

    for datei in ki_files:
        pfad = os.path.join(KI_ANTWORT_ORDNER, datei)
        try:
            ki_datei_verarbeiten(pfad)
        except Exception as e:
            print(f"FEHLER bei {pfad}: {e}")

    print("Alle KI-Antworten verarbeitet.")



if __name__ == "__main__":
    main()

