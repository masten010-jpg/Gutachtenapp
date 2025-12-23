# app.py  # Kommentar: Haupt-Streamlit-App (Login + Upload + Verarbeitung + Download)

import os  # Kommentar: Pfade und Dateisystem
import json  # Kommentar: User-Daten (Hashes) als JSON speichern
import time  # Kommentar: Login-Rate-Limit / Blockzeit
import hmac  # Kommentar: Zeitkonstanter Hash-Vergleich
import hashlib  # Kommentar: Passwort-Hashing (PBKDF2)
import secrets  # Kommentar: Sichere Zufalls-Salts
from datetime import datetime  # Kommentar: Timestamp für Dateinamen
import streamlit as st  # Kommentar: UI
from docxtpl import DocxTemplate  # Kommentar: Word-Template Variablen lesen (Debug / optional)

import config  # Kommentar: Deine Pfad-Konfig
import programm_1_ki_input  # Kommentar: Programm 1 (PDF->KI->TXT)
import programm_2_word_output  # Kommentar: Programm 2 (KI-TXT->DOCX)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Kommentar: Basisverzeichnis des Projekts
EINGANGS_ORDNER = config.EINGANGS_ORDNER  # Kommentar: Ordner für hochgeladene PDFs
KI_ANTWORT_ORDNER = config.KI_ANTWORT_ORDNER  # Kommentar: Ordner für KI-Antworten
AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # Kommentar: Ordner für fertige DOCX

os.makedirs(EINGANGS_ORDNER, exist_ok=True)  # Kommentar: Ordner sicher anlegen
os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: Ordner sicher anlegen
os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: Ordner sicher anlegen

st.set_page_config(page_title="Kfz-Gutachten → Anwaltsschreiben", layout="centered")  # Kommentar: Streamlit Layout

USERS_FILE = os.path.join(BASE_DIR, "users.json")  # Kommentar: Persistenter User-Speicher (nur Hashes, keine Klartext-PWs)

def _atomic_write_json(path: str, data: dict) -> None:  # Kommentar: JSON atomar schreiben (keine kaputten Dateien)
    tmp = path + ".tmp"  # Kommentar: Temporärer Dateiname
    with open(tmp, "w", encoding="utf-8") as f:  # Kommentar: Temp-Datei öffnen
        json.dump(data, f, ensure_ascii=False, indent=2)  # Kommentar: JSON formatiert schreiben
    os.replace(tmp, path)  # Kommentar: Atomar ersetzen

def load_users() -> dict:  # Kommentar: Nutzer-Hashes laden
    if not os.path.isfile(USERS_FILE):  # Kommentar: Wenn Datei nicht existiert
        return {}  # Kommentar: Leeres Dict zurück
    try:  # Kommentar: Fehler robust abfangen
        with open(USERS_FILE, "r", encoding="utf-8") as f:  # Kommentar: Datei öffnen
            data = json.load(f)  # Kommentar: JSON laden
        if isinstance(data, dict):  # Kommentar: Typ prüfen
            return data  # Kommentar: Daten zurück
    except Exception:  # Kommentar: Bei Fehlern
        return {}  # Kommentar: Leeres Dict zurück
    return {}  # Kommentar: Fallback

def save_users(users: dict) -> None:  # Kommentar: Nutzer speichern
    _atomic_write_json(USERS_FILE, users)  # Kommentar: Atomar schreiben

def valid_username(name: str) -> bool:  # Kommentar: Username-Regeln
    if not name or len(name) < 3 or len(name) > 32:  # Kommentar: Länge prüfen
        return False  # Kommentar: Ungültig
    for ch in name:  # Kommentar: Zeichen prüfen
        if not (ch.isalnum() or ch in ["_", "-"]):  # Kommentar: Nur a-zA-Z0-9_- erlauben
            return False  # Kommentar: Ungültig
    return True  # Kommentar: Gültig

