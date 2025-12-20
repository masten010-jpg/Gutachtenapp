# programm_2_word_output.py  # Kommentar: Programm 2 (KI-JSON -> Korrekturen/Logik -> Word)

import os  # Kommentar: OS-Funktionen importieren
import json  # Kommentar: JSON importieren
from datetime import datetime, timedelta  # Kommentar: Datum/Zeit importieren
from docxtpl import DocxTemplate  # Kommentar: DocxTemplate importieren
from programm_1_ki_input import KI_ANTWORT_ORDNER, BASE_DIR  # Kommentar: Pfade aus Programm 1 übernehmen

AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # Kommentar: Ausgangsordner definieren
JSON_START_MARKER = "JSON_START"  # Kommentar: Startmarker
JSON_END_MARKER = "JSON_END"  # Kommentar: Endmarker


def json_aus_ki_antwort_parsen(ki_text: str) -> dict:  # Kommentar: JSON-Block aus KI-Text extrahieren
    start_idx = ki_text.find(JSON_START_MARKER)  # Kommentar: Startmarker suchen
    end_idx = ki_text.find(JSON_END_MARKER)  # Kommentar: Endmarker suchen
    if start_idx == -1 or end_idx == -1:  # Kommentar: Marker fehlen?
        raise ValueError("JSON_START oder JSON_END nicht gefunden.")  # Kommentar: Fehler werfen
    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()  # Kommentar: Block ausschneiden
    json_roh = json_roh.replace("```json", "").replace("```", "").strip()  # Kommentar: Codefences entfernen
    first_brace = json_roh.find("{")  # Kommentar: Erste Klammer
    last_brace = json_roh.rfind("}")  # Kommentar: Letzte Klammer
    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:  # Kommentar: Ungültig?
        raise ValueError("Kein gültiger JSON-Block in KI-Antwort.")  # Kommentar: Fehler werfen
    json_clean = json_roh[first_brace:last_brace + 1]  # Kommentar: Reines JSON herausnehmen
    json_clean = json_clean.replace(",\n}", "\n}").replace(",}", "}")  # Kommentar: Trailing commas fixen
    return json.loads(json_clean)  # Kommentar: JSON parsen und dict zurückgeben


def euro_zu_float(text) -> float:  # Kommentar: Euro-String zu Float robust konvertieren
    if isinstance(text, (int, float)):  # Kommentar: Wenn bereits Zahl
        return float(text)  # Kommentar: float zurückgeben
    if not text:  # Kommentar: Wenn leer
        return 0.0  # Kommentar: 0 zurückgeben
    t = str(text)  # Kommentar: String erzwingen
    t = t.replace("€", "").replace("EUR", "").replace("Euro", "")  # Kommentar: Währungszeichen entfernen
    t = t.replace("\u00a0", " ").strip()  # Kommentar: NBSP bereinigen
    t = t.replace(" ", "")  # Kommentar: Leerzeichen entfernen
    filtered = []  # Kommentar: Liste für erlaubte Zeichen
    for ch in t:  # Kommentar: Zeichen iterieren
        if ch.isdigit() or ch in [",", ".", "+", "-"]:  # Kommentar: Nur Zahlen/Trennzeichen erlauben
            filtered.append(ch)  # Kommentar: Zeichen aufnehmen
    t = "".join(filtered)  # Kommentar: Zusammenfügen
    if not t:  # Kommentar: Nach Filter leer?
        return 0.0  # Kommentar: 0 zurückgeben
    if "." in t and "," in t:  # Kommentar: Tausender und Dezimal vorhanden
        t = t.replace(".", "").replace(",", ".")  # Kommentar: DE->EN Format
    elif "," in t:  # Kommentar: Nur Komma als Dezimal
        t = t.replace(",", ".")  # Kommentar: Komma -> Punkt
    try:  # Kommentar: Parse versuchen
        return float(t)  # Kommentar: float zurückgeben
    except ValueError:  # Kommentar: Parse fehlgeschlagen
        return 0.0  # Kommentar: Fallback 0


def float_zu_euro(betrag: float) -> str:  # Kommentar: Float in Euro-String (DE) formatieren
    s = f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # Kommentar: DE Format
    return s + " €"  # Kommentar: Eurozeichen anhängen


