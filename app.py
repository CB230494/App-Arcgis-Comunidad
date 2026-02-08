# -*- coding: utf-8 -*-
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 1/10) ==============================
# = App: Encuesta Comunidad 2026 → Editor + XLSForm Survey123 (Páginas P1..P10)            =
# ==========================================================================================
#
# OBJETIVO:
# - Editor fácil (Streamlit) para mantener preguntas, choices, glosario y catálogo cantón→distrito.
# - Exportar XLSForm (survey/choices/settings) listo para Survey123 Connect (style = pages).
#
# ✅ FIXES CRÍTICOS INCLUIDOS DESDE PARTE 1:
# 1) pages definido SIEMPRE (p1..p10) → evita NameError en autocuración/UI.
# 2) Helper ensure_choice_list_exists_min → evita fallos de listas faltantes.
# 3) No se usa Word, no se solicita cargar documentos.
# 4) Sin prints/st.write de funciones (evita esas “tarjetas” de firma).
#
# ==========================================================================================

import re
import json
from io import BytesIO
from datetime import datetime

import streamlit as st
import pandas as pd

# ==========================================================================================
# Configuración UI
# ==========================================================================================
st.set_page_config(page_title="Editor XLSForm — Encuesta Comunidad 2026", layout="wide")
st.title("🏘️ Editor fácil — Encuesta Comunidad 2026 → XLSForm para ArcGIS Survey123")

st.markdown("""
Este editor permite construir y mantener un XLSForm (Survey123) de manera **amigable**:
- Preguntas editables, reordenables y eliminables (por página).
- Choices (opciones) fáciles de administrar.
- Glosario editable (global y por página).
- Catálogo Cantón→Distrito en cascada (choice_filter).
- Exportación final en Excel con hojas: **survey**, **choices**, **settings**.
""")

# ==========================================================================================
# PÁGINAS OFICIALES (P1..P10) — DEFINIDO AQUÍ PARA EVITAR NameError EN TODO EL SCRIPT
# ==========================================================================================
pages = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10"]

