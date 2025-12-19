# app.py  # Kommentar: Haupt-Streamlit-App für die Gutachten-Automatisierung

import os  # Kommentar: Modul für Pfade und Dateisystem importieren
import json  # Kommentar: Modul für JSON-Serialisierung importieren
import time  # Kommentar: Zeitfunktionen importieren (für Login-Blockierung)
from datetime import datetime  # Kommentar: Datums-/Zeit-Funktion für Dateinamen und Fristen
import streamlit as st  # Kommentar: Streamlit für die Weboberfläche importieren
from docxtpl import DocxTemplate  # Kommentar: DocxTemplate für Platzhalter-Analyse der Vorlagen importieren
import bcrypt  # Kommentar: bcrypt für sicheres Passwort-Hashing importieren

import config  # Kommentar: Eigene Konfiguration mit Pfaden importieren
import programm_1_ki_input  # Kommentar: Modul für KI-Input / PDF-Verarbeitung importieren
import programm_2_word_output  # Kommentar: Modul für Word-Ausgabe / Kostenlogik importieren

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Kommentar: Basisverzeichnis der App bestimmen

EINGANGS_ORDNER = config.EINGANGS_ORDNER  # Kommentar: Eingangsordner für Gutachten aus config übernehmen
KI_ANTWORT_ORDNER = config.KI_ANTWORT_ORDNER  # Kommentar: Ordner für KI-Antworten aus config übernehmen
AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")  # Kommentar: Ordner für fertige Schreiben definieren

os.makedirs(EINGANGS_ORDNER, exist_ok=True)  # Kommentar: Sicherstellen, dass der Eingangsordner existiert
os.makedirs(AUSGANGS_ORDNER, exist_ok=True)  # Kommentar: Sicherstellen, dass der Ausgangsordner existiert
os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)  # Kommentar: Sicherstellen, dass der KI-Antwortordner existiert

st.set_page_config(page_title="Kfz-Gutachten → Anwaltsschreiben", layout="centered")  # Kommentar: Grundkonfiguration für die Streamlit-Seite setzen

USERS_FILE = os.path.join(BASE_DIR, "users.json")  # Kommentar: Pfad zur JSON-Datei, in der Benutzer und Passwort-Hashes gespeichert werden


def _atomic_write_json(path: str, data: dict):  # Kommentar: Hilfsfunktion, um JSON-Dateien atomar zu schreiben
    tmp = path + ".tmp"  # Kommentar: Temporäre Datei mit .tmp-Endung erstellen
    with open(tmp, "w", encoding="utf-8") as f:  # Kommentar: Temporäre Datei zum Schreiben öffnen
        json.dump(data, f, ensure_ascii=False, indent=2)  # Kommentar: JSON-Daten mit UTF-8 und Einrückung schreiben
    os.replace(tmp, path)  # Kommentar: Temporäre Datei atomar durch die Ziel-Datei ersetzen


def load_users() -> dict:  # Kommentar: Benutzer aus der JSON-Datei laden
    if not os.path.isfile(USERS_FILE):  # Kommentar: Prüfen, ob die users.json überhaupt existiert
        return {}  # Kommentar: Wenn nicht, leeres Dict zurückgeben
    try:  # Kommentar: Versuch, JSON-Datei zu lesen
        with open(USERS_FILE, "r", encoding="utf-8") as f:  # Kommentar: users.json im Lesemodus öffnen
            data = json.load(f)  # Kommentar: JSON-Daten einlesen
        if isinstance(data, dict):  # Kommentar: Prüfen, ob es ein Dict ist
            return data  # Kommentar: Eingelesenes Dict zurückgeben
    except Exception:  # Kommentar: Bei Fehlern (defekte Datei etc.) abfangen
        pass  # Kommentar: In diesem Fall einfach unten leeres Dict zurückgeben
    return {}  # Kommentar: Fallback: leeres Dict


