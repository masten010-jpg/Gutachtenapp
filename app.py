# app.py  # Kommentar: Streamlit App (Upload -> KI Analyse -> Korrektur -> Word erzeugen)

import os  # Kommentar: Für Dateipfade und Ordner
import json  # Kommentar: Für JSON (Users / KI-Zwischenformat)
import time  # Kommentar: Für Timing (optional)
import hashlib  # Kommentar: Für PBKDF2 Passwort-Hashing (ohne externe Library)
import hmac  # Kommentar: Für konstanten Zeitvergleich beim Login
import secrets  # Kommentar: Für kryptografisch sicheren Salt
from datetime import datetime  # Kommentar: Für Zeitstempel bei Dateinamen
import streamlit as st  # Kommentar: Streamlit UI

import config  # Kommentar: Konfigurationsdatei (Ordnerpfade / Vorlagenordner)
import programm_1_ki_input  # Kommentar: Programm 1: PDF -> KI -> _ki.txt
import programm_2_word_output  # Kommentar: Programm 2: JSON -> DOCX

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Kommentar: Basisverzeichnis des Projekts
EINGANGS_ORDNER = config.EINGANGS_ORDNER  # Kommentar: PDF Eingang
KI_ANTWORT_ORDNER = config.KI_ANTWORT_ORDNER  # Kommentar: KI Antworten Ordner
AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # Kommentar: DOCX Ausgabe Ordner

os.makedirs(EINGANGS_ORDNER, exist_ok=True)  # Kommentar: Ordner anlegen (falls nicht vorhanden)
os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: Ordner anlegen (falls nicht vorhanden)
os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: Ordner anlegen (falls nicht vorhanden)

st.set_page_config(page_title="Kfz-Gutachten → Anwaltsschreiben", layout="centered")  # Kommentar: Streamlit Setup

USERS_FILE = os.path.join(BASE_DIR, "users.json")  # Kommentar: User-Speicherdatei (Hash + Salt)
PBKDF2_ITERATIONS = 200_000  # Kommentar: PBKDF2 Iterationen (MVP-sicher)
PBKDF2_ALGO = "sha256"  # Kommentar: PBKDF2 Hash Algorithmus
SALT_BYTES = 16  # Kommentar: Salt Länge (Bytes)

# ==========================
# Prompt-Baustein (nur Anzeige / Copy-Paste in Programm 1)
# ==========================
SCHADENHERGANG_WORDTAUGLICH_PROMPT = """\
WICHTIG: Feld SCHADENHERGANG (Word-tauglich)

Das Feld "SCHADENHERGANG" soll NICHT als roher Gutachten-Abschnitt ausgegeben werden,
sondern als SCHREIBFERTIGER Absatz für ein Anwaltsschreiben.

REGELN:
- Verwende ausschließlich Informationen, die eindeutig im Gutachten-Text stehen.
- Erfinde nichts, rate nichts. Wenn wesentliche Infos fehlen: SCHADENHERGANG = "".
- Maximal 3–6 Sätze, sachlich und neutral.
- Keine Schuldzuweisung, keine rechtliche Bewertung, keine Floskeln.
- Wenn im Gutachten ein Abschnitt "Schadenhergang/Unfallhergang/Sachverhalt" existiert:
  Nutze nur dessen Inhalt als Grundlage (nicht andere Stellen).
- Wenn kein klarer Abschnitt vorhanden ist: SCHADENHERGANG = "".

INHALT (nur wenn vorhanden):
- Unfallzeitpunkt (Datum + Uhrzeit)
- Unfallort (Ort + Straße)
- Beteiligte Fahrzeuge (Fahrzeugtyp/Kennzeichen nur wenn genannt)
- Kurze Beschreibung des Ablaufs (nur wenn eindeutig)
- Schadenseintritt (z.B. Kollision/Anstoß – nur wenn eindeutig)

4. SCHADENHERGANG (WICHTIG – für Word als Absatz, aber TEXTTREU):

ZIEL:
- Das Feld "SCHADENHERGANG" soll als zusammenhängender Absatz in die Word-Vorlage passen.
- ABER: Der Inhalt muss trotzdem AUS dem Gutachten-Text stammen (texttreu).

VORGEHEN:
A) Suche eine Überschrift/Section wie:
   "Schadenhergang", "Schadenshergang", "Unfallhergang", "Sachverhalt", "Unfallschilderung".
B) Wenn gefunden:
   - Übernimm den Textabschnitt DIREKT unter dieser Überschrift möglichst WÖRTLICH.
   - Keine eigene Zusammenfassung, keine neuen Sätze, keine Umformulierungen.
   - Du darfst nur kürzen (z.B. auf 800–1500 Zeichen), aber nicht neu schreiben.
   - Stoppe beim nächsten klaren Kapitel/Überschrift.
C) Wenn NICHT gefunden:
   - SCHADENHERGANG = "" (leer).
   - KEIN Ersatztext wie "Der Unfall ereignete sich ..." – lieber leer als erfunden/abgeleitet.

Mindestlänge-Regel:
- Wenn ein passender Abschnitt gefunden wurde und er mindestens 250 Zeichen enthält:
  -> Gib mindestens 70 Zeichen davon in SCHADENHERGANG zurück.
- Wenn der Abschnitt kürzer ist oder nur aus 1 Zeile besteht:
  -> SCHADENHERGANG = "".

FORMAT:
- Ein zusammenhängender Absatz (keine Bulletpoints).
- Keine Überschrift davor.
"""