def valid_password(pw: str) -> bool:  # Kommentar: Passwort-Regeln (MVP)
    return isinstance(pw, str) and len(pw) >= 10  # Kommentar: Mindestens 10 Zeichen

def _pbkdf2_hash(password: str, salt_hex: str, iterations: int) -> str:  # Kommentar: PBKDF2-Hash berechnen
    salt = bytes.fromhex(salt_hex)  # Kommentar: Salt aus Hex zurück in Bytes
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)  # Kommentar: PBKDF2-HMAC-SHA256
    return dk.hex()  # Kommentar: Hash als Hex-String

def hash_password(plain_password: str) -> dict:  # Kommentar: Passwort sicher hashen (stdlib-only)
    salt = secrets.token_bytes(16)  # Kommentar: 16 Bytes Salt
    iterations = 200_000  # Kommentar: Iterationszahl (gut für 2025-MVP)
    salt_hex = salt.hex()  # Kommentar: Salt als Hex
    hash_hex = _pbkdf2_hash(plain_password, salt_hex, iterations)  # Kommentar: Hash berechnen
    return {"salt": salt_hex, "iterations": iterations, "hash": hash_hex}  # Kommentar: Speicherdaten zurückgeben

def check_password(plain_password: str, stored: dict) -> bool:  # Kommentar: Passwort prüfen
    try:  # Kommentar: Robustheit
        salt_hex = stored.get("salt", "")  # Kommentar: Salt holen
        iterations = int(stored.get("iterations", 0))  # Kommentar: Iterationen holen
        hash_hex = stored.get("hash", "")  # Kommentar: Hash holen
        if not salt_hex or not iterations or not hash_hex:  # Kommentar: Plausibilität
            return False  # Kommentar: Ungültige gespeicherte Daten
        calc = _pbkdf2_hash(plain_password, salt_hex, iterations)  # Kommentar: Hash neu berechnen
        return hmac.compare_digest(calc, hash_hex)  # Kommentar: Zeitkonstanter Vergleich
    except Exception:  # Kommentar: Bei Fehlern
        return False  # Kommentar: Login ablehnen

# ==========================
# Vorlagen (deine 6 Varianten)
# ==========================
VORLAGEN = {  # Kommentar: Dropdown-Name -> DOCX-Dateiname
    "Fiktive Abrechnung (Reparaturschaden)": "vorlage_fiktive_abrechnung.docx",  # Kommentar: Variante 1
    "Konkrete Abrechnung < WBW": "vorlage_konkret_unter_wbw.docx",  # Kommentar: Variante 2
    "130%-Regelung": "vorlage_130_prozent.docx",  # Kommentar: Variante 3
    "Totalschaden fiktiv": "vorlage_totalschaden_fiktiv.docx",  # Kommentar: Variante 4
    "Totalschaden konkret": "vorlage_totalschaden_konkret.docx",  # Kommentar: Variante 5
    "Totalschaden Ersatzbeschaffung": "vorlage_totalschaden_ersatzbeschaffung.docx",  # Kommentar: Variante 6
}  # Kommentar: Ende Vorlagen

def resolve_vorlage_pfad(auswahl: str) -> str:  # Kommentar: Vorlage-Pfad anhand Auswahl finden
    if auswahl not in VORLAGEN:  # Kommentar: Auswahl prüfen
        raise ValueError(f"Unbekannte Auswahl: {auswahl}")  # Kommentar: Fehler werfen
    dateiname = VORLAGEN[auswahl]  # Kommentar: Dateiname holen
    if getattr(config, "VORLAGEN_ORDNER", None):  # Kommentar: Wenn Vorlagenordner definiert
        pfad1 = os.path.join(config.VORLAGEN_ORDNER, dateiname)  # Kommentar: Pfad im Vorlagenordner
        if os.path.isfile(pfad1):  # Kommentar: Existenz prüfen
            return pfad1  # Kommentar: Gefunden
    pfad2 = os.path.join(BASE_DIR, dateiname)  # Kommentar: Fallback im BASE_DIR
    if os.path.isfile(pfad2):  # Kommentar: Existenz prüfen
        return pfad2  # Kommentar: Gefunden
    if os.path.isabs(dateiname) and os.path.isfile(dateiname):  # Kommentar: Falls absolute Pfade genutzt werden
        return dateiname  # Kommentar: Direkt zurück
    raise FileNotFoundError(f"Vorlage nicht gefunden: {dateiname}")  # Kommentar: Nichts gefunden