def save_users(users: dict):  # Kommentar: Benutzer-Hash-Daten zurück in users.json schreiben
    _atomic_write_json(USERS_FILE, users)  # Kommentar: Hilfsfunktion für atomaren JSON-Schreibvorgang verwenden


def hash_password(plain_password: str) -> str:  # Kommentar: Funktion zum Hashen eines Klartext-Passworts mit bcrypt
    pw_bytes = plain_password.encode("utf-8")  # Kommentar: Passwort in Bytes umwandeln
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())  # Kommentar: bcrypt-Hash mit zufälligem Salt erzeugen
    return hashed.decode("utf-8")  # Kommentar: Hash wieder in String (utf-8) umwandeln und zurückgeben


def check_password(plain_password: str, stored_hash: str) -> bool:  # Kommentar: Funktion zum Prüfen eines Passworts gegen einen gespeicherten Hash
    try:  # Kommentar: Passwortprüfung versuchen
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),  # Kommentar: Eingabepasswort in Bytes konvertieren
            stored_hash.encode("utf-8")  # Kommentar: Gespeicherten Hash in Bytes konvertieren
        )  # Kommentar: Ergebnis der bcrypt-Prüfung zurückgeben (True/False)
    except Exception:  # Kommentar: Bei Fehlern in der Prüfung
        return False  # Kommentar: Sicherheitshalber False zurückgeben


def valid_username(name: str) -> bool:  # Kommentar: Funktion zur Validierung eines Benutzernamens
    if not name or len(name) < 3 or len(name) > 32:  # Kommentar: Länge prüfen (3–32 Zeichen)
        return False  # Kommentar: Ungültig, wenn Länge nicht passt
    for ch in name:  # Kommentar: Jeden Buchstaben im Namen durchgehen
        if not (ch.isalnum() or ch in ["_", "-"]):  # Kommentar: Nur Buchstaben, Ziffern, Unterstrich und Minus erlauben
            return False  # Kommentar: Ungültig, wenn ein anderes Zeichen vorkommt
    return True  # Kommentar: Wenn alles passt, True zurückgeben


def valid_password(pw: str) -> bool:  # Kommentar: Funktion zur einfachen Passwort-Validierung
    return isinstance(pw, str) and len(pw) >= 10  # Kommentar: Mindestlänge 10 Zeichen, Typ muss String sein


VORLAGEN = {  # Kommentar: Mapping von Abrechnungsvarianten zu den jeweiligen Word-Vorlagendateien
    "Fiktive Abrechnung (Reparaturschaden)": "vorlage_fiktive_abrechnung.docx",  # Kommentar: Vorlage für fiktive Reparaturabrechnung
    "Konkrete Abrechnung < WBW": "vorlage_konkret_unter_wbw.docx",  # Kommentar: Vorlage für konkrete Abrechnung unterhalb WBW
    "130%-Regelung": "vorlage_130_prozent.docx",  # Kommentar: Vorlage für die 130%-Regelung
    "Totalschaden fiktiv": "vorlage_totalschaden_fiktiv.docx",  # Kommentar: Vorlage für fiktiven Totalschaden
    "Totalschaden konkret": "vorlage_totalschaden_konkret.docx",  # Kommentar: Vorlage für konkreten Totalschaden
    "Totalschaden Ersatzbeschaffung": "vorlage_totalschaden_ersatzbeschaffung.docx",  # Kommentar: Vorlage für Totalschaden mit Ersatzbeschaffung
}


def cleanup_files(*paths: str):  # Kommentar: Hilfsfunktion zum Aufräumen (Dateien löschen)
    for path in paths:  # Kommentar: Über alle übergebenen Pfade iterieren
        if path and os.path.exists(path):  # Kommentar: Prüfen, ob Pfad gesetzt ist und Datei existiert
            try:  # Kommentar: Versuch, die Datei zu löschen
                os.remove(path)  # Kommentar: Datei löschen
                print(f"Gelöscht: {path}")  # Kommentar: Löschbestätigung ins Log schreiben
            except OSError as e:  # Kommentar: OS-Fehler abfangen
                print(f"Fehler beim Löschen von {path}: {e}")  # Kommentar: Fehler im Log ausgeben


