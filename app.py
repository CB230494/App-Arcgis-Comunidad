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




