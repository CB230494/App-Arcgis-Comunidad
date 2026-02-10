# -*- coding: utf-8 -*-
# ==========================================================================================
# App: Encuesta Comunidad → XLSForm para ArcGIS Survey123 (versión extendida)
# - Constructor completo (agregar/editar/ordenar/borrar)
# - Condicionales (relevant) + finalizar temprano
# - Listas en cascada (choice_filter) Cantón→Distrito [CATÁLOGO MANUAL POR LOTES]
# - Exportar/Importar proyecto (JSON)
# - Exportar a XLSForm (survey/choices/settings)
# - PÁGINAS reales (style="pages"): Intro + Consentimiento + P2.. (por secciones)
# - Portada con logo (media::image) y texto de introducción
# - Consentimiento:
#     - Texto en BLOQUES (notes separados) para que se vea ordenado en Survey123
#     - Si marca "No" ⇒ NO muestra el resto de páginas y cae a una página final para enviar
# - MEJORA: no mostrar "— escoja un cantón —" cuando ya hay catálogo real
# - FIX MATRIZ (table-list): todas las filas comparten el MISMO list_name (list_override)
# - FIX: Página "Delitos" separada (solo título Delitos + intro + preguntas 18–28)
# ==========================================================================================

import re
import json
from io import BytesIO
from datetime import datetime
from typing import List, Dict

import streamlit as st
import pandas as pd

# ------------------------------------------------------------------------------------------
# Configuración de la app
# ------------------------------------------------------------------------------------------
st.set_page_config(page_title="Encuesta Comunidad → XLSForm (Survey123)", layout="wide")
st.title("🏘️ Encuesta Comunidad → XLSForm para ArcGIS Survey123")

st.markdown("""
Crea tu cuestionario y **exporta un XLSForm** listo para **ArcGIS Survey123**.

Incluye:
- Tipos: **text**, **integer/decimal**, **date**, **time**, **geopoint**, **select_one**, **select_multiple**.
- **Constructor completo** (agregar, editar, ordenar, borrar) con condicionales.
- **Listas en cascada** **Cantón→Distrito** (**catálogo manual por lotes**).
- **Páginas** con navegación **Siguiente/Anterior** (`settings.style = pages`).
- **Portada** con **logo** (`media::image`) e **introducción**.
- **Consentimiento informado** (si NO acepta, la encuesta termina) con texto ordenado por bloques.
""")

# ------------------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------------------
TIPOS = [
    "Texto (corto)",
    "Párrafo (texto largo)",
    "Número",
    "Selección única",
    "Selección múltiple",
    "Fecha",
    "Hora",
    "GPS (ubicación)",
]

def _rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

def slugify_name(texto: str) -> str:
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
    if base not in usados:
        return base
    i = 2
    while f"{base}_{i}" in usados:
        i += 1
    return f"{base}_{i}"

def map_tipo_to_xlsform(tipo_ui: str, name: str):
    if tipo_ui == "Texto (corto)":
        return ("text", None, None)
    if tipo_ui == "Párrafo (texto largo)":
        return ("text", "multiline", None)
    if tipo_ui == "Número":
        return ("integer", None, None)
    if tipo_ui == "Selección única":
        return (f"select_one list_{name}", None, f"list_{name}")
    if tipo_ui == "Selección múltiple":
        return (f"select_multiple list_{name}", None, f"list_{name}")
    if tipo_ui == "Fecha":
        return ("date", None, None)
    if tipo_ui == "Hora":
        return ("time", None, None)
    if tipo_ui == "GPS (ubicación)":
        return ("geopoint", None, None)
    return ("text", None, None)

def xlsform_or_expr(conds):
    if not conds:
        return None
    if len(conds) == 1:
        return conds[0]
    return "(" + " or ".join(conds) + ")"

def xlsform_not(expr):
    if not expr:
        return None
    return f"not({expr})"

def build_relevant_expr(rules_for_target: List[Dict]):
    or_parts = []
    for r in rules_for_target:
        src = r["src"]
        op = r.get("op", "=")
        vals = r.get("values", [])
        if not vals:
            continue

        if op == "=":
            segs = [f"${{{src}}}='{v}'" for v in vals]
        elif op == "selected":
            segs = [f"selected(${{{src}}}, '{v}')" for v in vals]
        elif op == "!=":
            segs = [f"${{{src}}}!='{v}'" for v in vals]
        else:
            segs = [f"${{{src}}}='{v}'" for v in vals]

        or_parts.append(xlsform_or_expr(segs))
    return xlsform_or_expr(or_parts)

# ------------------------------------------------------------------------------------------
# Estado base (session_state)
# ------------------------------------------------------------------------------------------
if "preguntas" not in st.session_state:
    st.session_state.preguntas = []
if "reglas_visibilidad" not in st.session_state:
    st.session_state.reglas_visibilidad = []
if "reglas_finalizar" not in st.session_state:
    st.session_state.reglas_finalizar = []

# ------------------------------------------------------------------------------------------
# Catálogo manual por lotes: Cantón → Distritos
# ------------------------------------------------------------------------------------------
if "choices_ext_rows" not in st.session_state:
    st.session_state.choices_ext_rows = []  # filas para hoja choices
if "choices_extra_cols" not in st.session_state:
    st.session_state.choices_extra_cols = set()

def _append_choice_unique(row: Dict):
    key = (row.get("list_name"), row.get("name"))
    exists = any((r.get("list_name"), r.get("name")) == key for r in st.session_state.choices_ext_rows)
    if not exists:
        st.session_state.choices_ext_rows.append(row)

def _asegurar_placeholders_catalogo():
    """
    FIX: Survey123 exige que existan list_canton/list_distrito en choices si se usan en survey.
    Esto garantiza placeholders aun cuando el usuario NO agregue lotes.
    """
    st.session_state.choices_extra_cols.update({"canton_key", "any"})
    _append_choice_unique({"list_name": "list_canton", "name": "__pick_canton__", "label": "— escoja un cantón —"})
    _append_choice_unique({"list_name": "list_distrito", "name": "__pick_distrito__", "label": "— escoja un cantón —", "any": "1"})

def _hay_catalogo_real() -> bool:
    cantones_reales = any(
        r.get("list_name") == "list_canton" and r.get("name") not in (None, "", "__pick_canton__")
        for r in st.session_state.choices_ext_rows
    )
    distritos_reales = any(
        r.get("list_name") == "list_distrito" and r.get("name") not in (None, "", "__pick_distrito__")
        for r in st.session_state.choices_ext_rows
    )
    return bool(cantones_reales and distritos_reales)

def _filtrar_placeholders_si_hay_catalogo(rows: List[Dict]) -> List[Dict]:
    if not _hay_catalogo_real():
        return rows
    filtradas = []
    for r in rows:
        if r.get("list_name") == "list_canton" and r.get("name") == "__pick_canton__":
            continue
        if r.get("list_name") == "list_distrito" and r.get("name") == "__pick_distrito__":
            continue
        filtradas.append(r)
    return filtradas

# Asegurar placeholders desde el inicio
_asegurar_placeholders_catalogo()

st.markdown("### 📚 Catálogo Cantón → Distrito (por lotes)")
with st.expander("Agrega un lote (un Cantón y varios Distritos)", expanded=True):
    col_c1, col_c2 = st.columns(2)
    canton_txt = col_c1.text_input("Cantón (una vez)", value="")
    distritos_txt = col_c2.text_area("Distritos del cantón (uno por línea)", value="", height=130)

    col_b1, col_b2, _ = st.columns([1, 1, 2])
    add_lote = col_b1.button("Agregar lote", type="primary", use_container_width=True)
    clear_all = col_b2.button("Limpiar catálogo", use_container_width=True)

    if clear_all:
        st.session_state.choices_ext_rows = []
        st.session_state.choices_extra_cols = set()
        _asegurar_placeholders_catalogo()
        st.success("Catálogo limpiado (placeholders conservados).")

    if add_lote:
        c = canton_txt.strip()
        distritos = [d.strip() for d in distritos_txt.splitlines() if d.strip()]
        if not c or not distritos:
            st.error("Debes indicar Cantón y al menos un Distrito.")
        else:
            slug_c = slugify_name(c)

            st.session_state.choices_extra_cols.update({"canton_key", "any"})
            _asegurar_placeholders_catalogo()

            _append_choice_unique({"list_name": "list_canton", "name": slug_c, "label": c})

            usados_d = set()
            for d in distritos:
                slug_d = asegurar_nombre_unico(slugify_name(d), usados_d)
                usados_d.add(slug_d)
                _append_choice_unique({"list_name": "list_distrito", "name": slug_d, "label": d, "canton_key": slug_c})

            st.success(f"Lote agregado: {c} → {len(distritos)} distritos.")