# ==========================
# Helper: JSON atomar schreiben
# ==========================
def _atomic_write_json(path: str, data: dict) -> None:  # Kommentar: JSON atomar speichern (verhindert kaputte Datei)
    tmp = path + ".tmp"  # Kommentar: Temp-Datei
    with open(tmp, "w", encoding="utf-8") as f:  # Kommentar: Temp-Datei öffnen
        json.dump(data, f, ensure_ascii=False, indent=2)  # Kommentar: JSON schreiben
    os.replace(tmp, path)  # Kommentar: Temp-Datei atomar ersetzen

# ==========================
# User Storage
# ==========================
def load_users() -> dict:  # Kommentar: Users.json laden
    if not os.path.isfile(USERS_FILE):  # Kommentar: Wenn Datei nicht existiert
        return {}  # Kommentar: Dann leeres Dict
    try:  # Kommentar: Fehler abfangen
        with open(USERS_FILE, "r", encoding="utf-8") as f:  # Kommentar: Datei öffnen
            data = json.load(f)  # Kommentar: JSON laden
        if isinstance(data, dict):  # Kommentar: Format check
            return data  # Kommentar: Zurückgeben
    except Exception:  # Kommentar: Fehlerfall
        return {}  # Kommentar: Fallback
    return {}  # Kommentar: Fallback

def save_users(users: dict) -> None:  # Kommentar: Users speichern
    _atomic_write_json(USERS_FILE, users)  # Kommentar: Atomar schreiben

def valid_username(name: str) -> bool:  # Kommentar: Username validieren
    if not name or len(name) < 3 or len(name) > 32:  # Kommentar: Längencheck
        return False  # Kommentar: Ungültig
    for ch in name:  # Kommentar: Zeichen prüfen
        if not (ch.isalnum() or ch in ["_", "-"]):  # Kommentar: Nur alnum/_/-
            return False  # Kommentar: Ungültig
    return True  # Kommentar: Gültig

def valid_password(pw: str) -> bool:  # Kommentar: Passwort validieren
    return isinstance(pw, str) and len(pw) >= 10  # Kommentar: Mindestlänge

def pbkdf2_hash_password(password: str, salt_hex: str) -> str:  # Kommentar: PBKDF2 Hash berechnen
    salt = bytes.fromhex(salt_hex)  # Kommentar: Salt hex -> bytes
    dk = hashlib.pbkdf2_hmac(PBKDF2_ALGO, password.encode("utf-8"), salt, PBKDF2_ITERATIONS)  # Kommentar: Ableitung
    return dk.hex()  # Kommentar: Rückgabe als hex