def extrahiere_platzhalter(vorlage_pfad: str):  # Kommentar: Platzhalter aus Word-Vorlage lesen
    doc = DocxTemplate(vorlage_pfad)  # Kommentar: Vorlage laden
    return doc.get_undeclared_template_variables()  # Kommentar: Variablen zurückgeben


def daten_defaults(daten: dict) -> dict:  # Kommentar: Erwartete Keys absichern
    keys = [  # Kommentar: Liste erwarteter Felder
        "MANDANT_VORNAME", "MANDANT_NACHNAME", "MANDANT_NAME", "MANDANT_STRASSE", "MANDANT_PLZ_ORT",  # Kommentar: Mandant
        "UNFALL_DATUM", "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE",  # Kommentar: Unfall
        "FAHRZEUGTYP", "KENNZEICHEN", "FAHRZEUG_KENNZEICHEN",  # Kommentar: Fahrzeug
        "POLIZEIAKTE_NUMMER", "SCHADENSNUMMER", "AKTENZEICHEN",  # Kommentar: Akten
        "SCHADENHERGANG",  # Kommentar: Text
        "REPARATURKOSTEN", "WERTMINDERUNG", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN", "NUTZUNGSAUSFALL", "MWST_BETRAG",  # Kommentar: Kosten
        "WIEDERBESCHAFFUNGSWERT", "RESTWERT",  # Kommentar: Totalschaden
        "FRIST_DATUM", "HEUTDATUM",  # Kommentar: Daten
        "ABRECHNUNGSART", "STEUERSTATUS",  # Kommentar: Kontext
        "WIEDERBESCHAFFUNGSAUFWAND", "ERSATZBESCHAFFUNG_MWST",  # Kommentar: Berechnete Felder
        "ZUSATZKOSTEN_BEZEICHNUNG", "ZUSATZKOSTEN_BETRAG",  # Kommentar: Zusatzkosten
        "KOSTENSUMME_X", "GESAMTSUMME",  # Kommentar: Summen
    ]  # Kommentar: Ende keys
    for k in keys:  # Kommentar: Keys iterieren
        daten.setdefault(k, "")  # Kommentar: Default setzen
    return daten  # Kommentar: Daten zurückgeben


def apply_overrides(daten: dict, overrides: dict | None) -> dict:  # Kommentar: Nutzer-Korrekturen anwenden
    if not overrides:  # Kommentar: Keine Overrides?
        return daten  # Kommentar: Unverändert zurück
    for k, v in overrides.items():  # Kommentar: Overrides iterieren
        if k is None:  # Kommentar: Key fehlt?
            continue  # Kommentar: Überspringen
        if v is None:  # Kommentar: Value fehlt?
            continue  # Kommentar: Überspringen
        daten[str(k)] = str(v)  # Kommentar: Als String setzen (auch leer erlaubt)
    return daten  # Kommentar: Daten zurückgeben


def _bestimme_kostenfelder(auswahl: str) -> list[str]:  # Kommentar: Kostenfelder je Vorlage bestimmen
    norm = (auswahl or "").lower()  # Kommentar: Normalisieren
    if "fiktive abrechnung" in norm:  # Kommentar: Fiktive Abrechnung
        return ["REPARATURKOSTEN", "WERTMINDERUNG", "NUTZUNGSAUSFALL", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]  # Kommentar: Summanden
    if "konkrete abrechnung" in norm:  # Kommentar: Konkrete Abrechnung
        return ["REPARATURKOSTEN", "MWST_BETRAG", "WERTMINDERUNG", "NUTZUNGSAUSFALL", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]  # Kommentar: Summanden
    if "130" in norm:  # Kommentar: 130%-Regelung
        return ["REPARATURKOSTEN", "MWST_BETRAG", "NUTZUNGSAUSFALL", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]  # Kommentar: Summanden
    if "totalschaden fiktiv" in norm:  # Kommentar: Totalschaden fiktiv
        return ["WIEDERBESCHAFFUNGSAUFWAND", "NUTZUNGSAUSFALL", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]  # Kommentar: Summanden
    if "totalschaden konkret" in norm or "ersatzbeschaffung" in norm:  # Kommentar: Totalschaden konkret/Ersatzbeschaffung
        return ["WIEDERBESCHAFFUNGSAUFWAND", "ERSATZBESCHAFFUNG_MWST", "NUTZUNGSAUSFALL", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]  # Kommentar: Summanden
    return ["REPARATURKOSTEN", "WERTMINDERUNG", "NUTZUNGSAUSFALL", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]  # Kommentar: Fallback