def extrahiere_platzhalter(vorlage_pfad):  # Kommentar: Platzhalter aus einer Word-Vorlage extrahieren (nur für Debug oder Kontrolle)
    doc = DocxTemplate(vorlage_pfad)  # Kommentar: Vorlage mit DocxTemplate öffnen
    return doc.get_undeclared_template_variables()  # Kommentar: Set der Platzhalter zurückgeben


def resolve_vorlage_pfad(auswahl: str) -> str:  # Kommentar: Funktion, um aus der Auswahl den tatsächlichen Vorlagen-Dateipfad zu bestimmen
    if auswahl not in VORLAGEN:  # Kommentar: Prüfen, ob die Auswahl im VORLAGEN-Dict existiert
        raise ValueError(f"Unbekannte Auswahl: {auswahl}")  # Kommentar: Fehlermeldung für unbekannte Vorlage

    dateiname = VORLAGEN[auswahl]  # Kommentar: Dateinamen aus dem Mapping holen

    if getattr(config, "VORLAGEN_ORDNER", None):  # Kommentar: Prüfen, ob in config ein VORLAGEN_ORDNER definiert ist
        pfad1 = os.path.join(config.VORLAGEN_ORDNER, dateiname)  # Kommentar: Pfad im Vorlagen-Ordner zusammensetzen
        if os.path.isfile(pfad1):  # Kommentar: Prüfen, ob diese Datei existiert
            return pfad1  # Kommentar: Pfad aus dem Vorlagenordner zurückgeben

    pfad2 = os.path.join(BASE_DIR, dateiname)  # Kommentar: Fallback – Datei direkt im Basisverzeichnis suchen
    if os.path.isfile(pfad2):  # Kommentar: Prüfen, ob Datei dort existiert
        return pfad2  # Kommentar: Fallback-Pfad zurückgeben

    if os.path.isabs(dateiname) and os.path.isfile(dateiname):  # Kommentar: Prüfen, ob der Eintrag bereits ein absoluter Pfad ist und existiert
        return dateiname  # Kommentar: Absoluten Pfad zurückgeben

    raise FileNotFoundError(f"Vorlage nicht gefunden: {dateiname}")  # Kommentar: Fehlermeldung, falls nichts gefunden wurde


if "logged_in" not in st.session_state:  # Kommentar: Check, ob Login-Status bereits in der Session gespeichert ist
    st.session_state["logged_in"] = False  # Kommentar: Initial: niemand ist eingeloggt
    st.session_state["username"] = None  # Kommentar: Benutzernamen in der Session auf None setzen

if "login_fail_count" not in st.session_state:  # Kommentar: Zähler für Fehlversuche initialisieren
    st.session_state["login_fail_count"] = 0  # Kommentar: Fehlversuche beginnen bei 0
if "login_block_until" not in st.session_state:  # Kommentar: Zeitstempel für Login-Block initialisieren
    st.session_state["login_block_until"] = 0.0  # Kommentar: Standard: kein Block aktiv


def is_blocked_now() -> bool:  # Kommentar: Prüfen, ob gerade eine Login-Blockade aktiv ist
    return time.time() < float(st.session_state.get("login_block_until", 0.0))  # Kommentar: True, wenn aktuelle Zeit vor block_until liegt


