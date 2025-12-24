# programm_2_word_output.py  # Kommentar: KI JSON -> Nachbearbeitung -> Word erzeugen

import os  # Kommentar: Pfade/Dateien
import json  # Kommentar: JSON parsing
from datetime import datetime, timedelta  # Kommentar: Datum/Fristen
from docxtpl import DocxTemplate  # Kommentar: DOCX Rendering
from programm_1_ki_input import KI_ANTWORT_ORDNER, BASE_DIR  # Kommentar: Ordnerpfade

AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # Kommentar: Output Ordner
JSON_START_MARKER = "JSON_START"  # Kommentar: JSON Start Marker
JSON_END_MARKER = "JSON_END"  # Kommentar: JSON End Marker

def json_aus_ki_antwort_parsen(ki_text: str) -> dict:  # Kommentar: JSON aus KI-Text extrahieren
    start_idx = ki_text.find(JSON_START_MARKER)  # Kommentar: Start suchen
    end_idx = ki_text.find(JSON_END_MARKER)  # Kommentar: Ende suchen
    if start_idx == -1 or end_idx == -1:  # Kommentar: Marker fehlt
        raise ValueError("JSON_START oder JSON_END nicht gefunden.")  # Kommentar: Fehler
    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()  # Kommentar: Bereich ausschneiden
    json_roh = json_roh.replace("```json", "").replace("```", "").strip()  # Kommentar: Codefences entfernen
    first_brace = json_roh.find("{")  # Kommentar: Erste Klammer
    last_brace = json_roh.rfind("}")  # Kommentar: Letzte Klammer
    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:  # Kommentar: Ungültig
        raise ValueError("Kein gültiger JSON-Block in KI-Antwort.")  # Kommentar: Fehler
    json_clean = json_roh[first_brace:last_brace + 1]  # Kommentar: JSON sauber ausschneiden
    json_clean = json_clean.replace(",\n}", "\n}").replace(",}", "}")  # Kommentar: Häufige KI-Kommafehler glätten
    return json.loads(json_clean)  # Kommentar: JSON parsen und zurückgeben

def euro_zu_float(text) -> float:  # Kommentar: Euro-String -> float robust
    if isinstance(text, (int, float)):  # Kommentar: Schon Zahl
        return float(text)  # Kommentar: Cast
    if not text:  # Kommentar: Leer
        return 0.0  # Kommentar: Null
    t = str(text)  # Kommentar: String
    t = t.replace("€", "").replace("EUR", "").replace("Euro", "")  # Kommentar: Währung entfernen
    t = t.replace("\u00a0", " ").strip()  # Kommentar: NBSP entfernen
    t = t.replace(" ", "")  # Kommentar: Spaces entfernen
    allowed = []  # Kommentar: Erlaubte Zeichen sammeln
    for ch in t:  # Kommentar: Iteration
        if ch.isdigit() or ch in [",", ".", "+", "-"]:  # Kommentar: erlaubte Zeichen
            allowed.append(ch)  # Kommentar: hinzufügen
    t = "".join(allowed)  # Kommentar: zusammensetzen
    if not t:  # Kommentar: leer
        return 0.0  # Kommentar: Null
    if "." in t and "," in t:  # Kommentar: Format 1.234,56
        t = t.replace(".", "").replace(",", ".")  # Kommentar: Tausenderpunkte raus, Komma -> Punkt
    elif "," in t:  # Kommentar: Format 1234,56
        t = t.replace(",", ".")  # Kommentar: Komma -> Punkt
    try:  # Kommentar: Parse versuchen
        return float(t)  # Kommentar: Return float
    except ValueError:  # Kommentar: Fehler
        return 0.0  # Kommentar: Fallback

def float_zu_euro(betrag: float) -> str:  # Kommentar: float -> deutsches Euroformat
    s = f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # Kommentar: Format
    return s + " €"  # Kommentar: Eurozeichen

