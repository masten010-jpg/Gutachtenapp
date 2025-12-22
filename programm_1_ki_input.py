# programm_1_ki_input.py  # Kommentar: Programm 1 (PDF -> Text -> Gemini -> KI-Antwortdatei)

import os  # Kommentar: Betriebssystem-Funktionen (Pfade/Env) importieren
import time  # Kommentar: Zeitfunktionen (sleep) importieren
import pdfplumber  # Kommentar: PDF-Text-Extraktion importieren
from google import genai  # Kommentar: Google GenAI Client importieren
from google.genai import errors as genai_errors  # Kommentar: GenAI Fehlerklassen importieren
import config  # Kommentar: Eigene Konfigurationsdatei importieren

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Kommentar: Basisverzeichnis des Projekts bestimmen

EINGANGS_ORDNER = config.EINGANGS_ORDNER  # Kommentar: Eingangsordner aus config übernehmen
KI_ANTWORT_ORDNER = config.KI_ANTWORT_ORDNER  # Kommentar: KI-Antwortordner aus config übernehmen

GEMINI_MODEL = "gemini-2.5-flash"  # Kommentar: Stabiler Modellname für generate_content setzen

MAX_TEXT_CHARS = 12000  # Kommentar: Begrenzung, damit Requests nicht zu groß werden (Streamlit Cloud stabil)
KI_MAX_RETRIES = 3  # Kommentar: Maximaler Retry-Zähler für KI-Aufrufe
MIN_TEXT_CHARS = 6000  # Kommentar: Mindestlänge des extrahierten Textes (sonst Abbruch)


def prompt_zusatz(auswahl: str, steuerstatus: str) -> str:  # Kommentar: Zusätzlichen Kontext je Abrechnungsvariante erzeugen
    basis = f"""  # Kommentar: Basis-Kontext-Block starten
KONTEXT:  # Kommentar: Überschrift
- Gewählte Abrechnungsvariante: {auswahl}  # Kommentar: Auswahl einfügen
- Steuerstatus des Geschädigten: {steuerstatus}  # Kommentar: Steuerstatus einfügen
"""  # Kommentar: Basis-Kontext-Block beenden
    norm = (auswahl or "").lower()  # Kommentar: Auswahl normalisieren (lower), um robust zu vergleichen

    if "fiktive abrechnung" in norm:  # Kommentar: Fall: Fiktive Abrechnung (Reparaturschaden)
        return basis + """  # Kommentar: Regeln für fiktive Abrechnung anhängen
REGELN:  # Kommentar: Überschrift
- FIKTIVE ABRECHNUNG: Auszahlung auf Gutachtenbasis ohne Reparaturrechnung.  # Kommentar: Regel
- Reparaturkosten ausschließlich NETTO (MwSt nicht ansetzen/ausweisen).  # Kommentar: Regel
- Merkantiler Minderwert (Wertminderung) ist steuerneutral und NETTO.  # Kommentar: Regel
- Extrahiere: REPARATURKOSTEN, WERTMINDERUNG, KOSTENPAUSCHALE, GUTACHTERKOSTEN, NUTZUNGSAUSFALL (falls vorhanden).  # Kommentar: Regel
- MWST_BETRAG: nur extrahieren, wenn im Gutachten ausdrücklich genannt, aber bei fiktiv später nicht in Summen einrechnen.  # Kommentar: Regel
"""  # Kommentar: Textblock Ende

    if "konkrete abrechnung" in norm:  # Kommentar: Fall: Konkrete Abrechnung < WBW
        return basis + """  # Kommentar: Regeln für konkrete Abrechnung anhängen
REGELN:  # Kommentar: Überschrift
- KONKRETE ABRECHNUNG: Reparatur tatsächlich durchgeführt, Rechnung liegt vor oder wird im Text ersichtlich.  # Kommentar: Regel
- Reparaturkosten BRUTTO (inkl. MwSt), sofern MwSt im Text erkennbar ist.  # Kommentar: Regel
- Merkantiler Minderwert (Wertminderung) ist steuerneutral und NETTO.  # Kommentar: Regel
- Extrahiere: REPARATURKOSTEN, MWST_BETRAG, WERTMINDERUNG, KOSTENPAUSCHALE, GUTACHTERKOSTEN, NUTZUNGSAUSFALL.  # Kommentar: Regel
"""  # Kommentar: Textblock Ende

    if "130" in norm:  # Kommentar: Fall: 130%-Regelung
        return basis + """  # Kommentar: Regeln für 130%-Regelung anhängen
REGELN:  # Kommentar: Überschrift
- 130%-REGELUNG: Reparaturkosten über WBW, aber <= 130% des WBW; fachgerechte Reparatur und Weiternutzung.  # Kommentar: Regel
- Merkantiler Minderwert wird NICHT ersetzt -> WERTMINDERUNG möglichst leer lassen, falls nur aus Standardpassagen.  # Kommentar: Regel
- Reparaturkosten BRUTTO (bei Rechnung), MWST_BETRAG extrahieren falls ausgewiesen.  # Kommentar: Regel
- Extrahiere: REPARATURKOSTEN, MWST_BETRAG, KOSTENPAUSCHALE, GUTACHTERKOSTEN, NUTZUNGSAUSFALL, WIEDERBESCHAFFUNGSWERT (WBW).  # Kommentar: Regel
"""  # Kommentar: Textblock Ende

    if "totalschaden" in norm:  # Kommentar: Fall: Totalschaden-Varianten
        return basis + """  # Kommentar: Regeln für Totalschaden anhängen
REGELN:  # Kommentar: Überschrift
- TOTALSCHADEN: Schwerpunkt auf WBW und Restwert.  # Kommentar: Regel
- Extrahiere unbedingt: WIEDERBESCHAFFUNGSWERT (WBW) und RESTWERT.  # Kommentar: Regel
- Zusätzlich: MWST_BETRAG (falls im WBW/Angebot/Ankauf explizit genannt) und Hinweise auf Ersatzbeschaffung.  # Kommentar: Regel
- Wenn Auswahl "Ersatzbeschaffung": MwSt kann erstattungsfähig sein (bis zur im WBW enthaltenen MwSt), sofern Text dazu vorhanden.  # Kommentar: Regel
- Steuerstatus beachten: vorsteuerabzugsberechtigt -> MwSt i.d.R. nicht erstatten.  # Kommentar: Regel
"""  # Kommentar: Textblock Ende

    return basis  # Kommentar: Fallback: nur Basis-Kontext zurückgeben


