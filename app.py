# -*- coding: utf-8 -*-
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 1/10) ==============================
# = App: Editor XLSForm — Encuesta Comunidad 2026 (Páginas) + Banco completo precargado
# ==========================================================================================
#
# OBJETIVO (100% como lo pediste):
# - Editor fácil en Streamlit para ver/editar/reordenar/eliminar preguntas (survey).
# - Editor fácil de choices (listas y opciones).
# - Glosario editable + glosario por página.
# - Catálogo Cantón→Distrito (choice_filter).
# - Exportación XLSForm (survey/choices/settings) listo para Survey123.
#
# REGLAS CRÍTICAS (sin suposiciones):
# - NO se pide subir el DOCX en la UI.
# - El banco completo se precarga leyendo AUTOMÁTICAMENTE el DOCX desde disco (Parte 2).
# - Si el DOCX no existe, la app se detiene con error claro (no queda a medias).
#
# ESTA PARTE 1/10 INCLUYE:
# 1) Imports (únicos, sin duplicados)
# 2) Configuración UI + estilo
# 3) Constantes: páginas P1–P10 (títulos oficiales)
# 4) Helpers base: slugify, nombres únicos, excel export, helpers choices
#
# ==========================================================================================

import re
import json
from io import BytesIO
from datetime import datetime

import streamlit as st
import pandas as pd

# ==========================================================================================
# Configuración UI (mantiene look limpio similar a tu screenshot)
# ==========================================================================================
st.set_page_config(page_title="Editor XLSForm — Encuesta Comunidad 2026", layout="wide")
st.title("🏘️ Editor XLSForm — Encuesta Comunidad 2026 (Páginas)")

st.markdown("""
Este editor permite construir y mantener un XLSForm (Survey123) de manera **amigable**:
- Preguntas (survey) editables, reordenables, duplicables y eliminables.
- Choices (opciones) fáciles de administrar (listas + opciones).
- Glosario editable (global y por página).
- Catálogo Cantón→Distrito con cascada (choice_filter).
- Exportación final a Excel con hojas: **survey**, **choices**, **settings**.
""")

st.markdown("---")

# ==========================================================================================
# Páginas oficiales (P1–P10) — EXACTAS según tu instrucción
# ==========================================================================================
PAGES = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10"]

PAGES_LABELS = {
    "p1": "P1 Introducción",
    "p2": "P2 Consentimiento Informado",
    "p3": "P3 I. DATOS DEMOGRÁFICOS",
    "p4": "P4 II. PERCEPCIÓN CIUDADANA DE SEGURIDAD EN EL DISTRITO",
    "p5": "P5 III. Riesgos sociales y situacionales en el distrito",
    "p6": "P6 III. Delitos",
    "p7": "P7 III. Victimización A: Violencia intrafamiliar",
    "p8": "P8 III. Victimización B: Victimización por otros delitos",
    "p9": "P9 Confianza Policial",
    "p10": "P10 Propuestas ciudadanas para la mejora de la seguridad",
}

# ==========================================================================================
# Helpers generales
# ==========================================================================================
def slugify_name(texto: str) -> str:
    """Convierte texto a un slug válido para XLSForm (name)."""
    if not texto:
        return "campo"
    t = texto.lower()
    t = re.sub(r"[áàäâ]", "a", t)
    t = re.sub(r"[éèëê]", "e", t)
    t = re.sub(r"[íìïî]", "i", t)
    t = re.sub(r"[óòöô]", "o", t)
    t = re.sub(r"[úùüû]", "u", t)
    t = re.sub(r"ñ", "n", t)
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t or "campo"


def asegurar_nombre_unico(base: str, usados: set) -> str:
    """
    Asegura que un name sea único (para no duplicar name en survey).
    Si base ya existe, agrega sufijos _2, _3, etc.
    """
    if base not in usados:
        return base
    i = 2
    while f"{base}_{i}" in usados:
        i += 1
    return f"{base}_{i}"


def _new_qid(prefix: str = "q") -> str:
    """ID único interno para el bank (evita colisiones por reruns)."""
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def descargar_xlsform(df_survey: pd.DataFrame, df_choices: pd.DataFrame, df_settings: pd.DataFrame, nombre_archivo: str):
    """
    Genera y permite descargar el XLSForm en Excel con 3 hojas:
    - survey
    - choices
    - settings
    """
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_survey.to_excel(writer, sheet_name="survey", index=False)
        df_choices.to_excel(writer, sheet_name="choices", index=False)
        df_settings.to_excel(writer, sheet_name="settings", index=False)

        wb = writer.book
        fmt_hdr = wb.add_format({"bold": True, "align": "left"})

        for sheet, df in (("survey", df_survey), ("choices", df_choices), ("settings", df_settings)):
            ws = writer.sheets[sheet]
            ws.freeze_panes(1, 0)
            ws.set_row(0, None, fmt_hdr)
            for col_idx, col_name in enumerate(df.columns):
                ws.set_column(col_idx, col_idx, max(14, min(90, len(str(col_name)) + 10)))

    buffer.seek(0)
    st.download_button(
        label=f"📥 Descargar XLSForm ({nombre_archivo})",
        data=buffer,
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )


