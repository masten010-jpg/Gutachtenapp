# app.py  # Kommentar: Streamlit App mit 2-Schritt-Flow (Analyse -> Review -> Word)

import os  # Kommentar: OS-Funktionen importieren
import json  # Kommentar: JSON importieren
from datetime import datetime  # Kommentar: datetime importieren
import hashlib  # Kommentar: hashlib für PBKDF2 importieren
import secrets  # Kommentar: secrets für sicheren Vergleich/Salt importieren
import streamlit as st  # Kommentar: Streamlit importieren
import config  # Kommentar: config importieren
import programm_1_ki_input  # Kommentar: Programm 1 importieren
import programm_2_word_output  # Kommentar: Programm 2 importieren

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Kommentar: Basisverzeichnis bestimmen
EINGANGS_ORDNER = config.EINGANGS_ORDNER  # Kommentar: Eingangsordner übernehmen
KI_ANTWORT_ORDNER = config.KI_ANTWORT_ORDNER  # Kommentar: KI-Antwortordner übernehmen
AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # Kommentar: Ausgangsordner definieren
USERS_FILE = os.path.join(BASE_DIR, "users.json")  # Kommentar: User-Datei definieren

os.makedirs(EINGANGS_ORDNER, exist_ok=True)  # Kommentar: Eingang anlegen
os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: KI-Ordner anlegen
os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: Ausgang anlegen

st.set_page_config(page_title="Kfz-Gutachten → Anwaltsschreiben", layout="centered")  # Kommentar: Page Config


def _atomic_write_json(path: str, data: dict) -> None:  # Kommentar: JSON atomar schreiben
    tmp = path + ".tmp"  # Kommentar: Temp-Pfad
    with open(tmp, "w", encoding="utf-8") as f:  # Kommentar: Temp-Datei öffnen
        json.dump(data, f, ensure_ascii=False, indent=2)  # Kommentar: JSON schreiben
    os.replace(tmp, path)  # Kommentar: Atomar ersetzen


def load_users() -> dict:  # Kommentar: Users laden
    if not os.path.isfile(USERS_FILE):  # Kommentar: Existiert Datei?
        return {}  # Kommentar: Leeres dict
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


def hash_password(plain_password: str) -> str:  # Kommentar: PBKDF2 Hash erzeugen (ohne bcrypt)
    salt = secrets.token_hex(16)  # Kommentar: Salt generieren
    iterations = 200_000  # Kommentar: Iterationen setzen
    dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), iterations)  # Kommentar: Hash ableiten
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"  # Kommentar: Formatierter Hash-String


def check_password(plain_password: str, stored_hash: str) -> bool:  # Kommentar: Passwort prüfen
    try:  # Kommentar: Try
        parts = stored_hash.split("$")  # Kommentar: Split
        if len(parts) != 4:  # Kommentar: Format prüfen
            return False  # Kommentar: Ungültig
        algo, iter_s, salt, hexhash = parts  # Kommentar: Teile entpacken
        if algo != "pbkdf2_sha256":  # Kommentar: Algo prüfen
            return False  # Kommentar: Ungültig
        iterations = int(iter_s)  # Kommentar: Iterationen parsen
        dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), iterations)  # Kommentar: Hash neu berechnen
        return secrets.compare_digest(dk.hex(), hexhash)  # Kommentar: Konstantzeitvergleich
    except Exception:  # Kommentar: Fehler
        return False  # Kommentar: Fallback


def valid_username(name: str) -> bool:  # Kommentar: Username validieren
    if not name or len(name) < 3 or len(name) > 32:  # Kommentar: Länge prüfen
        return False  # Kommentar: Fail
    for ch in name:  # Kommentar: Iterieren
        if not (ch.isalnum() or ch in ["_", "-"]):  # Kommentar: Erlaubte Zeichen
            return False  # Kommentar: Fail
    return True  # Kommentar: OK


def valid_password(pw: str) -> bool:  # Kommentar: Passwort validieren
    return isinstance(pw, str) and len(pw) >= 10  # Kommentar: Mindestens 10 Zeichen