def daten_defaults(daten: dict) -> dict:  # Kommentar: Defaults für erwartete Keys
    keys = [  # Kommentar: Liste aller wichtigen Keys
        "MANDANT_VORNAME", "MANDANT_NACHNAME", "MANDANT_NAME",  # Kommentar: Mandant
        "MANDANT_STRASSE", "MANDANT_PLZ_ORT",  # Kommentar: Adresse
        "UNFALL_DATUM", "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE",  # Kommentar: Unfall
        "FAHRZEUGTYP", "KENNZEICHEN", "FAHRZEUG_KENNZEICHEN",  # Kommentar: Fahrzeug
        "POLIZEIAKTE_NUMMER", "SCHADENSNUMMER", "AKTENZEICHEN",  # Kommentar: Akten
        "SCHADENHERGANG",  # Kommentar: Text
        "REPARATURKOSTEN", "WERTMINDERUNG", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN",  # Kommentar: Kosten
        "NUTZUNGSAUSFALL", "MWST_BETRAG",  # Kommentar: Nutzung/MwSt
        "WIEDERBESCHAFFUNGSWERT", "RESTWERT",  # Kommentar: Totalschaden
        "FRIST_DATUM", "HEUTDATUM",  # Kommentar: System
        "ABRECHNUNGSART", "STEUERSTATUS",  # Kommentar: Auswahl
        "VORSTEUERBERECHTIGUNG",  # Kommentar: Textvariable für Word
        "ZUSATZKOSTEN_BEZEICHNUNG", "ZUSATZKOSTEN_BETRAG",  # Kommentar: Optional
        "WIEDERBESCHAFFUNGSAUFWAND",  # Kommentar: WBW - Restwert
        "KOSTENSUMME_X", "GESAMTSUMME",  # Kommentar: Summen
    ]  # Kommentar: Ende keys
    for k in keys:  # Kommentar: Iteration
        daten.setdefault(k, "")  # Kommentar: Default setzen
    return daten  # Kommentar: Return

def setze_vorsteuer_text(daten: dict, steuerstatus: str) -> dict:  # Kommentar: VORSTEUERBERECHTIGUNG als Text setzen
    daten["STEUERSTATUS"] = steuerstatus  # Kommentar: speichern
    if steuerstatus == "vorsteuerabzugsberechtigt":  # Kommentar: Vorsteuer-Fall
        daten["VORSTEUERBERECHTIGUNG"] = "vorsteuerberechtigt"  # Kommentar: gewünschter Text
    else:  # Kommentar: Nicht-Vorsteuer-Fall
        daten["VORSTEUERBERECHTIGUNG"] = "nicht vorsteuerberechtigt"  # Kommentar: gewünschter Text
    return daten  # Kommentar: Return

def mwst_leeren_wenn_noetig(daten: dict, auswahl: str, steuerstatus: str) -> dict:  # Kommentar: MWST_BETRAG leeren wenn irrelevant
    norm = (auswahl or "").lower()  # Kommentar: normalize
    is_fiktiv = "fiktive abrechnung" in norm  # Kommentar: fiktiv?
    if is_fiktiv:  # Kommentar: fiktiv => keine MwSt
        daten["MWST_BETRAG"] = ""  # Kommentar: leer
        return daten  # Kommentar: Return
    if steuerstatus == "vorsteuerabzugsberechtigt":  # Kommentar: Vorsteuer => MwSt nicht fordern
        daten["MWST_BETRAG"] = ""  # Kommentar: leer
        return daten  # Kommentar: Return
    return daten  # Kommentar: sonst unverändert

