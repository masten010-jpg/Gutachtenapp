# programm_2_word_output.py  # Kommentar: Dateiname dieses Moduls

import os  # Kommentar: Modul für Pfad- und Dateisystemoperationen importieren
import json  # Kommentar: Modul zum Parsen und Schreiben von JSON importieren
from datetime import datetime, timedelta  # Kommentar: Datum/Zeit-Werkzeuge importieren
from docxtpl import DocxTemplate  # Kommentar: Bibliothek zum Füllen von Word-Vorlagen importieren
from programm_1_ki_input import KI_ANTWORT_ORDNER, BASE_DIR  # Kommentar: Pfadangaben aus programm_1_ki_input übernehmen

AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # Kommentar: Ordner für fertige Anwaltsschreiben definieren
JSON_START_MARKER = "JSON_START"  # Kommentar: Marker, an dem der JSON-Block in der KI-Antwort beginnt
JSON_END_MARKER = "JSON_END"  # Kommentar: Marker, an dem der JSON-Block in der KI-Antwort endet


def json_aus_ki_antwort_parsen(ki_text: str) -> dict:  # Kommentar: JSON-Block aus der KI-Antwort ausschneiden und parsen
    start_idx = ki_text.find(JSON_START_MARKER)  # Kommentar: Index des JSON_START-Markers im Text suchen
    end_idx = ki_text.find(JSON_END_MARKER)  # Kommentar: Index des JSON_END-Markers im Text suchen
    if start_idx == -1 or end_idx == -1:  # Kommentar: Prüfen, ob einer der Marker fehlt
        raise ValueError("JSON_START oder JSON_END nicht gefunden.")  # Kommentar: Fehler werfen, wenn Marker fehlen

    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()  # Kommentar: Roh-JSON-Text zwischen den Markern ausschneiden
    json_roh = json_roh.replace("```json", "").replace("```", "").strip()  # Kommentar: Mögliche Markdown-Backticks entfernen

    first_brace = json_roh.find("{")  # Kommentar: Position der ersten geschweiften Klammer ermitteln
    last_brace = json_roh.rfind("}")  # Kommentar: Position der letzten geschweiften Klammer ermitteln
    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:  # Kommentar: Prüfen, ob ein gültiger JSON-Bereich existiert
        raise ValueError("Kein gültiger JSON-Block in KI-Antwort.")  # Kommentar: Fehler werfen, wenn kein gültiger JSON-Block gefunden wird

    json_clean = json_roh[first_brace:last_brace + 1]  # Kommentar: Nur den Bereich zwischen erster und letzter Klammer übernehmen
    json_clean = json_clean.replace(",\n}", "\n}").replace(",}", "}")  # Kommentar: Überflüssige Kommas vor schließender Klammer entfernen
    return json.loads(json_clean)  # Kommentar: JSON-Text in Python-Dict umwandeln und zurückgeben


def euro_zu_float(text) -> float:  # Kommentar: Funktion, um Euro-Beträge robust in float umzuwandeln
    if isinstance(text, (int, float)):  # Kommentar: Wenn bereits eine Zahl übergeben wurde
        return float(text)  # Kommentar: Zahl als float zurückgeben
    if not text:  # Kommentar: Wenn der Text leer oder None ist
        return 0.0  # Kommentar: 0.0 zurückgeben

    t = str(text)  # Kommentar: Sicherstellen, dass wir mit einem String arbeiten
    t = t.replace("€", "").replace("EUR", "").replace("Euro", "")  # Kommentar: Währungssymbole entfernen
    t = t.replace("\u00a0", " ").strip()  # Kommentar: Geschützte Leerzeichen ersetzen und trimmen
    t = t.replace(" ", "")  # Kommentar: Alle Leerzeichen entfernen

    filtered = []  # Kommentar: Liste für erlaubte Zeichen initialisieren
    for ch in t:  # Kommentar: Über alle Zeichen iterieren
        if ch.isdigit() or ch in [",", ".", "+", "-"]:  # Kommentar: Nur Ziffern, Punkt, Komma und Vorzeichen zulassen
            filtered.append(ch)  # Kommentar: Erlaubtes Zeichen in Liste aufnehmen
    t = "".join(filtered)  # Kommentar: Liste zu String zusammenfügen

    if not t:  # Kommentar: Wenn nach der Filterung nichts übrig bleibt
        return 0.0  # Kommentar: 0.0 zurückgeben

    if "." in t and "," in t:  # Kommentar: Wenn sowohl Punkt als auch Komma vorkommen (z.B. "1.234,56")
        t = t.replace(".", "").replace(",", ".")  # Kommentar: Punkt als Tausendertrenner entfernen, Komma in Dezimalpunkt umwandeln
    elif "," in t:  # Kommentar: Wenn nur Komma vorkommt (z.B. "123,45")
        t = t.replace(",", ".")  # Kommentar: Komma in Dezimalpunkt umwandeln

    try:  # Kommentar: Versuch, den bereinigten String in float zu konvertieren
        return float(t)  # Kommentar: Konvertierten float zurückgeben
    except ValueError:  # Kommentar: Falls Konvertierung fehlschlägt
        return 0.0  # Kommentar: Sicherheitsfallback 0.0 zurückgeben


