# programm_2_word_output.py

import os  # Betriebssystemfunktionen (Pfad, Dateien)
import json  # Zum Parsen der JSON-Antwort aus der KI
from datetime import datetime, timedelta  # Für Datumsberechnungen (Frist, Heute)
from docxtpl import DocxTemplate  # Für das Füllen der Word-Vorlage
from programm_1_ki_input import KI_ANTWORT_ORDNER, BASE_DIR  # Pfade aus programm_1 übernehmen

# Ausgabeordner für fertige Schreiben (DOCX) definieren
AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")

# Marker, zwischen denen die KI das JSON einbettet
JSON_START_MARKER = "JSON_START"
JSON_END_MARKER = "JSON_END"


def json_aus_ki_antwort_parsen(ki_text: str) -> dict:
    """Extrahiert den JSON-Block zwischen JSON_START und JSON_END aus der KI-Antwort."""

    # Position des Start-Markers im KI-Text suchen
    start_idx = ki_text.find(JSON_START_MARKER)
    # Position des End-Markers im KI-Text suchen
    end_idx = ki_text.find(JSON_END_MARKER)

    # Wenn einer der Marker fehlt, ist die Antwort ungültig
    if start_idx == -1 or end_idx == -1:
        raise ValueError("JSON_START oder JSON_END nicht gefunden.")

    # Roh-JSON-Text zwischen den Markern ausschneiden
    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()
    # Mögliche Markdown-Codeblock-Reste entfernen
    json_roh = json_roh.replace("```json", "").replace("```", "").strip()

    # Erste öffnende geschweifte Klammer suchen
    first_brace = json_roh.find("{")
    # Letzte schließende geschweifte Klammer suchen
    last_brace = json_roh.rfind("}")

    # Wenn keine gültige JSON-Struktur erkennbar ist -> Fehler
    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
        raise ValueError("Kein gültiger JSON-Block in KI-Antwort.")

    # JSON-Teil genau zwischen der ersten und letzten Klammer ausschneiden
    json_clean = json_roh[first_brace:last_brace + 1]
    # Häufiger Fehler: ein Komma vor der schließenden Klammer -> entfernen
    json_clean = json_clean.replace(",\n}", "\n}").replace(",}", "}")

    # String in Python-Dict umwandeln
    return json.loads(json_clean)


def euro_zu_float(text) -> float:
    """Wandelt einen Euro-String wie '1.234,56 €' robust in float (1234.56) um."""

    # Direkte Zahlen (int/float) unverändert in float umwandeln
    if isinstance(text, (int, float)):
        return float(text)

    # Leere oder None -> 0.0
    if not text:
        return 0.0

    # In String umwandeln
    t = str(text)
    # Typische Währungs-Symbole entfernen
    t = t.replace("€", "").replace("EUR", "").replace("Euro", "")
    # geschütztes Leerzeichen entfernen
    t = t.replace("\u00a0", " ").strip()
    # Normale Leerzeichen entfernen
    t = t.replace(" ", "")

    # Nur Ziffern, Minus, Plus, Punkt und Komma übrig lassen
    filtered = []
    for ch in t:
        if ch.isdigit() or ch in [",", ".", "+", "-"]:
            filtered.append(ch)
    t = "".join(filtered)

    # Wenn danach nichts übrig bleibt -> 0.0
    if not t:
        return 0.0

    # Wenn sowohl Punkt als auch Komma vorkommen: Punkt als Tausender, Komma als Dezimal
    if "." in t and "," in t:
        t = t.replace(".", "").replace(",", ".")
    # Wenn nur Komma vorkommt: Komma als Dezimal
    elif "," in t:
        t = t.replace(",", ".")

    # Versuch, in float zu parsen
    try:
        return float(t)
    except ValueError:
        # Falls immer noch etwas schiefgeht: 0.0 zurückgeben
        return 0.0


def float_zu_euro(betrag: float) -> str:
    """Formatiert einen float wie 1234.5 zu '1.234,50 €'."""

    # Betrag auf zwei Nachkommastellen mit Tausenderpunkten formatieren
    s = f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    # Euro-Symbol anhängen
    return s + " €"


def extrahiere_platzhalter(vorlage_pfad):
    """Liest alle Platzhalter-Namen aus der übergebenen Word-Vorlage."""

    # Vorlage laden
    doc = DocxTemplate(vorlage_pfad)
    # Ungenutzte Template-Variablen (Platzhalter) zurückgeben
    return doc.get_undeclared_template_variables()


