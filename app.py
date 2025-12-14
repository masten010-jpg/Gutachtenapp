# app.py
import os
from datetime import datetime
import streamlit as st
from docxtpl import DocxTemplate

import programm_1_ki_input
import programm_2_word_output

# ==========================
# Basis-Setup / Pfade
# ==========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EINGANGS_ORDNER = os.path.join(BASE_DIR, "eingang_gutachten")
AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")
KI_ANTWORT_ORDNER = os.path.join(BASE_DIR, "ki_antworten")

os.makedirs(EINGANGS_ORDNER, exist_ok=True)
os.makedirs(AUSGANGS_ORDNER, exist_ok=True)
os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)

st.set_page_config(page_title="Kfz-Gutachten → Anwaltsschreiben", layout="centered")

# ==========================
# Benutzerkonten
# ==========================
USER_CREDENTIALS = {
    "admin": "passwort123",
    "husseon": "geheim",
    "anwalt": "anwaltpass"
}

VORLAGEN = {
    "Wertminderung": "vorlage_schreibenwertmind.docx",
    "Totalschaden": "vorlage_schreibentotalschaden.docx"
}

# ==========================
# Passwortschutz
# ==========================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = None

if not st.session_state["logged_in"]:
    st.title("Zugang geschützt")
    username = st.text_input("Benutzername")
    pw = st.text_input("Passwort", type="password")
    login_clicked = st.button("Login")

    if login_clicked:
        if USER_CREDENTIALS.get(username) == pw:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.rerun()
        else:
            st.error("Benutzername oder Passwort falsch")
    else:
        st.stop()

# ==========================
# App-Inhalt (nach Login)
# ==========================
st.title(f"Kfz-Gutachten Automatisierung - Eingeloggt als {st.session_state['username']}")

# Logout
if st.button("Logout"):
    st.session_state["logged_in"] = False
    st.session_state["username"] = None
    st.rerun()

# ==========================
# Vorlage auswählen
# ==========================
st.header("1. Schreiben Vorlage wählen")
auswahl = st.selectbox("Welche Vorlage möchten Sie verwenden?", list(VORLAGEN.keys()))
vorlage_pfad = os.path.join(BASE_DIR, VORLAGEN[auswahl])

# ==========================
# Hilfsfunktionen
# ==========================
def cleanup_files(*paths: str):
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                print(f"Gelöscht: {path}")
            except OSError as e:
                print(f"Fehler beim Löschen von {path}: {e}")

def extrahiere_platzhalter(vorlage_pfad):
    """Platzhalter aus der Word-Vorlage extrahieren."""
    doc = DocxTemplate(vorlage_pfad)
    return doc.get_undeclared_template_variables()

# ==========================
# PDF Upload & Verarbeitung
# ==========================
st.header("2. Gutachten hochladen, verarbeiten und Schreiben herunterladen")
uploaded_file = st.file_uploader("Gutachten als PDF hochladen", type=["pdf"])

if st.button("Gutachten verarbeiten"):
    if uploaded_file is None:
        st.error("Bitte zuerst eine PDF-Datei hochladen.")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"gutachten_{timestamp}.pdf"
        pdf_path = os.path.join(EINGANGS_ORDNER, safe_name)

        try:
            with open(pdf_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
        except Exception as e:
            st.error(f"Fehler beim Speichern der PDF-Datei: {e}")
            st.stop()

        st.info(f"PDF gespeichert als: {safe_name}")

        try:
            with st.spinner("Verarbeite Gutachten mit KI..."):
                # 1) KI-Programm
                pfad_ki = programm_1_ki_input.main(pdf_path)

                if pfad_ki is None or not os.path.isfile(pfad_ki):
                    raise RuntimeError("Programm 1 hat keine gültige KI-Antwort erzeugt.")

                # 2) Platzhalter aus Vorlage extrahieren
                platzhalter = extrahiere_platzhalter(vorlage_pfad)

                # 3) Word-Dokument erzeugen
                # Hier nutzen wir programm_2_word_output.main, das jetzt flexibel alle Variablen aus der KI einfügt
                docx_pfad = programm_2_word_output.main(pfad_ki)

                if docx_pfad is None or not os.path.isfile(docx_pfad):
                    raise RuntimeError("Programm 2 hat kein Schreiben erzeugt.")

            # Word-Datei in Speicher laden, bevor wir sie löschen
            with open(docx_pfad, "rb") as f:
                docx_bytes = f.read()

            # Dateien vom Server löschen (PDF, KI-Text, DOCX)
            cleanup_files(pdf_path, pfad_ki, docx_pfad)

            st.success("Verarbeitung abgeschlossen.")
            st.success("Alle Daten wurden gelöscht!")

            # Download-Button mit in-memory Bytes
            st.download_button(
                label="Erstelltes Anwaltsschreiben herunterladen",
                data=docx_bytes,
                file_name=os.path.basename(docx_pfad),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        except Exception as e:
            st.error(f"Fehler bei der Verarbeitung: {e}")

# ==========================
# Debug-Infos
# ==========================
with st.expander("Debug: Dateien im System anzeigen"):
    st.subheader("Eingang Gutachten")
    st.write(os.listdir(EINGANGS_ORDNER))
    st.subheader("KI-Antworten")
    st.write(os.listdir(KI_ANTWORT_ORDNER))
    st.subheader("Ausgang-Schreiben")
    st.write(os.listdir(AUSGANGS_ORDNER))
