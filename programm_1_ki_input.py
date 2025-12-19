# programm_1_ki_input.py  # Kommentar: Datei für PDF->Text->KI->KI-Antwortdatei

import os  # Kommentar: OS-Funktionen (Pfade/Env) importieren
import time  # Kommentar: Zeitfunktionen (sleep) importieren
import pdfplumber  # Kommentar: PDF-Text-Extraktion importieren
from google import genai  # Kommentar: Google GenAI Client importieren
from google.genai import errors as genai_errors  # Kommentar: GenAI Fehlerklassen importieren

import config  # Kommentar: Eigene Konfiguration importieren

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Kommentar: Basisverzeichnis bestimmen

EINGANGS_ORDNER = config.EINGANGS_ORDNER  # Kommentar: Eingangspfad aus config übernehmen
KI_ANTWORT_ORDNER = config.KI_ANTWORT_ORDNER  # Kommentar: KI-Antwortpfad aus config übernehmen

GEMINI_MODEL = "gemini-2.5-flash"  # Kommentar: Modellname festlegen

MAX_TEXT_CHARS = 1000000  # Kommentar: Maximaler Text, der an die KI gesendet wird
KI_MAX_RETRIES = 3  # Kommentar: Anzahl Retry-Versuche bei KI-Fehlern
MIN_TEXT_CHARS = 60000  # Kommentar: Mindestlänge, damit PDF als ausreichend gilt


def prompt_zusatz(auswahl: str, steuerstatus: str) -> str:  # Kommentar: Varianten-spezifischen Prompt-Zusatz erzeugen
    basis = f"""
KONTEXT:
- Gewählte Abrechnungsvariante: {auswahl}
- Steuerstatus des Geschädigten: {steuerstatus}
"""  # Kommentar: Basis-Kontexttext mit Auswahl und Steuerstatus
    norm = (auswahl or "").lower()  # Kommentar: Auswahl normalisieren (klein), um robust zu vergleichen

    if "fiktive abrechnung" in norm:  # Kommentar: Fall: Fiktive Abrechnung (Reparaturschaden)
        return basis + """
REGELN:
- FIKTIVE ABRECHNUNG: Auszahlung auf Gutachtenbasis ohne Reparaturrechnung.
- Reparaturkosten ausschließlich NETTO (MwSt nicht ansetzen/ausweisen).
- Merkantiler Minderwert (Wertminderung) ist steuerneutral und NETTO.
- Extrahiere: REPARATURKOSTEN, WERTMINDERUNG, KOSTENPAUSCHALE, GUTACHTERKOSTEN, NUTZUNGSAUSFALL (falls vorhanden).
- MWST_BETRAG: nur extrahieren, wenn im Gutachten ausdrücklich genannt, aber bei fiktiv später nicht in Summen einrechnen.
"""  # Kommentar: Regeln für fiktive Abrechnung

    if "konkrete abrechnung" in norm:  # Kommentar: Fall: Konkrete Abrechnung < WBW (Reparatur erfolgt)
        return basis + """
REGELN:
- KONKRETE ABRECHNUNG: Reparatur tatsächlich durchgeführt, Rechnung liegt vor oder wird im Text ersichtlich.
- Reparaturkosten BRUTTO (inkl. MwSt), sofern MwSt im Text erkennbar ist.
- Merkantiler Minderwert (Wertminderung) ist steuerneutral und NETTO.
- Extrahiere: REPARATURKOSTEN, MWST_BETRAG, WERTMINDERUNG, KOSTENPAUSCHALE, GUTACHTERKOSTEN, NUTZUNGSAUSFALL.
"""  # Kommentar: Regeln für konkrete Abrechnung unter WBW

    if "130" in norm:  # Kommentar: Fall: 130%-Regelung
        return basis + """
REGELN:
- 130%-REGELUNG: Reparaturkosten über WBW, aber <= 130% des WBW; fachgerechte Reparatur und Weiternutzung.
- Merkantiler Minderwert wird NICHT ersetzt -> WERTMINDERUNG möglichst leer lassen, falls nur aus Standardpassagen.
- Reparaturkosten BRUTTO (bei Rechnung), MWST_BETRAG extrahieren falls ausgewiesen.
- Extrahiere: REPARATURKOSTEN, MWST_BETRAG, KOSTENPAUSCHALE, GUTACHTERKOSTEN, NUTZUNGSAUSFALL, WIEDERBESCHAFFUNGSWERT (WBW).
"""  # Kommentar: Regeln für 130%-Regel

    if "totalschaden" in norm:  # Kommentar: Fall: Totalschaden-Varianten
        return basis + """
REGELN:
- TOTALSCHADEN: Schwerpunkt auf WBW und Restwert.
- Extrahiere unbedingt: WIEDERBESCHAFFUNGSWERT (WBW) und RESTWERT.
- Zusätzlich: MWST_BETRAG (falls im WBW/Angebot/Ankauf explizit genannt) und Hinweise auf Ersatzbeschaffung.
- Wenn Auswahl "Ersatzbeschaffung": MwSt kann erstattungsfähig sein (bis zur im WBW enthaltenen MwSt), sofern Text dazu vorhanden.
- Steuerstatus beachten: vorsteuerabzugsberechtigt -> MwSt i.d.R. nicht erstatten.
"""  # Kommentar: Regeln für Totalschaden

    return basis  # Kommentar: Fallback: nur Basis-Kontext zurückgeben


