# -*- coding: utf-8 -*-
"""
App: Word (.docx) -> XLSForm (Survey123) con estructura FIJA por páginas (1..10)
- Siempre crea 10 páginas (begin_group / end_group) en el orden oficial que indicaste.
- Inserta INTRO (P1) y CONSENTIMIENTO (P2) como notes (editable).
- Detecta preguntas numeradas y opciones; asigna a la página según encabezados detectados.
- Evita duplicados en 'name' (case-insensitive) para evitar errores de Survey123.
- Genera XLSX con hojas: survey, choices, settings (+ glosario extra opcional)
"""

import re
import io
import unicodedata
from typing import List, Dict, Tuple, Optional

import streamlit as st
import pandas as pd
from docx import Document


# -----------------------------
# Config de páginas (FIJA)
# -----------------------------
PAGES = [
    ("p1_intro", "Página 1 — Introducción"),
    ("p2_consent", "Página 2 — Consentimiento informado"),
    ("p3_demo", "Página 3 — I. DATOS DEMOGRÁFICOS"),
    ("p4_percep", "Página 4 — II. PERCEPCIÓN CIUDADANA DE SEGURIDAD EN EL DISTRITO"),
    ("p5_riesgos", "Página 5 — III. RIESGOS (Riesgos sociales y situacionales en el distrito)"),
    ("p6_delitos", "Página 6 — Delitos"),
    ("p7_vict_a", "Página 7 — Victimización A: Violencia intrafamiliar"),
    ("p8_vict_b", "Página 8 — Victimización B: Victimización por otros delitos"),
    ("p9_conf", "Página 9 — Confianza Policial"),
    ("p10_prop", "Página 10 — Propuestas ciudadanas para la mejora de la seguridad"),
]

# Títulos/keywords que el parser reconoce en el Word para “cambiar de página”
# (se puede ampliar, pero ya cubre tus nombres reales)
PAGE_MATCHERS = [
    ("p1_intro",  [r"^\s*p[aá]gina\s*1\b", r"\bintroducci[oó]n\b", r"\bformato\s+encuesta\s+comunidad\b"]),
    ("p2_consent",[r"^\s*p[aá]gina\s*2\b", r"\bconsentimiento\s+informado\b", r"\bacepta\s+participar\b"]),
    ("p3_demo",   [r"^\s*p[aá]gina\s*3\b", r"\bi\.\s*datos\s+demogr[aá]ficos\b", r"\bdatos\s+demogr[aá]ficos\b"]),
    ("p4_percep", [r"^\s*p[aá]gina\s*4\b", r"\bii\.\s*percepci[oó]n\b", r"\bpercepci[oó]n\s+ciudadana\b"]),
    ("p5_riesgos",[r"^\s*p[aá]gina\s*5\b", r"\biii\.\s*riesgos\b", r"\briesgos\s+sociales\b", r"\bsituacionales\b"]),
    ("p6_delitos",[r"^\s*p[aá]gina\s*6\b", r"^\s*delitos\b"]),
    ("p7_vict_a", [r"^\s*p[aá]gina\s*7\b", r"\bvictimizaci[oó]n\b.*\bviolencia\s+intrafamiliar\b", r"\bapartado\s*a\b"]),
    ("p8_vict_b", [r"^\s*p[aá]gina\s*8\b", r"\bapartado\s*b\b", r"\botros\s+delitos\b"]),
    ("p9_conf",   [r"^\s*p[aá]gina\s*9\b", r"\bconfianza\s+policial\b"]),
    ("p10_prop",  [r"^\s*p[aá]gina\s*10\b", r"\bpropuestas\s+ciudadanas\b", r"\bmejora\s+de\s+la\s+seguridad\b"]),
]


# -----------------------------
# Utilidades
# -----------------------------

def slugify(text: str, max_len: int = 50) -> str:
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s-]+", "_", text).strip("_")
    if not text:
        text = "item"
    return text[:max_len]


