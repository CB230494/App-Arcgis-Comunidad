# -*- coding: utf-8 -*-
# ==========================================================================================
# App: Encuesta Comunidad → XLSForm para ArcGIS Survey123 (versión extendida)
# - Constructor completo (agregar/editar/ordenar/borrar)
# - Condicionales (relevant) + finalizar temprano
# - Listas en cascada (choice_filter) Cantón→Distrito→Barrio [CARGA DESDE EXCEL]
# - Exportar/Importar proyecto (JSON)
# - Exportar a XLSForm (survey/choices/settings)
# - PÁGINAS reales (style="pages"): Intro + P2..P7
# - Portada con logo (media::image) y texto de introducción
# - Exportes Word/PDF con el estilo afinado (observaciones sin límite, colores)
# - Opciones visibles en Word/PDF para select_one/multiple, salvo preguntas Sí/No
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
Crea tu cuestionario y **exporta un XLSForm** listo para **ArcGIS Survey123** (Connect/Web Designer).

Incluye:
- Tipos: **text**, **integer/decimal**, **date**, **time**, **geopoint**, **select_one**, **select_multiple**.
- **Constructor completo** (agregar, editar, ordenar, borrar) con condicionales.
- **Listas en cascada** **Cantón→Distrito→Barrio** (choice_filter precargado desde Excel).
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
    if hasattr(st, "rerun"): st.rerun()
    else: st.experimental_rerun()

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
    if base not in usados: return base
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
        return ("integer", None, None)  # usa decimal si lo cambias luego
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
    if not conds: return None
    if len(conds) == 1: return conds[0]
    return "(" + " or ".join(conds) + ")"

def xlsform_not(expr):
    if not expr: return None
    return f"not({expr})"

def build_relevant_expr(rules_for_target: List[Dict]):
    or_parts = []
    for r in rules_for_target:
        src = r["src"]
        op = r.get("op", "=")
        vals = r.get("values", [])
        if not vals: continue
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
# Cargar cascadas Cantón→Distrito→Barrio desde Excel
# Espera columnas equivalentes a:
#  - 'Nombre Cantón' (o 'Cantón' / 'Canton' / variantes)
#  - 'Nombre Distrito' (o 'Distrito' / variantes)
#  - 'Nombre Localidad' (o 'Localidad' / 'Barrio' / variantes)
# Detecta automáticamente la HOJA adecuada.
# ------------------------------------------------------------------------------------------
def cargar_cascadas_desde_excel(ruta_excel: str):
    """
    Carga Cantón→Distrito→Barrio desde un Excel detectando hoja/columnas automáticamente.
    """
    xls = pd.ExcelFile(ruta_excel)
    target_df = None
    sheet_found = None

    def norm(s: str) -> str:
        s = s.strip().lower()
        s = (s.replace("á","a").replace("é","e").replace("í","i")
                .replace("ó","o").replace("ú","u").replace("ñ","n"))
        return s

    wants_canton   = {"canton", "nombre canton", "cantón", "nombre cantón"}
    wants_distrito = {"distrito", "nombre distrito", "distritos"}
    wants_barrio   = {"localidad", "nombre localidad", "barrio", "barrios", "localidades"}

    for sh in xls.sheet_names:
        df_try = pd.read_excel(ruta_excel, sheet_name=sh, dtype=str)
        cols_norm = {norm(c): c for c in df_try.columns}
        has_canton   = any(k in cols_norm for k in wants_canton)
        has_distrito = any(k in cols_norm for k in wants_distrito)
        has_barrio   = any(k in cols_norm for k in wants_barrio)
        if has_canton and has_distrito and has_barrio:
            target_df = df_try
            sheet_found = sh
            break

    if target_df is None:
        raise ValueError("No se encontraron columnas de Cantón, Distrito y Localidad en ninguna hoja del Excel.")

    cols_norm = {norm(c): c for c in target_df.columns}
    def pick(wants: set) -> str:
        for w in wants:
            if w in cols_norm:
                return cols_norm[w]
        raise KeyError("Columna requerida no encontrada.")

    c_col = pick(wants_canton)
    d_col = pick(wants_distrito)
    b_col = pick(wants_barrio)

    sub = target_df[[c_col, d_col, b_col]].dropna(how="any").copy()
    sub[c_col] = sub[c_col].astype(str).str.strip()
    sub[d_col] = sub[d_col].astype(str).str.strip()
    sub[b_col] = sub[b_col].astype(str).str.strip()
    sub = sub[(sub[c_col] != "") & (sub[d_col] != "") & (sub[b_col] != "")]

    if "choices_ext_rows" not in st.session_state:
        st.session_state.choices_ext_rows = []
    st.session_state.choices_extra_cols.update({"canton_key", "distrito_key"})
    st.session_state.choices_ext_rows = [
        r for r in st.session_state.choices_ext_rows
        if r.get("list_name") not in ("list_distrito", "list_barrio")
    ]

    distritos = sub[[c_col, d_col]].drop_duplicates().sort_values([c_col, d_col])
    barrios   = sub[[d_col, b_col]].drop_duplicates().sort_values([d_col, b_col])

    for _, row in distritos.iterrows():
        st.session_state.choices_ext_rows.append({
            "list_name": "list_distrito",
            "name": slugify_name(str(row[d_col])),
            "label": str(row[d_col]),
            "canton_key": str(row[c_col])
        })
    for _, row in barrios.iterrows():
        st.session_state.choices_ext_rows.append({
            "list_name": "list_barrio",
            "name": slugify_name(str(row[b_col])),
            "label": str(row[b_col]),
            "distrito_key": str(row[d_col])
        })

    st.session_state.cascadas_cargadas = True
    st.info(f"Cascadas cargadas desde la hoja **{sheet_found}**.")