def float_zu_euro(betrag: float) -> str:  # Kommentar: Funktion, um eine float-Zahl als deutschen Euro-Betrag zu formatieren
    s = f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # Kommentar: Zahl mit 2 Nachkommastellen formatieren und Punkt/Komma tauschen
    return s + " €"  # Kommentar: Euro-Symbol anhängen und zurückgeben


def extrahiere_platzhalter(vorlage_pfad):  # Kommentar: Platzhalter aus einer Word-Vorlage auslesen
    doc = DocxTemplate(vorlage_pfad)  # Kommentar: Word-Vorlage mit DocxTemplate öffnen
    return doc.get_undeclared_template_variables()  # Kommentar: Noch nicht gesetzte Template-Variablen (Platzhalter) zurückgeben


def daten_defaults(daten: dict):  # Kommentar: Sicherstellen, dass alle erwarteten Schlüssel im Daten-Dict existieren
    keys = [  # Kommentar: Liste aller genutzten Keys definieren
        "MANDANT_VORNAME", "MANDANT_NACHNAME", "MANDANT_NAME",
        "MANDANT_STRASSE", "MANDANT_PLZ_ORT",
        "UNFALL_DATUM", "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE",
        "FAHRZEUGTYP", "KENNZEICHEN", "FAHRZEUG_KENNZEICHEN",
        "POLIZEIAKTE_NUMMER", "SCHADENSNUMMER", "AKTENZEICHEN",
        "SCHADENHERGANG",
        "REPARATURKOSTEN", "WERTMINDERUNG", "KOSTENPAUSCHALE",
        "GUTACHTERKOSTEN", "NUTZUNGSAUSFALL", "MWST_BETRAG",
        "WIEDERBESCHAFFUNGSWERT", "RESTWERT",
        "FRIST_DATUM", "HEUTDATUM",
        "ABRECHNUNGSART", "STEUERSTATUS",
        "WIEDERBESCHAFFUNGSAUFWAND",
        "ERSATZBESCHAFFUNG_MWST",
        "ZUSATZKOSTEN_BEZEICHNUNG", "ZUSATZKOSTEN_BETRAG",
        "KOSTENSUMME_X", "GESAMTSUMME",
    ]
    for k in keys:  # Kommentar: Über alle erwarteten Keys iterieren
        daten.setdefault(k, "")  # Kommentar: Wenn Key nicht existiert, mit leerem String vorbelegen
    return daten  # Kommentar: Ergänztes Daten-Dict zurückgeben


