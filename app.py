# app.py
import os
from datetime import datetime

import streamlit as st

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
# Einfacher Passwortschutz
# ==========================

# HIER Passwort einstellen
x = "dein_sicheres_passwort"  # <- anpassen

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.title("Zugang geschützt")
    pw = st.text_input("Passwort eingeben", type="password")

    # Sofortiges Prüfen – kein Button nötig
    if pw == x:
        st.session_state["logged_in"] = True
    elif pw != "":
        st.error("Falsches Passwort.")

    st.stop()

# ==========================
# App-Inhalt (nur nach Login)
# ==========================

st.title("Kfz-Gutachten Automatisierung")
st.write(
    "PDF-Gutachten hochladen, von der KI auswerten lassen und fertiges "
    "Anwaltsschreiben als Word-Datei erhalten."
)

# Optional: Logout-Button
if st.button("Logout"):
    st.session_state["logged_in"] = False
    st.stop()


def cleanup_files(*paths: str):
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                print(f"Gelöscht: {path}")
            except OSError as e:
                print(f"Fehler beim Löschen von {path}: {e}")


# --------------------------------------------------
# 1) Upload + Verarbeiten + Download + Löschen
# --------------------------------------------------

st.header("1. Gutachten hochladen, verarbeiten und Schreiben herunterladen")

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
        else:
            st.info(f"PDF gespeichert als: {safe_name}")

            try:
                with st.spinner("Verarbeite Gutachten mit KI..."):
                    # Programm 1: genau DIESE PDF an Gemini → *_ki.txt
                    pfad_ki = programm_1_ki_input.main(pdf_path)

                    if pfad_ki is None or not os.path.isfile(pfad_ki):
                        raise RuntimeError(
                            "Programm 1 hat keine gültige KI-Antwort erzeugt."
                        )

                    # Programm 2: *_ki.txt → Word-Dokument
                    docx_pfad = programm_2_word_output.main(pfad_ki)

                    if docx_pfad is None or not os.path.isfile(docx_pfad):
                        raise RuntimeError(
                            "Programm 2 hat kein Schreiben erzeugt."
                        )

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
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                )

            except Exception as e:
                st.error(f"Fehler bei der Verarbeitung: {e}")


# --------------------------------------------------
# 2) Debug-Infos (optional)
# --------------------------------------------------

with st.expander("Debug: Dateien im System anzeigen"):
    st.subheader("Eingang Gutachten (eingang_gutachten)")
    if os.path.isdir(EINGANGS_ORDNER):
        st.write(os.listdir(EINGANGS_ORDNER))
    else:
        st.write("Ordner existiert nicht.")

    st.subheader("KI-Antworten (ki_antworten)")
    if os.path.isdir(KI_ANTWORT_ORDNER):
        st.write(os.listdir(KI_ANTWORT_ORDNER))
    else:
        st.write("Ordner existiert nicht.")

    st.subheader("Ausgang-Schreiben (ausgang_schreiben)")
    if os.path.isdir(AUSGANGS_ORDNER):
        st.write(os.listdir(AUSGANGS_ORDNER))
    else:
        st.write("Ordner existiert nicht.")
