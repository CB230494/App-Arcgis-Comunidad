# -*- coding: utf-8 -*-
# ==========================================================================================
# ============================== PARTE 1/10 ===============================================
# ============ Encabezado, imports, config y helpers base =================================
# ==========================================================================================
#
# App: Encuesta Comunidad → XLSForm para ArcGIS Survey123 (versión extendida)
# - Constructor completo (agregar/editar/ordenar/borrar)
# - Condicionales (relevant) + finalizar temprano
# - Listas en cascada (choice_filter) Cantón→Distrito (SIN Barrio)
# - Exportar/Importar proyecto (JSON)
# - Exportar a XLSForm (survey/choices/settings)
# - PÁGINAS reales (style="pages")
# - Portada con logo (media::image) y texto de introducción
# - Word/PDF (según tus páginas definidas)
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
    "GPS (ubicación)"
]

def _rerun():
    """Compatibilidad Streamlit rerun."""
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

def slugify_name(texto: str) -> str:
    """Convierte texto a un identificador seguro para XLSForm (minúsculas y _)."""
    if not texto:
        return "campo"
    t = texto.lower()
    t = re.sub(r"[áàäâ]", "a", t); t = re.sub(r"[éèëê]", "e", t)
    t = re.sub(r"[íìïî]", "i", t); t = re.sub(r"[óòöô]", "o", t)
    t = re.sub(r"[úùüû]", "u", t); t = re.sub(r"ñ", "n", t)
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t or "campo"

def asegurar_nombre_unico(base: str, usados: set) -> str:
    """Evita duplicados de name: base, base_2, base_3, ..."""
    if base not in usados:
        return base
    i = 2
    while f"{base}_{i}" in usados:
        i += 1
    return f"{base}_{i}"

def map_tipo_to_xlsform(tipo_ui: str, name: str):
    """
    Mapea el tipo UI a XLSForm:
    - Retorna (type, appearance_default, list_name_si_aplica)
    """
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

def xlsform_or_expr(conds: List[str] | None):
    """Une condiciones con OR. Si hay 1, la devuelve; si hay varias, las encierra."""
    if not conds:
        return None
    if len(conds) == 1:
        return conds[0]
    return "(" + " or ".join(conds) + ")"

def xlsform_not(expr: str | None):
    """NOT(expr) si expr existe."""
    if not expr:
        return None
    return f"not({expr})"

def build_relevant_expr(rules_for_target: List[Dict]):
    """
    Construye expresión relevant (OR de reglas). Soporta:
    - op "=" (select_one)
    - op "selected" (select_multiple)
    - op "!="
    """
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
# ==========================================================================================
# ============================== PARTE 2/10 ===============================================
# ======== Catálogo Cantón → Distrito (SIN Barrio) + vista previa + helpers choices ========
# ==========================================================================================

# ------------------------------------------------------------------------------------------
# Catálogo manual por lotes: Cantón → Distrito (SIN Barrio)
# ------------------------------------------------------------------------------------------
if "choices_ext_rows" not in st.session_state:
    st.session_state.choices_ext_rows = []  # filas para hoja choices
if "choices_extra_cols" not in st.session_state:
    st.session_state.choices_extra_cols = set()

def _append_choice_unique(row: Dict):
    """Inserta fila en choices evitando duplicados por (list_name,name)."""
    key = (row.get("list_name"), row.get("name"))
    exists = any((r.get("list_name"), r.get("name")) == key for r in st.session_state.choices_ext_rows)
    if not exists:
        st.session_state.choices_ext_rows.append(row)

st.markdown("### 📚 Catálogo Cantón → Distrito (por lotes)")

with st.expander("Agrega un lote (un Cantón y uno o varios Distritos)", expanded=True):
    col_c1, col_c2 = st.columns(2)
    canton_txt = col_c1.text_input("Cantón (una vez)", value="")
    distritos_txt = col_c2.text_area(
        "Distritos del cantón (uno por línea)",
        value="",
        height=120
    )

    col_b1, col_b2, col_b3 = st.columns([1, 1, 2])
    add_lote = col_b1.button("Agregar lote", type="primary", use_container_width=True)
    clear_all = col_b2.button("Limpiar catálogo", use_container_width=True)

    if clear_all:
        st.session_state.choices_ext_rows = []
        st.success("Catálogo limpiado.")

    if add_lote:
        c = canton_txt.strip()
        distritos = [d.strip() for d in distritos_txt.splitlines() if d.strip()]

        if not c or not distritos:
            st.error("Debes indicar Cantón y al menos un Distrito.")
        else:
            slug_c = slugify_name(c)

            # columnas extra usadas por filtros/placeholder
            st.session_state.choices_extra_cols.update({"canton_key", "any"})

            # Placeholders (una sola vez por lista)
            _append_choice_unique({
                "list_name": "list_canton",
                "name": "__pick_canton__",
                "label": "— escoja un cantón —"
            })
            _append_choice_unique({
                "list_name": "list_distrito",
                "name": "__pick_distrito__",
                "label": "— escoja un cantón —",
                "any": "1"
            })

            # Cantón (evita duplicados)
            _append_choice_unique({"list_name": "list_canton", "name": slug_c, "label": c})

            # Distritos del cantón
            usados_d = set()
            for d in distritos:
                slug_d = asegurar_nombre_unico(slugify_name(d), usados_d)
                usados_d.add(slug_d)
                _append_choice_unique({
                    "list_name": "list_distrito",
                    "name": slug_d,
                    "label": d,
                    "canton_key": slug_c
                })

            st.success(f"Lote agregado: {c} → {len(distritos)} distritos.")

# Vista previa de catálogo
if st.session_state.choices_ext_rows:
    st.dataframe(
        pd.DataFrame(st.session_state.choices_ext_rows),
        use_container_width=True,
        hide_index=True,
        height=240
    )
else:
    st.info("Aún no has cargado el catálogo Cantón → Distrito.")
# ==========================================================================================
# ============================== PARTE 3/10 ===============================================
# ============ Cabecera (Logo + Delegación) + Estado + Intro + Precarga (seed) ============
# ======= IMPORTANTE: Seed actualizado para SOLO Cantón y Distrito (sin Barrio) ===========
# ==========================================================================================

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
# Estado
# ------------------------------------------------------------------------------------------
if "preguntas" not in st.session_state:
    st.session_state.preguntas = []
if "reglas_visibilidad" not in st.session_state:
    st.session_state.reglas_visibilidad = []
if "reglas_finalizar" not in st.session_state:
    st.session_state.reglas_finalizar = []

# ------------------------------------------------------------------------------------------
# Intro (Página 1)
# ------------------------------------------------------------------------------------------
INTRO_COMUNIDAD = (
    "Con el fin de hacer más segura nuestra comunidad, queremos concentrarnos en los problemas de "
    "seguridad más importantes. Por lo que debemos trabajar juntos, tanto con el gobierno local como "
    "con otras instituciones y la comunidad, para reducir los delitos y riesgos que afectan a la gente. "
    "Es importante recordar que la información que nos proporcionas es confidencial y solo se usará para "
    "mejorar la seguridad en nuestra área."
)

# ------------------------------------------------------------------------------------------
# Precarga de preguntas (P2 incluida; SOLO Cantón y Distrito; sin Barrio)
# ------------------------------------------------------------------------------------------
if "seed_cargado" not in st.session_state:

    v_si = slugify_name("Si")
    v_no = slugify_name("No")
    v_mas_seguro = slugify_name("Más seguro")
    v_igual = slugify_name("Igual")
    v_menos_seg = slugify_name("Menos seguro")

    seed = [
        # ---------------- Página 2: Datos demográficos ----------------
        {"tipo_ui": "Selección única", "label": "Cantón", "name": "canton", "required": True,
         "opciones": [], "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección única", "label": "Distrito", "name": "distrito", "required": True,
         "opciones": [], "appearance": None, "choice_filter": "canton_key=${canton} or any='1'", "relevant": None},

        {"tipo_ui": "Número", "label": "Edad", "name": "edad", "required": True,
         "opciones": [], "appearance": None, "choice_filter": None, "relevant": None},

        # NOTA: aquí lo dejé como selección única para que puedas mapear tus opciones exactas luego
        {"tipo_ui": "Selección única", "label": "¿Con cuál de estas opciones se identifica?", "name": "genero", "required": True,
         "opciones": ["Femenino", "Masculino", "Persona No Binaria", "Prefiero no decir"],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección única", "label": "Escolaridad:", "name": "escolaridad", "required": True,
         "opciones": [
             "Ninguna",
             "Primaria incompleta",
             "Primaria completa",
             "Secundaria incompleta",
             "Secundaria completa",
             "Técnico",
             "Universitaria incompleta",
             "Universitaria completa"
         ],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección única", "label": "¿Cuál es su relación con la zona?", "name": "relacion_zona", "required": True,
         "opciones": ["Vivo en la zona", "Trabajo en la zona", "Visito la zona", "Estudio en la zona"],
         "appearance": None, "choice_filter": None, "relevant": None},

        # ---------------- Página 3: Sentimiento de inseguridad ----------------
        {"tipo_ui": "Selección única", "label": "¿Se siente usted seguro en este distrito?", "name": "se_siente_seguro", "required": True,
         "opciones": ["Sí", "No"], "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección múltiple", "label": "7.1. Indique por qué considera el distrito inseguro (Marque todas las situaciones que correspondan):", "name": "motivos_inseguridad", "required": True,
         "opciones": [
             "Venta o distribución de drogas",
             "Consumo de drogas en espacios públicos",
             "Consumo de alcohol en espacios públicos",
             "Riñas o peleas frecuentes",
             "Asaltos o robos a personas",
             "Robos a viviendas o comercios",
             "Amenazas o extorsiones",
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
             "Presencia de personas en situación de calle",
             "Ventas ambulantes desordenadas",
             "Problemas con transporte informal",
             "Zonas donde se concentra consumo de alcohol o drogas",
             "Puntos conflictivos recurrentes",
             "Falta de patrullajes visibles",
             "Falta de presencia policial en la zona",
             "Situaciones de violencia intrafamiliar",
             "Situaciones de violencia de género",
             "Otro problema que considere importante"
         ],
         "appearance": None, "choice_filter": None, "relevant": f"${{se_siente_seguro}}='{slugify_name('No')}'"},

        {"tipo_ui": "Párrafo (texto largo)", "label": "Detalle (opcional) del motivo seleccionado como 'Otro problema que considere importante':", "name": "motivo_otro_detalle", "required": False,
         "opciones": [], "appearance": "multiline", "choice_filter": None, "relevant": None},

        {"tipo_ui": "Selección única", "label": "8. ¿Cómo se siente la seguridad en este distrito este año en comparación con el año anterior?", "name": "comparacion_anual", "required": True,
         "opciones": ["Mucho Menos Seguro (1)", "Menos Seguro (2)", "Igual de Seguro/Inseguro (3)", "Más Seguro (4)", "Mucho Más Seguro (5)"],
         "appearance": None, "choice_filter": None, "relevant": None},

        {"tipo_ui": "Párrafo (texto largo)", "label": "8.1. Indique por qué:", "name": "motivo_comparacion", "required": True,
         "opciones": [], "appearance": "multiline", "choice_filter": None, "relevant": None},
    ]

    # Mantengo el resto EXACTO como lo venías teniendo antes (P4..P7) en la siguiente parte,
    # para no mezclar y evitar errores por tamaño.

    st.session_state.preguntas = seed
    st.session_state.seed_cargado = True
