# programm_2_word_output.py  # Kommentar: KI-JSON aus TXT lesen, Daten nachbearbeiten, DOCX erstellen

import os  # Kommentar: Pfade und Dateisystem
import json  # Kommentar: JSON parsen
import re  # Kommentar: Textbereinigung / Zahlenfilter
from datetime import datetime, timedelta  # Kommentar: Frist/Heutdatum
from docxtpl import DocxTemplate  # Kommentar: DOCX Templates rendern
from programm_1_ki_input import KI_ANTWORT_ORDNER, BASE_DIR  # Kommentar: Ordner/BASE_DIR übernehmen

AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # Kommentar: Ausgangsordner für DOCX
JSON_START_MARKER = "JSON_START"  # Kommentar: Startmarker im KI-Text
JSON_END_MARKER = "JSON_END"  # Kommentar: Endmarker im KI-Text

def json_aus_ki_antwort_parsen(ki_text: str) -> dict:  # Kommentar: JSON zwischen Markern extrahieren
    start_idx = ki_text.find(JSON_START_MARKER)  # Kommentar: Start suchen
    end_idx = ki_text.find(JSON_END_MARKER)  # Kommentar: Ende suchen
    if start_idx == -1 or end_idx == -1:  # Kommentar: Marker fehlen?
        raise ValueError("JSON_START oder JSON_END nicht gefunden.")  # Kommentar: Fehler werfen
    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()  # Kommentar: Block ausschneiden
    json_roh = json_roh.replace("```json", "").replace("```", "").strip()  # Kommentar: Falls KI Code-Fences setzt
    first_brace = json_roh.find("{")  # Kommentar: Erste Klammer
    last_brace = json_roh.rfind("}")  # Kommentar: Letzte Klammer
    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:  # Kommentar: Ungültig?
        raise ValueError("Kein gültiger JSON-Block in KI-Antwort.")  # Kommentar: Fehler
    json_clean = json_roh[first_brace:last_brace + 1]  # Kommentar: JSON isolieren
    json_clean = json_clean.replace(",\n}", "\n}").replace(",}", "}")  # Kommentar: Häufiger KI-Fehler: trailing comma
    return json.loads(json_clean)  # Kommentar: JSON parsen

def euro_zu_float(text) -> float:  # Kommentar: Euro-Text -> Float (robust)
    if isinstance(text, (int, float)):  # Kommentar: Wenn schon Zahl
        return float(text)  # Kommentar: Float zurück
    if not text:  # Kommentar: Leer?
        return 0.0  # Kommentar: Null
    t = str(text)  # Kommentar: Zu String
    t = t.replace("€", "").replace("EUR", "").replace("Euro", "")  # Kommentar: Währung entfernen
    t = t.replace("\u00a0", " ").strip()  # Kommentar: NBSP entfernen
    t = t.replace(" ", "")  # Kommentar: Spaces entfernen
    filtered = []  # Kommentar: Nur Zahlzeichen sammeln
    for ch in t:  # Kommentar: Zeichen durchlaufen
        if ch.isdigit() or ch in [",", ".", "+", "-"]:  # Kommentar: Erlaubte Zeichen
            filtered.append(ch)  # Kommentar: Sammeln
    t = "".join(filtered)  # Kommentar: Zusammenbauen
    if not t:  # Kommentar: Wenn nichts übrig
        return 0.0  # Kommentar: Null
    if "." in t and "," in t:  # Kommentar: Tausenderpunkt + Dezimalkomma
        t = t.replace(".", "").replace(",", ".")  # Kommentar: In Float-Format
    elif "," in t:  # Kommentar: Nur Komma
        t = t.replace(",", ".")  # Kommentar: In Float-Format
    try:  # Kommentar: Parse versuchen
        return float(t)  # Kommentar: Float
    except ValueError:  # Kommentar: Parse fehlgeschlagen
        return 0.0  # Kommentar: Null

def float_zu_euro(betrag: float) -> str:  # Kommentar: Float -> "1.234,56 €"
    s = f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # Kommentar: Format DE
    return s + " €"  # Kommentar: Eurozeichen anfügen

def extrahiere_platzhalter(vorlage_pfad: str):  # Kommentar: Platzhalter aus DOCX lesen
    doc = DocxTemplate(vorlage_pfad)  # Kommentar: Vorlage laden
    return doc.get_undeclared_template_variables()  # Kommentar: Variablen zurückgeben

