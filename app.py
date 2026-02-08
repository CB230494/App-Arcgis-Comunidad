# -*- coding: utf-8 -*-
"""
App: Word (.docx) -> XLSForm (Survey123) + control de nombres únicos
- Genera XLSX con hojas: survey, choices, settings (+ glosario opcional)
- Detecta preguntas numeradas y opciones tipo "( )", "☐", "-", "•"
- Crea grupos/páginas cuando detecta encabezados (Heading o líneas tipo "Página X")
- Evita duplicados en la columna "name" (case-insensitive) para que Survey123 no falle
"""

import re
import io
import unicodedata
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import streamlit as st
import pandas as pd
from docx import Document


# -----------------------------
# Utilidades
# -----------------------------

def slugify(text: str, max_len: int = 50) -> str:
    """Convierte texto a un name válido: sin tildes, minúsculas, _ en vez de espacios, alfanumérico/_."""
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s-]+", "_", text).strip("_")
    if not text:
        text = "item"
    return text[:max_len]


def is_heading(paragraph) -> bool:
    """Detecta encabezado por estilo Word."""
    try:
        style = (paragraph.style.name or "").lower()
        return style.startswith("heading")
    except Exception:
        return False


def looks_like_page_title(text: str) -> bool:
    """Detecta encabezados tipo 'Página 5 ...' o 'P5 Riesgos'."""
    t = (text or "").strip()
    return bool(re.match(r"^(p(ágina)?\s*\d+|p\d+)\b", t, flags=re.IGNORECASE))


def extract_numbered_question(text: str) -> Optional[Tuple[str, str]]:
    """
    Detecta '12. ¿Texto?' o '12- Texto' o '12) Texto'
    Devuelve (qnum, qtext) o None
    """
    t = (text or "").strip()
    m = re.match(r"^(\d{1,3})\s*[\.\-\)]\s*(.+)$", t)
    if not m:
        return None
    return m.group(1), m.group(2).strip()


def is_option_line(text: str) -> bool:
    """Detecta líneas que parecen opción: '( ) Sí', '☐ ...', '-', '•' etc."""
    t = (text or "").strip()
    if not t:
        return False
    if re.match(r"^\(\s*\)\s*\S+", t):  # ( ) Opción
        return True
    if re.match(r"^[☐□]\s*\S+", t):
        return True
    if re.match(r"^[-•·]\s+\S+", t):
        return True
    return False


