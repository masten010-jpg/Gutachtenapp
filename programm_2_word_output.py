# programm_2_word_output.py  # Kommentar: Programm 2 – KI-JSON (oder korrigierte Daten) -> Word Schreiben

import os  # Kommentar: Dateipfade/Ordner
import json  # Kommentar: JSON parsing
from datetime import datetime, timedelta  # Kommentar: Datum/Fristen
from docxtpl import DocxTemplate  # Kommentar: Word Template Rendering
from programm_1_ki_input import KI_ANTWORT_ORDNER, BASE_DIR  # Kommentar: Ordnerpfade aus Programm 1

AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # Kommentar: DOCX Output Ordner
JSON_START_MARKER = "JSON_START"  # Kommentar: Marker Start
JSON_END_MARKER = "JSON_END"  # Kommentar: Marker Ende


def json_aus_ki_antwort_parsen(ki_text: str) -> dict:  # Kommentar: JSON Block aus KI Text extrahieren
    start_idx = ki_text.find(JSON_START_MARKER)  # Kommentar: Startmarker finden
    end_idx = ki_text.find(JSON_END_MARKER)  # Kommentar: Endmarker finden
    if start_idx == -1 or end_idx == -1:  # Kommentar: Marker fehlen?
        raise ValueError("JSON_START oder JSON_END nicht gefunden.")  # Kommentar: Fehler
    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()  # Kommentar: Bereich ausschneiden
    json_roh = json_roh.replace("```json", "").replace("```", "").strip()  # Kommentar: Codefences entfernen
    first_brace = json_roh.find("{")  # Kommentar: Erste geschweifte Klammer finden
    last_brace = json_roh.rfind("}")  # Kommentar: Letzte geschweifte Klammer finden
    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:  # Kommentar: Ungültig?
        raise ValueError("Kein gültiger JSON-Block in KI-Antwort.")  # Kommentar: Fehler
    json_clean = json_roh[first_brace:last_brace + 1]  # Kommentar: JSON sauber ausschneiden
    json_clean = json_clean.replace(",\n}", "\n}").replace(",}", "}")  # Kommentar: Häufige KI-Kommafehler glätten
    return json.loads(json_clean)  # Kommentar: JSON laden


def euro_zu_float(text) -> float:  # Kommentar: Euro-String robust -> float
    if isinstance(text, (int, float)):  # Kommentar: Schon Zahl?
        return float(text)  # Kommentar: Cast
    if not text:  # Kommentar: leer?
        return 0.0  # Kommentar: 0
    t = str(text)  # Kommentar: in String
    t = t.replace("€", "").replace("EUR", "").replace("Euro", "")  # Kommentar: Währung entfernen
    t = t.replace("\u00a0", " ").strip()  # Kommentar: NBSP entfernen
    t = t.replace(" ", "")  # Kommentar: Spaces entfernen
    filtered = []  # Kommentar: erlaubte Zeichen
    for ch in t:  # Kommentar: iterieren
        if ch.isdigit() or ch in [",", ".", "+", "-"]:  # Kommentar: erlaubte Zeichen
            filtered.append(ch)  # Kommentar: sammeln
    t = "".join(filtered)  # Kommentar: wieder zusammensetzen
    if not t:  # Kommentar: immer noch leer
        return 0.0  # Kommentar: 0
    if "." in t and "," in t:  # Kommentar: Format 1.234,56
        t = t.replace(".", "").replace(",", ".")  # Kommentar: tausender entfernen, komma->punkt
    elif "," in t:  # Kommentar: Format 1234,56
        t = t.replace(",", ".")  # Kommentar: komma->punkt
    try:  # Kommentar: parse versuchen
        return float(t)  # Kommentar: float
    except ValueError:  # Kommentar: parse fail
        return 0.0  # Kommentar: fallback


def float_zu_euro(betrag: float) -> str:  # Kommentar: float -> deutsches Euroformat
    s = f"{betrag:,.2f}"  # Kommentar: US-Format
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")  # Kommentar: Tausender/Punkt/Komma umstellen
    return s + " €"  # Kommentar: Eurozeichen


