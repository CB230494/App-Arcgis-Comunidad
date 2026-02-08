# -*- coding: utf-8 -*-
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 1/10) ==============================
# ===================== Encuesta Comunidad — Editor XLSForm (Base/Estado) ==================
# ==========================================================================================
# Objetivo de esta parte:
# - Imports
# - Config Streamlit
# - Utilidades (slugify, ids)
# - Estructura base en session_state
# - Seed inicial: páginas + preguntas (vacías/placeholder) para que la app NO quede en blanco
#
# Nota:
# - NO se carga ningún Word.
# - Las preguntas reales se irán cargando en partes posteriores (o pegándolas tú).
# - Desde YA dejamos la estructura lista para: label, info/hint, required, type, choices.
# ==========================================================================================

import re
import json
import uuid
from copy import deepcopy
import streamlit as st

# ------------------------------------------------------------------------------------------
# Config general
# ------------------------------------------------------------------------------------------
st.set_page_config(
    page_title="Encuesta Comunidad — Editor XLSForm",
    page_icon="🧩",
    layout="wide"
)

# ------------------------------------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------------------------------------
def slugify_name(text: str) -> str:
    """Convierte a slug simple para 'name' interno."""
    text = (text or "").strip().lower()
    text = re.sub(r"[áàäâ]", "a", text)
    text = re.sub(r"[éèëê]", "e", text)
    text = re.sub(r"[íìïî]", "i", text)
    text = re.sub(r"[óòöô]", "o", text)
    text = re.sub(r"[úùüû]", "u", text)
    text = re.sub(r"ñ", "n", text)
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("_")
    return text or "item"

def asegurar_nombre_unico(base: str, usados: set[str]) -> str:
    """Devuelve un name único dentro de 'usados'."""
    base = slugify_name(base)
    if base not in usados:
        return base
    i = 2
    while f"{base}_{i}" in usados:
        i += 1
    return f"{base}_{i}"

def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"

# ------------------------------------------------------------------------------------------
# Modelo de datos (en memoria)
# ------------------------------------------------------------------------------------------
DEFAULT_PAGES = [
    {"id": "P1", "title": "Página 1 — Portada", "info": "Formato Encuesta Comunidad 2026."},
    {"id": "P2", "title": "Página 2 — Consentimiento Informado", "info": "Texto legal + aceptación Sí/No."},
    {"id": "P3", "title": "I. DATOS DEMOGRÁFICOS", "info": "Datos generales de la persona participante."},
    {"id": "P4", "title": "II. PERCEPCIÓN CIUDADANA DE SEGURIDAD EN EL DISTRITO", "info": "Percepción, horarios, factores."},
    {"id": "P5", "title": "III. RIESGOS... — Riesgos sociales y situacionales", "info": "Riesgos sociales/situacionales del distrito."},
    {"id": "P6", "title": "III. RIESGOS... — Delitos", "info": "Delitos observados / ocurridos."},
    {"id": "P7", "title": "Victimización A: Violencia intrafamiliar", "info": "Victimización en el hogar."},
    {"id": "P8", "title": "Victimización B: Otros delitos", "info": "Victimización por otros delitos."},
    {"id": "P9", "title": "Confianza Policial", "info": "Relación con policía, respuesta institucional."},
    {"id": "P10", "title": "Propuestas ciudadanas", "info": "Sugerencias y mejoras en seguridad."},
]

def default_question_seed(page_id: str) -> list[dict]:
    """
    Seed mínimo por página para que el editor NO quede vacío.
    Luego tú vas pegando el banco real en partes posteriores.
    """
    if page_id == "P2":
        return [
            {
                "id": new_id("q"),
                "page_id": "P2",
                "type": "select_one",
                "name": "consentimiento",
                "label": "¿Acepta participar en esta encuesta?",
                "info": "Si responde 'No', finaliza la encuesta.",
                "required": True,
                "relevant": "",
                "constraint": "",
                "calculation": "",
                "choice_list": "yesno",
                "choices_inline": ["Sí", "No"],
            }
        ]
    return [
        {
            "id": new_id("q"),
            "page_id": page_id,
            "type": "text",
            "name": f"{slugify_name(page_id)}_placeholder",
            "label": f"Pregunta placeholder en {page_id}",
            "info": "Edita o elimina esta pregunta y agrega las reales.",
            "required": False,
            "relevant": "",
            "constraint": "",
            "calculation": "",
            "choice_list": "",
            "choices_inline": [],
        }
    ]

