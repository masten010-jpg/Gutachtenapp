# programm_2_word_output.py  # Kommentar: Datei für KI-JSON->Nachbearbeitung->Word-Ausgabe

import os  # Kommentar: OS-Funktionen importieren
import json  # Kommentar: JSON importieren
from datetime import datetime, timedelta  # Kommentar: Datum/Fristen importieren
from docxtpl import DocxTemplate  # Kommentar: Word-Template-Engine importieren
from programm_1_ki_input import KI_ANTWORT_ORDNER, BASE_DIR  # Kommentar: Pfade übernehmen

AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # Kommentar: Output-Ordner
JSON_START_MARKER = "JSON_START"  # Kommentar: Marker Start
JSON_END_MARKER = "JSON_END"  # Kommentar: Marker Ende


def json_aus_ki_antwort_parsen(ki_text: str) -> dict:  # Kommentar: JSON aus KI-Text extrahieren
    start_idx = ki_text.find(JSON_START_MARKER)  # Kommentar: Startmarker suchen
    end_idx = ki_text.find(JSON_END_MARKER)  # Kommentar: Endmarker suchen
    if start_idx == -1 or end_idx == -1:  # Kommentar: Marker prüfen
        raise ValueError("JSON_START oder JSON_END nicht gefunden.")  # Kommentar: Fehler

    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()  # Kommentar: Block ausschneiden
    json_roh = json_roh.replace("```json", "").replace("```", "").strip()  # Kommentar: Backticks entfernen

    first_brace = json_roh.find("{")  # Kommentar: Erste Klammer
    last_brace = json_roh.rfind("}")  # Kommentar: Letzte Klammer
    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:  # Kommentar: Validieren
        raise ValueError("Kein gültiger JSON-Block in KI-Antwort.")  # Kommentar: Fehler

    json_clean = json_roh[first_brace:last_brace + 1]  # Kommentar: Reines JSON schneiden
    json_clean = json_clean.replace(",\n}", "\n}").replace(",}", "}")  # Kommentar: Trailing commas fixen
    return json.loads(json_clean)  # Kommentar: JSON parse


def euro_zu_float(text) -> float:  # Kommentar: Eurostring -> float robust
    if isinstance(text, (int, float)):  # Kommentar: Zahl?
        return float(text)  # Kommentar: Direkt
    if not text:  # Kommentar: Leer?
        return 0.0  # Kommentar: 0
    t = str(text)  # Kommentar: String erzwingen
    t = t.replace("€", "").replace("EUR", "").replace("Euro", "")  # Kommentar: Währung entfernen
    t = t.replace("\u00a0", " ").strip()  # Kommentar: NBSP bereinigen
    t = t.replace(" ", "")  # Kommentar: Spaces entfernen
    filtered = []  # Kommentar: Filterliste
    for ch in t:  # Kommentar: Zeichen iterieren
        if ch.isdigit() or ch in [",", ".", "+", "-"]:  # Kommentar: Zulässige Zeichen
            filtered.append(ch)  # Kommentar: Sammeln
    t = "".join(filtered)  # Kommentar: Join
    if not t:  # Kommentar: Leer nach Filter?
        return 0.0  # Kommentar: 0
    if "." in t and "," in t:  # Kommentar: Tausender+Dezimal
        t = t.replace(".", "").replace(",", ".")  # Kommentar: DE->EN
    elif "," in t:  # Kommentar: Nur Komma
        t = t.replace(",", ".")  # Kommentar: Komma->Punkt
    try:  # Kommentar: Parse
        return float(t)  # Kommentar: Return float
    except ValueError:  # Kommentar: Fehler
        return 0.0  # Kommentar: Fallback


def float_zu_euro(betrag: float) -> str:  # Kommentar: float -> Eurostring DE
    s = f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # Kommentar: Format DE
    return s + " €"  # Kommentar: Eurozeichen


def extrahiere_platzhalter(vorlage_pfad: str):  # Kommentar: Platzhalter aus Word holen
    doc = DocxTemplate(vorlage_pfad)  # Kommentar: Vorlage laden
    return doc.get_undeclared_template_variables()  # Kommentar: Variablen zurückgeben


