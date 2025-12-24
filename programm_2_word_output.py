# programm_2_word_output.py  # Kommentar: Programm 2 – KI JSON -> Word, inkl. Debug und korrekter Summenlogik

import os  # Kommentar: OS-Pfade/Ordner
import json  # Kommentar: JSON parsing
from datetime import datetime, timedelta  # Kommentar: Datum/Frist
from docxtpl import DocxTemplate  # Kommentar: Word-Template Engine
from programm_1_ki_input import KI_ANTWORT_ORDNER, BASE_DIR  # Kommentar: Pfade aus Programm 1

PROGRAMM_2_VERSION = "2025-12-24-summe-all-varianten-v1"  # Kommentar: Version zum Debuggen (siehst du in der App)

AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # Kommentar: Ausgabeordner
JSON_START_MARKER = "JSON_START"  # Kommentar: JSON Start Marker
JSON_END_MARKER = "JSON_END"  # Kommentar: JSON End Marker


def json_aus_ki_antwort_parsen(ki_text: str) -> dict:  # Kommentar: JSON Block aus KI Text extrahieren
    start_idx = ki_text.find(JSON_START_MARKER)  # Kommentar: Startmarker suchen
    end_idx = ki_text.find(JSON_END_MARKER)  # Kommentar: Endmarker suchen
    if start_idx == -1 or end_idx == -1:  # Kommentar: Marker fehlen?
        raise ValueError("JSON_START oder JSON_END nicht gefunden.")  # Kommentar: Fehler werfen
    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()  # Kommentar: Block ausschneiden
    json_roh = json_roh.replace("```json", "").replace("```", "").strip()  # Kommentar: Codefences entfernen
    first_brace = json_roh.find("{")  # Kommentar: Erste Klammer
    last_brace = json_roh.rfind("}")  # Kommentar: Letzte Klammer
    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:  # Kommentar: Ungültig?
        raise ValueError("Kein gültiger JSON-Block in KI-Antwort.")  # Kommentar: Fehler
    json_clean = json_roh[first_brace:last_brace + 1]  # Kommentar: JSON sauber ausschneiden
    json_clean = json_clean.replace(",\n}", "\n}").replace(",}", "}")  # Kommentar: KI-Kommafehler reparieren
    return json.loads(json_clean)  # Kommentar: JSON laden


def euro_zu_float(text) -> float:  # Kommentar: Euro-String robust -> float
    if isinstance(text, (int, float)):  # Kommentar: Schon Zahl?
        return float(text)  # Kommentar: Cast
    if not text:  # Kommentar: leer?
        return 0.0  # Kommentar: Null
    t = str(text)  # Kommentar: in String
    t = t.replace("€", "").replace("EUR", "").replace("Euro", "")  # Kommentar: Währung entfernen
    t = t.replace("\u00a0", " ").strip()  # Kommentar: NBSP entfernen
    t = t.replace(" ", "")  # Kommentar: Spaces entfernen
    filtered = []  # Kommentar: erlaubte Zeichen
    for ch in t:  # Kommentar: iterieren
        if ch.isdigit() or ch in [",", ".", "+", "-"]:  # Kommentar: erlaubte Zeichen
            filtered.append(ch)  # Kommentar: sammeln
    t = "".join(filtered)  # Kommentar: zusammenbauen
    if not t:  # Kommentar: leer?
        return 0.0  # Kommentar: Null
    if "." in t and "," in t:  # Kommentar: 1.234,56
        t = t.replace(".", "").replace(",", ".")  # Kommentar: tausender weg, komma -> punkt
    elif "," in t:  # Kommentar: 1234,56
        t = t.replace(",", ".")  # Kommentar: komma -> punkt
    try:  # Kommentar: parse versuchen
        return float(t)  # Kommentar: float
    except ValueError:  # Kommentar: parse fail
        return 0.0  # Kommentar: fallback


def float_zu_euro(betrag: float) -> str:  # Kommentar: float -> deutsches Euroformat
    s = f"{betrag:,.2f}"  # Kommentar: US-Format
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")  # Kommentar: Punkt/Komma tauschen
    return s + " €"  # Kommentar: Eurozeichen anhängen