def clean_option_text(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^\(\s*\)\s*", "", t)
    t = re.sub(r"^[☐□]\s*", "", t)
    t = re.sub(r"^[-•·]\s+", "", t)
    return t.strip()


def make_survey_names_unique(survey_rows: List[Dict]):
    """
    Garantiza que cada 'name' en la hoja survey sea único (case-insensitive),
    agregando sufijos _2, _3... si se repite.
    """
    seen: Dict[str, int] = {}
    for r in survey_rows:
        base = (r.get("name") or "").strip()
        if not base:
            continue
        key = base.lower()
        if key not in seen:
            seen[key] = 1
            continue
        seen[key] += 1
        r["name"] = f"{base}_{seen[key]}"


def make_choice_names_unique(choices_rows: List[Dict]):
    """
    Garantiza que dentro de un mismo list_name no se repita 'name' (case-insensitive).
    """
    seen: Dict[Tuple[str, str], int] = {}
    for r in choices_rows:
        ln = (r.get("list_name") or "").strip()
        nm = (r.get("name") or "").strip()
        if not ln or not nm:
            continue
        key = (ln.lower(), nm.lower())
        if key not in seen:
            seen[key] = 1
            continue
        seen[key] += 1
        r["name"] = f"{nm}_{seen[key]}"


# -----------------------------
# Parser DOCX -> XLSForm
# -----------------------------

@dataclass
class PendingQuestion:
    qnum: str
    qtext: str
    options: List[str]
    multi: bool = False


def parse_docx_to_xlsform(docx_bytes: bytes) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Devuelve: survey_df, choices_df, settings_df, glossary_df
    """
    doc = Document(io.BytesIO(docx_bytes))

    survey_rows: List[Dict] = []
    choices_rows: List[Dict] = []
    glossary_rows: List[Dict] = []

    # settings mínimos recomendados para Survey123
    settings_df = pd.DataFrame([{
        "form_title": "Encuesta Comunidad",
        "form_id": "encuesta_comunidad",
        "version": "1"
    }])

    current_group_name = None
    current_group_label = None

    pending: Optional[PendingQuestion] = None

    def flush_pending():
        nonlocal pending
        if not pending:
            return

        # Crear list_name para choices si hay opciones
        if pending.options:
            list_name = f"q{pending.qnum}_opts"
            # Registrar choices
            for idx, opt in enumerate(pending.options, start=1):
                choices_rows.append({
                    "list_name": list_name,
                    "name": slugify(opt, 40) or f"opt_{idx}",
                    "label": opt
                })

            qtype = "select_multiple" if pending.multi else "select_one"
            survey_rows.append({
                "type": f"{qtype} {list_name}",
                "name": f"q{pending.qnum}_{slugify(pending.qtext, 30)}",
                "label": pending.qtext
            })
        else:
            # Sin opciones: default a texto
            survey_rows.append({
                "type": "text",
                "name": f"q{pending.qnum}_{slugify(pending.qtext, 30)}",
                "label": pending.qtext
            })

        pending = None

    def open_group(label: str):
        nonlocal current_group_name, current_group_label
        # Cerrar grupo previo si está abierto
        if current_group_name:
            survey_rows.append({"type": "end_group", "name": "", "label": ""})

        current_group_label = (label or "").strip()
        current_group_name = slugify(current_group_label, 40)
        survey_rows.append({"type": "begin_group", "name": current_group_name, "label": current_group_label})

    # Heurística para glosario: "Término: Definición"
    def try_parse_glossary_line(text: str):
        t = (text or "").strip()
        m = re.match(r"^([^:]{3,80})\s*:\s*(.{5,})$", t)
        if not m:
            return
        term = m.group(1).strip()
        definition = m.group(2).strip()
        # Evitar capturar "Objetivo: ..." etc (muy común) -> lo filtramos un poco
        if term.lower() in {"objetivo", "finalidad", "datos", "responsable"}:
            return
        glossary_rows.append({"termino": term, "definicion": definition, "pagina": current_group_label or ""})

    # Recorremos párrafos del doc
    for p in doc.paragraphs:
        raw = p.text or ""
        text = raw.strip()
        if not text:
            continue

        # Encabezados / páginas
        if is_heading(p) or looks_like_page_title(text):
            flush_pending()
            open_group(text)
            continue

        # Capturar glosario si viene en formato "Termino: definicion"
        try_parse_glossary_line(text)

        # ¿Nueva pregunta numerada?
        nq = extract_numbered_question(text)
        if nq:
            flush_pending()
            qnum, qtext = nq
            pending = PendingQuestion(qnum=qnum, qtext=qtext, options=[], multi=False)
            continue

        # ¿Es línea de opción para la pregunta en curso?
        if pending and is_option_line(text):
            opt = clean_option_text(text)
            if opt:
                pending.options.append(opt)
            # Si aparece checkbox "☐" asumimos múltiple
            if re.match(r"^[☐□]", (raw or "").strip()):
                pending.multi = True
            continue

        # Si hay texto suelto dentro de un grupo y NO es opción:
        # lo metemos como "note" (información debajo del título, editable en Survey123)
        flush_pending()
        note_name = f"note_{slugify(text, 30)}"
        survey_rows.append({
            "type": "note",
            "name": note_name,
            "label": text
        })

    # Final
    flush_pending()
    if current_group_name:
        survey_rows.append({"type": "end_group", "name": "", "label": ""})

    # Normalizaciones críticas para evitar errores Survey123
    # 1) names únicos (survey)
    make_survey_names_unique(survey_rows)
    # 2) choices únicos dentro de list_name
    make_choice_names_unique(choices_rows)

    # DataFrames
    survey_df = pd.DataFrame(survey_rows)
    choices_df = pd.DataFrame(choices_rows)
    glossary_df = pd.DataFrame(glossary_rows)

    # Asegurar columnas mínimas (XLSForm tolera más, pero mejor fijas)
    for col in ["type", "name", "label", "hint", "required", "relevant", "calculation", "constraint", "constraint_message"]:
        if col not in survey_df.columns:
            survey_df[col] = ""

    for col in ["list_name", "name", "label"]:
        if col not in choices_df.columns:
            choices_df[col] = ""

    # Orden de columnas
    survey_df = survey_df[["type", "name", "label", "hint", "required", "relevant", "calculation", "constraint", "constraint_message"]]
    choices_df = choices_df[["list_name", "name", "label"]]

    return survey_df, choices_df, settings_df, glossary_df


def build_xlsform_xlsx_bytes(survey_df: pd.DataFrame, choices_df: pd.DataFrame, settings_df: pd.DataFrame, glossary_df: pd.DataFrame) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        survey_df.to_excel(writer, index=False, sheet_name="survey")
        choices_df.to_excel(writer, index=False, sheet_name="choices")
        settings_df.to_excel(writer, index=False, sheet_name="settings")
        # hoja extra (no afecta Survey123)
        glossary_df.to_excel(writer, index=False, sheet_name="glosario")
    return out.getvalue()


# -----------------------------
# UI Streamlit
# -----------------------------

st.set_page_config(page_title="Word -> XLSForm (Survey123)", layout="wide")

st.title("🧩 Convertidor Word (.docx) → XLSForm (Survey123)")
st.caption("Genera un XLSX con survey/choices/settings y corrige automáticamente nombres duplicados (ej: p2_consentimiento).")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1) Subí tu Word")
    docx_file = st.file_uploader("Documento Word (.docx)", type=["docx"])

    st.markdown("---")
    st.subheader("2) Opciones")
    form_title = st.text_input("Título del formulario (settings.form_title)", value="Encuesta Comunidad 2026")
    form_id = st.text_input("ID del formulario (settings.form_id)", value="encuesta_comunidad_2026")
    version = st.text_input("Versión (settings.version)", value="1")

with col2:
    st.subheader("Vista rápida (qué hace)")
    st.markdown(
        """
- Detecta **páginas/grupos** por estilos *Heading* o textos tipo **“Página 5 … / P5 …”**
- Detecta **preguntas numeradas**: `12. texto` / `12- texto` / `12) texto`
- Detecta **opciones**: `( )`, `☐`, `-`, `•`
- Texto bajo títulos -> lo convierte a **note** (editable)
- Corrige automáticamente:
  - **Duplicados en survey.name** (case-insensitive)
  - **Duplicados en choices.name** dentro de cada list_name
        """
    )

if docx_file:
    try:
        survey_df, choices_df, settings_df, glossary_df = parse_docx_to_xlsform(docx_file.read())

        # Aplicar settings ingresados por el usuario
        settings_df.loc[0, "form_title"] = form_title.strip() or "Encuesta Comunidad"
        settings_df.loc[0, "form_id"] = form_id.strip() or "encuesta_comunidad"
        settings_df.loc[0, "version"] = version.strip() or "1"

        st.success("✅ Documento procesado. Abajo podés revisar y descargar el XLSForm.")

        tabs = st.tabs(["survey", "choices", "settings", "glosario (extra)"])

        with tabs[0]:
            st.dataframe(survey_df, use_container_width=True, height=450)

        with tabs[1]:
            st.dataframe(choices_df, use_container_width=True, height=450)

        with tabs[2]:
            st.dataframe(settings_df, use_container_width=True, height=120)

        with tabs[3]:
            st.dataframe(glossary_df, use_container_width=True, height=300)

        xlsx_bytes = build_xlsform_xlsx_bytes(survey_df, choices_df, settings_df, glossary_df)
        st.download_button(
            label="⬇️ Descargar XLSForm (.xlsx)",
            data=xlsx_bytes,
            file_name=f"{form_id.strip() or 'encuesta_comunidad'}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.info("Tip: Si Survey123 te vuelve a dar error, revisá primero la columna 'name' en la hoja 'survey'. Pero esta app ya evita duplicados automáticamente.")

    except Exception as e:
        st.error("❌ Ocurrió un error procesando el Word.")
        st.exception(e)
else:
    st.warning("Subí un archivo .docx para generar el XLSForm.")