if st.session_state.choices_ext_rows:
    st.dataframe(
        pd.DataFrame(st.session_state.choices_ext_rows),
        use_container_width=True,
        hide_index=True,
        height=240
    )

# ------------------------------------------------------------------------------------------
# Cabecera: Logo + Delegación
# ------------------------------------------------------------------------------------------
DEFAULT_LOGO_PATH = "001.png"

col_logo, col_txt = st.columns([1, 3], vertical_alignment="center")
with col_logo:
    up_logo = st.file_uploader("Logo (PNG/JPG)", type=["png", "jpg", "jpeg"])
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
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    delegacion = st.text_input("Nombre del lugar / Delegación", value="San Carlos Oeste")
    logo_media_name = st.text_input(
        "Nombre de archivo para `media::image`",
        value=st.session_state.get("_logo_name", "001.png"),
        help="Debe coincidir con el archivo en `media/` de Survey123 Connect."
    )
    titulo_compuesto = (f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad")
    st.markdown(f"<h5 style='text-align:center;margin:4px 0'>📋 {titulo_compuesto}</h5>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------------------
# Intro (Página 1)
# ------------------------------------------------------------------------------------------
INTRO_COMUNIDAD = (
    "El presente formato corresponde a la Encuesta de Percepción de Comunidad 2026, diseñada para "
    "recopilar información clave sobre seguridad ciudadana, convivencia y factores de riesgo en los "
    "cantones del territorio nacional. Este documento se remite para su revisión y validación por parte "
    "de las direcciones, departamentos u oficinas con competencia técnica en cada uno de los apartados, "
    "con el fin de asegurar su coherencia metodológica, normativa y operativa con los lineamientos "
    "institucionales vigentes. Las observaciones recibidas permitirán fortalecer el instrumento antes "
    "de su aplicación en territorio."
)

# ------------------------------------------------------------------------------------------
# Consentimiento informado (Página 2)
# ------------------------------------------------------------------------------------------
CONSENTIMIENTO_TITULO = "Consentimiento Informado para la Participación en la Encuesta"
CONSENT_SI = slugify_name("Sí")
CONSENT_NO = slugify_name("No")

CONSENTIMIENTO_BLOQUES = [
    "Usted está siendo invitado(a) a participar de forma libre y voluntaria en una encuesta sobre seguridad, convivencia y percepción ciudadana, dirigida a personas mayores de 18 años.",
    "El objetivo de esta encuesta es recopilar información de carácter preventivo y estadístico, con el fin de apoyar la planificación de acciones de prevención, mejora de la convivencia y fortalecimiento de la seguridad en comunidades y zonas comerciales.",
    "La participación es totalmente voluntaria. Usted puede negarse a responder cualquier pregunta, así como retirarse de la encuesta en cualquier momento, sin que ello genere consecuencia alguna.",
    "De conformidad con lo dispuesto en el artículo 5 de la Ley N.º 8968 (Protección de la Persona frente al Tratamiento de sus Datos Personales), se le informa que:",
    "Finalidad del tratamiento: La información recopilada será utilizada exclusivamente para fines estadísticos, analíticos y preventivos, y no para investigaciones penales, procesos judiciales, sanciones administrativas ni procedimientos disciplinarios.",
    "Datos personales: Algunos apartados permiten, de forma voluntaria, el suministro de datos personales o información de contacto.",
    "Tratamiento de los datos: Los datos serán almacenados, analizados y resguardados bajo criterios de confidencialidad y seguridad, conforme a la normativa vigente.",
    "Destinatarios y acceso: La información será conocida únicamente por el personal autorizado de la Fuerza Pública / Ministerio de Seguridad Pública, para los fines indicados. No será cedida a terceros ajenos a estos fines.",
    "Responsable de la base de datos: El Ministerio de Seguridad Pública, a través de la Dirección de Programas Policiales Preventivos, Oficina Estrategia Integral de Prevención para la Seguridad Pública (EIPESP / Estrategia Sembremos Seguridad), será responsable del tratamiento y custodia de la información recolectada.",
    "Derechos de la persona participante: Usted conserva el derecho a la autodeterminación informativa y a decidir libremente sobre el suministro de sus datos.",
    "Las respuestas brindadas no constituyen denuncias formales, ni sustituyen los mecanismos legales correspondientes.",
    "Al continuar con la encuesta, usted manifiesta haber leído y comprendido la información anterior y otorga su consentimiento informado para participar."
]

# ------------------------------------------------------------------------------------------
# II. PERCEPCIÓN CIUDADANA DE SEGURIDAD EN EL DISTRITO (intro)
# ------------------------------------------------------------------------------------------
INTRO_PERCEPCION_DISTRITO = (
    "En esta sección le preguntaremos sobre cómo percibe la seguridad en su distrito. "
    "Las siguientes preguntas buscan conocer su opinión y experiencia sobre la seguridad en el lugar "
    "donde vive o trabaja, así como en los distintos espacios que forman parte del distrito. "
    "Nos interesa saber cómo siente y cómo observa la seguridad, cuáles lugares le generan mayor o menor "
    "tranquilidad y si considera que la situación ha mejorado, empeorado o se mantiene igual. "
    "Sus respuestas nos ayudarán a identificar qué espacios generan mayor preocupación, entender por qué "
    "se perciben como inseguros y conocer la forma en que las personas viven la seguridad en su entorno. "
    "Esta información se utilizará para apoyar el análisis de la situación del distrito y orientar acciones "
    "de mejora y prevención. No hay respuestas correctas o incorrectas. Le pedimos responder con sinceridad, "
    "según su experiencia y percepción personal."
)

# ------------------------------------------------------------------------------------------
# III. RIESGOS (intro)  — página separada
# ------------------------------------------------------------------------------------------
INTRO_RIESGOS_III = (
    "A continuación, en esta sección le preguntaremos sobre situaciones o condiciones que pueden representar "
    "riesgos para la convivencia y la seguridad en el distrito. "
    "Estas preguntas no se refieren necesariamente a delitos, sino a situaciones, comportamientos o problemas "
    "sociales que usted haya observado y que puedan generar preocupación, afectar la tranquilidad o aumentar "
    "el riesgo de que ocurran hechos de inseguridad. "
    "Nos interesa conocer qué situaciones están presentes en el distrito, con qué frecuencia se observan y en "
    "qué espacios se presentan, según su experiencia y percepción. Sus respuestas ayudarán a identificar "
    "factores de riesgo y a orientar acciones de prevención y atención a nivel local. "
    "No existen respuestas correctas o incorrectas. Le pedimos responder con sinceridad, de acuerdo con lo que "
    "ha visto o vivido en su entorno."
)

# ------------------------------------------------------------------------------------------
# Delitos (intro) — página SOLO delitos
# ------------------------------------------------------------------------------------------
INTRO_DELITOS = (
    "A continuación, se presenta una lista de delitos para que indique aquellos que, según su conocimiento u "
    "observación, considera que se presentan en el distrito. La información recopilada tiene fines de análisis "
    "preventivo y territorial, y no constituye una denuncia formal ni la confirmación judicial de hechos delictivos."
)

# ------------------------------------------------------------------------------------------
# Victimización — Apartado A: Violencia intrafamiliar (intro) — página nueva
# ------------------------------------------------------------------------------------------
INTRO_VICT_VI = (
    "A continuación, se presentan algunas preguntas relacionadas con situaciones de violencia intrafamiliar, "
    "con el fin de conocer si usted o algún miembro de su hogar ha sido afectado directamente por este tipo de "
    "situaciones en el distrito durante los últimos 12 meses. La información recopilada es confidencial y se utiliza "
    "únicamente con fines de análisis y mejora de las acciones de prevención y atención."
)

# ------------------------------------------------------------------------------------------
# Precarga de preguntas (seed)
# ------------------------------------------------------------------------------------------
if "seed_cargado" not in st.session_state:
    v_muy_inseguro = slugify_name("Muy inseguro")
    v_inseguro = slugify_name("Inseguro")

    # LISTA COMPARTIDA para la matriz (table-list)
    LISTA_MATRIZ_SEG = "list_matriz_seguridad"

    seed = [
        # ---------------- Consentimiento ----------------
        {"tipo_ui": "Selección única",
         "label": "¿Acepta participar en esta encuesta?",
         "name": "consentimiento",
         "required": True,
         "opciones": ["Sí", "No"],
         "appearance": "horizontal",
         "choice_filter": None,
         "relevant": None},

        # ---------------- I. DATOS DEMOGRÁFICOS ----------------
        {"tipo_ui": "Selección única", "label": "1. Cantón:", "name": "canton", "required": True,
         "opciones": [], "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección única", "label": "2. Distrito:", "name": "distrito", "required": True,
         "opciones": [], "appearance": None, "choice_filter": "canton_key=${canton}", "relevant": None},

        {"tipo_ui": "Selección única",
         "label": "3. Edad (en años cumplidos): marque una categoría que incluya su edad.",
         "name": "edad_rango",
         "required": True,
         "opciones": ["18 a 29 años", "30 a 44 años", "45 a 64 años", "65 años o más"],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección única",
         "label": "4. ¿Con cuál de estas opciones se identifica?",
         "name": "genero",
         "required": True,
         "opciones": ["Femenino", "Masculino", "Persona no Binaria", "Prefiero no decir"],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección única",
         "label": "5. Escolaridad:",
         "name": "escolaridad",
         "required": True,
         "opciones": [
             "Ninguna",
             "Primaria incompleta",
             "Primaria completa",
             "Secundaria incompleta",
             "Secundaria completa",
             "Técnico",
             "Universitaria incompleta",
             "Universitaria completa",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección única",
         "label": "6. ¿Cuál es su relación con la zona?",
         "name": "relacion_zona",
         "required": True,
         "opciones": ["Vivo en la zona", "Trabajo en la zona", "Visito la zona", "Estudio en la zona"],
         "appearance": None, "choice_filter": None, "relevant": None},

        # ---------------- II. PERCEPCIÓN CIUDADANA (7–11) ----------------
        {"tipo_ui": "Selección única",
         "label": "7. ¿Qué tan seguro percibe usted el distrito donde reside o transita?",
         "name": "percep_seg_distrito",
         "required": True,
         "opciones": ["Muy inseguro", "Inseguro", "Ni seguro ni inseguro", "Seguro", "Muy seguro"],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple",
         "label": "7.1. Indique por qué considera el distrito inseguro (Marque todas las situaciones que usted percibe que ocurren con mayor frecuencia en su comunidad):",
         "name": "motivos_inseguridad_distrito",
         "required": True,
         "opciones": [
             "Venta o distribución de drogas",
             "Consumo de drogas en espacios públicos",
             "Consumo de alcohol en espacios públicos",
             "Riñas o peleas frecuentes",
             "Asaltos o robos a personas",
             "Robos a viviendas o comercios",
             "Amenazas y extorsiones",
             "Balaceras, detonaciones o ruidos similares",
             "Presencia de grupos que generan temor",
             "Vandalismo o daños intencionales",
             "Poca iluminación en calles o espacios públicos",
             "Lotes baldíos o abandonados",
             "Casas o edificios abandonados",
             "Calles en mal estado",
             "Falta de limpieza o acumulación de basura",
             "Paradas de bus inseguras",
             "Falta de cámaras de seguridad",
             "Comercios inseguros o sin control",
             "Daños frecuentes a la propiedad",
             "Presencia de personas en situación de calle que influye en su percepción de seguridad",
             "Presencia de personas en situación de ocio (sin actividad laboral o educativa)",
             "Ventas informales (ambulantes)",
             "Zona donde se ejerce prostitución",
             "Problemas con transporte informal",
             "Falta de patrullajes visibles",
             "Falta de presencia policial en la zona",
             "Situaciones de violencia intrafamiliar",
             "Situaciones de violencia de género",
             "Otro problema que considere importante",
         ],
         "appearance": None,
         "choice_filter": None,
         "relevant": xlsform_or_expr([
             f"${{percep_seg_distrito}}='{v_muy_inseguro}'",
             f"${{percep_seg_distrito}}='{v_inseguro}'"
         ])},

        {"tipo_ui": "Párrafo (texto largo)",
         "label": "Indique cuál es ese otro problema importante:",
         "name": "otro_problema_inseg_distrito",
         "required": True,
         "opciones": [],
         "appearance": None,
         "choice_filter": None,
         "relevant": f"selected(${{motivos_inseguridad_distrito}}, '{slugify_name('Otro problema que considere importante')}')"},

        {"tipo_ui": "Selección única",
         "label": "8. En comparación con los 12 meses anteriores, ¿cómo percibe que ha cambiado la seguridad en este distrito?",
         "name": "cambio_seguridad_12m",
         "required": True,
         "opciones": ["Mucho menos seguro (1)", "Menos seguro (2)", "Se mantiene igual (3)", "Más seguro (4)", "Mucho más seguro (5)"],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Párrafo (texto largo)",
         "label": "8.1. Indique por qué (explique brevemente la razón de su respuesta anterior):",
         "name": "motivo_cambio_12m",
         "required": True,
         "opciones": [],
         "appearance": None, "choice_filter": None, "relevant": "string-length(${cambio_seguridad_12m})>0"},

        # 9. MATRIZ (todas comparten list_override = LISTA_MATRIZ_SEG)
        {"tipo_ui": "Selección única", "label": "Discotecas, bares, sitios de entretenimiento", "name": "seg_discotecas_bares",
         "required": True, "opciones": ["Muy inseguro (1)", "Inseguro (2)", "Ni seguro ni inseguro (3)", "Seguro (4)", "Muy seguro (5)", "No aplica"],
         "appearance": None, "choice_filter": None, "relevant": None, "list_override": LISTA_MATRIZ_SEG},

        {"tipo_ui": "Selección única", "label": "Espacios recreativos (parques, play, plaza de deportes)", "name": "seg_espacios_recreativos",
         "required": True, "opciones": ["Muy inseguro (1)", "Inseguro (2)", "Ni seguro ni inseguro (3)", "Seguro (4)", "Muy seguro (5)", "No aplica"],
         "appearance": None, "choice_filter": None, "relevant": None, "list_override": LISTA_MATRIZ_SEG},

        {"tipo_ui": "Selección única", "label": "Lugar de residencia (casa de habitación)", "name": "seg_lugar_residencia",
         "required": True, "opciones": ["Muy inseguro (1)", "Inseguro (2)", "Ni seguro ni inseguro (3)", "Seguro (4)", "Muy seguro (5)", "No aplica"],
         "appearance": None, "choice_filter": None, "relevant": None, "list_override": LISTA_MATRIZ_SEG},

        {"tipo_ui": "Selección única", "label": "Paradas y/o estaciones de buses, taxis, trenes", "name": "seg_paradas_estaciones",
         "required": True, "opciones": ["Muy inseguro (1)", "Inseguro (2)", "Ni seguro ni inseguro (3)", "Seguro (4)", "Muy seguro (5)", "No aplica"],
         "appearance": None, "choice_filter": None, "relevant": None, "list_override": LISTA_MATRIZ_SEG},

        {"tipo_ui": "Selección única", "label": "Puentes peatonales", "name": "seg_puentes_peatonales",
         "required": True, "opciones": ["Muy inseguro (1)", "Inseguro (2)", "Ni seguro ni inseguro (3)", "Seguro (4)", "Muy seguro (5)", "No aplica"],
         "appearance": None, "choice_filter": None, "relevant": None, "list_override": LISTA_MATRIZ_SEG},

        {"tipo_ui": "Selección única", "label": "Transporte público", "name": "seg_transporte_publico",
         "required": True, "opciones": ["Muy inseguro (1)", "Inseguro (2)", "Ni seguro ni inseguro (3)", "Seguro (4)", "Muy seguro (5)", "No aplica"],
         "appearance": None, "choice_filter": None, "relevant": None, "list_override": LISTA_MATRIZ_SEG},

        {"tipo_ui": "Selección única", "label": "Zona bancaria", "name": "seg_zona_bancaria",
         "required": True, "opciones": ["Muy inseguro (1)", "Inseguro (2)", "Ni seguro ni inseguro (3)", "Seguro (4)", "Muy seguro (5)", "No aplica"],
         "appearance": None, "choice_filter": None, "relevant": None, "list_override": LISTA_MATRIZ_SEG},

        {"tipo_ui": "Selección única", "label": "Zona de comercio", "name": "seg_zona_comercio",
         "required": True, "opciones": ["Muy inseguro (1)", "Inseguro (2)", "Ni seguro ni inseguro (3)", "Seguro (4)", "Muy seguro (5)", "No aplica"],
         "appearance": None, "choice_filter": None, "relevant": None, "list_override": LISTA_MATRIZ_SEG},

        {"tipo_ui": "Selección única", "label": "Zonas residenciales (calles y barrios, distinto a su casa)", "name": "seg_zonas_residenciales",
         "required": True, "opciones": ["Muy inseguro (1)", "Inseguro (2)", "Ni seguro ni inseguro (3)", "Seguro (4)", "Muy seguro (5)", "No aplica"],
         "appearance": None, "choice_filter": None, "relevant": None, "list_override": LISTA_MATRIZ_SEG},

        {"tipo_ui": "Selección única", "label": "Zonas francas", "name": "seg_zonas_francas",
         "required": True, "opciones": ["Muy inseguro (1)", "Inseguro (2)", "Ni seguro ni inseguro (3)", "Seguro (4)", "Muy seguro (5)", "No aplica"],
         "appearance": None, "choice_filter": None, "relevant": None, "list_override": LISTA_MATRIZ_SEG},

        {"tipo_ui": "Selección única", "label": "Lugares de interés turístico", "name": "seg_lugares_turisticos",
         "required": True, "opciones": ["Muy inseguro (1)", "Inseguro (2)", "Ni seguro ni inseguro (3)", "Seguro (4)", "Muy seguro (5)", "No aplica"],
         "appearance": None, "choice_filter": None, "relevant": None, "list_override": LISTA_MATRIZ_SEG},

        {"tipo_ui": "Selección única", "label": "Centros educativos", "name": "seg_centros_educativos",
         "required": True, "opciones": ["Muy inseguro (1)", "Inseguro (2)", "Ni seguro ni inseguro (3)", "Seguro (4)", "Muy seguro (5)", "No aplica"],
         "appearance": None, "choice_filter": None, "relevant": None, "list_override": LISTA_MATRIZ_SEG},

        {"tipo_ui": "Selección única",
         "label": "10. Desde su percepción ¿cuál considera que es el principal foco de inseguridad en el distrito?",
         "name": "foco_inseguridad",
         "required": True,
         "opciones": [
             "Discotecas, bares, sitios de entretenimiento",
             "Espacios recreativos (parques, play, plaza de deportes)",
             "Lugar de residencia (casa de habitación)",
             "Paradas y/o estaciones de buses, taxis, trenes",
             "Puentes peatonales",
             "Transporte público",
             "Zona bancaria",
             "Zona comercial",
             "Zonas francas",
             "Zonas residenciales (calles y barrios, distinto a su casa)",
             "Lugares de interés turístico",
             "Centros educativos",
             "Otros",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Texto (corto)",
         "label": "Indique cuál es ese otro foco de inseguridad:",
         "name": "foco_inseguridad_otro",
         "required": True,
         "opciones": [],
         "appearance": None, "choice_filter": None, "relevant": f"${{foco_inseguridad}}='{slugify_name('Otros')}'"},

        {"tipo_ui": "Párrafo (texto largo)",
         "label": "11. Describa brevemente las razones por las cuales considera inseguro el tipo de espacio seleccionado en la pregunta anterior:",
         "name": "razones_foco_inseguridad",
         "required": True,
         "opciones": [],
         "appearance": None, "choice_filter": None, "relevant": "string-length(${foco_inseguridad})>0"},

        # ---------------- III. RIESGOS (12–17) ----------------
        {"tipo_ui": "Selección múltiple",
         "label": "12. Según su conocimiento u observación, seleccione las problemáticas que afectan su distrito:",
         "name": "problematicas_distrito",
         "required": True,
         "opciones": [
             "Problemas vecinales o conflictos entre vecinos",
             "Presencia de personas en situación de calle (personas que viven permanentemente en la vía pública)",
             "Zona donde se ejerce prostitución",
             "Desvinculación escolar (deserción escolar)",
             "Falta de oportunidades laborales",
             "Acumulación de basura, aguas negras o mal alcantarillado",
             "Carencia o inexistencia de alumbrado público",
             "Lotes baldíos",
             "Cuarterías",
             "Asentamientos informales o precarios",
             "Pérdida de espacios públicos (parques, polideportivos u otros)",
             "Consumo de alcohol en vía pública",
             "Consumo de drogas en espacios públicos",
             "Ventas informales (ambulantes)",
             "Escándalos musicales o ruidos excesivos",
             "Otro problema que considere importante",
             "No se observan estas problemáticas en el distrito",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Párrafo (texto largo)",
         "label": "Indique cuál es ese otro problema importante:",
         "name": "problematicas_otro",
         "required": True,
         "opciones": [],
         "appearance": None, "choice_filter": None,
         "relevant": f"selected(${{problematicas_distrito}}, '{slugify_name('Otro problema que considere importante')}')"},

        {"tipo_ui": "Selección múltiple",
         "label": "13. En relación con la oferta de servicios y oportunidades en su distrito (Inversión social), indique cuáles de las siguientes carencias identifica:",
         "name": "carencias_inversion_social",
         "required": True,
         "opciones": [
             "Falta de oferta educativa",
             "Falta de oferta deportiva",
             "Falta de oferta recreativa",
             "Falta de actividades culturales",
             "Otro problema que considere importante",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Párrafo (texto largo)",
         "label": "Indique cuál es esa otra carencia importante:",
         "name": "carencias_inversion_social_otro",
         "required": True,
         "opciones": [],
         "appearance": None, "choice_filter": None,
         "relevant": f"selected(${{carencias_inversion_social}}, '{slugify_name('Otro problema que considere importante')}')"},

        {"tipo_ui": "Selección múltiple",
         "label": "14. En los casos en que se observa consumo de drogas en el distrito, indique dónde ocurre:",
         "name": "consumo_drogas_donde",
         "required": True,
         "opciones": [
             "Áreas públicas (calles, parques, paradas, espacios abiertos)",
             "Áreas privadas (viviendas, locales, espacios cerrados)",
             "No se observa consumo de drogas",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple",
         "label": "15. Indique las principales deficiencias de infraestructura vial que afectan su distrito:",
         "name": "infra_vial_deficiencias",
         "required": True,
         "opciones": [
             "Calles en mal estado",
             "Falta de señalización de tránsito",
             "Carencia o inexistencia de aceras",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple",
         "label": "16. Según su conocimiento u observación, indique en qué tipo de espacios se identifica la existencia de puntos de venta de drogas en el distrito:",
         "name": "puntos_venta_drogas",
         "required": True,
         "opciones": [
             "Casa de habitación (espacio cerrado)",
             "Edificación abandonada",
             "Lote baldío",
             "Otro tipo de espacio",
             "No se observa",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Texto (corto)",
         "label": "Indique cuál es ese otro tipo de espacio:",
         "name": "puntos_venta_drogas_otro",
         "required": True,
         "opciones": [],
         "appearance": None, "choice_filter": None,
         "relevant": f"selected(${{puntos_venta_drogas}}, '{slugify_name('Otro tipo de espacio')}')"},

        {"tipo_ui": "Selección múltiple",
         "label": "17. Según su conocimiento u observación, indique si ha identificado situaciones de inseguridad asociadas al uso de los siguientes medios o modalidades de transporte en su distrito:",
         "name": "inseguridad_transporte",
         "required": True,
         "opciones": [
             "Transporte informal o no autorizado (taxis piratas)",
             "Plataformas de transporte digital",
             "Transporte público (buses)",
             "Servicios de reparto o mensajería “exprés” (por ejemplo, repartidores en motocicleta o bicimoto)",
             "Otro tipo de situación relacionada con el transporte",
             "No se observa",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Texto (corto)",
         "label": "Indique cuál es ese otro tipo de situación relacionada con el transporte:",
         "name": "inseguridad_transporte_otro",
         "required": True,
         "opciones": [],
         "appearance": None, "choice_filter": None,
         "relevant": f"selected(${{inseguridad_transporte}}, '{slugify_name('Otro tipo de situación relacionada con el transporte')}')"},

        # ---------------- Delitos (18–28) ----------------
        {"tipo_ui": "Selección múltiple",
         "label": "18. Seleccione los delitos que, según su conocimiento u observación, se presentan en el distrito:",
         "name": "delitos_lista",
         "required": True,
         "opciones": [
             "Disturbios en vía pública (riñas o agresiones)",
             "Daños a la propiedad (viviendas, comercios, vehículos u otros bienes)",
             "Daños al poliducto (perforaciones, tomas ilegales o vandalismo)",
             "Extorsión (amenazas o intimidación para exigir dinero u otros beneficios)",
             "Hurto (sustracción de artículos mediante el descuido)",
             "Compra o venta de artículos robados (receptación)",
             "Contrabando (licor, cigarrillos, medicinas, ropa, calzado, etc.)",
             "Maltrato animal",
             "Tráfico de personas (coyotaje)",
             "Otro delito",
             "No se observan delitos",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Texto (corto)",
         "label": "Indique cuál es ese otro delito:",
         "name": "delitos_otro",
         "required": True,
         "opciones": [],
         "appearance": None, "choice_filter": None,
         "relevant": f"selected(${{delitos_lista}}, '{slugify_name('Otro delito')}')"},

        {"tipo_ui": "Selección múltiple",
         "label": "19. Según su conocimiento u observación, ¿de qué forma se presenta la venta de drogas en el distrito?",
         "name": "venta_drogas_forma",
         "required": True,
         "opciones": [
             "En espacios cerrados (casas, edificaciones u otros inmuebles)",
             "En vía pública",
             "De forma ocasional o móvil (sin punto fijo)",
             "No se observa venta de drogas",
             "Otro",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Texto (corto)",
         "label": "Indique cuál es ese otro modo de venta de drogas:",
         "name": "venta_drogas_forma_otro",
         "required": True,
         "opciones": [],
         "appearance": None, "choice_filter": None,
         "relevant": f"selected(${{venta_drogas_forma}}, '{slugify_name('Otro')}')"},

        {"tipo_ui": "Selección múltiple",
         "label": "20. Delitos contra la vida",
         "name": "delitos_vida",
         "required": True,
         "opciones": [
             "Homicidios (muerte intencional de una persona)",
             "Personas heridas de forma intencional (heridos)",
             "Femicide (homicidio de una mujer por razones de género)",
             "No se observan delitos contra la vida",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple",
         "label": "21. Delitos sexuales",
         "name": "delitos_sexuales",
         "required": True,
         "opciones": [
             "Abuso sexual (tocamientos u otros actos sexuales sin consentimiento)",
             "Violación (acceso sexual sin consentimiento)",
             "Acoso sexual (insinuaciones, solicitudes o conductas sexuales no deseadas)",
             "Acoso callejero (comentarios, gestos o conductas sexuales en espacios públicos)",
             "No se observan delitos sexuales",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple",
         "label": "22. Asaltos",
         "name": "asaltos",
         "required": True,
         "opciones": [
             "Asalto a personas",
             "Asalto a comercio",
             "Asalto a vivienda",
             "Asalto a transporte público",
             "No se observan asaltos",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple",
         "label": "23. Estafas",
         "name": "estafas",
         "required": True,
         "opciones": [
             "Billetes falsos",
             "Documentos falsos",
             "Estafas relacionadas con la compra o venta de oro",
             "Lotería falsa",
             "Estafas informáticas (por internet, redes sociales o correos electrónicos)",
             "Estafas telefónicas",
             "Estafas con tarjetas (clonación, cargos no autorizados)",
             "No se observan estafas",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple",
         "label": "24. Robo (Sustracción de artículos mediante la utilización de la fuerza)",
         "name": "robos",
         "required": True,
         "opciones": [
             "Robo a comercios",
             "Robo a edificaciones",
             "Robo a viviendas",
             "Robo de vehículos completos",
             "Robo a vehículos (tacha)",
             "Robo de ganado (destace)",
             "Robo de bienes agrícolas",
             "Robo de cultivos",
             "Robo de cable",
             "No se observan robos",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple",
         "label": "25. Abandono de personas",
         "name": "abandono",
         "required": True,
         "opciones": [
             "Abandono de adulto mayor",
             "Abandono de menor de edad",
             "Abandono de incapaz",
             "No se observan situaciones de abandono",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple",
         "label": "26. Explotación infantil",
         "name": "explotacion_infantil",
         "required": True,
         "opciones": [
             "Sexual",
             "Laboral",
             "No se observan",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple",
         "label": "27. Delitos ambientales",
         "name": "delitos_ambientales",
         "required": True,
         "opciones": [
             "Caza ilegal",
             "Pesca ilegal",
             "Tala ilegal",
             "Extracción ilegal de material minero",
             "No se observan delitos ambientales",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple",
         "label": "28. Trata de personas",
         "name": "trata_personas",
         "required": True,
         "opciones": [
             "Con fines laborales",
             "Con fines sexuales",
             "No se observan situaciones de trata de personas",
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        # ---------------- Victimización — Apartado A: Violencia intrafamiliar (29–29.3) ----------------
        {"tipo_ui": "Selección única",
         "label": "29. Durante los últimos 12 meses, ¿usted o algún miembro de su hogar ha sido afectado por alguna situación de violencia intrafamiliar (violencia doméstica)?",
         "name": "vi_12m",
         "required": True,
         "opciones": ["Sí", "No"],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple",
         "label": "29.1. ¿Qué tipo(s) de violencia intrafamiliar (violencia doméstica) se presentaron?",
         "name": "vi_tipos",
         "required": True,
         "opciones": [
             "Violencia psicológica (gritos, amenazas, humillaciones, maltratos, entre otros)",
             "Violencia física (agresiones físicas, empujones, golpes, entre otros)",
             "Violencia vicaria (uso de hijas, hijos u otras personas para causar daño emocional)",
             "Violencia patrimonial (destrucción, retención o control de bienes, documentos o dinero)",
             "Violencia sexual (actos de carácter sexual sin consentimiento)",
         ],
         "appearance": None, "choice_filter": None, "relevant": f"${{vi_12m}}='{CONSENT_SI}'"},

        {"tipo_ui": "Selección única",
         "label": "29.2 ¿En relación con la situación de violencia intrafamiliar indicada anteriormente, usted o algún miembro de su hogar solicitó medidas de protección?",
         "name": "vi_medidas_proteccion",
         "required": True,
         "opciones": ["Sí", "No", "No recuerda"],
         "appearance": None, "choice_filter": None, "relevant": f"${{vi_12m}}='{CONSENT_SI}'"},

        {"tipo_ui": "Selección única",
         "label": "29.3. ¿Cómo valora el abordaje de la Fuerza Pública ante esta situación?",
         "name": "vi_valoracion_fp",
         "required": True,
         "opciones": ["Excelente", "Bueno", "Regular", "Malo", "Muy malo"],
         "appearance": None, "choice_filter": None, "relevant": f"${{vi_12m}}='{CONSENT_SI}'"},
    ]

    st.session_state.preguntas = seed
    st.session_state.seed_cargado = True

# ------------------------------------------------------------------------------------------
# Sidebar: Metadatos + Exportar/Importar proyecto
# ------------------------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuración")
    form_title = st.text_input(
        "Título del formulario",
        value=(f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad")
    )
    idioma = st.selectbox("Idioma por defecto (default_language)", options=["es", "en"], index=0)
    version_auto = datetime.now().strftime("%Y%m%d%H%M")
    version = st.text_input("Versión (settings.version)", value=version_auto)

    st.markdown("---")
    st.caption("💾 Exporta/Importa tu proyecto (JSON)")
    col_exp, col_imp = st.columns(2)

    if col_exp.button("Exportar proyecto (JSON)", use_container_width=True):
        proj = {
            "form_title": form_title,
            "idioma": idioma,
            "version": version,
            "preguntas": st.session_state.preguntas,
            "reglas_visibilidad": st.session_state.reglas_visibilidad,
            "reglas_finalizar": st.session_state.reglas_finalizar,
            "choices_ext_rows": st.session_state.choices_ext_rows,
            "choices_extra_cols": list(st.session_state.choices_extra_cols),
        }
        jbuf = BytesIO(json.dumps(proj, ensure_ascii=False, indent=2).encode("utf-8"))
        st.download_button(
            "Descargar JSON",
            data=jbuf,
            file_name="proyecto_encuesta.json",
            mime="application/json",
            use_container_width=True
        )

    up = col_imp.file_uploader("Importar JSON", type=["json"], label_visibility="collapsed")
    if up is not None:
        try:
            raw = up.read().decode("utf-8")
            data = json.loads(raw)
            st.session_state.preguntas = list(data.get("preguntas", []))
            st.session_state.reglas_visibilidad = list(data.get("reglas_visibilidad", []))
            st.session_state.reglas_finalizar = list(data.get("reglas_finalizar", []))
            st.session_state.choices_ext_rows = list(data.get("choices_ext_rows", []))
            st.session_state.choices_extra_cols = set(data.get("choices_extra_cols", []))

            _asegurar_placeholders_catalogo()
            _rerun()
        except Exception as e:
            st.error(f"No se pudo importar el JSON: {e}")

# ------------------------------------------------------------------------------------------
# Constructor: Agregar nuevas preguntas
# ------------------------------------------------------------------------------------------
st.subheader("📝 Diseña tus preguntas")

with st.form("form_add_q", clear_on_submit=False):
    tipo_ui = st.selectbox("Tipo de pregunta", options=TIPOS)
    label = st.text_input("Etiqueta (texto exacto)")
    sugerido = slugify_name(label) if label else ""
    col_n1, col_n2, col_n3 = st.columns([2, 1, 1])
    name = col_n1.text_input("Nombre interno (XLSForm 'name')", value=sugerido)
    required = col_n2.checkbox("Requerida", value=False)
    appearance = col_n3.text_input("Appearance (opcional)", value="")
    opciones = []
    if tipo_ui in ("Selección única", "Selección múltiple"):
        st.markdown("**Opciones (una por línea)**")
        txt_opts = st.text_area("Opciones", height=120)
        if txt_opts.strip():
            opciones = [o.strip() for o in txt_opts.splitlines() if o.strip()]
    add = st.form_submit_button("➕ Agregar pregunta")

if add:
    if not label.strip():
        st.warning("Agrega una etiqueta.")
    else:
        base = slugify_name(name or label)
        usados = {q["name"] for q in st.session_state.preguntas}
        unico = asegurar_nombre_unico(base, usados)
        st.session_state.preguntas.append({
            "tipo_ui": tipo_ui,
            "label": label.strip(),
            "name": unico,
            "required": required,
            "opciones": opciones,
            "appearance": (appearance.strip() or None),
            "choice_filter": None,
            "relevant": None
        })
        st.success(f"Pregunta agregada: **{label}** (name: `{unico}`)")

# ------------------------------------------------------------------------------------------
# Lista / Ordenado / Edición (completa)
# ------------------------------------------------------------------------------------------
st.subheader("📚 Preguntas (ordénalas y edítalas)")
if not st.session_state.preguntas:
    st.info("Aún no has agregado preguntas.")
else:
    for idx, q in enumerate(st.session_state.preguntas):
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([4, 2, 2, 2, 2])
            c1.markdown(f"**{idx+1}. {q['label']}**")
            meta = f"type: {q['tipo_ui']}  •  name: `{q['name']}`  •  requerida: {'sí' if q['required'] else 'no'}"
            if q.get("appearance"):
                meta += f"  •  appearance: `{q['appearance']}`"
            if q.get("choice_filter"):
                meta += f"  •  choice_filter: `{q['choice_filter']}`"
            if q.get("relevant"):
                meta += f"  •  relevant: `{q['relevant']}`"
            if q.get("list_override"):
                meta += f"  •  list_override: `{q['list_override']}`"
            c1.caption(meta)
            if q["tipo_ui"] in ("Selección única", "Selección múltiple"):
                c1.caption("Opciones: " + ", ".join(q.get("opciones") or []))

            up_btn = c2.button("⬆️ Subir", key=f"up_{idx}", use_container_width=True, disabled=(idx == 0))
            down_btn = c3.button("⬇️ Bajar", key=f"down_{idx}", use_container_width=True, disabled=(idx == len(st.session_state.preguntas) - 1))
            edit_btn = c4.button("✏️ Editar", key=f"edit_{idx}", use_container_width=True)
            del_btn = c5.button("🗑️ Eliminar", key=f"del_{idx}", use_container_width=True)

            if up_btn:
                st.session_state.preguntas[idx - 1], st.session_state.preguntas[idx] = st.session_state.preguntas[idx], st.session_state.preguntas[idx - 1]
                _rerun()
            if down_btn:
                st.session_state.preguntas[idx + 1], st.session_state.preguntas[idx] = st.session_state.preguntas[idx], st.session_state.preguntas[idx + 1]
                _rerun()

            if edit_btn:
                st.markdown("**Editar esta pregunta**")
                ne_label = st.text_input("Etiqueta", value=q["label"], key=f"e_label_{idx}")
                ne_name = st.text_input("Nombre interno (name)", value=q["name"], key=f"e_name_{idx}")
                ne_required = st.checkbox("Requerida", value=q["required"], key=f"e_req_{idx}")
                ne_appearance = st.text_input("Appearance", value=q.get("appearance") or "", key=f"e_app_{idx}")
                ne_choice_filter = st.text_input("choice_filter (opcional)", value=q.get("choice_filter") or "", key=f"e_cf_{idx}")
                ne_relevant = st.text_input("relevant (opcional)", value=q.get("relevant") or "", key=f"e_rel_{idx}")

                # list_override NO se expone aquí para no romper matriz por accidente.

                ne_opciones = q.get("opciones") or []
                if q["tipo_ui"] in ("Selección única", "Selección múltiple"):
                    ne_opts_txt = st.text_area("Opciones (una por línea)", value="\n".join(ne_opciones), key=f"e_opts_{idx}")
                    ne_opciones = [o.strip() for o in ne_opts_txt.splitlines() if o.strip()]

                col_ok, col_cancel = st.columns(2)
                if col_ok.button("💾 Guardar cambios", key=f"e_save_{idx}", use_container_width=True):
                    new_base = slugify_name(ne_name or ne_label)
                    usados = {qq["name"] for j, qq in enumerate(st.session_state.preguntas) if j != idx}
                    ne_name_final = new_base if new_base not in usados else asegurar_nombre_unico(new_base, usados)

                    st.session_state.preguntas[idx]["label"] = ne_label.strip() or q["label"]
                    st.session_state.preguntas[idx]["name"] = ne_name_final
                    st.session_state.preguntas[idx]["required"] = ne_required
                    st.session_state.preguntas[idx]["appearance"] = ne_appearance.strip() or None
                    st.session_state.preguntas[idx]["choice_filter"] = ne_choice_filter.strip() or None
                    st.session_state.preguntas[idx]["relevant"] = ne_relevant.strip() or None
                    if q["tipo_ui"] in ("Selección única", "Selección múltiple"):
                        st.session_state.preguntas[idx]["opciones"] = ne_opciones
                    st.success("Cambios guardados.")
                    _rerun()

                if col_cancel.button("Cancelar", key=f"e_cancel_{idx}", use_container_width=True):
                    _rerun()

            if del_btn:
                del st.session_state.preguntas[idx]
                st.warning("Pregunta eliminada.")
                _rerun()

# ------------------------------------------------------------------------------------------
# Condicionales (panel)
# ------------------------------------------------------------------------------------------
st.subheader("🔀 Condicionales (mostrar / finalizar)")
if not st.session_state.preguntas:
    st.info("Agrega preguntas para definir condicionales.")
else:
    with st.expander("👁️ Mostrar pregunta si se cumple condición", expanded=False):
        names = [q["name"] for q in st.session_state.preguntas]
        labels_by_name = {q["name"]: q["label"] for q in st.session_state.preguntas}

        target = st.selectbox("Pregunta a mostrar (target)", options=names,
                              format_func=lambda n: f"{n} — {labels_by_name[n]}")
        src = st.selectbox("Depende de (source)", options=names,
                           format_func=lambda n: f"{n} — {labels_by_name[n]}")
        op = st.selectbox("Operador", options=["=", "selected"])
        src_q = next((qq for qq in st.session_state.preguntas if qq["name"] == src), None)

        vals = []
        if src_q and src_q.get("opciones"):
            vals = st.multiselect("Valores (usa texto, internamente se usará slug)", options=src_q["opciones"])
            vals = [slugify_name(v) for v in vals]
        else:
            manual = st.text_input("Valor (si la pregunta no tiene opciones)")
            vals = [slugify_name(manual)] if manual.strip() else []

        if st.button("➕ Agregar regla de visibilidad"):
            if target == src:
                st.error("Target y Source no pueden ser la misma pregunta.")
            elif not vals:
                st.error("Indica al menos un valor.")
            else:
                st.session_state.reglas_visibilidad.append({"target": target, "src": src, "op": op, "values": vals})
                st.success("Regla agregada.")
                _rerun()

        if st.session_state.reglas_visibilidad:
            st.markdown("**Reglas de visibilidad actuales:**")
            for i, r in enumerate(st.session_state.reglas_visibilidad):
                st.write(f"- Mostrar **{r['target']}** si **{r['src']}** {r['op']} {r['values']}")
                if st.button(f"Eliminar regla #{i+1}", key=f"del_vis_{i}"):
                    del st.session_state.reglas_visibilidad[i]
                    _rerun()

    with st.expander("⏹️ Finalizar temprano si se cumple condición", expanded=False):
        names = [q["name"] for q in st.session_state.preguntas]
        labels_by_name = {q["name"]: q["label"] for q in st.session_state.preguntas}
        src2 = st.selectbox("Condición basada en", options=names,
                            format_func=lambda n: f"{n} — {labels_by_name[n]}", key="final_src")
        op2 = st.selectbox("Operador", options=["=", "selected", "!="], key="final_op")
        src2_q = next((qq for qq in st.session_state.preguntas if qq["name"] == src2), None)

        vals2 = []
        if src2_q and src2_q.get("opciones"):
            vals2 = st.multiselect("Valores (slug interno)", options=src2_q["opciones"], key="final_vals")
            vals2 = [slugify_name(v) for v in vals2]
        else:
            manual2 = st.text_input("Valor (si no hay opciones)", key="final_manual")
            vals2 = [slugify_name(manual2)] if manual2.strip() else []

        if st.button("➕ Agregar regla de finalización"):
            if not vals2:
                st.error("Indica al menos un valor.")
            else:
                idx_src = next((i for i, qq in enumerate(st.session_state.preguntas) if qq["name"] == src2), 0)
                st.session_state.reglas_finalizar.append({"src": src2, "op": op2, "values": vals2, "index_src": idx_src})
                st.success("Regla agregada.")
                _rerun()

        if st.session_state.reglas_finalizar:
            st.markdown("**Reglas de finalización actuales:**")
            for i, r in enumerate(st.session_state.reglas_finalizar):
                st.write(f"- Si **{r['src']}** {r['op']} {r['values']} ⇒ ocultar lo que sigue (efecto fin)")
                if st.button(f"Eliminar regla fin #{i+1}", key=f"del_fin_{i}"):
                    del st.session_state.reglas_finalizar[i]
                    _rerun()

# ------------------------------------------------------------------------------------------
# Construcción XLSForm (Intro + Consentimiento + Páginas)
# ------------------------------------------------------------------------------------------
def _get_logo_media_name():
    return logo_media_name

def construir_xlsform(preguntas, form_title: str, idioma: str, version: str,
                      reglas_vis, reglas_fin):
    survey_rows = []
    choices_rows = []
    choices_keys = set()  # dedup choices por (list_name,name)

    def _choices_add_unique(row: Dict):
        key = (row.get("list_name"), row.get("name"))
        if key not in choices_keys:
            choices_rows.append(row)
            choices_keys.add(key)

    idx_by_name = {q.get("name"): i for i, q in enumerate(preguntas)}

    vis_by_target = {}
    for r in reglas_vis:
        vis_by_target.setdefault(r["target"], []).append(
            {"src": r["src"], "op": r.get("op", "="), "values": r.get("values", [])}
        )

    fin_conds = []
    for r in reglas_fin:
        cond = build_relevant_expr([{"src": r["src"], "op": r.get("op", "="), "values": r.get("values", [])}])
        if cond:
            fin_conds.append((r["index_src"], cond))

    def add_q(q, idx):
        x_type, default_app, list_name = map_tipo_to_xlsform(q["tipo_ui"], q["name"])

        # FIX MATRIZ: permitir forzar list_name compartido con list_override
        list_override = q.get("list_override")
        if list_override and isinstance(x_type, str):
            if x_type.startswith("select_one "):
                x_type = f"select_one {list_override}"
                list_name = list_override
            elif x_type.startswith("select_multiple "):
                x_type = f"select_multiple {list_override}"
                list_name = list_override

        rel_manual = q.get("relevant") or None
        rel_panel = build_relevant_expr(vis_by_target.get(q["name"], []))

        nots = [xlsform_not(cond) for idx_src, cond in fin_conds if idx_src < idx]
        rel_fin = "(" + " and ".join(nots) + ")" if nots else None

        parts = [p for p in [rel_manual, rel_panel, rel_fin] if p]
        rel_final = parts[0] if parts and len(parts) == 1 else ("(" + ") and (".join(parts) + ")" if parts else None)

        row = {"type": x_type, "name": q["name"], "label": q["label"]}
        if q.get("required"):
            row["required"] = "yes"
        app = q.get("appearance") or default_app
        if app:
            row["appearance"] = app
        if q.get("choice_filter"):
            row["choice_filter"] = q["choice_filter"]
        if rel_final:
            row["relevant"] = rel_final

        # Constraints placeholders SOLO si NO hay catálogo real (para no forzar "escoja un")
        if not _hay_catalogo_real():
            if q["name"] == "canton":
                row["constraint"] = ". != '__pick_canton__'"
                row["constraint_message"] = "Seleccione un cantón válido."
            if q["name"] == "distrito":
                row["constraint"] = ". != '__pick_distrito__'"
                row["constraint_message"] = "Seleccione un distrito válido."

        survey_rows.append(row)

        # Generar choices (excepto Cantón/Distrito)
        if list_name and q["name"] not in {"canton", "distrito"}:
            usados = set()
            for opt_label in (q.get("opciones") or []):
                base = slugify_name(opt_label)
                opt_name = asegurar_nombre_unico(base, usados)
                usados.add(opt_name)
                _choices_add_unique({"list_name": list_name, "name": opt_name, "label": str(opt_label)})

    # Página 1: Intro
    survey_rows += [
        {"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"},
        {"type": "note", "name": "intro_logo", "label": form_title, "media::image": _get_logo_media_name()},
        {"type": "note", "name": "intro_texto", "label": INTRO_COMUNIDAD},
        {"type": "end_group", "name": "p1_end"},
    ]

    # Página 2: Consentimiento
    idx_consent = idx_by_name.get("consentimiento", None)
    survey_rows.append({"type": "begin_group", "name": "p2_consentimiento", "label": "Consentimiento informado", "appearance": "field-list"})
    survey_rows.append({"type": "note", "name": "cons_title", "label": CONSENTIMIENTO_TITULO})
    for i, txt in enumerate(CONSENTIMIENTO_BLOQUES, start=1):
        survey_rows.append({"type": "note", "name": f"cons_b{i:02d}", "label": txt})

    if idx_consent is not None:
        add_q(preguntas[idx_consent], idx_consent)
    survey_rows.append({"type": "end_group", "name": "p2_consentimiento_end"})

    # ✅ Página final si NO acepta (para que pueda “Enviar” sin seguir a las demás)
    survey_rows.append({
        "type": "begin_group",
        "name": "p_fin_no",
        "label": "Finalización",
        "appearance": "field-list",
        "relevant": f"${{consentimiento}}='{CONSENT_NO}'"
    })
    survey_rows.append({
        "type": "note",
        "name": "fin_no_texto",
        "label": "Gracias. Al no aceptar participar, la encuesta finaliza en este punto."
    })
    survey_rows.append({"type": "end_group", "name": "p_fin_no_end"})

    # Sets por página (desde aquí, todo se muestra SOLO si consentimiento = Sí)
    rel_si = f"${{consentimiento}}='{CONSENT_SI}'"

    p_demograficos = {"canton", "distrito", "edad_rango", "genero", "escolaridad", "relacion_zona"}

    p_percepcion = {
        "percep_seg_distrito",
        "motivos_inseguridad_distrito",
        "otro_problema_inseg_distrito",
        "cambio_seguridad_12m",
        "motivo_cambio_12m",
        "seg_discotecas_bares",
        "seg_espacios_recreativos",
        "seg_lugar_residencia",
        "seg_paradas_estaciones",
        "seg_puentes_peatonales",
        "seg_transporte_publico",
        "seg_zona_bancaria",
        "seg_zona_comercio",
        "seg_zonas_residenciales",
        "seg_zonas_francas",
        "seg_lugares_turisticos",
        "seg_centros_educativos",
        "foco_inseguridad",
        "foco_inseguridad_otro",
        "razones_foco_inseguridad",
    }

    p_riesgos = {
        "problematicas_distrito",
        "problematicas_otro",
        "carencias_inversion_social",
        "carencias_inversion_social_otro",
        "consumo_drogas_donde",
        "infra_vial_deficiencias",
        "puntos_venta_drogas",
        "puntos_venta_drogas_otro",
        "inseguridad_transporte",
        "inseguridad_transporte_otro",
    }

    p_delitos = {
        "delitos_lista",
        "delitos_otro",
        "venta_drogas_forma",
        "venta_drogas_forma_otro",
        "delitos_vida",
        "delitos_sexuales",
        "asaltos",
        "estafas",
        "robos",
        "abandono",
        "explotacion_infantil",
        "delitos_ambientales",
        "trata_personas",
    }

    p_vict_vi = {"vi_12m", "vi_tipos", "vi_medidas_proteccion", "vi_valoracion_fp"}

    def add_page(group_name, page_label, names_set, intro_note_text: str = None,
                 group_appearance: str = "field-list", group_relevant: str = None):
        row = {"type": "begin_group", "name": group_name, "label": page_label, "appearance": group_appearance}
        if group_relevant:
            row["relevant"] = group_relevant
        survey_rows.append(row)

        if intro_note_text:
            note = {"type": "note", "name": f"{group_name}_intro", "label": intro_note_text}
            if group_relevant:
                note["relevant"] = group_relevant
            survey_rows.append(note)

        for i, qq in enumerate(preguntas):
            if qq["name"] in names_set:
                add_q(qq, i)

        survey_rows.append({"type": "end_group", "name": f"{group_name}_end"})

    add_page("p3_demograficos", "I. DATOS DEMOGRÁFICOS", p_demograficos, intro_note_text=None,
             group_appearance="field-list", group_relevant=rel_si)

    add_page("p4_percepcion_distrito", "II. PERCEPCIÓN CIUDADANA DE SEGURIDAD EN EL DISTRITO", p_percepcion,
             intro_note_text=INTRO_PERCEPCION_DISTRITO, group_appearance="field-list", group_relevant=rel_si)

    add_page("p5_riesgos_iii", "III. RIESGOS, DELITOS, VICTIMIZACIÓN Y EVALUACIÓN POLICIAL", p_riesgos,
             intro_note_text=INTRO_RIESGOS_III, group_appearance="field-list", group_relevant=rel_si)

    # ✅ Página SOLO Delitos (título Delitos + intro + preguntas 18–28)
    add_page("p6_delitos", "Delitos", p_delitos,
             intro_note_text=INTRO_DELITOS, group_appearance="field-list", group_relevant=rel_si)

    # ✅ Página Victimización (29–29.3)
    add_page("p7_vict_vi", "Victimización — Apartado A: Violencia intrafamiliar", p_vict_vi,
             intro_note_text=INTRO_VICT_VI, group_appearance="field-list", group_relevant=rel_si)

    # Encapsular matriz 9 en table-list (ya comparten list_override)
    def _postprocesar_matriz_table_list(df_survey: pd.DataFrame) -> pd.DataFrame:
        matriz_names = [
            "seg_discotecas_bares",
            "seg_espacios_recreativos",
            "seg_lugar_residencia",
            "seg_paradas_estaciones",
            "seg_puentes_peatonales",
            "seg_transporte_publico",
            "seg_zona_bancaria",
            "seg_zona_comercio",
            "seg_zonas_residenciales",
            "seg_zonas_francas",
            "seg_lugares_turisticos",
            "seg_centros_educativos",
        ]
        idxs = df_survey.index[df_survey["name"].isin(matriz_names)].tolist()
        if not idxs:
            return df_survey

        start = min(idxs)
        end = max(idxs)

        begin_row = {
            "type": "begin_group",
            "name": "matriz_seguridad_9",
            "label": "9. En términos de seguridad, indique qué tan seguros percibe los siguientes espacios de su distrito.",
            "appearance": "table-list",
        }
        end_row = {"type": "end_group", "name": "matriz_seguridad_9_end"}

        top = df_survey.iloc[:start].copy()
        mid = df_survey.iloc[start:end + 1].copy()
        bot = df_survey.iloc[end + 1:].copy()

        return pd.concat([top, pd.DataFrame([begin_row]), mid, pd.DataFrame([end_row]), bot], ignore_index=True)

    # Choices del catálogo (filtrando placeholders si hay catálogo real)
    _asegurar_placeholders_catalogo()
    catalog_rows = [dict(r) for r in st.session_state.choices_ext_rows]
    catalog_rows = _filtrar_placeholders_si_hay_catalogo(catalog_rows)
    for r in catalog_rows:
        _choices_add_unique(r)

    # DataFrames
    survey_cols_all = set().union(*[r.keys() for r in survey_rows])
    survey_cols = [c for c in [
        "type", "name", "label", "required", "appearance", "choice_filter",
        "relevant", "constraint", "constraint_message", "media::image"
    ] if c in survey_cols_all]
    for k in sorted(survey_cols_all):
        if k not in survey_cols:
            survey_cols.append(k)

    df_survey = pd.DataFrame(survey_rows, columns=survey_cols)
    df_survey = _postprocesar_matriz_table_list(df_survey)

    choices_cols_all = set()
    for r in choices_rows:
        choices_cols_all.update(r.keys())
    base_choice_cols = ["list_name", "name", "label"]
    for extra in sorted(choices_cols_all):
        if extra not in base_choice_cols:
            base_choice_cols.append(extra)
    df_choices = pd.DataFrame(choices_rows, columns=base_choice_cols) if choices_rows else pd.DataFrame(columns=base_choice_cols)

    df_settings = pd.DataFrame([{
        "form_title": form_title,
        "version": version,
        "default_language": idioma,
        "style": "pages",
    }], columns=["form_title", "version", "default_language", "style"])

    return df_survey, df_choices, df_settings

def descargar_excel_xlsform(df_survey, df_choices, df_settings, nombre_archivo: str):
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
            for col_idx, col_name in enumerate(list(df.columns)):
                ws.set_column(col_idx, col_idx, max(14, min(55, len(str(col_name)) + 8)))

    buffer.seek(0)
    st.download_button(
        label=f"📥 Descargar XLSForm ({nombre_archivo})",
        data=buffer,
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# ------------------------------------------------------------------------------------------
# Exportar / Vista previa XLSForm
# ------------------------------------------------------------------------------------------
st.markdown("---")
st.subheader("📦 Generar XLSForm (Excel) para Survey123")

if st.button("🧮 Construir XLSForm", use_container_width=True, disabled=not st.session_state.preguntas):
    try:
        names = [q["name"] for q in st.session_state.preguntas]
        if len(names) != len(set(names)):
            st.error("Hay 'name' duplicados. Edita las preguntas para que cada 'name' sea único.")
        else:
            df_survey, df_choices, df_settings = construir_xlsform(
                st.session_state.preguntas,
                form_title=(f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad"),
                idioma="es",
                version=(version.strip() or datetime.now().strftime("%Y%m%d%H%M")),
                reglas_vis=st.session_state.reglas_visibilidad,
                reglas_fin=st.session_state.reglas_finalizar
            )
            st.success("XLSForm construido. Vista previa:")
            c1, c2, c3 = st.columns(3)
            c1.markdown("**Hoja: survey**");   c1.dataframe(df_survey, use_container_width=True, hide_index=True)
            c2.markdown("**Hoja: choices**");  c2.dataframe(df_choices, use_container_width=True, hide_index=True)
            c3.markdown("**Hoja: settings**"); c3.dataframe(df_settings, use_container_width=True, hide_index=True)

            nombre_archivo = slugify_name(form_title) + "_xlsform.xlsx"
            descargar_excel_xlsform(df_survey, df_choices, df_settings, nombre_archivo)

            if st.session_state.get("_logo_bytes"):
                st.download_button(
                    "📥 Descargar logo para carpeta media",
                    data=st.session_state["_logo_bytes"],
                    file_name=logo_media_name,
                    mime="image/png",
                    use_container_width=True
                )

            st.info("Publica en Survey123 Connect: crea encuesta desde archivo, copia el logo a `media/` y publica.")
    except Exception as e:
        st.error(f"Ocurrió un error al generar el XLSForm: {e}")