def anwenden_abrechnungslogik(daten: dict, auswahl: str, steuerstatus: str) -> dict:  # Kommentar: Regelwerk + Summen bilden
    daten["ABRECHNUNGSART"] = auswahl  # Kommentar: Auswahl speichern
    daten["STEUERSTATUS"] = steuerstatus  # Kommentar: Steuerstatus speichern
    norm = (auswahl or "").lower()  # Kommentar: Normalisieren
    is_totalschaden = "totalschaden" in norm  # Kommentar: Flag Totalschaden
    is_fiktiv = "fiktive abrechnung" in norm or "totalschaden fiktiv" in norm  # Kommentar: Flag fiktiv
    is_130 = "130" in norm  # Kommentar: Flag 130%

    reparatur = euro_zu_float(daten.get("REPARATURKOSTEN", ""))  # Kommentar: Reparaturkosten float
    wertminderung = euro_zu_float(daten.get("WERTMINDERUNG", ""))  # Kommentar: Wertminderung float
    kostenpausch = euro_zu_float(daten.get("KOSTENPAUSCHALE", ""))  # Kommentar: Kostenpauschale float
    gutachter = euro_zu_float(daten.get("GUTACHTERKOSTEN", ""))  # Kommentar: Gutachterkosten float
    nutzung = euro_zu_float(daten.get("NUTZUNGSAUSFALL", ""))  # Kommentar: Nutzungsausfall float
    mwst = euro_zu_float(daten.get("MWST_BETRAG", ""))  # Kommentar: MwSt float

    wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))  # Kommentar: WBW float
    restwert = euro_zu_float(daten.get("RESTWERT", ""))  # Kommentar: Restwert float
    wied_aufwand = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSAUFWAND", ""))  # Kommentar: WBA float
    ersatz_mwst = euro_zu_float(daten.get("ERSATZBESCHAFFUNG_MWST", ""))  # Kommentar: Ersatz-MwSt float

    zus_betrag = euro_zu_float(daten.get("ZUSATZKOSTEN_BETRAG", ""))  # Kommentar: Zusatzkosten float

    if is_130:  # Kommentar: 130% -> keine Wertminderung
        wertminderung = 0.0  # Kommentar: auf 0 setzen
        daten["WERTMINDERUNG"] = ""  # Kommentar: Feld leeren

    if is_totalschaden:  # Kommentar: Totalschaden -> WBA berechnen
        if wied_aufwand <= 0.0 and (wbw > 0.0 or restwert > 0.0):  # Kommentar: Nur wenn WBA fehlt
            wied_aufwand = max(wbw - restwert, 0.0)  # Kommentar: WBA = WBW - Restwert

    if ("totalschaden konkret" in norm or "ersatzbeschaffung" in norm) and ersatz_mwst <= 0.0 and mwst > 0.0:  # Kommentar: Ersatz-MwSt ableiten
        ersatz_mwst = mwst  # Kommentar: MwSt übernehmen

    if steuerstatus == "vorsteuerabzugsberechtigt":  # Kommentar: Vorsteuer -> MwSt nicht ansetzen
        if is_totalschaden and ("totalschaden konkret" in norm or "ersatzbeschaffung" in norm):  # Kommentar: Relevanter Fall
            ersatz_mwst = 0.0  # Kommentar: auf 0
            daten["ERSATZBESCHAFFUNG_MWST"] = ""  # Kommentar: Feld leeren

    if is_fiktiv:  # Kommentar: Fiktiv -> MwSt nicht zeigen
        mwst = 0.0  # Kommentar: auf 0
        daten["MWST_BETRAG"] = ""  # Kommentar: Feld leeren

    if is_totalschaden:  # Kommentar: Totalschaden -> Reparaturkosten typischerweise nicht
        reparatur = 0.0  # Kommentar: auf 0
        daten["REPARATURKOSTEN"] = ""  # Kommentar: Feld leeren

    if reparatur > 0.0:  # Kommentar: Formatieren
        daten["REPARATURKOSTEN"] = float_zu_euro(reparatur)  # Kommentar: setzen
    if wertminderung > 0.0:  # Kommentar: Formatieren
        daten["WERTMINDERUNG"] = float_zu_euro(wertminderung)  # Kommentar: setzen
    if kostenpausch > 0.0:  # Kommentar: Formatieren
        daten["KOSTENPAUSCHALE"] = float_zu_euro(kostenpausch)  # Kommentar: setzen
    if gutachter > 0.0:  # Kommentar: Formatieren
        daten["GUTACHTERKOSTEN"] = float_zu_euro(gutachter)  # Kommentar: setzen
    if nutzung > 0.0:  # Kommentar: Formatieren
        daten["NUTZUNGSAUSFALL"] = float_zu_euro(nutzung)  # Kommentar: setzen
    if mwst > 0.0:  # Kommentar: Formatieren
        daten["MWST_BETRAG"] = float_zu_euro(mwst)  # Kommentar: setzen
    if zus_betrag > 0.0:  # Kommentar: Formatieren
        daten["ZUSATZKOSTEN_BETRAG"] = float_zu_euro(zus_betrag)  # Kommentar: setzen
    if wied_aufwand > 0.0:  # Kommentar: Formatieren
        daten["WIEDERBESCHAFFUNGSAUFWAND"] = float_zu_euro(wied_aufwand)  # Kommentar: setzen
    if ersatz_mwst > 0.0:  # Kommentar: Formatieren
        daten["ERSATZBESCHAFFUNG_MWST"] = float_zu_euro(ersatz_mwst)  # Kommentar: setzen

    kostenfelder = _bestimme_kostenfelder(auswahl)  # Kommentar: Kostenfelder bestimmen

    feld_zu_float = {  # Kommentar: Mapping Feld -> float
        "REPARATURKOSTEN": reparatur,  # Kommentar: Map
        "WERTMINDERUNG": wertminderung,  # Kommentar: Map
        "KOSTENPAUSCHALE": kostenpausch,  # Kommentar: Map
        "GUTACHTERKOSTEN": gutachter,  # Kommentar: Map
        "NUTZUNGSAUSFALL": nutzung,  # Kommentar: Map
        "MWST_BETRAG": mwst,  # Kommentar: Map
        "WIEDERBESCHAFFUNGSAUFWAND": wied_aufwand,  # Kommentar: Map
        "ERSATZBESCHAFFUNG_MWST": ersatz_mwst,  # Kommentar: Map
    }  # Kommentar: Ende mapping

    kosten_x = 0.0  # Kommentar: Summe initialisieren
    for feld in kostenfelder:  # Kommentar: Summanden iterieren
        kosten_x += feld_zu_float.get(feld, 0.0)  # Kommentar: Wert addieren

    daten["KOSTENSUMME_X"] = float_zu_euro(kosten_x) if kosten_x > 0.0 else ""  # Kommentar: Kostensumme setzen
    gesamt = kosten_x + zus_betrag  # Kommentar: Gesamtsumme = Tabelle + Zusatzkosten
    daten["GESAMTSUMME"] = float_zu_euro(gesamt) if gesamt > 0.0 else ""  # Kommentar: Gesamtsumme setzen

    return daten  # Kommentar: Daten zurückgeben