def berechne_summen(daten: dict, auswahl: str) -> dict:  # Kommentar: Summen bilden und Geld formatieren
    norm = (auswahl or "").lower()  # Kommentar: normalize
    is_totalschaden = "totalschaden" in norm  # Kommentar: totalschaden?
    reparatur = euro_zu_float(daten.get("REPARATURKOSTEN", ""))  # Kommentar: reparatur
    wertminderung = euro_zu_float(daten.get("WERTMINDERUNG", ""))  # Kommentar: wertminderung
    kostenpausch = euro_zu_float(daten.get("KOSTENPAUSCHALE", ""))  # Kommentar: kostenpausch
    gutachter = euro_zu_float(daten.get("GUTACHTERKOSTEN", ""))  # Kommentar: gutachter
    nutzung = euro_zu_float(daten.get("NUTZUNGSAUSFALL", ""))  # Kommentar: nutzungsausfall (wenn Betrag)
    mwst = euro_zu_float(daten.get("MWST_BETRAG", ""))  # Kommentar: mwst
    zusatz = euro_zu_float(daten.get("ZUSATZKOSTEN_BETRAG", ""))  # Kommentar: zusatzkosten
    wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))  # Kommentar: wbw
    restwert = euro_zu_float(daten.get("RESTWERT", ""))  # Kommentar: restwert

    if is_totalschaden:  # Kommentar: Totalschaden-Logik
        wba = max(wbw - restwert, 0.0)  # Kommentar: WBW - Restwert
        daten["WIEDERBESCHAFFUNGSAUFWAND"] = float_zu_euro(wba) if wba > 0 else ""  # Kommentar: format
        daten["REPARATURKOSTEN"] = ""  # Kommentar: Reparaturkosten leer im Totalschaden (wie üblich)
        reparatur = 0.0  # Kommentar: Für Summen nullen

    kosten_x = reparatur + wertminderung + kostenpausch + gutachter  # Kommentar: KOSTENSUMME_X
    gesamt = kosten_x + nutzung + zusatz + mwst  # Kommentar: Gesamtsumme inkl MwSt (wenn vorhanden)

    daten["REPARATURKOSTEN"] = float_zu_euro(reparatur) if reparatur > 0 else daten.get("REPARATURKOSTEN", "")  # Kommentar: format
    daten["WERTMINDERUNG"] = float_zu_euro(wertminderung) if wertminderung > 0 else daten.get("WERTMINDERUNG", "")  # Kommentar: format
    daten["KOSTENPAUSCHALE"] = float_zu_euro(kostenpausch) if kostenpausch > 0 else daten.get("KOSTENPAUSCHALE", "")  # Kommentar: format
    daten["GUTACHTERKOSTEN"] = float_zu_euro(gutachter) if gutachter > 0 else daten.get("GUTACHTERKOSTEN", "")  # Kommentar: format
    daten["NUTZUNGSAUSFALL"] = float_zu_euro(nutzung) if nutzung > 0 else daten.get("NUTZUNGSAUSFALL", "")  # Kommentar: format
    daten["MWST_BETRAG"] = float_zu_euro(mwst) if mwst > 0 else daten.get("MWST_BETRAG", "")  # Kommentar: format/leer lassen
    daten["ZUSATZKOSTEN_BETRAG"] = float_zu_euro(zusatz) if zusatz > 0 else daten.get("ZUSATZKOSTEN_BETRAG", "")  # Kommentar: format
    daten["KOSTENSUMME_X"] = float_zu_euro(kosten_x) if kosten_x > 0 else ""  # Kommentar: format
    daten["GESAMTSUMME"] = float_zu_euro(gesamt) if gesamt > 0 else ""  # Kommentar: format

    return daten  # Kommentar: Return

def daten_nachbearbeiten(daten: dict, auswahl: str, steuerstatus: str, zus_bez: str, zus_betrag: str) -> dict:  # Kommentar: zentrale Nachbearbeitung
    daten = daten_defaults(daten)  # Kommentar: defaults
    daten["ABRECHNUNGSART"] = auswahl  # Kommentar: speichern
    daten["ZUSATZKOSTEN_BEZEICHNUNG"] = (zus_bez or "").strip()  # Kommentar: speichern
    daten["ZUSATZKOSTEN_BETRAG"] = (zus_betrag or "").strip()  # Kommentar: speichern
    jetzt = datetime.now()  # Kommentar: now
    daten["HEUTDATUM"] = jetzt.strftime("%d.%m.%Y")  # Kommentar: setzen
    daten["FRIST_DATUM"] = (jetzt + timedelta(days=14)).strftime("%d.%m.%Y")  # Kommentar: setzen
    daten = setze_vorsteuer_text(daten, steuerstatus)  # Kommentar: Textvariable setzen
    daten = mwst_leeren_wenn_noetig(daten, auswahl, steuerstatus)  # Kommentar: MWST ggf leeren
    daten = berechne_summen(daten, auswahl)  # Kommentar: Summen/Format
    return daten  # Kommentar: Return