def daten_defaults(daten: dict) -> dict:  # Kommentar: Alle Keys absichern
    keys = [  # Kommentar: Erwartete Keys
        "MANDANT_VORNAME", "MANDANT_NACHNAME", "MANDANT_NAME", "MANDANT_STRASSE", "MANDANT_PLZ_ORT",  # Kommentar: Mandant
        "UNFALL_DATUM", "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE",  # Kommentar: Unfall
        "FAHRZEUGTYP", "KENNZEICHEN", "FAHRZEUG_KENNZEICHEN",  # Kommentar: Fahrzeug
        "POLIZEIAKTE_NUMMER", "SCHADENSNUMMER", "AKTENZEICHEN",  # Kommentar: Nummern
        "SCHADENHERGANG",  # Kommentar: Text
        "REPARATURKOSTEN", "WERTMINDERUNG", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN", "NUTZUNGSAUSFALL", "MWST_BETRAG",  # Kommentar: Kosten
        "WIEDERBESCHAFFUNGSWERT", "RESTWERT",  # Kommentar: Totalschaden
        "FRIST_DATUM", "HEUTDATUM",  # Kommentar: Daten
        "ABRECHNUNGSART", "STEUERSTATUS",  # Kommentar: Kontext
        "WIEDERBESCHAFFUNGSAUFWAND", "ERSATZBESCHAFFUNG_MWST",  # Kommentar: berechnete Felder
        "ZUSATZKOSTEN_BEZEICHNUNG", "ZUSATZKOSTEN_BETRAG",  # Kommentar: Zusatzkosten
        "KOSTENSUMME_X", "GESAMTSUMME",  # Kommentar: Summen
    ]
    for k in keys:  # Kommentar: Keys durchgehen
        daten.setdefault(k, "")  # Kommentar: Default setzen
    return daten  # Kommentar: zurück


def apply_overrides(daten: dict, overrides: dict | None) -> dict:  # Kommentar: User-Korrekturen auf KI-Daten anwenden
    if not overrides:  # Kommentar: Wenn keine Overrides
        return daten  # Kommentar: Nichts tun
    for k, v in overrides.items():  # Kommentar: Alle Korrekturen iterieren
        if k is None:  # Kommentar: Key-Guard
            continue  # Kommentar: Skip
        if v is None:  # Kommentar: Value-Guard
            continue  # Kommentar: Skip
        daten[str(k)] = str(v)  # Kommentar: Als String setzen (auch leer erlaubt)
    return daten  # Kommentar: Daten zurück