def register_user(username: str, pw: str) -> tuple[bool, str]:  # Kommentar: User registrieren
    users = load_users()  # Kommentar: Users laden
    if not valid_username(username):  # Kommentar: Username prüfen
        return False, "Benutzername ungültig (3–32 Zeichen, nur a-z A-Z 0-9 _ -)."  # Kommentar: Msg
    if username in users:  # Kommentar: Schon vorhanden?
        return False, "Benutzername existiert bereits."  # Kommentar: Msg
    if not valid_password(pw):  # Kommentar: Passwort prüfen
        return False, "Passwort zu kurz (mindestens 10 Zeichen)."  # Kommentar: Msg
    users[username] = hash_password(pw)  # Kommentar: Hash speichern
    save_users(users)  # Kommentar: Speichern
    return True, "Registrierung erfolgreich. Du kannst dich jetzt einloggen."  # Kommentar: OK


def login_user(username: str, pw: str) -> tuple[bool, str]:  # Kommentar: Login prüfen
    users = load_users()  # Kommentar: Users laden
    stored = users.get(username)  # Kommentar: Hash holen
    if not stored or not check_password(pw, stored):  # Kommentar: Prüfen
        return False, "Benutzername oder Passwort falsch."  # Kommentar: Msg
    return True, "Login erfolgreich."  # Kommentar: OK


def cleanup_files(*paths: str) -> None:  # Kommentar: Dateien löschen
    for path in paths:  # Kommentar: Iterieren
        if path and os.path.exists(path):  # Kommentar: Existiert?
            try:  # Kommentar: Try
                os.remove(path)  # Kommentar: Entfernen
            except OSError:  # Kommentar: Fehler
                pass  # Kommentar: Ignorieren (MVP)


VORLAGEN = {  # Kommentar: Deine Vorlagen-Auswahl
    "Fiktive Abrechnung (Reparaturschaden)": "vorlage_fiktive_abrechnung.docx",  # Kommentar: Vorlage
    "Konkrete Abrechnung < WBW": "vorlage_konkret_unter_wbw.docx",  # Kommentar: Vorlage
    "130%-Regelung": "vorlage_130_prozent.docx",  # Kommentar: Vorlage
    "Totalschaden fiktiv": "vorlage_totalschaden_fiktiv.docx",  # Kommentar: Vorlage
    "Totalschaden konkret": "vorlage_totalschaden_konkret.docx",  # Kommentar: Vorlage
    "Totalschaden Ersatzbeschaffung": "vorlage_totalschaden_ersatzbeschaffung.docx",  # Kommentar: Vorlage
}  # Kommentar: Ende dict


def resolve_vorlage_pfad(auswahl: str) -> str:  # Kommentar: Vorlage auflösen
    if auswahl not in VORLAGEN:  # Kommentar: Auswahl prüfen
        raise ValueError(f"Unbekannte Auswahl: {auswahl}")  # Kommentar: Fehler
    dateiname = VORLAGEN[auswahl]  # Kommentar: Dateiname holen
    if getattr(config, "VORLAGEN_ORDNER", None):  # Kommentar: Vorlagenordner vorhanden?
        pfad1 = os.path.join(config.VORLAGEN_ORDNER, dateiname)  # Kommentar: Pfad bauen
        if os.path.isfile(pfad1):  # Kommentar: Existiert?
            return pfad1  # Kommentar: Return
    pfad2 = os.path.join(BASE_DIR, dateiname)  # Kommentar: Fallback im Projektordner
    if os.path.isfile(pfad2):  # Kommentar: Existiert?
        return pfad2  # Kommentar: Return
    if os.path.isabs(dateiname) and os.path.isfile(dateiname):  # Kommentar: Absoluter Pfad?
        return dateiname  # Kommentar: Return
    raise FileNotFoundError(f"Vorlage nicht gefunden: {dateiname}")  # Kommentar: Fehler


if "logged_in" not in st.session_state:  # Kommentar: Session init
    st.session_state["logged_in"] = False  # Kommentar: Default
    st.session_state["username"] = None  # Kommentar: Default

if "analysis_done" not in st.session_state:  # Kommentar: Analyse-Status init
    st.session_state["analysis_done"] = False  # Kommentar: Default