def daten_defaults(daten: dict) -> dict:  # Kommentar: Setzt sicher alle Standardfelder
    keys = [  # Kommentar: Felder, die in Vorlagen vorkommen können
        "MANDANT_VORNAME", "MANDANT_NACHNAME", "MANDANT_NAME",  # Kommentar: Mandant
        "MANDANT_STRASSE", "MANDANT_PLZ_ORT",  # Kommentar: Adresse
        "UNFALL_DATUM", "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE",  # Kommentar: Unfall
        "FAHRZEUGTYP", "KENNZEICHEN", "FAHRZEUG_KENNZEICHEN",  # Kommentar: Fahrzeug
        "POLIZEIAKTE_NUMMER", "SCHADENSNUMMER", "AKTENZEICHEN",  # Kommentar: Akten
        "SCHADENHERGANG",  # Kommentar: Text
        "REPARATURKOSTEN", "WERTMINDERUNG", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN",  # Kommentar: Kosten
        "NUTZUNGSAUSFALL", "MWST_BETRAG",  # Kommentar: Nutzung/MwSt
        "WIEDERBESCHAFFUNGSWERT", "RESTWERT", "WIEDERBESCHAFFUNGSAUFWAND",  # Kommentar: Totalschaden
        "FRIST_DATUM", "HEUTDATUM",  # Kommentar: Datum
        "ABRECHNUNGSART", "STEUERSTATUS",  # Kommentar: Auswahl
        "VORSTEUERBERECHTIGUNG",  # Kommentar: Text für Word
        "ZUSATZKOSTEN_BEZEICHNUNG", "ZUSATZKOSTEN_BETRAG",  # Kommentar: Zusatzkosten
        "KOSTENSUMME_X", "GESAMTSUMME",  # Kommentar: Summen
    ]  # Kommentar: Ende keys
    for k in keys:  # Kommentar: Iteration
        daten.setdefault(k, "")  # Kommentar: Default
    return daten  # Kommentar: Return


def setze_vorsteuer_text(daten: dict, steuerstatus: str) -> dict:  # Kommentar: Setzt {{VORSTEUERBERECHTIGUNG}} als reinen Text
    daten["STEUERSTATUS"] = steuerstatus  # Kommentar: Steuerstatus speichern
    if steuerstatus == "vorsteuerabzugsberechtigt":  # Kommentar: Vorsteuer
        daten["VORSTEUERBERECHTIGUNG"] = "vorsteuerberechtigt"  # Kommentar: Text
    else:  # Kommentar: Nicht Vorsteuer
        daten["VORSTEUERBERECHTIGUNG"] = "nicht vorsteuerberechtigt"  # Kommentar: Text
    return daten  # Kommentar: Return


def mwst_anzeigen_oder_leeren(daten: dict, auswahl: str, steuerstatus: str) -> dict:  # Kommentar: MWST_BETRAG je Variante/Status
    norm = (auswahl or "").lower()  # Kommentar: normalize
    is_fiktiv = "fiktive abrechnung" in norm or ("totalschaden" in norm and "fiktiv" in norm)  # Kommentar: fiktive Fälle
    if is_fiktiv:  # Kommentar: fiktiv -> MwSt leer
        daten["MWST_BETRAG"] = ""  # Kommentar: leeren
        return daten  # Kommentar: Return
    if steuerstatus == "vorsteuerabzugsberechtigt":  # Kommentar: Vorsteuer -> MwSt leer
        daten["MWST_BETRAG"] = ""  # Kommentar: leeren
        return daten  # Kommentar: Return
    return daten  # Kommentar: sonst so lassen (kann aus KI oder Korrektur kommen)


def variante_key(auswahl: str) -> str:  # Kommentar: Mappt UI-Auswahl auf interne Variante
    if auswahl == "Fiktive Abrechnung (Reparaturschaden)":  # Kommentar: Fall 1
        return "FAKTISCH_FIKTIV_REP"  # Kommentar: Key
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


