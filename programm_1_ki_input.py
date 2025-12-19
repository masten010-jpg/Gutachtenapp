# programm_1_ki_input.py  # Kommentar: Dateiname zur Orientierung

import os  # Kommentar: Betriebssystemfunktionen für Pfade und Umgebungsvariablen importieren
import time  # Kommentar: Zeitfunktionen (z.B. sleep) importieren
import pdfplumber  # Kommentar: Bibliothek zum Auslesen von Text aus PDF-Dateien importieren
from google import genai  # Kommentar: Google GenAI Client importieren
from google.genai import errors as genai_errors  # Kommentar: Spezifische Fehlerklassen für GenAI importieren

import config  # Kommentar: Eigene config.py importieren, in der die Basis-Pfade definiert sind

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Kommentar: Basisverzeichnis = Ordner, in dem diese Datei liegt

EINGANGS_ORDNER = config.EINGANGS_ORDNER  # Kommentar: Ordnerpfad für eingehende Gutachten aus config übernehmen
KI_ANTWORT_ORDNER = config.KI_ANTWORT_ORDNER  # Kommentar: Ordnerpfad für KI-Antwortdateien aus config übernehmen

GEMINI_MODEL = "gemini-2.5"  # Kommentar: Name des zu verwendenden Gemini-Modells festlegen

MAX_TEXT_CHARS = 1000000  # Kommentar: Maximale Anzahl an Zeichen, die aus dem PDF an die KI geschickt werden
KI_MAX_RETRIES = 3  # Kommentar: Maximale Anzahl an Wiederholungsversuchen beim KI-Aufruf
MIN_TEXT_CHARS = 60000  # Kommentar: Minimale Länge des PDF-Textes, damit das Dokument als "ausreichend" gilt


# ==========================
# Prompt-Zusätze je Variante
# ==========================
def prompt_zusatz(auswahl: str, steuerstatus: str) -> str:  # Kommentar: Funktion, um je nach Abrechnungsvariante Zusatztext für den Prompt zu erzeugen
    basis = f"""
KONTEXT:
- Gewählte Abrechnungsvariante: {auswahl}
- Steuerstatus des Geschädigten: {steuerstatus}
"""  # Kommentar: Basis-Kontakttext mit gewählter Variante und Steuerstatus aufbauen
    if auswahl == "Standard":  # Kommentar: Wenn die ausgewählte Variante "Standard" ist
        return basis + """
REGELN:
- Klassischer Reparaturschaden, keine besondere 130%- oder Totalschadenlogik.
- Wenn nach Gutachten fiktiv abgerechnet wird (keine Reparaturrechnung): Reparaturkosten NETTO.
- Wenn eine konkrete Reparaturrechnung ersichtlich ist: Reparaturkosten BRUTTO und MwSt-Betrag, falls ausgewiesen.
- Merkantiler Minderwert (Wertminderung) ist steuerneutral und wird NETTO berücksichtigt.
"""  # Kommentar: Spezifische Abrechnungsregeln für "Standard" an den Basistext anhängen

    if auswahl == "Wertminderung":  # Kommentar: Wenn die ausgewählte Variante "Wertminderung" ist
        return basis + """
REGELN:
- Fokus auf merkantiler Wertminderung.
- Extrahiere unbedingt den Betrag der Wertminderung (merkantiler Minderwert), falls genannt.
- Wertminderung ist steuerneutral und wird NETTO angegeben.
- Reparaturkosten, Kostenpauschale, Gutachterkosten, Nutzungsausfall, soweit vorhanden, ebenfalls extrahieren.
"""  # Kommentar: Spezielle Regeln für Wertminderung hinzufügen

    if auswahl == "Totalschaden":  # Kommentar: Wenn die ausgewählte Variante "Totalschaden" ist
        return basis + """
REGELN:
- TOTALSCHADEN: Reparaturkosten übersteigen grundsätzlich den Wiederbeschaffungswert (WBW).
- WICHTIG: Extrahiere WIEDERBESCHAFFUNGSWERT (WBW) und RESTWERT des Fahrzeugs.
- Berechnungsbasis ist der Wiederbeschaffungsaufwand = WBW - Restwert.
- Ob netto oder brutto abgerechnet wird, hängt vom Steuerstatus ab:
  * Vorsteuerabzugsberechtigt: Netto-Ausgleich
  * Nicht vorsteuerabzugsberechtigt: Bruttowerte, soweit im Gutachten erkennbar
- Extrahiere ggf. Hinweise auf MwSt im WBW oder in der Ersatzbeschaffung.
"""  # Kommentar: Totalschaden-spezifische Regeln anhängen

    return basis  # Kommentar: Wenn keine spezielle Variante passt, nur den Basistext zurückgeben