PROMPT_TEMPLATE = """  # Kommentar: Prompt-Template (KI soll extrahieren und JSON liefern)
Du bist eine spezialisierte KI für die Auswertung von deutschsprachigen Kfz-Schadensgutachten.  # Kommentar: Systembeschreibung

Deine Aufgabe:  # Kommentar: Aufgabenbeschreibung
- Extrahiere Informationen exakt aus dem Text (ohne Erfinden, ohne Raten).  # Kommentar: Regel
- Wenn etwas nicht eindeutig im Text steht: "" (leer).  # Kommentar: Regel
- Antworte auf Deutsch.  # Kommentar: Regel
- Halte das JSON-Format gültig und exakt.  # Kommentar: Regel

WICHTIG:  # Kommentar: Wichtige Regeln
- Erfinde KEINE Daten.  # Kommentar: Regel
- Rate NICHT.  # Kommentar: Regel
- Nutze den Original-Wortlaut aus dem Gutachten.  # Kommentar: Regel

BESONDERS WICHTIGE FELDER:  # Kommentar: Fokusfelder
- UNFALL_DATUM, UNFALL_UHRZEIT, UNFALLORT, UNFALL_STRASSE  # Kommentar: Fokus
- POLIZEIAKTE_NUMMER  # Kommentar: Fokus
- SCHADENSNUMMER (Priorität: echte Schadensnummer > VS-Nr)  # Kommentar: Fokus
- SCHADENHERGANG (Original-Abschnitt unter passender Überschrift)  # Kommentar: Fokus

KOSTENFELDER (sofern eindeutig vorhanden):  # Kommentar: Kostenfelder
- REPARATURKOSTEN  # Kommentar: Feld
- WERTMINDERUNG  # Kommentar: Feld
- KOSTENPAUSCHALE  # Kommentar: Feld
- GUTACHTERKOSTEN  # Kommentar: Feld
- NUTZUNGSAUSFALL  # Kommentar: Feld
- MWST_BETRAG  # Kommentar: Feld
- WIEDERBESCHAFFUNGSWERT  # Kommentar: Feld
- RESTWERT  # Kommentar: Feld

AUSGABE:  # Kommentar: Ausgabeanforderung
1) Stichpunkte (lesbar)  # Kommentar: Teil 1
2) JSON zwischen JSON_START und JSON_END (nur gültiges JSON)  # Kommentar: Teil 2

JSON_START  # Kommentar: Marker Start
{
  "MANDANT_VORNAME": "",  # Kommentar: Key
  "MANDANT_NACHNAME": "",  # Kommentar: Key
  "MANDANT_NAME": "",  # Kommentar: Key
  "MANDANT_STRASSE": "",  # Kommentar: Key
  "MANDANT_PLZ_ORT": "",  # Kommentar: Key

  "UNFALL_DATUM": "",  # Kommentar: Key
  "UNFALL_UHRZEIT": "",  # Kommentar: Key
  "UNFALLORT": "",  # Kommentar: Key
  "UNFALL_STRASSE": "",  # Kommentar: Key

  "FAHRZEUGTYP": "",  # Kommentar: Key
  "KENNZEICHEN": "",  # Kommentar: Key
  "FAHRZEUG_KENNZEICHEN": "",  # Kommentar: Key

  "POLIZEIAKTE_NUMMER": "",  # Kommentar: Key
  "SCHADENSNUMMER": "",  # Kommentar: Key
  "AKTENZEICHEN": "",  # Kommentar: Key

  "SCHADENHERGANG": "",  # Kommentar: Key

  "REPARATURKOSTEN": "",  # Kommentar: Key
  "WERTMINDERUNG": "",  # Kommentar: Key
  "KOSTENPAUSCHALE": "",  # Kommentar: Key
  "GUTACHTERKOSTEN": "",  # Kommentar: Key
  "NUTZUNGSAUSFALL": "",  # Kommentar: Key
  "MWST_BETRAG": "",  # Kommentar: Key

  "WIEDERBESCHAFFUNGSWERT": "",  # Kommentar: Key
  "RESTWERT": "",  # Kommentar: Key

  "FRIST_DATUM": "",  # Kommentar: Key
  "HEUTDATUM": ""  # Kommentar: Key
}
JSON_END  # Kommentar: Marker Ende

HIER IST DER ZUSÄTZLICHE KONTEXT ZUR ABRECHNUNG:  # Kommentar: Zusatzkontext
{ZUSATZ}  # Kommentar: Placeholder

HIER IST DAS GUTACHTEN (Textauszug, nutze möglichst viele Infos daraus):  # Kommentar: Gutachtentext
{GUTACHTEN_TEXT}  # Kommentar: Placeholder
"""  # Kommentar: Ende Prompt-Template


