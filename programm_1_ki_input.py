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

# Versuch: Env-Var, danach ggf. Streamlit-Secrets
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    try:
        import streamlit as st
        GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        GEMINI_API_KEY = None

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY ist nicht gesetzt. Bitte Env-Var oder Streamlit-Secrets verwenden.")

client = genai.Client(api_key=GEMINI_API_KEY)

GEMINI_MODEL = "gemini-1.5-flash-lite"

...
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY ist nicht gesetzt. Bitte Umgebungsvariable setzen.")

# Direkt Client mit API-Key bauen (oder du lässt api_key weg, wenn du nur über Env gehst)
client = genai.Client(api_key=GEMINI_API_KEY)


# Wie viele Zeichen aus dem Gutachten maximal an die KI gehen
MAX_TEXT_CHARS = 7000

# Mehrere Versuche bei Fehlern
KI_MAX_RETRIES = 3
KI_TIMEOUT_SEKUNDEN = 60  # wird im SDK intern gehandhabt, wir nutzen es nur für Retry-Delays


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
   SACHVERHALT: ... (In Sätzen kurze zusammenfassung Gesehen für Anwalt Email)
   14tage vom erstellg Datum: ... (14tage in zukunft laut datum der ki anfrage überprüfe kalender!)

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
  "14tage von erstellg Datum",

  "FAHRZEUGTYP": "",
  "KENNZEICHEN": "",
  "FAHRZEUG_KENNZEICHEN": "",
  "SACHVERHALT",
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


def ki_aufrufen(prompt_text):
    """
    Schickt den Prompt an die Google-Gemini-API (über das offizielle SDK) und gibt die Antwort zurück.
    - Mehrere Versuche bei Fehlern
    - Temperatur = 0 (keine Kreativität, nur nüchterne Antwort)
    """
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

            # Das SDK baut dir den Text schon zusammen
            text = response.text
            print("[DEBUG] KI-Antwort erfolgreich empfangen.")
            return text

        except Exception as e:
            print("FEHLER beim Aufruf von Gemini (SDK):", e)
            if versuch < KI_MAX_RETRIES:
                print("Warte 5 Sekunden und versuche es erneut...")
                time.sleep(5)
            else:
                raise


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


def main():
    os.makedirs(EINGANGS_ORDNER, exist_ok=True)
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)

    print("Base dir:", BASE_DIR)
    print("Suche neueste PDF in:", EINGANGS_ORDNER)

    neueste_pdf = neueste_pdf_finden(EINGANGS_ORDNER)

    if neueste_pdf is None:
        print("Keine PDF-Datei im Ordner gefunden. Lege zuerst ein Gutachten (PDF) hinein.")
        return

    print(f"Neueste PDF gefunden: {neueste_pdf}")

    # Vollständigen Text lesen
    voller_text = pdf_text_auslesen(neueste_pdf)
    print("[DEBUG] Länge des vollen Gutachten-Textes:", len(voller_text), "Zeichen")

    # Text begrenzen (nur Anfangsbereich, da dort Mandant/Unfalldaten typischerweise stehen)
    gutachten_text = voller_text
    if len(gutachten_text) > MAX_TEXT_CHARS:
        print(f"[DEBUG] Kürze Text auf die ersten {MAX_TEXT_CHARS} Zeichen.")
        gutachten_text = gutachten_text[:MAX_TEXT_CHARS]

    prompt = prompt_bauen(gutachten_text)
    print("[DEBUG] Prompt-Länge:", len(prompt), "Zeichen")
    print("Sende Gutachten an Gemini... nicht abbrechen, bis Antwort kommt.")

    ki_antwort = ki_aufrufen(prompt)

    basisname = os.path.splitext(os.path.basename(neueste_pdf))[0]
    ki_antwort_speichern(basisname, ki_antwort)

    print("Programm 1 fertig. Starte jetzt Programm 2 (Word-Ausgabe)...")

    # Programm 2 starten: verarbeitet alle *_ki.txt in ki_antworten
    programm_2_word_output.main()

    print("Alles erledigt: KI-Auswertung + Word-Schreiben erstellt.")
if __name__ == "__main__":
    main()
