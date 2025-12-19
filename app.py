# app.py  # Kommentar: Streamlit App mit Review-Schritt

import os  # Kommentar: Pfade/Dateisystem
import json  # Kommentar: JSON für User-Speicher
import time  # Kommentar: Rate-Limit/Block
from datetime import datetime  # Kommentar: Timestamp
import hashlib  # Kommentar: Built-in Hashing (statt bcrypt)
import secrets  # Kommentar: Salt-Erzeugung für Passwort-Hashing
import streamlit as st  # Kommentar: Streamlit UI
from docxtpl import DocxTemplate  # Kommentar: Word Platzhalter (Debug/Check)

import config  # Kommentar: Eigene Config
import programm_1_ki_input  # Kommentar: PDF->KI
import programm_2_word_output  # Kommentar: KI->Word

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Kommentar: Basisverzeichnis
EINGANGS_ORDNER = config.EINGANGS_ORDNER  # Kommentar: Eingang
KI_ANTWORT_ORDNER = config.KI_ANTWORT_ORDNER  # Kommentar: KI Antworten
AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # Kommentar: Output

os.makedirs(EINGANGS_ORDNER, exist_ok=True)  # Kommentar: Ordner anlegen
os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: Ordner anlegen
os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: Ordner anlegen

st.set_page_config(page_title="Kfz-Gutachten → Anwaltsschreiben", layout="centered")  # Kommentar: Page Setup

USERS_FILE = os.path.join(BASE_DIR, "users.json")  # Kommentar: User-Datenbank (Hash only)


def _atomic_write_json(path: str, data: dict) -> None:  # Kommentar: JSON atomar schreiben
    tmp = path + ".tmp"  # Kommentar: Temp-Datei
    with open(tmp, "w", encoding="utf-8") as f:  # Kommentar: Öffnen
        json.dump(data, f, ensure_ascii=False, indent=2)  # Kommentar: Schreiben
    os.replace(tmp, path)  # Kommentar: Atomar ersetzen


def load_users() -> dict:  # Kommentar: Users laden
    if not os.path.isfile(USERS_FILE):  # Kommentar: Existiert Datei?
        return {}  # Kommentar: Leer
    try:  # Kommentar: Try
        with open(USERS_FILE, "r", encoding="utf-8") as f:  # Kommentar: Öffnen
            data = json.load(f)  # Kommentar: Laden
        if isinstance(data, dict):  # Kommentar: Typ prüfen
            return data  # Kommentar: Return
    except Exception:  # Kommentar: Fehler abfangen
        return {}  # Kommentar: Fallback
    return {}  # Kommentar: Fallback


def save_users(users: dict) -> None:  # Kommentar: Users speichern
    _atomic_write_json(USERS_FILE, users)  # Kommentar: Atomar speichern


def hash_password(plain_password: str) -> str:  # Kommentar: Passwort sicher hashen (PBKDF2)
    salt = secrets.token_hex(16)  # Kommentar: 16-Byte Salt als Hex
    iterations = 200_000  # Kommentar: Iterationszahl
    dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), iterations)  # Kommentar: Ableitung
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"  # Kommentar: String-Format speichern


def check_password(plain_password: str, stored_hash: str) -> bool:  # Kommentar: Passwort gegen Hash prüfen
    try:  # Kommentar: Try
        parts = stored_hash.split("$")  # Kommentar: Split
        if len(parts) != 4:  # Kommentar: Format prüfen
            return False  # Kommentar: Ungültig
        algo, iter_s, salt, hexhash = parts  # Kommentar: Entpacken
        if algo != "pbkdf2_sha256":  # Kommentar: Algo prüfen
            return False  # Kommentar: Ungültig
        iterations = int(iter_s)  # Kommentar: Iterationen
        dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), iterations)  # Kommentar: Recompute
        return secrets.compare_digest(dk.hex(), hexhash)  # Kommentar: Konstantzeitvergleich
    except Exception:  # Kommentar: Fehler
        return False  # Kommentar: Fallback


def valid_username(name: str) -> bool:  # Kommentar: Username validieren
    if not name or len(name) < 3 or len(name) > 32:  # Kommentar: Länge
        return False  # Kommentar: Fail
    for ch in name:  # Kommentar: Iter
        if not (ch.isalnum() or ch in ["_", "-"]):  # Kommentar: Allowed
            return False  # Kommentar: Fail
    return True  # Kommentar: OK