def _bestimme_kostenfelder(auswahl: str):  # Kommentar: Je nach Abrechnungsvariante bestimmen, welche Felder in der Kostentabelle summiert werden
    norm = (auswahl or "").lower()  # Kommentar: Auswahl in Kleinbuchstaben umwandeln, um robust zu vergleichen

    if "fiktive abrechnung" in norm and "reparatur" in norm:  # Kommentar: Fall "Fiktive Abrechnung (Reparaturschaden)"
        return [
            "REPARATURKOSTEN",
            "WERTMINDERUNG",
            "NUTZUNGSAUSFALL",
            "KOSTENPAUSCHALE",
            "GUTACHTERKOSTEN",
        ]  # Kommentar: Relevante Felder für diese Kostentabelle zurückgeben

    if "konkrete abrechnung" in norm:  # Kommentar: Fall "Konkrete Abrechnung < WBW"
        return [
            "REPARATURKOSTEN",
            "MWST_BETRAG",
            "WERTMINDERUNG",
            "NUTZUNGSAUSFALL",
            "KOSTENPAUSCHALE",
            "GUTACHTERKOSTEN",
        ]  # Kommentar: Hier gehört die MwSt auch in die Tabelle

    if "130" in norm:  # Kommentar: Fall "130%-Regelung"
        return [
            "REPARATURKOSTEN",
            "MWST_BETRAG",
            "NUTZUNGSAUSFALL",
            "KOSTENPAUSCHALE",
            "GUTACHTERKOSTEN",
        ]  # Kommentar: Wertminderung ist hier ausgeschlossen

    if "totalschaden fiktiv" in norm:  # Kommentar: Fall "Totalschaden fiktiv"
        return [
            "WIEDERBESCHAFFUNGSAUFWAND",
            "KOSTENPAUSCHALE",
            "GUTACHTERKOSTEN",
            "NUTZUNGSAUSFALL",
        ]  # Kommentar: Totalschaden fiktiv – Basis ist Wiederbeschaffungsaufwand

    if "totalschaden konkret" in norm or "ersatzbeschaffung" in norm:  # Kommentar: Fall "Totalschaden konkret" oder "Ersatzbeschaffung"
        return [
            "WIEDERBESCHAFFUNGSAUFWAND",
            "ERSATZBESCHAFFUNG_MWST",
            "KOSTENPAUSCHALE",
            "GUTACHTERKOSTEN",
            "NUTZUNGSAUSFALL",
        ]  # Kommentar: Hier wird zusätzlich die MwSt aus der Ersatzbeschaffung berücksichtigt

    return [
        "REPARATURKOSTEN",
        "WERTMINDERUNG",
        "KOSTENPAUSCHALE",
        "GUTACHTERKOSTEN",
        "NUTZUNGSAUSFALL",
    ]  # Kommentar: Fallback – klassischer Reparaturschaden