def cleanup_files(*paths: str) -> None:  # Kommentar: Dateien nach Verarbeitung löschen
    for path in paths:  # Kommentar: Pfade durchlaufen
        if path and os.path.exists(path):  # Kommentar: Wenn Datei existiert
            try:  # Kommentar: Fehler robust abfangen
                os.remove(path)  # Kommentar: Datei löschen
            except OSError:  # Kommentar: Falls Löschen fehlschlägt
                pass  # Kommentar: Ignorieren (MVP)

# ==========================
# Session / Login-State
# ==========================
if "logged_in" not in st.session_state:  # Kommentar: Session init
    st.session_state["logged_in"] = False  # Kommentar: Default
    st.session_state["username"] = None  # Kommentar: Default

if "login_fail_count" not in st.session_state:  # Kommentar: Fail Counter init
    st.session_state["login_fail_count"] = 0  # Kommentar: Default

if "login_block_until" not in st.session_state:  # Kommentar: Block Timer init
    st.session_state["login_block_until"] = 0.0  # Kommentar: Default

def is_blocked_now() -> bool:  # Kommentar: Prüfen, ob Login gerade gesperrt ist
    return time.time() < float(st.session_state.get("login_block_until", 0.0))  # Kommentar: Zeitvergleich

def register_user(username: str, pw: str) -> tuple[bool, str]:  # Kommentar: Neuen User anlegen
    users = load_users()  # Kommentar: Users laden
    if not valid_username(username):  # Kommentar: Username prüfen
        return False, "Benutzername ungültig (3–32 Zeichen, nur a-z A-Z 0-9 _ -)."  # Kommentar: Fehlertext
    if username in users:  # Kommentar: Existiert schon?
        return False, "Benutzername existiert bereits."  # Kommentar: Fehlertext
    if not valid_password(pw):  # Kommentar: Passwort prüfen
        return False, "Passwort zu kurz (mindestens 10 Zeichen)."  # Kommentar: Fehlertext
    users[username] = hash_password(pw)  # Kommentar: Hash erzeugen und speichern
    save_users(users)  # Kommentar: Persistieren
    return True, "Registrierung erfolgreich. Du kannst dich jetzt einloggen."  # Kommentar: OK

def login_user(username: str, pw: str) -> tuple[bool, str]:  # Kommentar: Login prüfen
    if is_blocked_now():  # Kommentar: Block aktiv?
        sek = int(st.session_state["login_block_until"] - time.time())  # Kommentar: Restzeit
        return False, f"Zu viele Fehlversuche. Bitte {sek}s warten."  # Kommentar: Hinweis
    users = load_users()  # Kommentar: Users laden
    stored = users.get(username)  # Kommentar: User-Record holen
    if not stored or not check_password(pw, stored):  # Kommentar: User fehlt oder Passwort falsch
        st.session_state["login_fail_count"] += 1  # Kommentar: Fail Counter erhöhen
        if st.session_state["login_fail_count"] >= 5:  # Kommentar: Schwelle erreicht
            st.session_state["login_block_until"] = time.time() + 30  # Kommentar: 30s blocken
            st.session_state["login_fail_count"] = 0  # Kommentar: Zähler resetten
        return False, "Benutzername oder Passwort falsch."  # Kommentar: Standardtext (keine User-Enumeration)
    st.session_state["login_fail_count"] = 0  # Kommentar: Reset bei Erfolg
    st.session_state["login_block_until"] = 0.0  # Kommentar: Reset bei Erfolg
    st.session_state["logged_in"] = True  # Kommentar: Login setzen
    st.session_state["username"] = username  # Kommentar: Username setzen
    return True, "Login erfolgreich."  # Kommentar: OK

