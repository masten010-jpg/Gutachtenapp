# programm_1_ki_input.py
# Aufgabe:
# - Neueste PDF in "eingang_gutachten" finden
# - Text auslesen
# - Klaren Extraktions-Prompt an Google Gemini schicken
# - Antwort als *_ki.txt in "ki_antworten" speichern
# - Pfad zur gespeicherten *_ki.txt zurückgeben

import os
import time
import pdfplumber
from google import genai
from google.genai import errors as genai_errors

# -------------------------
# BASISPFAD & ORDNER
# -------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EINGANGS_ORDNER = os.path.join(BASE_DIR, "eingang_gutachten")
KI_ANTWORT_ORDNER = os.path.join(BASE_DIR, "ki_antworten")

# Modellname für Gemini 2.5 Flash-Lite
GEMINI_MODEL = "gemini-2.5-flash"

MAX_TEXT_CHARS = 8000
KI_MAX_RETRIES = 3
KI_TIMEOUT_SEKUNDEN = 60  # nur Info für Logs
MIN_TEXT_CHARS = 500      # Mindestlänge, damit es als "Gutachten" durchgeht


PROMPT_TEMPLATE = """
Du bist eine spezialisierte KI für die Auswertung von deutschsprachigen Kfz-Schadensgutachten.
Deine einzige Aufgabe ist es, bestimmte Informationen GENAU so aus dem Text zu EXTRAHIEREN,
wie sie dort stehen (Namen, Adressen, Orte, Daten, Kennzeichen, Geldbeträge, Textpassagen).

WICHTIG:
- Erfinde KEINE Daten. Wenn etwas nicht eindeutig im Text steht, setze den Wert auf "".
- Rate NICHT. Lieber "" als eine Vermutung.
- Nutze den Original-Wortlaut aus dem Gutachten (z.B. Straßennamen, Ortsnamen).
- Antworte ausschließlich auf DEUTSCH.
- Halte dich EXAKT an die vorgegebenen Feldnamen und an das Ausgabeschema.

BESONDERS WICHTIGE FELDER (NICHT LEER LASSEN, WENN IM TEXT IRGENDWO ERWÄHNT):

1. UNFALL_DATUM / UNFALL_UHRZEIT:
   - Suche nach Formulierungen wie: "am 17.02.2025", "am 17.02.2025 gegen 14:30 Uhr", "Unfallzeit", "Unfalltag".
   - Gib das Datum im Format "TT.MM.JJJJ" zurück (z.B. "17.02.2025").
   - Gib die Uhrzeit im Format "HH:MM" zurück (z.B. "14:30").

2. UNFALLORT / UNFALL_STRASSE:
   - Suche nach Formulierungen wie: "im Bereich", "in Höhe von", "auf der Straße", "an der Kreuzung", "Unfallort".
   - UNFALLORT ist typischerweise "Stadt / Ort", UNFALL_STRASSE ist typischerweise "Straßenname + Hausnummer / Kreuzung".

3. POLIZEIAKTE_NUMMER:
   - Suche nach Angaben wie "Aktenzeichen", "Polizeivorgangsnummer", "Vorgangsnummer", "Geschäftszeichen" im Zusammenhang mit Polizei.
   - Wenn du eine solche Nummer findest, trage sie in POLIZEIAKTE_NUMMER ein.

4. SCHADENHERGANG:
   - Suche nach einer Überschrift wie "Schadenhergang", "Schadenshergang" oder einer sehr ähnlichen Formulierung.
   - Wenn es keine solche Überschrift gibt, suche nach "Unfallhergang" oder "Sachverhalt".
   - Für SCHADENHERGANG sollst du den TEXTABSCHNITT UNTERHALB DIESER ÜBERSCHRIFT möglichst WÖRTLICH übernehmen.
   - KEINE UMSCHREIBUNG, KEINE ZUSAMMENFASSUNG, KEINE eigenen Formulierungen. So nah wie möglich am Original.
   - Typischerweise endet der Abschnitt beim nächsten Überschriftstitel oder einem deutlichen Themenwechsel.
   - Wenn du keine passende Überschrift findest, setze SCHADENHERGANG auf "".

5. FRIST_DATUM:
   - Dieses Feld lässt du LEER (""), es wird später automatisch vom System gesetzt (14 Tage ab Datum des Schreibens).

6. SCHADENSNUMMER:
   - Suche nach Angaben wie "Schadensnummer", "Schaden-Nr.", "Schaden-Nr", "Schaden-Nummer".
   - Typischerweise von einer Versicherung oder einem regulierenden Unternehmen vergeben.
   - Wenn vorhanden, gib sie EXAKT so zurück, wie sie im Text steht (inkl. / - . etc.).
   - Wenn keine Schadensnummer erkennbar ist, setze "".

7. AKTENZEICHEN:
   - Suche nach "Aktenzeichen", "Az.", "AZ:" außerhalb des Polizeikontexts, z.B. als internes Aktenzeichen, Kanzlei- oder Gerichtszeichen.
   - Wenn ein solches Aktenzeichen vorhanden ist, gib es EXAKT so zurück.
   - Wenn kein Aktenzeichen erkennbar ist, setze "".

8. HEUTDATUM:
   - Dieses Feld lässt du LEER ("").
   - Es wird vom System automatisch mit dem Datum der Verarbeitung/Upload gefüllt.

AUSGABEFORMAT:

1. Zuerst eine gut lesbare Stichpunktliste im folgenden Schema:

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

   Polizei Aktennummer (VG/.../...): ...
   Schadensnummer: ...
   Aktenzeichen: ...

   Schadenhergang (Originaltext aus dem Gutachten): ...
   Reparaturkosten: ...
   Wertminderung: ...
   Kostenpauschale: ...
   Gutachterkosten: ...
   Kostensumme X (Reparatur + Wertminderung + Kostenpauschale + Gutachterkosten): ...

   Heutiges Datum (wird vom System gesetzt): ...

2. Danach gibst du GENAU die gleichen Informationen als reines JSON aus.
   WICHTIG:
   - Schreibe das JSON zwischen die Marker JSON_START und JSON_END.
   - Innerhalb dieser Marker nur gültiges JSON, KEINE Kommentare, KEINE Erklärung.
   - Strings immer in Anführungszeichen.
   - Verwende GENAU die folgenden Keys (nicht mehr, nicht weniger).

JSON-FORMAT (verwende GENAU diese Keys):

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
  "KOSTENSUMME_X": "",

  "FRIST_DATUM": "",
  "HEUTDATUM": ""
}
JSON_END

HIER IST DAS GUTACHTEN (nur ein Ausschnitt, aber benutze so viele Infos wie möglich daraus):

{GUTACHTEN_TEXT}
"""