def anwenden_abrechnungslogik(daten: dict, auswahl: str, steuerstatus: str):  # Kommentar: Zentrale Funktion für Formatierung und Summenlogik
    daten["ABRECHNUNGSART"] = auswahl  # Kommentar: Abrechnungsart in den Daten speichern
    daten["STEUERSTATUS"] = steuerstatus  # Kommentar: Steuerstatus in den Daten speichern

    norm = (auswahl or "").lower()  # Kommentar: Auswahl in Kleinbuchstaben umwandeln
    is_totalschaden = "totalschaden" in norm  # Kommentar: Prüfen, ob es sich um einen Totalschaden handelt
    is_130 = "130" in norm  # Kommentar: Prüfen, ob 130%-Regelung gilt

    reparatur = euro_zu_float(daten.get("REPARATURKOSTEN", ""))  # Kommentar: Reparaturkosten in float umwandeln
    wertminderung = euro_zu_float(daten.get("WERTMINDERUNG", ""))  # Kommentar: Wertminderung in float umwandeln
    kostenpausch = euro_zu_float(daten.get("KOSTENPAUSCHALE", ""))  # Kommentar: Kostenpauschale in float umwandeln
    gutachter = euro_zu_float(daten.get("GUTACHTERKOSTEN", ""))  # Kommentar: Gutachterkosten in float umwandeln
    nutzung = euro_zu_float(daten.get("NUTZUNGSAUSFALL", ""))  # Kommentar: Nutzungsausfall in float umwandeln
    mwst = euro_zu_float(daten.get("MWST_BETRAG", ""))  # Kommentar: MwSt-Betrag in float umwandeln

    wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))  # Kommentar: Wiederbeschaffungswert in float umwandeln
    restwert = euro_zu_float(daten.get("RESTWERT", ""))  # Kommentar: Restwert in float umwandeln

    wied_aufwand = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSAUFWAND", ""))  # Kommentar: Wiederbeschaffungsaufwand in float umwandeln
    ersatz_mwst = euro_zu_float(daten.get("ERSATZBESCHAFFUNG_MWST", ""))  # Kommentar: MwSt aus Ersatzbeschaffung in float umwandeln

    zus_betrag = euro_zu_float(daten.get("ZUSATZKOSTEN_BETRAG", ""))  # Kommentar: Zusatzkostenbetrag in float umwandeln

    if is_130:  # Kommentar: Wenn 130%-Regelung gilt
        wertminderung = 0.0  # Kommentar: Wertminderung auf 0 setzen (nicht ersatzfähig)
        daten["WERTMINDERUNG"] = ""  # Kommentar: Textfeld Wertminderung leeren

    if is_totalschaden:  # Kommentar: Wenn Totalschaden vorliegt
        if wied_aufwand <= 0 and (wbw > 0 or restwert > 0):  # Kommentar: Wenn Wiederbeschaffungsaufwand noch nicht gesetzt, aber WBW oder Restwert vorhanden
            wied_aufwand = max(wbw - restwert, 0.0)  # Kommentar: Wiederbeschaffungsaufwand als Differenz berechnen, nicht negativ

    if (("totalschaden konkret" in norm) or ("ersatzbeschaffung" in norm)) and ersatz_mwst == 0 and mwst > 0:  # Kommentar: Falls Totalschaden konkret/Ersatzbeschaffung und Ersatz-MwSt leer, aber MwSt vorhanden
        ersatz_mwst = mwst  # Kommentar: MwSt-Betrag als Ersatzbeschaffungs-MwSt übernehmen

    if reparatur:  # Kommentar: Wenn Reparaturkosten > 0
        daten["REPARATURKOSTEN"] = float_zu_euro(reparatur)  # Kommentar: Formatierten Euro-String zurückschreiben
    if wertminderung:  # Kommentar: Wenn Wertminderung > 0
        daten["WERTMINDERUNG"] = float_zu_euro(wertminderung)  # Kommentar: Formatierten Euro-String zurückschreiben
    if kostenpausch:  # Kommentar: Wenn Kostenpauschale > 0
        daten["KOSTENPAUSCHALE"] = float_zu_euro(kostenpausch)  # Kommentar: Formatierten Euro-String zurückschreiben
    if gutachter:  # Kommentar: Wenn Gutachterkosten > 0
        daten["GUTACHTERKOSTEN"] = float_zu_euro(gutachter)  # Kommentar: Formatierten Euro-String zurückschreiben
    if nutzung:  # Kommentar: Wenn Nutzungsausfall > 0
        daten["NUTZUNGSAUSFALL"] = float_zu_euro(nutzung)  # Kommentar: Formatierten Euro-String zurückschreiben
    if mwst:  # Kommentar: Wenn MwSt-Betrag > 0
        daten["MWST_BETRAG"] = float_zu_euro(mwst)  # Kommentar: Formatierten Euro-String zurückschreiben
    if zus_betrag:  # Kommentar: Wenn Zusatzkosten > 0
        daten["ZUSATZKOSTEN_BETRAG"] = float_zu_euro(zus_betrag)  # Kommentar: Formatierten Euro-String zurückschreiben
    if wied_aufwand:  # Kommentar: Wenn Wiederbeschaffungsaufwand > 0
        daten["WIEDERBESCHAFFUNGSAUFWAND"] = float_zu_euro(wied_aufwand)  # Kommentar: Formatierten Euro-String zurückschreiben
    if ersatz_mwst:  # Kommentar: Wenn Ersatzbeschaffungs-MwSt > 0
        daten["ERSATZBESCHAFFUNG_MWST"] = float_zu_euro(ersatz_mwst)  # Kommentar: Formatierten Euro-String zurückschreiben

    kostenfelder = _bestimme_kostenfelder(auswahl)  # Kommentar: Passende Tabellenfelder je nach Abrechnungsvariante bestimmen

    feld_zu_float = {  # Kommentar: Mapping von Feldnamen auf ihre aktuellen Float-Werte
        "REPARATURKOSTEN": reparatur,
        "WERTMINDERUNG": wertminderung,
        "KOSTENPAUSCHALE": kostenpausch,
        "GUTACHTERKOSTEN": gutachter,
        "NUTZUNGSAUSFALL": nutzung,
        "MWST_BETRAG": mwst,
        "WIEDERBESCHAFFUNGSAUFWAND": wied_aufwand,
        "ERSATZBESCHAFFUNG_MWST": ersatz_mwst,
    }

    kosten_x = 0.0  # Kommentar: Summe der Kostentabellenpositionen initial auf 0 setzen
    for feld in kostenfelder:  # Kommentar: Über alle relevanten Felder iterieren
        kosten_x += feld_zu_float.get(feld, 0.0)  # Kommentar: Wert des Felds zur Gesamtsumme addieren

    daten["KOSTENSUMME_X"] = float_zu_euro(kosten_x) if kosten_x > 0 else ""  # Kommentar: KOSTENSUMME_X setzen, falls > 0, sonst leer lassen

    gesamt = kosten_x + zus_betrag  # Kommentar: Gesamtsumme = Kostensumme X + Zusatzkosten berechnen
    daten["GESAMTSUMME"] = float_zu_euro(gesamt) if gesamt > 0 else ""  # Kommentar: GESAMTSUMME setzen, falls > 0, sonst leer lassen

    return daten  # Kommentar: Aufbereitete Daten mit allen Summen zurückgeben