# ==========================================================================================
# ============================== PARTE 4/10 ===============================================
# ====== Completar SEED (P4..P7) + sets por página (sin Barrio) + helpers de páginas ======
# ==========================================================================================

# ------------------------------------------------------------------------------------------
# Completar SEED (P4..P7) — se “pega” encima del seed existente (si ya cargó)
# Nota: NO tocamos lógica ni condicionales; solo agregamos lo que faltaba.
# ------------------------------------------------------------------------------------------
if st.session_state.get("seed_cargado") and st.session_state.get("_seed_completado_p4_p7") != True:

    # Traemos lo que ya existe (P2..P3) y le anexamos P4..P7
    seed = list(st.session_state.preguntas)

    # ---------------- Página 4: Lugares del barrio ----------------
    seed += [
        {"tipo_ui":"Selección única","label":"Discotecas, bares, sitios de entretenimiento","name":"lugar_entretenimiento","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Espacios recreativos","name":"espacios_recreativos","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Lugar de residencia","name":"lugar_residencia","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Paradas/estaciones (buses, taxis, trenes)","name":"paradas_estaciones","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Puentes peatonales","name":"puentes_peatonales","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Transporte público","name":"transporte_publico","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Zona bancaria","name":"zona_bancaria","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Zona de comercio","name":"zona_comercio","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Zonas residenciales (calles y barrios, distinto a su casa)","name":"zonas_residenciales","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Lugares de interés turístico","name":"lugares_turisticos","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"10. ¿Cuál es la zona que usted considera más insegura?","name":"zona_mas_insegura","required":True,
         "opciones":["Discotecas, bares, sitios de entretenimiento","Espacios recreativos","Lugar de residencia","Paradas/estaciones",
                     "Puentes peatonales","Transporte público","Zona bancaria","Zona de comercio","Zonas residenciales",
                     "Zonas francas","Lugares de interés turístico","Centros educativos","Otros"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"11. Describa por qué considera que esa zona es insegura (Marque todos los que apliquen y detalle):","name":"porque_insegura","required":False,
         "opciones":[],"appearance":"multiline","choice_filter":None,"relevant":None},
    ]

    # ---------------- Página 5: Incidencia de delitos ----------------
    seed += [
        {"tipo_ui":"Selección múltiple","label":"19. Selección múltiple de los siguientes delitos:","name":"incidencia_delitos","required":False,
         "opciones":[
            "Disturbios en vía pública. (Riñas o Agresión)",
            "Daños a la propiedad. (Destruir, inutilizar o desaparecer).",
            "Extorsión (intimidar o amenazar a otras personas con fines de lucro).",
            "Hurto. (sustracción de artículos mediante el descuido).",
            "Receptación (persona que adquiere, recibe u oculta artículos provenientes de un delito en el que no participó).",
            "Contrabando (licor, cigarrillos, medicinas, ropa, calzado, etc.)",
            "Maltrato animal",
            "Tráfico ilegal de personas (coyotaje)",
            "Otro"
         ],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"20. Venta de drogas","name":"venta_drogas","required":False,
         "opciones":["Búnker (espacio cerrado)","Vía pública","Exprés (entrega rápida / modalidad exprés)","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"21. Delitos contra la vida","name":"delitos_vida","required":False,
         "opciones":["Homicidios","Heridos (lesiones dolosas)","Femicidio","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"22. Delitos sexuales","name":"delitos_sexuales","required":False,
         "opciones":["Abuso sexual","Acoso sexual","Violación","Acoso callejero","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"23. Asaltos","name":"asaltos","required":False,
         "opciones":["Asalto a personas","Asalto a comercio","Asalto a vivienda","Asalto a transporte público","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"24. Estafas","name":"estafas","required":False,
         "opciones":["Billetes falsos","Documentos falsos","Estafa (Oro)","Lotería falsos","Estafas informáticas","Estafa telefónica","Estafa con tarjetas","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"25. Robo (Sustracción de artículos mediante la utilización de la fuerza)","name":"robo_fuerza","required":False,
         "opciones":[
            "Tacha a comercio","Tacha a edificaciones","Tacha a vivienda","Tacha de vehículos","Robo",
            "Robo de ganado (destace de ganado)","Robo de bienes agrícolas","Robo de cultivo","Robo de vehículos",
            "Robo de cable","Robo de combustible","Otro"
         ],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"26. Abandono de personas","name":"abandono_personas","required":False,
         "opciones":["Abandono de adulto mayor","Abandono de menor de edad","Abandono de incapaz","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"27. Explotación infantil","name":"explotacion_infantil","required":False,
         "opciones":["Sexual","Laboral","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"28. Delitos ambientales","name":"delitos_ambientales","required":False,
         "opciones":["Caza ilegal","Minería ilegal","Pesca ilegal","Tala ilegal","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"29. Trata de personas","name":"trata_personas","required":False,
         "opciones":["Con fines laborales","Con fines sexuales","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        # Victimización / VI (mantengo estructura de tu código original)
        {"tipo_ui":"Selección única","label":"30. Durante el último año, ¿usted o algún miembro de su hogar ha sido afectado por alguna situación de violencia intrafamiliar (violencia doméstica)?","name":"vi","required":False,
         "opciones":["Sí","No"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"30.1. ¿Qué tipo(s) de violencia intrafamiliar se presentaron? (Puede marcar más de una opción)","name":"vi_tipos","required":True,
         "opciones":[
             "Violencia psicológica (gritos, amenazas, humillaciones, maltratos, entre otros)",
             "Violencia física (agresiones físicas, empujones, golpes, entre otros)",
             "Violencia vicaria (uso de hijas, hijos u otras personas para causar daño emocional)",
             "Violencia patrimonial (destrucción, retención o control de bienes, documentos o dinero)",
             "Violencia sexual (actos de carácter sexual sin consentimiento)"
         ],
         "appearance":None,"choice_filter":None,"relevant":f"${{vi}}='{slugify_name('Sí')}'"},

        {"tipo_ui":"Selección única","label":"30.2. En relación con la situación de violencia intrafamiliar indicada anteriormente, ¿usted o algún miembro de su hogar solicitó medidas de protección?","name":"vi_medidas","required":True,
         "opciones":["Sí","No","No recuerda"],"appearance":None,"choice_filter":None,"relevant":f"${{vi}}='{slugify_name('Sí')}'"},

        {"tipo_ui":"Selección única","label":"30.3. ¿Cómo valora el abordaje de la Fuerza Pública ante esta situación?","name":"vi_fp_eval","required":True,
         "opciones":["Excelente","Bueno","Regular","Malo","Muy malo"],"appearance":None,"choice_filter":None,"relevant":f"${{vi}}='{slugify_name('Sí')}'"},
    ]

    # ---------------- Página 6: Riesgos Sociales ----------------
    seed += [
        {"tipo_ui":"Selección múltiple","label":"12. Selección múltiple de las siguientes problemáticas (Riesgos sociales):","name":"riesgos_sociales","required":False,
         "opciones":[
            "Problemas vecinales o conflictos entre vecinos",
            "Personas con exceso de tiempo de ocio",
            "Personas en situación de calle",
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
            "Ventas informales desordenadas",
            "Escándalos musicales o ruidos excesivos",
            "Otro problema que considere importante"
         ],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"13. Falta de inversión social","name":"falta_inversion_social","required":False,
         "opciones":["Falta de oferta educativa","Falta de oferta deportiva","Falta de oferta recreativa","Falta de actividades culturales"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"14. Consumo de drogas","name":"consumo_drogas","required":False,
         "opciones":["Área privada","Área pública","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"15. Deficiencia en la infraestructura vial","name":"infra_vial","required":False,
         "opciones":["Calles en mal estado","Falta de señalización de tránsito","Carencia o inexistencia de aceras","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"16. Búnker","name":"bunker","required":False,
         "opciones":["Casa de habitación (espacio cerrado)","Edificación abandonada","Lote baldío","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"17. Transporte","name":"transporte","required":False,
         "opciones":["Informal (taxis piratas)","Plataformas (digitales)","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"18. Presencia Policial","name":"presencia_policial","required":False,
         "opciones":["Falta de presencia policial","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},
    ]

    # ---------------- Página 7: Información adicional ----------------
    seed += [
        {"tipo_ui":"Selección única","label":"45. ¿Usted tiene información de alguna persona o grupo que se dedique a realizar algún delito en su comunidad? (Recuerde, su información es confidencial.)","name":"info_grupo_delito","required":True,
         "opciones":["Sí","No"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"45.1. Si su respuesta es \"Sí\", describa aquellas características que pueda aportar (nombre de personas, alias, domicilio, vehículos, etc.)","name":"desc_info_grupo","required":True,
         "opciones":[],"appearance":"multiline","choice_filter":None,"relevant":f"${{info_grupo_delito}}='{slugify_name('Sí')}'"},

        {"tipo_ui":"Texto (corto)","label":"46. (Voluntario) Nombre, teléfono o correo electrónico para ser contactado y continuar colaborando de forma confidencial con Fuerza Pública.","name":"contacto_voluntario","required":False,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"47. En el siguiente espacio podrá registrar alguna otra información que estime pertinente.","name":"otra_info","required":False,
         "opciones":[],"appearance":"multiline","choice_filter":None,"relevant":None},
    ]

    # Guardamos seed completo
    st.session_state.preguntas = seed
    st.session_state["_seed_completado_p4_p7"] = True

# ------------------------------------------------------------------------------------------
# Sets por página (para construir XLSForm por grupos/páginas)
# Nota: P2 ya NO incluye barrio
# ------------------------------------------------------------------------------------------
P2_SET = {"canton", "distrito", "edad", "genero", "escolaridad", "relacion_zona"}
P3_SET = {"se_siente_seguro", "motivos_inseguridad", "motivo_otro_detalle", "comparacion_anual", "motivo_comparacion"}
P4_SET = {
    "lugar_entretenimiento", "espacios_recreativos", "lugar_residencia", "paradas_estaciones",
    "puentes_peatonales", "transporte_publico", "zona_bancaria", "zona_comercio",
    "zonas_residenciales", "lugares_turisticos", "zona_mas_insegura", "porque_insegura"
}
P5_SET = {
    "incidencia_delitos", "venta_drogas", "delitos_vida", "delitos_sexuales", "asaltos", "estafas",
    "robo_fuerza", "abandono_personas", "explotacion_infantil", "delitos_ambientales", "trata_personas",
    "vi", "vi_tipos", "vi_medidas", "vi_fp_eval"
}
P6_SET = {"riesgos_sociales", "falta_inversion_social", "consumo_drogas", "infra_vial", "bunker", "transporte", "presencia_policial"}
P7_SET = {"info_grupo_delito", "desc_info_grupo", "contacto_voluntario", "otra_info"}
# ==========================================================================================
# ============================== PARTE 4/10 ===============================================
# ====== Completar SEED (P4..P7) + sets por página (sin Barrio) + helpers de páginas ======
# ==========================================================================================

# ------------------------------------------------------------------------------------------
# Completar SEED (P4..P7) — se “pega” encima del seed existente (si ya cargó)
# Nota: NO tocamos lógica ni condicionales; solo agregamos lo que faltaba.
# ------------------------------------------------------------------------------------------
if st.session_state.get("seed_cargado") and st.session_state.get("_seed_completado_p4_p7") != True:

    # Traemos lo que ya existe (P2..P3) y le anexamos P4..P7
    seed = list(st.session_state.preguntas)

    # ---------------- Página 4: Lugares del barrio ----------------
    seed += [
        {"tipo_ui":"Selección única","label":"Discotecas, bares, sitios de entretenimiento","name":"lugar_entretenimiento","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Espacios recreativos","name":"espacios_recreativos","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Lugar de residencia","name":"lugar_residencia","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Paradas/estaciones (buses, taxis, trenes)","name":"paradas_estaciones","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Puentes peatonales","name":"puentes_peatonales","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Transporte público","name":"transporte_publico","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Zona bancaria","name":"zona_bancaria","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Zona de comercio","name":"zona_comercio","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Zonas residenciales (calles y barrios, distinto a su casa)","name":"zonas_residenciales","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Lugares de interés turístico","name":"lugares_turisticos","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Distrito"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"10. ¿Cuál es la zona que usted considera más insegura?","name":"zona_mas_insegura","required":True,
         "opciones":["Discotecas, bares, sitios de entretenimiento","Espacios recreativos","Lugar de residencia","Paradas/estaciones",
                     "Puentes peatonales","Transporte público","Zona bancaria","Zona de comercio","Zonas residenciales",
                     "Zonas francas","Lugares de interés turístico","Centros educativos","Otros"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"11. Describa por qué considera que esa zona es insegura (Marque todos los que apliquen y detalle):","name":"porque_insegura","required":False,
         "opciones":[],"appearance":"multiline","choice_filter":None,"relevant":None},
    ]

    # ---------------- Página 5: Incidencia de delitos ----------------
    seed += [
        {"tipo_ui":"Selección múltiple","label":"19. Selección múltiple de los siguientes delitos:","name":"incidencia_delitos","required":False,
         "opciones":[
            "Disturbios en vía pública. (Riñas o Agresión)",
            "Daños a la propiedad. (Destruir, inutilizar o desaparecer).",
            "Extorsión (intimidar o amenazar a otras personas con fines de lucro).",
            "Hurto. (sustracción de artículos mediante el descuido).",
            "Receptación (persona que adquiere, recibe u oculta artículos provenientes de un delito en el que no participó).",
            "Contrabando (licor, cigarrillos, medicinas, ropa, calzado, etc.)",
            "Maltrato animal",
            "Tráfico ilegal de personas (coyotaje)",
            "Otro"
         ],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"20. Venta de drogas","name":"venta_drogas","required":False,
         "opciones":["Búnker (espacio cerrado)","Vía pública","Exprés (entrega rápida / modalidad exprés)","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"21. Delitos contra la vida","name":"delitos_vida","required":False,
         "opciones":["Homicidios","Heridos (lesiones dolosas)","Femicidio","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"22. Delitos sexuales","name":"delitos_sexuales","required":False,
         "opciones":["Abuso sexual","Acoso sexual","Violación","Acoso callejero","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"23. Asaltos","name":"asaltos","required":False,
         "opciones":["Asalto a personas","Asalto a comercio","Asalto a vivienda","Asalto a transporte público","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"24. Estafas","name":"estafas","required":False,
         "opciones":["Billetes falsos","Documentos falsos","Estafa (Oro)","Lotería falsos","Estafas informáticas","Estafa telefónica","Estafa con tarjetas","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"25. Robo (Sustracción de artículos mediante la utilización de la fuerza)","name":"robo_fuerza","required":False,
         "opciones":[
            "Tacha a comercio","Tacha a edificaciones","Tacha a vivienda","Tacha de vehículos","Robo",
            "Robo de ganado (destace de ganado)","Robo de bienes agrícolas","Robo de cultivo","Robo de vehículos",
            "Robo de cable","Robo de combustible","Otro"
         ],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"26. Abandono de personas","name":"abandono_personas","required":False,
         "opciones":["Abandono de adulto mayor","Abandono de menor de edad","Abandono de incapaz","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"27. Explotación infantil","name":"explotacion_infantil","required":False,
         "opciones":["Sexual","Laboral","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"28. Delitos ambientales","name":"delitos_ambientales","required":False,
         "opciones":["Caza ilegal","Minería ilegal","Pesca ilegal","Tala ilegal","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"29. Trata de personas","name":"trata_personas","required":False,
         "opciones":["Con fines laborales","Con fines sexuales","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        # Victimización / VI (mantengo estructura de tu código original)
        {"tipo_ui":"Selección única","label":"30. Durante el último año, ¿usted o algún miembro de su hogar ha sido afectado por alguna situación de violencia intrafamiliar (violencia doméstica)?","name":"vi","required":False,
         "opciones":["Sí","No"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"30.1. ¿Qué tipo(s) de violencia intrafamiliar se presentaron? (Puede marcar más de una opción)","name":"vi_tipos","required":True,
         "opciones":[
             "Violencia psicológica (gritos, amenazas, humillaciones, maltratos, entre otros)",
             "Violencia física (agresiones físicas, empujones, golpes, entre otros)",
             "Violencia vicaria (uso de hijas, hijos u otras personas para causar daño emocional)",
             "Violencia patrimonial (destrucción, retención o control de bienes, documentos o dinero)",
             "Violencia sexual (actos de carácter sexual sin consentimiento)"
         ],
         "appearance":None,"choice_filter":None,"relevant":f"${{vi}}='{slugify_name('Sí')}'"},

        {"tipo_ui":"Selección única","label":"30.2. En relación con la situación de violencia intrafamiliar indicada anteriormente, ¿usted o algún miembro de su hogar solicitó medidas de protección?","name":"vi_medidas","required":True,
         "opciones":["Sí","No","No recuerda"],"appearance":None,"choice_filter":None,"relevant":f"${{vi}}='{slugify_name('Sí')}'"},

        {"tipo_ui":"Selección única","label":"30.3. ¿Cómo valora el abordaje de la Fuerza Pública ante esta situación?","name":"vi_fp_eval","required":True,
         "opciones":["Excelente","Bueno","Regular","Malo","Muy malo"],"appearance":None,"choice_filter":None,"relevant":f"${{vi}}='{slugify_name('Sí')}'"},
    ]

    # ---------------- Página 6: Riesgos Sociales ----------------
    seed += [
        {"tipo_ui":"Selección múltiple","label":"12. Selección múltiple de las siguientes problemáticas (Riesgos sociales):","name":"riesgos_sociales","required":False,
         "opciones":[
            "Problemas vecinales o conflictos entre vecinos",
            "Personas con exceso de tiempo de ocio",
            "Personas en situación de calle",
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
            "Ventas informales desordenadas",
            "Escándalos musicales o ruidos excesivos",
            "Otro problema que considere importante"
         ],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"13. Falta de inversión social","name":"falta_inversion_social","required":False,
         "opciones":["Falta de oferta educativa","Falta de oferta deportiva","Falta de oferta recreativa","Falta de actividades culturales"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"14. Consumo de drogas","name":"consumo_drogas","required":False,
         "opciones":["Área privada","Área pública","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"15. Deficiencia en la infraestructura vial","name":"infra_vial","required":False,
         "opciones":["Calles en mal estado","Falta de señalización de tránsito","Carencia o inexistencia de aceras","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"16. Búnker","name":"bunker","required":False,
         "opciones":["Casa de habitación (espacio cerrado)","Edificación abandonada","Lote baldío","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"17. Transporte","name":"transporte","required":False,
         "opciones":["Informal (taxis piratas)","Plataformas (digitales)","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"18. Presencia Policial","name":"presencia_policial","required":False,
         "opciones":["Falta de presencia policial","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},
    ]

    # ---------------- Página 7: Información adicional ----------------
    seed += [
        {"tipo_ui":"Selección única","label":"45. ¿Usted tiene información de alguna persona o grupo que se dedique a realizar algún delito en su comunidad? (Recuerde, su información es confidencial.)","name":"info_grupo_delito","required":True,
         "opciones":["Sí","No"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"45.1. Si su respuesta es \"Sí\", describa aquellas características que pueda aportar (nombre de personas, alias, domicilio, vehículos, etc.)","name":"desc_info_grupo","required":True,
         "opciones":[],"appearance":"multiline","choice_filter":None,"relevant":f"${{info_grupo_delito}}='{slugify_name('Sí')}'"},

        {"tipo_ui":"Texto (corto)","label":"46. (Voluntario) Nombre, teléfono o correo electrónico para ser contactado y continuar colaborando de forma confidencial con Fuerza Pública.","name":"contacto_voluntario","required":False,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"47. En el siguiente espacio podrá registrar alguna otra información que estime pertinente.","name":"otra_info","required":False,
         "opciones":[],"appearance":"multiline","choice_filter":None,"relevant":None},
    ]

    # Guardamos seed completo
    st.session_state.preguntas = seed
    st.session_state["_seed_completado_p4_p7"] = True

# ------------------------------------------------------------------------------------------
# Sets por página (para construir XLSForm por grupos/páginas)
# Nota: P2 ya NO incluye barrio
# ------------------------------------------------------------------------------------------
P2_SET = {"canton", "distrito", "edad", "genero", "escolaridad", "relacion_zona"}
P3_SET = {"se_siente_seguro", "motivos_inseguridad", "motivo_otro_detalle", "comparacion_anual", "motivo_comparacion"}
P4_SET = {
    "lugar_entretenimiento", "espacios_recreativos", "lugar_residencia", "paradas_estaciones",
    "puentes_peatonales", "transporte_publico", "zona_bancaria", "zona_comercio",
    "zonas_residenciales", "lugares_turisticos", "zona_mas_insegura", "porque_insegura"
}
P5_SET = {
    "incidencia_delitos", "venta_drogas", "delitos_vida", "delitos_sexuales", "asaltos", "estafas",
    "robo_fuerza", "abandono_personas", "explotacion_infantil", "delitos_ambientales", "trata_personas",
    "vi", "vi_tipos", "vi_medidas", "vi_fp_eval"
}
P6_SET = {"riesgos_sociales", "falta_inversion_social", "consumo_drogas", "infra_vial", "bunker", "transporte", "presencia_policial"}
P7_SET = {"info_grupo_delito", "desc_info_grupo", "contacto_voluntario", "otra_info"}
# ==========================================================================================
# ============================== PARTE 5/10 ===============================================
# ====== Ajustes del CATÁLOGO Cantón→Distrito (sin Barrio) + Seed P2 (sin Barrio) =========
# ==========================================================================================

# ------------------------------------------------------------------------------------------
# 1) Catálogo por lotes: dejar SOLO Cantón→Distrito (eliminar Barrio en UI y en choices)
# ------------------------------------------------------------------------------------------
st.markdown("### 📚 Catálogo Cantón → Distrito (por lotes)")
with st.expander("Agrega un lote (un Cantón y varios Distritos)", expanded=True):
    col_c1, col_c2 = st.columns(2)
    canton_txt = col_c1.text_input("Cantón (una vez)", value="", key="cat_canton_txt")
    distritos_txt = col_c2.text_area("Distritos del cantón (uno por línea)", value="", height=130, key="cat_distritos_txt")

    col_b1, col_b2, col_b3 = st.columns([1, 1, 2])
    add_lote = col_b1.button("Agregar lote", type="primary", use_container_width=True, key="cat_add_lote")
    clear_all = col_b2.button("Limpiar catálogo", use_container_width=True, key="cat_clear_all")

    if clear_all:
        st.session_state.choices_ext_rows = []
        st.success("Catálogo limpiado.")

    if add_lote:
        c = canton_txt.strip()
        distritos = [d.strip() for d in distritos_txt.splitlines() if d.strip()]

        if not c or not distritos:
            st.error("Debes indicar Cantón y al menos un Distrito.")
        else:
            slug_c = slugify_name(c)

            # columnas extra usadas por filtros/placeholder
            st.session_state.choices_extra_cols.update({"canton_key", "any"})

            # Placeholders (una sola vez por lista)
            _append_choice_unique({"list_name": "list_canton",   "name": "__pick_canton__",   "label": "— escoja un cantón —"})
            _append_choice_unique({"list_name": "list_distrito", "name": "__pick_distrito__", "label": "— escoja un cantón —", "any": "1"})

            # Cantón
            _append_choice_unique({"list_name": "list_canton", "name": slug_c, "label": c})

            # Distritos
            usados_d = set()
            for d in distritos:
                slug_d = asegurar_nombre_unico(slugify_name(d), usados_d)
                usados_d.add(slug_d)
                _append_choice_unique({"list_name": "list_distrito", "name": slug_d, "label": d, "canton_key": slug_c})

            st.success(f"Lote agregado: {c} → {len(distritos)} distritos.")

# Vista previa de catálogo
if st.session_state.choices_ext_rows:
    st.dataframe(
        pd.DataFrame(st.session_state.choices_ext_rows),
        use_container_width=True, hide_index=True, height=240
    )

# ------------------------------------------------------------------------------------------
# 2) SEED P2: eliminar la pregunta de Barrio del seed (si existiera)
#    - Mantener Cantón y Distrito como select_one con choice_filter y constraints
# ------------------------------------------------------------------------------------------
if st.session_state.get("seed_cargado"):

    # Quitar la pregunta 'barrio' si todavía existe en preguntas
    st.session_state.preguntas = [q for q in st.session_state.preguntas if q.get("name") != "barrio"]

    # Asegurar que Cantón y Distrito queden con el choice_filter correcto
    # (si ya existían no se cambia nada más)
    for q in st.session_state.preguntas:
        if q.get("name") == "canton":
            q["tipo_ui"] = "Selección única"
            q["label"] = "Cantón"
            q["required"] = True
            q["opciones"] = []               # No generar opciones aquí, vienen del catálogo
            q["appearance"] = None
            q["choice_filter"] = None
            q["relevant"] = None

        if q.get("name") == "distrito":
            q["tipo_ui"] = "Selección única"
            q["label"] = "Distrito"
            q["required"] = True
            q["opciones"] = []               # No generar opciones aquí, vienen del catálogo
            q["appearance"] = None
            # Filtra distritos por el cantón seleccionado o permite placeholder 'any=1'
            q["choice_filter"] = "canton_key=${canton} or any='1'"
            q["relevant"] = None

# ------------------------------------------------------------------------------------------
# 3) Sets por página (P2 ya sin barrio) — por seguridad, re-declarar si no están
# ------------------------------------------------------------------------------------------
P2_SET = {"canton", "distrito", "edad", "genero", "escolaridad", "relacion_zona"}
# ==========================================================================================
# ============================== PARTE 6/10 ===============================================
# ====== construir_xlsform() actualizado: P2 sin Barrio + constraints/choices coherentes ===
# ==========================================================================================

# NOTA: Esta parte REEMPLAZA tu bloque completo:
#   - def _get_logo_media_name(): ...
#   - def construir_xlsform(...): ...
# (mantiene TODO igual excepto: elimina Barrio y ajusta catálogo Cantón→Distrito)

def _get_logo_media_name():
    return logo_media_name


def construir_xlsform(preguntas, form_title: str, idioma: str, version: str,
                      reglas_vis, reglas_fin):
    """
    Construye DataFrames: survey, choices, settings.
    - Páginas con groups begin_group/end_group + appearance=field-list
    - Portada (intro) con note + media::image
    - relevant (manual + panel) y finalizar-temprano (NOT de previas)
    - Cascadas: Cantón→Distrito por catálogo manual (choices_ext_rows)
    - SIN Barrio (eliminado completamente)
    """
    survey_rows = []
    choices_rows = []

    # ----- Reglas de visibilidad (panel) -----
    vis_by_target = {}
    for r in reglas_vis:
        vis_by_target.setdefault(r["target"], []).append(
            {"src": r["src"], "op": r.get("op", "="), "values": r.get("values", [])}
        )

    # ----- Reglas de finalizar temprano (panel) -----
    fin_conds = []
    for r in reglas_fin:
        cond = build_relevant_expr([{
            "src": r["src"],
            "op": r.get("op", "="),
            "values": r.get("values", [])
        }])
        if cond:
            fin_conds.append((r["index_src"], cond))

    # ------------------- Página 1: INTRODUCCIÓN -------------------
    survey_rows += [
        {"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"},
        {"type": "note", "name": "intro_logo", "label": form_title, "media::image": _get_logo_media_name()},
        {"type": "note", "name": "intro_texto", "label": INTRO_COMUNIDAD},
        {"type": "end_group", "name": "p1_end"}
    ]

    # ------------------- Sets por página (P2 sin Barrio) -------------------
    p2 = {"canton", "distrito", "edad", "genero", "escolaridad", "relacion_zona"}
    p3 = {"se_siente_seguro", "motivo_inseguridad", "comparacion_anual", "motivo_comparacion"}
    p4 = {"lugar_entretenimiento", "espacios_recreativos", "lugar_residencia", "paradas_estaciones",
          "puentes_peatonales", "transporte_publico", "zona_bancaria", "zona_comercio",
          "zonas_residenciales", "lugares_turisticos", "zona_mas_insegura", "porque_insegura"}
    p5 = {"incidencia_delitos", "venta_drogas", "delitos_vida", "delitos_sexuales", "asaltos", "estafas",
          "robo_fuerza", "abandono_personas", "explotacion_infantil", "delitos_ambientales", "trata_personas",
          "vi", "vi_victima_ultimo_anno", "vi_tipos", "vi_fp_abordaje", "vi_fp_eval"}
    p6 = {"riesgos_sociales", "falta_inversion_social", "consumo_drogas", "infra_vial", "bunker"}
    p7 = {"info_grupo_delito", "desc_info_grupo", "victimizacion_12m",
          "delito_victima_si", "modo_operar_si", "horario_hecho_si",
          "delito_victima_no", "motivo_no_denuncia", "modo_operar_no", "horario_hecho_no",
          "fp_calificacion", "fp_24m", "conoce_policias", "conversa_policias",
          "sugerencia_fp", "sugerencia_muni", "otra_info", "contacto_voluntario"}

    def add_q(q, idx):
        """Agrega fila survey + choices (si aplica), combinando relevants y finalización temprana."""
        x_type, default_app, list_name = map_tipo_to_xlsform(q["tipo_ui"], q["name"])

        # relevant: manual + panel + fin
        rel_manual = q.get("relevant") or None
        rel_panel = build_relevant_expr(vis_by_target.get(q["name"], []))
        nots = [xlsform_not(cond) for idx_src, cond in fin_conds if idx_src < idx]
        rel_fin = "(" + " and ".join(nots) + ")" if nots else None

        parts = [p for p in [rel_manual, rel_panel, rel_fin] if p]
        rel_final = None
        if parts:
            rel_final = parts[0] if len(parts) == 1 else "(" + ") and (".join(parts) + ")"

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

        # ---- Constraints placeholders SOLO para Cantón/Distrito ----
        if q["name"] == "canton":
            row["constraint"] = ". != '__pick_canton__'"
            row["constraint_message"] = "Seleccione un cantón válido."

        if q["name"] == "distrito":
            row["constraint"] = ". != '__pick_distrito__'"
            row["constraint_message"] = "Seleccione un distrito válido."

        survey_rows.append(row)

        # ---- Choices ----
        # NO generar opciones para Cantón/Distrito (vienen del catálogo choices_ext_rows)
        if list_name and q["name"] not in {"canton", "distrito"}:
            usados = set()
            for opt_label in (q.get("opciones") or []):
                base = slugify_name(opt_label)
                opt_name = asegurar_nombre_unico(base, usados)
                usados.add(opt_name)
                choices_rows.append({"list_name": list_name, "name": opt_name, "label": str(opt_label)})

    def add_page(group_name, page_label, names_set):
        survey_rows.append({"type": "begin_group", "name": group_name, "label": page_label, "appearance": "field-list"})
        for i, q in enumerate(preguntas):
            if q["name"] in names_set:
                add_q(q, i)
        survey_rows.append({"type": "end_group", "name": f"{group_name}_end"})

    # ------------------- Páginas P2..P7 -------------------
    add_page("p2_demograficos", "Datos demográficos", p2)
    add_page("p3_sentimiento", "Sentimiento de inseguridad en el barrio", p3)
    add_page("p4_lugares", "Indique cómo se siente en los siguientes lugares de su barrio", p4)
    add_page("p5_incidencia", "Incidencia relacionada a delitos", p5)
    add_page("p6_riesgos", "Riesgos Sociales", p6)
    add_page("p7_info_adicional", "Información adicional", p7)

    # ------------------- Choices del catálogo manual (Cantón/Distrito) -------------------
    # Incluye placeholders y keys (canton_key, any), todo lo que se haya agregado en la UI
    for r in st.session_state.choices_ext_rows:
        choices_rows.append(dict(r))

    # ------------------- DataFrames -------------------
    survey_cols_all = set()
    for r in survey_rows:
        survey_cols_all.update(r.keys())

    # columnas principales + extras
    survey_cols = [c for c in [
        "type", "name", "label", "required", "appearance", "choice_filter",
        "relevant", "constraint", "constraint_message", "media::image"
    ] if c in survey_cols_all]
    for k in sorted(survey_cols_all):
        if k not in survey_cols:
            survey_cols.append(k)

    df_survey = pd.DataFrame(survey_rows, columns=survey_cols)

    choices_cols_all = set()
    for r in choices_rows:
        choices_cols_all.update(r.keys())

    base_choice_cols = ["list_name", "name", "label"]
    for extra in sorted(choices_cols_all):
        if extra not in base_choice_cols:
            base_choice_cols.append(extra)

    df_choices = (pd.DataFrame(choices_rows, columns=base_choice_cols)
                  if choices_rows else pd.DataFrame(columns=base_choice_cols))

    # SETTINGS: pages
    df_settings = pd.DataFrame([{
        "form_title": form_title,
        "version": version,
        "default_language": idioma,
        "style": "pages"
    }], columns=["form_title", "version", "default_language", "style"])

    return df_survey, df_choices, df_settings
# ==========================================================================================
# ============================== PARTE 7/10 ===============================================
# ====== Catálogo manual actualizado: Cantón → Distrito (SIN Barrios) + validación UI ======
# ==========================================================================================
# NOTA: Esta parte REEMPLAZA tu bloque completo del catálogo, desde:
#   # ------------------------------------------------------------------------------------------
#   # Catálogo manual por lotes: Cantón → Distrito → (Barrios…)
#   # ------------------------------------------------------------------------------------------
# HASTA la "Vista previa de catálogo".
#
# Mantiene tu misma lógica (choices_ext_rows, choices_extra_cols, _append_choice_unique),
# pero elimina TODO lo de Barrios, placeholders de barrio y textos relacionados.

# ------------------------------------------------------------------------------------------
# Catálogo manual por lotes: Cantón → Distrito (SIN Barrios)
# ------------------------------------------------------------------------------------------
if "choices_ext_rows" not in st.session_state:
    st.session_state.choices_ext_rows = []  # filas para hoja choices
if "choices_extra_cols" not in st.session_state:
    st.session_state.choices_extra_cols = set()

def _append_choice_unique(row: Dict):
    """Inserta fila en choices evitando duplicados por (list_name,name)."""
    key = (row.get("list_name"), row.get("name"))
    exists = any((r.get("list_name"), r.get("name")) == key for r in st.session_state.choices_ext_rows)
    if not exists:
        st.session_state.choices_ext_rows.append(row)

st.markdown("### 📚 Catálogo Cantón → Distrito (por lotes)")
with st.expander("Agrega un lote (un Cantón y un Distrito)", expanded=True):
    col_c1, col_c2 = st.columns(2)
    canton_txt = col_c1.text_input("Cantón (una vez)", value="")
    distrito_txt = col_c2.text_input("Distrito (una vez)", value="")

    col_b1, col_b2, col_b3 = st.columns([1, 1, 2])
    add_lote = col_b1.button("Agregar lote", type="primary", use_container_width=True)
    clear_all = col_b2.button("Limpiar catálogo", use_container_width=True)

    if clear_all:
        st.session_state.choices_ext_rows = []
        st.session_state.choices_extra_cols = set()
        st.success("Catálogo limpiado.")

    if add_lote:
        c = canton_txt.strip()
        d = distrito_txt.strip()

        if not c or not d:
            st.error("Debes indicar Cantón y Distrito.")
        else:
            slug_c = slugify_name(c)
            slug_d = slugify_name(d)

            # columnas extra usadas por filtros/placeholder
            st.session_state.choices_extra_cols.update({"canton_key", "any"})

            # Placeholders (una sola vez por lista)
            _append_choice_unique({
                "list_name": "list_canton",
                "name": "__pick_canton__",
                "label": "— escoja un cantón —"
            })
            _append_choice_unique({
                "list_name": "list_distrito",
                "name": "__pick_distrito__",
                "label": "— escoja un cantón —",
                "any": "1"
            })

            # Cantón (evita duplicados automáticamente)
            _append_choice_unique({"list_name": "list_canton", "name": slug_c, "label": c})

            # Distrito (filtrado por canton_key)
            _append_choice_unique({
                "list_name": "list_distrito",
                "name": slug_d,
                "label": d,
                "canton_key": slug_c
            })

            st.success(f"Lote agregado: {c} → {d}")

# ---------------------------
# Validación rápida (visual)
# ---------------------------
if st.session_state.choices_ext_rows:
    df_cat = pd.DataFrame(st.session_state.choices_ext_rows)

    # métricas básicas
    cantones = df_cat[df_cat["list_name"] == "list_canton"]
    distritos = df_cat[df_cat["list_name"] == "list_distrito"]

    has_pick_c = ((cantones["name"] == "__pick_canton__").any()) if not cantones.empty else False
    has_pick_d = ((distritos["name"] == "__pick_distrito__").any()) if not distritos.empty else False

    num_cantones_real = int((cantones["name"] != "__pick_canton__").sum()) if not cantones.empty else 0
    num_distritos_real = int((distritos["name"] != "__pick_distrito__").sum()) if not distritos.empty else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Cantones (reales)", num_cantones_real)
    m2.metric("Distritos (reales)", num_distritos_real)
    m3.metric("Placeholder Cantón", "OK" if has_pick_c else "FALTA")
    m4.metric("Placeholder Distrito", "OK" if has_pick_d else "FALTA")

    # advertencias útiles (no rompen nada)
    if num_cantones_real == 0:
        st.warning("Aún no hay cantones cargados. Agrega al menos 1 para que la cascada funcione.")
    if num_distritos_real == 0:
        st.warning("Aún no hay distritos cargados. Agrega al menos 1 distrito asociado a un cantón.")

    # Vista previa de catálogo
    st.dataframe(df_cat, use_container_width=True, hide_index=True, height=240)
else:
    st.info("Catálogo vacío. Agrega lotes Cantón → Distrito para alimentar la hoja `choices`.")
# ==========================================================================================
# ============================== PARTE 8/10 ===============================================
# ====== Precarga (seed) actualizada: P2 SIN Barrio + filtros/constraints coherentes =======
# ==========================================================================================
# NOTA: Esta parte REEMPLAZA dentro de tu bloque:
#   # ------------------------------------------------------------------------------------------
#   # Precarga de preguntas (P2 incluida; SIN opciones dummy en C/D/B)
#   # ------------------------------------------------------------------------------------------
# todo el contenido que está dentro de:
#   if "seed_cargado" not in st.session_state:
# dejando el mismo encabezado y el mismo if, pero pegando ESTE seed completo.
#
# Cambios EXACTOS:
# - Se elimina completamente la pregunta "Barrio"
# - Se ajusta el texto del comentario (ya no C/D/B)
# - Se mantiene Cantón y Distrito como select_one con opciones vacías (usan catálogo)
# - Se mantiene el choice_filter de Distrito por canton_key=${canton} or any='1'
# - NO se toca nada de P3..P7 ni sus relevantes/condicionales

# ------------------------------------------------------------------------------------------
# Precarga de preguntas (P2 incluida; SIN Barrio)
# ------------------------------------------------------------------------------------------
if "seed_cargado" not in st.session_state:

    v_si = slugify_name("Si"); v_no = slugify_name("No")
    v_mas_seguro  = slugify_name("Más seguro")
    v_igual       = slugify_name("Igual")
    v_menos_seg   = slugify_name("Menos seguro")

    seed = [
        # ---------------- Página 2: Datos demográficos ----------------
        {"tipo_ui":"Selección única","label":"Cantón","name":"canton","required":True,
         "opciones":[], "appearance":None, "choice_filter":None, "relevant":None},

        {"tipo_ui":"Selección única","label":"Distrito","name":"distrito","required":True,
         "opciones":[], "appearance":None, "choice_filter":"canton_key=${canton} or any='1'", "relevant":None},

        {"tipo_ui":"Número","label":"Edad","name":"edad","required":True,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"Género","name":"genero","required":True,
         "opciones":["Masculino","Femenino","LGTBQ+"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"Escolaridad","name":"escolaridad","required":True,
         "opciones":["Ninguna","Primaria","Primaria incompleta","Secundaria completa","Secundaria incompleta","Universitaria","Universitaria incompleta","Técnico"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"¿Cuál es su relación con la zona?","name":"relacion_zona","required":True,
         "opciones":["Vivo en la zona","Trabajo en la zona","Visito la zona"],"appearance":None,"choice_filter":None,"relevant":None},


        # ---------------- Página 3: Sentimiento de inseguridad ----------------
        {"tipo_ui":"Selección única","label":"¿Se siente seguro en su barrio?","name":"se_siente_seguro","required":True,
         "opciones":["Si","No"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"Indique por qué considera el barrio inseguro","name":"motivo_inseguridad","required":True,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":f"${{se_siente_seguro}}='{slugify_name('No')}'"},

        {"tipo_ui":"Selección única","label":"¿Cómo se siente respecto a la seguridad en su barrio este año comparado con el anterior?","name":"comparacion_anual","required":True,
         "opciones":["Más seguro","Igual","Menos seguro"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"Indique por qué.","name":"motivo_comparacion","required":True,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":xlsform_or_expr([
            f"${{comparacion_anual}}='{v_mas_seguro}'",
            f"${{comparacion_anual}}='{v_igual}'",
            f"${{comparacion_anual}}='{v_menos_seg}'"
         ])},


        # ---------------- Página 4: Lugares del barrio ----------------
        {"tipo_ui":"Selección única","label":"Discotecas, bares, sitios de entretenimiento","name":"lugar_entretenimiento","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Barrio"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"Espacios recreativos","name":"espacios_recreativos","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Barrio"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"Lugar de residencia","name":"lugar_residencia","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Barrio"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"Paradas/estaciones (buses, taxis, trenes)","name":"paradas_estaciones","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Barrio"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"Puentes peatonales","name":"puentes_peatonales","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Barrio"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"Transporte público","name":"transporte_publico","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Barrio"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"Zona bancaria","name":"zona_bancaria","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Barrio"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"Zona de comercio","name":"zona_comercio","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Barrio"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"Zonas residenciales","name":"zonas_residenciales","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Barrio"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"Lugares de interés turístico","name":"lugares_turisticos","required":True,
         "opciones":["Seguro","Inseguro","No existe en el Barrio"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Texto (corto)","label":"¿Cuál es el lugar o zona más inseguro en su barrio? (opcional)","name":"zona_mas_insegura","required":False,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"Describa por qué considera que esa zona es insegura (opcional)","name":"porque_insegura","required":False,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":None},


        # ---------------- Página 5: Incidencia de delitos ----------------
        {"tipo_ui":"Selección múltiple","label":"Incidencia relacionada a delitos","name":"incidencia_delitos","required":False,
         "opciones":[
            "Disturbios en vía pública.(Riñas o Agresión)","Daños a la propiedad. (Destruir, inutilizar o desaparecer).",
            "Extorsión (intimidar o amenazar a otras personas con fines de lucro).","Hurto. (sustracción de artículos mediante el descuido).",
            "Receptación (persona que adquiere, recibe u oculta artículos provenientes de un delito en el que no participó).",
            "Contrabando (licor, cigarrillos, medicinas, ropa, calzado, etc.)","Maltrato animal","Tráfico ilegal de personas (coyotaje)"
         ],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Venta de drogas","name":"venta_drogas","required":False,
         "opciones":["bunker espacio cerrado","vía pública","exprés"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Delitos contra la vida","name":"delitos_vida","required":False,
         "opciones":["Homicidios","Heridos"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Delitos sexuales","name":"delitos_sexuales","required":False,
         "opciones":["Abuso sexual","Acoso sexual","Violación"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Asaltos","name":"asaltos","required":False,
         "opciones":["Asalto a personas","Asalto a comercio","Asalto a vivienda","Asalto a transporte público"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Estafas","name":"estafas","required":False,
         "opciones":["Billetes falso","Documentos falsos","Estafa (Oro)","Lotería falsos","Estafas informáticas","Estafa telefónica","Estafa con tarjetas"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Robo (sustracción con fuerza)","name":"robo_fuerza","required":False,
         "opciones":["Tacha a comercio","Tacha a edificaciones","Tacha a vivienda","Tacha de vehículos","Robo de Ganado Abigeato (Destace de ganado)",
                     "Robo de bienes agrícola","Robo de vehículos","Robo de cable","Robo de combustible"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Abandono de personas","name":"abandono_personas","required":False,
         "opciones":["Abandono de adulto mayor","Abandono de menor de edad","Abandono de incapaz"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Explotación infantil","name":"explotacion_infantil","required":False,
         "opciones":["Sexual","Laboral"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Delitos ambientales","name":"delitos_ambientales","required":False,
         "opciones":["Caza ilegal","Pesca ilegal","Tala ilegal"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Trata de personas","name":"trata_personas","required":False,
         "opciones":["Con fines laborales","Con fines sexuales"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"Violencia Intrafamiliar","name":"vi","required":False,
         "opciones":["Si","No"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"¿Ha sido víctima o conoce a alguien que haya sido víctima de VI en el último año?","name":"vi_victima_ultimo_anno","required":True,
         "opciones":["Si","No"],"appearance":None,"choice_filter":None,"relevant":f"${{vi}}='{slugify_name('Si')}'"},

        {"tipo_ui":"Selección múltiple","label":"Tipos de Violencia Intrafamiliar (marque todos los que correspondan)","name":"vi_tipos","required":True,
         "opciones":["Violencia psicológica (gritos, amenazas, burlas, maltratos, etc)",
                     "Violencia física (golpes, empujones, etc)","Violencia patrimonial (destrucción o retención de artículos, documentos, dinero, etc)",
                     "Violencia sexual (actos sexuales no consentido)"],
         "appearance":None,"choice_filter":None,"relevant":f"${{vi}}='{slugify_name('Si')}'"},

        {"tipo_ui":"Selección única","label":"¿Fue abordado por Fuerza Pública?","name":"vi_fp_abordaje","required":True,
         "opciones":["Si","No"],"appearance":None,"choice_filter":None,"relevant":f"${{vi}}='{slugify_name('Si')}'"},

        {"tipo_ui":"Selección única","label":"¿Cómo fue el abordaje de la Fuerza Pública?","name":"vi_fp_eval","required":True,
         "opciones":["Excelente","Bueno","Regular","Malo"],"appearance":None,"choice_filter":None,"relevant":f"${{vi_fp_abordaje}}='{slugify_name('Si')}'"},


        # ---------------- Página 6: Riesgos Sociales ----------------
        {"tipo_ui":"Selección múltiple","label":"Riesgos Sociales","name":"riesgos_sociales","required":False,
         "opciones":[
            "Escándalos musicales.","Falta de oportunidades laborales.","Problemas Vecinales.",
            "Asentamientos ilegales (conocido como precarios).","Personas en situación de calle.",
            "Desvinculación escolar (deserción escolar)","Zona de prostitución","Consumo de alcohol en vía pública",
            "Personas con exceso de tiempo de ocio","Acumulación de basuras, aguas negras, mal alcantarillado.",
            "Carencia o inexistencia de alumbrado público.","Cuarterías","Lotes baldíos.","Ventas informales",
            "Pérdida de espacios públicos (parques, polideportivos, etc.).","Otro"
         ],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Falta de inversión social","name":"falta_inversion_social","required":False,
         "opciones":["Falta de oferta educativa","Falta de oferta deportiva","Falta de oferta recreativa","Falta de actividades culturales"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Consumo de drogas","name":"consumo_drogas","required":False,
         "opciones":["Área privada","Área pública"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Deficiencia en la infraestructura vial","name":"infra_vial","required":False,
         "opciones":["Calles en mal estado","Falta de señalización de tránsito","Carencia o inexistencia de aceras"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección múltiple","label":"Búnker","name":"bunker","required":False,
         "opciones":["Casa de habitación","Edificación abandonada","Lote baldío","Otro"],
         "appearance":None,"choice_filter":None,"relevant":None},


        # ---------------- Página 7: Información adicional ----------------
        {"tipo_ui":"Selección única","label":"¿Tiene información de alguna persona o grupo que realice delitos en su comunidad? (confidencial)","name":"info_grupo_delito","required":True,
         "opciones":["Si","No"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"Si su respuesta es \"SI\", describa características relevantes (estructura, personas, alias, señas, domicilios, vehículos, etc.)","name":"desc_info_grupo","required":True,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":f"${{info_grupo_delito}}='{slugify_name('Si')}'"},

        {"tipo_ui":"Selección única","label":"¿Usted o algún familiar ha sido víctima de un delito en los últimos 12 meses? ¿Denunció ante el OIJ?","name":"victimizacion_12m","required":True,
         "opciones":["NO he sido víctima de ningún delito","SI he sido víctima y SI denuncié","SI he sido víctima pero NO denuncié"],
         "appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Texto (corto)","label":"¿Cuál fue el delito del que fue víctima?","name":"delito_victima_si","required":True,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":f"${{victimizacion_12m}}='{slugify_name('SI he sido víctima y SI denuncié')}'"},

        {"tipo_ui":"Selección múltiple","label":"Modo de operar en el delito (marque todos los factores pertinentes)","name":"modo_operar_si","required":True,
         "opciones":["Arma blanca (cuchillo, machete, tijeras).","Arma de fuego.","Amenazas","Arrebato","Boquete","Ganzúa (pata de chancho)","Engaño","No sé.","Otro"],
         "appearance":None,"choice_filter":None,"relevant":f"${{victimizacion_12m}}='{slugify_name('SI he sido víctima y SI denuncié')}'"},

        {"tipo_ui":"Selección única","label":"Horario del hecho delictivo","name":"horario_hecho_si","required":True,
         "opciones":["00:00 - 02:59 a. m.","03:00 - 05:59 a. m.","06:00 - 08:59 a. m.","09:00 - 11:59 a. m.","12:00 - 14:59 p. m.","15:00 - 17:59 p. m.","18:00 - 20:59 p. m.","21:00 - 23:59 p. m.","DESCONOCIDO"],
         "appearance":None,"choice_filter":None,"relevant":f"${{victimizacion_12m}}='{slugify_name('SI he sido víctima y SI denuncié')}'"},

        {"tipo_ui":"Texto (corto)","label":"¿Cuál fue el delito del que fue víctima?","name":"delito_victima_no","required":True,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":f"${{victimizacion_12m}}='{slugify_name('SI he sido víctima pero NO denuncié')}'"},

        {"tipo_ui":"Selección múltiple","label":"Motivo de no denunciar (marque todos los que apliquen)","name":"motivo_no_denuncia","required":True,
         "opciones":["Distancia (falta de oficinas)","Miedo a represalias","Falta de respuesta oportuna","He realizado denuncias y no ha pasado nada",
                     "Complejidad al colocar la denuncia","Desconocimiento de dónde denunciar","El policía sugirió no denunciar","Falta de tiempo"],
         "appearance":None,"choice_filter":None,"relevant":f"${{victimizacion_12m}}='{slugify_name('SI he sido víctima pero NO denuncié')}'"},

        {"tipo_ui":"Selección múltiple","label":"Modo de operar en el delito","name":"modo_operar_no","required":True,
         "opciones":["Arma blanca (cuchillo, machete, tijeras).","Arma de fuego.","Amenazas","Arrebato","Boquete","Ganzúa (pata de chancho)","Engaño","No sé.","Otro"],
         "appearance":None,"choice_filter":None,"relevant":f"${{victimizacion_12m}}='{slugify_name('SI he sido víctima pero NO denuncié')}'"},

        {"tipo_ui":"Selección única","label":"Horario del hecho delictivo","name":"horario_hecho_no","required":True,
         "opciones":["00:00 - 02:59 a. m.","03:00 - 05:59 a. m.","06:00 - 08:59 a. m.","09:00 - 11:59 a. m.","12:00 - 14:59 p. m.","15:00 - 17:59 p. m.","18:00 - 20:59 p. m.","21:00 - 23:59 p. m.","DESCONOCIDO"],
         "appearance":None,"choice_filter":None,"relevant":f"${{victimizacion_12m}}='{slugify_name('SI he sido víctima pero NO denuncié')}'"},

        {"tipo_ui":"Selección única","label":"¿Cómo califica el servicio policial de la Fuerza Pública de Costa Rica en su comunidad?","name":"fp_calificacion","required":True,
         "opciones":["Excelente","Bueno","Regular","Mala","Muy mala"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"¿Cómo ha sido el servicio de la Fuerza Pública en los últimos 24 meses?","name":"fp_24m","required":True,
         "opciones":["Mejor servicio","Igual","Peor servicio"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"¿Conoce a los policías de su comunidad?","name":"conoce_policias","required":True,
         "opciones":["Si","No"],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Selección única","label":"¿Ha conversado con ellos/ellas sobre temas de seguridad?","name":"conversa_policias","required":True,
         "opciones":["Si","No"],"appearance":None,"choice_filter":None,"relevant":f"${{conoce_policias}}='{slugify_name('Si')}'"},

        {"tipo_ui":"Párrafo (texto largo)","label":"¿Qué actividad debería realizar la Fuerza Pública para mejorar la seguridad en su comunidad? (opcional)","name":"sugerencia_fp","required":False,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"¿Qué actividad debería realizar la municipalidad para mejorar la seguridad en su comunidad? (opcional)","name":"sugerencia_muni","required":False,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"Otra información que estime pertinente (opcional)","name":"otra_info","required":False,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":None},

        {"tipo_ui":"Párrafo (texto largo)","label":"(Voluntario) Nombre, teléfono o correo de contacto (confidencial)","name":"contacto_voluntario","required":False,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":None},
    ]

    st.session_state.preguntas = seed
    st.session_state.seed_cargado = True
# ==========================================================================================
# ============================== PARTE 9/10 ===============================================
# ========= construir_xlsform actualizado: P2 SIN Barrio + catálogo Cantón→Distrito ========
# ==========================================================================================
# NOTA: Esta parte REEMPLAZA dentro de tu bloque:
#   # ------------------------------------------------------------------------------------------
#   # Construcción XLSForm (incluye P2) + constraints para placeholders
#   # ------------------------------------------------------------------------------------------
# específicamente la función:
#   construir_xlsform(...)
# (puedes dejar intacto: _get_logo_media_name(), descargar_excel_xlsform(), y lo demás)
#
# Cambios EXACTOS:
# - Elimina barrio de sets y constraints
# - Ajusta catálogo manual: Cantón y Distrito (ya no Barrios)
# - Mantiene placeholders y choice_filter funcionando igual:
#   * list_canton: __pick_canton__
#   * list_distrito: __pick_distrito__ con any='1'
# - Mantiene todo lo demás igual (relevant, finalize, visibilidad, páginas P3..P7, etc.)

# ------------------------------------------------------------------------------------------
# Construcción XLSForm (incluye P2) + constraints para placeholders
# ------------------------------------------------------------------------------------------
def _get_logo_media_name(): 
    return logo_media_name

def construir_xlsform(preguntas, form_title: str, idioma: str, version: str,
                      reglas_vis, reglas_fin):
    survey_rows = []
    choices_rows = []

    # ---------------- Visibilidad por target ----------------
    vis_by_target = {}
    for r in reglas_vis:
        vis_by_target.setdefault(r["target"], []).append(
            {"src": r["src"], "op": r.get("op","="), "values": r.get("values",[])}
        )

    # ---------------- Finalización temprana ----------------
    fin_conds = []
    for r in reglas_fin:
        cond = build_relevant_expr([{"src": r["src"], "op": r.get("op","="), "values": r.get("values",[])}])
        if cond:
            fin_conds.append((r["index_src"], cond))

    # ---------------- Página 1: Intro ----------------
    survey_rows += [
        {"type":"begin_group","name":"p1_intro","label":"Introducción","appearance":"field-list"},
        {"type":"note","name":"intro_logo","label":form_title, "media::image": _get_logo_media_name()},
        {"type":"note","name":"intro_texto","label":INTRO_COMUNIDAD},
        {"type":"end_group","name":"p1_end"}
    ]

    # ---------------- Sets por página ----------------
    # P2 SIN barrio
    p2 = {"canton","distrito","edad","genero","escolaridad","relacion_zona"}

    p3 = {"se_siente_seguro","motivo_inseguridad","comparacion_anual","motivo_comparacion"}

    p4 = {"lugar_entretenimiento","espacios_recreativos","lugar_residencia","paradas_estaciones",
          "puentes_peatonales","transporte_publico","zona_bancaria","zona_comercio",
          "zonas_residenciales","lugares_turisticos","zona_mas_insegura","porque_insegura"}

    p5 = {"incidencia_delitos","venta_drogas","delitos_vida","delitos_sexuales","asaltos","estafas",
          "robo_fuerza","abandono_personas","explotacion_infantil","delitos_ambientales","trata_personas",
          "vi","vi_victima_ultimo_anno","vi_tipos","vi_fp_abordaje","vi_fp_eval"}

    p6 = {"riesgos_sociales","falta_inversion_social","consumo_drogas","infra_vial","bunker"}

    p7 = {"info_grupo_delito","desc_info_grupo","victimizacion_12m",
          "delito_victima_si","modo_operar_si","horario_hecho_si",
          "delito_victima_no","motivo_no_denuncia","modo_operar_no","horario_hecho_no",
          "fp_calificacion","fp_24m","conoce_policias","conversa_policias",
          "sugerencia_fp","sugerencia_muni","otra_info","contacto_voluntario"}

    # ---------------- Helper para agregar preguntas ----------------
    def add_q(q, idx):
        x_type, default_app, list_name = map_tipo_to_xlsform(q["tipo_ui"], q["name"])

        # relevant manual (precarga) + panel (constructor condicionales) + finalización
        rel_manual = q.get("relevant") or None
        rel_panel  = build_relevant_expr(vis_by_target.get(q["name"], []))

        # not(cond) para todo lo que venga después del index_src
        nots = [xlsform_not(cond) for idx_src, cond in fin_conds if idx_src < idx]
        rel_fin = "(" + " and ".join(nots) + ")" if nots else None

        parts = [p for p in [rel_manual, rel_panel, rel_fin] if p]
        if parts:
            rel_final = parts[0] if len(parts)==1 else ("(" + ") and (".join(parts) + ")")
        else:
            rel_final = None

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

        # -------- Constraints placeholders (solo CANTON/DISTRITO) --------
        if q["name"] == "canton":
            row["constraint"] = ". != '__pick_canton__'"
            row["constraint_message"] = "Seleccione un cantón válido."

        if q["name"] == "distrito":
            row["constraint"] = ". != '__pick_distrito__'"
            row["constraint_message"] = "Seleccione un distrito válido."

        survey_rows.append(row)

        # No generar opciones para cantón/distrito (se usan las del catálogo).
        if list_name and q["name"] not in {"canton","distrito"}:
            usados = set()
            for opt_label in (q.get("opciones") or []):
                base = slugify_name(opt_label)
                opt_name = asegurar_nombre_unico(base, usados)
                usados.add(opt_name)
                choices_rows.append({"list_name": list_name, "name": opt_name, "label": str(opt_label)})

    # ---------------- Helper para páginas ----------------
    def add_page(group_name, page_label, names_set):
        survey_rows.append({"type":"begin_group","name":group_name,"label":page_label,"appearance":"field-list"})
        for i, q in enumerate(preguntas):
            if q["name"] in names_set:
                add_q(q, i)
        survey_rows.append({"type":"end_group","name":f"{group_name}_end"})

    # ---------------- Páginas reales ----------------
    add_page("p2_demograficos", "Datos demográficos", p2)
    add_page("p3_sentimiento", "Sentimiento de inseguridad en el barrio", p3)
    add_page("p4_lugares", "Indique cómo se siente en los siguientes lugares de su barrio", p4)
    add_page("p5_incidencia", "Incidencia relacionada a delitos", p5)
    add_page("p6_riesgos", "Riesgos Sociales", p6)
    add_page("p7_info_adicional", "Información adicional", p7)

    # ---------------- Choices del catálogo manual (con unicidad por list+name) ----------------
    # Aquí se agregan tus filas de st.session_state.choices_ext_rows (Cantón/Distrito)
    for r in st.session_state.choices_ext_rows:
        choices_rows.append(dict(r))

    # ---------------- DataFrames ----------------
    survey_cols_all = set().union(*[r.keys() for r in survey_rows])
    survey_cols = [c for c in ["type","name","label","required","appearance","choice_filter","relevant",
                               "constraint","constraint_message","media::image"] if c in survey_cols_all]
    for k in sorted(survey_cols_all):
        if k not in survey_cols:
            survey_cols.append(k)
    df_survey = pd.DataFrame(survey_rows, columns=survey_cols)

    choices_cols_all = set()
    for r in choices_rows:
        choices_cols_all.update(r.keys())
    base_choice_cols = ["list_name","name","label"]
    for extra in sorted(choices_cols_all):
        if extra not in base_choice_cols:
            base_choice_cols.append(extra)
    df_choices = pd.DataFrame(choices_rows, columns=base_choice_cols) if choices_rows else pd.DataFrame(columns=base_choice_cols)

    df_settings = pd.DataFrame([{
        "form_title": form_title,
        "version": version,
        "default_language": idioma,
        "style": "pages"
    }], columns=["form_title","version","default_language","style"])

    return df_survey, df_choices, df_settings
# ==========================================================================================
# ============================== PARTE 10/10 ==============================================
# ====== Catálogo por lotes actualizado: Cantón → Distrito (SIN Barrio) + placeholders ======
# ==========================================================================================
# NOTA: Esta parte REEMPLAZA COMPLETA la sección en tu código:
#   # ------------------------------------------------------------------------------------------
#   # Catálogo manual por lotes: Cantón → Distrito → (Barrios…)
#   # ------------------------------------------------------------------------------------------
# hasta la vista previa del catálogo (st.dataframe...).
#
# Cambios EXACTOS:
# - Ya NO se pide Barrios.
# - Ya NO existe list_barrio ni distrito_key.
# - Se mantienen placeholders:
#     list_canton:  __pick_canton__
#     list_distrito: __pick_distrito__  (con any='1')
# - list_distrito usa canton_key = slug_c para choice_filter en la pregunta Distrito
# - Mantiene todo lo demás igual.

# ------------------------------------------------------------------------------------------
# Catálogo manual por lotes: Cantón → Distrito
# ------------------------------------------------------------------------------------------
if "choices_ext_rows" not in st.session_state:
    st.session_state.choices_ext_rows = []  # filas para hoja choices
if "choices_extra_cols" not in st.session_state:
    st.session_state.choices_extra_cols = set()

def _append_choice_unique(row: Dict):
    """Inserta fila en choices evitando duplicados por (list_name,name)."""
    key = (row.get("list_name"), row.get("name"))
    exists = any((r.get("list_name"), r.get("name")) == key for r in st.session_state.choices_ext_rows)
    if not exists:
        st.session_state.choices_ext_rows.append(row)

st.markdown("### 📚 Catálogo Cantón → Distrito (por lotes)")
with st.expander("Agrega un lote (un Cantón y un Distrito)", expanded=True):
    col_c1, col_c2 = st.columns(2)
    canton_txt = col_c1.text_input("Cantón (una vez)", value="")
    distrito_txt = col_c2.text_input("Distrito (una vez)", value="")

    col_b1, col_b2, col_b3 = st.columns([1, 1, 2])
    add_lote = col_b1.button("Agregar lote", type="primary", use_container_width=True)
    clear_all = col_b2.button("Limpiar catálogo", use_container_width=True)

    if clear_all:
        st.session_state.choices_ext_rows = []
        st.success("Catálogo limpiado.")

    if add_lote:
        c = canton_txt.strip()
        d = distrito_txt.strip()

        if not c or not d:
            st.error("Debes indicar Cantón y Distrito.")
        else:
            slug_c = slugify_name(c)
            slug_d = slugify_name(d)

            # columnas extra usadas por filtros/placeholder
            st.session_state.choices_extra_cols.update({"canton_key", "any"})

            # Placeholders (una sola vez por lista)
            _append_choice_unique({
                "list_name": "list_canton",
                "name": "__pick_canton__",
                "label": "— escoja un cantón —"
            })
            _append_choice_unique({
                "list_name": "list_distrito",
                "name": "__pick_distrito__",
                "label": "— escoja un cantón —",
                "any": "1"
            })

            # Cantón (evita duplicados automáticamente)
            _append_choice_unique({
                "list_name": "list_canton",
                "name": slug_c,
                "label": c
            })

            # Distrito vinculado a Cantón (canton_key)
            _append_choice_unique({
                "list_name": "list_distrito",
                "name": slug_d,
                "label": d,
                "canton_key": slug_c
            })

            st.success(f"Lote agregado: {c} → {d}")

# Vista previa de catálogo
if st.session_state.choices_ext_rows:
    st.dataframe(
        pd.DataFrame(st.session_state.choices_ext_rows),
        use_container_width=True,
        hide_index=True,
        height=240
    )