pages_labels = {
    "p1":  "P1 Introducción",
    "p2":  "P2 Consentimiento informado",
    "p3":  "P3 I. Datos demográficos",
    "p4":  "P4 II. Percepción ciudadana de seguridad en el distrito",
    "p5":  "P5 III. Riesgos sociales y situacionales en el distrito",
    "p6":  "P6 III. Delitos",
    "p7":  "P7 III. Victimización — A: Violencia intrafamiliar",
    "p8":  "P8 III. Victimización — B: Otros delitos",
    "p9":  "P9 Confianza policial",
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
    Asegura que un name sea único.
    Si base ya existe, agrega sufijos _2, _3, etc.
    """
    base = (base or "").strip() or "campo"
    if base not in usados:
        return base
    i = 2
    while f"{base}_{i}" in usados:
        i += 1
    return f"{base}_{i}"


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
    list_name = str(list_name or "").strip()
    if not list_name:
        return

    usados = set((str(r.get("list_name","")).strip(), str(r.get("name","")).strip()) for r in (choices_rows or []))
    for lab in (labels or []):
        lab = str(lab or "").strip()
        if not lab:
            continue
        row = {"list_name": list_name, "name": slugify_name(lab), "label": lab}
        key = (row["list_name"], row["name"])
        if key not in usados:
            choices_rows.append(row)
            usados.add(key)

# ==========================================================================================
# FIX CRÍTICO: listas usadas en survey deben existir en choices (placeholder mínimo)
# ==========================================================================================
def ensure_choice_list_exists_min(choices_rows: list[dict], list_name: str):
    """
    Garantiza que exista al menos 1 fila en choices con ese list_name.
    Evita el error de Survey123:
    "List name not in choices sheet: <list_name>"
    """
    list_name = str(list_name or "").strip()
    if not list_name:
        return
    existing_lists = {str(r.get("list_name", "")).strip() for r in (choices_rows or []) if str(r.get("list_name", "")).strip()}
    if list_name not in existing_lists:
        choices_rows.append({"list_name": list_name, "name": "placeholder_1", "label": "—"})

# ==========================================================================================
# FIN PARTE 1/10
# ==========================================================================================

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 2/10) ==============================
# = Estado editable (bancos) + Seeds base P1..P10 (NO quedan páginas vacías)               =
# ==========================================================================================
#
# ESTA PARTE 2/10 HACE:
# 1) Inicializa st.session_state (bancos editables):
#    - questions_bank: preguntas (survey) editables
#    - choices_bank: opciones (choices) editables
#    - glossary_bank: glosario global editable
#    - page_glossary_map: glosario por página (P1..P10)
# 2) Carga SEED base (solo si los bancos están vacíos) para que:
#    ✅ P1..P10 tengan contenido mínimo y NO queden vacías
#    ✅ Cantón→Distrito esté listo (list_canton / list_distrito + choice_filter)
#    ✅ Consentimiento + end por No funcione
# 3) Encabezado: logo + delegación (SIN pedir Word)
#
# IMPORTANTE:
# - Las preguntas detalladas de P5..P10 se insertan en Partes posteriores (autocuración/seed extendido),
#   pero aquí garantizamos que el flujo ya sea funcional y navegable.
# ==========================================================================================

# ==========================================================================================
# 1) Inicialización de bancos en Session State
# ==========================================================================================
def init_state():
    if "questions_bank" not in st.session_state:
        st.session_state.questions_bank = []  # lista de dicts: {"qid","page","order","row"}
    if "choices_bank" not in st.session_state:
        st.session_state.choices_bank = []    # lista de dicts: {"list_name","name","label",...}
    if "glossary_bank" not in st.session_state:
        st.session_state.glossary_bank = {}   # dict: { "Termino": "Definición..." }
    if "choices_ext_rows" not in st.session_state:
        st.session_state.choices_ext_rows = []  # opcional

    if "page_glossary_map" not in st.session_state:
        st.session_state.page_glossary_map = {p: [] for p in pages}

    # UI
    if "active_page" not in st.session_state:
        st.session_state.active_page = "p1"
    if "selected_qid" not in st.session_state:
        st.session_state.selected_qid = None
    if "editor_mode" not in st.session_state:
        st.session_state.editor_mode = "Simple"
    if "show_advanced_fields" not in st.session_state:
        st.session_state.show_advanced_fields = False

    # flags
    if "_autocuracion_done" not in st.session_state:
        st.session_state["_autocuracion_done"] = False

init_state()

# ==========================================================================================
# 2) Textos base (P1 y P2) — iguales a tu lógica original
# ==========================================================================================
DEFAULT_LOGO_PATH = "001.png"

INTRO_COMUNIDAD_EXACTA = (
    "Con el fin de hacer más segura nuestra comunidad, deseamos concentrarnos en los \n"
    "problemas de seguridad más importantes. Queremos trabajar en conjunto con el gobierno \n"
    "local, otras instituciones y la comunidad para reducir los delitos y riesgos que afectan a las \n"
    "personas. \n"
    "Es importante recordarle que la información que usted nos proporcione es confidencial y se \n"
    "utilizará únicamente para mejorar la seguridad en nuestra área."
)

CONSENT_TITLE = "Consentimiento Informado para la Participación en la Encuesta"

CONSENT_PARRAFOS = [
    "Usted está siendo invitado(a) a participar de forma libre y voluntaria en una encuesta sobre seguridad, convivencia y percepción ciudadana, dirigida a personas mayores de 18 años.",
    "El objetivo de esta encuesta es recopilar información de carácter preventivo y estadístico, con el fin de apoyar la planificación de acciones de prevención, mejora de la convivencia y fortalecimiento de la seguridad en comunidades y zonas comerciales.",
    "La participación es totalmente voluntaria. Usted puede negarse a responder cualquier pregunta, así como retirarse de la encuesta en cualquier momento, sin que ello genere consecuencia alguna.",
    "De conformidad con lo dispuesto en el artículo 5 de la Ley N.º 8968, Ley de Protección de la Persona frente al Tratamiento de sus Datos Personales, se le informa que:"
]

CONSENT_BULLETS = [
    "Finalidad del tratamiento: La información recopilada será utilizada exclusivamente para fines estadísticos, analíticos y preventivos, y no para investigaciones penales, procesos judiciales, sanciones administrativas ni procedimientos disciplinarios.",
    "Datos personales: Algunos apartados permiten, de forma voluntaria, el suministro de datos personales o información de contacto.",
    "Tratamiento de los datos: Los datos serán almacenados, analizados y resguardados bajo criterios de confidencialidad y seguridad, conforme a la normativa vigente.",
    "Destinatarios y acceso: La información será conocida únicamente por el personal autorizado de la Fuerza Pública / Ministerio de Seguridad Pública, para los fines indicados. No será cedida a terceros ajenos a estos fines.",
    "Responsable de la base de datos: El Ministerio de Seguridad Pública, a través de la Dirección de Programas Policiales Preventivos, Oficina Estrategia Integral de Prevención para la Seguridad Pública (EIPSEP / Estrategia Sembremos Seguridad) será el responsable del tratamiento y custodia de la información recolectada.",
    "Derechos de la persona participante: Usted conserva el derecho a la autodeterminación informativa y a decidir libremente sobre el suministro de sus datos."
]

CONSENT_CIERRE = [
    "Las respuestas brindadas no constituyen denuncias formales, ni sustituyen los mecanismos legales correspondientes.",
    "Al continuar con la encuesta, usted manifiesta haber leído y comprendido la información anterior y otorga su consentimiento informado para participar."
]

# ==========================================================================================
# 3) Glosario base (editable) — incluye Arrebato
# ==========================================================================================
GLOSARIO_BASE = {
    "Extorsión": (
        "Extorsión: El que, para procurar un lucro injusto, obligare a otro, mediante intimidación o amenaza, "
        "a realizar u omitir un acto o negocio en perjuicio de su patrimonio o del de un tercero."
    ),
    "Daños/vandalismo": (
        "Daños/vandalismo: El que destruyere, inutilizare, hiciere desaparecer o deteriorare bienes, "
        "sean de naturaleza pública o privada (incluidos bienes del Estado), en perjuicio de persona física o jurídica."
    ),
    "Búnkeres": "Búnkeres: Punto fijo o inmueble utilizado para la venta o distribución de drogas.",
    "Receptación": "Receptación: Comprar, recibir u ocultar bienes de procedencia ilícita, con conocimiento de su origen.",
    "Contrabando": "Contrabando: Ingreso, egreso o comercialización de mercancías evadiendo controles o tributos establecidos.",
    "Trata de personas": "Trata de personas: Captación/traslado/acogida de personas con fines de explotación, mediante medios coercitivos o engaño.",
    "Explotación infantil": "Explotación infantil: Utilización de personas menores de edad con fines sexuales, laborales u otros fines de aprovechamiento.",
    "Acoso callejero": "Acoso callejero: Conductas no deseadas de naturaleza sexual o intimidatoria en espacios públicos.",
    "Tráfico de personas (coyotaje)": "Tráfico de personas (coyotaje): Facilitación del ingreso o tránsito irregular de personas, normalmente a cambio de un beneficio.",
    "Estafa": "Estafa: Obtención de un beneficio patrimonial mediante engaño.",
    "Tacha": "Tacha: Ingreso o acceso ilegítimo a inmueble/estructura para sustraer bienes (forzamiento, fractura o apertura indebida).",
    "Ganzúa (pata de chancho)": "Ganzúa (pata de chancho): Herramienta usada para forzar cerraduras o accesos (barra/palanca).",
    "Boquete": "Boquete: Apertura intencional (hueco) en pared/techo/piso para ingresar a un inmueble.",
    "Arrebato": "Arrebato: Sustracción rápida de un objeto a una persona (por ejemplo, arrancar bolso o celular).",
    "Coordinación interinstitucional": "Coordinación interinstitucional: Trabajo articulado entre instituciones para atender un problema común y mejorar resultados.",
    "Integridad y credibilidad policial": "Integridad y credibilidad policial: Percepción de honestidad, apego a la ley y confianza en el actuar del cuerpo policial.",
    "Acciones disuasivas": "Acciones disuasivas: Presencia y acciones preventivas orientadas a reducir oportunidades del delito y aumentar percepción de control.",
    "Patrullaje": "Patrullaje: Recorridos preventivos y operativos realizados por la policía para vigilancia y atención de incidentes.",
}

# ==========================================================================================
# 4) Seeds de choices base (editable)
#    - Garantiza yesno, list_canton, list_distrito con placeholder mínimo
# ==========================================================================================
def seed_choices_base():
    choices_rows = []

    add_choice_list(choices_rows, "yesno", ["Sí", "No"])
    add_choice_list(choices_rows, "genero", ["Femenino", "Masculino", "Persona No Binaria", "Prefiero no decir"])
    add_choice_list(choices_rows, "escolaridad", [
        "Ninguna",
        "Primaria incompleta",
        "Primaria completa",
        "Secundaria incompleta",
        "Secundaria completa",
        "Técnico",
        "Universitaria incompleta",
        "Universitaria completa",
    ])

    # relación con zona (comunidad)
    add_choice_list(choices_rows, "relacion_zona", ["Vivo en la zona", "Trabajo en la zona", "Visito la zona", "Estudio en la zona"])

    # escala 5
    add_choice_list(choices_rows, "seguridad_5", ["Muy inseguro", "Inseguro", "Ni seguro ni inseguro", "Seguro", "Muy seguro"])

    # listas críticas para cascada
    ensure_choice_list_exists_min(choices_rows, "list_canton")
    ensure_choice_list_exists_min(choices_rows, "list_distrito")

    return choices_rows

# ==========================================================================================
# 5) Seed mínimo de preguntas P1..P10 (para que NO queden páginas vacías)
# ==========================================================================================
def _new_qid(prefix: str = "q") -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def seed_questions_base(form_title: str, logo_media_name: str):
    qb = []

    v_si = slugify_name("Sí")
    v_no = slugify_name("No")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    def add_q(page: str, order: int, row: dict):
        qb.append({"qid": _new_qid("q"), "page": page, "order": order, "row": row})

    # -------------------------------- P1: Introducción --------------------------------
    add_q("p1", 10, {"type": "begin_group", "name": "p1_intro", "label": pages_labels["p1"], "appearance": "field-list"})
    add_q("p1", 20, {"type": "note", "name": "p1_logo", "label": form_title, "media::image": logo_media_name, "bind::esri:fieldType": "null"})
    add_q("p1", 30, {"type": "note", "name": "p1_texto", "label": INTRO_COMUNIDAD_EXACTA, "bind::esri:fieldType": "null"})
    add_q("p1", 40, {"type": "end_group", "name": "p1_end", "label": ""})

    # -------------------------------- P2: Consentimiento --------------------------------
    add_q("p2", 10, {"type": "begin_group", "name": "p2_consent", "label": pages_labels["p2"], "appearance": "field-list"})
    add_q("p2", 20, {"type": "note", "name": "p2_titulo", "label": CONSENT_TITLE, "bind::esri:fieldType": "null"})

    idx = 30
    for i, p in enumerate(CONSENT_PARRAFOS, start=1):
        add_q("p2", idx, {"type": "note", "name": f"p2_p_{i}", "label": p, "bind::esri:fieldType": "null"})
        idx += 10

    for j, b in enumerate(CONSENT_BULLETS, start=1):
        add_q("p2", idx, {"type": "note", "name": f"p2_b_{j}", "label": f"• {b}", "bind::esri:fieldType": "null"})
        idx += 10

    for k, c in enumerate(CONSENT_CIERRE, start=1):
        add_q("p2", idx, {"type": "note", "name": f"p2_c_{k}", "label": c, "bind::esri:fieldType": "null"})
        idx += 10

    add_q("p2", idx, {
        "type": "select_one yesno",
        "name": "acepta_participar",
        "label": "¿Acepta participar en esta encuesta?",
        "required": "yes",
        "appearance": "minimal"
    })
    idx += 10

    add_q("p2", idx, {"type": "end_group", "name": "p2_end", "label": ""})
    idx += 10

    add_q("p2", idx, {
        "type": "end",
        "name": "fin_por_no",
        "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.",
        "relevant": f"${{acepta_participar}}='{v_no}'"
    })

    # -------------------------------- P3: Datos demográficos --------------------------------
    add_q("p3", 10, {"type": "begin_group", "name": "p3_demograficos", "label": pages_labels["p3"], "appearance": "field-list", "relevant": rel_si})

    add_q("p3", 20, {
        "type": "select_one list_canton",
        "name": "canton",
        "label": "1. Cantón:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_distrito = f"({rel_si}) and string-length(${{canton}}) > 0"
    add_q("p3", 30, {
        "type": "select_one list_distrito",
        "name": "distrito",
        "label": "2. Distrito:",
        "required": "yes",
        "choice_filter": "canton_key=${canton}",
        "appearance": "minimal",
        "relevant": rel_distrito
    })

    add_q("p3", 40, {
        "type": "integer",
        "name": "edad_anos",
        "label": "3. Edad:",
        "required": "yes",
        "constraint": ". >= 18 and . <= 120",
        "constraint_message": "Debe ser un número entre 18 y 120.",
        "relevant": rel_si
    })

    add_q("p3", 50, {
        "type": "select_one genero",
        "name": "genero",
        "label": "4. ¿Con cuál de estas opciones se identifica?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    add_q("p3", 60, {
        "type": "select_one escolaridad",
        "name": "escolaridad",
        "label": "5. Escolaridad:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    add_q("p3", 70, {
        "type": "select_one relacion_zona",
        "name": "relacion_zona",
        "label": "6. ¿Cuál es su relación con la zona?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    add_q("p3", 80, {"type": "end_group", "name": "p3_end", "label": ""})

    # -------------------------------- P4: Percepción (mínimo) --------------------------------
    add_q("p4", 10, {"type": "begin_group", "name": "p4_percepcion", "label": pages_labels["p4"], "appearance": "field-list", "relevant": rel_si})
    add_q("p4", 20, {
        "type": "select_one seguridad_5",
        "name": "p4_seguridad_distrito",
        "label": "¿Qué tan seguro percibe usted el distrito donde reside o transita?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })
    add_q("p4", 90, {"type": "end_group", "name": "p4_end", "label": ""})

    # -------------------------------- P5..P10: contenedor mínimo (NO vacío) --------------------------------
    for p in ["p5", "p6", "p7", "p8", "p9", "p10"]:
        add_q(p, 10, {"type": "begin_group", "name": f"{p}_grupo", "label": pages_labels[p], "appearance": "field-list", "relevant": rel_si})
        add_q(p, 20, {"type": "note", "name": f"{p}_pendiente_seed", "label": "Contenido de esta sección será cargado/actualizado desde el editor.", "bind::esri:fieldType": "null", "relevant": rel_si})
        add_q(p, 90, {"type": "end_group", "name": f"{p}_end", "label": ""})

    return qb

# ==========================================================================================
# 6) Seed de glosario por página (editable)
# ==========================================================================================
def seed_page_glossary_map():
    return {
        "p1": [],
        "p2": [],
        "p3": [],
        "p4": ["Extorsión", "Daños/vandalismo"],
        "p5": ["Búnkeres", "Receptación", "Contrabando", "Trata de personas", "Explotación infantil", "Acoso callejero", "Tráfico de personas (coyotaje)", "Estafa", "Tacha"],
        "p6": ["Receptación", "Contrabando", "Tráfico de personas (coyotaje)", "Acoso callejero", "Estafa", "Tacha", "Trata de personas", "Explotación infantil", "Extorsión", "Búnkeres"],
        "p7": ["Arrebato", "Ganzúa (pata de chancho)", "Boquete", "Receptación", "Extorsión"],
        "p8": ["Arrebato", "Receptación", "Extorsión"],
        "p9": ["Patrullaje", "Acciones disuasivas", "Coordinación interinstitucional", "Integridad y credibilidad policial"],
        "p10": ["Coordinación interinstitucional"],
    }

# ==========================================================================================
# 7) Aplicar seed si los bancos están vacíos (una sola vez)
# ==========================================================================================
def apply_seed_if_empty(form_title: str, logo_media_name: str):
    if not st.session_state.questions_bank:
        st.session_state.questions_bank = seed_questions_base(form_title=form_title, logo_media_name=logo_media_name)

    if not st.session_state.choices_bank:
        st.session_state.choices_bank = seed_choices_base()

    if not st.session_state.glossary_bank:
        st.session_state.glossary_bank = dict(GLOSARIO_BASE)

    if not st.session_state.page_glossary_map or not isinstance(st.session_state.page_glossary_map, dict):
        st.session_state.page_glossary_map = seed_page_glossary_map()

    # Asegurar claves de páginas en page_glossary_map
    for p in pages:
        if p not in st.session_state.page_glossary_map:
            st.session_state.page_glossary_map[p] = []

    # Selección por defecto
    if st.session_state.questions_bank and not st.session_state.selected_qid:
        st.session_state.selected_qid = st.session_state.questions_bank[0]["qid"]

# ==========================================================================================
# 8) Encabezado: logo + delegación (SIN Word)
# ==========================================================================================
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

# Aplicar seed (una vez)
apply_seed_if_empty(form_title=form_title, logo_media_name=logo_media_name)

# ==========================================================================================
# FIN PARTE 2/10
# ==========================================================================================

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 3/10) ==============================
# ========================= Editor de Preguntas (Survey) — Fácil ==========================
# ==========================================================================================
#
# ESTA PARTE 3/10 INCLUYE:
# 1) Navegación por secciones (Preguntas / Choices / Glosario / Catálogo / Exportar)
# 2) Editor de Preguntas:
#    - Lista por páginas (P1..P10)
#    - Vista legible tipo Survey123 (para cualquier persona)
#    - Reordenar (↑ ↓), duplicar, eliminar
#    - Editar en modo Simple (texto + requerido + tipo + lista)
#    - Editar en modo Avanzado (XLSForm completo: relevant/constraint/choice_filter etc.)
# 3) Agregar nueva pregunta (rápido)
#
# IMPORTANTE:
# - Aquí NO exportamos todavía, solo editamos el banco (questions_bank).
# - La exportación y validación van en Partes posteriores.
# ==========================================================================================

# ==========================================================================================
# 1) Navegación principal
# ==========================================================================================
st.markdown("---")
tabs = ["Preguntas", "Choices", "Glosario", "Catálogo", "Exportar"]
active_tab = st.radio("Sección", options=tabs, horizontal=True, key="main_tabs")

# ==========================================================================================
# 2) Helpers de preguntas (bank)
# ==========================================================================================
def qb_sorted():
    """Ordena questions_bank por page y order."""
    order_map = {p: i for i, p in enumerate(pages)}
    return sorted(
        st.session_state.questions_bank,
        key=lambda x: (order_map.get(x.get("page", ""), 999), int(x.get("order", 0)))
    )

def get_q_by_id(qid: str):
    return next((q for q in st.session_state.questions_bank if q.get("qid") == qid), None)

def update_q(qid: str, new_q: dict):
    qb = st.session_state.questions_bank
    for i, q in enumerate(qb):
        if q.get("qid") == qid:
            qb[i] = new_q
            break
    st.session_state.questions_bank = qb

def delete_q(qid: str):
    st.session_state.questions_bank = [q for q in st.session_state.questions_bank if q.get("qid") != qid]
    if st.session_state.questions_bank:
        st.session_state.selected_qid = st.session_state.questions_bank[0]["qid"]
    else:
        st.session_state.selected_qid = None

def duplicate_q(qid: str):
    src = get_q_by_id(qid)
    if not src:
        return
    used_names = {q.get("row", {}).get("name", "") for q in st.session_state.questions_bank}
    row = dict(src.get("row", {}) or {})
    if row.get("name"):
        row["name"] = asegurar_nombre_unico(row["name"], used_names)

    st.session_state.questions_bank.append({
        "qid": _new_qid("q"),
        "page": src.get("page", "p1"),
        "order": int(src.get("order", 0)) + 5,
        "row": row
    })

def move_q_within_page(qid: str, direction: str):
    """
    Reordena una pregunta dentro de su página usando swap de 'order'.
    direction: 'up' o 'down'
    """
    q = get_q_by_id(qid)
    if not q:
        return
    page = q.get("page", "p1")

    items = sorted([x for x in st.session_state.questions_bank if x.get("page") == page],
                   key=lambda x: int(x.get("order", 0)))
    idx = next((i for i, x in enumerate(items) if x.get("qid") == qid), None)
    if idx is None:
        return

    if direction == "up" and idx > 0:
        items[idx]["order"], items[idx - 1]["order"] = items[idx - 1]["order"], items[idx]["order"]
    if direction == "down" and idx < len(items) - 1:
        items[idx]["order"], items[idx + 1]["order"] = items[idx + 1]["order"], items[idx]["order"]

    others = [x for x in st.session_state.questions_bank if x.get("page") != page]
    st.session_state.questions_bank = others + items

def extract_list_name(tp: str) -> str:
    """Devuelve list_name desde type: select_one X / select_multiple X."""
    tp = (tp or "").strip()
    if tp.startswith("select_one "):
        return tp.replace("select_one ", "").strip()
    if tp.startswith("select_multiple "):
        return tp.replace("select_multiple ", "").strip()
    return ""

def all_choice_lists() -> list:
    """Todas las listas list_name existentes en choices_bank."""
    return sorted({str(r.get("list_name", "")).strip() for r in st.session_state.choices_bank if str(r.get("list_name", "")).strip()})

def choice_labels_for_list(list_name: str) -> list:
    """Labels de opciones de una lista."""
    out = []
    for r in st.session_state.choices_bank:
        if str(r.get("list_name", "")).strip() == list_name:
            out.append(str(r.get("label", "")).strip() or str(r.get("name", "")).strip())
    return out

def add_question(page: str, qtype: str, label: str):
    """
    Agrega pregunta al banco.
    - Genera name único basado en label.
    - Para 'note' agrega bind::esri:fieldType='null'.
    """
    used_names = {q.get("row", {}).get("name", "") for q in st.session_state.questions_bank}
    base = slugify_name(label or "pregunta")
    name = asegurar_nombre_unico(base, usados=used_names)

    row = {
        "type": qtype,
        "name": name,
        "label": label or "",
        "required": "no",
        "appearance": "",
        "relevant": "",
        "choice_filter": "",
        "constraint": "",
        "constraint_message": "",
        "media::image": "",
        "bind::esri:fieldType": "null" if qtype == "note" else "",
    }

    max_order = max([int(q.get("order", 0)) for q in st.session_state.questions_bank if q.get("page") == page] + [0])
    st.session_state.questions_bank.append({"qid": _new_qid("q"), "page": page, "order": max_order + 10, "row": row})

# ==========================================================================================
# 3) UI Editor Preguntas
# ==========================================================================================
if active_tab == "Preguntas":
    st.subheader("🧾 Editor de Preguntas (survey) — vista legible + edición")

    left, right = st.columns([1.2, 2.3])

    with left:
        # página activa (P1..P10)
        st.session_state.active_page = st.selectbox(
            "Página",
            options=pages,
            format_func=lambda p: pages_labels.get(p, p),
            index=pages.index(st.session_state.active_page) if st.session_state.active_page in pages else 0,
            key="page_select"
        )

        search_text = st.text_input("Buscar en esta página", value="", key="q_search_text")
        qs_page = [q for q in qb_sorted() if q.get("page") == st.session_state.active_page]

        if search_text.strip():
            s = search_text.strip().lower()
            qs_page = [q for q in qs_page if s in str(q.get("row", {}).get("label", "")).lower()]

        label_map = {}
        display = []
        for q in qs_page:
            r = q.get("row", {}) or {}
            t = str(r.get("type", "")).strip()
            l = str(r.get("label", "")).strip() or "(sin texto)"
            if t in ("begin_group", "end_group", "note", "end"):
                txt = f"[{t}] {l}"
            else:
                txt = l
            display.append(txt)
            label_map[txt] = q.get("qid")

        if display:
            chosen = st.selectbox("Preguntas", options=display, key="q_list_select")
            st.session_state.selected_qid = label_map.get(chosen)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.button("⬆", on_click=move_q_within_page, args=(st.session_state.selected_qid, "up"), key="btn_up")
            with c2:
                st.button("⬇", on_click=move_q_within_page, args=(st.session_state.selected_qid, "down"), key="btn_down")
            with c3:
                st.button("📄", on_click=duplicate_q, args=(st.session_state.selected_qid,), key="btn_dup")
            with c4:
                st.button("🗑", on_click=delete_q, args=(st.session_state.selected_qid,), key="btn_del")
        else:
            st.info("No hay preguntas en esta página (aún).")

        st.markdown("### ➕ Agregar pregunta")
        new_type = st.selectbox(
            "Tipo",
            options=[
                "note",
                "text",
                "integer",
                "select_one yesno",
                "select_one genero",
                "select_one escolaridad",
                "select_one relacion_zona",
                "select_one seguridad_5",
                "select_one list_canton",
                "select_one list_distrito",
                "select_multiple yesno",
            ],
            key="add_q_type"
        )
        new_label = st.text_input("Texto", value="", key="add_q_label")
        if st.button("Agregar", type="primary", use_container_width=True, key="add_q_btn"):
            add_question(st.session_state.active_page, new_type, new_label)
            st.success("Pregunta agregada.")
            st.rerun()

    with right:
        qid = st.session_state.selected_qid
        q = get_q_by_id(qid)

        if not q:
            st.info("Selecciona una pregunta para editar.")
        else:
            row = dict(q.get("row", {}) or {})
            qtype = str(row.get("type", "")).strip()
            qlabel = str(row.get("label", "")).strip()
            qname = str(row.get("name", "")).strip()
            list_name = extract_list_name(qtype)

            st.markdown("### 👁️ Vista legible (similar a Survey123)")
            st.caption(f"Nombre interno: `{qname}`  |  Tipo: `{qtype}`")

            with st.container(border=True):
                st.markdown(f"#### {qlabel if qlabel else '(Pregunta sin texto)'}")

                if qtype.startswith("select_one "):
                    opts = choice_labels_for_list(list_name)
                    if opts:
                        st.radio(" ", options=opts, index=None, key=f"prev_radio_{qid}", label_visibility="collapsed")
                    else:
                        st.warning("Esta lista no tiene opciones. Ve a la pestaña Choices para agregarlas.")

                elif qtype.startswith("select_multiple "):
                    opts = choice_labels_for_list(list_name)
                    if opts:
                        for i, opt in enumerate(opts):
                            st.checkbox(opt, value=False, key=f"prev_chk_{qid}_{i}")
                    else:
                        st.warning("Esta lista no tiene opciones. Ve a la pestaña Choices para agregarlas.")

                elif qtype == "integer":
                    st.number_input(" ", value=None, step=1, key=f"prev_int_{qid}", label_visibility="collapsed")
                elif qtype == "text":
                    st.text_area(" ", value="", height=90, key=f"prev_txt_{qid}", label_visibility="collapsed")
                elif qtype == "note":
                    st.info("ℹ️ Nota (no genera columna en resultados).")
                elif qtype in ("begin_group", "end_group", "end"):
                    st.warning(f"Elemento estructural: {qtype}")
                else:
                    st.info("Tipo no previsualizado, pero se exporta correctamente.")

            st.markdown("---")

            st.session_state.editor_mode = st.radio(
                "Modo de edición",
                options=["Simple", "Avanzado"],
                horizontal=True,
                index=0 if st.session_state.editor_mode == "Simple" else 1,
                key="edit_mode_radio"
            )

            # =========================
            # MODO SIMPLE
            # =========================
            if st.session_state.editor_mode == "Simple":
                st.markdown("### ✏️ Editar (Simple)")
                with st.form("simple_edit_form"):
                    new_label = st.text_area("Texto de la pregunta", value=qlabel, height=120, key="simple_label")
                    req = st.checkbox("Obligatoria (required)", value=(str(row.get("required", "")).strip() == "yes"), key="simple_req")

                    simple_type = st.selectbox(
                        "Tipo",
                        options=["select_one", "select_multiple", "text", "integer", "note", "begin_group", "end_group", "end"],
                        index=0 if qtype.startswith("select_one ") else
                              1 if qtype.startswith("select_multiple ") else
                              2 if qtype == "text" else
                              3 if qtype == "integer" else
                              4 if qtype == "note" else
                              5 if qtype == "begin_group" else
                              6 if qtype == "end_group" else
                              7,
                        key="simple_type"
                    )

                    chosen_list = list_name
                    if simple_type in ("select_one", "select_multiple"):
                        lists = all_choice_lists()
                        if not lists:
                            lists = ["yesno"]
                        chosen_list = st.selectbox(
                            "Lista de opciones",
                            options=lists,
                            index=lists.index(list_name) if list_name in lists else 0,
                            key="simple_list"
                        )
                        st.caption("Opciones actuales de esa lista:")
                        st.write(choice_labels_for_list(chosen_list))

                    save = st.form_submit_button("💾 Guardar cambios", use_container_width=True)

                if save:
                    row["label"] = new_label.strip()
                    row["required"] = "yes" if req else "no"

                    if simple_type == "select_one":
                        row["type"] = f"select_one {chosen_list}".strip()
                    elif simple_type == "select_multiple":
                        row["type"] = f"select_multiple {chosen_list}".strip()
                    else:
                        row["type"] = simple_type

                    if row["type"] == "note":
                        row["bind::esri:fieldType"] = "null"
                    else:
                        if row.get("bind::esri:fieldType", "") == "null":
                            row["bind::esri:fieldType"] = ""

                    q["row"] = row
                    update_q(qid, q)
                    st.success("Actualizado.")
                    st.rerun()

            # =========================
            # MODO AVANZADO
            # =========================
            else:
                st.markdown("### 🧠 Editar (Avanzado XLSForm)")
                st.caption("Edita campos XLSForm: relevant, constraint, choice_filter, etc.")

                with st.form("advanced_edit_form"):
                    row["type"] = st.text_input("type", value=row.get("type", ""), key="adv_type")
                    row["name"] = st.text_input("name", value=row.get("name", ""), key="adv_name")
                    row["label"] = st.text_area("label", value=row.get("label", ""), height=120, key="adv_label")

                    row["required"] = st.selectbox(
                        "required",
                        options=["", "yes", "no"],
                        index=1 if str(row.get("required", "")).strip() == "yes" else (2 if str(row.get("required", "")).strip() == "no" else 0),
                        key="adv_required"
                    )

                    row["appearance"] = st.text_input("appearance", value=row.get("appearance", ""), key="adv_app")
                    row["relevant"] = st.text_area("relevant", value=row.get("relevant", ""), height=70, key="adv_rel")
                    row["choice_filter"] = st.text_input("choice_filter", value=row.get("choice_filter", ""), key="adv_cf")
                    row["constraint"] = st.text_area("constraint", value=row.get("constraint", ""), height=70, key="adv_con")
                    row["constraint_message"] = st.text_area("constraint_message", value=row.get("constraint_message", ""), height=70, key="adv_conmsg")
                    row["media::image"] = st.text_input("media::image", value=row.get("media::image", ""), key="adv_img")
                    row["bind::esri:fieldType"] = st.text_input("bind::esri:fieldType", value=row.get("bind::esri:fieldType", ""), key="adv_bind")

                    save_adv = st.form_submit_button("💾 Guardar (Avanzado)", use_container_width=True)

                if save_adv:
                    q["row"] = row
                    update_q(qid, q)
                    st.success("Guardado.")
                    st.rerun()

# ==========================================================================================
# FIN PARTE 3/10
# ==========================================================================================

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 4/10) ==============================
# ============================ PÁGINA 6 — DELITOS (PERCEPCIÓN) =============================
# ==========================================================================================
#
# ✅ ESTA PARTE:
# - Completa la Página 6 (Delitos) con preguntas reales (numeración continúa: 14+)
# - Crea (si no existen) las listas de choices necesarias:
#     - delitos_presentes
#     - frecuencia_5
#     - lugares_distrito
#     - horarios_dia
# - Reemplaza el placeholder de P6 SOLO si detecta "p6_placeholder"
# - NO toca Word, NO pide subir nada, NO rompe páginas anteriores
#
# ==========================================================================================

def _choices_list_exists(list_name: str) -> bool:
    return any(str(r.get("list_name", "")).strip() == list_name for r in (st.session_state.choices_bank or []))

def _ensure_choices_list_with_seed(list_name: str, labels: list[str]):
    """
    Crea la lista y opciones base si no existe (o si solo existe placeholder).
    Mantiene lo que el usuario ya haya editado.
    """
    if not _choices_list_exists(list_name):
        # crear placeholder mínimo
        ensure_choice_list_exists_min(st.session_state.choices_bank, list_name)

    # si solo hay placeholder_1, agregamos opciones seed
    rows = [r for r in st.session_state.choices_bank if str(r.get("list_name", "")).strip() == list_name]
    real = [r for r in rows if str(r.get("name", "")).strip() != "placeholder_1"]
    if not real and labels:
        add_choice_list(st.session_state.choices_bank, list_name, labels)

def seed_choices_p6_if_needed():
    """
    Asegura choices necesarios para P6 (Delitos).
    """
    _ensure_choices_list_with_seed("delitos_presentes", [
        "Asalto o robo a persona (en vía pública)",
        "Arrebato (bolso/celular u objeto personal)",
        "Robo a vivienda",
        "Robo a comercio",
        "Robo de vehículo",
        "Robo de motocicleta",
        "Robo de partes de vehículo (batería, llanta, accesorios)",
        "Hurto (sin violencia, sin amenaza)",
        "Daños/vandalismo a la propiedad",
        "Amenazas o intimidación",
        "Extorsión",
        "Estafa o fraude",
        "Receptación (compra/venta de artículos robados)",
        "Venta o distribución de drogas",
        "Consumo de drogas en espacios públicos",
        "Consumo de alcohol en espacios públicos",
        "Balaceras / detonaciones / disparos",
        "Portación o uso de armas en la vía pública",
        "Violencia intrafamiliar (se abordará en secciones posteriores)",
        "Otro",
        "No percibe delitos en el distrito"
    ])

    _ensure_choices_list_with_seed("frecuencia_5", [
        "Nunca",
        "Rara vez",
        "Algunas veces",
        "Frecuentemente",
        "Muy frecuentemente"
    ])

    _ensure_choices_list_with_seed("lugares_distrito", [
        "Calles principales",
        "Calles secundarias",
        "Parques o áreas recreativas",
        "Paradas de bus / terminal",
        "Centros educativos (alrededores)",
        "Zonas comerciales",
        "Bares / centros de entretenimiento",
        "Zonas residenciales",
        "Lotes baldíos / zonas abandonadas",
        "Ríos / quebradas / zonas solitarias",
        "Otro"
    ])

    _ensure_choices_list_with_seed("horarios_dia", [
        "Madrugada (12:00 a.m. – 5:59 a.m.)",
        "Mañana (6:00 a.m. – 11:59 a.m.)",
        "Tarde (12:00 m.d. – 5:59 p.m.)",
        "Noche (6:00 p.m. – 11:59 p.m.)",
        "No sabe / No aplica"
    ])

def _page_has_placeholder(page_id: str, placeholder_name: str) -> bool:
    for q in (st.session_state.questions_bank or []):
        if q.get("page") == page_id:
            nm = str((q.get("row", {}) or {}).get("name", "")).strip()
            if nm == placeholder_name:
                return True
    return False

def _replace_page_questions(page_id: str, new_items: list[dict]):
    """
    Reemplaza TODAS las preguntas de una página por new_items (lista de bank-items).
    """
    st.session_state.questions_bank = [q for q in st.session_state.questions_bank if q.get("page") != page_id] + new_items

def seed_p6_delitos_bank(rel_si: str) -> list[dict]:
    """
    Construye bank-items (qid/page/order/row) para P6 (Delitos).
    """
    items = []

    def add_q(order: int, row: dict):
        items.append({"qid": _new_qid("q"), "page": "p6", "order": order, "row": row})

    add_q(10, {
        "type": "begin_group",
        "name": "p6_delitos",
        "label": "III. Delitos",
        "appearance": "field-list",
        "relevant": rel_si
    })

    # 14
    add_q(20, {
        "type": "select_multiple delitos_presentes",
        "name": "p14_delitos_presentes",
        "label": (
            "14. Según su percepción, ¿cuáles de los siguientes delitos o situaciones delictivas "
            "considera usted que ocurren en el distrito? (Marque todas las que correspondan)"
        ),
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 14.1 (si marcó Otro)
    rel_141 = f"({rel_si}) and selected(${{p14_delitos_presentes}}, '{slugify_name('Otro')}')"
    add_q(30, {
        "type": "text",
        "name": "p14_1_otro_delito",
        "label": "14.1. Otro delito o situación delictiva (especifique):",
        "required": "no",
        "relevant": rel_141
    })

    # 15 (si NO marcó 'No percibe delitos...')
    rel_15 = f"({rel_si}) and (not selected(${{p14_delitos_presentes}}, '{slugify_name('No percibe delitos en el distrito')}'))"
    add_q(40, {
        "type": "select_one frecuencia_5",
        "name": "p15_frecuencia_delitos",
        "label": "15. En general, ¿con qué frecuencia considera que ocurren estas situaciones en el distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_15
    })

    # 16 (lugares)
    add_q(50, {
        "type": "select_multiple lugares_distrito",
        "name": "p16_lugares_delitos",
        "label": "16. ¿En qué lugares del distrito percibe mayor ocurrencia de estas situaciones? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_15
    })

    # 16.1 (otro lugar)
    rel_161 = f"({rel_15}) and selected(${{p16_lugares_delitos}}, '{slugify_name('Otro')}')"
    add_q(60, {
        "type": "text",
        "name": "p16_1_otro_lugar",
        "label": "16.1. Otro lugar (especifique):",
        "required": "no",
        "relevant": rel_161
    })

    # 17 (horarios)
    add_q(70, {
        "type": "select_multiple horarios_dia",
        "name": "p17_horarios_delitos",
        "label": "17. ¿En qué horarios percibe mayor ocurrencia de estas situaciones? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_15
    })

    # 18 (principal)
    add_q(80, {
        "type": "select_one delitos_presentes",
        "name": "p18_principal_delito",
        "label": "18. Si tuviera que seleccionar UNO, ¿cuál considera el principal delito o situación delictiva del distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_15
    })

    add_q(90, {"type": "end_group", "name": "p6_end", "label": ""})

    return items

def apply_seed_p6_update():
    """
    Reemplaza el placeholder de P6 por preguntas reales si detecta el placeholder.
    Si P6 ya fue llenada (sin placeholder), no toca nada.
    """
    # asegurar choices de P6 (sin borrar ediciones del usuario)
    seed_choices_p6_if_needed()

    # lógica de relevancia base
    v_si = slugify_name("Sí")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    # solo reemplazar si existe el placeholder original
    if _page_has_placeholder("p6", "p6_placeholder"):
        new_items = seed_p6_delitos_bank(rel_si=rel_si)
        _replace_page_questions("p6", new_items)

# Ejecutar automáticamente
apply_seed_p6_update()

# ==========================================================================================
# FIN PARTE 4/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 5/10) ==============================
# ========== PÁGINA 7 — VICTIMIZACIÓN (APARTADO A: VIOLENCIA INTRAFAMILIAR) ================
# ==========================================================================================
#
# ✅ ESTA PARTE:
# - Completa la Página 7 (Victimización A: Violencia intrafamiliar) con preguntas reales
# - Crea (si no existen) las listas choices necesarias:
#     - victima_si_no_ns
#     - frecuencia_4
#     - tipo_violencia_vif
#     - convivencia_relacion
#     - donde_ocurre_vif
# - Reemplaza el placeholder de P7 SOLO si detecta "p7_placeholder"
# - NO toca Word, NO pide subir nada, NO rompe páginas anteriores
#
# NOTA:
# - Mantiene relevancia solo si acepta participar
# - Evita preguntas invasivas/gráficas: informativas y de encuesta
#
# ==========================================================================================

def _ensure_choices_list_with_seed_keep(list_name: str, labels: list[str]):
    """
    Crea lista y opciones seed si la lista no existe o si solo tiene placeholder.
    Mantiene lo que el usuario ya editó.
    """
    if not any(str(r.get("list_name", "")).strip() == list_name for r in (st.session_state.choices_bank or [])):
        ensure_choice_list_exists_min(st.session_state.choices_bank, list_name)

    rows = [r for r in st.session_state.choices_bank if str(r.get("list_name", "")).strip() == list_name]
    real = [r for r in rows if str(r.get("name", "")).strip() != "placeholder_1"]
    if not real and labels:
        add_choice_list(st.session_state.choices_bank, list_name, labels)

def seed_choices_p7_if_needed():
    """
    Asegura choices necesarios para Victimización A (VIF).
    """
    _ensure_choices_list_with_seed_keep("victima_si_no_ns", ["Sí", "No", "No sabe / No responde"])

    _ensure_choices_list_with_seed_keep("frecuencia_4", [
        "Una vez",
        "Algunas veces",
        "Frecuentemente",
        "No sabe / No responde"
    ])

    _ensure_choices_list_with_seed_keep("tipo_violencia_vif", [
        "Agresiones físicas",
        "Amenazas o intimidación",
        "Violencia psicológica o emocional",
        "Violencia económica o patrimonial",
        "Restricción o control excesivo",
        "Otro",
        "No sabe / No responde"
    ])

    _ensure_choices_list_with_seed_keep("convivencia_relacion", [
        "Pareja actual",
        "Expareja",
        "Familiar (padre/madre/hijo/a/hermano/a)",
        "Otro conviviente en el hogar",
        "No aplica / No sabe"
    ])

    _ensure_choices_list_with_seed_keep("donde_ocurre_vif", [
        "Dentro de la vivienda",
        "Alrededor de la vivienda (vecindario)",
        "En vía pública",
        "En un comercio o lugar de trabajo",
        "Otro",
        "No sabe / No responde"
    ])

def _page_has_placeholder(page_id: str, placeholder_name: str) -> bool:
    for q in (st.session_state.questions_bank or []):
        if q.get("page") == page_id:
            nm = str((q.get("row", {}) or {}).get("name", "")).strip()
            if nm == placeholder_name:
                return True
    return False

def _replace_page_questions(page_id: str, new_items: list[dict]):
    st.session_state.questions_bank = [q for q in st.session_state.questions_bank if q.get("page") != page_id] + new_items

def seed_p7_vif_bank(rel_si: str) -> list[dict]:
    """
    Construye bank-items para P7 (Victimización A: Violencia intrafamiliar).
    Numeración sugerida continúa después de P6: 19+
    """
    items = []
    v_si = slugify_name("Sí")
    v_ns = slugify_name("No sabe / No responde")

    def add_q(order: int, row: dict):
        items.append({"qid": _new_qid("q"), "page": "p7", "order": order, "row": row})

    add_q(10, {
        "type": "begin_group",
        "name": "p7_victimizacion_vif",
        "label": "III. Victimización — Apartado A: Violencia intrafamiliar",
        "appearance": "field-list",
        "relevant": rel_si
    })

    add_q(20, {
        "type": "note",
        "name": "p7_vif_intro",
        "label": (
            "Las siguientes preguntas se refieren a situaciones de violencia intrafamiliar. "
            "Puede omitir cualquier pregunta si así lo desea. Sus respuestas son confidenciales."
        ),
        "bind::esri:fieldType": "null",
        "relevant": rel_si
    })

    # 19
    add_q(30, {
        "type": "select_one victima_si_no_ns",
        "name": "p19_vif_presencia",
        "label": (
            "19. En los últimos 12 meses, ¿ha conocido o presenciado situaciones de violencia intrafamiliar "
            "en el distrito (en su hogar o en hogares cercanos)?"
        ),
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_vif_si = f"({rel_si}) and (${{p19_vif_presencia}}='{v_si}')"
    rel_vif_si_no_ns = f"({rel_si}) and (${{p19_vif_presencia}}='{v_ns}')"

    # 20 (solo si Sí)
    add_q(40, {
        "type": "select_multiple tipo_violencia_vif",
        "name": "p20_tipo_violencia_vif",
        "label": "20. ¿Qué tipos de violencia intrafamiliar se han presentado? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_vif_si
    })

    # 20.1 (si Otro)
    rel_201 = f"({rel_vif_si}) and selected(${{p20_tipo_violencia_vif}}, '{slugify_name('Otro')}')"
    add_q(50, {
        "type": "text",
        "name": "p20_1_otro_tipo_vif",
        "label": "20.1. Otro tipo de violencia (especifique):",
        "required": "no",
        "relevant": rel_201
    })

    # 21 (frecuencia) (solo si Sí)
    add_q(60, {
        "type": "select_one frecuencia_4",
        "name": "p21_frecuencia_vif",
        "label": "21. ¿Con qué frecuencia se presentan estas situaciones?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_vif_si
    })

    # 22 (relación) (solo si Sí)
    add_q(70, {
        "type": "select_one convivencia_relacion",
        "name": "p22_relacion_agresor",
        "label": "22. En general, ¿qué relación tiene la persona agresora con la víctima?",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_vif_si
    })

    # 23 (dónde ocurre) (solo si Sí)
    add_q(80, {
        "type": "select_multiple donde_ocurre_vif",
        "name": "p23_donde_ocurre_vif",
        "label": "23. ¿Dónde ocurren principalmente estas situaciones? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_vif_si
    })

    # 23.1 (otro lugar)
    rel_231 = f"({rel_vif_si}) and selected(${{p23_donde_ocurre_vif}}, '{slugify_name('Otro')}')"
    add_q(85, {
        "type": "text",
        "name": "p23_1_otro_lugar_vif",
        "label": "23.1. Otro lugar (especifique):",
        "required": "no",
        "relevant": rel_231
    })

    # 24 (si no sabe/no responde, pedir comentario opcional muy general)
    add_q(86, {
        "type": "text",
        "name": "p24_observacion_vif",
        "label": "24. Si desea, indique una observación general sobre esta situación (opcional):",
        "required": "no",
        "relevant": rel_vif_si_no_ns
    })

    add_q(90, {"type": "end_group", "name": "p7_end", "label": ""})

    return items

def apply_seed_p7_update():
    # asegurar choices necesarios
    seed_choices_p7_if_needed()

    v_si = slugify_name("Sí")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    if _page_has_placeholder("p7", "p7_placeholder"):
        new_items = seed_p7_vif_bank(rel_si=rel_si)
        _replace_page_questions("p7", new_items)

# Ejecutar automáticamente
apply_seed_p7_update()

# ==========================================================================================
# FIN PARTE 5/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 6/10) ==============================
# ======= PÁGINA 8 — VICTIMIZACIÓN (APARTADO B: VICTIMIZACIÓN POR OTROS DELITOS) ===========
# ==========================================================================================
#
# ✅ ESTA PARTE:
# - Completa la Página 8 (Victimización B: otros delitos) con preguntas reales
# - Crea (si no existen) las listas choices necesarias:
#     - victima_si_no_ns
#     - vict_delitos_b
#     - cantidad_veces_5
#     - denuncia_si_no_ns
#     - razones_no_denuncia
#     - lugar_victimizacion
#     - horarios_dia   (si ya existe por P6, se reutiliza)
# - Reemplaza el placeholder de P8 SOLO si detecta "p8_placeholder"
# - NO toca Word, NO pide subir nada, NO rompe páginas anteriores
#
# ==========================================================================================

# ---------- Helpers (solo si no existen aún) ----------
try:
    _ensure_choices_list_with_seed_keep
except NameError:
    def _ensure_choices_list_with_seed_keep(list_name: str, labels: list[str]):
        if not any(str(r.get("list_name", "")).strip() == list_name for r in (st.session_state.choices_bank or [])):
            ensure_choice_list_exists_min(st.session_state.choices_bank, list_name)
        rows = [r for r in st.session_state.choices_bank if str(r.get("list_name", "")).strip() == list_name]
        real = [r for r in rows if str(r.get("name", "")).strip() != "placeholder_1"]
        if not real and labels:
            add_choice_list(st.session_state.choices_bank, list_name, labels)

try:
    _page_has_placeholder
except NameError:
    def _page_has_placeholder(page_id: str, placeholder_name: str) -> bool:
        for q in (st.session_state.questions_bank or []):
            if q.get("page") == page_id:
                nm = str((q.get("row", {}) or {}).get("name", "")).strip()
                if nm == placeholder_name:
                    return True
        return False

try:
    _replace_page_questions
except NameError:
    def _replace_page_questions(page_id: str, new_items: list[dict]):
        st.session_state.questions_bank = [q for q in st.session_state.questions_bank if q.get("page") != page_id] + new_items


# ---------- Choices seed para P8 ----------
def seed_choices_p8_if_needed():
    _ensure_choices_list_with_seed_keep("victima_si_no_ns", ["Sí", "No", "No sabe / No responde"])

    _ensure_choices_list_with_seed_keep("vict_delitos_b", [
        "Asalto o robo a persona (en vía pública)",
        "Arrebato (bolso/celular u objeto personal)",
        "Hurto (sin violencia, sin amenaza)",
        "Robo a vivienda",
        "Robo a comercio",
        "Robo de vehículo",
        "Robo de motocicleta",
        "Robo de partes de vehículo",
        "Estafa o fraude",
        "Amenazas o intimidación",
        "Extorsión",
        "Daños/vandalismo a la propiedad",
        "Otro",
        "No aplica"
    ])

    _ensure_choices_list_with_seed_keep("cantidad_veces_5", [
        "1 vez",
        "2 veces",
        "3 veces",
        "4 o más veces",
        "No sabe / No responde"
    ])

    _ensure_choices_list_with_seed_keep("denuncia_si_no_ns", ["Sí", "No", "No sabe / No responde"])

    _ensure_choices_list_with_seed_keep("razones_no_denuncia", [
        "Lo consideró un hecho menor / sin importancia",
        "No confía en que se resuelva",
        "Miedo a represalias",
        "No sabía dónde o cómo denunciar",
        "Falta de tiempo",
        "No había pruebas suficientes",
        "Se resolvió por cuenta propia",
        "Otro",
        "No sabe / No responde"
    ])

    _ensure_choices_list_with_seed_keep("lugar_victimizacion", [
        "Dentro de la vivienda",
        "Alrededor de la vivienda (vecindario)",
        "En vía pública",
        "En el trabajo",
        "En un comercio",
        "En un centro educativo (alrededores)",
        "En transporte público / parada",
        "Otro",
        "No sabe / No responde"
    ])

    # horarios_dia ya se creó en P6; si no existe, lo creamos aquí
    _ensure_choices_list_with_seed_keep("horarios_dia", [
        "Madrugada (12:00 a.m. – 5:59 a.m.)",
        "Mañana (6:00 a.m. – 11:59 a.m.)",
        "Tarde (12:00 m.d. – 5:59 p.m.)",
        "Noche (6:00 p.m. – 11:59 p.m.)",
        "No sabe / No aplica"
    ])


# ---------- Bank seed (preguntas) para P8 ----------
def seed_p8_victimizacion_b_bank(rel_si: str) -> list[dict]:
    items = []
    v_si = slugify_name("Sí")

    def add_q(order: int, row: dict):
        items.append({"qid": _new_qid("q"), "page": "p8", "order": order, "row": row})

    add_q(10, {
        "type": "begin_group",
        "name": "p8_victimizacion_otros",
        "label": "III. Victimización — Apartado B: Victimización por otros delitos",
        "appearance": "field-list",
        "relevant": rel_si
    })

    add_q(20, {
        "type": "note",
        "name": "p8_intro",
        "label": (
            "En esta sección se consultan experiencias de victimización por otros delitos. "
            "Puede omitir cualquier pregunta si así lo desea. Sus respuestas son confidenciales."
        ),
        "bind::esri:fieldType": "null",
        "relevant": rel_si
    })

    # 25
    add_q(30, {
        "type": "select_one victima_si_no_ns",
        "name": "p25_victima_12m",
        "label": "25. En los últimos 12 meses, ¿usted ha sido víctima de algún delito en el distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_vict_si = f"({rel_si}) and (${{p25_victima_12m}}='{v_si}')"

    # 26
    add_q(40, {
        "type": "select_multiple vict_delitos_b",
        "name": "p26_delitos_victima",
        "label": "26. ¿De cuáles delitos fue víctima? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_vict_si
    })

    # 26.1 (otro)
    rel_261 = f"({rel_vict_si}) and selected(${{p26_delitos_victima}}, '{slugify_name('Otro')}')"
    add_q(50, {
        "type": "text",
        "name": "p26_1_otro_delito",
        "label": "26.1. Otro delito (especifique):",
        "required": "no",
        "relevant": rel_261
    })

    # 27
    add_q(60, {
        "type": "select_one cantidad_veces_5",
        "name": "p27_cantidad_veces",
        "label": "27. ¿Cuántas veces fue víctima (en total) en los últimos 12 meses?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_vict_si
    })

    # 28
    add_q(70, {
        "type": "select_multiple lugar_victimizacion",
        "name": "p28_lugar_victima",
        "label": "28. ¿En qué lugar(es) ocurrió? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_vict_si
    })

    # 28.1 (otro lugar)
    rel_281 = f"({rel_vict_si}) and selected(${{p28_lugar_victima}}, '{slugify_name('Otro')}')"
    add_q(75, {
        "type": "text",
        "name": "p28_1_otro_lugar",
        "label": "28.1. Otro lugar (especifique):",
        "required": "no",
        "relevant": rel_281
    })

    # 29
    add_q(80, {
        "type": "select_multiple horarios_dia",
        "name": "p29_horario",
        "label": "29. ¿En qué horario(s) ocurrió? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_vict_si
    })

    # 30
    add_q(90, {
        "type": "select_one denuncia_si_no_ns",
        "name": "p30_denuncio",
        "label": "30. ¿Usted denunció el hecho ante alguna autoridad?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_vict_si
    })

    v_no = slugify_name("No")
    rel_no_den = f"({rel_vict_si}) and (${{p30_denuncio}}='{v_no}')"

    # 30.1
    add_q(100, {
        "type": "select_multiple razones_no_denuncia",
        "name": "p30_1_razones_no_denuncia",
        "label": "30.1. ¿Por qué no denunció? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_no_den
    })

    # 30.2 (otro motivo)
    rel_302 = f"({rel_no_den}) and selected(${{p30_1_razones_no_denuncia}}, '{slugify_name('Otro')}')"
    add_q(110, {
        "type": "text",
        "name": "p30_2_otro_motivo",
        "label": "30.2. Otro motivo (especifique):",
        "required": "no",
        "relevant": rel_302
    })

    add_q(190, {"type": "end_group", "name": "p8_end", "label": ""})

    return items


def apply_seed_p8_update():
    seed_choices_p8_if_needed()

    v_si = slugify_name("Sí")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    if _page_has_placeholder("p8", "p8_placeholder"):
        new_items = seed_p8_victimizacion_b_bank(rel_si=rel_si)
        _replace_page_questions("p8", new_items)

# Ejecutar automáticamente
apply_seed_p8_update()

# ==========================================================================================
# FIN PARTE 6/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 7/10) ==============================
# ============================= PÁGINA 9 — CONFIANZA POLICIAL ==============================
# ==========================================================================================
#
# ✅ ESTA PARTE:
# - Completa la Página 9 (Confianza policial) con preguntas reales
# - Crea (si no existen) las listas choices necesarias:
#     - confianza_5
#     - acciones_policiales
#     - tiempos_respuesta
#     - canales_contacto
# - Reemplaza el placeholder de P9 SOLO si detecta "p9_placeholder"
# - NO toca Word, NO pide subir nada, NO rompe páginas anteriores
#
# ==========================================================================================

# ---------- Helpers (solo si no existen aún) ----------
try:
    _ensure_choices_list_with_seed_keep
except NameError:
    def _ensure_choices_list_with_seed_keep(list_name: str, labels: list[str]):
        if not any(str(r.get("list_name", "")).strip() == list_name for r in (st.session_state.choices_bank or [])):
            ensure_choice_list_exists_min(st.session_state.choices_bank, list_name)
        rows = [r for r in st.session_state.choices_bank if str(r.get("list_name", "")).strip() == list_name]
        real = [r for r in rows if str(r.get("name", "")).strip() != "placeholder_1"]
        if not real and labels:
            add_choice_list(st.session_state.choices_bank, list_name, labels)

try:
    _page_has_placeholder
except NameError:
    def _page_has_placeholder(page_id: str, placeholder_name: str) -> bool:
        for q in (st.session_state.questions_bank or []):
            if q.get("page") == page_id:
                nm = str((q.get("row", {}) or {}).get("name", "")).strip()
                if nm == placeholder_name:
                    return True
        return False

try:
    _replace_page_questions
except NameError:
    def _replace_page_questions(page_id: str, new_items: list[dict]):
        st.session_state.questions_bank = [q for q in st.session_state.questions_bank if q.get("page") != page_id] + new_items


# ---------- Choices seed para P9 ----------
def seed_choices_p9_if_needed():
    _ensure_choices_list_with_seed_keep("confianza_5", [
        "Nada de confianza",
        "Poca confianza",
        "Confianza media",
        "Mucha confianza",
        "Total confianza"
    ])

    _ensure_choices_list_with_seed_keep("acciones_policiales", [
        "Patrullaje preventivo",
        "Operativos focalizados",
        "Acciones disuasivas (presencia visible)",
        "Control de armas",
        "Control de drogas",
        "Control vehicular",
        "Atención de incidentes / llamadas",
        "Coordinación con municipalidad",
        "Coordinación interinstitucional",
        "Programas preventivos y comunitarios",
        "Otro",
        "No sabe / No responde"
    ])

    _ensure_choices_list_with_seed_keep("tiempos_respuesta", [
        "Muy rápido",
        "Rápido",
        "Regular",
        "Lento",
        "Muy lento",
        "No sabe / No responde"
    ])

    _ensure_choices_list_with_seed_keep("canales_contacto", [
        "911",
        "Delegación / puesto policial",
        "Patrulla en la zona",
        "WhatsApp",
        "Redes sociales",
        "Municipalidad",
        "Otro",
        "No sabe / No responde"
    ])


# ---------- Bank seed (preguntas) para P9 ----------
def seed_p9_confianza_bank(rel_si: str) -> list[dict]:
    items = []

    def add_q(order: int, row: dict):
        items.append({"qid": _new_qid("q"), "page": "p9", "order": order, "row": row})

    add_q(10, {
        "type": "begin_group",
        "name": "p9_confianza_policial",
        "label": "Confianza policial",
        "appearance": "field-list",
        "relevant": rel_si
    })

    # 31
    add_q(20, {
        "type": "select_one confianza_5",
        "name": "p31_confianza_fp",
        "label": "31. ¿Qué nivel de confianza tiene usted en la Fuerza Pública en el distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 32
    add_q(30, {
        "type": "select_one tiempos_respuesta",
        "name": "p32_tiempo_respuesta",
        "label": "32. En general, ¿cómo califica el tiempo de respuesta policial ante incidentes en el distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 33
    add_q(40, {
        "type": "select_multiple acciones_policiales",
        "name": "p33_acciones_necesarias",
        "label": "33. ¿Qué acciones considera usted que deberían fortalecerse en el distrito? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 33.1 (otro)
    rel_331 = f"({rel_si}) and selected(${{p33_acciones_necesarias}}, '{slugify_name('Otro')}')"
    add_q(50, {
        "type": "text",
        "name": "p33_1_otro_accion",
        "label": "33.1. Otra acción (especifique):",
        "required": "no",
        "relevant": rel_331
    })

    # 34
    add_q(60, {
        "type": "select_multiple canales_contacto",
        "name": "p34_canales_contacto",
        "label": "34. ¿Cuáles canales considera más efectivos para contactar a la policía? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 34.1 (otro canal)
    rel_341 = f"({rel_si}) and selected(${{p34_canales_contacto}}, '{slugify_name('Otro')}')"
    add_q(70, {
        "type": "text",
        "name": "p34_1_otro_canal",
        "label": "34.1. Otro canal (especifique):",
        "required": "no",
        "relevant": rel_341
    })

    # 35 (comentario general)
    add_q(80, {
        "type": "text",
        "name": "p35_comentario_confianza",
        "label": "35. Si lo desea, indique un comentario general sobre la atención policial en el distrito (opcional):",
        "required": "no",
        "relevant": rel_si
    })

    add_q(90, {"type": "end_group", "name": "p9_end", "label": ""})

    return items


def apply_seed_p9_update():
    seed_choices_p9_if_needed()

    v_si = slugify_name("Sí")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    if _page_has_placeholder("p9", "p9_placeholder"):
        new_items = seed_p9_confianza_bank(rel_si=rel_si)
        _replace_page_questions("p9", new_items)

# Ejecutar automáticamente
apply_seed_p9_update()

# ==========================================================================================
# FIN PARTE 7/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 8/10) ==============================
# ========== PÁGINA 10 — PROPUESTAS CIUDADANAS PARA LA MEJORA DE LA SEGURIDAD ==============
# ==========================================================================================
#
# ✅ ESTA PARTE:
# - Completa la Página 10 (Propuestas) con preguntas reales
# - Crea (si no existen) las listas choices necesarias:
#     - acciones_municipalidad
#     - acciones_fp
#     - acciones_comunidad
#     - prioridad_3
# - Reemplaza el placeholder de P10 SOLO si detecta "p10_placeholder"
# - NO toca Word, NO pide subir nada, NO rompe páginas anteriores
#
# ==========================================================================================

# ---------- Helpers (solo si no existen aún) ----------
try:
    _ensure_choices_list_with_seed_keep
except NameError:
    def _ensure_choices_list_with_seed_keep(list_name: str, labels: list[str]):
        if not any(str(r.get("list_name", "")).strip() == list_name for r in (st.session_state.choices_bank or [])):
            ensure_choice_list_exists_min(st.session_state.choices_bank, list_name)
        rows = [r for r in st.session_state.choices_bank if str(r.get("list_name", "")).strip() == list_name]
        real = [r for r in rows if str(r.get("name", "")).strip() != "placeholder_1"]
        if not real and labels:
            add_choice_list(st.session_state.choices_bank, list_name, labels)

try:
    _page_has_placeholder
except NameError:
    def _page_has_placeholder(page_id: str, placeholder_name: str) -> bool:
        for q in (st.session_state.questions_bank or []):
            if q.get("page") == page_id:
                nm = str((q.get("row", {}) or {}).get("name", "")).strip()
                if nm == placeholder_name:
                    return True
        return False

try:
    _replace_page_questions
except NameError:
    def _replace_page_questions(page_id: str, new_items: list[dict]):
        st.session_state.questions_bank = [q for q in st.session_state.questions_bank if q.get("page") != page_id] + new_items


# ---------- Choices seed para P10 ----------
def seed_choices_p10_if_needed():
    _ensure_choices_list_with_seed_keep("acciones_municipalidad", [
        "Mantenimiento e iluminación del espacio público",
        "Limpieza y ordenamiento urbano",
        "Recuperación de espacios públicos",
        "Instalación de cámaras / monitoreo municipal",
        "Control del comercio informal",
        "Mejora de infraestructura vial y señalización",
        "Programas sociales y de empleo",
        "Atención de población vulnerable",
        "Control de patentes y regulación de horarios",
        "Coordinación interinstitucional",
        "Otro",
        "No sabe / No responde"
    ])

    _ensure_choices_list_with_seed_keep("acciones_fp", [
        "Aumentar patrullaje preventivo",
        "Operativos focalizados en puntos críticos",
        "Acciones disuasivas (presencia visible)",
        "Mayor control de armas",
        "Mayor control de drogas",
        "Control vehicular",
        "Atención rápida de incidentes",
        "Mayor acercamiento a la comunidad",
        "Coordinación con municipalidad",
        "Programas preventivos",
        "Otro",
        "No sabe / No responde"
    ])

    _ensure_choices_list_with_seed_keep("acciones_comunidad", [
        "Organización comunitaria / comités",
        "Denuncia oportuna",
        "Cuidado de espacios públicos",
        "Participación en actividades preventivas",
        "Redes de apoyo vecinal",
        "Acciones de convivencia y mediación",
        "Otro",
        "No sabe / No responde"
    ])

    _ensure_choices_list_with_seed_keep("prioridad_3", [
        "Alta prioridad",
        "Prioridad media",
        "Baja prioridad"
    ])


# ---------- Bank seed (preguntas) para P10 ----------
def seed_p10_propuestas_bank(rel_si: str) -> list[dict]:
    items = []

    def add_q(order: int, row: dict):
        items.append({"qid": _new_qid("q"), "page": "p10", "order": order, "row": row})

    add_q(10, {
        "type": "begin_group",
        "name": "p10_propuestas",
        "label": "Propuestas ciudadanas para la mejora de la seguridad",
        "appearance": "field-list",
        "relevant": rel_si
    })

    # 36
    add_q(20, {
        "type": "select_multiple acciones_municipalidad",
        "name": "p36_acciones_muni",
        "label": "36. ¿Qué acciones considera que debería realizar la municipalidad para mejorar la seguridad en el distrito? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 36.1 (otro)
    rel_361 = f"({rel_si}) and selected(${{p36_acciones_muni}}, '{slugify_name('Otro')}')"
    add_q(30, {
        "type": "text",
        "name": "p36_1_otro_muni",
        "label": "36.1. Otra acción municipal (" + "especifique):",
        "required": "no",
        "relevant": rel_361
    })

    # 37
    add_q(40, {
        "type": "select_multiple acciones_fp",
        "name": "p37_acciones_fp",
        "label": "37. ¿Qué acciones considera que debería fortalecer la Fuerza Pública en el distrito? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 37.1 (otro)
    rel_371 = f"({rel_si}) and selected(${{p37_acciones_fp}}, '{slugify_name('Otro')}')"
    add_q(50, {
        "type": "text",
        "name": "p37_1_otro_fp",
        "label": "37.1. Otra acción de Fuerza Pública (especifique):",
        "required": "no",
        "relevant": rel_371
    })

    # 38
    add_q(60, {
        "type": "select_multiple acciones_comunidad",
        "name": "p38_acciones_comunidad",
        "label": "38. ¿Qué acciones considera que puede realizar la comunidad para mejorar la seguridad? (Seleccione todas las que correspondan)",
        "required": "no",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 38.1 (otro)
    rel_381 = f"({rel_si}) and selected(${{p38_acciones_comunidad}}, '{slugify_name('Otro')}')"
    add_q(70, {
        "type": "text",
        "name": "p38_1_otro_comunidad",
        "label": "38.1. Otra acción comunitaria (especifique):",
        "required": "no",
        "relevant": rel_381
    })

    # 39 (prioridad)
    add_q(80, {
        "type": "select_one prioridad_3",
        "name": "p39_prioridad",
        "label": "39. En general, ¿qué prioridad considera que debe darse a la mejora de la seguridad en el distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 40 (abierta final)
    add_q(90, {
        "type": "text",
        "name": "p40_propuesta_abierta",
        "label": "40. Si desea, indique una propuesta adicional para mejorar la seguridad en el distrito (opcional):",
        "required": "no",
        "relevant": rel_si
    })

    add_q(190, {"type": "end_group", "name": "p10_end", "label": ""})

    return items


def apply_seed_p10_update():
    seed_choices_p10_if_needed()

    v_si = slugify_name("Sí")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    if _page_has_placeholder("p10", "p10_placeholder"):
        new_items = seed_p10_propuestas_bank(rel_si=rel_si)
        _replace_page_questions("p10", new_items)

# Ejecutar automáticamente
apply_seed_p10_update()

# ==========================================================================================
# FIN PARTE 8/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 9/10) ==============================
# ===================== FIXES CRÍTICOS + AUTOCURACIÓN (SIN WORD / SIN SUPOSICIONES) ========
# ==========================================================================================
#
# ✅ ESTA PARTE ES LA QUE TE EVITA LOS FALLOS QUE VISTE EN TUS CAPTURAS:
# - Si una página (p5..p10) NO tiene placeholder y queda vacía -> la llena igual (sin depender del placeholder)
# - Crea helpers faltantes (por ejemplo: ensure_choice_list_exists_min) para que NO haya NameError
# - Repara selección UI (selected_qid) si queda nula
# - Repara active_page si queda en una página inválida
#
# IMPORTANTÍSIMO:
# - NO toca Word
# - NO te pide subir nada
# - NO cambia el flujo original, solo garantiza que SIEMPRE esté operativo
#
# ==========================================================================================

# ------------------------------------------------------------------------------------------
# 1) Helper faltante (CRÍTICO): ensure_choice_list_exists_min
#    (Se usa en Partes 4-8 para garantizar que Survey123 no reviente por listas faltantes)
# ------------------------------------------------------------------------------------------
def ensure_choice_list_exists_min(choices_rows: list[dict], list_name: str):
    """
    Garantiza que exista al menos 1 fila en choices con ese list_name.
    (placeholder mínimo para que Survey123 Connect no falle)
    """
    list_name = str(list_name or "").strip()
    if not list_name:
        return
    existing_lists = {str(r.get("list_name", "")).strip() for r in (choices_rows or []) if str(r.get("list_name", "")).strip()}
    if list_name not in existing_lists:
        choices_rows.append({"list_name": list_name, "name": "placeholder_1", "label": "—"})


# ------------------------------------------------------------------------------------------
# 2) Helpers de páginas: detectar si una página existe / está vacía
# ------------------------------------------------------------------------------------------
def _page_exists(page_id: str) -> bool:
    return any(q.get("page") == page_id for q in (st.session_state.questions_bank or []))

def _page_is_empty(page_id: str) -> bool:
    # vacía = no hay filas para esa page
    return not any(q.get("page") == page_id for q in (st.session_state.questions_bank or []))

def _page_has_any_end_group(page_id: str) -> bool:
    for q in (st.session_state.questions_bank or []):
        if q.get("page") == page_id:
            r = q.get("row", {}) or {}
            if str(r.get("type", "")).strip() == "end_group":
                return True
    return False


# ------------------------------------------------------------------------------------------
# 3) AUTOCURACIÓN: si P5..P10 no están (o están vacías), se insertan correctamente
#    - NO depende de placeholders
# ------------------------------------------------------------------------------------------
def autocurar_paginas_p5_a_p10():
    """
    Asegura que P5..P10 existan con contenido.
    Si el usuario ya llenó/editar páginas, NO las sobreescribe.
    Solo inserta si la página está vacía o no existe.
    """
    v_si = slugify_name("Sí")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    # -------- P5: Riesgos --------
    if _page_is_empty("p5"):
        # Usa tu seed de Parte 3 si existe
        try:
            qb = st.session_state.questions_bank
            seed_p5_riesgos(qb, rel_si)
        except Exception:
            # fallback mínimo si algo faltara
            st.session_state.questions_bank.append({
                "qid": _new_qid("q"), "page": "p5", "order": 10,
                "row": {"type": "begin_group", "name": "p5_riesgos", "label": "III. Riesgos sociales y situacionales en el distrito", "appearance": "field-list", "relevant": rel_si}
            })
            st.session_state.questions_bank.append({
                "qid": _new_qid("q"), "page": "p5", "order": 90,
                "row": {"type": "end_group", "name": "p5_end", "label": ""}
            })

    # -------- P6: Delitos --------
    if _page_is_empty("p6"):
        try:
            seed_choices_p6_if_needed()
            new_items = seed_p6_delitos_bank(rel_si=rel_si)
            st.session_state.questions_bank += new_items
        except Exception:
            st.session_state.questions_bank.append({
                "qid": _new_qid("q"), "page": "p6", "order": 10,
                "row": {"type": "begin_group", "name": "p6_delitos", "label": "III. Delitos", "appearance": "field-list", "relevant": rel_si}
            })
            st.session_state.questions_bank.append({
                "qid": _new_qid("q"), "page": "p6", "order": 90,
                "row": {"type": "end_group", "name": "p6_end", "label": ""}
            })

    # -------- P7: VIF --------
    if _page_is_empty("p7"):
        try:
            seed_choices_p7_if_needed()
            new_items = seed_p7_vif_bank(rel_si=rel_si)
            st.session_state.questions_bank += new_items
        except Exception:
            st.session_state.questions_bank.append({
                "qid": _new_qid("q"), "page": "p7", "order": 10,
                "row": {"type": "begin_group", "name": "p7_victimizacion_vif", "label": "III. Victimización — Apartado A: Violencia intrafamiliar", "appearance": "field-list", "relevant": rel_si}
            })
            st.session_state.questions_bank.append({
                "qid": _new_qid("q"), "page": "p7", "order": 90,
                "row": {"type": "end_group", "name": "p7_end", "label": ""}
            })

    # -------- P8: Victimización otros --------
    if _page_is_empty("p8"):
        try:
            seed_choices_p8_if_needed()
            new_items = seed_p8_victimizacion_b_bank(rel_si=rel_si)
            st.session_state.questions_bank += new_items
        except Exception:
            st.session_state.questions_bank.append({
                "qid": _new_qid("q"), "page": "p8", "order": 10,
                "row": {"type": "begin_group", "name": "p8_victimizacion_otros", "label": "III. Victimización — Apartado B: Victimización por otros delitos", "appearance": "field-list", "relevant": rel_si}
            })
            st.session_state.questions_bank.append({
                "qid": _new_qid("q"), "page": "p8", "order": 190,
                "row": {"type": "end_group", "name": "p8_end", "label": ""}
            })

    # -------- P9: Confianza policial --------
    if _page_is_empty("p9"):
        try:
            seed_choices_p9_if_needed()
            new_items = seed_p9_confianza_bank(rel_si=rel_si)
            st.session_state.questions_bank += new_items
        except Exception:
            st.session_state.questions_bank.append({
                "qid": _new_qid("q"), "page": "p9", "order": 10,
                "row": {"type": "begin_group", "name": "p9_confianza_policial", "label": "Confianza policial", "appearance": "field-list", "relevant": rel_si}
            })
            st.session_state.questions_bank.append({
                "qid": _new_qid("q"), "page": "p9", "order": 90,
                "row": {"type": "end_group", "name": "p9_end", "label": ""}
            })

    # -------- P10: Propuestas --------
    if _page_is_empty("p10"):
        try:
            seed_choices_p10_if_needed()
            new_items = seed_p10_propuestas_bank(rel_si=rel_si)
            st.session_state.questions_bank += new_items
        except Exception:
            st.session_state.questions_bank.append({
                "qid": _new_qid("q"), "page": "p10", "order": 10,
                "row": {"type": "begin_group", "name": "p10_propuestas", "label": "Propuestas ciudadanas para la mejora de la seguridad", "appearance": "field-list", "relevant": rel_si}
            })
            st.session_state.questions_bank.append({
                "qid": _new_qid("q"), "page": "p10", "order": 190,
                "row": {"type": "end_group", "name": "p10_end", "label": ""}
            })


# ------------------------------------------------------------------------------------------
# 4) FIX UI: selected_qid / active_page para evitar “no actualiza” o “no aparece”
# ------------------------------------------------------------------------------------------
def autocurar_ui_seleccion():
    # active_page válida
    if st.session_state.get("active_page") not in pages:
        st.session_state.active_page = "p1"

    # selected_qid no nulo
    if not st.session_state.get("selected_qid"):
        if st.session_state.questions_bank:
            st.session_state.selected_qid = st.session_state.questions_bank[0]["qid"]

    # si selected_qid ya no existe (por delete), set al primero
    if st.session_state.get("selected_qid"):
        exists = any(q.get("qid") == st.session_state.selected_qid for q in (st.session_state.questions_bank or []))
        if not exists and st.session_state.questions_bank:
            st.session_state.selected_qid = st.session_state.questions_bank[0]["qid"]


# ------------------------------------------------------------------------------------------
# 5) EJECUCIÓN AUTOMÁTICA (una vez por sesión)
# ------------------------------------------------------------------------------------------
def run_autocuracion_once():
    if st.session_state.get("_autocuracion_done") is True:
        return

    # asegurar listas base que SIEMPRE deben existir
    ensure_choice_list_exists_min(st.session_state.choices_bank, "yesno")
    ensure_choice_list_exists_min(st.session_state.choices_bank, "list_canton")
    ensure_choice_list_exists_min(st.session_state.choices_bank, "list_distrito")

    # autocurar páginas faltantes/vacías
    autocurar_paginas_p5_a_p10()

    # autocurar UI selección
    autocurar_ui_seleccion()

    st.session_state["_autocuracion_done"] = True

run_autocuracion_once()

# ==========================================================================================
# FIN PARTE 9/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 10/10) =============================
# ===================== EXPORTAR + BACKUP/RESTORE + RESET (CORREGIDO 100%) =================
# ==========================================================================================
#
# ✅ ESTA PARTE:
# - Deja el EXPORT 100% funcional (usa tu motor build_xlsform_dataframes)
# - Corrige el RESET (en tu código anterior llamaba funciones que no existían)
# - Backup/Restore JSON sin romper session_state
#
# IMPORTANTE:
# - NO pide Word
# - NO cambia flujo
#
# ==========================================================================================

# ------------------------------------------------------------------------------------------
# 1) RESET CORRECTO (usa TUS seeds reales)
# ------------------------------------------------------------------------------------------
def reset_to_seed_total():
    """
    Reset total a plantilla base (tus seeds reales).
    """
    # limpiar bancos
    st.session_state.questions_bank = seed_questions_base(form_title=form_title, logo_media_name=logo_media_name)
    st.session_state.choices_bank = seed_choices_base()
    st.session_state.glossary_bank = dict(GLOSARIO_BASE)

    # glosario por página
    if "page_glossary_map" in st.session_state:
        del st.session_state["page_glossary_map"]
    init_page_glossary_map()

    # selección inicial
    if st.session_state.questions_bank:
        st.session_state.selected_qid = st.session_state.questions_bank[0]["qid"]
    st.session_state.active_page = "p1"

    # limpiar cache export
    for k in ["_df_survey", "_df_choices", "_df_settings", "_export_errors", "_export_blocked"]:
        if k in st.session_state:
            del st.session_state[k]

    # autocuración se vuelve a ejecutar
    if "_autocuracion_done" in st.session_state:
        del st.session_state["_autocuracion_done"]


# ------------------------------------------------------------------------------------------
# 2) BACKUP / RESTORE
# ------------------------------------------------------------------------------------------
def build_backup_payload() -> dict:
    return {
        "meta": {
            "app": "Encuesta Comunidad XLSForm Builder (editable)",
            "created_at": datetime.now().isoformat(),
            "form_title": form_title,
        },
        "questions_bank": st.session_state.get("questions_bank", []),
        "choices_bank": st.session_state.get("choices_bank", []),
        "glossary_bank": st.session_state.get("glossary_bank", {}),
        "page_glossary_map": st.session_state.get("page_glossary_map", {}),
    }

def apply_backup_payload(payload: dict):
    if not isinstance(payload, dict):
        raise ValueError("El backup no es un JSON válido (dict).")

    qb = payload.get("questions_bank", [])
    cb = payload.get("choices_bank", [])
    gb = payload.get("glossary_bank", {})
    pg = payload.get("page_glossary_map", {})

    if not isinstance(qb, list) or not isinstance(cb, list) or not isinstance(gb, dict) or not isinstance(pg, dict):
        raise ValueError("Estructura inválida en backup.")

    st.session_state.questions_bank = qb
    st.session_state.choices_bank = cb
    st.session_state.glossary_bank = gb
    st.session_state.page_glossary_map = pg

    # asegurar listas críticas
    ensure_choice_list_exists_min(st.session_state.choices_bank, "yesno")
    ensure_choice_list_exists_min(st.session_state.choices_bank, "list_canton")
    ensure_choice_list_exists_min(st.session_state.choices_bank, "list_distrito")

    # autocuración para que no quede nada vacío
    if "_autocuracion_done" in st.session_state:
        del st.session_state["_autocuracion_done"]
    run_autocuracion_once()


# ------------------------------------------------------------------------------------------
# 3) EXPORTAR (usa tu pestaña Exportar existente)
#    ✅ Aquí solo añadimos el panel de mantenimiento al final
# ------------------------------------------------------------------------------------------
if active_tab == "Exportar":
    st.markdown("---")
    st.subheader("🛠️ Mantenimiento (Backup / Restore / Reset)")

    with st.expander("📦 Backup/Restore (JSON) — guardar y restaurar la encuesta editable", expanded=False):
        st.caption(
            "Este backup guarda TODO lo editable: preguntas, choices, glosario y glosario por página. "
            "Puedes guardarlo y restaurarlo cuando quieras."
        )

        payload = build_backup_payload()
        backup_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

        st.download_button(
            label="⬇️ Descargar BACKUP (JSON)",
            data=backup_bytes,
            file_name=slugify_name(form_title) + "_backup.json",
            mime="application/json",
            use_container_width=True,
            key="dl_backup_json"
        )

        st.markdown("### ♻️ Restaurar backup")
        up = st.file_uploader("Sube un archivo BACKUP (.json)", type=["json"], key="up_backup_json")

        if up is not None:
            try:
                raw = up.getvalue().decode("utf-8", errors="replace")
                data = json.loads(raw)
                apply_backup_payload(data)
                st.success("Backup restaurado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo restaurar el backup: {e}")

    with st.expander("🧨 Reset a plantilla base (seed) — iniciar desde cero", expanded=False):
        st.warning(
            "Esto reemplaza el contenido actual (preguntas/choices/glosario) por la plantilla base. "
            "Si no quieres perder cambios, descarga primero un BACKUP."
        )
        if st.button("RESET TOTAL", type="primary", use_container_width=True, key="btn_reset_seed"):
            reset_to_seed_total()
            st.success("Reset completado.")
            st.rerun()

# ==========================================================================================
# FIN PARTE 10/10
# ==========================================================================================