def daten_nachbearbeiten(
    daten: dict,
    platzhalter,
    auswahl: str,
    steuerstatus: str,
    zus_bez: str,
    zus_betrag: str
):  # Kommentar: Funktion zur finalen Nachbearbeitung der Daten vor dem Einfügen in die Vorlage
    daten = daten_defaults(daten)  # Kommentar: Alle erwarteten Keys sicherstellen

    daten["ZUSATZKOSTEN_BEZEICHNUNG"] = (zus_bez or "").strip()  # Kommentar: Zusatzkosten-Bezeichnung aus User-Input übernehmen und trimmen
    daten["ZUSATZKOSTEN_BETRAG"] = (zus_betrag or "").strip()  # Kommentar: Zusatzkosten-Betrag aus User-Input übernehmen und trimmen

    jetzt = datetime.now()  # Kommentar: Aktuelle Uhrzeit bestimmen
    daten["FRIST_DATUM"] = (jetzt + timedelta(days=14)).strftime("%d.%m.%Y")  # Kommentar: Fristdatum (heute + 14 Tage) setzen
    daten["HEUTDATUM"] = jetzt.strftime("%d.%m.%Y")  # Kommentar: Heutiges Datum setzen

    daten = anwenden_abrechnungslogik(daten, auswahl, steuerstatus)  # Kommentar: Abrechnungslogik anwenden (Summen, Formatierung)

    if "WIEDERBESCHAFFUNGSAUFWAND" in platzhalter and not daten.get("WIEDERBESCHAFFUNGSAUFWAND"):  # Kommentar: Falls Vorlage WIEDERBESCHAFFUNGSAUFWAND erwartet, Feld aber noch leer ist
        wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))  # Kommentar: WBW aus den Daten als float lesen
        rest = euro_zu_float(daten.get("RESTWERT", ""))  # Kommentar: Restwert aus den Daten als float lesen
        if wbw or rest:  # Kommentar: Nur berechnen, wenn einer der Werte gesetzt ist
            daten["WIEDERBESCHAFFUNGSAUFWAND"] = float_zu_euro(max(wbw - rest, 0.0))  # Kommentar: Wiederbeschaffungsaufwand neu berechnen und formatiert setzen

    return daten  # Kommentar: Nachbearbeitete Daten zurückgeben


def word_aus_vorlage_erstellen(daten: dict, vorlage_pfad: str, ziel_pfad: str):  # Kommentar: Word-Dokument aus Vorlage und Daten erstellen
    doc = DocxTemplate(vorlage_pfad)  # Kommentar: Vorlage-Datei öffnen
    platzhalter = doc.get_undeclared_template_variables()  # Kommentar: Verwendete Platzhalter auslesen
    daten_fuer_vorlage = {k: v for k, v in daten.items() if k in platzhalter}  # Kommentar: Nur Werte übernehmen, für die es Platzhalter gibt
    os.makedirs(os.path.dirname(ziel_pfad), exist_ok=True)  # Kommentar: Zielordner anlegen, falls er nicht existiert
    doc.render(daten_fuer_vorlage)  # Kommentar: Platzhalter in der Vorlage mit Daten füllen
    doc.save(ziel_pfad)  # Kommentar: Fertiges Schreiben als DOCX speichern