PROMPT_TEMPLATE = """
Du bist eine spezialisierte KI für die Auswertung von deutschsprachigen Kfz-Schadensgutachten.

Deine Aufgabe:
- Extrahiere Informationen exakt aus dem Text (ohne Erfinden, ohne Raten).
- Wenn etwas nicht eindeutig im Text steht: "" (leer).
- Antworte auf Deutsch.
- Halte das JSON-Format gültig und exakt.

WICHTIG:
- Erfinde KEINE Daten.
- Rate NICHT.
- Nutze den Original-Wortlaut aus dem Gutachten.

BESONDERS WICHTIGE FELDER:
- UNFALL_DATUM, UNFALL_UHRZEIT, UNFALLORT, UNFALL_STRASSE
- POLIZEIAKTE_NUMMER
- SCHADENSNUMMER (Priorität: echte Schadensnummer > VS-Nr)
- SCHADENHERGANG (Original-Abschnitt unter passender Überschrift)

KOSTENFELDER (sofern eindeutig vorhanden):
- REPARATURKOSTEN
- WERTMINDERUNG
- KOSTENPAUSCHALE
- GUTACHTERKOSTEN
- NUTZUNGSAUSFALL
- MWST_BETRAG
- WIEDERBESCHAFFUNGSWERT
- RESTWERT

AUSGABE:
1) Stichpunkte (lesbar)
2) JSON zwischen JSON_START und JSON_END (nur gültiges JSON)

JSON_START
{
  "MANDANT_VORNAME": "",
  "MANDANT_NACHNAME": "",
  "MANDANT_NAME": "",
  "MANDANT_STRASSE": "",
  "MANDANT_PLZ_ORT": "",

  "UNFALL_DATUM": "",
  "UNFALL_UHRZEIT": "",
  "UNFALLORT": "",
  "UNFALL_STRASSE": "",

  "FAHRZEUGTYP": "",
  "KENNZEICHEN": "",
  "FAHRZEUG_KENNZEICHEN": "",

  "POLIZEIAKTE_NUMMER": "",
  "SCHADENSNUMMER": "",
  "AKTENZEICHEN": "",

  "SCHADENHERGANG": "",

  "REPARATURKOSTEN": "",
  "WERTMINDERUNG": "",
  "KOSTENPAUSCHALE": "",
  "GUTACHTERKOSTEN": "",
  "NUTZUNGSAUSFALL": "",
  "MWST_BETRAG": "",

  "WIEDERBESCHAFFUNGSWERT": "",
  "RESTWERT": "",

  "FRIST_DATUM": "",
  "HEUTDATUM": ""
}
JSON_END

HIER IST DER ZUSÄTZLICHE KONTEXT ZUR ABRECHNUNG:
{ZUSATZ}

HIER IST DAS GUTACHTEN (Textauszug, nutze möglichst viele Infos daraus):
{GUTACHTEN_TEXT}
"""  # Kommentar: Prompt-Template mit Platzhaltern


def get_gemini_client():  # Kommentar: Gemini-Client erstellen (Env + Streamlit Secrets Fallback)
    api_key = os.getenv("GEMINI_API_KEY")  # Kommentar: Zuerst API-Key aus Environment Variable lesen
    if not api_key:  # Kommentar: Wenn Env-Variable nicht gesetzt ist
        try:  # Kommentar: Streamlit-Secrets Fallback versuchen (für Streamlit Cloud typisch)
            import streamlit as st  # Kommentar: Streamlit importieren
            api_key = st.secrets.get("GEMINI_API_KEY")  # Kommentar: API-Key aus Streamlit Secrets lesen
        except Exception:  # Kommentar: Wenn Streamlit nicht verfügbar oder Secret fehlt
            api_key = None  # Kommentar: Explizit None setzen
    if not api_key:  # Kommentar: Wenn immer noch kein Key vorhanden ist
        raise RuntimeError("GEMINI_API_KEY fehlt (Env oder Streamlit Secrets).")  # Kommentar: Verständlicher Fehler
    return genai.Client(api_key=api_key)  # Kommentar: GenAI Client mit Key zurückgeben