def get_gemini_client():  # Kommentar: Gemini-Client erstellen (Env + Streamlit-Secrets Fallback)
    api_key = os.getenv("GEMINI_API_KEY")  # Kommentar: Zuerst aus Environment Variable lesen
    if not api_key:  # Kommentar: Wenn Env-Variable nicht gesetzt ist
        try:  # Kommentar: Fallback für Streamlit Cloud versuchen
            import streamlit as st  # Kommentar: Streamlit importieren
            api_key = st.secrets.get("GEMINI_API_KEY")  # Kommentar: API-Key aus Secrets holen
        except Exception:  # Kommentar: Wenn Streamlit/Secrets nicht verfügbar
            api_key = None  # Kommentar: explizit None setzen
    print("[DEBUG] GEMINI_API_KEY vorhanden:", bool(api_key))  # Kommentar: Nur True/False loggen (Key niemals ausgeben!)
    if not api_key:  # Kommentar: Wenn immer noch kein Key vorhanden
        raise RuntimeError("GEMINI_API_KEY fehlt (Env oder Streamlit Secrets).")  # Kommentar: Klarer Fehler
    return genai.Client(api_key=api_key)  # Kommentar: Client mit Key erstellen und zurückgeben


def pdf_text_auslesen(pfad: str) -> str:  # Kommentar: PDF-Text extrahieren
    seiten_text = []  # Kommentar: Liste für Seitentexte
    with pdfplumber.open(pfad) as pdf:  # Kommentar: PDF öffnen
        for seite in pdf.pages:  # Kommentar: Seiten iterieren
            seiten_text.append(seite.extract_text() or "")  # Kommentar: Text extrahieren (oder leer)
    return "\n".join(seiten_text)  # Kommentar: Seiten zusammenfügen und zurückgeben


def prompt_bauen(gutachten_text: str, auswahl: str, steuerstatus: str) -> str:  # Kommentar: Prompt final erstellen
    zusatz = prompt_zusatz(auswahl, steuerstatus)  # Kommentar: Zusatzkontext bauen
    prompt = PROMPT_TEMPLATE.replace("{GUTACHTEN_TEXT}", gutachten_text)  # Kommentar: Gutachtentext einsetzen
    prompt = prompt.replace("{ZUSATZ}", zusatz.strip())  # Kommentar: Zusatz einsetzen
    return prompt  # Kommentar: Prompt zurückgeben