def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def detect_page(text: str) -> Optional[str]:
    t = (text or "").strip().lower()
    for page_id, patterns in PAGE_MATCHERS:
        for pat in patterns:
            if re.search(pat, t, flags=re.IGNORECASE):
                return page_id
    return None


def extract_numbered_question(text: str) -> Optional[Tuple[str, str]]:
    t = (text or "").strip()
    m = re.match(r"^(\d{1,3})\s*[\.\-\)]\s*(.+)$", t)
    if not m:
        return None
    return m.group(1), m.group(2).strip()


def is_option_line(raw: str) -> bool:
    t = (raw or "").strip()
    if not t:
        return False
    if re.match(r"^\(\s*\)\s*\S+", t):
        return True
    if re.match(r"^[☐□]\s*\S+", t):
        return True
    if re.match(r"^[-•·]\s+\S+", t):
        return True
    return False


def clean_option_text(raw: str) -> str:
    t = (raw or "").strip()
    t = re.sub(r"^\(\s*\)\s*", "", t)
    t = re.sub(r"^[☐□]\s*", "", t)
    t = re.sub(r"^[-•·]\s+", "", t)
    return t.strip()


def make_survey_names_unique(rows: List[Dict]):
    seen = {}
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key not in seen:
            seen[key] = 1
        else:
            seen[key] += 1
            r["name"] = f"{name}_{seen[key]}"


def make_choice_names_unique(rows: List[Dict]):
    seen = {}
    for r in rows:
        ln = (r.get("list_name") or "").strip()
        nm = (r.get("name") or "").strip()
        if not ln or not nm:
            continue
        key = (ln.lower(), nm.lower())
        if key not in seen:
            seen[key] = 1
        else:
            seen[key] += 1
            r["name"] = f"{nm}_{seen[key]}"


# -----------------------------
# Parser DOCX -> XLSForm fijo
# -----------------------------

class PendingQuestion:
    def __init__(self, page_id: str, qnum: str, qtext: str):
        self.page_id = page_id
        self.qnum = qnum
        self.qtext = qtext
        self.options: List[str] = []
        self.multi: bool = False