def valid_password(pw: str) -> bool:  # Kommentar: Passwortregeln
    return isinstance(pw, str) and len(pw) >= 10  # Kommentar: Min 10


VORLAGEN = {  # Kommentar: Deine 6 Varianten
    "Fiktive Abrechnung (Reparaturschaden)": "vorlage_fiktive_abrechnung.docx",  # Kommentar: Datei
    "Konkrete Abrechnung < WBW": "vorlage_konkret_unter_wbw.docx",  # Kommentar: Datei
    "130%-Regelung": "vorlage_130_prozent.docx",  # Kommentar: Datei
    "Totalschaden fiktiv": "vorlage_totalschaden_fiktiv.docx",  # Kommentar: Datei
    "Totalschaden konkret": "vorlage_totalschaden_konkret.docx",  # Kommentar: Datei
    "Totalschaden Ersatzbeschaffung": "vorlage_totalschaden_ersatzbeschaffung.docx",  # Kommentar: Datei
}  # Kommentar: Ende


def resolve_vorlage_pfad(auswahl: str) -> str:  # Kommentar: Vorlage auflösen
    if auswahl not in VORLAGEN:  # Kommentar: Check
        raise ValueError(f"Unbekannte Auswahl: {auswahl}")  # Kommentar: Fehler
    dateiname = VORLAGEN[auswahl]  # Kommentar: Dateiname holen
    if getattr(config, "VORLAGEN_ORDNER", None):  # Kommentar: Ordner aus config?
        pfad1 = os.path.join(config.VORLAGEN_ORDNER, dateiname)  # Kommentar: Pfad bauen
        if os.path.isfile(pfad1):  # Kommentar: Existiert?
            return pfad1  # Kommentar: Return
    pfad2 = os.path.join(BASE_DIR, dateiname)  # Kommentar: Fallback im Base
    if os.path.isfile(pfad2):  # Kommentar: Existiert?
        return pfad2  # Kommentar: Return
    if os.path.isabs(dateiname) and os.path.isfile(dateiname):  # Kommentar: Absolut?
        return dateiname  # Kommentar: Return
    raise FileNotFoundError(f"Vorlage nicht gefunden: {dateiname}")  # Kommentar: Fehler


def cleanup_files(*paths: str) -> None:  # Kommentar: Dateien löschen
    for path in paths:  # Kommentar: Iter
        if path and os.path.exists(path):  # Kommentar: Existiert?
            try:  # Kommentar: Try
                os.remove(path)  # Kommentar: Löschen
            except OSError:  # Kommentar: Fehler
                pass  # Kommentar: Ignorieren (MVP)


def register_user(username: str, pw: str) -> tuple[bool, str]:  # Kommentar: Registrierung
    users = load_users()  # Kommentar: Laden
    if not valid_username(username):  # Kommentar: Prüfen
        return False, "Benutzername ungültig (3–32 Zeichen, nur a-z A-Z 0-9 _ -)."  # Kommentar: Msg
    if username in users:  # Kommentar: Exists?
        return False, "Benutzername existiert bereits."  # Kommentar: Msg
    if not valid_password(pw):  # Kommentar: Pw prüfen
        return False, "Passwort zu kurz (mindestens 10 Zeichen)."  # Kommentar: Msg
    users[username] = hash_password(pw)  # Kommentar: Hash speichern
    save_users(users)  # Kommentar: Speichern
    return True, "Registrierung erfolgreich. Du kannst dich jetzt einloggen."  # Kommentar: OK


def login_user(username: str, pw: str) -> tuple[bool, str]:  # Kommentar: Login
    users = load_users()  # Kommentar: Laden
    stored = users.get(username)  # Kommentar: Hash holen
    if not stored or not check_password(pw, stored):  # Kommentar: Prüfen
        return False, "Benutzername oder Passwort falsch."  # Kommentar: Msg
    return True, "Login erfolgreich."  # Kommentar: OK


if "logged_in" not in st.session_state:  # Kommentar: Session init
    st.session_state["logged_in"] = False  # Kommentar: Default
    st.session_state["username"] = None  # Kommentar: Default

if "analysis_done" not in st.session_state:  # Kommentar: Analyse-Status init
    st.session_state["analysis_done"] = False  # Kommentar: Default

if "analysis_data" not in st.session_state:  # Kommentar: Analyse-Daten init
    st.session_state["analysis_data"] = {}  # Kommentar: Default