def _init_state():
    if "app_title" not in st.session_state:
        st.session_state.app_title = "Encuesta comunidad — San Carlos Oeste"

    # Banco de páginas
    if "pages" not in st.session_state:
        st.session_state.pages = deepcopy(DEFAULT_PAGES)

    # Preguntas: lista de dicts (una lista global con page_id)
    if "questions" not in st.session_state:
        qs = []
        for p in st.session_state.pages:
            qs.extend(default_question_seed(p["id"]))
        st.session_state.questions = qs

    # Banco de choices (opcional): también mantenemos un "choices_bank" tipo XLSForm
    # Cada fila: {list_name, name, label, extra...}
    if "choices_bank" not in st.session_state:
        st.session_state.choices_bank = []
        # lista yesno por defecto
        st.session_state.choices_bank.extend([
            {"list_name": "yesno", "name": "si", "label": "Sí"},
            {"list_name": "yesno", "name": "no", "label": "No"},
        ])

    if "active_section" not in st.session_state:
        st.session_state.active_section = "Preguntas"

    if "active_page" not in st.session_state:
        st.session_state.active_page = st.session_state.pages[0]["id"]

_init_state()

# ==========================================================================================
# FIN PARTE 1/10
# ==========================================================================================
# -*- coding: utf-8 -*-
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 2/10) ==============================
# =================== UI Base + Editor de Preguntas (con opciones desglosadas) ==============
# ==========================================================================================
# Objetivo de esta parte:
# - Encabezado (logo + nombre)
# - Navegación de secciones (Preguntas / Choices / Glosario / Catálogo / Exportar)
# - Editor de Preguntas:
#     - Editar título de página y su "info" (texto después del título)
#     - Listado de preguntas por página
#     - Cada pregunta editable: label + info + required + type + name
#     - Si es select_one / select_multiple: desglosa opciones inline para editar/agregar/borrar/reordenar
#
# Nota:
# - Choices global y glosario/catálogo/export se manejan en otras partes.
# ==========================================================================================

# ------------------------------------------------------------------------------------------
# Helpers UI
# ------------------------------------------------------------------------------------------
def get_page_by_id(pid: str) -> dict | None:
    for p in st.session_state.pages:
        if p["id"] == pid:
            return p
    return None

def get_questions_for_page(pid: str) -> list[dict]:
    return [q for q in (st.session_state.questions or []) if q.get("page_id") == pid]

def upsert_question(q: dict):
    qid = q["id"]
    for i, existing in enumerate(st.session_state.questions):
        if existing.get("id") == qid:
            st.session_state.questions[i] = q
            return
    st.session_state.questions.append(q)

def delete_question(qid: str):
    st.session_state.questions = [q for q in st.session_state.questions if q.get("id") != qid]

def move_question(qid: str, direction: int):
    """direction: -1 arriba, +1 abajo dentro de la misma página"""
    pid = None
    for q in st.session_state.questions:
        if q.get("id") == qid:
            pid = q.get("page_id")
            break
    if not pid:
        return
    page_qs = [q for q in st.session_state.questions if q.get("page_id") == pid]
    other_qs = [q for q in st.session_state.questions if q.get("page_id") != pid]

    idx = next((i for i, q in enumerate(page_qs) if q.get("id") == qid), None)
    if idx is None:
        return

    new_idx = idx + direction
    if new_idx < 0 or new_idx >= len(page_qs):
        return

    page_qs[idx], page_qs[new_idx] = page_qs[new_idx], page_qs[idx]
    st.session_state.questions = other_qs + page_qs