def _bestimme_kostenfelder(auswahl: str) -> list[str]:  # Kommentar: Kostentabellen-Felder je Vorlage bestimmen
    norm = (auswahl or "").lower()  # Kommentar: Normalisieren
    if "fiktive abrechnung" in norm:  # Kommentar: Fiktiv (Reparatur)
        return ["REPARATURKOSTEN", "WERTMINDERUNG", "NUTZUNGSAUSFALL", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]  # Kommentar: Summanden
    if "konkrete abrechnung" in norm:  # Kommentar: Konkret unter WBW
        return ["REPARATURKOSTEN", "MWST_BETRAG", "WERTMINDERUNG", "NUTZUNGSAUSFALL", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]  # Kommentar: Summanden
    if "130" in norm:  # Kommentar: 130%
        return ["REPARATURKOSTEN", "MWST_BETRAG", "NUTZUNGSAUSFALL", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]  # Kommentar: Summanden
    if "totalschaden fiktiv" in norm:  # Kommentar: Totalschaden fiktiv
        return ["WIEDERBESCHAFFUNGSAUFWAND", "NUTZUNGSAUSFALL", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]  # Kommentar: Summanden
    if "totalschaden konkret" in norm or "ersatzbeschaffung" in norm:  # Kommentar: Totalschaden konkret/Ersatzbeschaffung
        return ["WIEDERBESCHAFFUNGSAUFWAND", "ERSATZBESCHAFFUNG_MWST", "NUTZUNGSAUSFALL", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]  # Kommentar: Summanden
    return ["REPARATURKOSTEN", "WERTMINDERUNG", "NUTZUNGSAUSFALL", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN"]  # Kommentar: Fallback


def anwenden_abrechnungslogik(daten: dict, auswahl: str, steuerstatus: str) -> dict:  # Kommentar: Summen/Format/Regeln anwenden
    daten["ABRECHNUNGSART"] = auswahl  # Kommentar: Speichern
    daten["STEUERSTATUS"] = steuerstatus  # Kommentar: Speichern
    norm = (auswahl or "").lower()  # Kommentar: Normalisieren
    is_totalschaden = "totalschaden" in norm  # Kommentar: Flag
    is_fiktiv = "fiktive abrechnung" in norm or "totalschaden fiktiv" in norm  # Kommentar: Flag
    is_130 = "130" in norm  # Kommentar: Flag

    reparatur = euro_zu_float(daten.get("REPARATURKOSTEN", ""))  # Kommentar: Reparatur
    wertminderung = euro_zu_float(daten.get("WERTMINDERUNG", ""))  # Kommentar: Wertminderung
    kostenpausch = euro_zu_float(daten.get("KOSTENPAUSCHALE", ""))  # Kommentar: Pauschale
    gutachter = euro_zu_float(daten.get("GUTACHTERKOSTEN", ""))  # Kommentar: Gutachter
    nutzung = euro_zu_float(daten.get("NUTZUNGSAUSFALL", ""))  # Kommentar: Nutzung
    mwst = euro_zu_float(daten.get("MWST_BETRAG", ""))  # Kommentar: MwSt

    wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))  # Kommentar: WBW
    restwert = euro_zu_float(daten.get("RESTWERT", ""))  # Kommentar: Restwert
    wied_aufwand = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSAUFWAND", ""))  # Kommentar: WBA
    ersatz_mwst = euro_zu_float(daten.get("ERSATZBESCHAFFUNG_MWST", ""))  # Kommentar: Ersatz-MwSt

    zus_betrag = euro_zu_float(daten.get("ZUSATZKOSTEN_BETRAG", ""))  # Kommentar: Zusatzkosten

    if is_130:  # Kommentar: 130% -> Wertminderung raus
        wertminderung = 0.0  # Kommentar: auf 0
        daten["WERTMINDERUNG"] = ""  # Kommentar: Feld leeren

    if is_totalschaden:  # Kommentar: Totalschaden -> WBA berechnen
        if wied_aufwand <= 0.0 and (wbw > 0.0 or restwert > 0.0):  # Kommentar: Wenn nicht vorhanden
            wied_aufwand = max(wbw - restwert, 0.0)  # Kommentar: WBA = WBW - Restwert

    if ("totalschaden konkret" in norm or "ersatzbeschaffung" in norm) and ersatz_mwst <= 0.0 and mwst > 0.0:  # Kommentar: Ersatz-MwSt ableiten
        ersatz_mwst = mwst  # Kommentar: übernehmen

    if steuerstatus == "vorsteuerabzugsberechtigt":  # Kommentar: Vorsteuer -> MwSt i.d.R. nicht in Summe
        if is_totalschaden and ("totalschaden konkret" in norm or "ersatzbeschaffung" in norm):  # Kommentar: Relevanter Fall
            ersatz_mwst = 0.0  # Kommentar: nicht ansetzen
            daten["ERSATZBESCHAFFUNG_MWST"] = ""  # Kommentar: Feld leeren

    if is_fiktiv:  # Kommentar: Fiktiv -> MwSt nicht zeigen
        mwst = 0.0  # Kommentar: auf 0
        daten["MWST_BETRAG"] = ""  # Kommentar: Feld leeren

    if is_totalschaden:  # Kommentar: Totalschaden -> Reparaturkosten typischerweise nicht
        reparatur = 0.0  # Kommentar: auf 0
        daten["REPARATURKOSTEN"] = ""  # Kommentar: leeren

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

    kostenfelder = _bestimme_kostenfelder(auswahl)  # Kommentar: Tabellenfelder wählen

    feld_zu_float = {  # Kommentar: Mapping Felder->Floatwerte
        "REPARATURKOSTEN": reparatur,  # Kommentar: Map
        "WERTMINDERUNG": wertminderung,  # Kommentar: Map
        "KOSTENPAUSCHALE": kostenpausch,  # Kommentar: Map
        "GUTACHTERKOSTEN": gutachter,  # Kommentar: Map
        "NUTZUNGSAUSFALL": nutzung,  # Kommentar: Map
        "MWST_BETRAG": mwst,  # Kommentar: Map
        "WIEDERBESCHAFFUNGSAUFWAND": wied_aufwand,  # Kommentar: Map
        "ERSATZBESCHAFFUNG_MWST": ersatz_mwst,  # Kommentar: Map
    }  # Kommentar: Ende mapping

    kosten_x = 0.0  # Kommentar: Summe initial
    for feld in kostenfelder:  # Kommentar: Iteration
        kosten_x += feld_zu_float.get(feld, 0.0)  # Kommentar: Add

    daten["KOSTENSUMME_X"] = float_zu_euro(kosten_x) if kosten_x > 0.0 else ""  # Kommentar: Kostensumme setzen
    gesamt = kosten_x + zus_betrag  # Kommentar: Gesamtsumme = Tabelle + Zusatzkosten
    daten["GESAMTSUMME"] = float_zu_euro(gesamt) if gesamt > 0.0 else ""  # Kommentar: Gesamtsumme setzen

    return daten  # Kommentar: Return


