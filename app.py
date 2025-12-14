import os
import json
from datetime import datetime
import streamlit as st
from werkzeug.security import check_password_hash

import programm_1_ki_input
import programm_2_word_output

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EINGANG = os.path.join(BASE_DIR, "eingang_gutachten")
KI_ORDNER = os.path.join(BASE_DIR, "ki_antworten")
AUSGANG = os.path.join(BASE_DIR, "ausgang_schreiben")
VORLAGEN = os.path.join(BASE_DIR, "vorlagen")
USERS = os.path.join(BASE_DIR, "users", "users.json")

for p in [EINGANG, KI_ORDNER, AUSGANG]:
    os.makedirs(p, exist_ok=True)

st.set_page_config("Gutachten → Anwaltsschreiben", layout="centered")

# ---------------- LOGIN ----------------

def lade_users():
    with open(USERS, "r", encoding="utf-8") as f:
        return json.load(f)

if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("Login")

    username = st.text_input("Benutzername")
    password = st.text_input("Passwort", type="password")

    if st.button("Login"):
        users = lade_users()
        if username in users and check_password_hash(
            users[username]["password_hash"], password
        ):
            st.session_state.user = username
            st.rerun()
        else:
            st.error("Login fehlgeschlagen")

    st.stop()

# ---------------- APP ----------------

st.title("Kfz-Gutachten Automatisierung")
st.success(f"Eingeloggt als {st.session_state.user}")

vorlagen = {
    "Reparaturschaden": "reparaturschaden.docx",
    "Totalschaden": "totalschaden.docx"
}

auswahl = st.selectbox("Vorlage auswählen", list(vorlagen.keys()))
vorlage_pfad = os.path.join(VORLAGEN, vorlagen[auswahl])

uploaded = st.file_uploader("Gutachten (PDF)", type=["pdf"])

if st.button("Verarbeiten"):
    if not uploaded:
        st.error("Bitte PDF hochladen.")
        st.stop()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_pfad = os.path.join(EINGANG, f"gutachten_{ts}.pdf")

    with open(pdf_pfad, "wb") as f:
        f.write(uploaded.getbuffer())

    with st.spinner("KI analysiert Gutachten..."):
        ki_pfad = programm_1_ki_input.main(pdf_pfad)

        docx_pfad = programm_2_word_output.main(
            pfad_ki_txt=ki_pfad,
            vorlage_pfad=vorlage_pfad
        )

    with open(docx_pfad, "rb") as f:
        daten = f.read()

    st.download_button(
        "Anwaltsschreiben herunterladen",
        daten,
        file_name=os.path.basename(docx_pfad),
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    for p in [pdf_pfad, ki_pfad, docx_pfad]:
        if os.path.exists(p):
            os.remove(p)

    st.success("Fertig. Alle Dateien gelöscht.")