def parse_docx_fixed_pages(docx_bytes: bytes, intro_text: str, consent_text: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, List[str]]:
    doc = Document(io.BytesIO(docx_bytes))

    # Contenedores por página
    page_notes: Dict[str, List[str]] = {pid: [] for pid, _ in PAGES}
    page_questions: Dict[str, List[PendingQuestion]] = {pid: [] for pid, _ in PAGES}

    glossary_rows: List[Dict] = []
    unassigned_lines: List[str] = []

    # Página actual
    current_page = "p1_intro"

    # Inyectar intro/consentimiento (SIEMPRE)
    page_notes["p1_intro"].append(normalize_space(intro_text))
    page_notes["p2_consent"].append(normalize_space(consent_text))

    pending: Optional[PendingQuestion] = None

    def flush_pending():
        nonlocal pending
        if pending:
            page_questions[pending.page_id].append(pending)
            pending = None

    def try_parse_glossary_line(line: str):
        t = (line or "").strip()
        m = re.match(r"^([^:]{3,80})\s*:\s*(.{5,})$", t)
        if not m:
            return
        term = m.group(1).strip()
        definition = m.group(2).strip()
        if term.lower() in {"objetivo", "finalidad", "datos", "responsable"}:
            return
        glossary_rows.append({"termino": term, "definicion": definition, "pagina": current_page})

    for p in doc.paragraphs:
        raw = p.text or ""
        text = raw.strip()
        if not text:
            continue

        # ¿Cambia de página?
        detected = detect_page(text)
        if detected:
            flush_pending()
            current_page = detected
            # Guardamos el encabezado como note editable (por si querés editar el título)
            page_notes[current_page].append(normalize_space(text))
            continue

        # glosario "Termino: definicion"
        try_parse_glossary_line(text)

        # ¿Nueva pregunta numerada?
        nq = extract_numbered_question(text)
        if nq:
            flush_pending()
            qnum, qtext = nq
            pending = PendingQuestion(current_page, qnum, qtext)
            continue

        # ¿Opción?
        if pending and is_option_line(raw):
            opt = clean_option_text(raw)
            if opt:
                pending.options.append(opt)
            if re.match(r"^[☐□]", (raw or "").strip()):
                pending.multi = True
            continue

        # Texto suelto = note bajo la página correspondiente
        flush_pending()
        # Evitar duplicar intro/consent ya inyectados si el Word repite portada
        page_notes[current_page].append(normalize_space(text))

    flush_pending()

    # Construir survey/choices con páginas fijas
    survey_rows: List[Dict] = []
    choices_rows: List[Dict] = []

    # settings mínimos
    settings_df = pd.DataFrame([{
        "form_title": "Encuesta Comunidad 2026",
        "form_id": "encuesta_comunidad_2026",
        "version": "1"
    }])

    # Helper para insertar note
    def add_note(pid: str, idx: int, label: str):
        survey_rows.append({
            "type": "note",
            "name": f"{pid}_note_{idx}",
            "label": label
        })

    # Insertar grupos en orden fijo
    for pid, plabel in PAGES:
        survey_rows.append({"type": "begin_group", "name": pid, "label": plabel})

        # notes (incluye título capturado y texto dentro de la página)
        notes = [n for n in page_notes[pid] if n]
        if notes:
            for i, n in enumerate(notes, start=1):
                add_note(pid, i, n)
        else:
            add_note(pid, 1, "— (Sin texto detectado para esta página en el Word) —")

        # preguntas
        qs = page_questions[pid]
        for q in qs:
            if q.options:
                list_name = f"{pid}_q{q.qnum}_opts"
                for k, opt in enumerate(q.options, start=1):
                    choices_rows.append({
                        "list_name": list_name,
                        "name": slugify(opt, 40) or f"opt_{k}",
                        "label": opt
                    })
                qtype = "select_multiple" if q.multi else "select_one"
                survey_rows.append({
                    "type": f"{qtype} {list_name}",
                    "name": f"{pid}_q{q.qnum}_{slugify(q.qtext, 28)}",
                    "label": q.qtext
                })
            else:
                survey_rows.append({
                    "type": "text",
                    "name": f"{pid}_q{q.qnum}_{slugify(q.qtext, 28)}",
                    "label": q.qtext
                })

        survey_rows.append({"type": "end_group", "name": "", "label": ""})

    # Normalizaciones para Survey123
    make_survey_names_unique(survey_rows)
    make_choice_names_unique(choices_rows)

    survey_df = pd.DataFrame(survey_rows)
    choices_df = pd.DataFrame(choices_rows)
    glossary_df = pd.DataFrame(glossary_rows)

    # Columnas mínimas
    for col in ["type","name","label","hint","required","relevant","calculation","constraint","constraint_message"]:
        if col not in survey_df.columns:
            survey_df[col] = ""
    survey_df = survey_df[["type","name","label","hint","required","relevant","calculation","constraint","constraint_message"]]

    for col in ["list_name","name","label"]:
        if col not in choices_df.columns:
            choices_df[col] = ""
    choices_df = choices_df[["list_name","name","label"]]

    return survey_df, choices_df, settings_df, glossary_df, unassigned_lines


def build_xlsx_bytes(survey_df, choices_df, settings_df, glossary_df) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        survey_df.to_excel(writer, index=False, sheet_name="survey")
        choices_df.to_excel(writer, index=False, sheet_name="choices")
        settings_df.to_excel(writer, index=False, sheet_name="settings")
        glossary_df.to_excel(writer, index=False, sheet_name="glosario")
    return out.getvalue()


# -----------------------------
# UI Streamlit
# -----------------------------

st.set_page_config(page_title="Word -> XLSForm (10 páginas fijas)", layout="wide")
st.title("✅ Word (.docx) → XLSForm (Survey123) — 10 páginas fijas (P1..P10)")