def register_user(username: str, pw: str) -> tuple[bool, str]:  # Kommentar: Funktion zur Registrierung eines neuen Benutzers
    users = load_users()  # Kommentar: Bestehende Benutzer laden

    if not valid_username(username):  # Kommentar: Prüfen, ob der Benutzername gültig ist
        return False, "Benutzername ungültig (3–32 Zeichen, nur a-z A-Z 0-9 _ -)."  # Kommentar: Fehlertext bei ungültigem Namen

    if username in users:  # Kommentar: Prüfen, ob der Benutzername bereits existiert
        return False, "Benutzername existiert bereits."  # Kommentar: Fehlertext bei bereits vorhandenem Benutzer

    if not valid_password(pw):  # Kommentar: Prüfen, ob das Passwort den Regeln entspricht
        return False, "Passwort zu kurz (mindestens 10 Zeichen)."  # Kommentar: Fehlertext bei zu kurzem Passwort

    users[username] = hash_password(pw)  # Kommentar: Hash des Passworts erzeugen und unter dem Usernamen speichern
    save_users(users)  # Kommentar: Benutzerliste mit neuem User speichern
    return True, "Registrierung erfolgreich. Du kannst dich jetzt einloggen."  # Kommentar: Erfolgsmeldung zurückgeben


def login_user(username: str, pw: str) -> tuple[bool, str]:  # Kommentar: Funktion zum Einloggen eines Benutzers
    if is_blocked_now():  # Kommentar: Prüfen, ob gerade wegen Fehlversuchen blockiert wird
        sek = int(st.session_state["login_block_until"] - time.time())  # Kommentar: Verbleibende Sekunden der Blockade berechnen
        return False, f"Zu viele Fehlversuche. Bitte {sek}s warten."  # Kommentar: Hinweis an den Benutzer zurückgeben

    users = load_users()  # Kommentar: Benutzerliste laden
    stored_hash = users.get(username)  # Kommentar: Gespeicherten Hash für diesen Benutzernamen holen

    if not stored_hash or not check_password(pw, stored_hash):  # Kommentar: Prüfen, ob User existiert und Passwort korrekt ist
        st.session_state["login_fail_count"] += 1  # Kommentar: Fehlversuchszähler erhöhen
        if st.session_state["login_fail_count"] >= 5:  # Kommentar: Wenn mindestens 5 Fehlversuche
            st.session_state["login_block_until"] = time.time() + 30  # Kommentar: Login für 30 Sekunden blockieren
            st.session_state["login_fail_count"] = 0  # Kommentar: Fehlversuchszähler zurücksetzen
        return False, "Benutzername oder Passwort falsch."  # Kommentar: Generische Fehlermeldung ohne zu verraten, was falsch war

    st.session_state["login_fail_count"] = 0  # Kommentar: Fehlversuche zurücksetzen
    st.session_state["login_block_until"] = 0.0  # Kommentar: Blockierungszeit zurücksetzen
    st.session_state["logged_in"] = True  # Kommentar: Benutzer als eingeloggt markieren
    st.session_state["username"] = username  # Kommentar: Benutzernamen in der Session speichern
    return True, "Login erfolgreich."  # Kommentar: Erfolgsmeldung zurückgeben