def daten_defaults(daten: dict) -> dict:  # Kommentar: Defaults für alle bekannten Keys setzen
    keys = [  # Kommentar: mögliche Template-Keys
        "REPARATURKOSTEN", "MWST_BETRAG", "WERTMINDERUNG", "NUTZUNGSAUSFALL",  # Kommentar: Tabelle
        "KOSTENPAUSCHALE", "GUTACHTERKOSTEN",  # Kommentar: weitere Kosten
        "WIEDERBESCHAFFUNGSWERT", "RESTWERT", "WIEDERBESCHAFFUNGSAUFWAND",  # Kommentar: Totalschaden
        "ZUSATZKOSTEN_BEZEICHNUNG", "ZUSATZKOSTEN_BETRAG",  # Kommentar: Zusatz
        "KOSTENSUMME_X", "GESAMTSUMME",  # Kommentar: Summen
        "ABRECHNUNGSART", "STEUERSTATUS", "VORSTEUERBERECHTIGUNG",  # Kommentar: Text
        "FRIST_DATUM", "HEUTDATUM",  # Kommentar: Datum
        # Kommentar: plus alles aus deinem JSON (sicherheitshalber)
        "MANDANT_VORNAME", "MANDANT_NACHNAME", "MANDANT_NAME", "MANDANT_STRASSE", "MANDANT_PLZ_ORT",
        "UNFALL_DATUM", "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE",
        "FAHRZEUGTYP", "KENNZEICHEN", "FAHRZEUG_KENNZEICHEN",
        "POLIZEIAKTE_NUMMER", "SCHADENSNUMMER", "AKTENZEICHEN",
        "SCHADENHERGANG",
    ]  # Kommentar: Ende Keys
    for k in keys:  # Kommentar: iterieren
        daten.setdefault(k, "")  # Kommentar: Default
    return daten  # Kommentar: Return


def setze_vorsteuer_text(daten: dict, steuerstatus: str) -> dict:  # Kommentar: setzt {{VORSTEUERBERECHTIGUNG}}
    daten["STEUERSTATUS"] = steuerstatus  # Kommentar: speichern
    if steuerstatus == "vorsteuerabzugsberechtigt":  # Kommentar: Vorsteuer-Fall
        daten["VORSTEUERBERECHTIGUNG"] = "vorsteuerberechtigt"  # Kommentar: gewünschter Text
    else:  # Kommentar: Standard
        daten["VORSTEUERBERECHTIGUNG"] = "nicht vorsteuerberechtigt"  # Kommentar: gewünschter Text
    return daten  # Kommentar: Return


def mwst_leeren_wenn_noetig(daten: dict, auswahl: str, steuerstatus: str) -> dict:  # Kommentar: MWST_BETRAG leer lassen wo nötig
    if auswahl in ["Fiktive Abrechnung (Reparaturschaden)", "Totalschaden fiktiv"]:  # Kommentar: fiktive Fälle
        daten["MWST_BETRAG"] = ""  # Kommentar: leeren
        return daten  # Kommentar: Return
    if steuerstatus == "vorsteuerabzugsberechtigt":  # Kommentar: Vorsteuer -> MwSt leer
        daten["MWST_BETRAG"] = ""  # Kommentar: leeren
        return daten  # Kommentar: Return
    return daten  # Kommentar: sonst belassen


def variante_key(auswahl: str) -> str:  # Kommentar: Mappt UI-Auswahl auf internen Key
    if auswahl == "Fiktive Abrechnung (Reparaturschaden)":  # Kommentar: Fall 1
        return "FIKTIV_REPARATUR"  # Kommentar: Key
    if auswahl == "Konkrete Abrechnung < WBW":  # Kommentar: Fall 2
        return "KONKRET_UNTER_WBW"  # Kommentar: Key
    if auswahl == "130%-Regelung":  # Kommentar: Fall 3
        return "REGEL_130"  # Kommentar: Key
    if auswahl == "Totalschaden fiktiv":  # Kommentar: Fall 4
        return "TOTAL_FIKTIV"  # Kommentar: Key
    if auswahl == "Totalschaden konkret":  # Kommentar: Fall 5
        return "TOTAL_KONKRET"  # Kommentar: Key
    if auswahl == "Totalschaden Ersatzbeschaffung":  # Kommentar: Fall 6
        return "TOTAL_ERSATZ"  # Kommentar: Key
    return "UNKNOWN"  # Kommentar: Fallback


def summe_tabelle_berechnen(variant: str, reparatur: float, mwst: float, wertminderung: float, nutzung: float, kostenpausch: float, gutachter: float, zusatz: float, wba: float) -> float:  # Kommentar: Summen je Variante
    if variant == "FIKTIV_REPARATUR":  # Kommentar: fiktiv Reparaturschaden
        return reparatur + wertminderung + nutzung + kostenpausch + gutachter + zusatz  # Kommentar: ohne MwSt
    if variant == "KONKRET_UNTER_WBW":  # Kommentar: konkret < WBW
        return reparatur + mwst + wertminderung + nutzung + kostenpausch + gutachter + zusatz  # Kommentar: alles addieren
    if variant == "REGEL_130":  # Kommentar: 130%
        return reparatur + mwst + nutzung + kostenpausch + gutachter + zusatz  # Kommentar: ohne Wertminderung
    if variant == "TOTAL_FIKTIV":  # Kommentar: Totalschaden fiktiv
        return wba + nutzung + kostenpausch + gutachter + zusatz  # Kommentar: WBA + Nebenkosten
    if variant == "TOTAL_KONKRET":  # Kommentar: Totalschaden konkret
        return wba + mwst + nutzung + kostenpausch + gutachter + zusatz  # Kommentar: WBA + MwSt + Nebenkosten
    if variant == "TOTAL_ERSATZ":  # Kommentar: Totalschaden Ersatzbeschaffung
        return wba + mwst + nutzung + kostenpausch + gutachter + zusatz  # Kommentar: WBA + MwSt + Nebenkosten
    return reparatur + mwst + wertminderung + nutzung + kostenpausch + gutachter + zusatz + wba  # Kommentar: Fallback