def ki_aufrufen(prompt_text: str) -> str:  # Kommentar: Gemini aufrufen und Antworttext zurückgeben
    client = get_gemini_client()  # Kommentar: Gemini Client holen
    print("[DEBUG] Verwende Modell:", GEMINI_MODEL)  # Kommentar: Modell in Logs ausgeben
    print("[DEBUG] Prompt-Länge Zeichen:", len(prompt_text))  # Kommentar: Prompt-Länge loggen
    for versuch in range(1, KI_MAX_RETRIES + 1):  # Kommentar: Retry-Schleife
        try:  # Kommentar: Versuch starten
            response = client.models.generate_content(  # Kommentar: Content generieren
                model=GEMINI_MODEL,  # Kommentar: Modell übergeben
                contents=prompt_text,  # Kommentar: Prompt übergeben
            )  # Kommentar: Call Ende
            return response.text  # Kommentar: Antworttext zurückgeben
        except genai_errors.ClientError as e:  # Kommentar: ClientError (Auth/Quota/BadRequest) abfangen
            msg = f"Gemini ClientError: {repr(e)}"  # Kommentar: repr enthält oft Statuscodes/Details
            print(msg)  # Kommentar: Fehler in Logs schreiben
            if versuch == KI_MAX_RETRIES:  # Kommentar: Letzter Versuch?
                raise RuntimeError(msg) from e  # Kommentar: Eskalieren mit Details
            time.sleep(5)  # Kommentar: Kurz warten und erneut versuchen
        except Exception as e:  # Kommentar: Sonstige Fehler abfangen
            msg = f"Allgemeiner Fehler bei Gemini: {repr(e)}"  # Kommentar: Fehlertext bauen
            print(msg)  # Kommentar: In Logs schreiben
            if versuch == KI_MAX_RETRIES:  # Kommentar: Letzter Versuch?
                raise RuntimeError(msg) from e  # Kommentar: Eskalieren
            time.sleep(5)  # Kommentar: Kurz warten


def ki_antwort_speichern(basisname: str, ki_text: str) -> str:  # Kommentar: KI-Antwort in Datei speichern
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: Ordner sicherstellen
    ziel_pfad = os.path.join(KI_ANTWORT_ORDNER, basisname + "_ki.txt")  # Kommentar: Zielpfad bilden
    with open(ziel_pfad, "w", encoding="utf-8") as f:  # Kommentar: Datei öffnen
        f.write(ki_text)  # Kommentar: Inhalt schreiben
    return ziel_pfad  # Kommentar: Pfad zurückgeben


def main(pdf_pfad: str | None = None, auswahl: str = "", steuerstatus: str = "") -> str | None:  # Kommentar: Entry-Point
    os.makedirs(EINGANGS_ORDNER, exist_ok=True)  # Kommentar: Eingang sicherstellen
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: KI-Ordner sicherstellen

    if pdf_pfad is None:  # Kommentar: PDF muss übergeben werden (Multi-User sicher)
        raise RuntimeError("pdf_pfad muss übergeben werden.")  # Kommentar: Fehler

    voller_text = pdf_text_auslesen(pdf_pfad)  # Kommentar: PDF-Text extrahieren

    if not voller_text or len(voller_text.strip()) < MIN_TEXT_CHARS:  # Kommentar: Mindesttext prüfen
        raise RuntimeError("Das Dokument enthält zu wenig verwertbaren Text.")  # Kommentar: Fehler

    gutachten_text = voller_text[:MAX_TEXT_CHARS]  # Kommentar: Text begrenzen
    prompt = prompt_bauen(gutachten_text, auswahl, steuerstatus)  # Kommentar: Prompt bauen
    ki_antwort = ki_aufrufen(prompt)  # Kommentar: KI aufrufen

    basisname = os.path.splitext(os.path.basename(pdf_pfad))[0]  # Kommentar: Basisname aus PDF-Datei
    pfad_ki = ki_antwort_speichern(basisname, ki_antwort)  # Kommentar: Antwort speichern
    return pfad_ki  # Kommentar: Pfad zur KI-Datei zurückgeben


if __name__ == "__main__":  # Kommentar: Direktausführung
    main()  # Kommentar: Aufruf