def daten_defaults(daten: dict) -> dict:  # Kommentar: Standardkeys setzen
    keys = [  # Kommentar: Alle erwarteten Keys (inkl. deiner neuen)
        "MANDANT_VORNAME", "MANDANT_NACHNAME", "MANDANT_NAME",  # Kommentar: Mandant
        "MANDANT_STRASSE", "MANDANT_PLZ_ORT",  # Kommentar: Adresse
        "UNFALL_DATUM", "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE",  # Kommentar: Unfall
        "FAHRZEUGTYP", "KENNZEICHEN", "FAHRZEUG_KENNZEICHEN",  # Kommentar: Fahrzeug
        "POLIZEIAKTE_NUMMER", "SCHADENSNUMMER", "AKTENZEICHEN",  # Kommentar: Nummern
        "SCHADENHERGANG",  # Kommentar: Hergang
        "REPARATURKOSTEN", "WERTMINDERUNG", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN",  # Kommentar: Kosten
        "NUTZUNGSAUSFALL", "MWST_BETRAG",  # Kommentar: Nutzung + MwSt
        "WIEDERBESCHAFFUNGSWERT", "RESTWERT",  # Kommentar: WBW/Rest
        "FRIST_DATUM", "HEUTDATUM",  # Kommentar: Frist/Heute
        "ABRECHNUNGSART", "STEUERSTATUS",  # Kommentar: Meta
        "VORSTEUERBERECHTIGUNG",  # Kommentar: Textvariable für Word (genau wie du es willst)
        "ZUSATZKOSTEN_BEZEICHNUNG", "ZUSATZKOSTEN_BETRAG",  # Kommentar: Optional
        "KOSTENSUMME_X", "GESAMTSUMME",  # Kommentar: Summen
    ]  # Kommentar: Ende Keys
    for k in keys:  # Kommentar: Keys durchlaufen
        daten.setdefault(k, "")  # Kommentar: Default leer
    return daten  # Kommentar: Zurück

def anwenden_mwst_anzeige_logik(daten: dict, auswahl: str, steuerstatus: str) -> dict:  # Kommentar: MWST_BETRAG anzeigen/leer
    norm = (auswahl or "").lower()  # Kommentar: Variante normalisieren
    is_fiktiv = "fiktive abrechnung" in norm or "totalschaden fiktiv" in norm  # Kommentar: Fiktive Varianten erkennen
    vorsteuer = (steuerstatus == "vorsteuerabzugsberechtigt")  # Kommentar: Boolean für Vorsteuer

    # Kommentar: Wenn vorsteuerabzugsberechtigt ODER fiktiv -> MwSt nicht fordern/anzeigen
    if vorsteuer or is_fiktiv:  # Kommentar: Bedingung
        daten["MWST_BETRAG"] = ""  # Kommentar: Leer lassen (damit Word-Zeile leer bleibt)
        return daten  # Kommentar: Fertig

    # Kommentar: Ansonsten MwSt anzeigen, wenn Wert vorhanden (und sauber formatieren)
    mwst_val = euro_zu_float(daten.get("MWST_BETRAG", ""))  # Kommentar: MwSt als Zahl
    if mwst_val > 0:  # Kommentar: Wenn vorhanden
        daten["MWST_BETRAG"] = float_zu_euro(mwst_val)  # Kommentar: Formatieren
    else:  # Kommentar: Wenn nicht vorhanden
        daten["MWST_BETRAG"] = daten.get("MWST_BETRAG", "") or ""  # Kommentar: Leer/Fallback
    return daten  # Kommentar: Zurück

