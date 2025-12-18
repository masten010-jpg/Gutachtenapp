# programm_1_ki_input.py
import os
import time
import pdfplumber
from google import genai
from google.genai import errors as genai_errors

import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EINGANGS_ORDNER = config.EINGANGS_ORDNER
KI_ANTWORT_ORDNER = config.KI_ANTWORT_ORDNER

GEMINI_MODEL = "gemini-2.5-flash"

MAX_TEXT_CHARS = 100000
KI_MAX_RETRIES = 3
MIN_TEXT_CHARS = 6000

# ==========================
# Prompt-Zusätze je Variante
# ==========================
def prompt_zusatz(auswahl: str, steuerstatus: str) -> str:
    basis = f"""
KONTEXT:
- Gewählte Abrechnungsvariante: {auswahl}
- Steuerstatus des Geschädigten: {steuerstatus}
"""
    if auswahl == "Standard":
        return basis + """
REGELN:
- Klassischer Reparaturschaden, keine besondere 130%- oder Totalschadenlogik.
- Wenn nach Gutachten fiktiv abgerechnet wird (keine Reparaturrechnung): Reparaturkosten NETTO.
- Wenn eine konkrete Reparaturrechnung ersichtlich ist: Reparaturkosten BRUTTO und MwSt-Betrag, falls ausgewiesen.
- Merkantiler Minderwert (Wertminderung) ist steuerneutral und wird NETTO berücksichtigt.
"""
    if auswahl == "Wertminderung":
        return basis + """
REGELN:
- Fokus auf merkantiler Wertminderung.
- Extrahiere unbedingt den Betrag der Wertminderung (merkantiler Minderwert), falls genannt.
- Wertminderung ist steuerneutral und wird NETTO angegeben.
- Reparaturkosten, Kostenpauschale, Gutachterkosten, Nutzungsausfall, soweit vorhanden, ebenfalls extrahieren.
"""
    if auswahl == "Totalschaden":
        return basis + """
REGELN:
- TOTALSCHADEN: Reparaturkosten übersteigen grundsätzlich den Wiederbeschaffungswert (WBW).
- WICHTIG: Extrahiere WIEDERBESCHAFFUNGSWERT (WBW) und RESTWERT des Fahrzeugs.
- Berechnungsbasis ist der Wiederbeschaffungsaufwand = WBW - Restwert.
- Ob netto oder brutto abgerechnet wird, hängt vom Steuerstatus ab:
  * Vorsteuerabzugsberechtigt: Netto-Ausgleich
  * Nicht vorsteuerabzugsberechtigt: Bruttowerte, soweit im Gutachten erkennbar
- Extrahiere ggf. Hinweise auf MwSt im WBW oder in der Ersatzbeschaffung.
"""
    return basis

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
"""

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            api_key = None
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY ist nicht gesetzt.")
    return genai.Client(api_key=api_key)

def pdf_text_auslesen(pfad: str) -> str:
    seiten_text = []
    with pdfplumber.open(pfad) as pdf:
        for seite in pdf.pages:
            seiten_text.append(seite.extract_text() or "")
    return "\n".join(seiten_text)

def prompt_bauen(gutachten_text: str, auswahl: str, steuerstatus: str) -> str:
    zusatz = prompt_zusatz(auswahl, steuerstatus)
    prompt = PROMPT_TEMPLATE.replace("{GUTACHTEN_TEXT}", gutachten_text)
    prompt = prompt.replace("{ZUSATZ}", zusatz.strip())
    return prompt

def ki_aufrufen(prompt_text: str) -> str:
    client = get_gemini_client()
    for versuch in range(1, KI_MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt_text,
            )
            return response.text
        except genai_errors.ClientError as e:
            if versuch == KI_MAX_RETRIES:
                raise RuntimeError(f"Gemini ClientError: {e}") from e
            time.sleep(5)
        except Exception:
            if versuch == KI_MAX_RETRIES:
                raise
            time.sleep(5)

def ki_antwort_speichern(basisname: str, ki_text: str) -> str:
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)
    ziel_pfad = os.path.join(KI_ANTWORT_ORDNER, basisname + "_ki.txt")
    with open(ziel_pfad, "w", encoding="utf-8") as f:
        f.write(ki_text)
    return ziel_pfad

def neueste_pdf_finden(ordner: str) -> str | None:
    if not os.path.isdir(ordner):
        return None
    pdf_pfade = []
    for datei in os.listdir(ordner):
        datei_clean = datei.strip()
        if datei_clean.lower().endswith(".pdf"):
            pdf_pfade.append(os.path.join(ordner, datei_clean))
    if not pdf_pfade:
        return None
    return max(pdf_pfade, key=os.path.getmtime)

def main(
    pdf_pfad: str | None = None,
    auswahl: str = "Standard",
    steuerstatus: str = "nicht vorsteuerabzugsberechtigt"
) -> str | None:
    os.makedirs(EINGANGS_ORDNER, exist_ok=True)
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)

    if pdf_pfad is None:
        neueste_pdf = neueste_pdf_finden(EINGANGS_ORDNER)
        if neueste_pdf is None:
            raise RuntimeError("Kein Gutachten gefunden. Laden Sie ein Gutachten hoch!")
        zu_verarbeitende_pdf = neueste_pdf
    else:
        zu_verarbeitende_pdf = pdf_pfad

    voller_text = pdf_text_auslesen(zu_verarbeitende_pdf)

    if not voller_text or len(voller_text.strip()) < MIN_TEXT_CHARS:
        raise RuntimeError(
            "Das hochgeladene Dokument enthält zu wenig verwertbare Informationen. "
            "Laden Sie ein vollständiges Gutachten hoch!"
        )

    gutachten_text = voller_text[:MAX_TEXT_CHARS]
    prompt = prompt_bauen(gutachten_text, auswahl, steuerstatus)
    ki_antwort = ki_aufrufen(prompt)

    basisname = os.path.splitext(os.path.basename(zu_verarbeitende_pdf))[0]
    pfad_ki = ki_antwort_speichern(basisname, ki_antwort)
    return pfad_ki

if __name__ == "__main__":
    main()