if not st.session_state["logged_in"]:  # Kommentar: Wenn noch niemand eingeloggt ist, Login-/Registriermaske anzeigen
    st.title("Zugang geschützt")  # Kommentar: Überschrift für den Loginbereich setzen

    users = load_users()  # Kommentar: Aktuelle Benutzerliste laden
    allow_registration = True  # Kommentar: Standard: Registrierung ist erlaubt

    EINMALIGE_REGISTRIERUNG_GLOBAL = False  # Kommentar: Konfiguration, ob Registrierung nur einmal global erlaubt ist
    if EINMALIGE_REGISTRIERUNG_GLOBAL and len(users) > 0:  # Kommentar: Falls einmalige Registrierung aktiv und bereits Nutzer vorhanden
        allow_registration = False  # Kommentar: Registrierung deaktivieren

    mode = st.radio(  # Kommentar: Radiobutton für Auswahl zwischen Login und Registrierung
        "Aktion",  # Kommentar: Label für die Radiobutton-Gruppe
        options=["Login", "Registrieren"] if allow_registration else ["Login"],  # Kommentar: Optionen abhängig von allow_registration
        horizontal=True  # Kommentar: Radiobuttons horizontal anzeigen
    )

    username = st.text_input("Benutzername")  # Kommentar: Eingabefeld für Benutzernamen anzeigen
    pw = st.text_input("Passwort", type="password")  # Kommentar: Eingabefeld für Passwort (versteckt) anzeigen

    if mode == "Registrieren":  # Kommentar: Wenn der Benutzer "Registrieren" gewählt hat
        pw2 = st.text_input("Passwort wiederholen", type="password")  # Kommentar: Eingabefeld zur Passwort-Wiederholung
        register_clicked = st.button("Registrieren")  # Kommentar: Button, um Registrierung auszulösen

        if register_clicked:  # Kommentar: Wenn der Registrieren-Button gedrückt wurde
            if pw != pw2:  # Kommentar: Prüfen, ob die beiden Passwörter übereinstimmen
                st.error("Passwörter stimmen nicht überein.")  # Kommentar: Fehlermeldung anzeigen
                st.stop()  # Kommentar: Weitere Verarbeitung stoppen

            ok, msg = register_user(username.strip(), pw)  # Kommentar: Versuch, Benutzer zu registrieren
            if ok:  # Kommentar: Wenn Registrierung erfolgreich
                st.success(msg)  # Kommentar: Erfolgsmeldung anzeigen
            else:  # Kommentar: Wenn Registrierung fehlgeschlagen ist
                st.error(msg)  # Kommentar: Fehlermeldung anzeigen
        st.stop()  # Kommentar: Bei Registriermodus hier abbrechen, um kein Login mehr anzuzeigen

    login_clicked = st.button("Login")  # Kommentar: Button, um den Login-Vorgang auszulösen
    if login_clicked:  # Kommentar: Wenn Login-Button gedrückt wurde
        ok, msg = login_user(username.strip(), pw)  # Kommentar: Login-Versuch starten
        if ok:  # Kommentar: Wenn Login erfolgreich
            st.rerun()  # Kommentar: Seite neu laden, jetzt im eingeloggten Zustand
        else:  # Kommentar: Wenn Login fehlgeschlagen
            st.error(msg)  # Kommentar: Fehlermeldung anzeigen
            st.stop()  # Kommentar: Verarbeitung beenden
    else:  # Kommentar: Wenn Login-Button noch nicht gedrückt wurde
        st.stop()  # Kommentar: Keine App-Inhalte anzeigen, bis Login-Action erfolgt ist


st.title(f"Kfz-Gutachten Automatisierung - Eingeloggt als {st.session_state['username']}")  # Kommentar: Haupttitel mit Anzeige des eingeloggten Benutzers

if st.button("Logout"):  # Kommentar: Logout-Button anzeigen
    st.session_state["logged_in"] = False  # Kommentar: Login-Status zurücksetzen
    st.session_state["username"] = None  # Kommentar: Benutzernamen zurücksetzen
    st.rerun()  # Kommentar: Seite neu laden, wieder im Loginmodus


st.header("1. Abrechnungsvariante / Vorlage wählen")  # Kommentar: Abschnittsüberschrift für die Vorlagenauswahl
auswahl = st.selectbox("Welche Variante möchten Sie verwenden?", list(VORLAGEN.keys()))  # Kommentar: Dropdown mit allen Abrechnungsvarianten anzeigen
try:  # Kommentar: Versuch, den tatsächlichen Vorlagenpfad zu ermitteln
    vorlage_pfad = resolve_vorlage_pfad(auswahl)  # Kommentar: Pfad zur ausgewählten Word-Vorlage bestimmen
except Exception as e:  # Kommentar: Fehler beim Auflösen des Vorlagenpfads abfangen
    st.error(f"Vorlagenfehler: {e}")  # Kommentar: Fehlermeldung in der UI anzeigen
    st.stop()  # Kommentar: Verarbeitung abbrechen, weil ohne Vorlage nichts geht

