# app.py
import os
from datetime import datetime

import streamlit as st

import programm_1_ki_input
import programm_2_word_output

# Basisordner = dieser Dateiort
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EINGANGS_ORDNER = os.path.join(BASE_DIR, "eingang_gutachten")
AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")

os.makedirs(EINGANGS_ORDNER, exist_ok=True)
os.makedirs(AUSGANGS_ORDNER, exist_ok=True)

st.set_page_config(page_title="Kfz-Gutachten → Anwaltsschreiben", layout="centered")

st.title("Kfz-Gutachten Automatisierung")
st.write(
    "PDF-Gutachten hochladen, von der KI auswerten lassen und fertiges "
    "Anwaltsschreiben als Word-Datei erhalten."
)

# --------------------------------------------------
# 1) Upload + Verarbeiten
# --------------------------------------------------

st.header("1. Gutachten hochladen und verarbeiten")

uploaded_file = st.file_uploader("Gutachten als PDF hochladen", type=["pdf"])

if st.button("Gutachten verarbeiten"):
    if uploaded_file is None:
        st.error("Bitte zuerst eine PDF-Datei hochladen.")
    else:
        # PDF speichern
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

                st.success(
                    "Verarbeitung abgeschlossen. Das Schreiben kann jetzt "
                    "unter Punkt 2 heruntergeladen werden."
                )

            except Exception as e:
                st.error(f"Fehler bei der Verarbeitung: {e}")


# --------------------------------------------------
# 2) Download der neuesten Word-Datei
# --------------------------------------------------

st.header("2. Letztes Anwaltsschreiben herunterladen")

neueste_docx = None
if os.path.isdir(AUSGANGS_ORDNER):
    files = [
        os.path.join(AUSGANGS_ORDNER, d)
        for d in os.listdir(AUSGANGS_ORDNER)
        if d.lower().endswith(".docx")
    ]
    if files:
        neueste_docx = max(files, key=os.path.getmtime)

if neueste_docx:
    st.write(f"Aktuellste Datei: **{os.path.basename(neueste_docx)}**")
    with open(neueste_docx, "rb") as f:
        st.download_button(
            label="Neueste Word-Datei herunterladen",
            data=f,
            file_name=os.path.basename(neueste_docx),
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
else:
    st.info("Noch keine Word-Datei erzeugt. Bitte zuerst ein Gutachten verarbeiten.")


# --------------------------------------------------
# 3) Debug-Infos (optional)
# --------------------------------------------------

with st.expander("Debug: Dateien im System anzeigen"):
    ki_ordner = os.path.join(BASE_DIR, "ki_antworten")
    out_ordner = AUSGANGS_ORDNER
    in_ordner = EINGANGS_ORDNER

    st.subheader("Eingang Gutachten (eingang_gutachten)")
    if os.path.isdir(in_ordner):
        st.write(os.listdir(in_ordner))
    else:
        st.write("Ordner existiert nicht.")

    st.subheader("KI-Antworten (ki_antworten)")
    if os.path.isdir(ki_ordner):
        st.write(os.listdir(ki_ordner))
    else:
        st.write("Ordner existiert nicht.")

    st.subheader("Ausgang-Schreiben (ausgang_schreiben)")
    if os.path.isdir(out_ordner):
        st.write(os.listdir(out_ordner))
    else:
        st.write("Ordner existiert nicht.")
