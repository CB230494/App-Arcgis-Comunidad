# ===== PARCHE ANTI-ESTADO CORRUPTO (OBLIGATORIO) =====
def _force_dict_state(key: str):
    """
    Garantiza que session_state[key] sea dict.
    Si por ejecuciones previas quedó como list/str/None, lo resetea a {}.
    """
    if key not in st.session_state or not isinstance(st.session_state.get(key), dict):
        st.session_state[key] = {}

def _force_list_state(key: str):
    """
    Garantiza que session_state[key] sea list.
    """
    if key not in st.session_state or not isinstance(st.session_state.get(key), list):
        st.session_state[key] = []

_force_list_state("pages")
_force_dict_state("questions")
_force_dict_state("choices_lists")
_force_dict_state("glossary_terms")
_force_dict_state("page_glossary_map")
# =====================================================
# ==========================================================================================
# PARTE 1/10
# App: Editor XLSForm — Encuesta Comunidad (Banco de preguntas + Editor + Choices + Glosario)
# Objetivo de esta parte:
# - Configuración base
# - Estructuras de datos en st.session_state (pages, questions, choices, glosario, etc.)
# - Funciones utilitarias (normalización, CRUD base, seeds mínimos)
# NOTA: No se solicita subir Word. Todo se precarga por código.
# ==========================================================================================

from __future__ import annotations

import re
import json
from typing import Dict, List, Any, Optional

import streamlit as st


