# app.py
import os
import json
import time
from datetime import datetime
import streamlit as st
from docxtpl import DocxTemplate
import bcrypt

import config
import programm_1_ki_input
import programm_2_word_output

# ==========================
# Basis-Setup / Pfade
# ==========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EINGANGS_ORDNER = config.EINGANGS_ORDNER
KI_ANTWORT_ORDNER = config.KI_ANTWORT_ORDNER
AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # bleibt wie bei dir

os.makedirs(EINGANGS_ORDNER, exist_ok=True)
os.makedirs(AUSGANGS_ORDNER, exist_ok=True)
os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)

st.set_page_config(page_title="Kfz-Gutachten → Anwaltsschreiben", layout="centered")

# ==========================
# Benutzer "Datenbank" (persistenter Hash-Speicher)
# ==========================
USERS_FILE = os.path.join(BASE_DIR, "users.json")  # enthält nur Hashes, keine Klartext-PWs

def _atomic_write_json(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def load_users() -> dict:
    if not os.path.isfile(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # erwartet: {"username": "bcrypt_hash", ...}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}

def save_users(users: dict):
    _atomic_write_json(USERS_FILE, users)

def hash_password(plain_password: str) -> str:
    pw_bytes = plain_password.encode("utf-8")
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")

def check_password(plain_password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            stored_hash.encode("utf-8")
        )
    except Exception:
        return False

def valid_username(name: str) -> bool:
    # simpel & robust: nur Buchstaben/Zahlen/_/-
    if not name or len(name) < 3 or len(name) > 32:
        return False
    for ch in name:
        if not (ch.isalnum() or ch in ["_", "-"]):
            return False
    return True

def valid_password(pw: str) -> bool:
    # MVP-Regeln (kannst du später verschärfen)
    return isinstance(pw, str) and len(pw) >= 10

# ==========================
# Vorlagen
# ==========================
VORLAGEN = {
    "Standard": "vorlage_schreiben.docx",
    "Wertminderung": "vorlage_schreibenwertmind.docx",
    "Totalschaden": "vorlage_schreibentotalschaden.docx"
}

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
    doc = DocxTemplate(vorlage_pfad)
    return doc.get_undeclared_template_variables()

def resolve_vorlage_pfad(auswahl: str) -> str:
    if auswahl not in VORLAGEN:
        raise ValueError(f"Unbekannte Auswahl: {auswahl}")

    dateiname = VORLAGEN[auswahl]

    # 1) Wenn Standard: bevorzugt config.DEFAULT_VORLAGE
    if auswahl == "Standard":
        if getattr(config, "DEFAULT_VORLAGE", None) and os.path.isfile(config.DEFAULT_VORLAGE):
            return config.DEFAULT_VORLAGE

    # 2) Vorlagenordner
    if getattr(config, "VORLAGEN_ORDNER", None):
        pfad1 = os.path.join(config.VORLAGEN_ORDNER, dateiname)
        if os.path.isfile(pfad1):
            return pfad1

    # 3) BASE_DIR fallback
    pfad2 = os.path.join(BASE_DIR, dateiname)
    if os.path.isfile(pfad2):
        return pfad2

    # 4) falls absolute Pfade in VORLAGEN stehen
    if os.path.isabs(dateiname) and os.path.isfile(dateiname):
        return dateiname

    raise FileNotFoundError(f"Vorlage nicht gefunden: {dateiname}")

# ==========================
# Passwortschutz / Session
# ==========================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = None

# simple Brute-Force Bremse (pro Session)
if "login_fail_count" not in st.session_state:
    st.session_state["login_fail_count"] = 0
if "login_block_until" not in st.session_state:
    st.session_state["login_block_until"] = 0.0

def is_blocked_now() -> bool:
    return time.time() < float(st.session_state.get("login_block_until", 0.0))

def register_user(username: str, pw: str) -> tuple[bool, str]:
    users = load_users()

    if not valid_username(username):
        return False, "Benutzername ungültig (3–32 Zeichen, nur a-z A-Z 0-9 _ -)."

    if username in users:
        return False, "Benutzername existiert bereits."

    if not valid_password(pw):
        return False, "Passwort zu kurz (mindestens 10 Zeichen)."

    users[username] = hash_password(pw)
    save_users(users)
    return True, "Registrierung erfolgreich. Du kannst dich jetzt einloggen."

def login_user(username: str, pw: str) -> tuple[bool, str]:
    if is_blocked_now():
        sek = int(st.session_state["login_block_until"] - time.time())
        return False, f"Zu viele Fehlversuche. Bitte {sek}s warten."

    users = load_users()
    stored_hash = users.get(username)

    # Immer gleiche Fehlermeldung, um User-Enum zu vermeiden
    if not stored_hash or not check_password(pw, stored_hash):
        st.session_state["login_fail_count"] += 1
        # nach 5 Fehlversuchen: 30 Sekunden blocken
        if st.session_state["login_fail_count"] >= 5:
            st.session_state["login_block_until"] = time.time() + 30
            st.session_state["login_fail_count"] = 0
        return False, "Benutzername oder Passwort falsch."

    st.session_state["login_fail_count"] = 0
    st.session_state["login_block_until"] = 0.0
    st.session_state["logged_in"] = True
    st.session_state["username"] = username
    return True, "Login erfolgreich."

# ==========================
# Login / Registrierung UI
# ==========================
if not st.session_state["logged_in"]:
    st.title("Zugang geschützt")

    users = load_users()
    allow_registration = True

    # Optional: Registrierung nur erlauben, wenn noch keine Nutzer existieren (wirklich "einmalig" global)
    # -> Falls du stattdessen "pro User einmalig" meinst: setze die nächste Zeile auf False
    EINMALIGE_REGISTRIERUNG_GLOBAL = False
    if EINMALIGE_REGISTRIERUNG_GLOBAL and len(users) > 0:
        allow_registration = False

    mode = st.radio(
        "Aktion",
        options=["Login", "Registrieren"] if allow_registration else ["Login"],
        horizontal=True
    )

    username = st.text_input("Benutzername")
    pw = st.text_input("Passwort", type="password")

    if mode == "Registrieren":
        pw2 = st.text_input("Passwort wiederholen", type="password")
        register_clicked = st.button("Registrieren")

        if register_clicked:
            if pw != pw2:
                st.error("Passwörter stimmen nicht überein.")
                st.stop()

            ok, msg = register_user(username.strip(), pw)
            if ok:
                st.success(msg)
            else:
                st.error(msg)
        st.stop()

    # Login
    login_clicked = st.button("Login")
    if login_clicked:
        ok, msg = login_user(username.strip(), pw)
        if ok:
            st.rerun()
        else:
            st.error(msg)
            st.stop()
    else:
        st.stop()

# ==========================
# App-Inhalt (nach Login)
# ==========================
st.title(f"Kfz-Gutachten Automatisierung - Eingeloggt als {st.session_state['username']}")

if st.button("Logout"):
    st.session_state["logged_in"] = False
    st.session_state["username"] = None
    st.rerun()

# ==========================
# Vorlage auswählen
# ==========================
st.header("1. Schreiben Vorlage wählen")
auswahl = st.selectbox("Welche Vorlage möchten Sie verwenden?", list(VORLAGEN.keys()))
try:
    vorlage_pfad = resolve_vorlage_pfad(auswahl)
except Exception as e:
    st.error(f"Vorlagenfehler: {e}")
    st.stop()

# ==========================
# PDF Upload & Verarbeitung
# ==========================
st.header("2. Gutachten hochladen, verarbeiten und Schreiben herunterladen")
uploaded_file = st.file_uploader("Gutachten als PDF hochladen", type=["pdf"])

if st.button("Gutachten verarbeiten"):
    if uploaded_file is None:
        st.error("Bitte zuerst eine PDF-Datei hochladen.")
        st.stop()

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
            # 1) KI-Programm (mit auswahl -> prompt passend zur Vorlage)
            pfad_ki = programm_1_ki_input.main(pdf_path, auswahl)

            if pfad_ki is None or not os.path.isfile(pfad_ki):
                raise RuntimeError("Programm 1 hat keine gültige KI-Antwort erzeugt.")

            # 2) Word-Dokument erzeugen
            docx_pfad = programm_2_word_output.main(pfad_ki, vorlage_pfad)

            if docx_pfad is None or not os.path.isfile(docx_pfad):
                raise RuntimeError("Programm 2 hat kein Schreiben erzeugt.")

        with open(docx_pfad, "rb") as f:
            docx_bytes = f.read()

        # Dateien löschen (PDF, KI-Text, DOCX)
        cleanup_files(pdf_path, pfad_ki, docx_pfad)

        st.success("Verarbeitung abgeschlossen.")
        st.success("Die Dateien wurden nach der Verarbeitung vom Server gelöscht.")

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
    st.subheader("Debug: gewählte Vorlage")
    st.write(os.path.basename(vorlage_pfad) if vorlage_pfad else None)
    st.subheader("Debug: registrierte User (nur Usernames)")
    st.write(sorted(list(load_users().keys())))