def baue_totalschaden(daten, platzhalter):
    """
    Ältere Hilfsfunktion aus deiner ersten Version:
    Rechnet WIEDERBESCHAFFUNGSWERTAUFWAND = WBW - Restwert,
    falls dieser Platzhalter in der Vorlage vorkommt.
    """

    # Prüfen, ob der Platzhalter 'WIEDERBESCHAFFUNGSWERTAUFWAND' in der Vorlage existiert
    if "WIEDERBESCHAFFUNGSWERTAUFWAND" in platzhalter:
        # Wiederbeschaffungswert als float holen
        wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", 0))
        # Restwert als float holen
        restwert = euro_zu_float(daten.get("RESTWERT", 0))
        # Wiederbeschaffungsaufwand berechnen
        wiederbeschaffungsaufwand = wbw - restwert
        # Formatiert im Daten-Dict speichern
        daten["WIEDERBESCHAFFUNGSWERTAUFWAND"] = float_zu_euro(wiederbeschaffungsaufwand)
    # Angepasstes Dict zurückgeben
    return daten


def daten_defaults(daten: dict):
    """Sorgt dafür, dass alle erwarteten Keys existieren (mindestens mit '')."""

    # Liste aller Keys, die wir im System erwarten
    keys = [
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
        # Zusätzliche Felder für Abrechnungslogik
        "ABRECHNUNGSART", "STEUERSTATUS",
        "WIEDERBESCHAFFUNGSAUFWAND",
        "ERSATZBESCHAFFUNG_MWST",
        "ZUSATZKOSTEN_BEZEICHNUNG", "ZUSATZKOSTEN_BETRAG",
        "KOSTENSUMME_X", "GESAMTSUMME",
    ]

    # Für jeden Key sicherstellen, dass er im Dict existiert (sonst "")
    for k in keys:
        daten.setdefault(k, "")

    # Das vervollständigte Dict zurückgeben
    return daten


def _bestimme_kostenfelder(auswahl: str):
    """
    Bestimmt je nach gewählter Vorlage (Abrechnungsvariante),
    welche Felder in der Kostentabelle stehen und damit in KOSTENSUMME_X
    berücksichtigt werden sollen.
    """

    # Auswahl in Kleinbuchstaben zur robusten Erkennung
    norm = (auswahl or "").lower()

    # Fiktive Abrechnung (Reparaturschaden)
    if "fiktive abrechnung" in norm and "reparaturschaden" in norm:
        return [
            "REPARATURKOSTEN",
            "WERTMINDERUNG",
            "NUTZUNGSAUSFALL",
            "KOSTENPAUSCHALE",
            "GUTACHTERKOSTEN",
        ]

    # Konkrete Abrechnung < WBW
    if "konkrete abrechnung" in norm:
        return [
            "REPARATURKOSTEN",
            "MWST_BETRAG",
            "WERTMINDERUNG",
            "NUTZUNGSAUSFALL",
            "KOSTENPAUSCHALE",
            "GUTACHTERKOSTEN",
        ]

    # 130%-Regelung (keine Wertminderung)
    if "130" in norm:
        return [
            "REPARATURKOSTEN",
            "MWST_BETRAG",
            "NUTZUNGSAUSFALL",
            "KOSTENPAUSCHALE",
            "GUTACHTERKOSTEN",
        ]

    # Totalschaden fiktiv
    if "totalschaden fiktiv" in norm:
        return [
            "WIEDERBESCHAFFUNGSAUFWAND",
            "KOSTENPAUSCHALE",
            "GUTACHTERKOSTEN",
            "NUTZUNGSAUSFALL",
        ]

    # Totalschaden konkret oder Totalschaden Ersatzbeschaffung
    if "totalschaden konkret" in norm or "ersatzbeschaffung" in norm:
        return [
            "WIEDERBESCHAFFUNGSAUFWAND",
            "ERSATZBESCHAFFUNG_MWST",
            "KOSTENPAUSCHALE",
            "GUTACHTERKOSTEN",
            "NUTZUNGSAUSFALL",
        ]

    # Fallback: klassischer Reparaturschaden mit allen Standardpositionen
    return [
        "REPARATURKOSTEN",
        "WERTMINDERUNG",
        "KOSTENPAUSCHALE",
        "GUTACHTERKOSTEN",
        "NUTZUNGSAUSFALL",
    ]