PROMPT_TEMPLATE = """
Du bist eine spezialisierte KI für die Auswertung von deutschsprachigen Kfz-Schadensgutachten.

Deine Aufgabe:
- Extrahiere Informationen exakt aus dem Text (ohne Erfinden, ohne Raten).
- Wenn etwas nicht eindeutig im Text steht: "" (leer).
- Antworte auf Deutsch.
- Halte das JSON-Format gültig und exakt.

BESONDERS WICHTIGE FELDER:

1. UNFALL_DATUM / UNFALL_UHRZEIT:
   - Suche nach Formulierungen wie: "am 17.02.2025", "am 17.02.2025 gegen 14:30 Uhr", "Unfallzeit", "Unfalltag".
   - Gib das Datum im Format "TT.MM.JJJJ" zurück.
   - Gib die Uhrzeit im Format "HH:MM" zurück.

2. UNFALLORT / UNFALL_STRASSE:
   - UNFALLORT = Ort/Stadt.
   - UNFALL_STRASSE = Straßenname + Hausnummer/Kreuzung, soweit erkennbar.

3. POLIZEIAKTE_NUMMER:
   - Suche nach Angaben wie "Aktenzeichen", "Polizeivorgangsnummer", "Vorgangsnummer", "Geschäftszeichen" im Zusammenhang mit Polizei.

4. SCHADENSNUMMER:
   - Suche nach "Schadensnummer", "Schaden-Nr.", "Schaden-Nummer".
   - Alternativ: "Versicherungsnummer", "Versicherungsschein-Nr.", "VS-Nr", "VSNR" etc.
   - Wenn sowohl eine echte Schadensnummer als auch eine Versicherungsnummer vorkommen:
     -> Nur die Schadensnummer als SCHADENSNUMMER verwenden.
   - Wenn nur eine Versicherungsnummer o.ä. vorkommt:
     -> Diese als SCHADENSNUMMER verwenden.
   - Erfinde nichts.

5. SCHADENHERGANG:
   - Suche nach einer Überschrift "Schadenhergang", "Schadenshergang", "Unfallhergang", "Sachverhalt" o.ä.
   - Gib den Textabschnitt darunter möglichst WÖRTLICH wieder (kein Umschreiben, keine eigene Zusammenfassung).

6. FRIST_DATUM und HEUTDATUM:
   - Beide Felder bleiben im JSON LEER ("").
   - Sie werden später im System gesetzt.

KOSTENFELDER (sofern im Text eindeutig vorhanden):
- REPARATURKOSTEN
- WERTMINDERUNG (merkantiler Minderwert)
- KOSTENPAUSCHALE
- GUTACHTERKOSTEN
- NUTZUNGSAUSFALL
- MWST_BETRAG
- WIEDERBESCHAFFUNGSWERT (WBW)
- RESTWERT

AUSGABE:
1) Zuerst eine gut lesbare Stichpunktliste im Schema:

   Mandant Vorname: ...
   Mandant Nachname: ...
   Mandant voller Name: ...
   Mandant Straße: ...
   Mandant PLZ Ort: ...

   Unfall Datum: ...
   Unfall Uhrzeit: ...
   Unfallort: ...
   Unfallstraße: ...

   Fahrzeugtyp: ...
   Kennzeichen: ...
   Fahrzeug Kennzeichen: ...

   Polizei Aktennummer: ...
   Schadensnummer: ...
   Aktenzeichen: ...

   Schadenhergang (Originaltext aus dem Gutachten): ...
   Reparaturkosten: ...
   Wertminderung: ...
   Nutzungsausfall: ...
   Kostenpauschale: ...
   Gutachterkosten: ...
   Wiederbeschaffungswert: ...
   Restwert: ...
   MwSt-Betrag (falls relevant): ...

2) Danach GENAU die gleichen Informationen als JSON zwischen JSON_START und JSON_END.

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
"""  # Kommentar: Großer Prompt-Template-String, in den später Zusatztext und Gutachtentext eingesetzt werden