def pdf_text_auslesen(pfad: str) -> str:  # Kommentar: PDF-Text auslesen
    seiten_text = []  # Kommentar: Liste für Seitentexte
    with pdfplumber.open(pfad) as pdf:  # Kommentar: PDF öffnen
        for seite in pdf.pages:  # Kommentar: Seiten iterieren
            seiten_text.append(seite.extract_text() or "")  # Kommentar: Text extrahieren oder leer
    return "\n".join(seiten_text)  # Kommentar: Zusammenfügen


def prompt_bauen(gutachten_text: str, auswahl: str, steuerstatus: str) -> str:  # Kommentar: Prompt final bauen
    zusatz = prompt_zusatz(auswahl, steuerstatus)  # Kommentar: Zusatz holen
    prompt = PROMPT_TEMPLATE.replace("{GUTACHTEN_TEXT}", gutachten_text)  # Kommentar: Gutachtentext einsetzen
    prompt = prompt.replace("{ZUSATZ}", zusatz.strip())  # Kommentar: Zusatz einsetzen
    return prompt  # Kommentar: Prompt zurückgeben


def ki_aufrufen(prompt_text: str) -> str:  # Kommentar: KI aufrufen
    client = get_gemini_client()  # Kommentar: Client holen
    for versuch in range(1, KI_MAX_RETRIES + 1):  # Kommentar: Retries
        try:  # Kommentar: Versuch starten
            response = client.models.generate_content(  # Kommentar: Anfrage an Gemini
                model=GEMINI_MODEL,  # Kommentar: Modell wählen
                contents=prompt_text,  # Kommentar: Prompt senden
            )
            return response.text  # Kommentar: Antworttext zurückgeben
        except genai_errors.ClientError as e:  # Kommentar: ClientError abfangen
            if versuch == KI_MAX_RETRIES:  # Kommentar: Letzter Versuch?
                raise RuntimeError(f"Gemini ClientError: {e}") from e  # Kommentar: Eskalieren
            time.sleep(5)  # Kommentar: Warten
        except Exception:  # Kommentar: Sonstige Fehler
            if versuch == KI_MAX_RETRIES:  # Kommentar: Letzter Versuch?
                raise  # Kommentar: Eskalieren
            time.sleep(5)  # Kommentar: Warten


def ki_antwort_speichern(basisname: str, ki_text: str) -> str:  # Kommentar: KI-Antwort speichern
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: Ordner sicher anlegen
    ziel_pfad = os.path.join(KI_ANTWORT_ORDNER, basisname + "_ki.txt")  # Kommentar: Zielpfad bauen
    with open(ziel_pfad, "w", encoding="utf-8") as f:  # Kommentar: Datei öffnen
        f.write(ki_text)  # Kommentar: Schreiben
    return ziel_pfad  # Kommentar: Pfad zurückgeben


def main(pdf_pfad: str | None = None, auswahl: str = "", steuerstatus: str = "") -> str | None:  # Kommentar: Hauptfunktion
    os.makedirs(EINGANGS_ORDNER, exist_ok=True)  # Kommentar: Eingang sicherstellen
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: KI-Ordner sicherstellen

    if pdf_pfad is None:  # Kommentar: Wenn keine PDF übergeben wurde
        raise RuntimeError("pdf_pfad muss übergeben werden.")  # Kommentar: In Multiuser-Umgebung nicht automatisch suchen

    voller_text = pdf_text_auslesen(pdf_pfad)  # Kommentar: Text extrahieren

    if not voller_text or len(voller_text.strip()) < MIN_TEXT_CHARS:  # Kommentar: Mindestlänge prüfen
        raise RuntimeError("Das Dokument enthält zu wenig verwertbaren Text.")  # Kommentar: Fehler

    gutachten_text = voller_text[:MAX_TEXT_CHARS]  # Kommentar: Kürzen
    prompt = prompt_bauen(gutachten_text, auswahl, steuerstatus)  # Kommentar: Prompt bauen
    ki_antwort = ki_aufrufen(prompt)  # Kommentar: KI ausführen

    basisname = os.path.splitext(os.path.basename(pdf_pfad))[0]  # Kommentar: Basisname
    pfad_ki = ki_antwort_speichern(basisname, ki_antwort)  # Kommentar: Speichern
    return pfad_ki  # Kommentar: Pfad zurückgeben


if __name__ == "__main__":  # Kommentar: Direktausführung
    main()  # Kommentar: Aufrufen (wird hier i.d.R. nicht genutzt)