st.caption(f"Verwendete Vorlage-Datei: {os.path.basename(vorlage_pfad)}")  # Kommentar: Name der verwendeten Vorlagendatei anzeigen


st.header("2. Steuerstatus (relevant für MwSt / Totalschaden)")  # Kommentar: Abschnittsüberschrift für den Steuerstatus
steuerstatus = st.selectbox(  # Kommentar: Dropdown zur Auswahl des Steuerstatus
    "Steuerstatus des Geschädigten",  # Kommentar: Label für das Dropdown
    ["nicht vorsteuerabzugsberechtigt", "vorsteuerabzugsberechtigt"],  # Kommentar: Mögliche Auswahloptionen
    index=0  # Kommentar: Standardauswahl: "nicht vorsteuerabzugsberechtigt"
)


st.header("3. Optional: Zusatzkosten")  # Kommentar: Abschnittsüberschrift für optionale Zusatzkosten
zusatzkosten_bezeichnung = st.text_input("Bezeichnung (optional)", value="")  # Kommentar: Textfeld für die Bezeichnung der Zusatzkosten
zusatzkosten_betrag = st.text_input("Betrag in Euro (optional, z.B. 25,00)", value="")  # Kommentar: Textfeld für den Betrag der Zusatzkosten in Euro


st.header("4. Gutachten hochladen, verarbeiten und Schreiben herunterladen")  # Kommentar: Abschnittsüberschrift für den Upload und die Verarbeitung
uploaded_file = st.file_uploader("Gutachten als PDF hochladen", type=["pdf"])  # Kommentar: Upload-Feld für PDF-Gutachten anzeigen