def summe_tabelle_berechnen(  # Kommentar: Summiert so, wie deine Kostentabelle pro Variante gedacht ist
    variant: str,  # Kommentar: interne Variante
    reparatur: float,  # Kommentar: Reparaturkosten
    mwst: float,  # Kommentar: MwSt (0 wenn leer)
    wertminderung: float,  # Kommentar: Wertminderung
    nutzung: float,  # Kommentar: Nutzungsausfall (Betrag)
    kostenpausch: float,  # Kommentar: Kostenpauschale
    gutachter: float,  # Kommentar: Gutachterkosten
    zusatz: float,  # Kommentar: Zusatzkosten
    wbw_minus_rest: float,  # Kommentar: Wiederbeschaffungsaufwand
) -> float:  # Kommentar: Ergebnis-Summe
    # Kommentar: Fiktive Abrechnung (Reparaturschaden) -> Netto, keine MwSt
    if variant == "FAKTISCH_FIKTIV_REP":  # Kommentar: Fall fiktiv Reparaturschaden
        return reparatur + wertminderung + nutzung + kostenpausch + gutachter + zusatz  # Kommentar: Summe

    # Kommentar: Konkrete Abrechnung < WBW -> Brutto + MwSt + Wertminderung + Nutzung + Zusatz + Nebenkosten
    if variant == "KONKRET_UNTER_WBW":  # Kommentar: Fall konkret unter WBW
        return reparatur + mwst + wertminderung + nutzung + kostenpausch + gutachter + zusatz  # Kommentar: Summe

    # Kommentar: 130%-Regelung -> keine Wertminderung, MwSt nur wenn nicht vorsteuer und vorhanden
    if variant == "REGEL_130":  # Kommentar: Fall 130%
        return reparatur + mwst + nutzung + kostenpausch + gutachter + zusatz  # Kommentar: Summe ohne Wertminderung

    # Kommentar: Totalschaden fiktiv -> Basis WBW-REST (ohne MwSt) + Nebenkosten + Zusatz + Nutzung
    if variant == "TOTAL_FIKTIV":  # Kommentar: Fall Totalschaden fiktiv
        return wbw_minus_rest + nutzung + kostenpausch + gutachter + zusatz  # Kommentar: Summe

    # Kommentar: Totalschaden konkret -> WBW-REST + (ggf. MwSt begrenzt) + Nebenkosten + Zusatz + Nutzung
    if variant == "TOTAL_KONKRET":  # Kommentar: Fall Totalschaden konkret
        return wbw_minus_rest + mwst + nutzung + kostenpausch + gutachter + zusatz  # Kommentar: Summe

    # Kommentar: Totalschaden Ersatzbeschaffung -> WBW-REST + MwSt (bis WBW-Grenze) + Nebenkosten + Zusatz + Nutzung
    if variant == "TOTAL_ERSATZ":  # Kommentar: Fall Totalschaden Ersatzbeschaffung
        return wbw_minus_rest + mwst + nutzung + kostenpausch + gutachter + zusatz  # Kommentar: Summe

    # Kommentar: Fallback -> addiere alles
    return reparatur + mwst + wertminderung + nutzung + kostenpausch + gutachter + zusatz + wbw_minus_rest  # Kommentar: Safe fallback