def add_choice_list(choices_rows: list[dict], list_name: str, labels: list[str]):
    """
    Agrega choices (list_name/name/label) evitando duplicados.
    - name se genera con slugify(label)
    """
    usados = set((str(r.get("list_name", "")).strip(), str(r.get("name", "")).strip()) for r in choices_rows)
    for lab in labels:
        row = {"list_name": list_name, "name": slugify_name(lab), "label": lab}
        key = (row["list_name"], row["name"])
        if key not in usados:
            choices_rows.append(row)
            usados.add(key)


def ensure_choice_list_exists(choices_rows: list[dict], list_name: str):
    """
    Garantiza que exista al menos 1 fila en choices con ese list_name.
    Esto evita el error de Survey123: "List name not in choices sheet: <list_name>"
    """
    existing_lists = {str(r.get("list_name", "")).strip() for r in choices_rows if str(r.get("list_name", "")).strip()}
    if list_name not in existing_lists:
        choices_rows.append({"list_name": list_name, "name": "placeholder_1", "label": "—"})

# ==========================================================================================
# FIN PARTE 1/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 2/10) ==============================
# =================== Session State + Carga automática del banco completo =================
# ==========================================================================================
#
# ESTA PARTE 2/10 HACE:
# 1) Inicializa bancos:
#    - questions_bank (survey)
#    - choices_bank (choices)
#    - glossary_bank (glosario)
# 2) Carga AUTOMÁTICA el DOCX DESDE DISCO (sin uploader) y construye:
#    - preguntas completas en P1–P10
#    - opciones en choices (listas generadas)
# 3) Si falta el DOCX o falta python-docx, se detiene con error claro.
#
# ==========================================================================================

# ------------------------------------------------------------------------------------------
# Ajuste: nombre exacto del DOCX en el servidor / repo (sin subir en la UI)
# ------------------------------------------------------------------------------------------
DOCX_PATH = "Formato de encuesta Comunidad 2026 V.4.1 cambios generales.docx"

# ------------------------------------------------------------------------------------------
# Session State
# ------------------------------------------------------------------------------------------
def init_state():
    if "questions_bank" not in st.session_state:
        st.session_state.questions_bank = []  # [{"qid","page","order","row"}]
    if "choices_bank" not in st.session_state:
        st.session_state.choices_bank = []    # [{"list_name","name","label",...}]
    if "glossary_bank" not in st.session_state:
        st.session_state.glossary_bank = {}   # {"Termino":"Def..."}

    if "active_page" not in st.session_state:
        st.session_state.active_page = "p1"
    if "selected_qid" not in st.session_state:
        st.session_state.selected_qid = None
    if "editor_mode" not in st.session_state:
        st.session_state.editor_mode = "Simple"

    # Para evitar re-seed infinito:
    if "seed_loaded" not in st.session_state:
        st.session_state.seed_loaded = False

init_state()

# ------------------------------------------------------------------------------------------
# UI encabezado (logo + nombre del lugar)
# ------------------------------------------------------------------------------------------
DEFAULT_LOGO_PATH = "001.png"

col_logo, col_txt = st.columns([1, 3], vertical_alignment="center")