if "analysis_paths" not in st.session_state:  # Kommentar: Pfade init
    st.session_state["analysis_paths"] = {"pdf": None, "ki": None, "docx": None}  # Kommentar: Default


if not st.session_state["logged_in"]:  # Kommentar: Login UI
    st.title("Zugang geschützt")  # Kommentar: Titel
    mode = st.radio("Aktion", options=["Login", "Registrieren"], horizontal=True)  # Kommentar: Mode
    username = st.text_input("Benutzername")  # Kommentar: Username input
    pw = st.text_input("Passwort", type="password")  # Kommentar: Pw input
    if mode == "Registrieren":  # Kommentar: Register mode
        pw2 = st.text_input("Passwort wiederholen", type="password")  # Kommentar: Pw2
        if st.button("Registrieren"):  # Kommentar: Button
            if pw != pw2:  # Kommentar: Match?
                st.error("Passwörter stimmen nicht überein.")  # Kommentar: Error
                st.stop()  # Kommentar: Stop
            ok, msg = register_user(username.strip(), pw)  # Kommentar: Register
            if ok:  # Kommentar: OK?
                st.success(msg)  # Kommentar: Show
            else:  # Kommentar: Fail
                st.error(msg)  # Kommentar: Show
        st.stop()  # Kommentar: Stop
    if st.button("Login"):  # Kommentar: Login button
        ok, msg = login_user(username.strip(), pw)  # Kommentar: Login
        if ok:  # Kommentar: OK?
            st.session_state["logged_in"] = True  # Kommentar: Set
            st.session_state["username"] = username.strip()  # Kommentar: Set
            st.rerun()  # Kommentar: Rerun
        else:  # Kommentar: Fail
            st.error(msg)  # Kommentar: Show
            st.stop()  # Kommentar: Stop
    st.stop()  # Kommentar: Stop if not logged in

st.title(f"Kfz-Gutachten Automatisierung - Eingeloggt als {st.session_state['username']}")  # Kommentar: Titel

if st.button("Logout"):  # Kommentar: Logout
    st.session_state["logged_in"] = False  # Kommentar: Set
    st.session_state["username"] = None  # Kommentar: Set
    st.session_state["analysis_done"] = False  # Kommentar: Reset
    st.session_state["analysis_data"] = {}  # Kommentar: Reset
    st.session_state["analysis_paths"] = {"pdf": None, "ki": None, "docx": None}  # Kommentar: Reset
    st.rerun()  # Kommentar: Rerun


st.header("1. Abrechnungsvariante / Vorlage wählen")  # Kommentar: Header
auswahl = st.selectbox("Welche Variante möchten Sie verwenden?", list(VORLAGEN.keys()))  # Kommentar: Select
vorlage_pfad = resolve_vorlage_pfad(auswahl)  # Kommentar: Pfad auflösen
st.caption(f"Verwendete Vorlage-Datei: {os.path.basename(vorlage_pfad)}")  # Kommentar: Info

st.header("2. Steuerstatus")  # Kommentar: Header
steuerstatus = st.selectbox("Steuerstatus des Geschädigten", ["nicht vorsteuerabzugsberechtigt", "vorsteuerabzugsberechtigt"], index=0)  # Kommentar: Select

st.header("3. Optional: Zusatzkosten")  # Kommentar: Header
zusatzkosten_bezeichnung = st.text_input("Bezeichnung (optional)", value="")  # Kommentar: Input
zusatzkosten_betrag = st.text_input("Betrag in Euro (optional, z.B. 25,00)", value="")  # Kommentar: Input

st.header("4. Gutachten hochladen")  # Kommentar: Header
uploaded_file = st.file_uploader("Gutachten als PDF hochladen", type=["pdf"])  # Kommentar: Upload


col1, col2 = st.columns(2)  # Kommentar: 2 Spalten für Buttons