def create_password_record(password: str) -> dict:  # Kommentar: Record erstellen (salt + hash)
    salt_hex = secrets.token_bytes(SALT_BYTES).hex()  # Kommentar: Salt erzeugen
    pw_hash_hex = pbkdf2_hash_password(password, salt_hex)  # Kommentar: Hash erzeugen
    return {"salt": salt_hex, "hash": pw_hash_hex}  # Kommentar: Record zurückgeben

def check_password(password: str, record: dict) -> bool:  # Kommentar: Passwort prüfen
    if not isinstance(record, dict):  # Kommentar: Typcheck
        return False  # Kommentar: Ungültig
    salt_hex = record.get("salt", "")  # Kommentar: Salt holen
    stored_hash = record.get("hash", "")  # Kommentar: Hash holen
    if not salt_hex or not stored_hash:  # Kommentar: Wenn fehlt
        return False  # Kommentar: Ungültig
    candidate = pbkdf2_hash_password(password, salt_hex)  # Kommentar: Kandidatenhash
    return hmac.compare_digest(candidate, stored_hash)  # Kommentar: Konstanter Vergleich

def register_user(username: str, pw: str) -> tuple[bool, str]:  # Kommentar: Registrieren
    users = load_users()  # Kommentar: Users laden
    if not valid_username(username):  # Kommentar: Username prüfen
        return False, "Benutzername ungültig (3–32 Zeichen, nur a-z A-Z 0-9 _ -)."  # Kommentar: Meldung
    if username in users:  # Kommentar: Existiert bereits?
        return False, "Benutzername existiert bereits."  # Kommentar: Meldung
    if not valid_password(pw):  # Kommentar: Passwort prüfen
        return False, "Passwort zu kurz (mindestens 10 Zeichen)."  # Kommentar: Meldung
    users[username] = create_password_record(pw)  # Kommentar: Hash+Salt speichern
    save_users(users)  # Kommentar: Persistieren
    return True, "Registrierung erfolgreich. Du kannst dich jetzt einloggen."  # Kommentar: OK

def login_user(username: str, pw: str) -> tuple[bool, str]:  # Kommentar: Login
    users = load_users()  # Kommentar: Users laden
    record = users.get(username)  # Kommentar: Record holen
    if not record or not check_password(pw, record):  # Kommentar: Check
        return False, "Benutzername oder Passwort falsch."  # Kommentar: Einheitliche Meldung
    st.session_state["logged_in"] = True  # Kommentar: Session setzen
    st.session_state["username"] = username  # Kommentar: Username setzen
    return True, "Login erfolgreich."  # Kommentar: OK

# ==========================
# Vorlagen-Auswahl
# ==========================
VORLAGEN = {  # Kommentar: Deine 6 Varianten
    "Fiktive Abrechnung (Reparaturschaden)": "vorlage_fiktive_abrechnung.docx",  # Kommentar: Variante 1
    "Konkrete Abrechnung < WBW": "vorlage_konkret_unter_wbw.docx",  # Kommentar: Variante 2
    "130%-Regelung": "vorlage_130_prozent.docx",  # Kommentar: Variante 3
    "Totalschaden fiktiv": "vorlage_totalschaden_fiktiv.docx",  # Kommentar: Variante 4
    "Totalschaden konkret": "vorlage_totalschaden_konkret.docx",  # Kommentar: Variante 5
    "Totalschaden Ersatzbeschaffung": "vorlage_schreibentotalschaden.docx"  # Kommentar: Variante 6
}  # Kommentar: Ende Vorlagen