def anwenden_abrechnungslogik(daten: dict, auswahl: str, steuerstatus: str):
    """
    Bereitet alle Beträge vor:
    - Rechnet ggf. Wiederbeschaffungsaufwand
    - Behandelt Wertminderung (z.B. bei 130%-Regelung)
    - Setzt/entfernt MwSt je nach Variante
    - Berechnet KOSTENSUMME_X (Summe Kostentabellen-Positionen)
    - Berechnet GESAMTSUMME = KOSTENSUMME_X + Zusatzkosten
    """

    # Abrechnungsart im Dict speichern
    daten["ABRECHNUNGSART"] = auswahl
    # Steuerstatus im Dict speichern
    daten["STEUERSTATUS"] = steuerstatus

    # Auswahl-Namen in Kleinbuchstaben für Vergleiche aufbereiten
    norm = (auswahl or "").lower()

    # Flags für Varianten bestimmen
    is_totalschaden = "totalschaden" in norm
    is_fiktiv = "fiktive abrechnung" in norm
    is_konkret = "konkrete abrechnung" in norm
    is_130 = "130" in norm

    # Alle relevanten Beträge als float einlesen
    reparatur = euro_zu_float(daten.get("REPARATURKOSTEN", ""))
    wertminderung = euro_zu_float(daten.get("WERTMINDERUNG", ""))
    kostenpausch = euro_zu_float(daten.get("KOSTENPAUSCHALE", ""))
    gutachter = euro_zu_float(daten.get("GUTACHTERKOSTEN", ""))
    nutzung = euro_zu_float(daten.get("NUTZUNGSAUSFALL", ""))
    mwst = euro_zu_float(daten.get("MWST_BETRAG", ""))

    # Werte für Totalschaden
    wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))
    restwert = euro_zu_float(daten.get("RESTWERT", ""))
    wied_aufwand = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSAUFWAND", ""))
    ersatz_mwst = euro_zu_float(daten.get("ERSATZBESCHAFFUNG_MWST", ""))

    # Zusatzkosten-Betrag als float einlesen
    zus_betrag = euro_zu_float(daten.get("ZUSATZKOSTEN_BETRAG", ""))

    # Bei 130%-Regelung ist merkantile Wertminderung ausgeschlossen
    if is_130:
        wertminderung = 0.0  # Wert auf 0 setzen
        daten["WERTMINDERUNG"] = ""  # Textfeld leeren

    # Wenn Totalschaden und Wiederbeschaffungsaufwand noch nicht gesetzt:
    if is_totalschaden and wied_aufwand <= 0 and (wbw > 0 or restwert > 0):
        # Wiederbeschaffungsaufwand = WBW - Restwert
        wied_aufwand = max(wbw - restwert, 0.0)

    # Bei Totalschaden konkret / Ersatzbeschaffung:
    # Wenn ERSATZBESCHAFFUNG_MWST noch 0, aber MWST_BETRAG vorhanden ist,
    # interpretieren wir MWST_BETRAG als Ersatzbeschaffungs-MwSt
    if (("totalschaden konkret" in norm) or ("ersatzbeschaffung" in norm)) and ersatz_mwst == 0 and mwst > 0:
        ersatz_mwst = mwst

    # Bei fiktiver Reparatur: MwSt darf nicht abgerechnet werden
    if is_fiktiv and not is_totalschaden:
        mwst = 0.0  # MwSt-Wert auf 0
        daten["MWST_BETRAG"] = ""  # Feld leeren

    # Ab hier: alle verfügbaren Beträge wieder formatiert ins Dict zurückschreiben (wenn > 0)

    if reparatur:
        daten["REPARATURKOSTEN"] = float_zu_euro(reparatur)
    if wertminderung:
        daten["WERTMINDERUNG"] = float_zu_euro(wertminderung)
    if kostenpausch:
        daten["KOSTENPAUSCHALE"] = float_zu_euro(kostenpausch)
    if gutachter:
        daten["GUTACHTERKOSTEN"] = float_zu_euro(gutachter)
    if nutzung:
        daten["NUTZUNGSAUSFALL"] = float_zu_euro(nutzung)
    if mwst:
        daten["MWST_BETRAG"] = float_zu_euro(mwst)
    if zus_betrag:
        daten["ZUSATZKOSTEN_BETRAG"] = float_zu_euro(zus_betrag)
    if wied_aufwand:
        daten["WIEDERBESCHAFFUNGSAUFWAND"] = float_zu_euro(wied_aufwand)
    if ersatz_mwst:
        daten["ERSATZBESCHAFFUNG_MWST"] = float_zu_euro(ersatz_mwst)

    # Kostenfelder bestimmen, die in der Kostentabelle stehen
    kostenfelder = _bestimme_kostenfelder(auswahl)

    # Mapping Feld -> float-Wert für Summenbildung vorbereiten
    feld_zu_float = {
        "REPARATURKOSTEN": reparatur,
        "WERTMINDERUNG": wertminderung,
        "KOSTENPAUSCHALE": kostenpausch,
        "GUTACHTERKOSTEN": gutachter,
        "NUTZUNGSAUSFALL": nutzung,
        "MWST_BETRAG": mwst,
        "WIEDERBESCHAFFUNGSAUFWAND": wied_aufwand,
        "ERSATZBESCHAFFUNG_MWST": ersatz_mwst,
    }

    # KOSTENSUMME_X = Summe aller Felder, die in der Kostentabelle stehen
    kosten_x = 0.0  # Startwert für Summe
    for feld in kostenfelder:
        kosten_x += feld_zu_float.get(feld, 0.0)  # entsprechenden Wert addieren

    # Wenn KOSTENSUMME_X > 0 ist, als Euro-String formatieren, sonst Feld leer lassen
    daten["KOSTENSUMME_X"] = float_zu_euro(kosten_x) if kosten_x > 0 else ""

    # GESAMTSUMME = KOSTENSUMME_X + Zusatzkosten
    gesamt = kosten_x + zus_betrag  # Gesamtsumme als float
    # Nur wenn > 0, als formatierten String zurückgeben
    daten["GESAMTSUMME"] = float_zu_euro(gesamt) if gesamt > 0 else ""

    # Fertig aufbereitetes Dict zurückgeben
    return daten