with col_logo:
    up_logo = st.file_uploader("Logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="logo_uploader")
    if up_logo:
        st.image(up_logo, caption="Logo cargado", use_container_width=True)
        st.session_state["_logo_bytes"] = up_logo.getvalue()
        st.session_state["_logo_name"] = up_logo.name
    else:
        try:
            st.image(DEFAULT_LOGO_PATH, caption="Logo (001.png)", use_container_width=True)
            st.session_state["_logo_bytes"] = None
            st.session_state["_logo_name"] = "001.png"
        except Exception:
            st.warning("Sube un logo para incluirlo en el XLSForm.")
            st.session_state["_logo_bytes"] = None
            st.session_state["_logo_name"] = "logo.png"

with col_txt:
    delegacion = st.text_input("Nombre del lugar / Delegación", value="San Carlos Oeste", key="delegacion_input")
    logo_media_name = st.text_input(
        "Nombre de archivo para `media::image`",
        value=st.session_state.get("_logo_name", "001.png"),
        help="Debe coincidir con el archivo dentro de la carpeta `media/` del proyecto Survey123.",
        key="logo_media_name_input"
    )

form_title = f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad"
st.markdown(f"### {form_title}")

# ------------------------------------------------------------------------------------------
# Loader DOCX -> preguntas + choices
# ------------------------------------------------------------------------------------------
def _require_docx_lib():
    try:
        from docx import Document  # noqa
        return True
    except Exception:
        return False


def _read_docx_paragraphs(path: str) -> list[str]:
    from docx import Document
    doc = Document(path)
    paras = []
    for p in doc.paragraphs:
        tx = (p.text or "").strip()
        if tx:
            paras.append(tx)
    return paras


def _is_option_line(t: str) -> bool:
    t = (t or "").strip()
    return t.startswith("( )") or t.startswith("(  )") or t.startswith("☐") or t.startswith("•") or t.startswith("-")


def _clean_option_text(t: str) -> str:
    t = (t or "").strip()
    t = t.replace("( )", "").replace("(  )", "").strip()
    if t.startswith("☐"):
        t = t.replace("☐", "").strip()
    if t.startswith("•"):
        t = t.replace("•", "").strip()
    if t.startswith("-"):
        t = t[1:].strip()
    return t.strip()


def _extract_question_number(t: str) -> str:
    # Ej: "29.3. ¿Cómo valora..." -> "29_3"
    m = re.match(r"^\s*(\d+)\.(\d+)?\.?\s*", t)
    if not m:
        return ""
    a = m.group(1)
    b = m.group(2)
    return f"{a}_{b}" if b else f"{a}"


def _strip_leading_number(t: str) -> str:
    # Quita "29.3." al inicio para dejar el texto de pregunta limpio.
    return re.sub(r"^\s*\d+(\.\d+)?\.?\s*", "", (t or "").strip()).strip()


def _ensure_choices_list_with_seed_keep(list_name: str, labels: list[str]):
    """
    Crea lista y opciones seed si la lista no existe o si solo tiene placeholder.
    Mantiene lo que el usuario ya editó.
    """
    if not list_name:
        return

    # filas actuales de esa lista
    cur = [r for r in st.session_state.choices_bank if str(r.get("list_name","")).strip() == list_name]
    # detecta placeholder único
    has_real = any(str(r.get("name","")).strip() != "placeholder_1" for r in cur)

    if not cur:
        # crear desde cero
        temp = []
        add_choice_list(temp, list_name, labels)
        if not temp:
            temp = [{"list_name": list_name, "name": "placeholder_1", "label": "—"}]
        st.session_state.choices_bank.extend(temp)
        return

    if cur and not has_real:
        # reemplazar placeholder por opciones reales
        st.session_state.choices_bank = [r for r in st.session_state.choices_bank
                                        if not (str(r.get("list_name","")).strip() == list_name and str(r.get("name","")).strip() == "placeholder_1")]
        temp = []
        add_choice_list(temp, list_name, labels)
        if not temp:
            temp = [{"list_name": list_name, "name": "placeholder_1", "label": "—"}]
        st.session_state.choices_bank.extend(temp)


def _build_bank_from_docx(paras: list[str], form_title: str, logo_media_name: str):
    """
    Construye:
    - P1: Intro (note logo + texto intro)
    - P2: Consentimiento + acepta (select_one yesno) + end si No
    - P3..P10: según headings y numeración del documento.
    """
    qb = []
    choices_rows = []

    # base yesno (fijo)
    add_choice_list(choices_rows, "yesno", ["Sí", "No"])

    # CANTÓN/DISTRITO (placeholder por defecto; el catálogo real se mete en pestaña Catálogo)
    ensure_choice_list_exists(choices_rows, "list_canton")
    ensure_choice_list_exists(choices_rows, "list_distrito")

    # map slug de Sí/No
    v_si = slugify_name("Sí")
    v_no = slugify_name("No")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    def add_q(page: str, order: int, row: dict):
        qb.append({"qid": _new_qid("q"), "page": page, "order": order, "row": row})

    # ------------------- localizar consentimiento e intro del doc -------------------
    # En tu DOCX viene el consentimiento y la intro (texto) también.
    # Tomamos lo que existe en el docx sin “inventar”.

    # Buscar bloque de consentimiento (hasta la línea donde está la pregunta acepta)
    idx_accept = None
    for i, t in enumerate(paras):
        if "¿Acepta participar" in t:
            idx_accept = i
            break

    if idx_accept is None:
        raise ValueError("No se encontró la pregunta '¿Acepta participar...?' en el DOCX.")

    consent_title = paras[0].strip()
    consent_block = paras[1:idx_accept]  # textos previos al acepta

    # Buscar texto de introducción (en tu doc aparece después del consentimiento)
    intro_text = None
    for t in paras:
        if t.startswith("Con el fin de hacer más segura nuestra comunidad"):
            intro_text = t.strip()
            break
    if not intro_text:
        intro_text = "Con el fin de hacer más segura nuestra comunidad, deseamos concentrarnos en los problemas de seguridad más importantes."

    # ------------------- P1 Introducción -------------------
    add_q("p1", 10, {"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"})
    add_q("p1", 20, {"type": "note", "name": "p1_logo", "label": form_title, "media::image": logo_media_name, "bind::esri:fieldType": "null"})
    add_q("p1", 30, {"type": "note", "name": "p1_texto", "label": intro_text, "bind::esri:fieldType": "null"})
    add_q("p1", 40, {"type": "end_group", "name": "p1_end", "label": ""})

    # ------------------- P2 Consentimiento -------------------
    add_q("p2", 10, {"type": "begin_group", "name": "p2_consent", "label": "Consentimiento Informado", "appearance": "field-list"})
    add_q("p2", 20, {"type": "note", "name": "p2_titulo", "label": consent_title, "bind::esri:fieldType": "null"})

    o = 30
    for k, t in enumerate(consent_block, start=1):
        # bullets del doc vienen como texto normal; lo mostramos como note
        add_q("p2", o, {"type": "note", "name": f"p2_txt_{k}", "label": t, "bind::esri:fieldType": "null"})
        o += 10

    add_q("p2", o, {"type": "select_one yesno", "name": "acepta_participar", "label": "¿Acepta participar en esta encuesta?", "required": "yes", "appearance": "minimal"})
    o += 10
    add_q("p2", o, {"type": "end_group", "name": "p2_end", "label": ""})
    o += 10
    add_q("p2", o, {"type": "end", "name": "fin_por_no", "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.", "relevant": f"${{acepta_participar}}='{v_no}'"})

    # ------------------- Helpers: crear preguntas desde doc (num + opciones) -------------------
    def add_numbered_question(page: str, order: int, qtext: str, options: list[str], allow_multi: bool):
        used_names = {x.get("row", {}).get("name", "") for x in qb}
        num = _extract_question_number(qtext)
        base_name = f"p{page[1:]}_{num}" if num else slugify_name(qtext)[:30]
        name = asegurar_nombre_unico(slugify_name(base_name), used_names)

        label = qtext.strip()

        if options:
            list_name = f"list_{name}"
            _ensure_choices_list_with_seed_keep(list_name, options)
            qtype = f"select_multiple {list_name}" if allow_multi else f"select_one {list_name}"
            add_q(page, order, {"type": qtype, "name": name, "label": label, "required": "no", "appearance": "minimal", "relevant": rel_si})
        else:
            add_q(page, order, {"type": "text", "name": name, "label": label, "required": "no", "relevant": rel_si})

    # ------------------- Mapeo a páginas por bloques del DOCX -------------------
    # Índices de headings relevantes
    def find_idx(exact: str):
        for i, t in enumerate(paras):
            if t.strip() == exact:
                return i
        return None

    idx_demo = find_idx("I. DATOS DEMOGRÁFICOS")
    idx_perc = find_idx("II. PERCEPCIÓN CIUDADANA DE SEGURIDAD EN EL DISTRITO")
    idx_riesgos = find_idx("Riesgos sociales y situacionales en el distrito")
    idx_delitos = find_idx("Delitos")
    idx_vict = find_idx("Victimización")
    idx_b = find_idx("Apartado B: Victimización por otros delitos")
    idx_conf = find_idx("Confianza Policial")
    idx_prop = find_idx("Propuestas ciudadanas para la mejora de la seguridad")

    # Validación mínima (sin suposiciones)
    required_idxs = [idx_demo, idx_perc, idx_riesgos, idx_delitos, idx_vict, idx_b, idx_conf, idx_prop]
    if any(x is None for x in required_idxs):
        missing = []
        names = ["I. DATOS DEMOGRÁFICOS", "II. PERCEPCIÓN...", "Riesgos...", "Delitos", "Victimización", "Apartado B...", "Confianza Policial", "Propuestas..."]
        for nm, ix in zip(names, required_idxs):
            if ix is None:
                missing.append(nm)
        raise ValueError("Faltan headings en el DOCX (no puedo mapear páginas): " + ", ".join(missing))

    # Bloques por página
    blocks = {
        "p3": (idx_demo, idx_perc),
        "p4": (idx_perc, idx_riesgos),
        "p5": (idx_riesgos, idx_delitos),
        "p6": (idx_delitos, idx_vict),
        "p7": (idx_vict, idx_b),
        "p8": (idx_b, idx_conf),
        "p9": (idx_conf, idx_prop),
        "p10": (idx_prop, len(paras)),
    }

    # P3 fijo incluye cantón/distrito + edad por rangos + género + escolaridad (del doc)
    add_q("p3", 10, {"type": "begin_group", "name": "p3_demograficos", "label": "I. DATOS DEMOGRÁFICOS", "appearance": "field-list", "relevant": rel_si})
    add_q("p3", 20, {"type": "select_one list_canton", "name": "canton", "label": "1. Cantón:", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_q("p3", 30, {"type": "select_one list_distrito", "name": "distrito", "label": "2. Distrito:", "required": "yes", "choice_filter": "canton_key=${canton}", "appearance": "minimal", "relevant": f"({rel_si}) and string-length(${{canton}})>0"})

    # Edad por rangos (del doc)
    edad_opts = ["18 a 29 años", "30 a 44 años", "45 a 64 años", "65 años o más"]
    _ensure_choices_list_with_seed_keep("edad_rango", edad_opts)
    add_q("p3", 40, {"type": "select_one edad_rango", "name": "edad_rango", "label": "3. Edad (en años cumplidos): marque una categoría que incluya su edad.", "required": "yes", "appearance": "minimal", "relevant": rel_si})

    # Género (del doc)
    genero_opts = ["Femenino", "Masculino", "Persona no Binaria", "Prefiero no decir"]
    _ensure_choices_list_with_seed_keep("genero", genero_opts)
    add_q("p3", 50, {"type": "select_one genero", "name": "genero", "label": "4. ¿Con cuál de estas opciones se identifica?", "required": "yes", "appearance": "minimal", "relevant": rel_si})

    # Escolaridad (del doc)
    escolaridad_opts = ["Ninguna", "Primaria incompleta", "Primaria completa", "Secundaria incompleta", "Secundaria completa", "Técnico", "Universitaria incompleta", "Universitaria completa"]
    _ensure_choices_list_with_seed_keep("escolaridad", escolaridad_opts)
    add_q("p3", 60, {"type": "select_one escolaridad", "name": "escolaridad", "label": "5. Escolaridad:", "required": "yes", "appearance": "minimal", "relevant": rel_si})

    add_q("p3", 90, {"type": "end_group", "name": "p3_end", "label": ""})

    # Para el resto de páginas (p4–p10), construimos preguntas numeradas detectando:
    # - línea que empieza con número => pregunta
    # - siguientes líneas "( )" o "☐" => opciones
    # - si hay "selección múltiple" en notas cercanas => select_multiple
    for page_id, (a, b) in blocks.items():
        if page_id == "p3":
            continue

        title = PAGES_LABELS.get(page_id, page_id)
        add_q(page_id, 10, {"type": "begin_group", "name": f"{page_id}_grp", "label": title.split(" ", 1)[1] if " " in title else title, "appearance": "field-list", "relevant": rel_si})

        order = 20
        i = a
        # saltar el heading
        i += 1

        while i < b:
            t = paras[i].strip()

            # ignora notas generales
            if t.lower().startswith("nota"):
                i += 1
                continue

            # detecta pregunta numerada
            if re.match(r"^\s*\d+(\.\d+)?\.?\s*", t):
                qtext = t
                opts = []
                allow_multi = False

                j = i + 1
                # recolectar opciones inmediatas
                while j < b and _is_option_line(paras[j]):
                    opt = _clean_option_text(paras[j])
                    if opt:
                        opts.append(opt)
                    j += 1

                # buscar pista de “selección múltiple” en las siguientes 5 líneas (doc trae nota)
                lookahead = " ".join(paras[j:j+6]).lower()
                if "selección múltiple" in lookahead or "seleccion múltiple" in lookahead:
                    allow_multi = True

                add_numbered_question(page_id, order, qtext, opts, allow_multi)

                order += 10
                i = j
                continue

            i += 1

        add_q(page_id, 9990, {"type": "end_group", "name": f"{page_id}_end", "label": ""})

    return qb, choices_rows


def apply_seed_if_empty():
    """
    Carga el banco completo UNA SOLA VEZ.
    Si ya hay bancos, no los pisa.
    """
    if st.session_state.seed_loaded:
        return

    # si ya hay preguntas (por backup restore), no reseed
    if st.session_state.questions_bank:
        st.session_state.seed_loaded = True
        return

    if not _require_docx_lib():
        st.error("Falta la librería python-docx. Debe estar en requirements.txt como: python-docx")
        st.stop()

    try:
        paras = _read_docx_paragraphs(DOCX_PATH)
    except Exception as e:
        st.error(f"No pude leer el DOCX automáticamente. Verifica que exista en el mismo folder que app.py.\n\nArchivo: {DOCX_PATH}\nError: {e}")
        st.stop()

    try:
        qb, choices_seed = _build_bank_from_docx(paras, form_title=form_title, logo_media_name=logo_media_name)
    except Exception as e:
        st.error(f"El DOCX se leyó, pero no pude construir el banco (estructura inesperada).\nError: {e}")
        st.stop()

    # cargar banks
    st.session_state.questions_bank = qb
    st.session_state.choices_bank = choices_seed

    # glosario base mínimo (se amplía en partes posteriores)
    if not st.session_state.glossary_bank:
        st.session_state.glossary_bank = {}

    # selección inicial
    if st.session_state.questions_bank and not st.session_state.selected_qid:
        st.session_state.selected_qid = st.session_state.questions_bank[0]["qid"]

    st.session_state.seed_loaded = True


# Ejecutar seed automático
apply_seed_if_empty()

# ==========================================================================================
# FIN PARTE 2/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 3/10) ==============================
# ========================= Navegación de Secciones + helpers UI ===========================
# ==========================================================================================

def _get_page_label(page_id: str) -> str:
    return PAGES_LABELS.get(page_id, page_id)

def _get_questions_for_page(page_id: str) -> list[dict]:
    items = [q for q in st.session_state.questions_bank if q.get("page") == page_id]
    return sorted(items, key=lambda x: int(x.get("order", 0)))

def _set_selected_qid(qid: str):
    st.session_state.selected_qid = qid

# ------------------- Barra de Secciones (como tu UI) -------------------
st.markdown("### Sección")
section = st.radio(
    "",
    ["Preguntas", "Choices", "Glosario", "Catálogo", "Exportar"],
    horizontal=True,
    key="section_radio",
    label_visibility="collapsed"
)

st.markdown("---")

# ==========================================================================================
# FIN PARTE 3/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 4/10) ==============================
# =============================== Sección: Preguntas (survey) ==============================
# ==========================================================================================

def _normalize_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default

def _delete_question(qid: str):
    st.session_state.questions_bank = [q for q in st.session_state.questions_bank if q.get("qid") != qid]
    if st.session_state.selected_qid == qid:
        st.session_state.selected_qid = st.session_state.questions_bank[0]["qid"] if st.session_state.questions_bank else None

def _move_question(qid: str, direction: int, page_id: str):
    items = _get_questions_for_page(page_id)
    idx = next((i for i, it in enumerate(items) if it["qid"] == qid), None)
    if idx is None:
        return
    new_idx = idx + direction
    if new_idx < 0 or new_idx >= len(items):
        return
    # swap "order"
    a = items[idx]
    b = items[new_idx]
    ao = _normalize_int(a.get("order", 0))
    bo = _normalize_int(b.get("order", 0))
    a["order"], b["order"] = bo, ao

def _update_question_row(qid: str, new_row: dict):
    for q in st.session_state.questions_bank:
        if q.get("qid") == qid:
            q["row"] = new_row
            return

def _add_new_question(page_id: str):
    # Orden final: max + 10
    items = _get_questions_for_page(page_id)
    max_order = max([_normalize_int(i.get("order", 0)) for i in items], default=0)
    order = max_order + 10
    qid = _new_qid("q")
    row = {
        "type": "text",
        "name": asegurar_nombre_unico(f"{page_id}_nuevo", {x.get("row", {}).get("name", "") for x in st.session_state.questions_bank}),
        "label": "Nueva pregunta",
        "required": "no"
    }
    st.session_state.questions_bank.append({"qid": qid, "page": page_id, "order": order, "row": row})
    st.session_state.selected_qid = qid

if section == "Preguntas":
    st.markdown("## 🧾 Editor de Preguntas (survey) — vista legible + editar")

    colA, colB = st.columns([1.1, 1.9], vertical_alignment="top")

    with colA:
        page_id = st.selectbox(
            "Página",
            PAGES,
            index=PAGES.index(st.session_state.active_page) if st.session_state.active_page in PAGES else 0,
            format_func=_get_page_label,
            key="page_selectbox"
        )
        st.session_state.active_page = page_id

        search_txt = st.text_input("Buscar en esta página", value="", key="q_search")

        page_items = _get_questions_for_page(page_id)
        if search_txt.strip():
            s = search_txt.strip().lower()
            page_items = [
                it for it in page_items
                if s in str(it.get("row", {}).get("label", "")).lower()
                or s in str(it.get("row", {}).get("name", "")).lower()
                or s in str(it.get("row", {}).get("type", "")).lower()
            ]

        if not page_items:
            st.info("No hay preguntas en esta página (aún).")

        st.markdown("### Lista (por orden)")
        for it in page_items:
            row = it.get("row", {})
            label = row.get("label", "")
            t = row.get("type", "")
            nm = row.get("name", "")
            is_sel = (st.session_state.selected_qid == it["qid"])

            c1, c2, c3, c4 = st.columns([0.1, 0.7, 0.1, 0.1], vertical_alignment="center")
            with c1:
                if st.button("▶" if not is_sel else "✅", key=f"sel_{it['qid']}"):
                    _set_selected_qid(it["qid"])
            with c2:
                st.caption(f"**{label}**\n\n`{t}` · `{nm}` · orden {it.get('order')}")
            with c3:
                if st.button("⬆", key=f"up_{it['qid']}"):
                    _move_question(it["qid"], -1, page_id)
            with c4:
                if st.button("⬇", key=f"dn_{it['qid']}"):
                    _move_question(it["qid"], +1, page_id)

        st.markdown("---")
        if st.button("➕ Agregar pregunta", use_container_width=True):
            _add_new_question(page_id)

    with colB:
        st.markdown("### ✏️ Editor de la pregunta seleccionada")

        qid = st.session_state.selected_qid
        selected = next((q for q in st.session_state.questions_bank if q.get("qid") == qid), None)

        if not selected:
            st.warning("Seleccione una pregunta de la lista.")
        else:
            row = dict(selected.get("row", {}))  # copia editable

            # Campos principales XLSForm
            row["type"] = st.text_input("type", value=row.get("type", ""), key=f"type_{qid}")
            row["name"] = st.text_input("name", value=row.get("name", ""), key=f"name_{qid}")
            row["label"] = st.text_area("label", value=row.get("label", ""), height=90, key=f"label_{qid}")

            colx1, colx2, colx3 = st.columns(3)
            with colx1:
                row["required"] = st.selectbox("required", ["no", "yes"], index=1 if row.get("required") == "yes" else 0, key=f"req_{qid}")
            with colx2:
                row["appearance"] = st.text_input("appearance", value=row.get("appearance", ""), key=f"app_{qid}")
            with colx3:
                row["relevant"] = st.text_input("relevant", value=row.get("relevant", ""), key=f"rel_{qid}")

            row["constraint"] = st.text_input("constraint", value=row.get("constraint", ""), key=f"con_{qid}")
            row["constraint_message"] = st.text_input("constraint_message", value=row.get("constraint_message", ""), key=f"conm_{qid}")
            row["calculation"] = st.text_input("calculation", value=row.get("calculation", ""), key=f"calc_{qid}")
            row["choice_filter"] = st.text_input("choice_filter", value=row.get("choice_filter", ""), key=f"cf_{qid}")

            # media opcional
            row["media::image"] = st.text_input("media::image", value=row.get("media::image", ""), key=f"img_{qid}")

            csave, cdel = st.columns([0.7, 0.3])
            with csave:
                if st.button("💾 Guardar cambios", use_container_width=True, key=f"save_{qid}"):
                    # asegurar name único si lo cambiaron
                    used = {x.get("row", {}).get("name", "") for x in st.session_state.questions_bank if x.get("qid") != qid}
                    base = slugify_name(row.get("name", "campo"))
                    row["name"] = asegurar_nombre_unico(base, used)
                    _update_question_row(qid, row)
                    st.success("Guardado.")
            with cdel:
                if st.button("🗑️ Eliminar", use_container_width=True, key=f"del_{qid}"):
                    _delete_question(qid)
                    st.warning("Eliminado.")

# ==========================================================================================
# FIN PARTE 4/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 5/10) ==============================
# =============================== Sección: Choices (choices) ===============================
# ==========================================================================================

def _cb_all_lists() -> list[str]:
    return sorted({
        str(r.get("list_name", "")).strip()
        for r in st.session_state.choices_bank
        if str(r.get("list_name", "")).strip()
    })

def _cb_rows_for_list(list_name: str) -> list[dict]:
    ln = str(list_name or "").strip()
    return [r for r in st.session_state.choices_bank if str(r.get("list_name", "")).strip() == ln]

def _cb_upsert(row: dict):
    ln = str(row.get("list_name", "")).strip()
    nm = str(row.get("name", "")).strip()
    if not ln or not nm:
        return

    for i, r in enumerate(st.session_state.choices_bank):
        if str(r.get("list_name", "")).strip() == ln and str(r.get("name", "")).strip() == nm:
            st.session_state.choices_bank[i] = dict(row)
            return
    st.session_state.choices_bank.append(dict(row))

def _cb_delete(list_name: str, name: str):
    ln = str(list_name or "").strip()
    nm = str(name or "").strip()
    st.session_state.choices_bank = [
        r for r in st.session_state.choices_bank
        if not (str(r.get("list_name", "")).strip() == ln and str(r.get("name", "")).strip() == nm)
    ]

def _cb_ensure_list_placeholder(list_name: str):
    ln = str(list_name or "").strip()
    if not ln:
        return
    rows = _cb_rows_for_list(ln)
    if not rows:
        _cb_upsert({"list_name": ln, "name": "placeholder_1", "label": "—"})

def _cb_rebuild_names(list_name: str):
    ln = str(list_name or "").strip()
    if not ln:
        return
    rows = _cb_rows_for_list(ln)
    used = set()
    for r in rows:
        # No tocar placeholder
        if str(r.get("name", "")).strip() == "placeholder_1" and str(r.get("label", "")).strip() == "—":
            continue
        lab = str(r.get("label", "")).strip()
        base = slugify_name(lab) if lab else "opcion"
        nm = asegurar_nombre_unico(base, used)
        used.add(nm)
        r["name"] = nm

def _cb_rename_list(old: str, new: str):
    o = str(old or "").strip()
    n = str(new or "").strip()
    if not o or not n or o == n:
        return
    for i, r in enumerate(st.session_state.choices_bank):
        if str(r.get("list_name", "")).strip() == o:
            st.session_state.choices_bank[i]["list_name"] = n

def _cb_remove_duplicates():
    """
    Quita duplicados por llave (list_name, name) conservando la primera ocurrencia.
    """
    seen = set()
    new_rows = []
    for r in st.session_state.choices_bank:
        ln = str(r.get("list_name", "")).strip()
        nm = str(r.get("name", "")).strip()
        if not ln or not nm:
            continue
        key = (ln, nm)
        if key in seen:
            continue
        seen.add(key)
        new_rows.append(r)
    st.session_state.choices_bank = new_rows

if section == "Choices":
    st.markdown("## 🧩 Editor de Choices (opciones) — fácil para cualquier persona")

    left, right = st.columns([1.05, 1.95], vertical_alignment="top")

    # ------------------ LEFT: Listas ------------------
    with left:
        st.markdown("### 📚 Listas")

        new_list = st.text_input("Crear nueva lista (list_name)", value="", key="cb_new_list_name")
        if st.button("➕ Crear lista", type="primary", use_container_width=True, key="cb_btn_create_list"):
            if not new_list.strip():
                st.error("Indica un nombre de lista.")
            else:
                _cb_ensure_list_placeholder(new_list.strip())
                st.success("Lista creada.")
                st.rerun()

        lists = _cb_all_lists()
        if not lists:
            # mínimo: asegurar yesno/list_canton/list_distrito
            _cb_ensure_list_placeholder("yesno")
            _cb_ensure_list_placeholder("list_canton")
            _cb_ensure_list_placeholder("list_distrito")
            lists = _cb_all_lists()

        default_sel = "yesno" if "yesno" in lists else lists[0]
        selected_list = st.selectbox("Selecciona lista", options=lists, index=lists.index(default_sel), key="cb_selected_list")

        st.markdown("### ⚙️ Acciones de lista")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🧼 Normalizar names", use_container_width=True, key="cb_btn_norm"):
                _cb_rebuild_names(selected_list)
                st.success("Names normalizados.")
                st.rerun()

        with c2:
            rename_to = st.text_input("Renombrar list_name a", value="", key="cb_rename_to")
            if st.button("✏️ Renombrar", use_container_width=True, key="cb_btn_rename"):
                if not rename_to.strip():
                    st.error("Indica el nuevo nombre.")
                else:
                    _cb_rename_list(selected_list, rename_to.strip())
                    st.success("Lista renombrada.")
                    st.rerun()

        if st.button("🧹 Quitar duplicados (list_name + name)", use_container_width=True, key="cb_btn_dedup"):
            _cb_remove_duplicates()
            st.success("Duplicados eliminados.")
            st.rerun()

        st.markdown("### ➕ Agregar opción")
        opt_label = st.text_input("label (visible)", value="", key="cb_add_label")
        opt_name = st.text_input("name (interno) (opcional)", value="", key="cb_add_name")

        opt_ck = ""
        if selected_list == "list_distrito":
            opt_ck = st.text_input("canton_key (solo list_distrito)", value="", key="cb_add_ck")

        if st.button("Agregar opción", type="primary", use_container_width=True, key="cb_btn_add_opt"):
            if not opt_label.strip():
                st.error("Indica el texto visible (label).")
            else:
                existing = _cb_rows_for_list(selected_list)
                used = {str(r.get("name", "")).strip() for r in existing if str(r.get("name", "")).strip()}
                nm = opt_name.strip() if opt_name.strip() else slugify_name(opt_label.strip())
                nm = asegurar_nombre_unico(nm, used)

                row = {"list_name": selected_list, "name": nm, "label": opt_label.strip()}
                if selected_list == "list_distrito":
                    row["canton_key"] = opt_ck.strip()

                _cb_upsert(row)
                st.success("Opción agregada.")
                st.rerun()

    # ------------------ RIGHT: Opciones ------------------
    with right:
        st.markdown(f"### 🧾 Opciones en: `{selected_list}`")
        rows = _cb_rows_for_list(selected_list)

        if not rows:
            st.info("Esta lista no tiene opciones.")
        else:
            st.caption("Edita texto y campos. Para borrar, usa el botón 🗑.")

            for i, r in enumerate(rows):
                ln = str(r.get("list_name", "")).strip()
                nm = str(r.get("name", "")).strip()
                lb = str(r.get("label", "")).strip()

                base_key = f"cb_{ln}_{nm}_{i}"

                with st.container(border=True):
                    # 2 campos visibles como tu screenshot
                    top = st.columns([2.2, 2.2, 0.9, 0.9], vertical_alignment="center")
                    with top[0]:
                        new_label = st.text_input("label (visible)", value=lb, key=f"{base_key}_lab")
                    with top[1]:
                        new_name = st.text_input("name (interno)", value=nm, key=f"{base_key}_nm")
                    with top[2]:
                        if st.button("💾", use_container_width=True, key=f"{base_key}_save"):
                            # Si cambia name: borrar la fila vieja
                            if new_name.strip() and new_name.strip() != nm:
                                _cb_delete(ln, nm)

                            row_new = dict(r)
                            row_new["label"] = new_label.strip()
                            row_new["name"] = (new_name.strip() if new_name.strip() else nm)

                            if selected_list == "list_distrito":
                                ck_val = st.session_state.get(f"{base_key}_ck", str(r.get("canton_key", "")).strip())
                                row_new["canton_key"] = str(ck_val).strip()

                            _cb_upsert(row_new)
                            st.success("Guardado.")
                            st.rerun()

                    with top[3]:
                        if st.button("🗑", use_container_width=True, key=f"{base_key}_del"):
                            _cb_delete(ln, nm)
                            st.success("Eliminado.")
                            st.rerun()

                    if selected_list == "list_distrito":
                        ck = str(r.get("canton_key", "")).strip()
                        st.text_input("canton_key (para choice_filter)", value=ck, key=f"{base_key}_ck")

            # Nunca dejar listas críticas sin placeholder
            if selected_list in ("yesno", "list_canton", "list_distrito"):
                _cb_ensure_list_placeholder(selected_list)

# ==========================================================================================
# FIN PARTE 5/10
# ==========================================================================================