def daten_nachbearbeiten(daten: dict, platzhalter: set, auswahl: str, steuerstatus: str, zus_bez: str, zus_betrag: str) -> dict:  # Kommentar: Defaults + Fristen + Logik
    daten = daten_defaults(daten)  # Kommentar: Defaults setzen
    daten["ZUSATZKOSTEN_BEZEICHNUNG"] = (zus_bez or "").strip()  # Kommentar: Zusatzkosten-Bezeichnung setzen
    daten["ZUSATZKOSTEN_BETRAG"] = (zus_betrag or "").strip()  # Kommentar: Zusatzkosten-Betrag setzen
    jetzt = datetime.now()  # Kommentar: aktuelles Datum
    daten["FRIST_DATUM"] = (jetzt + timedelta(days=14)).strftime("%d.%m.%Y")  # Kommentar: Frist = +14 Tage
    daten["HEUTDATUM"] = jetzt.strftime("%d.%m.%Y")  # Kommentar: Heutdatum setzen
    daten = anwenden_abrechnungslogik(daten, auswahl, steuerstatus)  # Kommentar: Abrechnungslogik anwenden
    if "WIEDERBESCHAFFUNGSAUFWAND" in platzhalter and not daten.get("WIEDERBESCHAFFUNGSAUFWAND"):  # Kommentar: Wenn Vorlage WBA erwartet
        wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))  # Kommentar: WBW float
        rest = euro_zu_float(daten.get("RESTWERT", ""))  # Kommentar: Restwert float
        if wbw > 0.0 or rest > 0.0:  # Kommentar: nur wenn Werte vorhanden
            daten["WIEDERBESCHAFFUNGSAUFWAND"] = float_zu_euro(max(wbw - rest, 0.0))  # Kommentar: WBA setzen
    return daten  # Kommentar: Daten zurückgeben