def get_gemini_client():  # Kommentar: Funktion, um einen konfigurierten Gemini-Client zu erzeugen
    api_key = os.getenv("GEMINI_API_KEY")  # Kommentar: API-Key aus Umgebungsvariablen lesen
    if not api_key:  # Kommentar: Wenn kein API-Key in den Umgebungsvariablen gefunden wurde
        try:  # Kommentar: Versuch, den Key aus Streamlit-Secrets zu ziehen
            import streamlit as st  # Kommentar: Streamlit nur lokal importieren, falls verfügbar
            api_key = st.secrets.get("GEMINI_API_KEY")  # Kommentar: API-Key aus Streamlit-Secrets lesen
        except Exception:  # Kommentar: Falls Streamlit nicht verfügbar oder Secrets nicht gesetzt
            api_key = None  # Kommentar: API-Key auf None setzen
    if not api_key:  # Kommentar: Wenn immer noch kein API-Key vorhanden ist
        raise RuntimeError("GEMINI_API_KEY ist nicht gesetzt.")  # Kommentar: Fehler werfen, da ohne Key kein KI-Aufruf möglich ist
    return genai.Client(api_key=api_key)  # Kommentar: Konfigurierten GenAI-Client mit API-Key zurückgeben


def pdf_text_auslesen(pfad: str) -> str:  # Kommentar: Funktion, um den gesamten Text aus einem PDF auszulesen
    seiten_text = []  # Kommentar: Liste für Text aller Seiten initialisieren
    with pdfplumber.open(pfad) as pdf:  # Kommentar: PDF-Datei mit pdfplumber öffnen
        for seite in pdf.pages:  # Kommentar: Über alle Seiten im PDF iterieren
            seiten_text.append(seite.extract_text() or "")  # Kommentar: Text der Seite auslesen, None durch leere Zeichenfolge ersetzen und zur Liste hinzufügen
    return "\n".join(seiten_text)  # Kommentar: Alle Seitentexte mit Zeilenumbrüchen verbinden und zurückgeben


def prompt_bauen(gutachten_text: str, auswahl: str, steuerstatus: str) -> str:  # Kommentar: Funktion, um den finalen Prompt-Text zu bauen
    zusatz = prompt_zusatz(auswahl, steuerstatus)  # Kommentar: Variantenabhängigen Zusatztext erzeugen
    prompt = PROMPT_TEMPLATE.replace("{GUTACHTEN_TEXT}", gutachten_text)  # Kommentar: Platzhalter für Gutachtentext im Template ersetzen
    prompt = prompt.replace("{ZUSATZ}", zusatz.strip())  # Kommentar: Platzhalter für Zusatztext im Template ersetzen
    return prompt  # Kommentar: Fertigen Prompt-Text zurückgeben


def ki_aufrufen(prompt_text: str) -> str:  # Kommentar: Funktion, um den Prompt an Gemini zu schicken und die Antwort zu erhalten
    client = get_gemini_client()  # Kommentar: Konfigurierten Gemini-Client erzeugen
    for versuch in range(1, KI_MAX_RETRIES + 1):  # Kommentar: Mehrfach versuchen, die KI zu kontaktieren (bis KI_MAX_RETRIES)
        try:  # Kommentar: Versuch des KI-Aufrufs
            response = client.models.generate_content(  # Kommentar: Anfrage an das angegebene Modell senden
                model=GEMINI_MODEL,  # Kommentar: Zu verwendendes Modell angeben
                contents=prompt_text,  # Kommentar: Prompt-Text als Inhalt übergeben
            )
            return response.text  # Kommentar: Text-Antwort des Modells zurückgeben
        except genai_errors.ClientError as e:  # Kommentar: Spezifische Client-Fehler abfangen
            if versuch == KI_MAX_RETRIES:  # Kommentar: Wenn dies der letzte Versuch war
                raise RuntimeError(f"Gemini ClientError: {e}") from e  # Kommentar: Fehler mit Zusatzinfo weiterwerfen
            time.sleep(5)  # Kommentar: 5 Sekunden warten, bevor erneut versucht wird
        except Exception:  # Kommentar: Sonstige Fehler abfangen
            if versuch == KI_MAX_RETRIES:  # Kommentar: Wenn letzter Versuch fehlgeschlagen ist
                raise  # Kommentar: Fehler unverändert weiterwerfen
            time.sleep(5)  # Kommentar: 5 Sekunden Pause vor dem nächsten Versuch


def ki_antwort_speichern(basisname: str, ki_text: str) -> str:  # Kommentar: Funktion, um die KI-Antwort in einer Textdatei zu speichern
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: Ordner für KI-Antworten erstellen, falls noch nicht vorhanden
    ziel_pfad = os.path.join(KI_ANTWORT_ORDNER, basisname + "_ki.txt")  # Kommentar: Dateipfad für die KI-Antwort zusammensetzen
    with open(ziel_pfad, "w", encoding="utf-8") as f:  # Kommentar: Zieldatei im Schreibmodus mit UTF-8-Encoding öffnen
        f.write(ki_text)  # Kommentar: KI-Antwort in die Datei schreiben
    return ziel_pfad  # Kommentar: Pfad zur gespeicherten KI-Antwortdatei zurückgeben


