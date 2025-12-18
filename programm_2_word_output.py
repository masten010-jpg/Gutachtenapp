# programm_2_word_output.py
import os
import json
from datetime import datetime, timedelta
from docxtpl import DocxTemplate
from programm_1_ki_input import KI_ANTWORT_ORDNER, BASE_DIR

AUSGANGS_ORDNER = os.path.join(BASE_DIR, "ausgang_schreiben")
JSON_START_MARKER = "JSON_START"
JSON_END_MARKER = "JSON_END"


def json_aus_ki_antwort_parsen(ki_text: str) -> dict:
    start_idx = ki_text.find(JSON_START_MARKER)
    end_idx = ki_text.find(JSON_END_MARKER)
    if start_idx == -1 or end_idx == -1:
        raise ValueError("JSON_START oder JSON_END nicht gefunden.")

    json_roh = ki_text[start_idx + len(JSON_START_MARKER):end_idx].strip()
    json_roh = json_roh.replace("```json", "").replace("```", "").strip()

    first_brace = json_roh.find("{")
    last_brace = json_roh.rfind("}")
    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
        raise ValueError("Kein gültiger JSON-Block in KI-Antwort.")

    json_clean = json_roh[first_brace:last_brace + 1]
    json_clean = json_clean.replace(",\n}", "\n}").replace(",}", "}")
    return json.loads(json_clean)


def euro_zu_float(text) -> float:
    if isinstance(text, (int, float)):
        return float(text)
    if not text:
        return 0.0

    t = str(text)
    t = t.replace("€", "").replace("EUR", "").replace("Euro", "")
    t = t.replace("\u00a0", " ").strip()
    t = t.replace(" ", "")

    filtered = []
    for ch in t:
        if ch.isdigit() or ch in [",", ".", "+", "-"]:
            filtered.append(ch)
    t = "".join(filtered)

    if not t:
        return 0.0

    if "." in t and "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")

    try:
        return float(t)
    except ValueError:
        return 0.0


def float_zu_euro(betrag: float) -> str:
    s = f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"


def extrahiere_platzhalter(vorlage_pfad):
    doc = DocxTemplate(vorlage_pfad)
    return doc.get_undeclared_template_variables()


def baue_totalschaden(daten, platzhalter):
    """
    Alte Hilfsfunktion aus deiner ersten Version – wir lassen sie drin,
    falls du sie später wieder direkt brauchst.
    Für die neue Logik nutzen wir aber 'anwenden_abrechnungslogik'.
    """
    if "WIEDERBESCHAFFUNGSWERTAUFWAND" in platzhalter:
        wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", 0))
        restwert = euro_zu_float(daten.get("RESTWERT", 0))
        wiederbeschaffungsaufwand = wbw - restwert
        daten["WIEDERBESCHAFFUNGSWERTAUFWAND"] = float_zu_euro(wiederbeschaffungsaufwand)
    return daten


def daten_defaults(daten: dict):
    keys = [
        "MANDANT_VORNAME", "MANDANT_NACHNAME", "MANDANT_NAME",
        "MANDANT_STRASSE", "MANDANT_PLZ_ORT",
        "UNFALL_DATUM", "UNFALL_UHRZEIT", "UNFALLORT", "UNFALL_STRASSE",
        "FAHRZEUGTYP", "KENNZEICHEN", "FAHRZEUG_KENNZEICHEN",
        "POLIZEIAKTE_NUMMER", "SCHADENSNUMMER", "AKTENZEICHEN",
        "SCHADENHERGANG",
        "REPARATURKOSTEN", "WERTMINDERUNG", "KOSTENPAUSCHALE",
        "GUTACHTERKOSTEN", "NUTZUNGSAUSFALL", "MWST_BETRAG",
        "WIEDERBESCHAFFUNGSWERT", "RESTWERT",
        "FRIST_DATUM", "HEUTDATUM",
        # neue Felder:
        "ABRECHNUNGSART", "STEUERSTATUS",
        "WIEDERBESCHAFFUNGSAUFWAND",
        "ERSATZBESCHAFFUNG_MWST",
        "ZUSATZKOSTEN_BEZEICHNUNG", "ZUSATZKOSTEN_BETRAG",
        "KOSTENSUMME_X", "GESAMTSUMME",
    ]
    for k in keys:
        daten.setdefault(k, "")
    return daten