if "analysis_data" not in st.session_state:  # Kommentar: Analyse-Daten init
    st.session_state["analysis_data"] = {}  # Kommentar: Default

if "analysis_paths" not in st.session_state:  # Kommentar: Pfade init
    st.session_state["analysis_paths"] = {"pdf": None, "ki": None, "docx": None}  # Kommentar: Default


if not st.session_state["logged_in"]:  # Kommentar: Login/Registrierung UI
    st.title("Zugang geschützt")  # Kommentar: Titel
    mode = st.radio("Aktion", options=["Login", "Registrieren"], horizontal=True)  # Kommentar: Auswahl
    username = st.text_input("Benutzername")  # Kommentar: Username Input
    pw = st.text_input("Passwort", type="password")  # Kommentar: Passwort Input
    if mode == "Registrieren":  # Kommentar: Registrierung
        pw2 = st.text_input("Passwort wiederholen", type="password")  # Kommentar: Passwort 2
        if st.button("Registrieren"):  # Kommentar: Button
            if pw != pw2:  # Kommentar: Prüfen
                st.error("Passwörter stimmen nicht überein.")  # Kommentar: Fehler
                st.stop()  # Kommentar: Stop
            ok, msg = register_user(username.strip(), pw)  # Kommentar: Registrieren
            if ok:  # Kommentar: Erfolg?
                st.success(msg)  # Kommentar: Anzeige
            else:  # Kommentar: Fehler
                st.error(msg)  # Kommentar: Anzeige
        st.stop()  # Kommentar: Stop
    if st.button("Login"):  # Kommentar: Login Button
        ok, msg = login_user(username.strip(), pw)  # Kommentar: Login
        if ok:  # Kommentar: Erfolg?
            st.session_state["logged_in"] = True  # Kommentar: Set
            st.session_state["username"] = username.strip()  # Kommentar: Set
            st.rerun()  # Kommentar: Rerun
        else:  # Kommentar: Fehler
            st.error(msg)  # Kommentar: Anzeige
            st.stop()  # Kommentar: Stop
    st.stop()  # Kommentar: Stop wenn nicht eingeloggt

st.title(f"Kfz-Gutachten Automatisierung - Eingeloggt als {st.session_state['username']}")  # Kommentar: Titel

if st.button("Logout"):  # Kommentar: Logout Button
    cleanup_files(st.session_state["analysis_paths"].get("pdf"), st.session_state["analysis_paths"].get("ki"), st.session_state["analysis_paths"].get("docx"))  # Kommentar: Dateien löschen
    st.session_state["logged_in"] = False  # Kommentar: Reset
    st.session_state["username"] = None  # Kommentar: Reset
    st.session_state["analysis_done"] = False  # Kommentar: Reset
    st.session_state["analysis_data"] = {}  # Kommentar: Reset
    st.session_state["analysis_paths"] = {"pdf": None, "ki": None, "docx": None}  # Kommentar: Reset
    st.rerun()  # Kommentar: Rerun

st.header("1. Abrechnungsvariante / Vorlage wählen")  # Kommentar: Header
auswahl = st.selectbox("Welche Variante möchten Sie verwenden?", list(VORLAGEN.keys()))  # Kommentar: Auswahl
vorlage_pfad = resolve_vorlage_pfad(auswahl)  # Kommentar: Pfad auflösen
st.caption(f"Verwendete Vorlage-Datei: {os.path.basename(vorlage_pfad)}")  # Kommentar: Anzeige

st.header("2. Steuerstatus")  # Kommentar: Header
steuerstatus = st.selectbox("Steuerstatus des Geschädigten", ["nicht vorsteuerabzugsberechtigt", "vorsteuerabzugsberechtigt"], index=0)  # Kommentar: Auswahl

st.header("3. Optional: Zusatzkosten")  # Kommentar: Header
zusatzkosten_bezeichnung = st.text_input("Bezeichnung (optional)", value="")  # Kommentar: Input
zusatzkosten_betrag = st.text_input("Betrag in Euro (optional, z.B. 25,00)", value="")  # Kommentar: Input

st.header("4. Gutachten hochladen")  # Kommentar: Header
uploaded_file = st.file_uploader("Gutachten als PDF hochladen", type=["pdf"])  # Kommentar: Upload

