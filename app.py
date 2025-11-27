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
    "PDF-Gutachten hochladen, von der KI auswerten lassen und fertiges Anwaltsschreiben "
    "als Word-Datei erhalten."
)


# 1) Upload + Verarbeiten
st.header("1. Gutachten hochladen und verarbeiten")

uploaded_file = st.file_uploader("Gutachten als PDF hochladen", type=["pdf"])

if st.button("Gutachten verarbeiten (Programm 1 + Programm 2)"):
    if uploaded_file is None:
        st.error("Bitte zuerst eine PDF-Datei hochladen.")
    else:
        # PDF speichern
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"gutachten_{timestamp}.pdf"
        pdf_path = os.path.join(EINGANGS_ORDNER, safe_name)

        with open(pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.info(f"PDF gespeichert als: {safe_name}")

        try:
            with st.spinner("Verarbeite Gutachten mit KI..."):
                # Programm 1: PDF → KI → *_ki.txt, gibt Pfad zurück
                pfad_ki = programm_1_ki_input.main()

                if pfad_ki is None:
                    st.error(
                        "Programm 1 hat keine KI-Antwort erzeugt. "
                        "Bitte Log-Ausgabe prüfen."
                    )
                else:
                    # Programm 2: *_ki.txt → Word-Dokument
                    programm_2_word_output.main(pfad_ki)
        except RuntimeError as e:
            st.error(f"Fehler bei der KI-Verarbeitung: {e}")
        except Exception as e:
            st.error(f"Unerwarteter Fehler: {e}")
        else:
            st.success(
                "Verarbeitung abgeschlossen. Das Schreiben kann jetzt heruntergeladen werden."
            )


# 2) Download der neuesten Word-Datei
st.header("2. Letztes Anwaltsschreiben herunterladen")


def finde_neueste_docx(ordner: str):
    if not os.path.isdir(ordner):
        return None
    dateien = [
        os.path.join(ordner, d)
        for d in os.listdir(ordner)
        if d.lower().endswith(".docx")
    ]
    if not dateien:
        return None
    return max(dateien, key=os.path.getmtime)


neueste_docx = finde_neueste_docx(AUSGANGS_ORDNER)

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