with col1:  # Kommentar: Linke Spalte
    if st.button("1) KI analysieren"):  # Kommentar: Analyse-Button
        if uploaded_file is None:  # Kommentar: Datei vorhanden?
            st.error("Bitte zuerst eine PDF-Datei hochladen.")  # Kommentar: Error
            st.stop()  # Kommentar: Stop
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Kommentar: Timestamp
        safe_name = f"gutachten_{timestamp}.pdf"  # Kommentar: Dateiname
        pdf_path = os.path.join(EINGANGS_ORDNER, safe_name)  # Kommentar: Pfad
        with open(pdf_path, "wb") as f:  # Kommentar: Speichern
            f.write(uploaded_file.getbuffer())  # Kommentar: Bytes schreiben
        st.info(f"PDF gespeichert als: {safe_name}")  # Kommentar: Info
        with st.spinner("KI analysiert das Gutachten..."):  # Kommentar: Spinner
            pfad_ki = programm_1_ki_input.main(pdf_path, auswahl, steuerstatus)  # Kommentar: Programm 1
        with open(pfad_ki, "r", encoding="utf-8") as f:  # Kommentar: KI-Datei öffnen
            ki_text = f.read()  # Kommentar: Lesen
        daten = programm_2_word_output.json_aus_ki_antwort_parsen(ki_text)  # Kommentar: JSON parsen
        st.session_state["analysis_done"] = True  # Kommentar: Flag setzen
        st.session_state["analysis_data"] = daten  # Kommentar: Daten speichern
        st.session_state["analysis_paths"] = {"pdf": pdf_path, "ki": pfad_ki, "docx": None}  # Kommentar: Pfade speichern
        st.success("Analyse abgeschlossen. Bitte Daten prüfen/korrigieren und dann Schreiben erzeugen.")  # Kommentar: OK

with col2:  # Kommentar: Rechte Spalte
    if st.button("Reset / Abbrechen"):  # Kommentar: Reset-Button
        cleanup_files(st.session_state["analysis_paths"].get("pdf"), st.session_state["analysis_paths"].get("ki"), st.session_state["analysis_paths"].get("docx"))  # Kommentar: Dateien löschen
        st.session_state["analysis_done"] = False  # Kommentar: Reset
        st.session_state["analysis_data"] = {}  # Kommentar: Reset
        st.session_state["analysis_paths"] = {"pdf": None, "ki": None, "docx": None}  # Kommentar: Reset
        st.rerun()  # Kommentar: Neu laden