def ki_datei_verarbeiten(
    pfad_ki_txt: str,
    vorlage_pfad: str,
    auswahl: str,
    steuerstatus: str,
    zus_bez: str,
    zus_betrag: str
) -> str:  # Kommentar: KI-Antwortdatei einlesen, Daten bearbeiten, Schreiben erzeugen
    with open(pfad_ki_txt, "r", encoding="utf-8") as f:  # Kommentar: KI-Textdatei im Lesemodus öffnen
        ki_text = f.read()  # Kommentar: gesamten Inhalt der KI-Antwort einlesen

    daten = json_aus_ki_antwort_parsen(ki_text)  # Kommentar: JSON-Daten aus der KI-Antwort parsen
    platzhalter = extrahiere_platzhalter(vorlage_pfad)  # Kommentar: Platzhalter aus Word-Vorlage extrahieren
    daten = daten_nachbearbeiten(daten, platzhalter, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: Daten nachbearbeiten und Summen berechnen

    basisname = os.path.splitext(os.path.basename(pfad_ki_txt))[0]  # Kommentar: Basisdateiname der KI-Datei bestimmen
    datum_str = datetime.now().strftime("%Y%m%d_%H%M%S")  # Kommentar: Zeitstempel für eindeutigen Ausgabedateinamen erzeugen
    ausgabe_name = f"{basisname}_schreiben_{datum_str}.docx"  # Kommentar: Ausgabedateinamen zusammenbauen
    ausgabe_pfad = os.path.join(AUSGANGS_ORDNER, ausgabe_name)  # Kommentar: Vollständigen Pfad für die Ausgabedatei berechnen

    word_aus_vorlage_erstellen(daten, vorlage_pfad, ausgabe_pfad)  # Kommentar: Word-Schreiben auf Basis der Vorlage erzeugen
    return ausgabe_pfad  # Kommentar: Pfad zur fertigen DOCX-Datei zurückgeben


def main(
    pfad_ki_txt: str = None,
    vorlage_pfad: str | None = None,
    auswahl: str = "",
    steuerstatus: str = "",
    zus_bez: str = "",
    zus_betrag: str = ""
) -> str:  # Kommentar: main-Funktion, die von app.py aufgerufen wird
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: Ordner für KI-Antworten anlegen, falls nötig
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: Ordner für Ausgangsschreiben anlegen, falls nötig

    if vorlage_pfad is None:  # Kommentar: Prüfen, ob eine Vorlage übergeben wurde
        raise ValueError("vorlage_pfad muss übergeben werden (Word-Vorlage .docx).")  # Kommentar: Fehlermeldung, wenn keine Vorlage angegeben wurde

    if pfad_ki_txt is None:  # Kommentar: Wenn kein konkreter KI-Dateipfad übergeben wurde
        dateien = [  # Kommentar: Alle KI-Textdateien im Ordner sammeln
            os.path.join(KI_ANTWORT_ORDNER, f)
            for f in os.listdir(KI_ANTWORT_ORDNER)
            if f.endswith("_ki.txt")
        ]
        if not dateien:  # Kommentar: Prüfen, ob keine KI-Dateien vorhanden sind
            raise FileNotFoundError("Keine KI-Datei gefunden.")  # Kommentar: Fehlermeldung, wenn kein _ki.txt existiert
        pfad_ki_txt = max(dateien, key=os.path.getmtime)  # Kommentar: Neueste KI-Datei anhand Änderungsdatum bestimmen

    if not os.path.isfile(pfad_ki_txt):  # Kommentar: Prüfen, ob die KI-Datei existiert
        raise FileNotFoundError(f"KI-Datei existiert nicht: {pfad_ki_txt}")  # Kommentar: Fehlermeldung, wenn die Datei fehlt

    if not os.path.isfile(vorlage_pfad):  # Kommentar: Prüfen, ob die angegebene Vorlage-Datei existiert
        raise FileNotFoundError(f"Vorlage existiert nicht: {vorlage_pfad}")  # Kommentar: Fehlermeldung, wenn die Vorlage fehlt

    return ki_datei_verarbeiten(pfad_ki_txt, vorlage_pfad, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: Verarbeitung starten und Pfad zur Ausgabedatei zurückgeben


if __name__ == "__main__":  # Kommentar: Prüfen, ob dieses Modul direkt ausgeführt wird
    main()  # Kommentar: main() mit Standardparametern aufrufen