def summen_berechnen(daten: dict) -> dict:  # Kommentar: Summen aus Kostenfeldern berechnen
    reparatur = euro_zu_float(daten.get("REPARATURKOSTEN", ""))  # Kommentar: Reparatur
    wertminderung = euro_zu_float(daten.get("WERTMINDERUNG", ""))  # Kommentar: Wertminderung
    kostenpausch = euro_zu_float(daten.get("KOSTENPAUSCHALE", ""))  # Kommentar: Pauschale
    gutachter = euro_zu_float(daten.get("GUTACHTERKOSTEN", ""))  # Kommentar: Gutachter
    zusatz = euro_zu_float(daten.get("ZUSATZKOSTEN_BETRAG", ""))  # Kommentar: Zusatzkosten
    nutzung = euro_zu_float(daten.get("NUTZUNGSAUSFALL", ""))  # Kommentar: Nutzung

    # Kommentar: KOSTENSUMME_X wie in deinem Schema: Reparatur + Wertminderung + Kostenpauschale + Gutachter
    kosten_x = reparatur + wertminderung + kostenpausch + gutachter  # Kommentar: Summe X
    daten["KOSTENSUMME_X"] = float_zu_euro(kosten_x) if kosten_x > 0 else ""  # Kommentar: Formatieren oder leer

    # Kommentar: GESAMTSUMME: Summe X + Nutzung + Zusatzkosten (MwSt wird separat dargestellt über MWST_BETRAG)
    gesamt = kosten_x + nutzung + zusatz  # Kommentar: Gesamt
    daten["GESAMTSUMME"] = float_zu_euro(gesamt) if gesamt > 0 else ""  # Kommentar: Formatieren oder leer

    return daten  # Kommentar: Zurück

def daten_nachbearbeiten(daten: dict, vorlage_pfad: str, auswahl: str, steuerstatus: str, zus_bez: str, zus_betrag: str) -> dict:  # Kommentar: Alle Anpassungen zentral
    daten = daten_defaults(daten)  # Kommentar: Defaults setzen

    daten["ABRECHNUNGSART"] = auswahl  # Kommentar: Variante speichern
    daten["STEUERSTATUS"] = steuerstatus  # Kommentar: Steuerstatus speichern

    # Kommentar: Genau wie du es willst: Textvariable für Word setzen (kein Bool, kein True/False)
    daten["VORSTEUERBERECHTIGUNG"] = "vorsteuerabzugsberechtigt" if steuerstatus == "vorsteuerabzugsberechtigt" else "nicht vorsteuerabzugsberechtigt"  # Kommentar: Textwert setzen

    daten["ZUSATZKOSTEN_BEZEICHNUNG"] = (zus_bez or "").strip()  # Kommentar: Zusatzkosten-Bezeichnung
    daten["ZUSATZKOSTEN_BETRAG"] = (zus_betrag or "").strip()  # Kommentar: Zusatzkosten-Betrag roh

    # Kommentar: Geldfelder sauber formatieren (ohne MwSt-Entscheidung)
    for feld in ["REPARATURKOSTEN", "WERTMINDERUNG", "KOSTENPAUSCHALE", "GUTACHTERKOSTEN", "NUTZUNGSAUSFALL"]:  # Kommentar: Felderliste
        val = euro_zu_float(daten.get(feld, ""))  # Kommentar: In Float
        daten[feld] = float_zu_euro(val) if val > 0 else (daten.get(feld, "") or "")  # Kommentar: Format oder leer

    # Kommentar: Zusatzkosten-Betrag formatieren
    zus_val = euro_zu_float(daten.get("ZUSATZKOSTEN_BETRAG", ""))  # Kommentar: Zusatzkosten Zahl
    daten["ZUSATZKOSTEN_BETRAG"] = float_zu_euro(zus_val) if zus_val > 0 else ""  # Kommentar: Format oder leer

    # Kommentar: FRIST/HEUTE setzen
    jetzt = datetime.now()  # Kommentar: Jetzt
    daten["FRIST_DATUM"] = (jetzt + timedelta(days=14)).strftime("%d.%m.%Y")  # Kommentar: +14 Tage
    daten["HEUTDATUM"] = jetzt.strftime("%d.%m.%Y")  # Kommentar: Heute

    # Kommentar: MwSt-Zeile: anzeigen oder leer lassen (genau nach deiner Auswahl)
    daten = anwenden_mwst_anzeige_logik(daten, auswahl, steuerstatus)  # Kommentar: MwSt setzen/leer

    # Kommentar: Summen berechnen (unabhängig davon, ob MwSt angezeigt wird)
    daten = summen_berechnen(daten)  # Kommentar: Summen setzen

    # Kommentar: Optional: Platzhalterliste für Debug (kannst du bei Bedarf ausgeben)
    _ = extrahiere_platzhalter(vorlage_pfad)  # Kommentar: Platzhalter lesen (nicht zwingend, aber hilft später)

    return daten  # Kommentar: Fertige Daten zurück