def word_aus_vorlage_erstellen(daten: dict, vorlage_pfad: str, ziel_pfad: str) -> None:  # Kommentar: DOCX erzeugen
    doc = DocxTemplate(vorlage_pfad)  # Kommentar: Vorlage laden
    os.makedirs(os.path.dirname(ziel_pfad), exist_ok=True)  # Kommentar: Zielordner sicher
    doc.render(daten)  # Kommentar: Render (alle Variablen, kein Filter)
    doc.save(ziel_pfad)  # Kommentar: speichern

def generate_from_data(daten: dict, vorlage_pfad: str, auswahl: str, steuerstatus: str, zus_bez: str = "", zus_betrag: str = "") -> str:  # Kommentar: DOCX direkt aus Daten erzeugen
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: ordner sicherstellen
    daten = daten_nachbearbeiten(daten, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: nachbearbeiten
    datum_str = datetime.now().strftime("%Y%m%d_%H%M%S")  # Kommentar: timestamp
    ausgabe_name = f"korrigiert_schreiben_{datum_str}.docx"  # Kommentar: name
    ausgabe_pfad = os.path.join(AUSGANGS_ORDNER, ausgabe_name)  # Kommentar: pfad
    word_aus_vorlage_erstellen(daten, vorlage_pfad, ausgabe_pfad)  # Kommentar: erstellen
    return ausgabe_pfad  # Kommentar: return

def ki_datei_verarbeiten(pfad_ki_txt: str, vorlage_pfad: str, auswahl: str, steuerstatus: str, zus_bez: str, zus_betrag: str) -> str:  # Kommentar: KI-Datei -> DOCX
    with open(pfad_ki_txt, "r", encoding="utf-8") as f:  # Kommentar: open
        ki_text = f.read()  # Kommentar: read
    daten = json_aus_ki_antwort_parsen(ki_text)  # Kommentar: parse
    return generate_from_data(daten, vorlage_pfad, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: weiter

def main(pfad_ki_txt: str = None, vorlage_pfad: str | None = None, auswahl: str = "", steuerstatus: str = "", zus_bez: str = "", zus_betrag: str = "") -> str:  # Kommentar: Kompatibler Main
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: ordner
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: ordner
    if vorlage_pfad is None:  # Kommentar: vorlage fehlt
        raise ValueError("vorlage_pfad muss übergeben werden (Word-Vorlage .docx).")  # Kommentar: error
    if pfad_ki_txt is None:  # Kommentar: keine KI-Datei angegeben
        dateien = [os.path.join(KI_ANTWORT_ORDNER, f) for f in os.listdir(KI_ANTWORT_ORDNER) if f.endswith("_ki.txt")]  # Kommentar: liste
        if not dateien:  # Kommentar: none
            raise FileNotFoundError("Keine KI-Datei gefunden.")  # Kommentar: error
        pfad_ki_txt = max(dateien, key=os.path.getmtime)  # Kommentar: neueste
    if not os.path.isfile(pfad_ki_txt):  # Kommentar: exists?
        raise FileNotFoundError(f"KI-Datei existiert nicht: {pfad_ki_txt}")  # Kommentar: error
    if not os.path.isfile(vorlage_pfad):  # Kommentar: exists?
        raise FileNotFoundError(f"Vorlage existiert nicht: {vorlage_pfad}")  # Kommentar: error
    return ki_datei_verarbeiten(pfad_ki_txt, vorlage_pfad, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: run

if __name__ == "__main__":  # Kommentar: direct run
    main()  # Kommentar: run