# ------------------------------------------------------------------------------------------
# Cabecera: Logo + “Nombre de la Delegación” (encabezado compuesto)
# ------------------------------------------------------------------------------------------
DEFAULT_LOGO_PATH = "001.png"

col_logo, col_txt = st.columns([1, 3], vertical_alignment="center")
with col_logo:
    up_logo = st.file_uploader("Logo (PNG/JPG)", type=["png","jpg","jpeg"])
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
        value=st.session_state.get("_logo_name","001.png"),
        help="Debe coincidir con el archivo en la carpeta `media/` de Survey123 Connect."
    )
    titulo_compuesto = (f"Encuesta comunidad – {delegacion.strip()}"
                        if delegacion.strip() else "Encuesta comunidad")
    st.markdown(f"<h5 style='text-align:center;margin:4px 0'>📋 {titulo_compuesto}</h5>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------------------
# Estado (session_state)
# ------------------------------------------------------------------------------------------
if "preguntas" not in st.session_state:
    st.session_state.preguntas = []
if "reglas_visibilidad" not in st.session_state:
    st.session_state.reglas_visibilidad = []
if "reglas_finalizar" not in st.session_state:
    st.session_state.reglas_finalizar = []
if "choices_extra_cols" not in st.session_state:
    st.session_state.choices_extra_cols = set()
if "choices_ext_rows" not in st.session_state:
    st.session_state.choices_ext_rows = []
if "cascadas_cargadas" not in st.session_state:
    st.session_state.cascadas_cargadas = False
if "ruta_excel_cascadas" not in st.session_state:
    st.session_state.ruta_excel_cascadas = "Base de Datos Poblados por Regiones 2021.xlsx"

# Intento de auto-carga una vez
if not st.session_state.cascadas_cargadas:
    try:
        cargar_cascadas_desde_excel(st.session_state.ruta_excel_cascadas)
        st.session_state.cascadas_cargadas = True
    except Exception as e:
        st.warning(f"No se pudo precargar Cantón→Distrito→Barrio desde Excel: {e}")

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
# Precarga EXACTA de preguntas (páginas 2–7)
# ------------------------------------------------------------------------------------------
if "seed_cargado" not in st.session_state:

    v_si = slugify_name("Si")
    v_no = slugify_name("No")
    v_mas_seguro  = slugify_name("Más seguro")
    v_igual       = slugify_name("Igual")
    v_menos_seg   = slugify_name("Menos seguro")

    seed = [
        # ---------------- Página 2: Datos demográficos ----------------
        {"tipo_ui":"Selección única","label":"Cantón","name":"canton","required":True,
         "opciones":["— cargado desde Excel —"],"appearance":None,"choice_filter":None,"relevant":None},
        {"tipo_ui":"Selección única","label":"Distrito","name":"distrito","required":True,
         "opciones":["— se rellena según Cantón —"],"appearance":None,"choice_filter":"canton_key=${canton}","relevant":None},
        {"tipo_ui":"Selección única","label":"Barrio","name":"barrio","required":True,
         "opciones":["— se rellena según Distrito —"],"appearance":None,"choice_filter":"distrito_key=${distrito}","relevant":None},
        {"tipo_ui":"Número","label":"Edad","name":"edad","required":True,"opciones":[],"appearance":None,"choice_filter":None,"relevant":None},
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

        # Subflujo Violencia Intrafamiliar (no obligatorias salvo al entrar al subflujo)
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

        # Rama: SI víctima y SI denunció
        {"tipo_ui":"Texto (corto)","label":"¿Cuál fue el delito del que fue víctima?","name":"delito_victima_si","required":True,
         "opciones":[],"appearance":None,"choice_filter":None,"relevant":f"${{victimizacion_12m}}='{slugify_name('SI he sido víctima y SI denuncié')}'"},
        {"tipo_ui":"Selección múltiple","label":"Modo de operar en el delito (marque todos los factores pertinentes)","name":"modo_operar_si","required":True,
         "opciones":["Arma blanca (cuchillo, machete, tijeras).","Arma de fuego.","Amenazas","Arrebato","Boquete","Ganzúa (pata de chancho)","Engaño","No sé.","Otro"],
         "appearance":None,"choice_filter":None,"relevant":f"${{victimizacion_12m}}='{slugify_name('SI he sido víctima y SI denuncié')}'"},
        {"tipo_ui":"Selección única","label":"Horario del hecho delictivo","name":"horario_hecho_si","required":True,
         "opciones":["00:00 - 02:59 a. m.","03:00 - 05:59 a. m.","06:00 - 08:59 a. m.","09:00 - 11:59 a. m.","12:00 - 14:59 p. m.","15:00 - 17:59 p. m.","18:00 - 20:59 p. m.","21:00 - 23:59 p. m.","DESCONOCIDO"],
         "appearance":None,"choice_filter":None,"relevant":f"${{victimizacion_12m}}='{slugify_name('SI he sido víctima y SI denuncié')}'"},

        # Rama: SI víctima pero NO denunció
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

        # Evaluación y sugerencias
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
# ------------------------------------------------------------------------------------------
# Sidebar: Metadatos + Acciones (cargar Excel cascadas / exportar-importar proyecto)
# ------------------------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuración")
    form_title = st.text_input(
        "Título del formulario",
        value=(f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad")
    )
    idioma = st.selectbox("Idioma por defecto (default_language)", options=["es","en"], index=0)
    version_auto = datetime.now().strftime("%Y%m%d%H%M")
    version = st.text_input("Versión (settings.version)", value=version_auto)

    st.markdown("---")
    st.caption("📚 **Fuente de cascadas** Cantón→Distrito→Barrio (Excel)")
    ruta_excel = st.text_input("Ruta del Excel", value=st.session_state.ruta_excel_cascadas,
                               help="Debe contener columnas: Nombre Cantón, Nombre Distrito, Nombre Localidad (o equivalentes).")
    up_excel = st.file_uploader("…o subir Excel", type=["xlsx"])

    col_c1, col_c2 = st.columns(2)
    if col_c1.button("Cargar/recargar cascadas", use_container_width=True):
        try:
            if up_excel is not None:
                data_bytes = up_excel.read()
                tmp_buf = BytesIO(data_bytes)
                with open("tmp_cascadas.xlsx", "wb") as f:
                    f.write(tmp_buf.getvalue())
                cargar_cascadas_desde_excel("tmp_cascadas.xlsx")
                st.success("Cascadas cargadas desde el Excel subido.")
            else:
                st.session_state.ruta_excel_cascadas = ruta_excel
                cargar_cascadas_desde_excel(ruta_excel)
                st.success("Cascadas cargadas desde la ruta indicada.")
        except Exception as e:
            st.error(f"No se pudieron cargar las cascadas: {e}")

    if col_c2.button("Limpiar cascadas", use_container_width=True):
        st.session_state.choices_ext_rows = [r for r in st.session_state.choices_ext_rows
                                             if r.get("list_name") not in ("list_distrito","list_barrio")]
        st.session_state.cascadas_cargadas = False
        st.info("Cascadas eliminadas de la sesión.")

    st.markdown("---")
    st.caption("💾 Exporta/Importa tu proyecto (JSON)")
    col_exp, col_imp = st.columns(2)
    with col_exp:
        if st.button("Exportar proyecto (JSON)", use_container_width=True):
            proj = {
                "form_title": form_title,
                "idioma": idioma,
                "version": version,
                "preguntas": st.session_state.preguntas,
                "reglas_visibilidad": st.session_state.reglas_visibilidad,
                "reglas_finalizar": st.session_state.reglas_finalizar
            }
            jbuf = BytesIO(json.dumps(proj, ensure_ascii=False, indent=2).encode("utf-8"))
            st.download_button("Descargar JSON", data=jbuf, file_name="proyecto_encuesta.json",
                               mime="application/json", use_container_width=True)
    with col_imp:
        up = st.file_uploader("Importar JSON", type=["json"], label_visibility="collapsed")
        if up is not None:
            try:
                raw = up.read().decode("utf-8")
                data = json.loads(raw)
                st.session_state.preguntas = list(data.get("preguntas", []))
                st.session_state.reglas_visibilidad = list(data.get("reglas_visibilidad", []))
                st.session_state.reglas_finalizar = list(data.get("reglas_finalizar", []))
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
    col_n1, col_n2, col_n3 = st.columns([2,1,1])
    with col_n1:
        name = st.text_input("Nombre interno (XLSForm 'name')", value=sugerido)
    with col_n2:
        required = st.checkbox("Requerida", value=False)
    with col_n3:
        appearance = st.text_input("Appearance (opcional)", value="")

    opciones = []
    if tipo_ui in ("Selección única","Selección múltiple"):
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
        nueva = {
            "tipo_ui": tipo_ui,
            "label": label.strip(),
            "name": unico,
            "required": required,
            "opciones": opciones,
            "appearance": (appearance.strip() or None),
            "choice_filter": None,
            "relevant": None
        }
        st.session_state.preguntas.append(nueva)
        st.success(f"Pregunta agregada: **{label}** (name: `{unico}`)")

# ------------------------------------------------------------------------------------------
# Panel de Condicionales (mostrar / finalizar)
# ------------------------------------------------------------------------------------------
st.subheader("🔀 Condicionales (mostrar / finalizar)")

if not st.session_state.preguntas:
    st.info("Agrega preguntas para definir condicionales.")
else:
    # ----- Reglas de visibilidad -----
    with st.expander("👁️ Mostrar pregunta si se cumple condición", expanded=False):
        names = [q["name"] for q in st.session_state.preguntas]
        labels_by_name = {q["name"]: q["label"] for q in st.session_state.preguntas}

        target = st.selectbox("Pregunta a mostrar (target)", options=names, format_func=lambda n: f"{n} — {labels_by_name[n]}")
        src = st.selectbox("Depende de (source)", options=names, format_func=lambda n: f"{n} — {labels_by_name[n]}")
        op = st.selectbox("Operador", options=["=", "selected"], help="= para select_one; selected para select_multiple")

        src_q = next((q for q in st.session_state.preguntas if q["name"] == src), None)
        vals = []
        if src_q and src_q["opciones"]:
            vals = st.multiselect("Valores que activan la visibilidad (elige texto; internamente se usa el 'name' slug)", options=src_q["opciones"])
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

    # ----- Reglas de finalizar -----
    with st.expander("⏹️ Finalizar temprano si se cumple condición", expanded=False):
        names = [q["name"] for q in st.session_state.preguntas]
        labels_by_name = {q["name"]: q["label"] for q in st.session_state.preguntas}
        src2 = st.selectbox("Condición basada en", options=names, format_func=lambda n: f"{n} — {labels_by_name[n]}", key="final_src")
        op2 = st.selectbox("Operador", options=["=", "selected", "!="], key="final_op")
        src2_q = next((q for q in st.session_state.preguntas if q["name"] == src2), None)
        vals2 = []
        if src2_q and src2_q["opciones"]:
            vals2 = st.multiselect("Valores que disparan el fin (se usan como 'name' slug)", options=src2_q["opciones"], key="final_vals")
            vals2 = [slugify_name(v) for v in vals2]
        else:
            manual2 = st.text_input("Valor (si no hay opciones)", key="final_manual")
            vals2 = [slugify_name(manual2)] if manual2.strip() else []
        if st.button("➕ Agregar regla de finalización"):
            if not vals2:
                st.error("Indica al menos un valor.")
            else:
                idx_src = next((i for i, q in enumerate(st.session_state.preguntas) if q["name"] == src2), 0)
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
            if q.get("appearance"): meta += f"  •  appearance: `{q['appearance']}`"
            if q.get("choice_filter"): meta += f"  •  choice_filter: `{q['choice_filter']}`"
            if q.get("relevant"): meta += f"  •  relevant: `{q['relevant']}`"
            c1.caption(meta)
            if q["tipo_ui"] in ("Selección única","Selección múltiple"):
                c1.caption("Opciones: " + ", ".join(q.get("opciones") or []))

            up = c2.button("⬆️ Subir", key=f"up_{idx}", use_container_width=True, disabled=(idx == 0))
            down = c3.button("⬇️ Bajar", key=f"down_{idx}", use_container_width=True, disabled=(idx == len(st.session_state.preguntas)-1))
            edit = c4.button("✏️ Editar", key=f"edit_{idx}", use_container_width=True)
            borrar = c5.button("🗑️ Eliminar", key=f"del_{idx}", use_container_width=True)

            if up:
                st.session_state.preguntas[idx-1], st.session_state.preguntas[idx] = st.session_state.preguntas[idx], st.session_state.preguntas[idx-1]
                _rerun()
            if down:
                st.session_state.preguntas[idx+1], st.session_state.preguntas[idx] = st.session_state.preguntas[idx], st.session_state.preguntas[idx+1]
                _rerun()

            if edit:
                st.markdown("**Editar esta pregunta**")
                ne_label = st.text_input("Etiqueta", value=q["label"], key=f"e_label_{idx}")
                ne_name = st.text_input("Nombre interno (name)", value=q["name"], key=f"e_name_{idx}")
                ne_required = st.checkbox("Requerida", value=q["required"], key=f"e_req_{idx}")
                ne_appearance = st.text_input("Appearance", value=q.get("appearance") or "", key=f"e_app_{idx}")
                ne_choice_filter = st.text_input("choice_filter (opcional)", value=q.get("choice_filter") or "", key=f"e_cf_{idx}")
                ne_relevant = st.text_input("relevant (opcional – se autogenera por reglas)", value=q.get("relevant") or "", key=f"e_rel_{idx}")

                ne_opciones = q.get("opciones") or []
                if q["tipo_ui"] in ("Selección única","Selección múltiple"):
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
                    if q["tipo_ui"] in ("Selección única","Selección múltiple"):
                        st.session_state.preguntas[idx]["opciones"] = ne_opciones
                    st.success("Cambios guardados.")
                    _rerun()
                if col_cancel.button("Cancelar", key=f"e_cancel_{idx}", use_container_width=True):
                    _rerun()

            if borrar:
                del st.session_state.preguntas[idx]
                st.warning("Pregunta eliminada.")
                _rerun()
# ------------------------------------------------------------------------------------------
# Construcción XLSForm (páginas, condicionales y logo)
# ------------------------------------------------------------------------------------------
def _get_logo_media_name():
    return logo_media_name

def construir_xlsform(preguntas, form_title: str, idioma: str, version: str,
                      reglas_vis, reglas_fin):
    survey_rows = []
    choices_rows = []

    vis_by_target = {}
    for r in reglas_vis:
        vis_by_target.setdefault(r["target"], []).append({
            "src": r["src"], "op": r.get("op","="), "values": r.get("values",[])
        })

    fin_conds = []
    for r in reglas_fin:
        cond = build_relevant_expr([{"src": r["src"], "op": r.get("op","="), "values": r.get("values",[])}])
        if cond:
            fin_conds.append((r["index_src"], cond))

    # ------------------- Página 1: INTRO -------------------
    survey_rows.append({"type":"begin_group","name":"p1_intro","label":"Introducción","appearance":"field-list"})
    survey_rows.append({"type":"note","name":"intro_logo","label":form_title, "media::image": _get_logo_media_name()})
    survey_rows.append({"type":"note","name":"intro_texto","label":INTRO_COMUNIDAD})
    survey_rows.append({"type":"end_group","name":"p1_end"})

    # Sets por página
    p2 = {"canton","distrito","barrio","edad","genero","escolaridad","relacion_zona"}
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

    def add_q(q, idx):
        x_type, default_app, list_name = map_tipo_to_xlsform(q["tipo_ui"], q["name"])

        rel_manual = q.get("relevant") or None
        rel_panel  = build_relevant_expr(vis_by_target.get(q["name"], []))

        nots = []
        for idx_src, cond in fin_conds:
            if idx_src < idx:
                nots.append(xlsform_not(cond))
        rel_fin = "(" + " and ".join(nots) + ")" if nots else None

        parts = [p for p in [rel_manual, rel_panel, rel_fin] if p]
        rel_final = parts[0] if parts and len(parts)==1 else ("(" + ") and (".join(parts) + ")" if parts else None)

        row = {"type": x_type, "name": q["name"], "label": q["label"]}
        if q.get("required"): row["required"] = "yes"
        app = q.get("appearance") or default_app
        if app: row["appearance"] = app
        if q.get("choice_filter"): row["choice_filter"] = q["choice_filter"]
        if rel_final: row["relevant"] = rel_final
        survey_rows.append(row)

        if list_name:
            usados = set()
            for opt_label in (q.get("opciones") or []):
                base = slugify_name(opt_label)
                opt_name = asegurar_nombre_unico(base, usados)
                usados.add(opt_name)
                choices_rows.append({"list_name": list_name, "name": opt_name, "label": str(opt_label)})

    def add_page(group_name, page_label, names_set):
        survey_rows.append({"type":"begin_group","name":group_name,"label":page_label,"appearance":"field-list"})
        for i, q in enumerate(preguntas):
            if q["name"] in names_set:
                add_q(q, i)
        survey_rows.append({"type":"end_group","name":f"{group_name}_end"})

    add_page("p2_demograficos", "Datos demográficos", p2)
    add_page("p3_sentimiento", "Sentimiento de inseguridad en el barrio", p3)
    add_page("p4_lugares", "Indique cómo se siente en los siguientes lugares de su barrio", p4)
    add_page("p5_incidencia", "Incidencia relacionada a delitos", p5)
    add_page("p6_riesgos", "Riesgos Sociales", p6)
    add_page("p7_info_adicional", "Información adicional", p7)

    # Choices extendidos (cascadas)
    if "choices_ext_rows" in st.session_state:
        for r in st.session_state.choices_ext_rows:
            choices_rows.append(dict(r))

    # DataFrames
    survey_cols_all = set()
    for r in survey_rows:
        survey_cols_all.update(r.keys())
    survey_cols = [c for c in ["type","name","label","required","appearance","choice_filter","relevant","media::image"] if c in survey_cols_all]
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

def descargar_excel_xlsform(df_survey, df_choices, df_settings, nombre_archivo: str):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_survey.to_excel(writer,  sheet_name="survey",   index=False)
        df_choices.to_excel(writer, sheet_name="choices",  index=False)
        df_settings.to_excel(writer, sheet_name="settings", index=False)
        wb = writer.book
        fmt_hdr = wb.add_format({"bold": True, "align": "left"})
        for sheet, df in (("survey", df_survey), ("choices", df_choices), ("settings", df_settings)):
            ws = writer.sheets[sheet]
            ws.freeze_panes(1, 0)
            ws.set_row(0, None, fmt_hdr)
            cols = list(df.columns)
            for col_idx, col_name in enumerate(cols):
                ws.set_column(col_idx, col_idx, max(14, min(40, len(str(col_name)) + 10)))
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

st.caption("""
Incluye:
- **survey** con tipos, `relevant`, `choice_filter`, `appearance`, `media::image` (portada),
- **choices** (con columnas extra como `canton_key`/`distrito_key` para cascadas),
- **settings** con título, versión, idioma y **style = pages**.
""")

if st.button("🧮 Construir XLSForm", use_container_width=True, disabled=not st.session_state.preguntas):
    try:
        names = [q["name"] for q in st.session_state.preguntas]
        if len(names) != len(set(names)):
            st.error("Hay 'name' duplicados. Edita las preguntas para que cada 'name' sea único.")
        else:
            df_survey, df_choices, df_settings = construir_xlsform(
                st.session_state.preguntas,
                form_title=(f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad"),
                idioma=st.session_state.get("idioma", "es") if False else "es",
                version=version.strip() or datetime.now().strftime("%Y%m%d%H%M"),
                reglas_vis=st.session_state.reglas_visibilidad,
                reglas_fin=st.session_state.reglas_finalizar
            )

            st.success("XLSForm construido. Vista previa:")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Hoja: survey**")
                st.dataframe(df_survey, use_container_width=True, hide_index=True)
            with c2:
                st.markdown("**Hoja: choices**")
                st.dataframe(df_choices, use_container_width=True, hide_index=True)
            with c3:
                st.markdown("**Hoja: settings**")
                st.dataframe(df_settings, use_container_width=True, hide_index=True)

            nombre_archivo = slugify_name(form_title) + "_xlsform.xlsx"
            descargar_excel_xlsform(df_survey, df_choices, df_settings, nombre_archivo=nombre_archivo)

            if st.session_state.get("_logo_bytes"):
                st.download_button(
                    "📥 Descargar logo para carpeta media",
                    data=st.session_state["_logo_bytes"],
                    file_name=logo_media_name,
                    mime="image/png",
                    use_container_width=True
                )

            st.info("""
**Publicar en Survey123 (Connect)**
1) Crea la encuesta **desde archivo** con el XLSForm exportado.
2) Copia tu imagen de logo a la carpeta **media/** del proyecto con el **mismo nombre** que figura en `media::image`.
3) Previsualiza: verás la página 1 **Introducción** y el encabezado **“Encuesta comunidad – …”**.
4) Usa **Siguiente / Atrás** para navegar y publica.
""")
    except Exception as e:
        st.error(f"Ocurrió un error al generar el XLSForm: {e}")
# ------------------------------------------------------------------------------------------
# PARTE 10/10 — Exportar Word y PDF editable con el estilo afinado
# - Portada con logo grande, título centrado (negro), intro
# - Secciones por página (P2..P7) con sus títulos
# - Debajo de cada pregunta: cuadro de observaciones (sin límite), colores rotativos
# - Mostrar opciones para preguntas de selección (excepto Sí/No)
# ------------------------------------------------------------------------------------------
from typing import List, Dict

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
except Exception:
    Document = None

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.lib.colors import HexColor, black
except Exception:
    canvas = None

# ---------- utilidades compartidas ----------
def _build_cond_text(qname: str, reglas_vis: List[Dict]) -> str:
    rels = [r for r in reglas_vis if r.get("target") == qname]
    if not rels:
        return ""
    parts = []
    for r in rels:
        op = r.get("op", "=")
        vals = r.get("values", [])
        vtxt = ", ".join(vals) if vals else ""
        parts.append(f"{r['src']} {op} [{vtxt}]")
    return "Condición: se muestra si " + " OR ".join(parts)

def _get_logo_bytes_fallback() -> bytes | None:
    if st.session_state.get("_logo_bytes"):
        return st.session_state["_logo_bytes"]
    try:
        with open("001.png", "rb") as f:
            return f.read()
    except Exception:
        return None

def _wrap_text_lines(text: str, font_name: str, font_size: float, max_width: float) -> List[str]:
    if not text:
        return []
    words = text.split()
    lines, current = [], ""
    for w in words:
        test = (current + " " + w).strip()
        if stringWidth(test, font_name, font_size) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            if stringWidth(w, font_name, font_size) > max_width:
                chunk = ""
                for ch in w:
                    if stringWidth(chunk + ch, font_name, font_size) <= max_width:
                        chunk += ch
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = ch
                current = chunk
            else:
                current = w
    if current:
        lines.append(current)
    return lines

def _is_yes_no_options(opts: List[str]) -> bool:
    if not opts: return False
    norm = {slugify_name(x) for x in opts if x and str(x).strip()}
    yes_variants = {"si","sí","yes"}
    no_variants = {"no"}
    return norm.issubset(yes_variants | no_variants) and any(y in norm for y in yes_variants) and any(n in norm for n in no_variants)

def _should_show_options(q: Dict) -> bool:
    if q.get("tipo_ui") not in ("Selección única", "Selección múltiple"):
        return False
    opts = q.get("opciones") or []
    return bool(opts) and not _is_yes_no_options(opts)

# Sets por página (para imprimir secciones)
P2_NAMES = {"canton","distrito","barrio","edad","genero","escolaridad","relacion_zona"}
P3_NAMES = {"se_siente_seguro","motivo_inseguridad","comparacion_anual","motivo_comparacion"}
P4_NAMES = {"lugar_entretenimiento","espacios_recreativos","lugar_residencia","paradas_estaciones",
            "puentes_peatonales","transporte_publico","zona_bancaria","zona_comercio",
            "zonas_residenciales","lugares_turisticos","zona_mas_insegura","porque_insegura"}
P5_NAMES = {"incidencia_delitos","venta_drogas","delitos_vida","delitos_sexuales","asaltos","estafas",
            "robo_fuerza","abandono_personas","explotacion_infantil","delitos_ambientales","trata_personas",
            "vi","vi_victima_ultimo_anno","vi_tipos","vi_fp_abordaje","vi_fp_eval"}
P6_NAMES = {"riesgos_sociales","falta_inversion_social","consumo_drogas","infra_vial","bunker"}
P7_NAMES = {"info_grupo_delito","desc_info_grupo","victimizacion_12m",
            "delito_victima_si","modo_operar_si","horario_hecho_si",
            "delito_victima_no","motivo_no_denuncia","modo_operar_no","horario_hecho_no",
            "fp_calificacion","fp_24m","conoce_policias","conversa_policias",
            "sugerencia_fp","sugerencia_muni","otra_info","contacto_voluntario"}

ALL_BY_PAGE = [
    ("Datos demográficos", P2_NAMES),
    ("Sentimiento de inseguridad en el barrio", P3_NAMES),
    ("Indique cómo se siente en los siguientes lugares de su barrio", P4_NAMES),
    ("Incidencia relacionada a delitos", P5_NAMES),
    ("Riesgos Sociales", P6_NAMES),
    ("Información adicional", P7_NAMES),
]

# ---------- helpers Word ----------
def _set_cell_shading(cell, fill_hex: str):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = tcPr.find(qn('w:shd'))
    if shd is None:
        shd = OxmlElement('w:shd')
        tcPr.append(shd)
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex.replace('#','').upper())

def _set_cell_borders(cell, color_hex: str):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    borders = tcPr.find(qn('w:tcBorders'))
    if borders is None:
        borders = OxmlElement('w:tcBorders')
        tcPr.append(borders)
    for edge in ('top','left','bottom','right'):
        tag = OxmlElement(f'w:{edge}')
        tag.set(qn('w:val'), 'single')
        tag.set(qn('w:sz'), '8')  # ~0.5pt
        tag.set(qn('w:color'), color_hex.replace('#','').upper())
        borders.append(tag)

def _add_observation_box(doc: Document, fill_hex: str, border_hex: str):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl.autofit = True
    cell = tbl.cell(0, 0)
    _set_cell_shading(cell, fill_hex)
    _set_cell_borders(cell, border_hex)
    row = tbl.rows[0]
    row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    row.height = Inches(1.1)  # alto mínimo, luego crece sin límite
    p = cell.paragraphs[0]
    p.add_run("")

# ---------- EXPORT WORD ----------
def export_docx_form(preguntas: List[Dict], form_title: str, intro: str, reglas_vis: List[Dict]):
    if Document is None:
        st.error("Falta dependencia: instala `python-docx` para generar Word.")
        return

    fills = ["#E6F4EA", "#E7F0FE", "#FDECEA"]
    borders = ["#1E8E3E", "#1A73E8", "#D93025"]
    BLACK = RGBColor(0, 0, 0)

    doc = Document()

    # Título 24pt centrado
    p = doc.add_paragraph()
    run = p.add_run(form_title)
    run.bold = True
    run.font.size = Pt(24)
    run.font.color.rgb = BLACK
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Logo grande centrado
    logo_b = _get_logo_bytes_fallback()
    if logo_b:
        try:
            img_buf = BytesIO(logo_b)
            doc.add_paragraph().alignment = WD_ALIGN_PARAGRAPH.CENTER
            doc.add_picture(img_buf, width=Inches(2.8))
        except Exception:
            pass

    # Introducción 12pt
    intro_p = doc.add_paragraph(intro)
    intro_p.runs[0].font.size = Pt(12)
    intro_p.runs[0].font.color.rgb = BLACK

    # Secciones por página
    i = 1
    color_idx = 0
    for section_title, names in ALL_BY_PAGE:
        sec = doc.add_paragraph(section_title)
        rs = sec.runs[0]; rs.bold = True; rs.font.size = Pt(14); rs.font.color.rgb = BLACK

        for q in preguntas:
            if q.get("name") not in names:
                continue

            doc.add_paragraph("")
            h = doc.add_paragraph(f"{i}. {q['label']}")
            r = h.runs[0]; r.font.size = Pt(11); r.font.color.rgb = BLACK

            cond_txt = _build_cond_text(q["name"], reglas_vis)
            if cond_txt:
                cpara = doc.add_paragraph(cond_txt)
                rc = cpara.runs[0]; rc.italic = True; rc.font.size = Pt(9); rc.font.color.rgb = BLACK

            if _should_show_options(q):
                opts_str = ", ".join([str(x) for x in q.get("opciones") if str(x).strip()])
                opara = doc.add_paragraph(f"Opciones: {opts_str}")
                ro = opara.runs[0]; ro.font.size = Pt(10); ro.font.color.rgb = BLACK

            fill = fills[color_idx % len(fills)]
            border = borders[color_idx % len(borders)]
            color_idx += 1
            _add_observation_box(doc, fill, border)

            help_p = doc.add_paragraph("Agregue sus observaciones sobre la pregunta.")
            rh = help_p.runs[0]; rh.italic = True; rh.font.size = Pt(9); rh.font.color.rgb = BLACK

            i += 1

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    st.download_button(
        "📄 Descargar Word del formulario",
        data=buf,
        file_name=slugify_name(form_title) + "_formulario.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True
    )

# ---------- EXPORT PDF ----------
def export_pdf_editable_form(preguntas: List[Dict], form_title: str, intro: str, reglas_vis: List[Dict]):
    if canvas is None:
        st.error("Falta dependencia: instala `reportlab` para generar PDF.")
        return

    PAGE_W, PAGE_H = A4
    margin = 2 * cm
    max_text_w = PAGE_W - 2 * margin

    title_font, title_size = "Helvetica-Bold", 24
    intro_font, intro_size = "Helvetica", 12
    intro_line_h = 18
    sec_font, sec_size = "Helvetica-Bold", 14
    label_font, label_size = "Helvetica", 11
    cond_font, cond_size = "Helvetica-Oblique", 9
    helper_font, helper_size = "Helvetica-Oblique", 9
    opts_font, opts_size = "Helvetica", 10

    fills = [HexColor("#E6F4EA"), HexColor("#E7F0FE"), HexColor("#FDECEA")]
    borders = [HexColor("#1E8E3E"), HexColor("#1A73E8"), HexColor("#D93025")]

    field_h = 80
    line_h = 14
    y = PAGE_H - margin

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(form_title)

    # Portada
    logo_b = _get_logo_bytes_fallback()
    if logo_b:
        try:
            img = ImageReader(BytesIO(logo_b))
            logo_w, logo_h = 160, 115
            c.drawImage(img, (PAGE_W - logo_w) / 2, y - logo_h, width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask='auto')
            y -= (logo_h + 24)
        except Exception:
            pass

    c.setFillColor(black)
    title_lines = _wrap_text_lines(form_title, title_font, title_size, max_text_w) or [form_title]
    c.setFont(title_font, title_size)
    for tl in title_lines:
        c.drawCentredString(PAGE_W / 2, y, tl)
        y -= 26

    c.setFont(intro_font, intro_size)
    intro_lines = _wrap_text_lines(intro, intro_font, intro_size, max_text_w)
    for line in intro_lines:
        if y < margin + 80:
            c.showPage(); y = PAGE_H - margin
            c.setFillColor(black); c.setFont(intro_font, intro_size)
        c.drawString(margin, y, line)
        y -= intro_line_h

    # Páginas/secciones
    def ensure_space(need, section_title=None):
        nonlocal y
        if y - need < margin:
            c.showPage()
            y = PAGE_H - margin
            c.setFillColor(black)
            if section_title:
                c.setFont(sec_font, sec_size)
                c.drawString(margin, y, section_title)
                y -= (line_h + 6)
                c.setFont(label_font, label_size)

    c.showPage()
    y = PAGE_H - margin
    c.setFillColor(black)

    i = 1
    color_idx = 0
    for section_title, names in ALL_BY_PAGE:
        c.setFont(sec_font, sec_size)
        c.drawString(margin, y, section_title)
        y -= (line_h + 6)
        c.setFont(label_font, label_size)

        for q in st.session_state.preguntas:
            if q.get("name") not in names:
                continue

            label_lines = _wrap_text_lines(f"{i}. {q['label']}", label_font, label_size, max_text_w)
            needed = line_h * len(label_lines) + field_h + 26

            cond_txt = _build_cond_text(q["name"], reglas_vis)
            cond_lines = []
            if cond_txt:
                cond_lines = _wrap_text_lines(cond_txt, cond_font, cond_size, max_text_w)
                needed += line_h * len(cond_lines)

            opts_lines = []
            if _should_show_options(q):
                opts_str = ", ".join([str(x) for x in q.get("opciones") if str(x).strip()])
                opts_lines = _wrap_text_lines(f"Opciones: {opts_str}", opts_font, opts_size, max_text_w)
                needed += line_h * len(opts_lines)

            ensure_space(needed, section_title=section_title)

            for line in label_lines:
                c.drawString(margin, y, line)
                y -= line_h

            if cond_lines:
                c.setFont(cond_font, cond_size)
                for cl in cond_lines:
                    c.drawString(margin, y, cl)
                    y -= line_h
                c.setFont(label_font, label_size)

            if opts_lines:
                c.setFont(opts_font, opts_size)
                for ol in opts_lines:
                    c.drawString(margin, y, ol)
                    y -= line_h
                c.setFont(label_font, label_size)

            fill_color = fills[color_idx % len(fills)]
            border_color = borders[color_idx % len(borders)]
            color_idx += 1
            c.setFillColor(fill_color); c.setStrokeColor(border_color)
            c.rect(margin, y - field_h, max_text_w, field_h, fill=1, stroke=1)
            c.setFillColor(black)

            c.acroForm.textfield(
                name=f"campo_obs_{i}",
                tooltip=f"Observaciones para: {q['name']}",
                x=margin, y=y - field_h,
                width=max_text_w, height=field_h,
                borderWidth=1, borderStyle='solid',
                forceBorder=True, fieldFlags=4096, value=""
            )
            c.setFont(helper_font, helper_size)
            c.drawString(margin, y - field_h - 10, "Agregue sus observaciones sobre la pregunta.")
            c.setFont(label_font, label_size)

            y -= (field_h + 26)
            i += 1

        if y < margin + 120:
            c.showPage(); y = PAGE_H - margin; c.setFillColor(black)

    c.showPage()
    c.save()
    buf.seek(0)
    st.download_button(
        "🧾 Descargar PDF editable del formulario",
        data=buf,
        file_name=slugify_name(form_title) + "_formulario_editable.pdf",
        mime="application/pdf",
        use_container_width=True
    )

# ---------- Botones ----------
st.markdown("### 📝 Exportar formulario en **Word** y **PDF editable**")
col_w, col_p = st.columns(2)

with col_w:
    if st.button("Generar Word (DOCX)"):
        export_docx_form(
            preguntas=st.session_state.preguntas,
            form_title=(f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad"),
            intro=INTRO_COMUNIDAD,
            reglas_vis=st.session_state.reglas_visibilidad
        )

with col_p:
    if st.button("Generar PDF editable"):
        export_pdf_editable_form(
            preguntas=st.session_state.preguntas,
            form_title=(f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad"),
            intro=INTRO_COMUNIDAD,
            reglas_vis=st.session_state.reglas_visibilidad
        )


