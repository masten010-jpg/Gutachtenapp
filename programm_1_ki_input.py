# programm_1_ki_input.py
# Aufgabe:
# - Neueste PDF in "eingang_gutachten" finden
# - Text auslesen
# - Text begrenzen
# - Klaren Extraktions-Prompt an die KI schicken (Google Gemini)
# - Antwort als *_ki.txt in "ki_antworten" speichern

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

GEMINI_MODEL = "gemini-2.5-flash-lite"

# Konfiguration
MAX_TEXT_CHARS = 8000       # mehr Kontext für Unfallhergang etc.
KI_MAX_RETRIES = 3
KI_TIMEOUT_SEKUNDEN = 60    # aktuell nur für Logging / Retry genutzt


PROMPT_TEMPLATE = """
Du bist eine spezialisierte KI für die Auswertung von deutschsprachigen Kfz-Schadensgutachten.
Deine einzige Aufgabe ist es, bestimmte Informationen GENAU so aus dem Text zu EXTRAHIEREN,
wie sie dort stehen (Namen, Adressen, Orte, Daten, Kennzeichen, Geldbeträge).

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
   - Wenn es mehrere Aktenzeichen gibt, nimm dasjenige, das eindeutig zur Polizei passt.

4. UNFALLHERGANG:
   - Suche nach Abschnitten, die den Ablauf des Unfalls beschreiben ("Unfallhergang", "Sachverhalt", "zum Hergang", "es ereignete sich folgender Unfall").
   - Fasse den beschriebenen Unfallhergang in 2–4 SÄTZEN kurz zusammen.
   - Verwende NUR Informationen, die im Text stehen, keine eigenen Ergänzungen.

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

   Wie ereignete sich der Unfall: ...
   Reparaturkosten: ...
   Wertminderung: ...
   Kostenpauschale: ...
   Gutachterkosten: ...
   Kostensumme X (Reparatur + Wertminderung + Kostenpauschale + Gutachterkosten): ...

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

  "UNFALLHERGANG": "",

  "REPARATURKOSTEN": "",
  "WERTMINDERUNG": "",
  "KOSTENPAUSCHALE": "",
  "GUTACHTERKOSTEN": "",
  "KOSTENSUMME_X": ""
}
JSON_END

HIER IST DAS GUTACHTEN (nur ein Ausschnitt, aber benutze so viele Infos wie möglich daraus):

{GUTACHTEN_TEXT}
"""


# -------------------------
# Hilfsfunktionen
# -------------------------

def get_gemini_client():
    """
    Holt den Gemini-API-Key aus Umgebungsvariablen oder Streamlit-Secrets
    und baut einen Client. Wird NUR aufgerufen, wenn wirklich ein Request
    gesendet werden soll (kein Fehler beim Import).
    """
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


def pdf_text_auslesen(pfad):
    """Liest den Text aus einer PDF-Datei (alle Seiten)."""
    seiten_text = []
    with pdfplumber.open(pfad) as pdf:
        for seite in pdf.pages:
            seiten_text.append(seite.extract_text() or "")
    return "\n".join(seiten_text)


def prompt_bauen(gutachten_text):
    """Setzt den Gutachtentext in das Prompt-Template ein."""
    return PROMPT_TEMPLATE.replace("{GUTACHTEN_TEXT}", gutachten_text)


def ki_aufrufen(prompt_text: str) -> str:
    """
    Schickt den Prompt an die Google-Gemini-API (über das offizielle SDK) und gibt die Antwort zurück.
    """
    client = get_gemini_client()

    for versuch in range(1, KI_MAX_RETRIES + 1):
        print(
            f"[DEBUG] Sende Request an Gemini (SDK) – Versuch {versuch}/{KI_MAX_RETRIES}"
        )
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt_text,
                config={
                    "temperature": 0.0,
                },
            )

            text = response.text
            print("[DEBUG] KI-Antwort erfolgreich empfangen.")
            return text

        except genai_errors.ClientError as e:
            # Hier ist die eigentliche Fehlermeldung von Gemini
            msg = f"Gemini ClientError: {e}"
            print(msg)

            # Typische Fälle, bei denen Retry nichts bringt
            if versuch == KI_MAX_RETRIES:
                raise RuntimeError(msg) from e

            print("Warte 5 Sekunden und versuche es erneut...")
            time.sleep(5)

        except Exception as e:
            print("Allgemeiner Fehler beim Aufruf von Gemini (SDK):", e)
            if versuch == KI_MAX_RETRIES:
                raise
            print("Warte 5 Sekunden und versuche es erneut...")
            time.sleep(5)



def ki_antwort_speichern(basisname, ki_text):
    """Speichert die KI-Antwort als .txt-Datei in KI_ANTWORT_ORDNER."""
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)
    ziel_pfad = os.path.join(KI_ANTWORT_ORDNER, basisname + "_ki.txt")
    with open(ziel_pfad, "w", encoding="utf-8") as f:
        f.write(ki_text)
    print(f"KI-Antwort gespeichert: {ziel_pfad}")


def neueste_pdf_finden(ordner):
    """
    Sucht im Ordner nach allen .pdf-Dateien und gibt die neueste zurück.
    Gibt zusätzlich Debug-Ausgaben aus.
    """
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


# -------------------------
# MAIN
# -------------------------

def main():
    # Ordner sicherstellen
    os.makedirs(EINGANGS_ORDNER, exist_ok=True)
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)

    print("Base dir:", BASE_DIR)
    print("Suche neueste PDF in:", EINGANGS_ORDNER)

    neueste_pdf = neueste_pdf_finden(EINGANGS_ORDNER)

    if neueste_pdf is None:
        print("Keine PDF-Datei im Ordner gefunden. Lege zuerst ein Gutachten (PDF) hinein.")
        return

    print(f"Neueste PDF gefunden: {neueste_pdf}")

    voller_text = pdf_text_auslesen(neueste_pdf)
    print("[DEBUG] Länge des vollen Gutachten-Textes:", len(voller_text), "Zeichen")

    gutachten_text = voller_text
    if len(gutachten_text) > MAX_TEXT_CHARS:
        print(f"[DEBUG] Kürze Text auf die ersten {MAX_TEXT_CHARS} Zeichen.")
        gutachten_text = gutachten_text[:MAX_TEXT_CHARS]

    prompt = prompt_bauen(gutachten_text)
    print("[DEBUG] Prompt-Länge:", len(prompt), "Zeichen")
    print("Sende Gutachten an Gemini...")

    ki_antwort = ki_aufrufen(prompt)

    basisname = os.path.splitext(os.path.basename(neueste_pdf))[0]
    ki_antwort_speichern(basisname, ki_antwort)

    print("Fertig. Diese eine PDF wurde verarbeitet.")


if __name__ == "__main__":
    main()