# ==========================
# Login / Registrierung UI
# ==========================
if not st.session_state["logged_in"]:  # Kommentar: Wenn nicht eingeloggt
    st.title("Zugang geschützt")  # Kommentar: Titel
    users = load_users()  # Kommentar: Users laden (z.B. um Registrierung ggf. zu sperren)
    allow_registration = True  # Kommentar: Default
    EINMALIGE_REGISTRIERUNG_GLOBAL = False  # Kommentar: Optional: auf True stellen, wenn nur 1 Registrierung insgesamt erlaubt ist
    if EINMALIGE_REGISTRIERUNG_GLOBAL and len(users) > 0:  # Kommentar: Wenn global nur einmal und schon existiert
        allow_registration = False  # Kommentar: Registrierung sperren

    mode = st.radio(  # Kommentar: Moduswahl
        "Aktion",  # Kommentar: Label
        options=["Login", "Registrieren"] if allow_registration else ["Login"],  # Kommentar: Optionen
        horizontal=True  # Kommentar: Layout
    )  # Kommentar: Ende Radio

    username = st.text_input("Benutzername")  # Kommentar: Username Input
    pw = st.text_input("Passwort", type="password")  # Kommentar: Passwort Input

    if mode == "Registrieren":  # Kommentar: Registrieren-Flow
        pw2 = st.text_input("Passwort wiederholen", type="password")  # Kommentar: Passwort 2
        if st.button("Registrieren"):  # Kommentar: Button
            if pw != pw2:  # Kommentar: Match prüfen
                st.error("Passwörter stimmen nicht überein.")  # Kommentar: Fehler
                st.stop()  # Kommentar: Stop
            ok, msg = register_user(username.strip(), pw)  # Kommentar: Registrieren
            if ok:  # Kommentar: Erfolg
                st.success(msg)  # Kommentar: Nachricht
            else:  # Kommentar: Fehler
                st.error(msg)  # Kommentar: Nachricht
        st.stop()  # Kommentar: Stop nach Register-UI

    if st.button("Login"):  # Kommentar: Login-Button
        ok, msg = login_user(username.strip(), pw)  # Kommentar: Login prüfen
        if ok:  # Kommentar: Erfolg
            st.rerun()  # Kommentar: App neu laden
        st.error(msg)  # Kommentar: Fehler anzeigen
        st.stop()  # Kommentar: Stop bei Fehler
    st.stop()  # Kommentar: Stop, wenn noch kein Login

# ==========================
# App-Inhalt (nach Login)
# ==========================
st.title(f"Kfz-Gutachten Automatisierung - Eingeloggt als {st.session_state['username']}")  # Kommentar: Titel mit Username

if st.button("Logout"):  # Kommentar: Logout Button
    st.session_state["logged_in"] = False  # Kommentar: Login-State reset
    st.session_state["username"] = None  # Kommentar: Username reset
    st.rerun()  # Kommentar: Reload

st.header("1. Abrechnungsvariante / Vorlage wählen")  # Kommentar: Abschnitt
auswahl = st.selectbox("Welche Variante möchten Sie verwenden?", list(VORLAGEN.keys()))  # Kommentar: Dropdown Auswahl
vorlage_pfad = resolve_vorlage_pfad(auswahl)  # Kommentar: DOCX Pfad finden
st.caption(f"Verwendete Vorlage-Datei: {os.path.basename(vorlage_pfad)}")  # Kommentar: Info

st.header("2. Steuerstatus des Geschädigten")  # Kommentar: Abschnitt
steuerstatus = st.selectbox(  # Kommentar: Dropdown Steuerstatus
    "Steuerstatus",  # Kommentar: Label
    ["nicht vorsteuerabzugsberechtigt", "vorsteuerabzugsberechtigt"],  # Kommentar: Optionen
    index=0  # Kommentar: Default
)  # Kommentar: Ende Dropdown