def word_aus_vorlage_erstellen(daten: dict, vorlage_pfad: str, ziel_pfad: str) -> None:  # Kommentar: DOCX generieren
    doc = DocxTemplate(vorlage_pfad)  # Kommentar: Vorlage laden
    os.makedirs(os.path.dirname(ziel_pfad), exist_ok=True)  # Kommentar: Zielordner sicherstellen
    doc.render(daten)  # Kommentar: Wichtig: Render ALLES, damit auch Steuerstatus/Ifs funktionieren
    doc.save(ziel_pfad)  # Kommentar: Speichern

def ki_datei_verarbeiten(pfad_ki_txt: str, vorlage_pfad: str, auswahl: str, steuerstatus: str, zus_bez: str, zus_betrag: str) -> str:  # Kommentar: KI TXT -> DOCX
    with open(pfad_ki_txt, "r", encoding="utf-8") as f:  # Kommentar: KI-Datei lesen
        ki_text = f.read()  # Kommentar: Text holen
    daten = json_aus_ki_antwort_parsen(ki_text)  # Kommentar: JSON parsen
    daten = daten_nachbearbeiten(daten, vorlage_pfad, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: Daten finalisieren
    basisname = os.path.splitext(os.path.basename(pfad_ki_txt))[0]  # Kommentar: Basisname
    datum_str = datetime.now().strftime("%Y%m%d_%H%M%S")  # Kommentar: Timestamp
    ausgabe_name = f"{basisname}_schreiben_{datum_str}.docx"  # Kommentar: Ausgabe-Dateiname
    ausgabe_pfad = os.path.join(AUSGANGS_ORDNER, ausgabe_name)  # Kommentar: Ausgabe-Pfad
    word_aus_vorlage_erstellen(daten, vorlage_pfad, ausgabe_pfad)  # Kommentar: DOCX erzeugen
    return ausgabe_pfad  # Kommentar: Pfad zurück

def main(  # Kommentar: Entry-Point für App
    pfad_ki_txt: str = None,  # Kommentar: Optional: KI-Datei, sonst neueste
    vorlage_pfad: str | None = None,  # Kommentar: Muss gesetzt sein (Word-Vorlage)
    auswahl: str = "",  # Kommentar: Variante
    steuerstatus: str = "",  # Kommentar: Steuerstatus
    zus_bez: str = "",  # Kommentar: Zusatzkosten-Bezeichnung
    zus_betrag: str = ""  # Kommentar: Zusatzkosten-Betrag
) -> str:  # Kommentar: Gibt DOCX-Pfad zurück
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: Ordner sicher
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: Ordner sicher

    if vorlage_pfad is None:  # Kommentar: Vorlage muss übergeben werden
        raise ValueError("vorlage_pfad muss übergeben werden (Word-Vorlage .docx).")  # Kommentar: Fehler

    if pfad_ki_txt is None:  # Kommentar: Wenn keine KI-Datei angegeben
        dateien = [os.path.join(KI_ANTWORT_ORDNER, f) for f in os.listdir(KI_ANTWORT_ORDNER) if f.endswith("_ki.txt")]  # Kommentar: Kandidaten suchen
        if not dateien:  # Kommentar: Keine gefunden?
            raise FileNotFoundError("Keine KI-Datei gefunden.")  # Kommentar: Fehler
        pfad_ki_txt = max(dateien, key=os.path.getmtime)  # Kommentar: Neueste nehmen

    if not os.path.isfile(pfad_ki_txt):  # Kommentar: Existiert KI-Datei?
        raise FileNotFoundError(f"KI-Datei existiert nicht: {pfad_ki_txt}")  # Kommentar: Fehler

    if not os.path.isfile(vorlage_pfad):  # Kommentar: Existiert Vorlage?
        raise FileNotFoundError(f"Vorlage existiert nicht: {vorlage_pfad}")  # Kommentar: Fehler

    return ki_datei_verarbeiten(pfad_ki_txt, vorlage_pfad, auswahl, steuerstatus, zus_bez, zus_betrag)  # Kommentar: Verarbeiten und DOCX-Pfad liefern

if __name__ == "__main__":  # Kommentar: Direktlauf
    main()  # Kommentar: Start