if st.session_state["analysis_done"]:  # Kommentar: Wenn Analyse fertig, Review anzeigen
    st.header("5. KI-Daten prüfen & korrigieren")  # Kommentar: Header

    daten = st.session_state["analysis_data"]  # Kommentar: Daten holen

    st.info("Bitte prüfen: besonders Schadensnummer, Aktenzeichen, Unfall-Daten, WBW/Restwert (bei Totalschaden) und Kostenpositionen.")  # Kommentar: Hinweis

    overrides = {}  # Kommentar: Dict für Korrekturen

    c1, c2 = st.columns(2)  # Kommentar: 2 Spalten
    with c1:  # Kommentar: Spalte 1
        overrides["SCHADENSNUMMER"] = st.text_input("Schadensnummer", value=daten.get("SCHADENSNUMMER", ""))  # Kommentar: Input
        overrides["AKTENZEICHEN"] = st.text_input("Aktenzeichen", value=daten.get("AKTENZEICHEN", ""))  # Kommentar: Input
        overrides["POLIZEIAKTE_NUMMER"] = st.text_input("Polizei-Aktennummer", value=daten.get("POLIZEIAKTE_NUMMER", ""))  # Kommentar: Input
        overrides["UNFALL_DATUM"] = st.text_input("Unfall Datum (TT.MM.JJJJ)", value=daten.get("UNFALL_DATUM", ""))  # Kommentar: Input
        overrides["UNFALL_UHRZEIT"] = st.text_input("Unfall Uhrzeit (HH:MM)", value=daten.get("UNFALL_UHRZEIT", ""))  # Kommentar: Input

    with c2:  # Kommentar: Spalte 2
        overrides["UNFALLORT"] = st.text_input("Unfallort", value=daten.get("UNFALLORT", ""))  # Kommentar: Input
        overrides["UNFALL_STRASSE"] = st.text_input("Unfallstraße", value=daten.get("UNFALL_STRASSE", ""))  # Kommentar: Input
        overrides["KENNZEICHEN"] = st.text_input("Kennzeichen", value=daten.get("KENNZEICHEN", ""))  # Kommentar: Input
        overrides["FAHRZEUGTYP"] = st.text_input("Fahrzeugtyp", value=daten.get("FAHRZEUGTYP", ""))  # Kommentar: Input
        overrides["MANDANT_NAME"] = st.text_input("Mandant Name", value=daten.get("MANDANT_NAME", ""))  # Kommentar: Input

    with st.expander("Weitere Felder (Kosten / Totalschaden / Text)", expanded=False):  # Kommentar: Expander
        overrides["REPARATURKOSTEN"] = st.text_input("Reparaturkosten", value=daten.get("REPARATURKOSTEN", ""))  # Kommentar: Input
        overrides["MWST_BETRAG"] = st.text_input("MwSt-Betrag", value=daten.get("MWST_BETRAG", ""))  # Kommentar: Input
        overrides["WERTMINDERUNG"] = st.text_input("Wertminderung", value=daten.get("WERTMINDERUNG", ""))  # Kommentar: Input
        overrides["NUTZUNGSAUSFALL"] = st.text_input("Nutzungsausfall", value=daten.get("NUTZUNGSAUSFALL", ""))  # Kommentar: Input
        overrides["KOSTENPAUSCHALE"] = st.text_input("Kostenpauschale", value=daten.get("KOSTENPAUSCHALE", ""))  # Kommentar: Input
        overrides["GUTACHTERKOSTEN"] = st.text_input("Gutachterkosten", value=daten.get("GUTACHTERKOSTEN", ""))  # Kommentar: Input
        overrides["WIEDERBESCHAFFUNGSWERT"] = st.text_input("Wiederbeschaffungswert (WBW)", value=daten.get("WIEDERBESCHAFFUNGSWERT", ""))  # Kommentar: Input
        overrides["RESTWERT"] = st.text_input("Restwert", value=daten.get("RESTWERT", ""))  # Kommentar: Input
        overrides["SCHADENHERGANG"] = st.text_area("Schadenhergang (Originaltext, ggf. korrigieren)", value=daten.get("SCHADENHERGANG", ""), height=180)  # Kommentar: Textarea

    st.header("6. Schreiben erzeugen")  # Kommentar: Header
    if st.button("2) Schreiben erzeugen & herunterladen"):  # Kommentar: Button
        pfad_ki = st.session_state["analysis_paths"].get("ki")  # Kommentar: KI-Pfad
        pdf_path = st.session_state["analysis_paths"].get("pdf")  # Kommentar: PDF-Pfad
        with st.spinner("Erzeuge Word-Schreiben..."):  # Kommentar: Spinner
            docx_pfad = programm_2_word_output.main(  # Kommentar: Programm 2
                pfad_ki_txt=pfad_ki,  # Kommentar: KI-Datei
                vorlage_pfad=vorlage_pfad,  # Kommentar: Vorlage
                auswahl=auswahl,  # Kommentar: Auswahl
                steuerstatus=steuerstatus,  # Kommentar: Steuerstatus
                zus_bez=zusatzkosten_bezeichnung,  # Kommentar: Zusatz bez
                zus_betrag=zusatzkosten_betrag,  # Kommentar: Zusatz betrag
                overrides=overrides,  # Kommentar: Korrekturen
            )
        with open(docx_pfad, "rb") as f:  # Kommentar: DOCX öffnen
            docx_bytes = f.read()  # Kommentar: Bytes lesen
        cleanup_files(pdf_path, pfad_ki, docx_pfad)  # Kommentar: Alles löschen
        st.session_state["analysis_done"] = False  # Kommentar: Reset
        st.session_state["analysis_data"] = {}  # Kommentar: Reset
        st.session_state["analysis_paths"] = {"pdf": None, "ki": None, "docx": None}  # Kommentar: Reset
        st.success("Schreiben erstellt. Dateien wurden vom Server gelöscht.")  # Kommentar: OK
        st.download_button(  # Kommentar: Download
            label="DOCX herunterladen",  # Kommentar: Label
            data=docx_bytes,  # Kommentar: Daten
            file_name=os.path.basename(docx_pfad),  # Kommentar: Name
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # Kommentar: Mime
        )  # Kommentar: Ende


with st.expander("Debug: Dateien im System anzeigen"):  # Kommentar: Debug expander
    st.write({"eingang_gutachten": os.listdir(EINGANGS_ORDNER)})  # Kommentar: Anzeigen
    st.write({"ki_antworten": os.listdir(KI_ANTWORT_ORDNER)})  # Kommentar: Anzeigen
    st.write({"ausgang_schreiben": os.listdir(AUSGANGS_ORDNER)})  # Kommentar: Anzeigen