def berechne_summen_und_format(daten: dict, auswahl: str, steuerstatus: str) -> dict:  # Kommentar: Summen + Geldformatierung
    variant = variante_key(auswahl)  # Kommentar: interne Variante bestimmen

    # Kommentar: Zahlenwerte als float holen
    reparatur = euro_zu_float(daten.get("REPARATURKOSTEN", ""))  # Kommentar: Reparatur
    mwst = euro_zu_float(daten.get("MWST_BETRAG", ""))  # Kommentar: MwSt
    wertminderung = euro_zu_float(daten.get("WERTMINDERUNG", ""))  # Kommentar: Wertminderung
    nutzung = euro_zu_float(daten.get("NUTZUNGSAUSFALL", ""))  # Kommentar: Nutzungsausfall
    kostenpausch = euro_zu_float(daten.get("KOSTENPAUSCHALE", ""))  # Kommentar: Pauschale
    gutachter = euro_zu_float(daten.get("GUTACHTERKOSTEN", ""))  # Kommentar: Gutachter
    zusatz = euro_zu_float(daten.get("ZUSATZKOSTEN_BETRAG", ""))  # Kommentar: Zusatz

    wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))  # Kommentar: WBW
    restwert = euro_zu_float(daten.get("RESTWERT", ""))  # Kommentar: Restwert
    wbw_minus_rest = max(wbw - restwert, 0.0)  # Kommentar: Wiederbeschaffungsaufwand

    # Kommentar: 130%-Regelung -> Wertminderung immer deaktivieren
    if variant == "REGEL_130":  # Kommentar: 130%-Fall
        wertminderung = 0.0  # Kommentar: Wertminderung auf 0
        daten["WERTMINDERUNG"] = ""  # Kommentar: Feld leeren

    # Kommentar: MwSt-Handling: wenn MwSt im Feld leer ist, dann ist mwst float ohnehin 0
    # Kommentar: Für vorsteuerabzugsberechtigt wird MWST_BETRAG vorher geleert -> mwst 0

    # Kommentar: Totalschaden: Reparaturkosten gehören meist nicht in die Tabelle -> optional leeren
    if variant in ["TOTAL_FIKTIV", "TOTAL_KONKRET", "TOTAL_ERSATZ"]:  # Kommentar: Totalschaden-Fälle
        daten["REPARATURKOSTEN"] = ""  # Kommentar: Reparaturkosten leeren (typischerweise nicht Teil Totalschaden)
        reparatur = 0.0  # Kommentar: Für Summen auf 0 setzen
        if wbw_minus_rest > 0:  # Kommentar: wenn sinnvoll
            daten["WIEDERBESCHAFFUNGSAUFWAND"] = float_zu_euro(wbw_minus_rest)  # Kommentar: setzen

    # Kommentar: Summe berechnen passend zur Variante
    summe = summe_tabelle_berechnen(  # Kommentar: Summenfunktion aufrufen
        variant=variant,  # Kommentar: Variante
        reparatur=reparatur,  # Kommentar: Reparatur
        mwst=mwst,  # Kommentar: MwSt
        wertminderung=wertminderung,  # Kommentar: Wertminderung
        nutzung=nutzung,  # Kommentar: Nutzung
        kostenpausch=kostenpausch,  # Kommentar: Pauschale
        gutachter=gutachter,  # Kommentar: Gutachter
        zusatz=zusatz,  # Kommentar: Zusatz
        wbw_minus_rest=wbw_minus_rest,  # Kommentar: WBW-Rest
    )  # Kommentar: Ende Summenfunktion

    # Kommentar: Summenfelder für Word setzen
    daten["KOSTENSUMME_X"] = float_zu_euro(summe) if summe > 0 else ""  # Kommentar: Vorläufige Summe
    daten["GESAMTSUMME"] = daten["KOSTENSUMME_X"]  # Kommentar: Identisch halten als Fallback

    # Kommentar: Geldfelder formatiert zurückschreiben
    if reparatur > 0:  # Kommentar: Reparatur vorhanden?
        daten["REPARATURKOSTEN"] = float_zu_euro(reparatur)  # Kommentar: format
    if mwst > 0 and daten.get("MWST_BETRAG", "") != "":  # Kommentar: MwSt soll angezeigt werden?
        daten["MWST_BETRAG"] = float_zu_euro(mwst)  # Kommentar: format
    if wertminderung > 0:  # Kommentar: Wertminderung vorhanden?
        daten["WERTMINDERUNG"] = float_zu_euro(wertminderung)  # Kommentar: format
    if nutzung > 0:  # Kommentar: Nutzung vorhanden?
        daten["NUTZUNGSAUSFALL"] = float_zu_euro(nutzung)  # Kommentar: format
    if kostenpausch > 0:  # Kommentar: Pauschale vorhanden?
        daten["KOSTENPAUSCHALE"] = float_zu_euro(kostenpausch)  # Kommentar: format
    if gutachter > 0:  # Kommentar: Gutachter vorhanden?
        daten["GUTACHTERKOSTEN"] = float_zu_euro(gutachter)  # Kommentar: format
    if zusatz > 0:  # Kommentar: Zusatz vorhanden?
        daten["ZUSATZKOSTEN_BETRAG"] = float_zu_euro(zusatz)  # Kommentar: format

    return daten  # Kommentar: Return