def render_choice_inline_editor(q: dict):
    """
    Editor de opciones inline para preguntas select_one / select_multiple.
    q["choices_inline"] = ["Opción 1", "Opción 2", ...]
    """
    st.markdown("**Opciones (una por fila)**")
    current = q.get("choices_inline", []) or []
    # Text area para edición rápida
    raw = "\n".join([str(x) for x in current])
    new_raw = st.text_area(
        "Editar opciones (una por línea)",
        value=raw,
        height=120,
        key=f"{q['id']}_choices_textarea"
    )
    # Botones: aplicar / agregar vacía
    c1, c2, c3 = st.columns([1, 1, 2])
    if c1.button("💾 Guardar opciones", use_container_width=True, key=f"{q['id']}_choices_save"):
        lines = [ln.strip() for ln in (new_raw or "").splitlines() if ln.strip()]
        q["choices_inline"] = lines
        # si no tiene choice_list, le ponemos una lista local por name
        if not q.get("choice_list"):
            q["choice_list"] = f"list_{q.get('name','pregunta')}"
        upsert_question(q)
        st.success("Opciones guardadas.")
        st.rerun()

    if c2.button("➕ Agregar opción vacía", use_container_width=True, key=f"{q['id']}_choices_add"):
        lines = [ln.strip() for ln in (new_raw or "").splitlines()]
        lines.append("")
        q["choices_inline"] = [x for x in lines if x != ""]
        upsert_question(q)
        st.rerun()

    with c3:
        st.caption("Tip: aquí editás rápido. En partes posteriores, el banco global de Choices también se puede sincronizar.")

def render_question_card(q: dict, idx: int):
    with st.container(border=True):
        top = st.columns([3, 1, 1, 1, 1])
        top[0].markdown(f"### {idx+1}. {q.get('label','(sin título)')}")

        if top[1].button("⬆️", key=f"{q['id']}_up", use_container_width=True):
            move_question(q["id"], -1); st.rerun()
        if top[2].button("⬇️", key=f"{q['id']}_down", use_container_width=True):
            move_question(q["id"], +1); st.rerun()
        if top[3].button("🗑", key=f"{q['id']}_del", use_container_width=True):
            delete_question(q["id"]); st.rerun()
        if top[4].button("💾", key=f"{q['id']}_save_btn", use_container_width=True):
            # Guardado se hace por widgets (ya están ligados abajo). Solo re-run para confirmar.
            st.success("Guardado."); st.rerun()

        col1, col2, col3 = st.columns([2, 2, 1])

        q["label"] = col1.text_input(
            "Título / Pregunta (label)",
            value=q.get("label", ""),
            key=f"{q['id']}_label"
        )
        q["name"] = col2.text_input(
            "Nombre interno (name)",
            value=q.get("name", ""),
            key=f"{q['id']}_name"
        )
        q["required"] = col3.checkbox(
            "Obligatoria",
            value=bool(q.get("required", False)),
            key=f"{q['id']}_req"
        )

        q["info"] = st.text_area(
            "Info / Descripción (sale debajo del título en el formulario)",
            value=q.get("info", ""),
            height=80,
            key=f"{q['id']}_info"
        )

        col4, col5, col6 = st.columns([1.5, 2, 2])
        q["type"] = col4.selectbox(
            "Tipo",
            options=["text", "integer", "decimal", "date", "select_one", "select_multiple", "note"],
            index=["text","integer","decimal","date","select_one","select_multiple","note"].index(q.get("type","text")) if q.get("type","text") in ["text","integer","decimal","date","select_one","select_multiple","note"] else 0,
            key=f"{q['id']}_type"
        )
        q["relevant"] = col5.text_input(
            "Relevancia (relevant) [opcional]",
            value=q.get("relevant", ""),
            key=f"{q['id']}_rel"
        )
        q["constraint"] = col6.text_input(
            "Restricción (constraint) [opcional]",
            value=q.get("constraint", ""),
            key=f"{q['id']}_con"
        )

        q["calculation"] = st.text_input(
            "Cálculo (calculation) [opcional]",
            value=q.get("calculation", ""),
            key=f"{q['id']}_calc"
        )

        # Si es selección, desglosar opciones
        if q["type"] in ("select_one", "select_multiple"):
            q["choice_list"] = st.text_input(
                "Lista de opciones (choice_list) [interno]",
                value=q.get("choice_list",""),
                key=f"{q['id']}_clist"
            )
            render_choice_inline_editor(q)
        else:
            # limpiar campos si no aplica
            q["choice_list"] = q.get("choice_list","")
            q["choices_inline"] = q.get("choices_inline", [])

        # Guardar cambios al vuelo
        upsert_question(q)