def resolve_vorlage_pfad(auswahl: str) -> str:  # Kommentar: Auswahl -> Pfad
    if auswahl not in VORLAGEN:  # Kommentar: Check
        raise ValueError(f"Unbekannte Auswahl: {auswahl}")  # Kommentar: Fehler
    dateiname = VORLAGEN[auswahl]  # Kommentar: Dateiname
    if getattr(config, "VORLAGEN_ORDNER", None):  # Kommentar: Wenn Vorlagenordner gesetzt
        pfad1 = os.path.join(config.VORLAGEN_ORDNER, dateiname)  # Kommentar: Pfad
        if os.path.isfile(pfad1):  # Kommentar: Existiert?
            return pfad1  # Kommentar: Treffer
    pfad2 = os.path.join(BASE_DIR, dateiname)  # Kommentar: Fallback in BASE_DIR
    if os.path.isfile(pfad2):  # Kommentar: Existiert?
        return pfad2  # Kommentar: Treffer
    if os.path.isabs(dateiname) and os.path.isfile(dateiname):  # Kommentar: Absoluter Pfad
        return dateiname  # Kommentar: Treffer
    raise FileNotFoundError(f"Vorlage nicht gefunden: {dateiname}")  # Kommentar: Fehler

# ==========================
# Datei-Cleanup
# ==========================
def cleanup_files(*paths: str) -> None:  # Kommentar: Dateien löschen
    for path in paths:  # Kommentar: Iterieren
        if path and os.path.exists(path):  # Kommentar: Existenz prüfen
            try:  # Kommentar: Try
                os.remove(path)  # Kommentar: Löschen
            except OSError:  # Kommentar: Fehler ignorieren
                pass  # Kommentar: MVP

# ==========================
# Wrapper: DOCX aus korrigierten Daten erzeugen (robust)
# ==========================
def generate_docx_from_corrected_data(  # Kommentar: Erzeugt DOCX aus Daten, egal ob programm_2 generate_from_data existiert
    daten: dict,  # Kommentar: Korrigierte Daten
    vorlage_pfad: str,  # Kommentar: Vorlagepfad
    auswahl: str,  # Kommentar: Variante
    steuerstatus: str,  # Kommentar: Steuerstatus
    zus_bez: str,  # Kommentar: Zusatzkosten-Bezeichnung
    zus_betrag: str,  # Kommentar: Zusatzkosten-Betrag
) -> str:  # Kommentar: Gibt Pfad zur DOCX zurück
    if hasattr(programm_2_word_output, "generate_from_data"):  # Kommentar: Wenn Funktion existiert
        return programm_2_word_output.generate_from_data(  # Kommentar: Direkt nutzen
            daten=daten,  # Kommentar: Daten
            vorlage_pfad=vorlage_pfad,  # Kommentar: Vorlage
            auswahl=auswahl,  # Kommentar: Variante
            steuerstatus=steuerstatus,  # Kommentar: Steuerstatus
            zus_bez=zus_bez,  # Kommentar: Zusatzname
            zus_betrag=zus_betrag,  # Kommentar: Zusatzbetrag
        )  # Kommentar: Return
    tmp_name = f"corrected_{datetime.now().strftime('%Y%m%d_%H%M%S')}_ki.txt"  # Kommentar: Temp-Dateiname
    tmp_path = os.path.join(KI_ANTWORT_ORDNER, tmp_name)  # Kommentar: Temp-Pfad
    wrapper_text = "JSON_START\n" + json.dumps(daten, ensure_ascii=False, indent=2) + "\nJSON_END\n"  # Kommentar: KI-Wrapper bauen
    with open(tmp_path, "w", encoding="utf-8") as f:  # Kommentar: Schreiben
        f.write(wrapper_text)  # Kommentar: Inhalt schreiben
    try:  # Kommentar: Try
        return programm_2_word_output.main(  # Kommentar: Fallback: main nutzen
            pfad_ki_txt=tmp_path,  # Kommentar: Temp-KI-Datei
            vorlage_pfad=vorlage_pfad,  # Kommentar: Vorlage
            auswahl=auswahl,  # Kommentar: Variante
            steuerstatus=steuerstatus,  # Kommentar: Steuerstatus
            zus_bez=zus_bez,  # Kommentar: Zusatzname
            zus_betrag=zus_betrag,  # Kommentar: Zusatzbetrag
        )  # Kommentar: Return
    finally:  # Kommentar: Cleanup
        cleanup_files(tmp_path)  # Kommentar: Temp-Datei löschen