def anwenden_abrechnungslogik(daten: dict, auswahl: str, steuerstatus: str):
    daten["ABRECHNUNGSART"] = auswahl
    daten["STEUERSTATUS"] = steuerstatus

    reparatur = euro_zu_float(daten.get("REPARATURKOSTEN", ""))
    wertminderung = euro_zu_float(daten.get("WERTMINDERUNG", ""))
    kostenpausch = euro_zu_float(daten.get("KOSTENPAUSCHALE", ""))
    gutachter = euro_zu_float(daten.get("GUTACHTERKOSTEN", ""))
    nutzung = euro_zu_float(daten.get("NUTZUNGSAUSFALL", ""))
    mwst = euro_zu_float(daten.get("MWST_BETRAG", ""))

    wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))
    restwert = euro_zu_float(daten.get("RESTWERT", ""))

    zus_betrag = euro_zu_float(daten.get("ZUSATZKOSTEN_BETRAG", ""))

    # 130%-Regelung -> keine Wertminderung
    if auswahl == "130%-Regelung":
        daten["WERTMINDERUNG"] = ""
        wertminderung = 0.0

    # Totalschaden-Logik
    if auswahl in ["Totalschaden fiktiv", "Totalschaden konkret", "Totalschaden Ersatzbeschaffung"]:
        wba = max(wbw - restwert, 0.0)  # Wiederbeschaffungsaufwand
        daten["WIEDERBESCHAFFUNGSAUFWAND"] = float_zu_euro(wba) if (wbw or restwert) else ""

        reparatur = 0.0  # Totalschaden -> nicht reparaturbasiert
        kostenbasis = wba

        ersatz_mwst = 0.0
        if auswahl in ["Totalschaden konkret", "Totalschaden Ersatzbeschaffung"]:
            ersatz_mwst = mwst
            daten["ERSATZBESCHAFFUNG_MWST"] = float_zu_euro(ersatz_mwst) if ersatz_mwst else ""
        else:
            daten["ERSATZBESCHAFFUNG_MWST"] = ""

        if steuerstatus == "vorsteuerabzugsberechtigt":
            mwst_anzurechnen = 0.0
        else:
            mwst_anzurechnen = ersatz_mwst if ersatz_mwst else 0.0

        gesamt = kostenbasis + mwst_anzurechnen + kostenpausch + gutachter + nutzung + zus_betrag

        daten["REPARATURKOSTEN"] = ""
        daten["MWST_BETRAG"] = float_zu_euro(mwst) if mwst else ""
        daten["KOSTENPAUSCHALE"] = float_zu_euro(kostenpausch) if kostenpausch else ""
        daten["GUTACHTERKOSTEN"] = float_zu_euro(gutachter) if gutachter else ""
        daten["NUTZUNGSAUSFALL"] = float_zu_euro(nutzung) if nutzung else ""
        daten["KOSTENSUMME_X"] = float_zu_euro(kostenpausch + gutachter + nutzung + zus_betrag)
        daten["GESAMTSUMME"] = float_zu_euro(gesamt)
        return daten

    # Reparaturschäden: Fiktiv / Konrekt < WBW / 130%
    if auswahl == "Fiktive Abrechnung (Reparaturschaden)":
        daten["MWST_BETRAG"] = ""  # keine MwSt bei fiktiv
    elif auswahl == "Konkrete Abrechnung < WBW":
        daten["MWST_BETRAG"] = float_zu_euro(mwst) if mwst else ""
    elif auswahl == "130%-Regelung":
        daten["MWST_BETRAG"] = float_zu_euro(mwst) if mwst else ""

    daten["REPARATURKOSTEN"] = float_zu_euro(reparatur) if reparatur else (daten.get("REPARATURKOSTEN", "") or "")
    daten["WERTMINDERUNG"] = float_zu_euro(wertminderung) if wertminderung else (daten.get("WERTMINDERUNG", "") or "")
    daten["KOSTENPAUSCHALE"] = float_zu_euro(kostenpausch) if kostenpausch else (daten.get("KOSTENPAUSCHALE", "") or "")
    daten["GUTACHTERKOSTEN"] = float_zu_euro(gutachter) if gutachter else (daten.get("GUTACHTERKOSTEN", "") or "")
    daten["NUTZUNGSAUSFALL"] = float_zu_euro(nutzung) if nutzung else (daten.get("NUTZUNGSAUSFALL", "") or "")

    kosten_x = reparatur + wertminderung + kostenpausch + gutachter + nutzung + zus_betrag
    daten["KOSTENSUMME_X"] = float_zu_euro(kosten_x) if kosten_x else ""
    daten["GESAMTSUMME"] = daten["KOSTENSUMME_X"]

    return daten