def daten_nachbearbeiten(
    daten: dict,
    platzhalter,
    auswahl: str,
    steuerstatus: str,
    zus_bez: str,
    zus_betrag: str
):
    """Setzt Defaultwerte, Fristen, Zusatzkosten und ruft die Abrechnungslogik."""

    # Sicherstellen, dass alle erwarteten Keys vorhanden sind
    daten = daten_defaults(daten)

    # Zusatzkostentext in Daten speichern (kann leer sein)
    daten["ZUSATZKOSTEN_BEZEICHNUNG"] = (zus_bez or "").strip()
    # Zusatzkostenbetrag (als Text, wird später in euro_zu_float interpretiert)
    daten["ZUSATZKOSTEN_BETRAG"] = (zus_betrag or "").strip()

    # Aktuellen Zeitpunkt holen
    jetzt = datetime.now()
    # Fristdatum = heute + 14 Tage
    daten["FRIST_DATUM"] = (jetzt + timedelta(days=14)).strftime("%d.%m.%Y")
    # Heutiges Datum setzen
    daten["HEUTDATUM"] = jetzt.strftime("%d.%m.%Y")

    # Abrechnungslogik anwenden (summiert alles etc.)
    daten = anwenden_abrechnungslogik(daten, auswahl, steuerstatus)

    # Falls Vorlage explizit WIEDERBESCHAFFUNGSAUFWAND hat und noch leer ist, nachträglich setzen
    if "WIEDERBESCHAFFUNGSAUFWAND" in platzhalter and not daten.get("WIEDERBESCHAFFUNGSAUFWAND"):
        wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))
        rest = euro_zu_float(daten.get("RESTWERT", ""))
        if wbw or rest:
            daten["WIEDERBESCHAFFUNGSAUFWAND"] = float_zu_euro(max(wbw - rest, 0.0))

    # Nachbearbeitetes Dict zurückgeben
    return daten


def word_aus_vorlage_erstellen(daten: dict, vorlage_pfad: str, ziel_pfad: str):
    """Füllt die Word-Vorlage mit den Daten und speichert sie als neues Dokument."""

    # Word-Vorlage laden
    doc = DocxTemplate(vorlage_pfad)
    # Alle Platzhalter in der Vorlage ermitteln
    platzhalter = doc.get_undeclared_template_variables()
    # Nur die Daten übernehmen, die auch wirklich als Platzhalter existieren
    daten_fuer_vorlage = {k: v for k, v in daten.items() if k in platzhalter}
    # Zielordner sicherstellen
    os.makedirs(os.path.dirname(ziel_pfad), exist_ok=True)
    # Vorlage mit Daten rendern
    doc.render(daten_fuer_vorlage)
    # Fertiges Dokument speichern
    doc.save(ziel_pfad)


