import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EINGANGS_ORDNER = os.path.join(BASE_DIR, "eingang_gutachten")
KI_ANTWORT_ORDNER = os.path.join(BASE_DIR, "ki_antworten")
VORLAGEN_ORDNER = os.path.join(BASE_DIR, "vorlagen")

DEFAULT_VORLAGE = os.path.join(VORLAGEN_ORDNER, "vorlage_schreiben.docx")