def daten_nachbearbeiten(
    daten: dict,
    platzhalter,
    auswahl: str,
    steuerstatus: str,
    zus_bez: str,
    zus_betrag: str
):
    daten = daten_defaults(daten)

    daten["ZUSATZKOSTEN_BEZEICHNUNG"] = (zus_bez or "").strip()
    daten["ZUSATZKOSTEN_BETRAG"] = (zus_betrag or "").strip()

    jetzt = datetime.now()
    daten["FRIST_DATUM"] = (jetzt + timedelta(days=14)).strftime("%d.%m.%Y")
    daten["HEUTDATUM"] = jetzt.strftime("%d.%m.%Y")

    daten = anwenden_abrechnungslogik(daten, auswahl, steuerstatus)

    # optionale Zusatzberechnung, falls Vorlage WIEDERBESCHAFFUNGSAUFWAND erwartet
    if "WIEDERBESCHAFFUNGSAUFWAND" in platzhalter and not daten.get("WIEDERBESCHAFFUNGSAUFWAND"):
        wbw = euro_zu_float(daten.get("WIEDERBESCHAFFUNGSWERT", ""))
        rest = euro_zu_float(daten.get("RESTWERT", ""))
        if wbw or rest:
            daten["WIEDERBESCHAFFUNGSAUFWAND"] = float_zu_euro(max(wbw - rest, 0.0))

    return daten


def word_aus_vorlage_erstellen(daten: dict, vorlage_pfad: str, ziel_pfad: str):
    doc = DocxTemplate(vorlage_pfad)
    platzhalter = doc.get_undeclared_template_variables()
    daten_fuer_vorlage = {k: v for k, v in daten.items() if k in platzhalter}
    os.makedirs(os.path.dirname(ziel_pfad), exist_ok=True)
    doc.render(daten_fuer_vorlage)
    doc.save(ziel_pfad)


def ki_datei_verarbeiten(
    pfad_ki_txt: str,
    vorlage_pfad: str,
    auswahl: str,
    steuerstatus: str,
    zus_bez: str,
    zus_betrag: str
) -> str:
    with open(pfad_ki_txt, "r", encoding="utf-8") as f:
        ki_text = f.read()

    daten = json_aus_ki_antwort_parsen(ki_text)
    platzhalter = extrahiere_platzhalter(vorlage_pfad)
    daten = daten_nachbearbeiten(daten, platzhalter, auswahl, steuerstatus, zus_bez, zus_betrag)

    basisname = os.path.splitext(os.path.basename(pfad_ki_txt))[0]
    datum_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    ausgabe_name = f"{basisname}_schreiben_{datum_str}.docx"
    ausgabe_pfad = os.path.join(AUSGANGS_ORDNER, ausgabe_name)

    word_aus_vorlage_erstellen(daten, vorlage_pfad, ausgabe_pfad)
    return ausgabe_pfad


def main(
    pfad_ki_txt: str = None,
    vorlage_pfad: str | None = None,
    auswahl: str = "",
    steuerstatus: str = "",
    zus_bez: str = "",
    zus_betrag: str = ""
) -> str:
    os.makedirs(KI_ANTWORT_ORDNER, exist_ok=True)
    os.makedirs(AUSGANGS_ORDNER, exist_ok=True)

    if vorlage_pfad is None:
        raise ValueError("vorlage_pfad muss übergeben werden (Word-Vorlage .docx).")

    if pfad_ki_txt is None:
        dateien = [
            os.path.join(KI_ANTWORT_ORDNER, f)
            for f in os.listdir(KI_ANTWORT_ORDNER)
            if f.endswith("_ki.txt")
        ]
        if not dateien:
            raise FileNotFoundError("Keine KI-Datei gefunden.")
        pfad_ki_txt = max(dateien, key=os.path.getmtime)

    if not os.path.isfile(pfad_ki_txt):
        raise FileNotFoundError(f"KI-Datei existiert nicht: {pfad_ki_txt}")

    if not os.path.isfile(vorlage_pfad):
        raise FileNotFoundError(f"Vorlage existiert nicht: {vorlage_pfad}")

    return ki_datei_verarbeiten(pfad_ki_txt, vorlage_pfad, auswahl, steuerstatus, zus_bez, zus_betrag)


if __name__ == "__main__":
    main()