# -------------------------
# Configuración de página
# -------------------------
st.set_page_config(
    page_title="Editor XLSForm — Encuesta Comunidad",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ==========================================================================================
# Helpers generales
# ==========================================================================================

def normalize_name(text: str) -> str:
    """
    Normaliza a un identificador seguro tipo XLSForm:
    - minúsculas
    - espacios a "_"
    - quita caracteres no válidos
    - evita comenzar con número
    """
    if text is None:
        text = ""
    t = str(text).strip().lower()
    t = re.sub(r"\s+", "_", t)
    t = re.sub(r"[^a-z0-9_]+", "", t)
    t = re.sub(r"_+", "_", t).strip("_")
    if t and t[0].isdigit():
        t = f"q_{t}"
    return t or "q_sin_nombre"


def _ensure_session_key(key: str, default_value):
    if key not in st.session_state:
        st.session_state[key] = default_value


def _ensure_list_dict_key(dct: dict, key: str, default_value):
    if key not in dct:
        dct[key] = default_value


# ==========================================================================================
# Modelo de datos (session_state)
# ==========================================================================================

def init_state():
    # Páginas
    _ensure_session_key("pages", [])  # List[dict]: {id,title,info}

    # Preguntas por página
    _ensure_session_key("questions", {})  # Dict[page_id, List[dict]]

    # Choices (listas)
    _ensure_session_key("choices_lists", {})  # Dict[list_name, List[dict{name,label}]]

    # Glosario (término -> definición)
    _ensure_session_key("glossary_terms", {})  # Dict[term, definition]

    # Asignación glosario por página (page_id -> [terms])
    _ensure_session_key("page_glossary_map", {})  # Dict[page_id, List[str]]

    # UI
    _ensure_session_key("active_page", None)
    _ensure_session_key("active_question_name", None)
    _ensure_session_key("modo_preguntas", "Editor (por página)")
    _ensure_session_key("active_list_name", None)


# ==========================================================================================
# Seeds (páginas oficiales + lista yes/no mínima)
# ==========================================================================================

def seed_pages_if_empty():
    """
    Crea P1..P10 con los títulos que indicaste.
    """
    if st.session_state.pages:
        return

    pages = [
        {"id": "P1", "title": "Formato Encuesta Comunidad", "info": "Portada / presentación general del instrumento."},
        {"id": "P2", "title": "Consentimiento informado", "info": "Texto legal + aceptación de participación."},
        {"id": "P3", "title": "I. Datos demográficos", "info": "Datos básicos de la persona encuestada."},
        {"id": "P4", "title": "II. Percepción ciudadana de seguridad en el distrito", "info": "Percepción y sentimientos asociados a seguridad."},
        {"id": "P5", "title": "III. Riesgos sociales y situacionales en el distrito", "info": "Riesgos observables y condiciones del entorno."},
        {"id": "P6", "title": "Delitos", "info": "Identificación de delitos percibidos/observados."},
        {"id": "P7", "title": "Victimización A: Violencia intrafamiliar", "info": "Módulo de VIF (apartado A)."},
        {"id": "P8", "title": "Victimización B: Otros delitos", "info": "Victimización por otros delitos (apartado B)."},
        {"id": "P9", "title": "Confianza policial", "info": "Confianza y evaluación del servicio policial."},
        {"id": "P10", "title": "Propuestas ciudadanas para mejora de la seguridad", "info": "Propuestas y recomendaciones de la ciudadanía."},
    ]
    st.session_state.pages = pages

    # Inicializa contenedores de preguntas y glosario por página
    for p in pages:
        _ensure_list_dict_key(st.session_state.questions, p["id"], [])
        _ensure_list_dict_key(st.session_state.page_glossary_map, p["id"], [])

    st.session_state.active_page = "P2"


def seed_choices_yesno_if_missing():
    """
    Crea lista yesno mínima (Sí/No).
    """
    if "yesno" not in st.session_state.choices_lists:
        st.session_state.choices_lists["yesno"] = [
            {"name": "si", "label": "Sí"},
            {"name": "no", "label": "No"},
        ]
    if st.session_state.active_list_name is None:
        st.session_state.active_list_name = "yesno"


def seed_minimum_questions_if_empty():
    """
    Para que la app muestre algo desde el inicio.
    (El banco completo REAL con todas tus preguntas se precarga en Parte 3.)
    """
    # P2: consentimiento básico
    qP2 = st.session_state.questions.get("P2", [])
    if not qP2:
        st.session_state.questions["P2"] = [
            {
                "name": "consent_text",
                "label": "Consentimiento Informado para la Participación en la Encuesta",
                "type": "note",
                "required": False,
                "info": "Texto legal visible para la persona encuestada (editable).",
                "choice_list": "",
                "choices_inline": [],
            },
            {
                "name": "consent_acepta",
                "label": "¿Acepta participar en esta encuesta?",
                "type": "select_one",
                "required": True,
                "info": "Selección única.",
                "choice_list": "yesno",
                "choices_inline": [],  # se puede usar inline, pero aquí usamos lista yesno
            },
        ]


# ==========================================================================================
# CRUD: páginas y preguntas
# ==========================================================================================

def get_page_by_id(page_id: str) -> Optional[dict]:
    for p in st.session_state.pages:
        if p["id"] == page_id:
            return p
    return None


def get_questions_for_page(page_id: str) -> List[dict]:
    return st.session_state.questions.get(page_id, [])


def set_questions_for_page(page_id: str, items: List[dict]) -> None:
    st.session_state.questions[page_id] = items


def add_question(page_id: str, q: dict) -> None:
    items = get_questions_for_page(page_id)
    items.append(q)
    set_questions_for_page(page_id, items)


def delete_question(page_id: str, q_name: str) -> None:
    items = get_questions_for_page(page_id)
    items = [x for x in items if x.get("name") != q_name]
    set_questions_for_page(page_id, items)
    if st.session_state.active_question_name == q_name:
        st.session_state.active_question_name = None


def get_question(page_id: str, q_name: str) -> Optional[dict]:
    for q in get_questions_for_page(page_id):
        if q.get("name") == q_name:
            return q
    return None


def upsert_question(page_id: str, q_name: str, new_q: dict) -> None:
    items = get_questions_for_page(page_id)
    found = False
    for i, q in enumerate(items):
        if q.get("name") == q_name:
            items[i] = new_q
            found = True
            break
    if not found:
        items.append(new_q)
    set_questions_for_page(page_id, items)


# ==========================================================================================
# Utilidades para choices (listas)
# ==========================================================================================

def get_choice_labels_for_question(q: dict) -> List[str]:
    """
    Retorna las opciones visibles de una pregunta:
    - Si tiene choices_inline => usa esas
    - Si no, usa la lista referenciada en choice_list (choices_lists)
    """
    inline = q.get("choices_inline") or []
    if inline:
        return [str(x) for x in inline]

    list_name = (q.get("choice_list") or "").strip()
    if list_name and list_name in st.session_state.choices_lists:
        return [row.get("label", "") for row in st.session_state.choices_lists[list_name]]

    return []


def ensure_choice_list(list_name: str) -> None:
    list_name = normalize_name(list_name)
    if list_name not in st.session_state.choices_lists:
        st.session_state.choices_lists[list_name] = []


# ==========================================================================================
# Inicialización
# ==========================================================================================

init_state()
seed_pages_if_empty()
seed_choices_yesno_if_missing()
seed_minimum_questions_if_empty()
# ==========================================================================================
# PARTE 2/10
# Objetivo de esta parte:
# - UI principal
# - Sección Preguntas:
#   - Editor (por página)
#   - Banco completo (ver todas las preguntas y opciones)
# - Sección Choices:
#   - Editor de listas y opciones (editable)
# NOTA: Glosario/Catálogo/Exportar quedan como placeholder (se completan en partes posteriores)
# ==========================================================================================

def header_brand():
    col1, col2 = st.columns([1, 2], vertical_alignment="center")
    with col1:
        st.markdown("### Encuesta comunidad")
        st.caption("Editor XLSForm — banco de preguntas + opciones")
    with col2:
        st.markdown("### Encuesta comunidad – San Carlos Oeste")
        st.caption("Podés cambiar este título luego en la parte de configuración / portada.")


def render_top_config():
    st.markdown("---")
    col1, col2 = st.columns([1, 2], vertical_alignment="top")
    with col1:
        st.markdown("**Logo (PNG/JPG)**")
        st.file_uploader("Subí tu logo", type=["png", "jpg", "jpeg"], key="logo_uploader")
    with col2:
        st.text_input("Nombre del lugar / Delegación", value="San Carlos Oeste", key="place_name")
        st.text_input("Nombre de archivo para media::image", value="001.png", key="logo_filename")


# ==========================================================================================
# Render: Preguntas (Editor por página)
# ==========================================================================================

QUESTION_TYPES = ["text", "integer", "select_one", "select_multiple", "note"]


def render_questions_list(page_id: str):
    qs = get_questions_for_page(page_id)

    if not qs:
        st.info("No hay preguntas en esta página (aún).")
        return

    # Selección de pregunta
    labels = [f"{q.get('name','')} — {q.get('label','')}" for q in qs]
    idx_default = 0
    if st.session_state.active_question_name:
        for i, q in enumerate(qs):
            if q.get("name") == st.session_state.active_question_name:
                idx_default = i
                break

    selected = st.selectbox("Seleccionar pregunta", labels, index=idx_default, key=f"select_q_{page_id}")
    selected_name = selected.split(" — ")[0].strip()
    st.session_state.active_question_name = selected_name

    q = get_question(page_id, selected_name)
    if not q:
        st.warning("No se encontró la pregunta seleccionada.")
        return

    st.markdown("---")
    st.markdown("### ✏️ Editar pregunta")

    colA, colB = st.columns([2, 1], vertical_alignment="top")
    with colA:
        new_label = st.text_input("Título de pregunta (label)", value=q.get("label", ""), key=f"lbl_{page_id}_{selected_name}")
        new_info = st.text_area("Info / ayuda (editable)", value=q.get("info", ""), height=90, key=f"inf_{page_id}_{selected_name}")

    with colB:
        new_name = st.text_input("name (interno)", value=q.get("name", ""), key=f"name_{page_id}_{selected_name}")
        new_type = st.selectbox("type", QUESTION_TYPES, index=QUESTION_TYPES.index(q.get("type", "text")), key=f"type_{page_id}_{selected_name}")
        new_required = st.checkbox("required", value=bool(q.get("required", False)), key=f"req_{page_id}_{selected_name}")

    # Opciones si aplica
    new_choice_list = q.get("choice_list", "")
    new_inline = q.get("choices_inline", []) or []

    if new_type in ("select_one", "select_multiple"):
        st.markdown("#### ✅ Opciones (choices)")
        modo = st.radio(
            "¿Cómo querés manejar las opciones?",
            options=["Usar lista (choice_list)", "Usar opciones inline (por pregunta)"],
            horizontal=True,
            key=f"optmode_{page_id}_{selected_name}",
            index=0 if (q.get("choice_list") or "").strip() else 1,
        )

        if modo == "Usar lista (choice_list)":
            all_lists = sorted(st.session_state.choices_lists.keys())
            if not all_lists:
                all_lists = ["yesno"]
                ensure_choice_list("yesno")

            # Permite elegir o crear
            colx, coly = st.columns([2, 1], vertical_alignment="center")
            with colx:
                picked = st.selectbox("Lista", all_lists, index=all_lists.index(q.get("choice_list", "yesno")) if q.get("choice_list") in all_lists else 0, key=f"picklist_{page_id}_{selected_name}")
                new_choice_list = picked
                new_inline = []  # al usar lista, inline se vacía
            with coly:
                new_list_name = st.text_input("Crear lista nueva", value="", key=f"newlist_{page_id}_{selected_name}")
                if st.button("Crear", key=f"btn_create_list_{page_id}_{selected_name}"):
                    if new_list_name.strip():
                        ln = normalize_name(new_list_name.strip())
                        ensure_choice_list(ln)
                        st.session_state.active_list_name = ln
                        st.success(f"Lista creada: {ln}")

            # Vista previa de opciones de esa lista
            st.markdown("**Vista previa de opciones:**")
            preview_rows = st.session_state.choices_lists.get(new_choice_list, [])
            if not preview_rows:
                st.info("La lista seleccionada no tiene opciones todavía. Agregalas en la sección Choices.")
            else:
                for i, r in enumerate(preview_rows, start=1):
                    st.write(f"{i}. {r.get('label','')}  (`{r.get('name','')}`)")

        else:
            # Inline editor
            new_choice_list = ""
            text_inline = "\n".join([str(x) for x in new_inline]) if new_inline else ""
            text_inline = st.text_area(
                "Pegá una opción por línea (se guardan como texto visible)",
                value=text_inline,
                height=140,
                key=f"inline_{page_id}_{selected_name}",
            )
            new_inline = [x.strip() for x in text_inline.splitlines() if x.strip()]

    # Guardar / eliminar
    colS, colD = st.columns([1, 1], vertical_alignment="center")
    with colS:
        if st.button("💾 Guardar cambios", key=f"save_{page_id}_{selected_name}"):
            fixed_name = normalize_name(new_name)
            new_q = {
                "name": fixed_name,
                "label": new_label,
                "type": new_type,
                "required": bool(new_required),
                "info": new_info,
                "choice_list": new_choice_list,
                "choices_inline": new_inline,
            }
            # Si cambió el name, borramos el viejo y guardamos el nuevo
            if fixed_name != selected_name:
                delete_question(page_id, selected_name)
            upsert_question(page_id, fixed_name, new_q)
            st.session_state.active_question_name = fixed_name
            st.success("Cambios guardados.")

    with colD:
        if st.button("🗑️ Eliminar pregunta", key=f"del_{page_id}_{selected_name}"):
            delete_question(page_id, selected_name)
            st.success("Pregunta eliminada.")


def render_add_question(page_id: str):
    st.markdown("---")
    st.markdown("### ➕ Agregar pregunta")

    col1, col2 = st.columns([2, 1], vertical_alignment="top")
    with col1:
        label = st.text_input("Título (label)", value="", key=f"add_label_{page_id}")
        info = st.text_area("Info / ayuda", value="", height=90, key=f"add_info_{page_id}")
    with col2:
        name = st.text_input("name (interno)", value="", key=f"add_name_{page_id}")
        qtype = st.selectbox("type", QUESTION_TYPES, key=f"add_type_{page_id}")
        required = st.checkbox("required", value=False, key=f"add_req_{page_id}")

    choice_list = ""
    choices_inline = []

    if qtype in ("select_one", "select_multiple"):
        st.markdown("#### ✅ Opciones iniciales")
        modo = st.radio(
            "Modo de opciones",
            options=["Lista (choice_list)", "Inline (por pregunta)"],
            horizontal=True,
            key=f"add_mode_{page_id}",
        )

        if modo == "Lista (choice_list)":
            all_lists = sorted(st.session_state.choices_lists.keys())
            if not all_lists:
                ensure_choice_list("yesno")
                all_lists = ["yesno"]
            choice_list = st.selectbox("Lista", all_lists, key=f"add_picklist_{page_id}")
        else:
            raw = st.text_area("Una opción por línea", value="", height=120, key=f"add_inline_{page_id}")
            choices_inline = [x.strip() for x in raw.splitlines() if x.strip()]

    if st.button("✅ Agregar pregunta", key=f"btn_add_q_{page_id}"):
        if not label.strip():
            st.error("Falta el título (label).")
            return
        if not name.strip():
            name = normalize_name(label)
        q = {
            "name": normalize_name(name),
            "label": label.strip(),
            "type": qtype,
            "required": bool(required),
            "info": info,
            "choice_list": choice_list,
            "choices_inline": choices_inline,
        }
        add_question(page_id, q)
        st.success("Pregunta agregada.")


def render_preguntas():
    st.markdown("## 🧾 Editor de Preguntas (survey)")
    pages = st.session_state.pages  # <- existe siempre (Parte 1 lo garantiza)

    page_labels = [f"{p['id']} — {p.get('title','')}" for p in pages]
    # índice por active_page
    idx = 0
    if st.session_state.active_page:
        for i, p in enumerate(pages):
            if p["id"] == st.session_state.active_page:
                idx = i
                break

    selected_page = st.selectbox("Página", page_labels, index=idx, key="select_page_main")
    page_id = selected_page.split(" — ")[0].strip()
    st.session_state.active_page = page_id

    page = get_page_by_id(page_id)
    if page:
        st.caption(f"**Título:** {page.get('title','')}")
        if (page.get("info") or "").strip():
            st.info(page.get("info"))

    # Buscar en esta página
    query = st.text_input("Buscar en esta página", value="", key=f"search_{page_id}")
    qs = get_questions_for_page(page_id)

    if query.strip():
        qlow = query.strip().lower()
        qs_f = []
        for q in qs:
            hay = f"{q.get('name','')} {q.get('label','')} {q.get('info','')}".lower()
            if qlow in hay:
                qs_f.append(q)
        # render reducido
        if not qs_f:
            st.warning("No hay coincidencias.")
        else:
            st.markdown("### Resultados")
            for i, q in enumerate(qs_f, start=1):
                st.write(f"{i}. **{q.get('label','')}** (`{q.get('name','')}`) — `{q.get('type','')}`")
        st.markdown("---")

    # Lista + editor
    render_questions_list(page_id)
    render_add_question(page_id)


# ==========================================================================================
# Banco completo (ver TODO)
# ==========================================================================================

def render_banco_completo():
    st.markdown("## 📚 Banco completo (todas las páginas, preguntas y opciones)")
    st.caption("Vista para revisar TODO lo cargado. Si algo no aparece aquí, todavía no está precargado en el banco.")

    for p in st.session_state.pages:
        with st.expander(f"{p['id']} — {p.get('title','')}", expanded=False):
            if (p.get("info") or "").strip():
                st.markdown(f"**Info de página:** {p.get('info','')}")

            qs = get_questions_for_page(p["id"])
            if not qs:
                st.info("No hay preguntas en esta página.")
                continue

            for i, q in enumerate(qs, start=1):
                st.markdown(f"### {i}. {q.get('label','(sin título)')}")
                st.markdown(f"- **name:** `{q.get('name','')}`")
                st.markdown(f"- **type:** `{q.get('type','')}`")
                st.markdown(f"- **required:** `{bool(q.get('required', False))}`")

                if (q.get("info") or "").strip():
                    st.markdown(f"- **info:** {q.get('info','')}")

                if q.get("type") in ("select_one", "select_multiple"):
                    cl = (q.get("choice_list") or "").strip()
                    st.markdown(f"- **choice_list:** `{cl}`")

                    opts = get_choice_labels_for_question(q)
                    if opts:
                        st.markdown("**Opciones:**")
                        for j, opt in enumerate(opts, start=1):
                            st.markdown(f"  {j}. {opt}")
                    else:
                        st.warning("Esta pregunta es de selección pero no tiene opciones cargadas.")

                st.markdown("---")


# ==========================================================================================
# Sección Choices (editar listas y opciones)
# ==========================================================================================

def render_choices():
    st.markdown("## 🧩 Editor de Choices (opciones) — fácil para cualquier persona")

    colL, colR = st.columns([1, 2], vertical_alignment="top")

    with colL:
        st.markdown("### 📋 Listas")
        new_list = st.text_input("Crear nueva lista (list_name)", value="", key="create_list_name")
        if st.button("➕ Crear lista", key="btn_create_list"):
            if new_list.strip():
                ln = normalize_name(new_list.strip())
                ensure_choice_list(ln)
                st.session_state.active_list_name = ln
                st.success(f"Lista creada: {ln}")
            else:
                st.error("Escribí un nombre para la lista.")

        all_lists = sorted(st.session_state.choices_lists.keys())
        if not all_lists:
            ensure_choice_list("yesno")
            all_lists = ["yesno"]

        current = st.session_state.active_list_name if st.session_state.active_list_name in all_lists else all_lists[0]
        picked = st.selectbox("Selecciona lista", all_lists, index=all_lists.index(current), key="pick_choice_list")
        st.session_state.active_list_name = picked

        st.markdown("### ⚙️ Acciones de lista")
        if st.button("🧽 Normalizar names", key="btn_norm_names"):
            rows = st.session_state.choices_lists.get(picked, [])
            for r in rows:
                r["name"] = normalize_name(r.get("name") or r.get("label") or "")
            st.session_state.choices_lists[picked] = rows
            st.success("Names normalizados.")

        st.markdown("---")

    with colR:
        list_name = st.session_state.active_list_name
        st.markdown(f"### 🗒️ Opciones en: `{list_name}`")

        rows = st.session_state.choices_lists.get(list_name, [])
        if rows is None:
            rows = []
            st.session_state.choices_lists[list_name] = rows

        # Mostrar editor fila por fila
        if not rows:
            st.info("Esta lista no tiene opciones todavía. Agregalas abajo.")

        for idx, row in enumerate(rows):
            c1, c2, c3, c4 = st.columns([2, 2, 0.6, 0.6], vertical_alignment="center")
            with c1:
                row_label = st.text_input("label (visible)", value=row.get("label", ""), key=f"lbl_{list_name}_{idx}")
            with c2:
                row_name = st.text_input("name (interno)", value=row.get("name", ""), key=f"name_{list_name}_{idx}")
            with c3:
                if st.button("💾", key=f"save_row_{list_name}_{idx}"):
                    rows[idx]["label"] = row_label.strip()
                    rows[idx]["name"] = normalize_name(row_name.strip() or row_label.strip())
                    st.session_state.choices_lists[list_name] = rows
                    st.success("Guardado.")
            with c4:
                if st.button("🗑️", key=f"del_row_{list_name}_{idx}"):
                    rows.pop(idx)
                    st.session_state.choices_lists[list_name] = rows
                    st.success("Eliminado.")
                    st.rerun()

        st.markdown("---")
        st.markdown("### ➕ Agregar opción")
        add_label = st.text_input("Nuevo label", value="", key=f"add_choice_lbl_{list_name}")
        add_name = st.text_input("Nuevo name (opcional)", value="", key=f"add_choice_name_{list_name}")
        if st.button("Agregar", key=f"btn_add_choice_{list_name}"):
            if not add_label.strip():
                st.error("Falta el label.")
            else:
                rows.append(
                    {
                        "label": add_label.strip(),
                        "name": normalize_name(add_name.strip() or add_label.strip()),
                    }
                )
                st.session_state.choices_lists[list_name] = rows
                st.success("Opción agregada.")


# ==========================================================================================
# Placeholders (se completan en partes siguientes)
# ==========================================================================================

def render_placeholder(title: str):
    st.markdown(f"## {title}")
    st.info("Esta sección se completa en las siguientes partes (para mantener el código ordenado por módulos).")


# ==========================================================================================
# UI principal
# ==========================================================================================

header_brand()
render_top_config()

st.markdown("## Sección")

section = st.radio(
    "",
    options=["Preguntas", "Choices", "Glosario", "Catálogo", "Exportar"],
    horizontal=True,
    key="section_main",
)

st.markdown("---")

if section == "Preguntas":
    modo = st.radio(
        "Modo",
        options=["Editor (por página)", "Banco completo (ver todo)"],
        horizontal=True,
        key="modo_preguntas",
    )

    if modo == "Editor (por página)":
        render_preguntas()
    else:
        render_banco_completo()

elif section == "Choices":
    render_choices()

elif section == "Glosario":
    render_placeholder("📘 Glosario (próxima parte)")

elif section == "Catálogo":
    render_placeholder("🗂️ Catálogo (próxima parte)")

elif section == "Exportar":
    render_placeholder("📤 Exportar (próxima parte)")