# ==========================
# Session State init
# ==========================
if "logged_in" not in st.session_state:  # Kommentar: Session init
    st.session_state["logged_in"] = False  # Kommentar: Default
    st.session_state["username"] = None  # Kommentar: Default

if "analysis_ready" not in st.session_state:  # Kommentar: Analyse-Flag
    st.session_state["analysis_ready"] = False  # Kommentar: Default
if "analysis_data" not in st.session_state:  # Kommentar: Analyse-Daten
    st.session_state["analysis_data"] = {}  # Kommentar: Default
if "analysis_pdf_path" not in st.session_state:  # Kommentar: PDF Pfad
    st.session_state["analysis_pdf_path"] = ""  # Kommentar: Default
if "analysis_ki_path" not in st.session_state:  # Kommentar: KI Pfad
    st.session_state["analysis_ki_path"] = ""  # Kommentar: Default
if "analysis_meta" not in st.session_state:  # Kommentar: Meta (Variante etc.)
    st.session_state["analysis_meta"] = {}  # Kommentar: Default

# ==========================
# Login UI
# ==========================
if not st.session_state["logged_in"]:  # Kommentar: Login Screen
    st.title("Zugang geschützt")  # Kommentar: Titel
    mode = st.radio("Aktion", options=["Login", "Registrieren"], horizontal=True)  # Kommentar: Moduswahl
    username = st.text_input("Benutzername")  # Kommentar: Username
    pw = st.text_input("Passwort", type="password")  # Kommentar: Passwort
    if mode == "Registrieren":  # Kommentar: Registrierung
        pw2 = st.text_input("Passwort wiederholen", type="password")  # Kommentar: PW2
        if st.button("Registrieren"):  # Kommentar: Button
            if pw != pw2:  # Kommentar: Match check
                st.error("Passwörter stimmen nicht überein.")  # Kommentar: Fehler
                st.stop()  # Kommentar: Stop
            ok, msg = register_user(username.strip(), pw)  # Kommentar: Register call
            if ok:  # Kommentar: Erfolg
                st.success(msg)  # Kommentar: Output
            else:  # Kommentar: Fehler
                st.error(msg)  # Kommentar: Output
        st.stop()  # Kommentar: Ende
    if st.button("Login"):  # Kommentar: Login button
        ok, msg = login_user(username.strip(), pw)  # Kommentar: Login call
        if ok:  # Kommentar: Erfolg
            st.rerun()  # Kommentar: Reload
        st.error(msg)  # Kommentar: Fehleranzeige
        st.stop()  # Kommentar: Stop
    st.stop()  # Kommentar: Ende

# ==========================
# App UI (nach Login)
# ==========================
st.title(f"Kfz-Gutachten Automatisierung - Eingeloggt als {st.session_state['username']}")  # Kommentar: Titel nach Login

if st.button("Logout"):  # Kommentar: Logout button
    st.session_state["logged_in"] = False  # Kommentar: Reset
    st.session_state["username"] = None  # Kommentar: Reset
    st.session_state["analysis_ready"] = False  # Kommentar: Reset
    st.session_state["analysis_data"] = {}  # Kommentar: Reset
    st.session_state["analysis_meta"] = {}  # Kommentar: Reset
    st.session_state["analysis_pdf_path"] = ""  # Kommentar: Reset
    st.session_state["analysis_ki_path"] = ""  # Kommentar: Reset
    st.rerun()  # Kommentar: Reload

st.header("1. Abrechnungsvariante / Vorlage wählen")  # Kommentar: Abschnitt
auswahl = st.selectbox("Welche Variante möchten Sie verwenden?", list(VORLAGEN.keys()))  # Kommentar: Auswahl
vorlage_pfad = resolve_vorlage_pfad(auswahl)  # Kommentar: Pfad bestimmen
st.caption(f"Verwendete Vorlage-Datei: {os.path.basename(vorlage_pfad)}")  # Kommentar: Anzeige