if st.button("Gutachten verarbeiten"):  # Kommentar: Button, um die Verarbeitung zu starten
    if uploaded_file is None:  # Kommentar: Prüfen, ob keine Datei hochgeladen wurde
        st.error("Bitte zuerst eine PDF-Datei hochladen.")  # Kommentar: Fehlermeldung anzeigen
        st.stop()  # Kommentar: Verarbeitung abbrechen

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Kommentar: Zeitstempel für Dateinamen erzeugen
    safe_name = f"gutachten_{timestamp}.pdf"  # Kommentar: Dateinamen für das hochgeladene Gutachten generieren
    pdf_path = os.path.join(EINGANGS_ORDNER, safe_name)  # Kommentar: Vollständigen Pfad für die gespeicherte PDF-Datei bestimmen

    try:  # Kommentar: Versuch, die hochgeladene Datei zu speichern
        with open(pdf_path, "wb") as f:  # Kommentar: Datei im Binärmodus zum Schreiben öffnen
            f.write(uploaded_file.getbuffer())  # Kommentar: Inhalt der hochgeladenen Datei in die lokale Datei schreiben
    except Exception as e:  # Kommentar: Fehler beim Speichern abfangen
        st.error(f"Fehler beim Speichern der PDF-Datei: {e}")  # Kommentar: Fehlermeldung anzeigen
        st.stop()  # Kommentar: Verarbeitung abbrechen

    st.info(f"PDF gespeichert als: {safe_name}")  # Kommentar: Info anzeigen, unter welchem Namen die Datei gespeichert wurde

    try:  # Kommentar: Gesamten Verarbeitungsprozess in Try-Block kapseln
        with st.spinner("Verarbeite Gutachten mit KI..."):  # Kommentar: Spinner anzeigen, solange die Verarbeitung läuft
            pfad_ki = programm_1_ki_input.main(pdf_path, auswahl, steuerstatus)  # Kommentar: Programm 1 aufrufen: PDF auslesen, KI anfragen, Antwort speichern

            if pfad_ki is None or not os.path.isfile(pfad_ki):  # Kommentar: Prüfen, ob eine gültige KI-Antwortdatei existiert
                raise RuntimeError("Programm 1 hat keine gültige KI-Antwort erzeugt.")  # Kommentar: Fehler werfen, wenn KI-Output fehlt

            docx_pfad = programm_2_word_output.main(  # Kommentar: Programm 2 aufrufen, um Word-Schreiben zu erzeugen
                pfad_ki,  # Kommentar: Pfad zur KI-Antwortdatei
                vorlage_pfad,  # Kommentar: Pfad zur ausgewählten Word-Vorlage
                auswahl,  # Kommentar: Abrechnungsvariante an Programm 2 übergeben
                steuerstatus,  # Kommentar: Steuerstatus an Programm 2 übergeben
                zusatzkosten_bezeichnung,  # Kommentar: Zusatzkosten-Bezeichnung an Programm 2 übergeben
                zusatzkosten_betrag,  # Kommentar: Zusatzkosten-Betrag an Programm 2 übergeben
            )

            if docx_pfad is None or not os.path.isfile(docx_pfad):  # Kommentar: Prüfen, ob Programm 2 ein Schreiben erzeugt hat
                raise RuntimeError("Programm 2 hat kein Schreiben erzeugt.")  # Kommentar: Fehler werfen, wenn keine DOCX erzeugt wurde

        with open(docx_pfad, "rb") as f:  # Kommentar: Fertige Word-Datei im Binärmodus öffnen
            docx_bytes = f.read()  # Kommentar: Inhalt der Word-Datei in den Speicher lesen

        cleanup_files(pdf_path, pfad_ki, docx_pfad)  # Kommentar: PDF, KI-Text und DOCX-Datei vom Server wieder löschen

        st.success("Verarbeitung abgeschlossen.")  # Kommentar: Erfolgsmeldung anzeigen
        st.success("Die Dateien wurden nach der Verarbeitung vom Server gelöscht.")  # Kommentar: Hinweis zur Datenlöschung anzeigen

        st.download_button(  # Kommentar: Download-Button für das fertige Anwaltsschreiben anzeigen
            label="Erstelltes Anwaltsschreiben herunterladen",  # Kommentar: Beschriftung des Buttons
            data=docx_bytes,  # Kommentar: Binärdaten der Word-Datei
            file_name=os.path.basename(docx_pfad),  # Kommentar: Dateiname für den Download
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # Kommentar: MIME-Typ für DOCX
        )

    except Exception as e:  # Kommentar: Alle Fehler im Prozess abfangen
        st.error(f"Fehler bei der Verarbeitung: {e}")  # Kommentar: Fehlermeldung anzeigen


with st.expander("Debug: Dateien im System anzeigen"):  # Kommentar: Debug-Bereich als aufklappbares Element
    st.subheader("Eingang Gutachten")  # Kommentar: Überschrift für Eingangsordner
    st.write(os.listdir(EINGANGS_ORDNER))  # Kommentar: Alle Dateien im Eingangsordner anzeigen
    st.subheader("KI-Antworten")  # Kommentar: Überschrift für KI-Antwort-Ordner
    st.write(os.listdir(KI_ANTWORT_ORDNER))  # Kommentar: Alle Dateien im KI-Antwortordner anzeigen
    st.subheader("Ausgang-Schreiben")  # Kommentar: Überschrift für Ausgangsschreiben-Ordner
    st.write(os.listdir(AUSGANGS_ORDNER))  # Kommentar: Alle Dateien im Ausgangsordner anzeigen
    st.subheader("Debug: aktuelle Auswahl")  # Kommentar: Überschrift für Debug-Infos zur aktuellen Auswahl
    st.write({  # Kommentar: Aktuelle Auswahl und Steuerstatus als Dict anzeigen
        "auswahl": auswahl,
        "vorlage": os.path.basename(vorlage_pfad) if vorlage_pfad else None,
        "steuerstatus": steuerstatus,
    })
    st.subheader("Debug: registrierte User (nur Usernames)")  # Kommentar: Überschrift für Benutzerliste
    st.write(sorted(list(load_users().keys())))  # Kommentar: Alphabetisch sortierte Liste der registrierten Benutzernamen anzeigen