def prepare_data_for_template(daten: dict, auswahl: str, steuerstatus: str, zus_bez: str = "", zus_betrag: str = "") -> dict:  # Kommentar: Public Funktion – bereitet Daten inkl. Summe vor
    daten = daten_defaults(daten)  # Kommentar: Defaults
    daten["ABRECHNUNGSART"] = auswahl  # Kommentar: Auswahl speichern
    daten["ZUSATZKOSTEN_BEZEICHNUNG"] = (zus_bez or "").strip()  # Kommentar: Zusatzbezeichnung
    daten["ZUSATZKOSTEN_BETRAG"] = (zus_betrag or "").strip()  # Kommentar: Zusatzbetrag
    jetzt = datetime.now()  # Kommentar: jetzt
    daten["HEUTDATUM"] = jetzt.strftime("%d.%m.%Y")  # Kommentar: heutiges Datum
    daten["FRIST_DATUM"] = (jetzt + timedelta(days=14)).strftime("%d.%m.%Y")  # Kommentar: Frist
    daten = setze_vorsteuer_text(daten, steuerstatus)  # Kommentar: Vorsteuertext setzen
    daten = mwst_leeren_wenn_noetig(daten, auswahl, steuerstatus)  # Kommentar: MwSt ggf leeren

    variant = variante_key(auswahl)  # Kommentar: Variante
    reparatur = euro_zu_float(daten.get("REPARATURKOSTEN", ""))  # Kommentar: float
    mwst = euro_zu_float(daten.get("MWST_BETRAG", ""))  # Kommentar: float
    wertminderung = euro_zu_float(daten.get("WERTMINDERUNG", ""))  # Kommentar: float
    nutzung = euro_zu_float(daten.get("NUTZUNGSAUSFALL", ""))  # Kommentar: float
    kostenpausch = euro_zu_float(daten.get("KOSTENPAUSCHALE", ""))  # Kommentar: float
    gutachter = euro_zu_float(daten.get("GUTACHTERKOSTEN", ""))  # Kommentar: float
    zusatz = euro_zu_float(daten.get("ZUSATZKOSTEN_BETRAG", ""))  # Kommentar: float
    wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))  # Kommentar: WBW
    rest = euro_zu_float(daten.get("RESTWERT", ""))  # Kommentar: Restwert
    wba = max(wbw - rest, 0.0)  # Kommentar: Wiederbeschaffungsaufwand

    if variant == "REGEL_130":  # Kommentar: 130% -> Wertminderung raus
        wertminderung = 0.0  # Kommentar: 0
        daten["WERTMINDERUNG"] = ""  # Kommentar: leeren

    if variant in ["TOTAL_FIKTIV", "TOTAL_KONKRET", "TOTAL_ERSATZ"]:  # Kommentar: Totalschaden -> Reparaturkosten typischerweise raus
        reparatur = 0.0  # Kommentar: 0
        daten["REPARATURKOSTEN"] = ""  # Kommentar: leeren
        if wba > 0:  # Kommentar: WBA vorhanden
            daten["WIEDERBESCHAFFUNGSAUFWAND"] = float_zu_euro(wba)  # Kommentar: setzen

    summe = summe_tabelle_berechnen(variant, reparatur, mwst, wertminderung, nutzung, kostenpausch, gutachter, zusatz, wba)  # Kommentar: Summe rechnen
    daten["KOSTENSUMME_X"] = float_zu_euro(summe) if summe > 0 else ""  # Kommentar: Summe (für Word)
    daten["GESAMTSUMME"] = daten["KOSTENSUMME_X"]  # Kommentar: identisch (Fallback)

    # Kommentar: Formatierung der Felder
    if reparatur > 0:  # Kommentar: falls gesetzt
        daten["REPARATURKOSTEN"] = float_zu_euro(reparatur)  # Kommentar: format
    if mwst > 0 and daten.get("MWST_BETRAG", "") != "":  # Kommentar: MwSt soll angezeigt werden?
        daten["MWST_BETRAG"] = float_zu_euro(mwst)  # Kommentar: format
    if wertminderung > 0:  # Kommentar: Wertminderung
        daten["WERTMINDERUNG"] = float_zu_euro(wertminderung)  # Kommentar: format
    if nutzung > 0:  # Kommentar: Nutzung
        daten["NUTZUNGSAUSFALL"] = float_zu_euro(nutzung)  # Kommentar: format
    if kostenpausch > 0:  # Kommentar: Pauschale
        daten["KOSTENPAUSCHALE"] = float_zu_euro(kostenpausch)  # Kommentar: format
    if gutachter > 0:  # Kommentar: Gutachter
        daten["GUTACHTERKOSTEN"] = float_zu_euro(gutachter)  # Kommentar: format
    if zusatz > 0:  # Kommentar: Zusatz
        daten["ZUSATZKOSTEN_BETRAG"] = float_zu_euro(zusatz)  # Kommentar: format

    # Kommentar: Debugfelder (nur für UI / optional in Word)
    daten["DEBUG_PROGRAMM2_VERSION"] = PROGRAMM_2_VERSION  # Kommentar: Version sichtbar machen
    daten["DEBUG_SUMME_TEILE"] = f"variant={variant} reparatur={reparatur} mwst={mwst} wm={wertminderung} nutzung={nutzung} pausch={kostenpausch} gutachter={gutachter} zusatz={zusatz} wba={wba} => summe={summe}"  # Kommentar: Debugstring
    return daten  # Kommentar: Return