st.header("2. Steuerstatus des Geschädigten")  # Kommentar: Abschnitt
steuerstatus = st.selectbox(  # Kommentar: Dropdown
    "Steuerstatus",  # Kommentar: Label
    ["nicht vorsteuerabzugsberechtigt", "vorsteuerabzugsberechtigt"],  # Kommentar: Optionen
    index=0,  # Kommentar: Default
)  # Kommentar: Ende selectbox

st.header("3. Optional: Zusatzkosten")  # Kommentar: Abschnitt
zusatzkosten_bezeichnung = st.text_input("Bezeichnung (optional)", value="")  # Kommentar: Zusatzkosten Name
zusatzkosten_betrag = st.text_input("Betrag in Euro (optional, z.B. 25,00)", value="")  # Kommentar: Zusatzkosten Betrag

st.header("4. Gutachten hochladen")  # Kommentar: Abschnitt
uploaded_file = st.file_uploader("Gutachten als PDF hochladen", type=["pdf"])  # Kommentar: Upload

# ==========================
# Schritt 1: Analyse
# ==========================
if st.button("1) Analysieren (KI)"):  # Kommentar: Schritt 1
    if uploaded_file is None:  # Kommentar: Kein Upload?
        st.error("Bitte zuerst eine PDF-Datei hochladen.")  # Kommentar: Hinweis
        st.stop()  # Kommentar: Stop
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Kommentar: Timestamp
    safe_name = f"gutachten_{timestamp}.pdf"  # Kommentar: Safe Name
    pdf_path = os.path.join(EINGANGS_ORDNER, safe_name)  # Kommentar: Zielpfad
    with open(pdf_path, "wb") as f:  # Kommentar: Speichern
        f.write(uploaded_file.getbuffer())  # Kommentar: Bytes speichern
    try:  # Kommentar: Fehler abfangen
        with st.spinner("Analysiere Gutachten mit KI..."):  # Kommentar: Spinner
            pfad_ki = programm_1_ki_input.main(pdf_path, auswahl, steuerstatus)  # Kommentar: Programm 1 starten
            with open(pfad_ki, "r", encoding="utf-8") as f:  # Kommentar: KI-Datei lesen
                ki_text = f.read()  # Kommentar: Text lesen
            daten = programm_2_word_output.json_aus_ki_antwort_parsen(ki_text)  # Kommentar: JSON aus KI parsen
        st.session_state["analysis_ready"] = True  # Kommentar: Flag setzen
        st.session_state["analysis_data"] = daten  # Kommentar: Daten speichern
        st.session_state["analysis_pdf_path"] = pdf_path  # Kommentar: PDF Pfad speichern
        st.session_state["analysis_ki_path"] = pfad_ki  # Kommentar: KI Pfad speichern
        st.session_state["analysis_meta"] = {  # Kommentar: Meta speichern (damit Nutzer nicht “umstellt”)
            "auswahl": auswahl,  # Kommentar: Variante
            "steuerstatus": steuerstatus,  # Kommentar: Steuerstatus
            "vorlage_pfad": vorlage_pfad,  # Kommentar: Vorlagepfad
        }  # Kommentar: Ende Meta
        st.success("Analyse abgeschlossen. Bitte Daten prüfen und korrigieren.")  # Kommentar: Info
    except Exception as e:  # Kommentar: Fehlerfall
        st.error(f"Fehler bei der Analyse: {e}")  # Kommentar: Anzeige
        cleanup_files(pdf_path)  # Kommentar: PDF im Fehlerfall löschen
        st.stop()  # Kommentar: Stop