def neueste_pdf_finden(ordner: str) -> str | None:  # Kommentar: Funktion, um die neueste PDF-Datei in einem Ordner zu finden
    if not os.path.isdir(ordner):  # Kommentar: Prüfen, ob der Ordner überhaupt existiert
        return None  # Kommentar: Wenn nicht, None zurückgeben
    pdf_pfade = []  # Kommentar: Liste für gefundene PDF-Dateipfade initialisieren
    for datei in os.listdir(ordner):  # Kommentar: Über alle Dateien im Ordner iterieren
        datei_clean = datei.strip()  # Kommentar: Dateinamen von Leerzeichen am Anfang/Ende bereinigen
        if datei_clean.lower().endswith(".pdf"):  # Kommentar: Prüfen, ob die Datei eine PDF-Datei ist (Case-insensitive)
            pdf_pfade.append(os.path.join(ordner, datei_clean))  # Kommentar: Vollständigen Pfad zur Liste hinzufügen
    if not pdf_pfade:  # Kommentar: Wenn keine PDFs gefunden wurden
        return None  # Kommentar: None zurückgeben
    return max(pdf_pfade, key=os.path.getmtime)  # Kommentar: Die neueste PDF anhand des Änderungsdatums bestimmen und zurückgeben


def main(
    pdf_pfad: str | None = None,  # Kommentar: Optionaler Pfad zu einer bestimmten PDF-Datei
    auswahl: str = "Standard",  # Kommentar: Standard-Auswahl der Abrechnungsvariante
    steuerstatus: str = "nicht vorsteuerabzugsberechtigt"  # Kommentar: Standard-Steuerstatus des Geschädigten
) -> str | None:  # Kommentar: Rückgabewert ist optional ein Pfad zur KI-Antwortdatei
    os.makedirs(EINGANGS_ORDNER, exist_ok=True)  # Kommentar: Eingangsordner für Gutachten sicher erstellen
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: Ordner für KI-Antworten sicher erstellen

    if pdf_pfad is None:  # Kommentar: Wenn kein konkreter PDF-Pfad übergeben wurde
        neueste_pdf = neueste_pdf_finden(EINGANGS_ORDNER)  # Kommentar: Neueste PDF im Eingangsordner suchen
        if neueste_pdf is None:  # Kommentar: Wenn keine PDF gefunden wurde
            raise RuntimeError("Kein Gutachten gefunden. Laden Sie ein Gutachten hoch!")  # Kommentar: Fehlermeldung, wenn kein Gutachten vorhanden ist
        zu_verarbeitende_pdf = neueste_pdf  # Kommentar: Neueste PDF als zu verarbeitende Datei setzen
    else:  # Kommentar: Wenn ein spezieller PDF-Pfad übergeben wurde
        zu_verarbeitende_pdf = pdf_pfad  # Kommentar: Übergebene PDF als zu verarbeitende Datei setzen

    voller_text = pdf_text_auslesen(zu_verarbeitende_pdf)  # Kommentar: Gesamten Text aus der PDF-Datei auslesen

    if not voller_text or len(voller_text.strip()) < MIN_TEXT_CHARS:  # Kommentar: Prüfen, ob der Text leer ist oder kürzer als der Mindestwert
        raise RuntimeError(
            "Das hochgeladene Dokument enthält zu wenig verwertbare Informationen. "
            "Laden Sie ein vollständiges Gutachten hoch!"
        )  # Kommentar: Fehlermeldung bei zu wenig Inhalt im Dokument

    gutachten_text = voller_text[:MAX_TEXT_CHARS]  # Kommentar: Text ggf. auf die maximale Zeichenanzahl begrenzen
    prompt = prompt_bauen(gutachten_text, auswahl, steuerstatus)  # Kommentar: Prompt für die KI mit Text, Abrechnungsart und Steuerstatus bauen
    ki_antwort = ki_aufrufen(prompt)  # Kommentar: KI mit dem Prompt aufrufen und Antwort erhalten

    basisname = os.path.splitext(os.path.basename(zu_verarbeitende_pdf))[0]  # Kommentar: Basisdateinamen aus dem PDF-Pfad ermitteln
    pfad_ki = ki_antwort_speichern(basisname, ki_antwort)  # Kommentar: KI-Antwort speichern und Pfad merken
    return pfad_ki  # Kommentar: Pfad zur KI-Antwortdatei zurückgeben


if __name__ == "__main__":  # Kommentar: Prüfen, ob das Skript direkt ausgeführt wird
    main()  # Kommentar: main-Funktion mit Standardparametern aufrufen