col1, col2 = st.columns(2)  # Kommentar: Buttons nebeneinander

with col1:  # Kommentar: Spalte 1
    if st.button("1) KI analysieren"):  # Kommentar: Analysebutton
        if uploaded_file is None:  # Kommentar: PDF vorhanden?
            st.error("Bitte zuerst eine PDF-Datei hochladen.")  # Kommentar: Fehler
            st.stop()  # Kommentar: Stop
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Kommentar: Timestamp
        safe_name = f"gutachten_{timestamp}.pdf"  # Kommentar: Dateiname
        pdf_path = os.path.join(EINGANGS_ORDNER, safe_name)  # Kommentar: Zielpfad
        with open(pdf_path, "wb") as f:  # Kommentar: PDF speichern
            f.write(uploaded_file.getbuffer())  # Kommentar: Bytes schreiben
        st.info(f"PDF gespeichert als: {safe_name}")  # Kommentar: Info
        with st.spinner("KI analysiert das Gutachten..."):  # Kommentar: Spinner
            try:  # Kommentar: Try, damit Streamlit nicht redacted
                pfad_ki = programm_1_ki_input.main(pdf_path, auswahl, steuerstatus)  # Kommentar: Programm 1 ausführen
            except Exception as e:  # Kommentar: Fehler abfangen
                st.error(f"KI-Fehler (Details): {repr(e)}")  # Kommentar: Echte Fehlermeldung anzeigen
                print("[KI-Fehler] repr(e) =", repr(e))  # Kommentar: In Logs schreiben
                cleanup_files(pdf_path)  # Kommentar: PDF löschen, weil Analyse fehlgeschlagen
                st.stop()  # Kommentar: Stop
        with open(pfad_ki, "r", encoding="utf-8") as f:  # Kommentar: KI-Datei öffnen
            ki_text = f.read()  # Kommentar: Inhalt lesen
        try:  # Kommentar: JSON parsen absichern
            daten = programm_2_word_output.json_aus_ki_antwort_parsen(ki_text)  # Kommentar: JSON extrahieren
        except Exception as e:  # Kommentar: Parse-Fehler abfangen
            st.error(f"JSON-Parse-Fehler (Details): {repr(e)}")  # Kommentar: Fehler anzeigen
            print("[JSON-Parse-Fehler] repr(e) =", repr(e))  # Kommentar: Logs
            cleanup_files(pdf_path, pfad_ki)  # Kommentar: Dateien löschen
            st.stop()  # Kommentar: Stop
        st.session_state["analysis_done"] = True  # Kommentar: Analyseflag setzen
        st.session_state["analysis_data"] = daten  # Kommentar: Daten speichern
        st.session_state["analysis_paths"] = {"pdf": pdf_path, "ki": pfad_ki, "docx": None}  # Kommentar: Pfade speichern
        st.success("Analyse abgeschlossen. Bitte Daten prüfen/korrigieren und dann Schreiben erzeugen.")  # Kommentar: OK

with col2:  # Kommentar: Spalte 2
    if st.button("Reset / Abbrechen"):  # Kommentar: Reset
        cleanup_files(st.session_state["analysis_paths"].get("pdf"), st.session_state["analysis_paths"].get("ki"), st.session_state["analysis_paths"].get("docx"))  # Kommentar: Dateien löschen
        st.session_state["analysis_done"] = False  # Kommentar: Reset
        st.session_state["analysis_data"] = {}  # Kommentar: Reset
        st.session_state["analysis_paths"] = {"pdf": None, "ki": None, "docx": None}  # Kommentar: Reset
        st.rerun()  # Kommentar: Rerun