def get_gemini_client():
    """API-Key aus Env oder Streamlit-Secrets holen und Client bauen."""
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            api_key = None

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY ist nicht gesetzt. "
            "Bitte als Umgebungsvariable oder in Streamlit-Secrets hinterlegen."
        )

    return genai.Client(api_key=api_key)


def pdf_text_auslesen(pfad: str) -> str:
    seiten_text = []
    with pdfplumber.open(pfad) as pdf:
        for seite in pdf.pages:
            seiten_text.append(seite.extract_text() or "")
    return "\n".join(seiten_text)


def prompt_bauen(gutachten_text: str) -> str:
    return PROMPT_TEMPLATE.replace("{GUTACHTEN_TEXT}", gutachten_text)


def ki_aufrufen(prompt_text: str) -> str:
    client = get_gemini_client()

    for versuch in range(1, KI_MAX_RETRIES + 1):
        print(f"[DEBUG] Sende Request an Gemini – Versuch {versuch}/{KI_MAX_RETRIES}")
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt_text,
                # generation_config={"temperature": 0.0},
            )
            text = response.text
            print("[DEBUG] KI-Antwort erfolgreich empfangen.")
            return text

        except genai_errors.ClientError as e:
            msg = f"Gemini ClientError: {e}"
            print(msg)
            if versuch == KI_MAX_RETRIES:
                raise RuntimeError(msg) from e
            print("Warte 5 Sekunden und versuche es erneut...")
            time.sleep(5)

        except Exception as e:
            print("Allgemeiner Fehler beim Aufruf von Gemini:", e)
            if versuch == KI_MAX_RETRIES:
                raise
            print("Warte 5 Sekunden und versuche es erneut...")
            time.sleep(5)