def ki_datei_verarbeiten(
    pfad_ki_txt: str,
    vorlage_pfad: str,
    auswahl: str,
    steuerstatus: str,
    zus_bez: str,
    zus_betrag: str
) -> str:
    """Liest die KI-Antwort, bereitet die Daten auf und erstellt das fertige Schreiben."""

    # KI-Textdatei öffnen und Inhalt lesen
    with open(pfad_ki_txt, "r", encoding="utf-8") as f:
        ki_text = f.read()

    # JSON-Daten aus der KI-Antwort extrahieren
    daten = json_aus_ki_antwort_parsen(ki_text)
    # Platzhalter aus der Word-Vorlage auslesen
    platzhalter = extrahiere_platzhalter(vorlage_pfad)
    # Daten nachbearbeiten (Summen, Fristen, Zusatzkosten, etc.)
    daten = daten_nachbearbeiten(daten, platzhalter, auswahl, steuerstatus, zus_bez, zus_betrag)

    # Basisname aus dem KI-Dateinamen ableiten (ohne Endung)
    basisname = os.path.splitext(os.path.basename(pfad_ki_txt))[0]
    # Zeitstempel für Dateinamen erzeugen
    datum_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Ausgabename für das neue Schreiben definieren
    ausgabe_name = f"{basisname}_schreiben_{datum_str}.docx"
    # Vollständigen Pfad im Ausgangsordner bauen
    ausgabe_pfad = os.path.join(AUSGANGS_ORDNER, ausgabe_name)

    # Word-Dokument aus der Vorlage erstellen
    word_aus_vorlage_erstellen(daten, vorlage_pfad, ausgabe_pfad)
    # Pfad zur fertigen DOCX-Datei zurückgeben
    return ausgabe_pfad


def main(
    pfad_ki_txt: str = None,
    vorlage_pfad: str | None = None,
    auswahl: str = "",
    steuerstatus: str = "",
    zus_bez: str = "",
    zus_betrag: str = ""
) -> str:
    """Haupteinstieg: nimmt KI-Datei + Vorlage, erzeugt fertiges Schreiben und gibt den Pfad zurück."""

    # Sicherstellen, dass Eingangs- und Ausgangsordner existieren
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)

    # Ohne Vorlage können wir kein Schreiben erzeugen -> harter Fehler
    if vorlage_pfad is None:
        raise ValueError("vorlage_pfad muss übergeben werden (Word-Vorlage .docx).")

    # Falls keine KI-Datei angegeben ist: die neueste im KI_ANTWORT_ORDNER suchen
    if pfad_ki_txt is None:
        dateien = [
            os.path.join(KI_ANTWORT_ORDNER, f)
            for f in os.listdir(KI_ANTWORT_ORDNER)
            if f.endswith("_ki.txt")
        ]
        # Wenn keine KI-Datei gefunden wurde -> Fehler werfen
        if not dateien:
            raise FileNotFoundError("Keine KI-Datei gefunden.")
        # Neueste Datei anhand des Änderungsdatums bestimmen
        pfad_ki_txt = max(dateien, key=os.path.getmtime)

    # Prüfen, ob die KI-Datei wirklich existiert
    if not os.path.isfile(pfad_ki_txt):
        raise FileNotFoundError(f"KI-Datei existiert nicht: {pfad_ki_txt}")

    # Prüfen, ob die Word-Vorlage existiert
    if not os.path.isfile(vorlage_pfad):
        raise FileNotFoundError(f"Vorlage existiert nicht: {vorlage_pfad}")

    # Verarbeitung der KI-Datei starten und Pfad zum fertigen Schreiben zurückgeben
    return ki_datei_verarbeiten(pfad_ki_txt, vorlage_pfad, auswahl, steuerstatus, zus_bez, zus_betrag)


# Wenn das Skript direkt ausgeführt wird (nicht nur importiert)
if __name__ == "__main__":
    # main() ohne Parameter aufrufen (wird dann die neueste KI-Datei + Fehler werfen,
    # wenn keine Vorlage mitgegeben wird)
    main()