# ==========================
# Schritt 2: Korrektur + DOCX
# ==========================
if st.session_state.get("analysis_ready"):  # Kommentar: Wenn Analyse vorhanden
    meta = st.session_state.get("analysis_meta", {})  # Kommentar: Meta laden
    st.header("5. Daten prüfen & korrigieren")  # Kommentar: Abschnitt
    st.caption(f"Analyse basiert auf: {meta.get('auswahl','')} | Steuerstatus: {meta.get('steuerstatus','')}")  # Kommentar: Info

    with st.expander("Prompt-Baustein für Programm 1 (SCHADENHERGANG Word-tauglich)"):  # Kommentar: Expander
        st.code(SCHADENHERGANG_WORDTAUGLICH_PROMPT, language="text")  # Kommentar: Prompt anzeigen

    data = dict(st.session_state.get("analysis_data", {}))  # Kommentar: Kopie der Daten

    st.subheader("Wichtige Felder")  # Kommentar: Untertitel

    data["SCHADENSNUMMER"] = st.text_input("Schadensnummer", value=str(data.get("SCHADENSNUMMER", "")))  # Kommentar: Input
    data["AKTENZEICHEN"] = st.text_input("Aktenzeichen", value=str(data.get("AKTENZEICHEN", "")))  # Kommentar: Input
    data["MANDANT_NAME"] = st.text_input("Mandant Name", value=str(data.get("MANDANT_NAME", "")))  # Kommentar: Input
    data["UNFALL_DATUM"] = st.text_input("Unfall Datum (TT.MM.JJJJ)", value=str(data.get("UNFALL_DATUM", "")))  # Kommentar: Input
    data["UNFALL_UHRZEIT"] = st.text_input("Unfall Uhrzeit (HH:MM)", value=str(data.get("UNFALL_UHRZEIT", "")))  # Kommentar: Input
    data["UNFALLORT"] = st.text_input("Unfallort", value=str(data.get("UNFALLORT", "")))  # Kommentar: Input
    data["UNFALL_STRASSE"] = st.text_input("Unfallstraße", value=str(data.get("UNFALL_STRASSE", "")))  # Kommentar: Input
    data["FAHRZEUGTYP"] = st.text_input("Fahrzeugtyp", value=str(data.get("FAHRZEUGTYP", "")))  # Kommentar: Input
    data["KENNZEICHEN"] = st.text_input("Kennzeichen", value=str(data.get("KENNZEICHEN", "")))  # Kommentar: Input

    st.subheader("Schadenshergang (für Word – als Absatz)")  # Kommentar: Untertitel
    data["SCHADENHERGANG"] = st.text_area(  # Kommentar: Textarea für SCHADENHERGANG
        "SCHADENHERGANG",  # Kommentar: Label
        value=str(data.get("SCHADENHERGANG", "")),  # Kommentar: Value
        height=160,  # Kommentar: Höhe
        help="Hier soll ein schreibfertiger, neutraler Absatz stehen (3–6 Sätze). Falls unklar: leer lassen.",  # Kommentar: Hilfe
    )  # Kommentar: Ende Textarea

    st.subheader("Kosten")  # Kommentar: Untertitel

    data["REPARATURKOSTEN"] = st.text_input("Reparaturkosten", value=str(data.get("REPARATURKOSTEN", "")))  # Kommentar: Input
    data["WERTMINDERUNG"] = st.text_input("Wertminderung", value=str(data.get("WERTMINDERUNG", "")))  # Kommentar: Input
    data["KOSTENPAUSCHALE"] = st.text_input("Kostenpauschale", value=str(data.get("KOSTENPAUSCHALE", "")))  # Kommentar: Input
    data["GUTACHTERKOSTEN"] = st.text_input("Gutachterkosten", value=str(data.get("GUTACHTERKOSTEN", "")))  # Kommentar: Input
    data["NUTZUNGSAUSFALL"] = st.text_input("Nutzungsausfall", value=str(data.get("NUTZUNGSAUSFALL", "")))  # Kommentar: Input
    data["MWST_BETRAG"] = st.text_input("MwSt-Betrag (wird je nach Fall ggf. leer)", value=str(data.get("MWST_BETRAG", "")))  # Kommentar: Input

    with st.expander("Alle Felder (optional)"):  # Kommentar: Expander
        skip_keys = {  # Kommentar: Keys, die schon oben gepflegt werden
            "SCHADENSNUMMER", "AKTENZEICHEN", "MANDANT_NAME", "UNFALL_DATUM", "UNFALL_UHRZEIT", "UNFALLORT",
            "UNFALL_STRASSE", "FAHRZEUGTYP", "KENNZEICHEN", "SCHADENHERGANG", "REPARATURKOSTEN", "WERTMINDERUNG",
            "KOSTENPAUSCHALE", "GUTACHTERKOSTEN", "NUTZUNGSAUSFALL", "MWST_BETRAG",
        }  # Kommentar: Ende Skip
        for k in sorted(list(data.keys())):  # Kommentar: Keys sortieren
            if k in skip_keys:  # Kommentar: Skip?
                continue  # Kommentar: Überspringen
            data[k] = st.text_input(f"{k}", value=str(data.get(k, "")))  # Kommentar: Generische Inputs

    st.session_state["analysis_data"] = data  # Kommentar: Zurück in Session speichern

    if st.button("2) Schreiben erzeugen (DOCX)"):  # Kommentar: Schritt 2
        try:  # Kommentar: Fehler abfangen
            with st.spinner("Erzeuge Word-Dokument..."):  # Kommentar: Spinner
                used_meta = st.session_state.get("analysis_meta", {})  # Kommentar: Meta holen
                docx_pfad = generate_docx_from_corrected_data(  # Kommentar: DOCX aus korrigierten Daten erstellen
                    daten=st.session_state["analysis_data"],  # Kommentar: Korrigierte Daten
                    vorlage_pfad=used_meta.get("vorlage_pfad", vorlage_pfad),  # Kommentar: Analyse-Vorlage nutzen
                    auswahl=used_meta.get("auswahl", auswahl),  # Kommentar: Analyse-Variante nutzen
                    steuerstatus=used_meta.get("steuerstatus", steuerstatus),  # Kommentar: Analyse-Steuerstatus nutzen
                    zus_bez=zusatzkosten_bezeichnung,  # Kommentar: Zusatzkosten Name
                    zus_betrag=zusatzkosten_betrag,  # Kommentar: Zusatzkosten Betrag
                )  # Kommentar: Ende call

            with open(docx_pfad, "rb") as f:  # Kommentar: DOCX lesen
                docx_bytes = f.read()  # Kommentar: Bytes lesen

            cleanup_files(st.session_state.get("analysis_pdf_path", ""))  # Kommentar: PDF löschen
            cleanup_files(st.session_state.get("analysis_ki_path", ""))  # Kommentar: KI-Text löschen
            cleanup_files(docx_pfad)  # Kommentar: DOCX auf Server löschen (wir haben Bytes)

            st.session_state["analysis_ready"] = False  # Kommentar: Reset
            st.session_state["analysis_data"] = {}  # Kommentar: Reset
            st.session_state["analysis_meta"] = {}  # Kommentar: Reset
            st.session_state["analysis_pdf_path"] = ""  # Kommentar: Reset
            st.session_state["analysis_ki_path"] = ""  # Kommentar: Reset

            st.download_button(  # Kommentar: Download Button
                label="Erstelltes Anwaltsschreiben herunterladen",  # Kommentar: Label
                data=docx_bytes,  # Kommentar: DOCX Bytes
                file_name="anwaltsschreiben.docx",  # Kommentar: Downloadname
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # Kommentar: MIME
            )  # Kommentar: Ende download
            st.success("Fertig. Dateien wurden gelöscht.")  # Kommentar: Erfolg
        except Exception as e:  # Kommentar: Fehlerfall
            st.error(f"Fehler beim Erzeugen: {e}")  # Kommentar: Anzeige

# ==========================
# Debug: Dateien
# ==========================
with st.expander("Debug: Dateien im System anzeigen"):  # Kommentar: Debug Bereich
    st.subheader("Eingang Gutachten")  # Kommentar: Untertitel
    st.write(os.listdir(EINGANGS_ORDNER))  # Kommentar: Liste anzeigen
    st.subheader("KI-Antworten")  # Kommentar: Untertitel
    st.write(os.listdir(KI_ANTWORT_ORDNER))  # Kommentar: Liste anzeigen
    st.subheader("Ausgang-Schreiben")  # Kommentar: Untertitel
    st.write(os.listdir(AUSGANGS_ORDNER))  # Kommentar: Liste anzeigen