def word_aus_vorlage_erstellen(daten: dict, vorlage_pfad: str, ziel_pfad: str) -> None:  # Kommentar: Word aus Vorlage erzeugen
    doc = DocxTemplate(vorlage_pfad)  # Kommentar: Vorlage laden
    platzhalter = doc.get_undeclared_template_variables()  # Kommentar: Platzhalter lesen
    daten_fuer_vorlage = {k: v for k, v in daten.items() if k in platzhalter}  # Kommentar: Nur verwendete Felder
    os.makedirs(os.path.dirname(ziel_pfad), exist_ok=True)  # Kommentar: Zielordner sicherstellen
    doc.render(daten_fuer_vorlage)  # Kommentar: Rendern
    doc.save(ziel_pfad)  # Kommentar: Speichern


def ki_datei_verarbeiten(pfad_ki_txt: str, vorlage_pfad: str, auswahl: str, steuerstatus: str, zus_bez: str, zus_betrag: str, overrides: dict | None) -> str:  # Kommentar: KI-Datei -> DOCX
    with open(pfad_ki_txt, "r", encoding="utf-8") as f:  # Kommentar: KI-Datei öffnen
        ki_text = f.read()  # Kommentar: Inhalt lesen
    daten = json_aus_ki_antwort_parsen(ki_text)  # Kommentar: JSON parsen
    daten = apply_overrides(daten, overrides)  # Kommentar: Nutzer-Korrekturen anwenden
    platzhalter = extrahiere_platzhalter(vorlage_pfad)  # Kommentar: Platzhalter lesen
    daten = daten_nachbearbeiten(daten, platzhalter, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: Nachbearbeiten
    basisname = os.path.splitext(os.path.basename(pfad_ki_txt))[0]  # Kommentar: Basisname
    datum_str = datetime.now().strftime("%Y%m%d_%H%M%S")  # Kommentar: Timestamp
    ausgabe_name = f"{basisname}_schreiben_{datum_str}.docx"  # Kommentar: Ausgabename
    ausgabe_pfad = os.path.join(AUSGANGS_ORDNER, ausgabe_name)  # Kommentar: Ausgabepfad
    word_aus_vorlage_erstellen(daten, vorlage_pfad, ausgabe_pfad)  # Kommentar: Word erzeugen
    return ausgabe_pfad  # Kommentar: Pfad zurückgeben


def main(pfad_ki_txt: str = None, vorlage_pfad: str | None = None, auswahl: str = "", steuerstatus: str = "", zus_bez: str = "", zus_betrag: str = "", overrides: dict | None = None) -> str:  # Kommentar: Entry-Point
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: KI-Ordner sicherstellen
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: Ausgangsordner sicherstellen
    if vorlage_pfad is None:  # Kommentar: Vorlage muss übergeben werden
        raise ValueError("vorlage_pfad muss übergeben werden (Word-Vorlage .docx).")  # Kommentar: Fehler
    if pfad_ki_txt is None:  # Kommentar: KI-Dateipfad muss übergeben werden
        raise ValueError("pfad_ki_txt muss übergeben werden.")  # Kommentar: Fehler
    if not os.path.isfile(pfad_ki_txt):  # Kommentar: KI-Datei existiert?
        raise FileNotFoundError(f"KI-Datei existiert nicht: {pfad_ki_txt}")  # Kommentar: Fehler
    if not os.path.isfile(vorlage_pfad):  # Kommentar: Vorlage existiert?
        raise FileNotFoundError(f"Vorlage existiert nicht: {vorlage_pfad}")  # Kommentar: Fehler
    return ki_datei_verarbeiten(pfad_ki_txt, vorlage_pfad, auswahl, steuerstatus, zus_bez, zus_betrag, overrides)  # Kommentar: Verarbeiten und Rückgabe


if __name__ == "__main__":  # Kommentar: Direktausführung
    main()  # Kommentar: Aufruf