def render_preguntas():
    # Selector de página
    pages = st.session_state.pages
    page_labels = [f"{p['id']} — {p['title']}" for p in pages]
    page_ids = [p["id"] for p in pages]

    sel = st.selectbox(
        "Página",
        options=page_ids,
        format_func=lambda pid: next((f"{p['id']} — {p['title']}" for p in pages if p["id"] == pid), pid),
        index=page_ids.index(st.session_state.active_page) if st.session_state.active_page in page_ids else 0,
        key="page_selector"
    )
    st.session_state.active_page = sel

    p = get_page_by_id(sel)
    if not p:
        st.error("Página no encontrada.")
        return

    st.markdown("## Editor de Página")
    with st.container(border=True):
        c1, c2 = st.columns([2, 3])
        p["title"] = c1.text_input("Título de la página", value=p.get("title",""), key=f"{p['id']}_page_title")
        p["info"] = c2.text_area("Info de la página (aparece debajo del título)", value=p.get("info",""), height=80, key=f"{p['id']}_page_info")

        # Guardar en session_state.pages
        for i, pp in enumerate(st.session_state.pages):
            if pp["id"] == p["id"]:
                st.session_state.pages[i] = p
                break

    st.markdown("---")
    st.markdown("## Preguntas en esta página")

    # Buscar
    query = st.text_input("Buscar en esta página", value="", key=f"{sel}_search")
    qs = get_questions_for_page(sel)
    if query.strip():
        qlow = query.strip().lower()
        qs = [q for q in qs if qlow in (q.get("label","").lower() + " " + q.get("name","").lower() + " " + q.get("info","").lower())]

    if not qs:
        st.info("No hay preguntas en esta página (aún).")
    else:
        for idx, q in enumerate(qs):
            render_question_card(q, idx)

    st.markdown("---")
    st.markdown("### ➕ Agregar pregunta")
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1.5, 1])
        new_label = c1.text_input("Título (label)", value="", key=f"{sel}_new_label")
        new_type = c2.selectbox("Tipo", ["text","integer","decimal","date","select_one","select_multiple","note"], key=f"{sel}_new_type")
        if c3.button("Agregar", type="primary", use_container_width=True, key=f"{sel}_add_btn"):
            usados = {q.get("name","") for q in st.session_state.questions}
            base = slugify_name(new_label or f"pregunta_{sel}")
            name = asegurar_nombre_unico(base, usados)
            q = {
                "id": new_id("q"),
                "page_id": sel,
                "type": new_type,
                "name": name,
                "label": new_label or "Nueva pregunta",
                "info": "",
                "required": False,
                "relevant": "",
                "constraint": "",
                "calculation": "",
                "choice_list": "yesno" if new_type in ("select_one","select_multiple") else "",
                "choices_inline": ["Sí","No"] if new_type in ("select_one","select_multiple") else [],
            }
            st.session_state.questions.append(q)
            st.success("Pregunta agregada.")
            st.rerun()

# ------------------------------------------------------------------------------------------
# Header (logo + nombre)
# ------------------------------------------------------------------------------------------
colL, colR = st.columns([1, 3], vertical_alignment="top")

with colL:
    st.markdown("### Logo (PNG/JPG)")
    logo = st.file_uploader("Sube el logo si lo deseas", type=["png", "jpg", "jpeg"], key="logo_uploader")
    if logo:
        st.image(logo, use_container_width=True)

with colR:
    st.markdown("### Nombre del lugar / Delegación")
    st.session_state.app_title = st.text_input(
        "Nombre visible en la app",
        value=st.session_state.app_title,
        key="app_title_input"
    )

st.title(st.session_state.app_title)

# ------------------------------------------------------------------------------------------
# Navegación Sección
# ------------------------------------------------------------------------------------------
st.markdown("## Sección")
section = st.radio(
    "Sección",
    options=["Preguntas", "Choices", "Glosario", "Catálogo", "Exportar"],
    horizontal=True,
    index=["Preguntas","Choices","Glosario","Catálogo","Exportar"].index(st.session_state.active_section) if st.session_state.active_section in ["Preguntas","Choices","Glosario","Catálogo","Exportar"] else 0,
    label_visibility="collapsed",
    key="section_radio"
)
st.session_state.active_section = section

st.markdown("---")

# ------------------------------------------------------------------------------------------
# Render según sección (en esta parte solo Preguntas)
# ------------------------------------------------------------------------------------------
if section == "Preguntas":
    render_preguntas()
else:
    st.info("Esta sección se completa en otras partes (Choices / Glosario / Catálogo / Exportar).")

# ==========================================================================================
# FIN PARTE 2/10
# ==========================================================================================