def ki_antwort_speichern(basisname: str, ki_text: str) -> str:
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)
    ziel_pfad = os.path.join(KI_ANTWORT_ORDNER, basisname + "_ki.txt")
    with open(ziel_pfad, "w", encoding="utf-8") as f:
        f.write(ki_text)
    print(f"KI-Antwort gespeichert: {ziel_pfad}")
    return ziel_pfad


def neueste_pdf_finden(ordner: str) -> str | None:
    print(f"[DEBUG] Absoluter Ordnerpfad: {ordner}")
    if not os.path.isdir(ordner):
        print("[DEBUG] Ordner existiert NICHT!")
        return None

    alle_dateien = os.listdir(ordner)
    print(f"[DEBUG] Dateien im Ordner: {alle_dateien}")

    pdf_pfade = []
    for datei in alle_dateien:
        datei_clean = datei.strip()
        if datei_clean.lower().endswith(".pdf"):
            vollpfad = os.path.join(ordner, datei_clean)
            pdf_pfade.append(vollpfad)

    print(f"[DEBUG] Erkannte PDF-Dateien: {pdf_pfade}")

    if not pdf_pfade:
        return None

    neueste = max(pdf_pfade, key=lambda p: os.path.getmtime(p))
    return neueste


def main() -> str | None:
    os.makedirs(EINGANGS_ORDNER, exist_ok=True)
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)

    print("Base dir:", BASE_DIR)
    print("Suche neueste PDF in:", EINGANGS_ORDNER)

    neueste_pdf = neueste_pdf_finden(EINGANGS_ORDNER)

    if neueste_pdf is None:
        print("Keine PDF-Datei im Ordner gefunden.")
        raise RuntimeError("Kein Gutachten gefunden. Laden Sie ein Gutachten hoch!")

    print(f"Neueste PDF gefunden: {neueste_pdf}")

    voller_text = pdf_text_auslesen(neueste_pdf)
    print("[DEBUG] Länge des vollen Gutachten-Textes:", len(voller_text), "Zeichen")

    if not voller_text or len(voller_text.strip()) < MIN_TEXT_CHARS:
        print("Zu wenig verwertbarer Text im Dokument. Abbruch.")
        raise RuntimeError(
            "Das hochgeladene Dokument enthält zu wenig verwertbare Informationen. "
            "Laden Sie ein vollständiges Gutachten hoch!"
        )

    gutachten_text = voller_text
    if len(gutachten_text) > MAX_TEXT_CHARS:
        print(f"[DEBUG] Kürze Text auf die ersten {MAX_TEXT_CHARS} Zeichen.")
        gutachten_text = gutachten_text[:MAX_TEXT_CHARS]

    prompt = prompt_bauen(gutachten_text)
    print("[DEBUG] Prompt-Länge:", len(prompt), "Zeichen")
    print("Sende Gutachten an Gemini...")

    ki_antwort = ki_aufrufen(prompt)

    basisname = os.path.splitext(os.path.basename(neueste_pdf))[0]
    pfad_ki = ki_antwort_speichern(basisname, ki_antwort)

    print("Fertig. Diese eine PDF wurde verarbeitet.")
    return pfad_ki


if __name__ == "__main__":
    main()