def daten_nachbearbeiten(daten: dict, auswahl: str, steuerstatus: str, zus_bez: str, zus_betrag: str) -> dict:  # Kommentar: Haupt-Nachbearbeitung
    daten = daten_defaults(daten)  # Kommentar: Defaults setzen
    daten["ABRECHNUNGSART"] = auswahl  # Kommentar: Auswahl speichern
    daten["ZUSATZKOSTEN_BEZEICHNUNG"] = (zus_bez or "").strip()  # Kommentar: Zusatzbezeichnung
    daten["ZUSATZKOSTEN_BETRAG"] = (zus_betrag or "").strip()  # Kommentar: Zusatzbetrag

    jetzt = datetime.now()  # Kommentar: Jetzt
    daten["HEUTDATUM"] = jetzt.strftime("%d.%m.%Y")  # Kommentar: Heutdatum
    daten["FRIST_DATUM"] = (jetzt + timedelta(days=14)).strftime("%d.%m.%Y")  # Kommentar: Frist

    daten = setze_vorsteuer_text(daten, steuerstatus)  # Kommentar: {{VORSTEUERBERECHTIGUNG}} setzen
    daten = mwst_anzeigen_oder_leeren(daten, auswahl, steuerstatus)  # Kommentar: {{MWST_BETRAG}} ggf leeren
    daten = berechne_summen_und_format(daten, auswahl, steuerstatus)  # Kommentar: Summen und Format
    return daten  # Kommentar: Return


def word_aus_vorlage_erstellen(daten: dict, vorlage_pfad: str, ziel_pfad: str) -> None:  # Kommentar: DOCX erstellen
    doc = DocxTemplate(vorlage_pfad)  # Kommentar: Template laden
    os.makedirs(os.path.dirname(ziel_pfad), exist_ok=True)  # Kommentar: Ordner sicher
    doc.render(daten)  # Kommentar: Rendern
    doc.save(ziel_pfad)  # Kommentar: Speichern


def generate_from_data(daten: dict, vorlage_pfad: str, auswahl: str, steuerstatus: str, zus_bez: str = "", zus_betrag: str = "") -> str:  # Kommentar: DOCX direkt aus Daten
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: Ordner sicherstellen
    daten = daten_nachbearbeiten(daten, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: Nachbearbeitung
    datum_str = datetime.now().strftime("%Y%m%d_%H%M%S")  # Kommentar: Timestamp
    ausgabe_name = f"korrigiert_schreiben_{datum_str}.docx"  # Kommentar: Name
    ausgabe_pfad = os.path.join(AUSGANGS_ORDNER, ausgabe_name)  # Kommentar: Pfad
    word_aus_vorlage_erstellen(daten, vorlage_pfad, ausgabe_pfad)  # Kommentar: Erstellen
    return ausgabe_pfad  # Kommentar: Rückgabe


def ki_datei_verarbeiten(pfad_ki_txt: str, vorlage_pfad: str, auswahl: str, steuerstatus: str, zus_bez: str, zus_betrag: str) -> str:  # Kommentar: KI-Datei -> DOCX
    with open(pfad_ki_txt, "r", encoding="utf-8") as f:  # Kommentar: Datei öffnen
        ki_text = f.read()  # Kommentar: Text lesen
    daten = json_aus_ki_antwort_parsen(ki_text)  # Kommentar: JSON parsen
    return generate_from_data(daten, vorlage_pfad, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: DOCX erzeugen


def main(pfad_ki_txt: str = None, vorlage_pfad: str | None = None, auswahl: str = "", steuerstatus: str = "", zus_bez: str = "", zus_betrag: str = "") -> str:  # Kommentar: Main kompatibel zur App
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: KI Ordner
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: Output Ordner
    if vorlage_pfad is None:  # Kommentar: Vorlage nötig
        raise ValueError("vorlage_pfad muss übergeben werden (Word-Vorlage .docx).")  # Kommentar: Fehler
    if pfad_ki_txt is None:  # Kommentar: Wenn keine KI-Datei angegeben
        dateien = [os.path.join(KI_ANTWORT_ORDNER, f) for f in os.listdir(KI_ANTWORT_ORDNER) if f.endswith("_ki.txt")]  # Kommentar: Dateien suchen
        if not dateien:  # Kommentar: keine gefunden
            raise FileNotFoundError("Keine KI-Datei gefunden.")  # Kommentar: Fehler
        pfad_ki_txt = max(dateien, key=os.path.getmtime)  # Kommentar: neueste Datei
    if not os.path.isfile(pfad_ki_txt):  # Kommentar: existiert?
       