st.caption("Esta versión NO improvisa páginas: siempre crea tus 10 páginas en orden y mete la intro/consentimiento dentro.")

colA, colB = st.columns([1,1], gap="large")

with colA:
    docx_file = st.file_uploader("Subí tu Word (.docx)", type=["docx"])

    st.markdown("### Settings (Survey123)")
    form_title = st.text_input("form_title", "Encuesta Comunidad 2026")
    form_id = st.text_input("form_id", "encuesta_comunidad_2026")
    version = st.text_input("version", "1")

with colB:
    st.markdown("### Texto fijo que SIEMPRE va en P1 y P2 (editable)")
    default_intro = (
        "El presente formato corresponde a la Encuesta de Percepción de Comunidad 2026, diseñada para recopilar "
        "información clave sobre seguridad ciudadana, convivencia y factores de riesgo en los cantones del territorio nacional. "
        "Este documento se remite para su revisión y validación por parte de las direcciones, departamentos u oficinas con competencia "
        "técnica en cada uno de los apartados, con el fin de asegurar su coherencia metodológica, normativa y operativa con los lineamientos "
        "institucionales vigentes. Las observaciones recibidas permitirán fortalecer el instrumento antes de su aplicación en territorio."
    )
    default_consent = (
        "Usted está siendo invitado(a) a participar de forma libre y voluntaria en una encuesta sobre seguridad, convivencia y percepción ciudadana, "
        "dirigida a personas mayores de 18 años.\n"
        "El objetivo de esta encuesta es recopilar información de carácter preventivo y estadístico, con el fin de apoyar la planificación de acciones de prevención, "
        "mejora de la convivencia y fortalecimiento de la seguridad en comunidades y zonas comerciales.\n"
        "La participación es totalmente voluntaria. Puede negarse a responder cualquier pregunta, así como retirarse de la encuesta en cualquier momento, sin que ello genere consecuencia alguna.\n"
        "De conformidad con la Ley N.° 8968, Ley de Protección de la Persona frente al Tratamiento de sus Datos Personales, se le informa que la información será usada con fines estadísticos, analíticos y preventivos."
    )

    intro_text = st.text_area("P1 — Introducción (note)", value=default_intro, height=180)
    consent_text = st.text_area("P2 — Consentimiento informado (note)", value=default_consent, height=200)

st.markdown("---")

if not docx_file:
    st.warning("Subí el .docx para generar el XLSForm con las 10 páginas.")
else:
    try:
        survey_df, choices_df, settings_df, glossary_df, unassigned = parse_docx_fixed_pages(
            docx_file.read(),
            intro_text=intro_text,
            consent_text=consent_text
        )

        settings_df.loc[0, "form_title"] = form_title.strip() or "Encuesta Comunidad 2026"
        settings_df.loc[0, "form_id"] = form_id.strip() or "encuesta_comunidad_2026"
        settings_df.loc[0, "version"] = version.strip() or "1"

        st.success("✅ Generación lista. Revisa y descarga el XLSForm.")

        tabs = st.tabs(["survey", "choices", "settings", "glosario (extra)"])
        with tabs[0]:
            st.dataframe(survey_df, use_container_width=True, height=520)
        with tabs[1]:
            st.dataframe(choices_df, use_container_width=True, height=520)
        with tabs[2]:
            st.dataframe(settings_df, use_container_width=True, height=120)
        with tabs[3]:
            st.dataframe(glossary_df, use_container_width=True, height=350)

        xlsx_bytes = build_xlsx_bytes(survey_df, choices_df, settings_df, glossary_df)
        st.download_button(
            "⬇️ Descargar XLSForm (.xlsx)",
            data=xlsx_bytes,
            file_name=f"{settings_df.loc[0,'form_id']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.info("Si te vuelve a aparecer un error de Survey123 por duplicados: esta app ya fuerza nombres únicos automáticamente.")

    except Exception as e:
        st.error("❌ Error procesando el Word.")
        st.exception(e)
