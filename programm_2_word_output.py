# programm_2_word_output.py
# Aufgabe:
# - Eine KI-Antwort-Textdatei mit JSON-Block verarbeiten
# - JSON-Daten nachbearbeiten
# - Word-Vorlage füllen
# - Pfad zur erzeugten .docx zurückgeben

import os
import json
from datetime import datetime
from docxtpl import DocxTemplate

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

KI_ANTWORT_ORDNER = os.path.join(BASE_DIR, "ki_antworten")
AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")
VORLAGE_PFAD = os.path.join(BASE_DIR, "vorlage_schreiben.docx")

JSON_START_MARKER = "JSON_START"
JSON_END_MARKER = "JSON_END"


def json_aus_ki_antwort_parsen(ki_text: str) -> dict:
    start_idx = ki_text.find(JSON_START_MARKER)
    end_idx = ki_text.find(JSON_END_MARKER)

    if start_idx == -1 or end_idx == -1:
        raise ValueError("JSON_START oder JSON_END nicht gefunden in KI-Antwort.")

    json_roh = ki_text[start_idx + len(JSON_START_MARKER) : end_idx].strip()
    json_roh = json_roh.strip("` \n")

    try:
        daten = json.loads(json_roh)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON konnte nicht geparst werden: {e}\nAuszug: {json_roh[:500]}") from e

    return daten


def euro_zu_float(text: str) -> float:
    if not text:
        return 0.0
    t = text.strip()
    t = t.replace("€", "").replace("EUR", "").strip()
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return 0.0


def float_zu_euro(betrag: float) -> str:
    s = f"{betrag:,.2f}"  # '6,580.00'
    s = s.replace(",", "X").replace(".", ",").