def daten_nachbearbeiten(daten: dict, platzhalter: set, auswahl: str, steuerstatus: str, zus_bez: str, zus_betrag: str) -> dict:  # Kommentar: Nachbearbeitung bündeln
    daten = daten_defaults(daten)  # Kommentar: Defaults setzen
    daten["ZUSATZKOSTEN_BEZEICHNUNG"] = (zus_bez or "").strip()  # Kommentar: Zusatzbez setzen
    daten["ZUSATZKOSTEN_BETRAG"] = (zus_betrag or "").strip()  # Kommentar: Zusatzbetrag setzen
    jetzt = datetime.now()  # Kommentar: Jetzt
    daten["FRIST_DATUM"] = (jetzt + timedelta(days=14)).strftime("%d.%m.%Y")  # Kommentar: Frist
    daten["HEUTDATUM"] = jetzt.strftime("%d.%m.%Y")  # Kommentar: Heute
    daten = anwenden_abrechnungslogik(daten, auswahl, steuerstatus)  # Kommentar: Logik anwenden
    if "WIEDERBESCHAFFUNGSAUFWAND" in platzhalter and not daten.get("WIEDERBESCHAFFUNGSAUFWAND"):  # Kommentar: Wenn Vorlage WBA erwartet
        wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))  # Kommentar: WBW
        rest = euro_zu_float(daten.get("RESTWERT", ""))  # Kommentar: Rest
        if wbw > 0.0 or rest > 0.0:  # Kommentar: Nur wenn Werte existieren
            daten["WIEDERBESCHAFFUNGSAUFWAND"] = float_zu_euro(max(wbw - rest, 0.0))  # Kommentar: WBA setzen
    return daten  # Kommentar: Return


def word_aus_vorlage_erstellen(daten: dict, vorlage_pfad: str, ziel_pfad: str) -> None:  # Kommentar: Word-Datei erzeugen
    doc = DocxTemplate(vorlage_pfad)  # Kommentar: Vorlage laden
    platzhalter = doc.get_undeclared_template_variables()  # Kommentar: Platzhalter lesen
    daten_fuer_vorlage = {k: v for k, v in daten.items() if k in platzhalter}  # Kommentar: Nur benötigte Daten
    os.makedirs(os.path.dirname(ziel_pfad), exist_ok=True)  # Kommentar: Zielordner sicherstellen
    doc.render(daten_fuer_vorlage)  # Kommentar: Rendern
    doc.save(ziel_pfad)  # Kommentar: Speichern


def ki_datei_verarbeiten(pfad_ki_txt: str, vorlage_pfad: str, auswahl: str, steuerstatus: str, zus_bez: str, zus_betrag: str, overrides: dict | None) -> str:  # Kommentar: KI-Datei->DOCX
    with open(pfad_ki_txt, "r", encoding="utf-8") as f:  # Kommentar: KI-Datei öffnen
        ki_text = f.read()  # Kommentar: Inhalt lesen
    daten = json_aus_ki_antwort_parsen(ki_text)  # Kommentar: JSON parsen
    daten = apply_overrides(daten, overrides)  # Kommentar: User-Overrides anwenden
    platzhalter = extrahiere_platzhalter(vorlage_pfad)  # Kommentar: Platzhalter lesen
    daten = daten_nachbearbeiten(daten, platzhalter, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: Nachbearbeiten
    basisname = os.path.splitext(os.path.basename(pfad_ki_txt))[0]  # Kommentar: Basisname
    datum_str = datetime.now().strftime("%Y%m%d_%H%M%S")  # Kommentar: Timestamp
    ausgabe_name = f"{basisname}_schreiben_{datum_str}.docx"  # Kommentar: Dateiname
    ausgabe_pfad = os.path.join(AUSGANGS_ORDNER, ausgabe_name)  # Kommentar: Vollpfad
    word_aus_vorlage_erstellen(daten, vorlage_pfad, ausgabe_pfad)  # Kommentar: Word erzeugen
    return ausgabe_pfad  # Kommentar: Pfad zurückgeben


def main(pfad_ki_txt: str = None, vorlage_pfad: str | None = None, auswahl: str = "", steuerstatus: str = "", zus_bez: str = "", zus_betrag: str = "", overrides: dict | None = None) -> str:  # Kommentar: Hauptentry
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: Ordner sicherstellen
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: Ordner sicherstellen
    if vorlage_pfad is None:  # Kommentar: Vorlage prüfen
        raise ValueError("vorlage_pfad muss übergeben werden (Word-Vorlage .docx).")  # Kommentar: Fehler
    if pfad_ki_txt is None:  # Kommentar: KI-Datei prüfen
        raise ValueError("pfad_ki_txt muss übergeben werden.")  # Kommentar: Fehler
    if not os.path.isfile(pfad_ki_txt):  # Kommentar: Existiert KI-Datei?
        raise FileNotFoundError(f"KI-Datei existiert nicht: {pfad_ki_txt}")  # Kommentar: Fehler
    if not os.path.isfile(vorlage_pfad):  # Kommentar: Existiert Vorlage?
        raise FileNotFoundError(f"Vorlage existiert nicht: {vorlage_pfad}")  # Kommentar: Fehler
    return ki_datei_verarbeiten(pfad_ki_txt, vorlage_pfad, auswahl, steuerstatus, zus_bez, zus_betrag, overrides)  # Kommentar: Verarbeiten


if __name__ == "__main__":  # Kommentar: Direktausführung
    main()  # Kommentar: Aufruf