def word_aus_vorlage_erstellen(daten: dict, vorlage_pfad: str, ziel_pfad: str) -> None:  # Kommentar: DOCX rendern
    doc = DocxTemplate(vorlage_pfad)  # Kommentar: Template laden
    os.makedirs(os.path.dirname(ziel_pfad), exist_ok=True)  # Kommentar: Ordner sicher
    doc.render(daten)  # Kommentar: render (alle Keys verfügbar)
    doc.save(ziel_pfad)  # Kommentar: speichern


def ki_datei_verarbeiten(pfad_ki_txt: str, vorlage_pfad: str, auswahl: str, steuerstatus: str, zus_bez: str, zus_betrag: str) -> str:  # Kommentar: KI-Datei -> DOCX
    with open(pfad_ki_txt, "r", encoding="utf-8") as f:  # Kommentar: öffnen
        ki_text = f.read()  # Kommentar: lesen
    daten = json_aus_ki_antwort_parsen(ki_text)  # Kommentar: JSON parsen
    daten = prepare_data_for_template(daten, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: nachbearbeiten
    datum_str = datetime.now().strftime("%Y%m%d_%H%M%S")  # Kommentar: timestamp
    out_name = f"schreiben_{datum_str}.docx"  # Kommentar: name
    out_path = os.path.join(AUSGANGS_ORDNER, out_name)  # Kommentar: pfad
    word_aus_vorlage_erstellen(daten, vorlage_pfad, out_path)  # Kommentar: rendern
    return out_path  # Kommentar: return pfad


def main(pfad_ki_txt: str = None, vorlage_pfad: str | None = None, auswahl: str = "", steuerstatus: str = "", zus_bez: str = "", zus_betrag: str = "") -> str:  # Kommentar: Main für App
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: Ordner sicher
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: Ordner sicher
    if vorlage_pfad is None:  # Kommentar: Vorlage nötig
        raise ValueError("vorlage_pfad muss übergeben werden (Word-Vorlage .docx).")  # Kommentar: Fehler
    if pfad_ki_txt is None:  # Kommentar: wenn nicht gegeben
        files = [os.path.join(KI_ANTWORT_ORDNER, f) for f in os.listdir(KI_ANTWORT_ORDNER) if f.endswith("_ki.txt")]  # Kommentar: suchen
        if not files:  # Kommentar: keine?
            raise FileNotFoundError("Keine KI-Datei gefunden.")  # Kommentar: Fehler
        pfad_ki_txt = max(files, key=os.path.getmtime)  # Kommentar: neueste
    if not os.path.isfile(pfad_ki_txt):  # Kommentar: existiert?
        raise FileNotFoundError(f"KI-Datei existiert nicht: {pfad_ki_txt}")  # Kommentar: Fehler
    if not os.path.isfile(vorlage_pfad):  # Kommentar: Vorlage existiert?
        raise FileNotFoundError(f"Vorlage existiert nicht: {vorlage_pfad}")  # Kommentar: Fehler
    return ki_datei_verarbeiten(pfad_ki_txt, vorlage_pfad, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: run


if __name__ == "__main__":  # Kommentar: Direktstart
    main()  # Kommentar: aufrufen