st.header("3. Optional: Zusatzkosten")  # Kommentar: Abschnitt
zusatzkosten_bezeichnung = st.text_input("Bezeichnung (optional)", value="")  # Kommentar: Optionaler Text
zusatzkosten_betrag = st.text_input("Betrag in Euro (optional, z.B. 25,00)", value="")  # Kommentar: Optionaler Betrag

st.header("4. Gutachten hochladen, verarbeiten und Schreiben herunterladen")  # Kommentar: Abschnitt
uploaded_file = st.file_uploader("Gutachten als PDF hochladen", type=["pdf"])  # Kommentar: Upload

if st.button("Gutachten verarbeiten"):  # Kommentar: Start Verarbeitung
    if uploaded_file is None:  # Kommentar: Prüfen Upload
        st.error("Bitte zuerst eine PDF-Datei hochladen.")  # Kommentar: Fehler
        st.stop()  # Kommentar: Stop

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Kommentar: Timestamp
    safe_name = f"gutachten_{timestamp}.pdf"  # Kommentar: Sicherer Dateiname
    pdf_path = os.path.join(EINGANGS_ORDNER, safe_name)  # Kommentar: Zielpfad

    with open(pdf_path, "wb") as f:  # Kommentar: PDF speichern
        f.write(uploaded_file.getbuffer())  # Kommentar: Bytes schreiben

    try:  # Kommentar: Verarbeitung try
        with st.spinner("Verarbeite Gutachten mit KI..."):  # Kommentar: Spinner
            pfad_ki = programm_1_ki_input.main(pdf_path, auswahl, steuerstatus)  # Kommentar: Programm 1 aufrufen

            docx_pfad = programm_2_word_output.main(  # Kommentar: Programm 2 aufrufen
                pfad_ki_txt=pfad_ki,  # Kommentar: Pfad zur KI-TXT
                vorlage_pfad=vorlage_pfad,  # Kommentar: Pfad zur Word-Vorlage
                auswahl=auswahl,  # Kommentar: Variante
                steuerstatus=steuerstatus,  # Kommentar: Steuerstatus
                zus_bez=zusatzkosten_bezeichnung,  # Kommentar: Zusatzkosten-Bezeichnung
                zus_betrag=zusatzkosten_betrag,  # Kommentar: Zusatzkosten-Betrag
            )  # Kommentar: Ende Programm 2

        with open(docx_pfad, "rb") as f:  # Kommentar: DOCX in Memory laden
            docx_bytes = f.read()  # Kommentar: Bytes lesen

        cleanup_files(pdf_path, pfad_ki, docx_pfad)  # Kommentar: Dateien löschen

        st.success("Verarbeitung abgeschlossen. Dateien wurden gelöscht.")  # Kommentar: Erfolg
        st.download_button(  # Kommentar: Download-Button
            label="Erstelltes Anwaltsschreiben herunterladen",  # Kommentar: Label
            data=docx_bytes,  # Kommentar: Daten
            file_name=os.path.basename(docx_pfad),  # Kommentar: Dateiname
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # Kommentar: MIME
        )  # Kommentar: Ende Button

    except Exception as e:  # Kommentar: Fehlerfall
        st.error(f"Fehler bei der Verarbeitung: {e}")  # Kommentar: Fehler anzeigen

with st.expander("Debug"):  # Kommentar: Debug Bereich
    st.write({  # Kommentar: Debug Daten
        "auswahl": auswahl,  # Kommentar: Auswahl
        "steuerstatus": steuerstatus,  # Kommentar: Steuerstatus
        "eingang": os.listdir(EINGANGS_ORDNER),  # Kommentar: Dateien Eingang
        "ki": os.listdir(KI_ANTWORT_ORDNER),  # Kommentar: Dateien KI
        "ausgang": os.listdir(AUSGANGS_ORDNER),  # Kommentar: Dateien Ausgang
    })  # Kommentar: Ende Debug