if st.session_state["analysis_done"]:  # Kommentar: Review-UI nur wenn Analyse fertig
    st.header("5. KI-Daten prüfen & korrigieren")  # Kommentar: Header
    daten = st.session_state["analysis_data"]  # Kommentar: Daten holen
    st.info("Bitte prüfen: Schadensnummer, Aktenzeichen, Unfall-Daten, Totalschadenwerte (WBW/Restwert) und Kostenpositionen.")  # Kommentar: Hinweis
    overrides = {}  # Kommentar: Overrides dict

    c1, c2 = st.columns(2)  # Kommentar: Zwei Spalten
    with c1:  # Kommentar: Links
        overrides["SCHADENSNUMMER"] = st.text_input("Schadensnummer", value=daten.get("SCHADENSNUMMER", ""))  # Kommentar: Input
        overrides["AKTENZEICHEN"] = st.text_input("Aktenzeichen", value=daten.get("AKTENZEICHEN", ""))  # Kommentar: Input
        overrides["POLIZEIAKTE_NUMMER"] = st.text_input("Polizei-Aktennummer", value=daten.get("POLIZEIAKTE_NUMMER", ""))  # Kommentar: Input
        overrides["UNFALL_DATUM"] = st.text_input("Unfall Datum (TT.MM.JJJJ)", value=daten.get("UNFALL_DATUM", ""))  # Kommentar: Input
        overrides["UNFALL_UHRZEIT"] = st.text_input("Unfall Uhrzeit (HH:MM)", value=daten.get("UNFALL_UHRZEIT", ""))  # Kommentar: Input

    with c2:  # Kommentar: Rechts
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
        overrides["SCHADENHERGANG"] = st.text_area("Schadenhergang (Originaltext, ggf. korrigieren)", value=daten.get("SCHADENHERGANG", ""), height=180)  # Kommentar: Input

    st.header("6. Schreiben erzeugen")  # Kommentar: Header
    if st.button("2) Schreiben erzeugen & herunterladen"):  # Kommentar: Button
        pfad_ki = st.session_state["analysis_paths"].get("ki")  # Kommentar: KI-Pfad
        pdf_path = st.session_state["analysis_paths"].get("pdf")  # Kommentar: PDF-Pfad
        with st.spinner("Erzeuge Word-Schreiben..."):  # Kommentar: Spinner
            try:  # Kommentar: Try
                docx_pfad = programm_2_word_output.main(  # Kommentar: Programm 2 aufrufen
                    pfad_ki_txt=pfad_ki,  # Kommentar: KI-Datei
                    vorlage_pfad=vorlage_pfad,  # Kommentar: Vorlage
                    auswahl=auswahl,  # Kommentar: Auswahl
                    steuerstatus=steuerstatus,  # Kommentar: Steuerstatus
                    zus_bez=zusatzkosten_bezeichnung,  # Kommentar: Zusatzkosten-Bezeichnung
                    zus_betrag=zusatzkosten_betrag,  # Kommentar: Zusatzkosten-Betrag
                    overrides=overrides,  # Kommentar: Nutzer-Korrekturen
                )  # Kommentar: Call Ende
            except Exception as e:  # Kommentar: Fehler abfangen
                st.error(f"Word-Erzeugung Fehler (Details): {repr(e)}")  # Kommentar: Fehler anzeigen
                print("[Word-Fehler] repr(e) =", repr(e))  # Kommentar: Logs
                st.stop()  # Kommentar: Stop
        with open(docx_pfad, "rb") as f:  # Kommentar: DOCX öffnen
            docx_bytes = f.read()  # Kommentar: Bytes lesen
        cleanup_files(pdf_path, pfad_ki, docx_pfad)  # Kommentar: Dateien löschen
        st.session_state["analysis_done"] = False  # Kommentar: Reset
        st.session_state["analysis_data"] = {}  # Kommentar: Reset
        st.session_state["analysis_paths"] = {"pdf": None, "ki": None, "docx": None}  # Kommentar: Reset
        st.success("Schreiben erstellt. Dateien wurden vom Server gelöscht.")  # Kommentar: OK
        st.download_button(label="DOCX herunterladen", data=docx_bytes, file_name=os.path.basename(docx_pfad), mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")  # Kommentar: Download

with st.expander("Debug: Dateien im System anzeigen"):  # Kommentar: Debug
    st.write({"eingang_gutachten": os.listdir(EINGANGS_ORDNER)})  # Kommentar: Dateien
    st.write({"ki_antworten": os.listdir(KI_ANTWORT_ORDNER)})  # Kommentar: Dateien
    st.write({"ausgang_schreiben": os.listdir(AUSGANGS_ORDNER)})  # Kommentar: Dateien
