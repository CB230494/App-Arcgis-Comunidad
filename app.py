# -*- coding: utf-8 -*-
"""
Word (.docx) -> XLSForm (Survey123) + Glosario
- Genera Excel con hojas: survey, choices, settings (+ glossary extra)
- Extrae preguntas numeradas, opciones ( ) y ☐, notas y definiciones tipo: "Extorsión (...)"
"""

import io
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from docx import Document


# =========================
# Utilidades
# =========================

def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[áàäâ]", "a", s)
    s = re.sub(r"[éèëê]", "e", s)
    s = re.sub(r"[íìïî]", "i", s)
    s = re.sub(r"[óòöô]", "o", s)
    s = re.sub(r"[úùüû]", "u", s)
    s = re.sub(r"ñ", "n", s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "x"


def safe_name(prefix: str, n: int) -> str:
    return f"{prefix}{n:02d}"


def is_blank(p: str) -> bool:
    return not p or not p.strip()


def clean_text(t: str) -> str:
    t = t.replace("\u00a0", " ").strip()
    t = re.sub(r"\s+", " ", t).strip()
    return t


# =========================
# Modelos
# =========================

@dataclass
class ChoiceItem:
    list_name: str
    name: str
    label: str


@dataclass
class SurveyRow:
    type: str
    name: str
    label: str
    hint: str = ""
    relevant: str = ""
    constraint: str = ""
    constraint_message: str = ""


@dataclass
class ParseContext:
    current_section: str = "general"
    current_intro_buffer: List[str] = field(default_factory=list)
    survey_rows: List[SurveyRow] = field(default_factory=list)
    choices: List[ChoiceItem] = field(default_factory=list)
    glossary: Dict[str, str] = field(default_factory=dict)
    list_registry: Dict[Tuple[str, str], str] = field(default_factory=dict)  # (list_name, label)->choice_name


# =========================
# Parsing
# =========================

QNUM_RE = re.compile(r"^\s*(\d+)\s*[\.\-]\s*(.+?)\s*$")
SUBQ_RE = re.compile(r"^\s*(\d+)\.(\d+)\s*[\.\-]?\s*(.+?)\s*$")

# Opciones:
# ( ) opción
RADIO_OPT_RE = re.compile(r"^\s*\(\s*\)\s*(.+?)\s*$")
# ☐ opción
CHECK_OPT_RE = re.compile(r"^\s*[☐■▪▫\[\]]\s*(.+?)\s*$")

# Definición: Término (definición)
DEF_RE = re.compile(r"^\s*([A-Za-zÁÉÍÓÚÑáéíóúñ0-9\/\-\s]+?)\s*\(([^)]+)\)\s*$")


def detect_section_title(text: str) -> Optional[str]:
    """
    Detecta títulos de sección/página según tu estructura típica.
    Devuelve un slug estable.
    """
    t = text.strip()

    # Portada / intro general
    if re.search(r"\bFORMATO\b.*\bENCUESTA\b.*\bCOMUNIDAD\b", t, flags=re.I):
        return "p1_intro"

    if re.search(r"\bConsentimiento Informado\b", t, flags=re.I):
        return "p2_consentimiento"

    if re.match(r"^I\.\s*DATOS DEMOGRÁFICOS", t, flags=re.I):
        return "p3_datos_demograficos"

    if re.match(r"^II\.\s*PERCEPCIÓN CIUDADANA", t, flags=re.I):
        return "p4_percepcion"

    if re.match(r"^III\.\s*RIESGOS", t, flags=re.I):
        # Este es el gran bloque; luego vienen subtítulos “Riesgos…”, “Delitos…”, etc.
        return "p5_riesgos_sociales"

    if re.match(r"^Riesgos sociales y situacionales", t, flags=re.I):
        return "p5_riesgos_sociales"

    if re.match(r"^Delitos\s*$", t, flags=re.I):
        return "p6_delitos"

    if re.match(r"^Victimización\s*$", t, flags=re.I):
        return "p7_vif"

    if re.match(r"^Apartado A:\s*Violencia intrafamiliar", t, flags=re.I):
        return "p7_vif"

    if re.match(r"^Apartado B:\s*Victimización por otros delitos", t, flags=re.I):
        return "p8_victimizacion_otros"

    if re.match(r"^Confianza Policial", t, flags=re.I):
        return "p9_confianza_policial"

    if re.match(r"^Propuestas ciudadanas", t, flags=re.I):
        return "p10_propuestas"

    # Cierre / contacto
    if re.match(r"^Información Adicional y Contacto", t, flags=re.I):
        return "p10_propuestas"

    return None


def ensure_choice(ctx: ParseContext, list_name: str, label: str) -> str:
    """
    Registra una opción en choices si no existe; devuelve el name interno.
    """
    label_clean = clean_text(label)
    key = (list_name, label_clean.lower())

    if key in ctx.list_registry:
        return ctx.list_registry[key]

    base = slugify(label_clean)
    # Evitar colisiones dentro del list_name
    existing = {c.name for c in ctx.choices if c.list_name == list_name}
    choice_name = base
    i = 2
    while choice_name in existing:
        choice_name = f"{base}_{i}"
        i += 1

    ctx.choices.append(ChoiceItem(list_name=list_name, name=choice_name, label=label_clean))
    ctx.list_registry[key] = choice_name
    return choice_name


def harvest_definition(ctx: ParseContext, text: str) -> None:
    """
    Si el texto luce como "Término (definición)", lo agrega al glosario.
    """
    m = DEF_RE.match(text.strip())
    if not m:
        return
    term = clean_text(m.group(1))
    definition = clean_text(m.group(2))
    if len(term) >= 3 and len(definition) >= 5:
        ctx.glossary.setdefault(term, definition)


def flush_intro_as_note(ctx: ParseContext, page_id: str) -> None:
    """
    Si hay texto acumulado (párrafos sin pregunta), se agrega como 'note' al inicio de la página.
    """
    if not ctx.current_intro_buffer:
        return
    label = clean_text(" ".join(ctx.current_intro_buffer))
    if label:
        ctx.survey_rows.append(SurveyRow(type="note", name=f"{page_id}_intro", label=label))
    ctx.current_intro_buffer = []


def begin_page_group(ctx: ParseContext, page_id: str, page_title: str) -> None:
    ctx.survey_rows.append(SurveyRow(type="begin_group", name=page_id, label=page_title))


def end_page_group(ctx: ParseContext, page_id: str) -> None:
    ctx.survey_rows.append(SurveyRow(type="end_group", name=page_id, label=""))


def parse_docx_to_xlsform(doc_bytes: bytes, form_title: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    doc = Document(io.BytesIO(doc_bytes))
    ctx = ParseContext()

    # settings
    settings_df = pd.DataFrame([{
        "form_title": form_title,
        "form_id": slugify(form_title),
        "version": "1",
        "default_language": "es",
    }])

    # Seed yesno
    ensure_choice(ctx, "yesno", "Sí")
    ensure_choice(ctx, "yesno", "No")

    # Páginas: creamos al menos las 10, aunque el Word tenga títulos mezclados
    pages_order = [
        ("p1_intro", "Página 1 — Introducción"),
        ("p2_consentimiento", "Página 2 — Consentimiento informado"),
        ("p3_datos_demograficos", "Página 3 — I. Datos demográficos"),
        ("p4_percepcion", "Página 4 — II. Percepción ciudadana de seguridad en el distrito"),
        ("p5_riesgos_sociales", "Página 5 — III. Riesgos sociales y situacionales en el distrito"),
        ("p6_delitos", "Página 6 — Delitos"),
        ("p7_vif", "Página 7 — Victimización A: Violencia intrafamiliar"),
        ("p8_victimizacion_otros", "Página 8 — Victimización B: Otros delitos"),
        ("p9_confianza_policial", "Página 9 — Confianza policial"),
        ("p10_propuestas", "Página 10 — Propuestas ciudadanas / Contacto"),
    ]
    page_titles = dict(pages_order)

    # Abrimos la primera página
    current_page = "p1_intro"
    begin_page_group(ctx, current_page, page_titles[current_page])

    q_counter = 1

    # Aux: estado para capturar opciones luego de una pregunta
    pending_q: Optional[SurveyRow] = None
    pending_opts: List[Tuple[str, str]] = []  # (kind, label) where kind in {"radio","check"}
    pending_notes: List[str] = []

    def commit_pending_question():
        nonlocal pending_q, pending_opts, pending_notes
        if pending_q is None:
            return

        # Hint con notas (si hay)
        if pending_notes:
            pending_q.hint = clean_text(" ".join(pending_notes))

        # Si hay opciones → convertimos a select_one / select_multiple
        if pending_opts:
            is_multi = any(k == "check" for k, _ in pending_opts)
            # Si mezclaron radio y check, priorizamos múltiple
            list_name = f"{pending_q.name}_list"

            for kind, lab in pending_opts:
                harvest_definition(ctx, lab)
                # si viene "Término (definición)" dejamos label completo igual
                ensure_choice(ctx, list_name, lab)

            if is_multi:
                pending_q.type = f"select_multiple {list_name}"
            else:
                pending_q.type = f"select_one {list_name}"

        ctx.survey_rows.append(pending_q)
        pending_q = None
        pending_opts = []
        pending_notes = []

    for p in doc.paragraphs:
        text = clean_text(p.text)
        if is_blank(text):
            continue

        # Detectar cambio de página/sección
        maybe_page = detect_section_title(text)
        if maybe_page and maybe_page != current_page:
            # cerrar pendiente
            commit_pending_question()
            flush_intro_as_note(ctx, current_page)
            end_page_group(ctx, current_page)

            current_page = maybe_page
            begin_page_group(ctx, current_page, page_titles.get(current_page, text))
            continue

        # Detectar “Nota: …” como texto auxiliar
        if text.lower().startswith("nota"):
            # si hay pregunta pendiente: su nota es hint
            if pending_q is not None:
                pending_notes.append(text)
            else:
                ctx.current_intro_buffer.append(text)
            continue

        # ¿Es subpregunta 7.1, 29.1 etc?
        msub = SUBQ_RE.match(text)
        if msub:
            commit_pending_question()
            qnum = f"{msub.group(1)}_{msub.group(2)}"
            qlabel = clean_text(msub.group(3))
            pending_q = SurveyRow(type="text", name=f"q{qnum}", label=qlabel)
            continue

        # ¿Es pregunta 7., 10., 44. etc?
        mq = QNUM_RE.match(text)
        if mq:
            commit_pending_question()
            qnum = mq.group(1)
            qlabel = clean_text(mq.group(2))
            pending_q = SurveyRow(type="text", name=f"q{int(qnum):02d}", label=qlabel)
            q_counter += 1
            continue

        # Opciones radio/check
        mr = RADIO_OPT_RE.match(text)
        if mr and pending_q is not None:
            pending_opts.append(("radio", clean_text(mr.group(1))))
            continue

        mc = CHECK_OPT_RE.match(text)
        if mc and pending_q is not None:
            pending_opts.append(("check", clean_text(mc.group(1))))
            continue

        # Caso especial: línea con "¿Acepta participar... ( ) Sí ( ) No"
        if "¿Acepta participar" in text and pending_q is None:
            commit_pending_question()
            pending_q = SurveyRow(type="select_one yesno", name="consent", label=text)
            continue

        # Si hay pregunta pendiente y el texto parece parte del enunciado (continuación)
        if pending_q is not None and not pending_opts:
            # concatenamos al label si es continuación evidente
            pending_q.label = clean_text(pending_q.label + " " + text)
            continue

        # Si no calza en nada, lo tratamos como intro/nota de la página
        ctx.current_intro_buffer.append(text)

    # Final
    commit_pending_question()
    flush_intro_as_note(ctx, current_page)
    end_page_group(ctx, current_page)

    # Ajustes rápidos: si el consentimiento quedó como text por no detectar, lo convertimos si aplica
    for r in ctx.survey_rows:
        if r.name == "consent" and not r.type.startswith("select_one"):
            r.type = "select_one yesno"

    # DataFrames
    survey_df = pd.DataFrame([{
        "type": r.type,
        "name": r.name,
        "label::es": r.label,
        "hint::es": r.hint,
        "relevant": r.relevant,
        "constraint": r.constraint,
        "constraint_message::es": r.constraint_message,
    } for r in ctx.survey_rows])

    choices_df = pd.DataFrame([{
        "list_name": c.list_name,
        "name": c.name,
        "label::es": c.label,
    } for c in ctx.choices])

    glossary_df = pd.DataFrame([{
        "term": k,
        "definition": v,
    } for k, v in sorted(ctx.glossary.items(), key=lambda x: x[0].lower())])

    return survey_df, choices_df, settings_df, glossary_df


def build_xlsx_bytes(survey_df: pd.DataFrame, choices_df: pd.DataFrame, settings_df: pd.DataFrame, glossary_df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        survey_df.to_excel(writer, sheet_name="survey", index=False)
        choices_df.to_excel(writer, sheet_name="choices", index=False)
        settings_df.to_excel(writer, sheet_name="settings", index=False)
        # hoja extra (no rompe XLSForm)
        glossary_df.to_excel(writer, sheet_name="glossary", index=False)
    return output.getvalue()


# =========================
# UI Streamlit
# =========================

st.set_page_config(page_title="Word → XLSForm (Survey123) + Glosario", layout="wide")
st.title("📄➡️📊 Word → XLSForm (Survey123) + Glosario")

st.write("Subí tu archivo **.docx** y la app genera un **XLSForm (.xlsx)** con `survey`, `choices`, `settings` y una hoja extra `glossary`.")

form_title = st.text_input("Título del formulario (form_title)", value="Encuesta Comunidad 2026")

docx_file = st.file_uploader("Subir Word (.docx)", type=["docx"])

col1, col2 = st.columns([1, 1], gap="large")

if docx_file is not None:
    doc_bytes = docx_file.read()

    try:
        survey_df, choices_df, settings_df, glossary_df = parse_docx_to_xlsform(doc_bytes, form_title=form_title)

        with col1:
            st.subheader("✅ Vista previa — survey")
            st.dataframe(survey_df, use_container_width=True, height=450)

            st.subheader("✅ Vista previa — settings")
            st.dataframe(settings_df, use_container_width=True)

        with col2:
            st.subheader("✅ Vista previa — choices")
            st.dataframe(choices_df, use_container_width=True, height=450)

            st.subheader("✅ Vista previa — glossary (extra)")
            if glossary_df.empty:
                st.info("No se detectaron definiciones tipo “Término (definición)” en el texto. (Podés agregarlas manualmente luego).")
            else:
                st.dataframe(glossary_df, use_container_width=True, height=220)

        xlsx_bytes = build_xlsx_bytes(survey_df, choices_df, settings_df, glossary_df)

        st.download_button(
            "⬇️ Descargar XLSForm (.xlsx)",
            data=xlsx_bytes,
            file_name=f"{slugify(form_title)}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        st.success("Listo: XLSForm generado. Si querés, luego te lo adapto para *cascada Cantón→Distrito* y lógica condicional exacta (relevant).")

    except Exception as e:
        st.error("Ocurrió un error procesando el Word. Mostrame este error y lo ajusto:")
        st.exception(e)
else:
    st.info("Subí un .docx para empezar.")
