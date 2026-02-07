# -*- coding: utf-8 -*-
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 1/10) ==============================
# ===== App: Encuesta Comunidad → XLSForm Survey123 (Editor fácil: Preguntas/Choices/Glosario)
# ==========================================================================================
#
# OBJETIVO DE ESTA PARTE:
# - Configuración general de Streamlit
# - Helpers base (slugify/unique)
# - BLINDAJE de estado (evita TypeError y pantallas “sin preguntas”)
# - Seed base (si el estado está vacío) → NO debe fallar nunca
#
# CORRECCIONES CLAVE:
# ✅ choices_bank SIEMPRE dict (evita TypeError: cb["list_canton"] = ...)
# ✅ survey_bank SIEMPRE list (evita páginas vacías por corrupción del estado)
# ✅ Se llama seed_* SOLO si está vacío (no pisa cambios)
# ✅ Se garantiza existencia de list_canton y list_distrito (evita error al cargar en ArcGIS)
# ==========================================================================================

import re
import json
from io import BytesIO
from datetime import datetime

import streamlit as st
import pandas as pd

# ==========================================================================================
# 1) UI base
# ==========================================================================================
st.set_page_config(page_title="Encuesta Comunidad — XLSForm (Editor)", layout="wide")
st.title("🏘️ Encuesta Comunidad → XLSForm para ArcGIS Survey123 (Editor fácil)")

st.markdown("""
Este editor permite:
- ✏️ **Editar preguntas** (texto, orden, required, relevant, constraint, etc.)
- 🧩 **Editar choices** sin Excel (listas y opciones)
- 📘 **Editar glosario** (definiciones y asignación por página)
- 📚 **Editar Catálogo Cantón→Distrito**
- 📦 **Exportar XLSForm** compatible con Survey123
- 🧰 **Backup/Restaurar** (JSON) para no perder cambios
""")

# ==========================================================================================
# 2) Helpers base
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
    """Asegura unicidad agregando sufijo _2, _3..."""
    if base not in usados:
        return base
    i = 2
    while f"{base}_{i}" in usados:
        i += 1
    return f"{base}_{i}"

def descargar_xlsform(df_survey, df_choices, df_settings, nombre_archivo: str):
    """Genera y descarga el XLSForm (Excel) con survey/choices/settings."""
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

# ==========================================================================================
# 3) BLINDAJE DE ESTADO (ESTO EVITA TUS ERRORES)
# ==========================================================================================
# survey_bank SIEMPRE debe ser list
if "survey_bank" not in st.session_state or not isinstance(st.session_state.survey_bank, list):
    st.session_state.survey_bank = []

# choices_bank SIEMPRE debe ser dict
if "choices_bank" not in st.session_state or not isinstance(st.session_state.choices_bank, dict):
    st.session_state.choices_bank = {}

# glosario y asignaciones SIEMPRE dict/list correctos
if "glossary_definitions" not in st.session_state or not isinstance(st.session_state.glossary_definitions, dict):
    st.session_state.glossary_definitions = {}

if "glossary_by_page" not in st.session_state or not isinstance(st.session_state.glossary_by_page, dict):
    st.session_state.glossary_by_page = {}

if "glossary_order_by_page" not in st.session_state or not isinstance(st.session_state.glossary_order_by_page, dict):
    st.session_state.glossary_order_by_page = {}

# catálogo por lotes opcional (si lo usas)
if "choices_ext_rows" not in st.session_state or not isinstance(st.session_state.choices_ext_rows, list):
    st.session_state.choices_ext_rows = []

def _ensure_mandatory_choice_lists():
    """
    Evita el error ArcGIS:
      List name not in choices sheet: list_canton
    y evita tu TypeError si choices_bank se corrompe.
    """
    cb = st.session_state.choices_bank

    # Re-blindaje (por si alguna parte asignó algo malo)
    if not isinstance(cb, dict):
        cb = {}
        st.session_state.choices_bank = cb

    if "list_canton" not in cb or not isinstance(cb.get("list_canton"), list) or len(cb.get("list_canton")) == 0:
        cb["list_canton"] = [{"name": "sin_catalogo", "label": "Sin catálogo (agregar cantones en Catálogo)"}]

    if "list_distrito" not in cb or not isinstance(cb.get("list_distrito"), list) or len(cb.get("list_distrito")) == 0:
        cb["list_distrito"] = [{
            "name": "sin_catalogo",
            "label": "Sin catálogo (agregar distritos en Catálogo)",
            "canton_key": "sin_catalogo"
        }]

    st.session_state.choices_bank = cb

# ==========================================================================================
# 4) Datos de encabezado (logo / delegación) — se usa en export y preview
# ==========================================================================================
DEFAULT_LOGO_PATH = "001.png"

col_logo, col_txt = st.columns([1, 3], vertical_alignment="center")

with col_logo:
    up_logo = st.file_uploader("Logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="up_logo")
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
    delegacion = st.text_input("Nombre del lugar / Delegación", value="San Carlos Oeste", key="delegacion")
    logo_media_name = st.text_input(
        "Nombre de archivo para `media::image`",
        value=st.session_state.get("_logo_name", "001.png"),
        help="Debe coincidir con el archivo dentro de la carpeta `media/` del proyecto Survey123 (Connect).",
        key="logo_media_name"
    )

form_title = f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad"
st.markdown(f"### {form_title}")

# ==========================================================================================
# 5) SEED (base) — SOLO si está vacío
# ==========================================================================================
INTRO_COMUNIDAD_EXACTA = (
    "Con el fin de hacer más segura nuestra comunidad, deseamos concentrarnos en los \n"
    "problemas de seguridad más importantes. Queremos trabajar en conjunto con el gobierno \n"
    "local, otras instituciones y la comunidad para reducir los delitos y riesgos que afectan a las \n"
    "personas. \n"
    "Es importante recordarle que la información que usted nos proporcione es confidencial y se \n"
    "utilizará únicamente para mejorar la seguridad en nuestra área."
)

def seed_choices_bank_if_empty(form_title: str, logo_media_name: str):
    """
    Inicializa choices_bank con listas mínimas.
    IMPORTANTE: No pisa si ya existe contenido.
    """
    cb = st.session_state.choices_bank
    if cb and isinstance(cb, dict) and len(cb.keys()) > 0:
        _ensure_mandatory_choice_lists()
        return

    cb = {}

    # yes/no
    cb["yesno"] = [{"name": slugify_name("Sí"), "label": "Sí"}, {"name": slugify_name("No"), "label": "No"}]

    # Ejemplos base (las demás listas completas siguen en tus otras partes)
    cb["genero"] = [{"name": slugify_name(x), "label": x} for x in ["Femenino", "Masculino", "Persona No Binaria", "Prefiero no decir"]]
    cb["escolaridad"] = [{"name": slugify_name(x), "label": x} for x in [
        "Ninguna","Primaria incompleta","Primaria completa","Secundaria incompleta","Secundaria completa",
        "Técnico","Universitaria incompleta","Universitaria completa"
    ]]
    cb["relacion_zona"] = [{"name": slugify_name(x), "label": x} for x in ["Vivo en la zona","Trabajo en la zona","Visito la zona","Estudio en la zona"]]
    cb["seguridad_5"] = [{"name": slugify_name(x), "label": x} for x in ["Muy inseguro","Inseguro","Ni seguro ni inseguro","Seguro","Muy seguro"]]
    cb["escala_1_10"] = [{"name": str(i), "label": str(i)} for i in range(1, 11)]

    # Cantón/Distrito mínimos (para no romper ArcGIS)
    cb["list_canton"] = [{"name": "sin_catalogo", "label": "Sin catálogo (agregar cantones en Catálogo)"}]
    cb["list_distrito"] = [{"name": "sin_catalogo", "label": "Sin catálogo (agregar distritos en Catálogo)", "canton_key": "sin_catalogo"}]

    st.session_state.choices_bank = cb
    _ensure_mandatory_choice_lists()

def seed_survey_bank_if_empty(form_title: str, logo_media_name: str):
    """
    Inicializa survey_bank con un esqueleto mínimo (P1..P8) para que NUNCA queden páginas vacías.
    IMPORTANTE: No pisa si ya existe contenido.
    """
    bank = st.session_state.survey_bank
    if isinstance(bank, list) and len(bank) > 0:
        return

    # Esqueleto mínimo con páginas para que el editor no quede en blanco.
    # (Tus preguntas completas se agregan con tus partes de seed extendido).
    bank = [
        {"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"},
        {"type": "note", "name": "p1_logo", "label": form_title, "media::image": logo_media_name, "bind::esri:fieldType": "null"},
        {"type": "note", "name": "p1_texto", "label": INTRO_COMUNIDAD_EXACTA, "bind::esri:fieldType": "null"},
        {"type": "end_group", "name": "p1_end"},

        {"type": "begin_group", "name": "p5_riesgos", "label": "Riesgos", "appearance": "field-list"},
        {"type": "note", "name": "p5_intro", "label": "Sección de Riesgos (seed mínimo).", "bind::esri:fieldType": "null"},
        {"type": "end_group", "name": "p5_end"},

        {"type": "begin_group", "name": "p8_confianza_policial", "label": "Confianza Policial", "appearance": "field-list"},
        {"type": "note", "name": "p8_intro", "label": "Sección de Confianza Policial (seed mínimo).", "bind::esri:fieldType": "null"},
        {"type": "end_group", "name": "p8_end"},
    ]

    st.session_state.survey_bank = bank

# Ejecutar seed seguro (solo si vacío)
seed_choices_bank_if_empty(form_title=form_title, logo_media_name=logo_media_name)
seed_survey_bank_if_empty(form_title=form_title, logo_media_name=logo_media_name)
_ensure_mandatory_choice_lists()

# ==========================================================================================
# 6) Menú (active_tab) — el resto de tabs se implementan en Partes 2..10
# ==========================================================================================
st.markdown("---")
menu_tabs = ["Preguntas", "Páginas", "Choices", "Glosario", "Catálogo", "Exportar", "Backup"]
active_tab = st.radio("Secciones", options=menu_tabs, horizontal=True, key="main_tabs")

# ==========================================================================================
# FIN PARTE 1/10
# ==========================================================================================

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 2/10) ==============================
# ===== Seed COMPLETO (P1..P8) + Choices COMPLETOS + Glosario Base (definiciones) ==========
# ==========================================================================================
#
# OBJETIVO DE ESTA PARTE:
# ✅ Cargar el “contenido real” (tu encuesta completa) dentro del estado editable:
#    - st.session_state.survey_bank  (todas las filas del XLSForm survey)
#    - st.session_state.choices_bank (todas las listas choices)
#    - st.session_state.glossary_definitions (término → definición)
#    - st.session_state.glossary_by_page (p4/p5/p6/p7/p8 → términos)
#    - st.session_state.glossary_order_by_page (opcional)
#
# IMPORTANTE:
# - NO crea widgets. Solo define constantes y funciones + ejecuta seed si hace falta.
# - NO pisa cambios del usuario si detecta que ya existe un seed completo.
# - SOLUCIONA: páginas vacías (P5) al garantizar que el survey_bank tenga P1..P8 completos.
#
# REQUISITOS:
# - Ya pegaste la PARTE 1/10 (con: slugify_name, asegurar_nombre_unico, _ensure_mandatory_choice_lists)
# - Ya existe active_tab (menú) en Parte 1 (pero aquí no dependemos de él)
# ==========================================================================================

# ==========================================================================================
# 1) Consentimiento (misma estructura que tu código original)
# ==========================================================================================
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
# 2) Glosario base (término → definición)
# ==========================================================================================
GLOSARIO_DEFINICIONES_BASE = {
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

# Asignación por página (editable luego en la pestaña Glosario)
GLOSARIO_POR_PAGINA_BASE = {
    "p4": ["Extorsión", "Daños/vandalismo"],
    "p5": [
        "Búnkeres", "Receptación", "Contrabando", "Trata de personas", "Explotación infantil",
        "Acoso callejero", "Tráfico de personas (coyotaje)", "Estafa", "Tacha"
    ],
    "p6": [
        "Receptación", "Contrabando", "Tráfico de personas (coyotaje)", "Acoso callejero", "Estafa",
        "Tacha", "Trata de personas", "Explotación infantil", "Extorsión", "Búnkeres"
    ],
    "p7": ["Ganzúa (pata de chancho)", "Boquete", "Arrebato", "Receptación", "Extorsión"],
    "p8": ["Patrullaje", "Acciones disuasivas", "Coordinación interinstitucional", "Integridad y credibilidad policial"],
}

# ==========================================================================================
# 3) Helpers para choices_bank (sin Excel)
# ==========================================================================================
def _ensure_choice_list(cb: dict, list_name: str):
    if list_name not in cb or not isinstance(cb.get(list_name), list):
        cb[list_name] = []

def _add_choice(cb: dict, list_name: str, label: str, extra: dict | None = None):
    _ensure_choice_list(cb, list_name)
    nm = slugify_name(label)
    exists = any(str(x.get("name","")) == nm for x in cb[list_name])
    if not exists:
        row = {"name": nm, "label": label}
        if extra:
            row.update(extra)
        cb[list_name].append(row)

def _add_choice_labels(cb: dict, list_name: str, labels: list[str]):
    for lab in labels:
        _add_choice(cb, list_name, lab)

# ==========================================================================================
# 4) Seed COMPLETO de choices_bank (todas las listas de tu código original)
# ==========================================================================================
def seed_choices_bank_full_if_needed():
    cb = st.session_state.choices_bank
    if not isinstance(cb, dict):
        cb = {}
        st.session_state.choices_bank = cb

    # Señal: si existe una lista grande, asumimos seed completo ya aplicado
    if "p19_delitos_general" in cb and isinstance(cb.get("p19_delitos_general"), list) and len(cb.get("p19_delitos_general")) > 5:
        _ensure_mandatory_choice_lists()
        return

    # yes/no
    _add_choice_labels(cb, "yesno", ["Sí", "No"])

    # demográficos
    _add_choice_labels(cb, "genero", ["Femenino", "Masculino", "Persona No Binaria", "Prefiero no decir"])
    _add_choice_labels(cb, "escolaridad", [
        "Ninguna",
        "Primaria incompleta",
        "Primaria completa",
        "Secundaria incompleta",
        "Secundaria completa",
        "Técnico",
        "Universitaria incompleta",
        "Universitaria completa",
    ])
    _add_choice_labels(cb, "relacion_zona", ["Vivo en la zona", "Trabajo en la zona", "Visito la zona", "Estudio en la zona"])

    # percepción
    _add_choice_labels(cb, "seguridad_5", ["Muy inseguro", "Inseguro", "Ni seguro ni inseguro", "Seguro", "Muy seguro"])

    causas_71 = [
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
    ]
    _add_choice_labels(cb, "causas_inseguridad", causas_71)

    _add_choice_labels(cb, "escala_1_5", [
        "1 (Mucho Menos Seguro)",
        "2 (Menos Seguro)",
        "3 (Se mantiene igual)",
        "4 (Más Seguro)",
        "5 (Mucho Más Seguro)",
    ])

    _add_choice_labels(cb, "matriz_1_5_na", [
        "Muy inseguro (1)",
        "Inseguro (2)",
        "Ni seguro ni inseguro (3)",
        "Seguro (4)",
        "Muy seguro (5)",
        "No aplica",
    ])

    tipos_10 = [
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
        "Zonas con deficiencia de iluminación",
        "Otros"
    ]
    _add_choice_labels(cb, "tipo_espacio", tipos_10)

    # riesgos
    p12 = [
        "Problemas vecinales o conflictos entre vecinos",
        "Personas en situación de ocio",
        "Presencia de personas en situación de calle",
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
    ]
    _add_choice_labels(cb, "p12_prob_situacionales", p12)

    _add_choice_labels(cb, "p13_carencias_inversion", [
        "Falta de oferta educativa",
        "Falta de oferta deportiva",
        "Falta de oferta recreativa",
        "Falta de actividades culturales",
    ])

    _add_choice_labels(cb, "p14_consumo_drogas_donde", ["Área privada", "Área pública", "No se observa consumo"])
    _add_choice_labels(cb, "p15_def_infra_vial", ["Calles en mal estado", "Falta de señalización de tránsito", "Carencia o inexistencia de aceras"])
    _add_choice_labels(cb, "p16_bunkeres_espacios", ["Casa de habitación (Espacio Cerrado)", "Edificación abandonada", "Lote baldío", "Otro"])
    _add_choice_labels(cb, "p17_transporte_afect", ["Informal (taxis piratas)", "Plataformas (digitales)"])
    _add_choice_labels(cb, "p18_presencia_policial", ["Falta de presencia policial", "Presencia policial insuficiente", "Presencia policial solo en ciertos horarios", "No observa presencia policial"])

    # delitos
    _add_choice_labels(cb, "p19_delitos_general", [
        "Disturbios en vía pública. (Riñas o Agresión)",
        "Daños a la propiedad. (Destruir, inutilizar o desaparecer).",
        "Extorsión (intimidar o amenazar a otras personas con fines de lucro).",
        "Hurto. (sustracción de artículos mediante el descuido).",
        "Compra o venta de bienes de presunta procedencia ilícita (receptación)",
        "Contrabando (licor, cigarrillos, medicinas, ropa, calzado, etc.)",
        "Maltrato animal",
        "Tráfico de personas (coyotaje)",
        "Otro"
    ])

    _add_choice_labels(cb, "p20_bunker_percepcion", [
        "En espacios cerrados (casas, edificaciones u otros inmuebles)",
        "En vía pública",
        "De forma ocasional o móvil (sin punto fijo)",
        "No se percibe consumo o venta",
        "Otro"
    ])

    _add_choice_labels(cb, "p21_vida", ["Homicidios", "Heridos (lesiones dolosas)", "Femicidio"])
    _add_choice_labels(cb, "p22_sexuales", ["Abuso sexual", "Acoso sexual", "Violación", "Acoso Callejero"])
    _add_choice_labels(cb, "p23_asaltos", ["Asalto a personas", "Asalto a comercio", "Asalto a vivienda", "Asalto a transporte público"])
    _add_choice_labels(cb, "p24_estafas", ["Billetes falsos", "Documentos falsos", "Estafa (Oro)", "Lotería falsos", "Estafas informáticas", "Estafa telefónica", "Estafa con tarjetas"])
    _add_choice_labels(cb, "p25_robo_fuerza", [
        "Tacha a comercio", "Tacha a edificaciones", "Tacha a vivienda", "Tacha de vehículos",
        "Robo de ganado (destace de ganado)", "Robo de bienes agrícolas", "Robo de cultivo",
        "Robo de vehículos", "Robo de cable", "Robo de combustible",
    ])
    _add_choice_labels(cb, "p26_abandono", ["Abandono de adulto mayor", "Abandono de menor de edad", "Abandono de incapaz"])
    _add_choice_labels(cb, "p27_explotacion_infantil", ["Sexual", "Laboral"])
    _add_choice_labels(cb, "p28_ambientales", ["Caza ilegal", "Pesca ilegal", "Tala ilegal", "Minería ilegal"])
    _add_choice_labels(cb, "p29_trata", ["Con fines laborales", "Con fines sexuales"])

    # victimización
    _add_choice_labels(cb, "p30_vif", ["Sí", "No"])
    _add_choice_labels(cb, "p301_tipos_vif", [
        "Violencia psicológica (gritos, amenazas, humillaciones, maltratos, entre otros)",
        "Violencia física (agresiones físicas, empujones, golpes, entre otros)",
        "Violencia vicaria (uso de hijas, hijos u otras personas para causar daño emocional)",
        "Violencia patrimonial (destrucción, retención o control de bienes, documentos o dinero)",
        "Violencia sexual (actos de carácter sexual sin consentimiento)"
    ])
    _add_choice_labels(cb, "p302_medidas", ["Sí", "No", "No recuerda"])
    _add_choice_labels(cb, "p303_valoracion_fp", ["Excelente", "Bueno", "Regular", "Malo", "Muy malo"])
    _add_choice_labels(cb, "p31_delito_12m", ["NO", "Sí, y denuncié", "Sí, pero no denuncié."])

    _add_choice_labels(cb, "p311_situaciones", [
        "A. Robo y Asalto (Violencia y Fuerza) — Asalto a mano armada (amenaza con arma o uso de violencia) en la calle o espacio público.",
        "A. Robo y Asalto (Violencia y Fuerza) — Asalto en el transporte público (bus, taxi, metro, etc.).",
        "A. Robo y Asalto (Violencia y Fuerza) — Asalto o robo de su vehículo (coche, motocicleta, etc.).",
        "A. Robo y Asalto (Violencia y Fuerza) — Robo de accesorios o partes de su vehículo (espejos, llantas, radio).",
        "A. Robo y Asalto (Violencia y Fuerza) — Robo o intento de robo con fuerza a su vivienda (ej. forzar una puerta o ventana).",
        "A. Robo y Asalto (Violencia y Fuerza) — Robo o intento de robo con fuerza a su comercio o negocio.",
        "B. Hurto y Daños (Sin Violencia Directa) — Hurto de su cartera, bolso o celular (sin que se diera cuenta, por descuido).",
        "B. Hurto y Daños (Sin Violencia Directa) — Daños a su propiedad (ej. grafitis, rotura de cristales, destrucción de cercas).",
        "B. Hurto y Daños (Sin Violencia Directa) — Receptación (Alguien en su hogar compró o recibió un artículo que luego supo que era robado).",
        "A. Robo y Asalto (Violencia y Fuerza) — Pérdida de artículos (celular, bicicleta, etc.) por descuido.",
        "C. Fraude y Engaño (Estafas) — Estafa telefónica (ej. llamadas para pedir dinero o datos personales).",
        "C. Fraude y Engaño (Estafas) — Estafa o fraude informático (ej. a través de internet, redes sociales o correo electrónico).",
        "C. Fraude y Engaño (Estafas) — Fraude con tarjetas bancarias (clonación o uso no autorizado).",
        "C. Fraude y Engaño (Estafas) — Ser víctima de billetes o documentos falsos.",
        "D. Otros Delitos y Problemas Personales — Extorsión (intimidación o amenaza para obtener dinero u otro beneficio).",
        "D. Otros Delitos y Problemas Personales — Maltrato animal (si usted o alguien de su hogar fue testigo o su mascota fue la víctima).",
        "D. Otros Delitos y Problemas Personales — Acoso o intimidación sexual en un espacio público",
        "D. Otros Delitos y Problemas Personales — Algún tipo de delito sexual (abuso, violación).",
        "D. Otros Delitos y Problemas Personales — Lesiones personales (haber sido herido en una riña o agresión).",
        "D. Otros Delitos y Problemas Personales — Otro"
    ])

    _add_choice_labels(cb, "p312_motivos_no_denuncia", [
        "Distancia (falta de oficinas para recepción de denuncias).",
        "Miedo a represalias.",
        "Falta de respuesta oportuna.",
        "He realizado denuncias y no ha pasado nada.",
        "Complejidad al colocar la denuncia.",
        "Desconocimiento de dónde colocar la denuncia.",
        "El Policía me dijo que era mejor no denunciar.",
        "Falta de tiempo para colocar la denuncia."
    ])

    _add_choice_labels(cb, "p313_horario", [
        "00:00 - 02:59 a. m.",
        "03:00 - 05:59 a. m.",
        "06:00 - 08:59 a. m.",
        "09:00 - 11:59 a. m.",
        "12:00 - 14:59 p. m.",
        "15:00 - 17:59 p. m.",
        "18:00 - 20:59 p. m.",
        "21:00 - 23:59 p. m.",
        "DESCONOCIDO"
    ])

    _add_choice_labels(cb, "p314_modo", [
        "Arma blanca (cuchillo, machete, tijeras).",
        "Arma de fuego.",
        "Amenazas",
        "Arrebato",
        "Boquete",
        "Ganzúa (pata de chancho)",
        "Engaño",
        "Escalamiento",
        "Otro",
        "No sé."
    ])

    # página 8 confianza
    _add_choice_labels(cb, "p32_identifica_policias", ["Sí", "No"])
    _add_choice_labels(cb, "p321_interacciones", [
        "Solicitud de ayuda o auxilio.",
        "Atención relacionada con una denuncia.",
        "Atención cordial o preventiva durante un patrullaje.",
        "Fui abordado o registrado para identificación.",
        "Fui objeto de una infracción o conflicto.",
        "Evento preventivos (Cívico policial, Reunión Comunitaria)",
        "Otra (especifique)"
    ])
    _add_choice_labels(cb, "escala_1_10", [str(i) for i in range(1, 11)])
    _add_choice_labels(cb, "p38_frecuencia", ["Todos los días", "Varias veces por semana", "Una vez por semana", "Casi nunca", "Nunca"])
    _add_choice_labels(cb, "p39_si_no_aveces", ["Sí", "No", "A veces"])
    _add_choice_labels(cb, "p41_opciones", ["Sí", "No", "No estoy seguro(a)"])
    _add_choice_labels(cb, "p43_acciones_fp", [
        "Mayor presencia policial y patrullaje",
        "Acciones disuasivas en puntos conflictivos",
        "Acciones contra consumo y venta de drogas",
        "Mejorar el servicio policial a la comunidad",
        "Acercamiento comunitario y comercial",
        "Actividades de prevención y educación",
        "Coordinación interinstitucional",
        "Integridad y credibilidad policial",
        "Otro",
        "No indica"
    ])
    _add_choice_labels(cb, "p44_acciones_muni", [
        "Mantenimiento e iluminación del espacio público",
        "Limpieza y ordenamiento urbano",
        "Instalación de cámaras y seguridad municipal",
        "Control del comercio informal y transporte",
        "Creación y mejoramiento de espacios públicos",
        "Desarrollo social y generación de empleo",
        "Coordinación interinstitucional",
        "Acercamiento municipal a comercio y comunidad",
        "Otro",
        "No indica"
    ])
    _add_choice_labels(cb, "p45_info_delito", ["Sí", "No"])

    st.session_state.choices_bank = cb
    _ensure_mandatory_choice_lists()

# ==========================================================================================
# 5) Seed COMPLETO de glosario (definiciones + asignación por página)
# ==========================================================================================
def seed_glossary_full_if_needed():
    if not isinstance(st.session_state.glossary_definitions, dict):
        st.session_state.glossary_definitions = {}
    if not isinstance(st.session_state.glossary_by_page, dict):
        st.session_state.glossary_by_page = {}
    if not isinstance(st.session_state.glossary_order_by_page, dict):
        st.session_state.glossary_order_by_page = {}

    # Definiciones: solo llenar si está vacío (o si faltan claves base)
    defs = st.session_state.glossary_definitions
    if len(defs.keys()) == 0:
        defs.update(GLOSARIO_DEFINICIONES_BASE)
    else:
        for k, v in GLOSARIO_DEFINICIONES_BASE.items():
            if k not in defs:
                defs[k] = v
    st.session_state.glossary_definitions = defs

    # Asignación por página: solo si no existe
    gbp = st.session_state.glossary_by_page
    for pid, terms in GLOSARIO_POR_PAGINA_BASE.items():
        if pid not in gbp or not isinstance(gbp.get(pid), list) or len(gbp.get(pid)) == 0:
            gbp[pid] = list(terms)
        else:
            # asegurar que existan (sin duplicar)
            for t in terms:
                if t not in gbp[pid]:
                    gbp[pid].append(t)
    st.session_state.glossary_by_page = gbp

# ==========================================================================================
# 6) Seed COMPLETO de survey_bank (P1..P8) — con tu lógica original
# ==========================================================================================
def _row_note(name: str, label: str, relevant: str = "", media_image: str = "") -> dict:
    r = {"type": "note", "name": name, "label": label, "bind::esri:fieldType": "null"}
    if relevant:
        r["relevant"] = relevant
    if media_image:
        r["media::image"] = media_image
    return r

def seed_survey_bank_full_if_needed(form_title: str, logo_media_name: str):
    bank = st.session_state.survey_bank
    if not isinstance(bank, list):
        bank = []
        st.session_state.survey_bank = bank

    # Señal de seed completo
    if any(str(r.get("name","")) == "acepta_participar" for r in bank):
        return

    v_si = slugify_name("Sí")
    v_no = slugify_name("No")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    survey_rows: list[dict] = []

    # ===================== P1 =====================
    survey_rows.append({"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"})
    survey_rows.append(_row_note("p1_logo", form_title, media_image=logo_media_name))
    survey_rows.append(_row_note("p1_texto", INTRO_COMUNIDAD_EXACTA))
    survey_rows.append({"type": "end_group", "name": "p1_end"})

    # ===================== P2 =====================
    survey_rows.append({"type": "begin_group", "name": "p2_consent", "label": "Consentimiento Informado", "appearance": "field-list"})
    survey_rows.append(_row_note("p2_titulo", CONSENT_TITLE))
    for i, p in enumerate(CONSENT_PARRAFOS, start=1):
        survey_rows.append(_row_note(f"p2_p_{i}", p))
    for j, b in enumerate(CONSENT_BULLETS, start=1):
        survey_rows.append(_row_note(f"p2_b_{j}", f"• {b}"))
    for k, c in enumerate(CONSENT_CIERRE, start=1):
        survey_rows.append(_row_note(f"p2_c_{k}", c))
    survey_rows.append({
        "type": "select_one yesno",
        "name": "acepta_participar",
        "label": "¿Acepta participar en esta encuesta?",
        "required": "yes",
        "appearance": "minimal"
    })
    survey_rows.append({"type": "end_group", "name": "p2_end"})
    survey_rows.append({
        "type": "end",
        "name": "fin_por_no",
        "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.",
        "relevant": f"${{acepta_participar}}='{v_no}'"
    })

    # ===================== P3 =====================
    survey_rows.append({"type": "begin_group", "name": "p3_datos_demograficos", "label": "Datos demográficos", "appearance": "field-list", "relevant": rel_si})

    survey_rows.append({
        "type": "select_one list_canton",
        "name": "canton",
        "label": "1. Cantón:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_distrito = f"({rel_si}) and string-length(${{canton}}) > 0"
    survey_rows.append({
        "type": "select_one list_distrito",
        "name": "distrito",
        "label": "2. Distrito:",
        "required": "yes",
        "appearance": "minimal",
        "choice_filter": "canton_key=${canton}",
        "relevant": rel_distrito
    })

    survey_rows.append({
        "type": "integer",
        "name": "edad_anos",
        "label": "3. Edad:",
        "required": "yes",
        "constraint": ". >= 18 and . <= 120",
        "constraint_message": "Debe ser un número entre 18 y 120.",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one genero",
        "name": "genero",
        "label": "4. ¿Con cuál de estas opciones se identifica?",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one escolaridad",
        "name": "escolaridad",
        "label": "5. Escolaridad:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one relacion_zona",
        "name": "relacion_zona",
        "label": "6. ¿Cuál es su relación con la zona?",
        "required": "yes",
        "relevant": rel_si
    })
    survey_rows.append({"type": "end_group", "name": "p3_end"})

    # ===================== P4 =====================
    survey_rows.append({"type": "begin_group", "name": "p4_percepcion_distrito", "label": "Percepción ciudadana de seguridad en el distrito", "appearance": "field-list", "relevant": rel_si})
    survey_rows.append({
        "type": "select_one seguridad_5",
        "name": "p7_seguridad_distrito",
        "label": "7. ¿Qué tan seguro percibe usted el distrito donde reside o transita?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_71 = (
        f"({rel_si}) and ("
        f"${{p7_seguridad_distrito}}='{slugify_name('Muy inseguro')}' or "
        f"${{p7_seguridad_distrito}}='{slugify_name('Inseguro')}'"
        f")"
    )
    survey_rows.append({
        "type": "select_multiple causas_inseguridad",
        "name": "p71_causas_inseguridad",
        "label": "7.1. Indique por qué considera el distrito inseguro (Marque todas las situaciones que usted percibe que ocurren con mayor frecuencia en su comunidad):",
        "required": "yes",
        "relevant": rel_71
    })
    survey_rows.append(_row_note("p71_no_denuncia", "Esta pregunta recoge percepción general y no constituye denuncia.", relevant=rel_71))
    survey_rows.append({
        "type": "text",
        "name": "p71_otro_detalle",
        "label": "Otro problema que considere importante (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_71}) and selected(${{p71_causas_inseguridad}}, '{slugify_name('Otro problema que considere importante')}')"
    })

    survey_rows.append({
        "type": "select_one escala_1_5",
        "name": "p8_comparacion_anno",
        "label": "8. ¿Cómo se percibe la seguridad en este distrito este año en comparación con el año anterior?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })
    rel_81 = f"({rel_si}) and string-length(${{p8_comparacion_anno}}) > 0"
    survey_rows.append({
        "type": "text",
        "name": "p81_indique_por_que",
        "label": "8.1. Indique por qué:",
        "required": "yes",
        "appearance": "multiline",
        "relevant": rel_81
    })

    survey_rows.append(_row_note("p9_instr", "9. Indique qué tan seguros percibe, en términos de seguridad, en los siguientes espacios de su Distrito:", relevant=rel_si))

    matriz_filas = [
        ("p9_discotecas", "Discotecas, bares, sitios de entretenimiento"),
        ("p9_espacios_recreativos", "Espacios recreativos (parques, play, plaza de deportes)"),
        ("p9_residencia", "Lugar de residencia (casa de habitación)"),
        ("p9_paradas", "Paradas y/o estaciones de buses, taxis, trenes"),
        ("p9_puentes", "Puentes peatonales"),
        ("p9_transporte", "Transporte público"),
        ("p9_bancaria", "Zona bancaria"),
        ("p9_comercio", "Zona de comercio"),
        ("p9_zonas_residenciales", "Zonas residenciales (calles y barrios, distinto a su casa)"),
        ("p9_zonas_francas", "Zonas francas"),
        ("p9_turisticos", "Lugares de interés turístico"),
        ("p9_centros_educativos", "Centros educativos"),
        ("p9_iluminacion", "Zonas con deficiencia de iluminación"),
    ]
    for name, label in matriz_filas:
        survey_rows.append({
            "type": "select_one matriz_1_5_na",
            "name": name,
            "label": label,
            "required": "yes",
            "appearance": "minimal",
            "relevant": rel_si
        })

    survey_rows.append({
        "type": "select_one tipo_espacio",
        "name": "p10_tipo_espacio_mas_inseguro",
        "label": "10. Según su percepción, ¿cuál de los siguientes tipos de espacios del distrito considera más inseguro?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })
    survey_rows.append({
        "type": "text",
        "name": "p10_otros_detalle",
        "label": "Otros (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and (${{p10_tipo_espacio_mas_inseguro}}='{slugify_name('Otros')}')"
    })
    survey_rows.append({
        "type": "text",
        "name": "p11_por_que_inseguro_tipo_espacio",
        "label": "11. Según su percepción, describa brevemente por qué considera inseguro el tipo de espacio seleccionado en la pregunta anterior.",
        "required": "no",
        "appearance": "multiline",
        "relevant": rel_si
    })
    survey_rows.append({"type": "end_group", "name": "p4_end"})

    # ===================== P5 =====================
    survey_rows.append({"type": "begin_group", "name": "p5_riesgos", "label": "III. RIESGOS, DELITOS, VICTIMIZACIÓN Y EVALUACIÓN POLICIAL", "appearance": "field-list", "relevant": rel_si})
    survey_rows.append(_row_note("p5_subtitulo", "Riesgos sociales y situacionales en el distrito", relevant=rel_si))
    survey_rows.append(_row_note("p5_intro", "A continuación, se presentará una lista de problemáticas que se catalogan como factores situacionales, con la finalidad de que seleccione aquellos que considere que ocurren en su distrito.", relevant=rel_si))

    survey_rows.append({
        "type": "select_multiple p12_prob_situacionales",
        "name": "p12_problematicas_distrito",
        "label": "12. Según su percepción u observación, seleccione las problemáticas que afectan su distrito:",
        "required": "yes",
        "relevant": rel_si
    })
    survey_rows.append({
        "type": "text",
        "name": "p12_otro_detalle",
        "label": "Otro problema que considere importante:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p12_problematicas_distrito}}, '{slugify_name('Otro problema que considere importante')}')"
    })

    survey_rows.append({
        "type": "select_multiple p13_carencias_inversion",
        "name": "p13_carencias_inversion_social",
        "label": "13. En relación con la inversión social en su distrito, indique cuáles de las siguientes carencias identifica:",
        "required": "yes",
        "relevant": rel_si
    })

    n_no_obs = slugify_name("No se observa consumo")
    n_priv = slugify_name("Área privada")
    n_pub = slugify_name("Área pública")
    constraint_p14 = f"not(selected(., '{n_no_obs}') and (selected(., '{n_priv}') or selected(., '{n_pub}')))"
    survey_rows.append({
        "type": "select_multiple p14_consumo_drogas_donde",
        "name": "p14_donde_consumo_drogas",
        "label": "14. Según su percepción u observación, indique dónde se presenta consumo de drogas en el distrito:",
        "required": "yes",
        "constraint": constraint_p14,
        "constraint_message": "Si selecciona “No se observa consumo”, no puede seleccionar “Área privada” ni “Área pública”.",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p15_def_infra_vial",
        "name": "p15_deficiencias_infra_vial",
        "label": "15. Indique las principales deficiencias de infraestructura vial que afectan su distrito:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p16_bunkeres_espacios",
        "name": "p16_bunkeres_espacios",
        "label": "16. Según su percepción u observación, indique en qué tipo de espacios se identifica la existencia de puntos de venta de drogas (búnkeres) en el distrito:",
        "required": "yes",
        "relevant": rel_si
    })
    survey_rows.append({
        "type": "text",
        "name": "p16_otro_detalle",
        "label": "Otro:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p16_bunkeres_espacios}}, '{slugify_name('Otro')}')"
    })

    survey_rows.append({
        "type": "select_multiple p17_transporte_afect",
        "name": "p17_transporte_afectacion",
        "label": "17. En relación con el transporte en su distrito, indique cuáles situaciones representan una afectación:",
        "required": "yes",
        "relevant": rel_si
    })

    n_no_pres = slugify_name("No observa presencia policial")
    n_falta = slugify_name("Falta de presencia policial")
    n_insuf = slugify_name("Presencia policial insuficiente")
    n_hor = slugify_name("Presencia policial solo en ciertos horarios")
    constraint_p18 = f"not(selected(., '{n_no_pres}') and (selected(., '{n_falta}') or selected(., '{n_insuf}') or selected(., '{n_hor}')))"
    survey_rows.append({
        "type": "select_multiple p18_presencia_policial",
        "name": "p18_presencia_policial",
        "label": "18. En relación con la presencia policial en su distrito, indique cuál de las siguientes situaciones identifica:",
        "required": "yes",
        "constraint": constraint_p18,
        "constraint_message": "Si selecciona “No observa presencia policial”, no seleccione otras opciones simultáneamente.",
        "relevant": rel_si
    })
    survey_rows.append({"type": "end_group", "name": "p5_end"})

    # ===================== P6 =====================
    survey_rows.append({"type": "begin_group", "name": "p6_delitos", "label": "Delitos", "appearance": "field-list", "relevant": rel_si})
    survey_rows.append(_row_note(
        "p6_intro",
        "A continuación, se presentará una lista de delitos y situaciones delictivas para que seleccione aquellos que, según su percepción u observación, considera que se presentan en su comunidad. Esta información no constituye denuncia formal ni confirmación de hechos delictivos.",
        relevant=rel_si
    ))
    survey_rows.append({
        "type": "select_multiple p19_delitos_general",
        "name": "p19_delitos_general",
        "label": "19. Selección múltiple de los siguientes delitos:",
        "required": "yes",
        "relevant": rel_si
    })
    survey_rows.append({
        "type": "text",
        "name": "p19_otro_detalle",
        "label": "Otro:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p19_delitos_general}}, '{slugify_name('Otro')}')"
    })

    n20_no_percibe = slugify_name("No se percibe consumo o venta")
    n20_cerrado = slugify_name("En espacios cerrados (casas, edificaciones u otros inmuebles)")
    n20_via = slugify_name("En vía pública")
    n20_movil = slugify_name("De forma ocasional o móvil (sin punto fijo)")
    n20_otro = slugify_name("Otro")
    constraint_p20 = f"not(selected(., '{n20_no_percibe}') and (selected(., '{n20_cerrado}') or selected(., '{n20_via}') or selected(., '{n20_movil}') or selected(., '{n20_otro}')))"
    survey_rows.append({
        "type": "select_multiple p20_bunker_percepcion",
        "name": "p20_bunker_percepcion",
        "label": "20. Percepción de consumo o venta de drogas en el entorno (Bunker)",
        "required": "yes",
        "constraint": constraint_p20,
        "constraint_message": "Si selecciona “No se percibe consumo o venta”, no seleccione otras opciones simultáneamente.",
        "relevant": rel_si
    })
    survey_rows.append({
        "type": "text",
        "name": "p20_otro_detalle",
        "label": "Otro:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p20_bunker_percepcion}}, '{slugify_name('Otro')}')"
    })

    for t, nm, lab in [
        ("select_multiple p21_vida", "p21_delitos_vida", "21. Delitos contra la vida"),
        ("select_multiple p22_sexuales", "p22_delitos_sexuales", "22. Delitos sexuales"),
        ("select_multiple p23_asaltos", "p23_asaltos_percibidos", "23. Asaltos percibidos"),
        ("select_multiple p24_estafas", "p24_estafas_percibidas", "24. Estafas percibidas"),
        ("select_multiple p25_robo_fuerza", "p25_robo_percibidos", "25. Robo percibidos (Sustracción de artículos mediante la utilización de la fuerza)"),
        ("select_multiple p26_abandono", "p26_abandono_personas", "26. Abandono de personas"),
        ("select_multiple p27_explotacion_infantil", "p27_explotacion_infantil", "27. Explotación infantil"),
        ("select_multiple p28_ambientales", "p28_delitos_ambientales", "28. Delitos ambientales percibidos"),
        ("select_multiple p29_trata", "p29_trata_personas", "29. Trata de personas"),
    ]:
        survey_rows.append({"type": t, "name": nm, "label": lab, "required": "yes", "relevant": rel_si})

    survey_rows.append({"type": "end_group", "name": "p6_end"})

    # ===================== P7 =====================
    survey_rows.append({"type": "begin_group", "name": "p7_victimizacion", "label": "Victimización", "appearance": "field-list", "relevant": rel_si})
    survey_rows.append(_row_note(
        "p7_intro",
        "A continuación, se presentará una lista de situaciones para que indique si usted o algún miembro de su hogar ha sido afectado por alguna de ellas en su distrito durante el último año.",
        relevant=rel_si
    ))

    survey_rows.append({
        "type": "select_one p30_vif",
        "name": "p30_vif",
        "label": "30. Durante el último año, ¿usted o algún miembro de su hogar ha sido afectado por alguna situación de violencia intrafamiliar (violencia doméstica)?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })
    rel_30_si = f"({rel_si}) and (${{p30_vif}}='{slugify_name('Sí')}')"
    survey_rows.append({"type": "select_multiple p301_tipos_vif", "name": "p301_tipos_vif", "label": "30.1. ¿Qué tipo(s) de violencia intrafamiliar (violencia doméstica) se presentaron?", "required": "yes", "relevant": rel_30_si})
    survey_rows.append({"type": "select_one p302_medidas", "name": "p302_medidas_proteccion", "label": "30.2. ¿En relación con la situación de violencia intrafamiliar indicada anteriormente, usted o algún miembro de su hogar solicitó medidas de protección?", "required": "yes", "appearance": "minimal", "relevant": rel_30_si})
    survey_rows.append({"type": "select_one p303_valoracion_fp", "name": "p303_valoracion_fp", "label": "30.3. ¿Cómo valora el abordaje de la Fuerza Pública ante esta situación?", "required": "yes", "appearance": "minimal", "relevant": rel_30_si})

    survey_rows.append({
        "type": "select_one p31_delito_12m",
        "name": "p31_delito_12m",
        "label": "31. Durante los últimos 12 meses, ¿usted o algún miembro de su hogar fue afectado por algún delito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    val_31_si_den = slugify_name("Sí, y denuncié")
    val_31_si_no_den = slugify_name("Sí, pero no denuncié.")
    rel_31_si = f"({rel_si}) and (${{p31_delito_12m}}='{val_31_si_den}' or ${{p31_delito_12m}}='{val_31_si_no_den}')"
    rel_31_si_no_den = f"({rel_si}) and (${{p31_delito_12m}}='{val_31_si_no_den}')"

    survey_rows.append({"type": "select_multiple p311_situaciones", "name": "p311_situaciones_afecto", "label": "31.1. ¿Cuál de las siguientes situaciones afectó a usted o a algún miembro de su hogar?", "required": "yes", "relevant": rel_31_si})
    survey_rows.append({"type": "select_multiple p312_motivos_no_denuncia", "name": "p312_motivo_no_denuncia", "label": "31.2. En caso de NO haber realizado la denuncia, indique ¿cuál fue el motivo?", "required": "yes", "relevant": rel_31_si_no_den})
    survey_rows.append({"type": "select_one p313_horario", "name": "p313_horario_hecho", "label": "31.3. ¿Tiene conocimiento sobre el horario en el cual se presentó el hecho o situación que le afectó a usted o un familiar?", "required": "yes", "appearance": "minimal", "relevant": rel_31_si})
    survey_rows.append({"type": "select_multiple p314_modo", "name": "p314_modo_ocurrio", "label": "31.4. ¿Cuál fue la forma o modo en que ocurrió la situación que afectó a usted o a algún miembro de su hogar?", "required": "yes", "relevant": rel_31_si})
    survey_rows.append({"type": "text", "name": "p314_otro_detalle", "label": "Otro (detalle):", "required": "no", "appearance": "multiline", "relevant": f"({rel_31_si}) and selected(${{p314_modo_ocurrio}}, '{slugify_name('Otro')}')"})
    survey_rows.append({"type": "end_group", "name": "p7_end"})

    # ===================== P8 =====================
    survey_rows.append({"type": "begin_group", "name": "p8_confianza_policial", "label": "Confianza Policial", "appearance": "field-list", "relevant": rel_si})
    survey_rows.append(_row_note("p8_intro", "A continuación, se presentará una lista de afirmaciones relacionadas con su percepción y confianza en el cuerpo de policía que opera en su (Distrito) barrio.", relevant=rel_si))

    survey_rows.append({"type": "select_one p32_identifica_policias", "name": "p32_identifica_policias", "label": "32. ¿Identifica usted a los policías de la Fuerza Pública de Costa Rica en su comunidad?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    rel_321 = f"({rel_si}) and (${{p32_identifica_policias}}='{slugify_name('Sí')}')"
    survey_rows.append({"type": "select_multiple p321_interacciones", "name": "p321_tipos_atencion", "label": "32.1 ¿Cuáles de los siguientes tipos de atención ha tenido?", "required": "yes", "relevant": rel_321})
    survey_rows.append({"type": "text", "name": "p321_otro_detalle", "label": "Otra (especifique):", "required": "no", "appearance": "multiline", "relevant": f"({rel_321}) and selected(${{p321_tipos_atencion}}, '{slugify_name('Otra (especifique)')}')"})

    for nm, lab in [
        ("p33_confianza_policial", "33. ¿Cuál es el nivel de confianza en la policía de la Fuerza Pública de Costa Rica de su comunidad? (1=Ninguna Confianza, 10=Mucha Confianza)"),
        ("p34_profesionalidad", "34. En una escala del 1 al 10, donde 1 es “Nada profesional” y 10 es “Muy profesional”, ¿cómo calificaría la profesionalidad de la Fuerza Pública en su distrito?"),
        ("p35_calidad_servicio", "35. En una escala del 1 al 10, donde 1 es “Muy mala” y 10 es “Muy buena”, ¿cómo califica la calidad del servicio policial en su distrito?"),
        ("p36_satisfaccion_preventivo", "36. En una escala del 1 al 10, donde 1 es “Nada satisfecho(a)” y 10 es “Muy satisfecho(a)”, ¿qué tan satisfecho(a) está con el trabajo preventivo que realiza la Fuerza Pública en su distrito?"),
        ("p37_contribucion_reduccion_crimen", "37. En una escala del 1 al 10, donde 1 es “No contribuye en nada” y 10 es “Contribuye muchísimo”, indique: ¿En qué medida considera que la presencia policial ayuda a reducir el crimen en su distrito?"),
    ]:
        survey_rows.append({"type": "select_one escala_1_10", "name": nm, "label": lab, "required": "yes", "appearance": "minimal", "relevant": rel_si})

    survey_rows.append({"type": "select_one p38_frecuencia", "name": "p38_frecuencia_presencia", "label": "38. ¿Con qué frecuencia observa presencia policial en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    survey_rows.append({"type": "select_one p39_si_no_aveces", "name": "p39_presencia_consistente", "label": "39. ¿Considera que la presencia policial es consistente a lo largo del día en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    survey_rows.append({"type": "select_one p39_si_no_aveces", "name": "p40_trato_justo", "label": "40. ¿Considera que la policía trata a las personas de manera justa e imparcial en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    survey_rows.append({"type": "select_one p41_opciones", "name": "p41_quejas_sin_temor", "label": "41. ¿Cree usted que puede expresar preocupaciones o quejas a la policía sin temor a represalias?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    survey_rows.append({"type": "select_one p39_si_no_aveces", "name": "p42_info_veraz_clara", "label": "42. ¿Considera que la policía proporciona información veraz, clara y oportuna a la comunidad?", "required": "yes", "appearance": "minimal", "relevant": rel_si})

    survey_rows.append({"type": "select_multiple p43_acciones_fp", "name": "p43_accion_fp_mejorar", "label": "43. ¿Qué actividad considera que debe realizar la Fuerza Pública para mejorar la seguridad en su comunidad?", "required": "yes", "relevant": rel_si})
    survey_rows.append({"type": "text", "name": "p43_otro_detalle", "label": "Otro (detalle):", "required": "no", "appearance": "multiline", "relevant": f"({rel_si}) and selected(${{p43_accion_fp_mejorar}}, '{slugify_name('Otro')}')"})

    survey_rows.append({"type": "select_multiple p44_acciones_muni", "name": "p44_accion_muni_mejorar", "label": "44. ¿Qué actividad considera que debe realizar la municipalidad para mejorar la seguridad en su comunidad?", "required": "yes", "relevant": rel_si})
    survey_rows.append({"type": "text", "name": "p44_otro_detalle", "label": "Otro (detalle):", "required": "no", "appearance": "multiline", "relevant": f"({rel_si}) and selected(${{p44_accion_muni_mejorar}}, '{slugify_name('Otro')}')"})

    survey_rows.append(_row_note("p8_info_adicional_titulo", "Información Adicional y Contacto Voluntario", relevant=rel_si))
    survey_rows.append({"type": "select_one p45_info_delito", "name": "p45_info_delito", "label": "45. ¿Usted tiene información de alguna persona o grupo que se dedique a realizar algún delito en su comunidad? (Recuerde, su información es confidencial.)", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    rel_451 = f"({rel_si}) and (${{p45_info_delito}}='{slugify_name('Sí')}')"
    survey_rows.append({"type": "text", "name": "p451_detalle_info", "label": "45.1. Si su respuesta es \"Sí\", describa aquellas características que pueda aportar tales como nombre de estructura o banda criminal... (nombre de personas, alias, domicilio, vehículos, etc.)", "required": "yes", "appearance": "multiline", "relevant": rel_451})
    survey_rows.append({"type": "text", "name": "p46_contacto_voluntario", "label": "46. En el siguiente espacio de forma voluntaria podrá anotar su nombre, teléfono o correo electrónico en el cual desee ser contactado y continuar colaborando de forma confidencial con Fuerza Pública.", "required": "no", "appearance": "multiline", "relevant": rel_si})
    survey_rows.append({"type": "text", "name": "p47_info_adicional", "label": "47. En el siguiente espacio podrá registrar alguna otra información que estime pertinente.", "required": "no", "appearance": "multiline", "relevant": rel_si})
    survey_rows.append(_row_note("p8_fin", "---------------------------------- Fin de la Encuesta ----------------------------------", relevant=rel_si))
    survey_rows.append({"type": "end_group", "name": "p8_end"})

    st.session_state.survey_bank = survey_rows

# ==========================================================================================
# 7) Ejecutar seed completo si hace falta
# ==========================================================================================
seed_choices_bank_full_if_needed()
seed_glossary_full_if_needed()
seed_survey_bank_full_if_needed(form_title=form_title, logo_media_name=logo_media_name)
_ensure_mandatory_choice_lists()

# ==========================================================================================
# FIN PARTE 2/10
# ==========================================================================================

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 3/10) ==============================
# ======================= Editor de Glosario (FÁCIL) + FIX “Arrebato” =====================
# ==========================================================================================
#
# OBJETIVO DE ESTA PARTE:
# ✅ Pestaña/Sección “Glosario” con edición para cualquier persona:
#    - Ver términos (chips/multiselect) por página (p4..p8)
#    - Agregar términos existentes (ya definidos) a una página
#    - Crear un término nuevo + definición (en 2 campos) y poder asignarlo
#    - Orden opcional “uno por línea” (para controlar orden de la vista previa)
# ✅ FIX PRINCIPAL (tu error actual):
#    - Cuando agregabas “Arrebato” a P5, NO se reflejaba en vista previa / orden:
#      Esto pasa cuando:
#        a) glossary_by_page se actualiza, pero
#        b) glossary_order_by_page NO se recalcula / normaliza, o
#        c) se guarda un orden que no incluye el nuevo término.
#      => Solución: normalizar SIEMPRE (merge + quitar duplicados + respetar orden si aplica).
#
# REQUISITOS:
# - Ya pegaste Parte 1/10 y Parte 2/10
# - En session_state existen:
#   glossary_definitions, glossary_by_page, glossary_order_by_page
#
# NOTA:
# - Esto NO exporta XLSForm aún (eso va en Partes posteriores).
# - Esto NO toca el banco survey; solo glosario.
# ==========================================================================================

# ==========================================================================================
# 1) Utilidades del glosario (normalización + render)
# ==========================================================================================
def _dedupe_preserve_order(seq: list[str]) -> list[str]:
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out

def normalize_glossary_for_page(page_id: str):
    """
    Normaliza:
    - glossary_by_page[page_id] => lista sin duplicados
    - glossary_order_by_page[page_id] => si existe, filtra solo términos válidos y
      agrega al final los términos nuevos que no estén en el order.
    """
    if "glossary_by_page" not in st.session_state or not isinstance(st.session_state.glossary_by_page, dict):
        st.session_state.glossary_by_page = {}
    if "glossary_order_by_page" not in st.session_state or not isinstance(st.session_state.glossary_order_by_page, dict):
        st.session_state.glossary_order_by_page = {}
    if "glossary_definitions" not in st.session_state or not isinstance(st.session_state.glossary_definitions, dict):
        st.session_state.glossary_definitions = {}

    defs = st.session_state.glossary_definitions
    gbp = st.session_state.glossary_by_page
    gop = st.session_state.glossary_order_by_page

    terms = gbp.get(page_id, [])
    if not isinstance(terms, list):
        terms = []
    terms = [t for t in terms if isinstance(t, str) and t.strip() != ""]
    # Solo dejamos términos que existan en definiciones
    terms = [t for t in terms if t in defs]
    terms = _dedupe_preserve_order(terms)
    gbp[page_id] = terms

    order = gop.get(page_id, [])
    if not isinstance(order, list):
        order = []
    order = [t for t in order if isinstance(t, str) and t.strip() != ""]
    order = [t for t in order if t in defs]           # solo términos definidos
    order = [t for t in order if t in terms]          # solo términos asignados a esta página
    # AÑADIR AL FINAL cualquier término asignado que no esté en el order (FIX “Arrebato”)
    for t in terms:
        if t not in order:
            order.append(t)
    gop[page_id] = _dedupe_preserve_order(order)

    st.session_state.glossary_by_page = gbp
    st.session_state.glossary_order_by_page = gop

def get_effective_glossary_terms(page_id: str) -> list[str]:
    """
    Retorna los términos en el orden efectivo:
    - Si hay order, usa order
    - Si no, usa by_page
    """
    normalize_glossary_for_page(page_id)
    order = st.session_state.glossary_order_by_page.get(page_id, [])
    if isinstance(order, list) and len(order) > 0:
        return list(order)
    return list(st.session_state.glossary_by_page.get(page_id, []))

def render_glossary_preview(page_id: str):
    """
    Vista previa legible del glosario de una página.
    """
    defs = st.session_state.glossary_definitions
    terms = get_effective_glossary_terms(page_id)
    if not terms:
        st.info("No hay términos asignados a esta página.")
        return

    st.markdown("### 👁️ Vista previa del glosario de esta página")
    for t in terms:
        st.markdown(f"**{t}**")
        st.write(defs.get(t, "").strip())
        st.markdown("---")

# ==========================================================================================
# 2) UI: Sección “Glosario” (solo se muestra si el usuario entra a esa sección)
# ==========================================================================================
# RECOMENDACIÓN: en tu menú/segmento principal, llama “Glosario” a este bloque.
# Para no depender del menú exacto, dejamos una variable booleana simple:
show_glossary_ui = False
try:
    # Si en tu Parte 1 ya hay un menú con 'active_tab', se usa:
    if "active_tab" in st.session_state:
        show_glossary_ui = (st.session_state.active_tab == "Glosario")
except Exception:
    show_glossary_ui = False

# Si tu Parte 1 aún no setea active_tab, puedes forzar:
# show_glossary_ui = True

if show_glossary_ui:

    st.header("📚 Glosario — editor fácil (por página)")
    st.caption("Aquí puedes agregar/quitar términos por página, crear términos nuevos con su definición y controlar el orden.")

    # Páginas disponibles para glosario:
    pages = [
        ("p4", "P4 Percepción"),
        ("p5", "P5 Riesgos"),
        ("p6", "P6 Delitos"),
        ("p7", "P7 Victimización"),
        ("p8", "P8 Confianza/Acciones"),
    ]
    page_map = {pid: label for pid, label in pages}

    colA, colB = st.columns([1, 2])
    with colA:
        page_id = st.selectbox(
            "Página",
            options=[pid for pid, _ in pages],
            format_func=lambda x: page_map.get(x, x),
            key="glossary_page_select"
        )

    # Normalizamos al entrar
    normalize_glossary_for_page(page_id)

    defs = st.session_state.glossary_definitions
    gbp = st.session_state.glossary_by_page

    with colB:
        st.markdown("#### Términos incluidos en el glosario de esta página")
        # multiselect con términos ya definidos
        all_terms_sorted = sorted(list(defs.keys()))
        selected_terms = st.multiselect(
            "Selecciona términos (puedes agregar/quitar)",
            options=all_terms_sorted,
            default=gbp.get(page_id, []),
            key=f"glossary_terms_{page_id}"
        )

    # Guardar asignación de términos
    colS1, colS2 = st.columns([1, 1])
    with colS1:
        if st.button("💾 Guardar asignación", use_container_width=True, key=f"btn_save_gloss_{page_id}"):
            st.session_state.glossary_by_page[page_id] = list(selected_terms)
            # FIX: normaliza para que el orden se actualice y se vea “Arrebato” inmediatamente
            normalize_glossary_for_page(page_id)
            st.success("Asignación guardada y normalizada (incluye orden).")

    with colS2:
        if st.button("🧹 Limpiar página", use_container_width=True, key=f"btn_clear_gloss_{page_id}"):
            st.session_state.glossary_by_page[page_id] = []
            st.session_state.glossary_order_by_page[page_id] = []
            st.success("Glosario de la página limpiado.")

    st.markdown("---")

    # Orden manual (opcional)
    st.subheader("🔀 Orden del glosario (opcional)")
    st.caption("Si quieres un orden manual, pega un término por línea. Si lo dejas vacío, se usará el orden de selección.")

    current_order = st.session_state.glossary_order_by_page.get(page_id, [])
    order_text = "\n".join(current_order) if isinstance(current_order, list) else ""

    new_order_text = st.text_area(
        "Orden (uno por línea)",
        value=order_text,
        height=120,
        key=f"glossary_order_text_{page_id}"
    )

    if st.button("✅ Aplicar orden", use_container_width=True, key=f"btn_apply_order_{page_id}"):
        lines = [ln.strip() for ln in new_order_text.splitlines() if ln.strip()]
        # Solo permitimos los que estén seleccionados y definidos
        allowed = set(st.session_state.glossary_by_page.get(page_id, []))
        lines = [t for t in lines if t in allowed and t in st.session_state.glossary_definitions]
        st.session_state.glossary_order_by_page[page_id] = lines
        # FIX: agrega al final los términos seleccionados que no estén en el order
        normalize_glossary_for_page(page_id)
        st.success("Orden aplicado (y normalizado con términos faltantes al final).")

    st.markdown("---")

    # Crear un término nuevo (rápido para cualquier persona)
    st.subheader("➕ Agregar término nuevo al glosario (con definición)")
    st.caption("Crea un término nuevo y, si quieres, lo asignas a esta página en un clic.")

    c1, c2 = st.columns([1, 2])
    with c1:
        new_term = st.text_input("Término", value="", key=f"new_gloss_term_{page_id}")
    with c2:
        new_def = st.text_area("Definición", value="", height=90, key=f"new_gloss_def_{page_id}")

    c3, c4 = st.columns([1, 1])
    with c3:
        assign_now = st.checkbox("Asignar a esta página al guardar", value=True, key=f"assign_new_term_{page_id}")
    with c4:
        if st.button("💾 Guardar término", use_container_width=True, key=f"btn_save_new_term_{page_id}"):
            term = new_term.strip()
            defin = new_def.strip()
            if not term or not defin:
                st.error("Debes escribir el término y su definición.")
            else:
                # Guardar/actualizar definición
                st.session_state.glossary_definitions[term] = defin

                # Asignar a la página si corresponde
                if assign_now:
                    if term not in st.session_state.glossary_by_page.get(page_id, []):
                        st.session_state.glossary_by_page.setdefault(page_id, []).append(term)

                # NORMALIZAR para que se vea de inmediato (FIX)
                normalize_glossary_for_page(page_id)
                st.success("Término guardado (y asignación/orden normalizados).")

    st.markdown("---")

    # Vista previa final
    render_glossary_preview(page_id)

# ==========================================================================================
# FIN PARTE 3/10
# ==========================================================================================

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 4/10) ==============================
# ================== FIX: Editor de Preguntas (survey) para P1..P8 =========================
# ==========================================================================================
#
# PROBLEMA QUE ESTÁS VIENDO:
# - En el editor, después de P5 ya “no aparecen preguntas”.
# - O te sale: “No hay preguntas en esta página…”.
#
# CAUSA TÍPICA:
# - El “mapeo” de páginas estaba hecho con nombres fijos o índices,
#   y cuando el banco/seed cambió, el editor ya no encontró el rango correcto.
#
# SOLUCIÓN (robusta):
# ✅ Detectar páginas leyendo la estructura REAL del “survey bank”:
#    - Identifica bloques begin_group/end_group que corresponden a páginas.
#    - Si no encuentra por begin_group, cae a heurística por prefijos de name.
# ✅ Así P6, P7, P8 aparecen siempre aunque muevas o agregues preguntas.
#
# REQUISITOS (ya en Partes 1-3):
# - st.session_state.survey_bank: list[dict] con filas tipo XLSForm (type/name/label/...)
# - st.session_state.active_tab (o el menú) para saber si estamos en "Preguntas"
#
# NOTA:
# - Este editor es “legible” (estilo Survey123) y también permite edición simple/avanzada.
# - No exporta XLSForm aún (eso va en Partes posteriores).
# ==========================================================================================

# ==========================================================================================
# 1) Helpers: acceso seguro a session_state
# ==========================================================================================
def _ss_get(name: str, default):
    if name not in st.session_state:
        st.session_state[name] = default
    return st.session_state[name]

def _row_get(r: dict, k: str, default=""):
    v = r.get(k, default)
    return "" if v is None else v

def _is_page_group_row(r: dict) -> bool:
    """
    Una 'página' en tu XLSForm está modelada como begin_group con appearance=field-list.
    Ejemplos en tu XLSForm original:
      - begin_group name="p4_percepcion_distrito" appearance="field-list"
      - begin_group name="p5_riesgos" appearance="field-list"
      - begin_group name="p6_delitos" appearance="field-list"
      - begin_group name="p7_victimizacion" appearance="field-list"
      - begin_group name="p8_confianza_policial" appearance="field-list"
    """
    t = str(_row_get(r, "type")).strip().lower()
    app = str(_row_get(r, "appearance")).strip().lower()
    return (t == "begin_group") and (app == "field-list")

def _is_end_group_row(r: dict) -> bool:
    return str(_row_get(r, "type")).strip().lower() == "end_group"

def _clean_label(s: str) -> str:
    return (s or "").strip()

# ==========================================================================================
# 2) Descubrir páginas (P1..P8) desde el survey_bank (robusto)
# ==========================================================================================
def discover_pages_from_survey_bank(survey_bank: list[dict]) -> list[dict]:
    """
    Retorna lista de páginas detectadas:
      [{
        "page_id": "P4",
        "title": "Percepción ciudadana de seguridad en el distrito",
        "start": idx_begin,
        "end": idx_end_inclusive,
        "group_name": "p4_percepcion_distrito"
      }, ...]
    """
    pages = []

    # A) Detectar por begin_group(field-list) + matching end_group (stack)
    stack = []
    for i, r in enumerate(survey_bank):
        if _is_page_group_row(r):
            stack.append((i, r))
        elif _is_end_group_row(r) and stack:
            begin_i, begin_r = stack.pop()
            # Cerrar solo el último begin_group (LIFO)
            group_name = _row_get(begin_r, "name")
            group_label = _clean_label(_row_get(begin_r, "label"))
            title = group_label if group_label else group_name

            # Asignación de page_id por heurística:
            # - Si el name inicia con "p4_" -> P4
            # - Si inicia con "p5_" -> P5, etc.
            pid = None
            n = str(group_name).lower()
            if n.startswith("p1_"): pid = "P1"
            elif n.startswith("p2_"): pid = "P2"
            elif n.startswith("p3_"): pid = "P3"
            elif n.startswith("p4_"): pid = "P4"
            elif n.startswith("p5_"): pid = "P5"
            elif n.startswith("p6_"): pid = "P6"
            elif n.startswith("p7_"): pid = "P7"
            elif n.startswith("p8_"): pid = "P8"

            # Si no pudimos inferir, lo dejamos como genérico
            if not pid:
                pid = f"PAGE_{len(pages)+1}"

            pages.append({
                "page_id": pid,
                "title": title,
                "start": begin_i,
                "end": i,  # inclusive
                "group_name": group_name
            })

    # B) Ordenar por aparición
    pages = sorted(pages, key=lambda x: x["start"])

    # C) Filtrar solo P1..P8 si existen, manteniendo orden
    wanted = ["P1","P2","P3","P4","P5","P6","P7","P8"]
    final = []
    seen = set()

    for w in wanted:
        for p in pages:
            if p["page_id"] == w and w not in seen:
                final.append(p)
                seen.add(w)

    # D) Si alguna falta, intentamos “fallback” por prefijo de rows (sin begin_group)
    # (por si alguien borró begin_group por accidente)
    if len(final) < 8:
        # agrupamos por prefijo pX_
        pref_map = {f"p{i}_": f"P{i}" for i in range(1, 9)}
        buckets = {f"P{i}": [] for i in range(1, 9)}
        for idx, r in enumerate(survey_bank):
            nm = str(_row_get(r, "name")).lower()
            for pref, pid in pref_map.items():
                if nm.startswith(pref):
                    buckets[pid].append(idx)
                    break
        for pid in wanted:
            if pid not in seen and buckets.get(pid):
                idxs = buckets[pid]
                final.append({
                    "page_id": pid,
                    "title": pid,
                    "start": min(idxs),
                    "end": max(idxs),
                    "group_name": ""
                })
                seen.add(pid)

        final = sorted(final, key=lambda x: x["start"])

    return final

def get_rows_for_page(survey_bank: list[dict], page_meta: dict) -> list[tuple[int, dict]]:
    """
    Retorna [(idx,row), ...] del rango de la página.
    Incluye begin_group y end_group para contexto.
    """
    a = int(page_meta["start"])
    b = int(page_meta["end"])
    out = []
    for i in range(a, b+1):
        out.append((i, survey_bank[i]))
    return out

# ==========================================================================================
# 3) UI Legible (similar Survey123) + Edición simple/avanzada
# ==========================================================================================
def _render_readable_card(idx: int, row: dict):
    """
    Render “legible” de una fila del survey:
    - Muestra label grande
    - Muestra metadata (type/name) pequeño
    """
    t = _row_get(row, "type")
    nm = _row_get(row, "name")
    lb = _row_get(row, "label")

    st.markdown(f"#### {lb or '— Sin texto —'}")
    st.caption(f"Índice: {idx}  |  Tipo: `{t}`  |  Nombre interno: `{nm}`")

def _editor_simple(row: dict, key_prefix: str) -> dict:
    """
    Editor simple:
    - Solo label y required
    - Para que cualquier persona lo entienda.
    """
    edited = dict(row)

    edited["label"] = st.text_area(
        "Texto visible (label)",
        value=_row_get(row, "label"),
        height=90,
        key=f"{key_prefix}_label"
    )

    # required: yes/no/""
    req_val = _row_get(row, "required").strip().lower()
    req_opt = "no"
    if req_val == "yes":
        req_opt = "sí"
    elif req_val == "no":
        req_opt = "no"
    else:
        req_opt = "no"

    req_pick = st.radio(
        "¿Obligatoria?",
        options=["sí", "no"],
        index=0 if req_opt == "sí" else 1,
        horizontal=True,
        key=f"{key_prefix}_required"
    )
    edited["required"] = "yes" if req_pick == "sí" else "no"

    return edited

def _editor_advanced(row: dict, key_prefix: str) -> dict:
    """
    Editor avanzado (para ti):
    - relevant, constraint, choice_filter, appearance, etc.
    """
    edited = dict(row)

    cols = ["type","name","label","required","appearance","relevant","choice_filter",
            "constraint","constraint_message","media::image","bind::esri:fieldType"]

    for c in cols:
        if c not in edited:
            edited[c] = ""

    edited["type"] = st.text_input("type", value=_row_get(row, "type"), key=f"{key_prefix}_type")
    edited["name"] = st.text_input("name", value=_row_get(row, "name"), key=f"{key_prefix}_name")
    edited["label"] = st.text_area("label", value=_row_get(row, "label"), height=90, key=f"{key_prefix}_label_adv")
    edited["required"] = st.text_input("required (yes/no)", value=_row_get(row, "required"), key=f"{key_prefix}_req_adv")
    edited["appearance"] = st.text_input("appearance", value=_row_get(row, "appearance"), key=f"{key_prefix}_app_adv")
    edited["relevant"] = st.text_area("relevant", value=_row_get(row, "relevant"), height=80, key=f"{key_prefix}_rel_adv")
    edited["choice_filter"] = st.text_input("choice_filter", value=_row_get(row, "choice_filter"), key=f"{key_prefix}_cf_adv")
    edited["constraint"] = st.text_area("constraint", value=_row_get(row, "constraint"), height=70, key=f"{key_prefix}_con_adv")
    edited["constraint_message"] = st.text_area("constraint_message", value=_row_get(row, "constraint_message"), height=70, key=f"{key_prefix}_cm_adv")
    edited["media::image"] = st.text_input("media::image", value=_row_get(row, "media::image"), key=f"{key_prefix}_img_adv")
    edited["bind::esri:fieldType"] = st.text_input("bind::esri:fieldType", value=_row_get(row, "bind::esri:fieldType"), key=f"{key_prefix}_bind_adv")

    return edited

def update_row_in_survey_bank(idx: int, new_row: dict):
    bank = _ss_get("survey_bank", [])
    if 0 <= idx < len(bank):
        bank[idx] = dict(new_row)
        st.session_state.survey_bank = bank

def delete_row_from_survey_bank(idx: int):
    bank = _ss_get("survey_bank", [])
    if 0 <= idx < len(bank):
        bank.pop(idx)
        st.session_state.survey_bank = bank

def move_row(bank: list[dict], idx: int, direction: int) -> list[dict]:
    """
    direction: -1 subir, +1 bajar
    """
    j = idx + direction
    if j < 0 or j >= len(bank):
        return bank
    bank[idx], bank[j] = bank[j], bank[idx]
    return bank

# ==========================================================================================
# 4) UI principal del editor de preguntas — “Preguntas”
# ==========================================================================================
show_questions_ui = False
try:
    if "active_tab" in st.session_state:
        show_questions_ui = (st.session_state.active_tab == "Preguntas")
except Exception:
    show_questions_ui = False

# Si tu menú aún no setea active_tab, puedes forzar para probar:
# show_questions_ui = True

if show_questions_ui:
    st.header("📝 Editor de Preguntas (survey) — vista legible + edición")
    st.caption("Selecciona una página (P1..P8). El editor detecta automáticamente el bloque real aunque cambies el orden o agregues preguntas.")

    survey_bank = _ss_get("survey_bank", [])
    if not isinstance(survey_bank, list) or len(survey_bank) == 0:
        st.error("No hay survey_bank cargado. (Debe existir desde el seed de Partes anteriores).")
    else:
        pages = discover_pages_from_survey_bank(survey_bank)
        if not pages:
            st.error("No pude detectar páginas. Revisa que existan begin_group con appearance='field-list' (o names p1_..p8_).")
        else:
            page_ids = [p["page_id"] for p in pages]
            page_labels = {p["page_id"]: p["title"] for p in pages}

            # OJO: key ÚNICO para evitar StreamlitDuplicateElementKey
            sel_pid = st.selectbox(
                "Página",
                options=page_ids,
                format_func=lambda x: f"{x} — {page_labels.get(x,'')}",
                key="page_sel_editor_v2"
            )

            page_meta = next(p for p in pages if p["page_id"] == sel_pid)
            page_rows = get_rows_for_page(survey_bank, page_meta)

            # Búsqueda
            q = st.text_input("Buscar en esta página", value="", key=f"search_{sel_pid}")
            q_low = q.strip().lower()

            filtered = []
            for idx, r in page_rows:
                txt = (_row_get(r, "label") + " " + _row_get(r, "name") + " " + _row_get(r, "type")).lower()
                if (not q_low) or (q_low in txt):
                    filtered.append((idx, r))

            if len(filtered) == 0:
                st.warning("No hay preguntas que coincidan con el filtro (o el bloque quedó vacío).")
            else:
                # Lista de elementos (para seleccionar uno)
                options = []
                opt_map = {}
                for idx, r in filtered:
                    lb = _clean_label(_row_get(r, "label"))
                    nm = _row_get(r, "name")
                    tp = _row_get(r, "type")
                    txt = f"[{idx}] {lb[:60] + ('…' if len(lb)>60 else '')}  —  ({tp})  —  {nm}"
                    options.append(txt)
                    opt_map[txt] = (idx, r)

                left, right = st.columns([1, 2])

                with left:
                    st.markdown("### 📌 Elementos en la página")
                    pick = st.selectbox(
                        "Selecciona un elemento",
                        options=options,
                        key=f"pick_row_{sel_pid}"
                    )

                    idx, row = opt_map[pick]

                    # Botones mover/eliminar (con keys únicos)
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        if st.button("⬆️ Subir", use_container_width=True, key=f"up_{sel_pid}_{idx}"):
                            bank = _ss_get("survey_bank", [])
                            st.session_state.survey_bank = move_row(bank, idx, -1)
                            st.rerun()
                    with b2:
                        if st.button("⬇️ Bajar", use_container_width=True, key=f"down_{sel_pid}_{idx}"):
                            bank = _ss_get("survey_bank", [])
                            st.session_state.survey_bank = move_row(bank, idx, +1)
                            st.rerun()
                    with b3:
                        if st.button("🗑️ Eliminar", use_container_width=True, key=f"del_{sel_pid}_{idx}"):
                            delete_row_from_survey_bank(idx)
                            st.success("Elemento eliminado.")
                            st.rerun()

                    st.markdown("---")
                    st.markdown("### ➕ Agregar pregunta rápida")
                    new_type = st.selectbox(
                        "Tipo",
                        options=[
                            "note",
                            "text",
                            "integer",
                            "select_one yesno",
                            "select_multiple yesno",
                            "select_one escala_1_10",
                        ],
                        key=f"new_type_{sel_pid}"
                    )
                    new_label = st.text_area("Texto", value="", height=80, key=f"new_label_{sel_pid}")
                    if st.button("Agregar", use_container_width=True, key=f"add_{sel_pid}"):
                        if not new_label.strip():
                            st.error("Escribe el texto de la pregunta.")
                        else:
                            bank = _ss_get("survey_bank", [])
                            # Insertar justo después del índice seleccionado
                            insert_at = idx + 1
                            # name único “auto_…”
                            base_name = slugify_name(new_label.strip())[:40]
                            if not base_name:
                                base_name = "auto"
                            used_names = set(str(_row_get(r, "name")).strip() for r in bank)
                            nm = base_name
                            k = 2
                            while nm in used_names:
                                nm = f"{base_name}_{k}"
                                k += 1

                            new_row = {
                                "type": new_type,
                                "name": nm,
                                "label": new_label.strip(),
                                "required": "no",
                                "appearance": "minimal",
                                "relevant": "",
                                "choice_filter": "",
                                "constraint": "",
                                "constraint_message": "",
                                "media::image": "",
                                "bind::esri:fieldType": "null" if new_type == "note" else ""
                            }
                            bank.insert(insert_at, new_row)
                            st.session_state.survey_bank = bank
                            st.success("Pregunta agregada.")
                            st.rerun()

                with right:
                    st.markdown("### 👁️ Vista legible (similar a Survey123)")
                    _render_readable_card(idx, row)

                    st.markdown("---")
                    st.markdown("### ✏️ Editar")
                    mode = st.radio(
                        "Modo de edición",
                        options=["Simple", "Avanzado"],
                        horizontal=True,
                        key=f"mode_{sel_pid}_{idx}"
                    )

                    key_prefix = f"edit_{sel_pid}_{idx}"
                    if mode == "Simple":
                        edited = _editor_simple(row, key_prefix=key_prefix)
                    else:
                        edited = _editor_advanced(row, key_prefix=key_prefix)

                    if st.button("💾 Guardar cambios", use_container_width=True, key=f"save_{sel_pid}_{idx}"):
                        update_row_in_survey_bank(idx, edited)
                        st.success("Cambios guardados.")
                        st.rerun()

# ==========================================================================================
# FIN PARTE 4/10
# ==========================================================================================

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 5/10) ==============================
# ================= FIX ArcGIS / Survey123: choices faltantes + errores de listas ==========
# ==========================================================================================
#
# LO QUE ARREGLA ESTA PARTE:
# ✅ Error al cargar XLSForm en Survey123:
#    - “choice list list_canton no existe”, o “list_name no encontrado”, etc.
#    - O te dice que un select_one/select_multiple usa una lista que no está en choices.
#
# ✅ Problema típico cuando editás:
#    - Cambiaste types como "select_one list_canton" / "select_multiple p19_delitos_general"
#      pero NO existe la lista en choices_rows.
#
# ✅ Solución robusta:
#    1) Escanear survey_bank y extraer TODAS las listas usadas (select_one / select_multiple).
#    2) Verificar que existan en choices_bank (choices_rows editable).
#    3) Crear automáticamente listas mínimas si faltan.
#    4) Corregir “yesno” y listas base obligatorias si se borraron.
#
# REQUISITOS (Partes previas):
# - st.session_state.survey_bank: list[dict]
# - st.session_state.choices_bank: list[dict]    (si no existe, la creamos)
# - helpers: slugify_name (de tu código original o Parte 1/10)
#
# NOTA:
# - Aquí NO generamos el XLSX todavía; solo garantizamos consistencia survey↔choices.
# - En Parte 6/10 conectamos esto con el export final.
# ==========================================================================================

import re

# ==========================================================================================
# 1) Session helpers
# ==========================================================================================
def _ss_get(name: str, default):
    if name not in st.session_state:
        st.session_state[name] = default
    return st.session_state[name]

def _row_get(r: dict, k: str, default=""):
    v = r.get(k, default)
    return "" if v is None else v

# ==========================================================================================
# 2) Detectar listas usadas en survey (select_one / select_multiple)
# ==========================================================================================
_SELECT_RE = re.compile(r"^\s*(select_one|select_multiple)\s+([A-Za-z0-9_]+)\s*$")

def extract_used_choice_lists(survey_bank: list[dict]) -> set[str]:
    """
    Busca en la columna 'type' filas que sean:
      - select_one <list_name>
      - select_multiple <list_name>
    Retorna set de list_name usados.
    """
    used = set()
    for r in survey_bank:
        t = str(_row_get(r, "type")).strip()
        m = _SELECT_RE.match(t)
        if m:
            list_name = m.group(2).strip()
            if list_name:
                used.add(list_name)
    return used

def get_existing_choice_lists(choices_bank: list[dict]) -> set[str]:
    """
    Retorna set de list_name existentes en choices_bank.
    """
    out = set()
    for r in choices_bank:
        ln = str(_row_get(r, "list_name")).strip()
        if ln:
            out.add(ln)
    return out

# ==========================================================================================
# 3) Crear listas mínimas cuando falten (fallback seguro)
# ==========================================================================================
def ensure_list_yesno(choices_bank: list[dict]):
    """
    Asegura que exista yesno con Sí/No.
    """
    lists = get_existing_choice_lists(choices_bank)
    if "yesno" not in lists:
        choices_bank.append({"list_name": "yesno", "name": slugify_name("Sí"), "label": "Sí"})
        choices_bank.append({"list_name": "yesno", "name": slugify_name("No"), "label": "No"})
        return

    # Si existe pero le faltan valores, los reponemos:
    items = [(r.get("list_name"), r.get("label")) for r in choices_bank]
    has_si = ("yesno", "Sí") in items
    has_no = ("yesno", "No") in items
    if not has_si:
        choices_bank.append({"list_name": "yesno", "name": slugify_name("Sí"), "label": "Sí"})
    if not has_no:
        choices_bank.append({"list_name": "yesno", "name": slugify_name("No"), "label": "No"})

def ensure_minimal_list(choices_bank: list[dict], list_name: str):
    """
    Crea una lista mínima (placeholder) para que Survey123 no falle.
    Esto NO reemplaza tu catálogo real; solo evita error de carga.
    """
    # No crear cosas raras para list_canton/list_distrito: ahí damos fallback mejor
    if list_name == "list_canton":
        # mínima: un cantón dummy
        choices_bank.append({"list_name": "list_canton", "name": "canton_demo", "label": "Cantón (demo)"})
        return
    if list_name == "list_distrito":
        # mínima: un distrito dummy y canton_key para choice_filter
        choices_bank.append({"list_name": "list_distrito", "name": "distrito_demo", "label": "Distrito (demo)", "canton_key": "canton_demo"})
        return

    # Para cualquier otra lista: dos opciones genéricas
    choices_bank.append({"list_name": list_name, "name": "opcion_1", "label": "Opción 1"})
    choices_bank.append({"list_name": list_name, "name": "opcion_2", "label": "Opción 2"})

# ==========================================================================================
# 4) Asegurar consistencia survey↔choices (principal)
# ==========================================================================================
def ensure_choice_lists_consistency():
    """
    - Garantiza que st.session_state.choices_bank exista.
    - Asegura yesno.
    - Detecta listas usadas en survey_bank.
    - Crea listas faltantes mínimas para evitar error en Survey123.
    """
    survey_bank = _ss_get("survey_bank", [])
    choices_bank = _ss_get("choices_bank", [])

    if not isinstance(survey_bank, list) or len(survey_bank) == 0:
        return False, "survey_bank está vacío."

    if not isinstance(choices_bank, list):
        st.session_state.choices_bank = []
        choices_bank = st.session_state.choices_bank

    # 1) yesno siempre
    ensure_list_yesno(choices_bank)

    # 2) listas usadas
    used_lists = extract_used_choice_lists(survey_bank)
    existing_lists = get_existing_choice_lists(choices_bank)

    missing = sorted(list(used_lists - existing_lists))
    if missing:
        for ln in missing:
            ensure_minimal_list(choices_bank, ln)

    # 3) Guardar
    st.session_state.choices_bank = choices_bank

    if missing:
        return True, f"Se crearon listas faltantes automáticamente: {', '.join(missing)}"
    return True, "choices_bank está consistente con survey_bank."

# ==========================================================================================
# 5) UI: Panel de diagnóstico (para que veas qué faltaba)
# ==========================================================================================
show_diag_ui = False
try:
    if "active_tab" in st.session_state:
        # si en tu menú tienes una pestaña "Diagnóstico" úsala; si no, se muestra en Export luego
        show_diag_ui = (st.session_state.active_tab == "Diagnóstico")
except Exception:
    show_diag_ui = False

# Si no tenés pestaña Diagnóstico, podés forzar para probar:
# show_diag_ui = True

if show_diag_ui:
    st.header("🧪 Diagnóstico — Survey vs Choices (Survey123)")
    ok, msg = ensure_choice_lists_consistency()
    if ok:
        st.success(msg)
    else:
        st.error(msg)

    survey_bank = _ss_get("survey_bank", [])
    choices_bank = _ss_get("choices_bank", [])

    used = extract_used_choice_lists(survey_bank) if isinstance(survey_bank, list) else set()
    existing = get_existing_choice_lists(choices_bank) if isinstance(choices_bank, list) else set()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Listas usadas en survey")
        st.write(sorted(list(used)))
    with col2:
        st.markdown("### Listas existentes en choices")
        st.write(sorted(list(existing)))

    missing_now = sorted(list(used - existing))
    if missing_now:
        st.warning(f"Aún faltan listas: {', '.join(missing_now)} (esto NO debería pasar).")
    else:
        st.info("No hay listas faltantes.")

# ==========================================================================================
# 6) Hook recomendado: llamar consistencia ANTES de exportar XLSForm
# ==========================================================================================
# En Parte 6/10 (export), antes de crear df_choices/df_survey, llamaremos:
#   ensure_choice_lists_consistency()
#
# Esto garantiza que lo que subís a ArcGIS siempre cargue.
# ==========================================================================================

# ==========================================================================================
# FIN PARTE 5/10
# ==========================================================================================

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 6/10) ==============================
# ========================= EXPORT XLSFORM (XLSX) 100% COMPATIBLE ==========================
# ==========================================================================================
#
# OBJETIVO:
# ✅ Generar el XLSForm FINAL (Excel .xlsx) desde lo que editás en la app:
#    - survey_bank (preguntas)
#    - choices_bank (opciones)
#    - settings (form_title, version, default_language, style="pages")
#
# ✅ Antes de exportar:
#    - Corre el FIX de consistencia survey↔choices (Parte 5):
#      ensure_choice_lists_consistency()
#
# ✅ Incluye descarga opcional del logo para carpeta media/
# ✅ Asegura columnas correctas y ordenadas para Survey123 Connect
#
# REQUISITOS (Partes 1-5):
# - slugify_name()
# - ensure_choice_lists_consistency()
# - st.session_state.survey_bank  (list[dict])
# - st.session_state.choices_bank (list[dict])
# - st.session_state._logo_bytes / _logo_name (si hay logo)
#
# NOTA:
# - Esta parte NO cambia tus preguntas; solo exporta y valida.
# - Si querés “Exportar” en una pestaña, poné active_tab = "Exportar".
# ==========================================================================================

from io import BytesIO
from datetime import datetime
import pandas as pd

# ==========================================================================================
# 1) Helpers de export (DataFrames + Writer)
# ==========================================================================================
def _ss_get(name: str, default):
    if name not in st.session_state:
        st.session_state[name] = default
    return st.session_state[name]

def _row_get(r: dict, k: str, default=""):
    v = r.get(k, default)
    return "" if v is None else v

def build_df_survey_from_bank(survey_bank: list[dict]) -> pd.DataFrame:
    """
    Construye df_survey con columnas recomendadas para Survey123.
    Mantiene campos extra si existieran, pero garantiza el set mínimo.
    """
    if not isinstance(survey_bank, list):
        survey_bank = []

    # Columnas base (las más comunes en XLSForm)
    base_cols = [
        "type", "name", "label", "hint",
        "required", "appearance",
        "relevant", "choice_filter",
        "constraint", "constraint_message",
        "calculation",
        "media::image", "media::audio", "media::video",
        "bind::esri:fieldType"
    ]

    # Detectar columnas adicionales presentes en el banco
    extra_cols = set()
    for r in survey_bank:
        if isinstance(r, dict):
            extra_cols.update(r.keys())

    # Unir columnas base + extras sin duplicar
    cols = list(base_cols)
    for c in sorted(extra_cols):
        if c not in cols:
            cols.append(c)

    df = pd.DataFrame(survey_bank, columns=cols).fillna("")
    return df

def build_df_choices_from_bank(choices_bank: list[dict]) -> pd.DataFrame:
    """
    Construye df_choices. Mantiene columnas extra como 'canton_key' si existen.
    """
    if not isinstance(choices_bank, list):
        choices_bank = []

    base_cols = ["list_name", "name", "label"]
    extra_cols = set()
    for r in choices_bank:
        if isinstance(r, dict):
            extra_cols.update(r.keys())

    cols = list(base_cols)
    for c in sorted(extra_cols):
        if c not in cols:
            cols.append(c)

    df = pd.DataFrame(choices_bank, columns=cols).fillna("")
    return df

def build_df_settings(form_title: str, version: str, idioma: str) -> pd.DataFrame:
    """
    settings.style = pages (como lo necesitás)
    """
    return pd.DataFrame([{
        "form_title": form_title,
        "version": version,
        "default_language": idioma,
        "style": "pages"
    }], columns=["form_title", "version", "default_language", "style"]).fillna("")

def export_xlsform_xlsx(df_survey: pd.DataFrame, df_choices: pd.DataFrame, df_settings: pd.DataFrame) -> bytes:
    """
    Genera bytes del Excel XLSForm (survey/choices/settings).
    """
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_survey.to_excel(writer, sheet_name="survey", index=False)
        df_choices.to_excel(writer, sheet_name="choices", index=False)
        df_settings.to_excel(writer, sheet_name="settings", index=False)

        wb = writer.book
        fmt_hdr = wb.add_format({"bold": True, "align": "left"})

        for sheet_name, df in (("survey", df_survey), ("choices", df_choices), ("settings", df_settings)):
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)
            ws.set_row(0, None, fmt_hdr)
            for col_idx, col_name in enumerate(df.columns):
                # ancho flexible
                ws.set_column(col_idx, col_idx, max(14, min(90, len(str(col_name)) + 10)))

    buffer.seek(0)
    return buffer.getvalue()

# ==========================================================================================
# 2) Validaciones rápidas antes de exportar (mensajes claros)
# ==========================================================================================
def validate_before_export() -> tuple[bool, list[str]]:
    """
    Valida mínimos:
    - survey_bank existe y tiene filas
    - form_title no vacío
    - hay settings básicos
    """
    msgs = []
    survey_bank = _ss_get("survey_bank", [])
    if not isinstance(survey_bank, list) or len(survey_bank) == 0:
        msgs.append("No hay preguntas (survey_bank vacío).")

    # Form title
    form_title = str(_ss_get("form_title", "")).strip()
    if not form_title:
        msgs.append("Falta form_title (título del formulario).")

    ok = (len(msgs) == 0)
    return ok, msgs

# ==========================================================================================
# 3) UI: Exportar (pestaña Exportar)
# ==========================================================================================
show_export_ui = False
try:
    if "active_tab" in st.session_state:
        show_export_ui = (st.session_state.active_tab == "Exportar")
except Exception:
    show_export_ui = False

# Si tu menú aún no setea active_tab, podés forzar para probar:
# show_export_ui = True

if show_export_ui:
    st.header("📦 Exportar XLSForm (Survey123) — XLSX final")
    st.caption("Este export usa lo que editaste en la app. Antes de exportar, se corrigen listas faltantes para que Survey123 Connect no falle.")

    # Inputs export (si no los tenés en Parte 1, aquí los garantizamos)
    # - form_title lo guardamos en session_state.form_title para que sea global
    default_title = _ss_get("form_title", "Encuesta comunidad")
    form_title = st.text_input("Título del formulario (settings.form_title)", value=default_title, key="export_form_title")
    st.session_state.form_title = form_title

    idioma = st.selectbox("Idioma (settings.default_language)", options=["es", "en"], index=0, key="export_lang")

    version_auto = datetime.now().strftime("%Y%m%d%H%M")
    version = st.text_input("Versión (settings.version)", value=version_auto, key="export_version").strip() or version_auto

    st.markdown("---")

    # Botón export
    if st.button("🧮 Construir y descargar XLSForm (.xlsx)", use_container_width=True, key="btn_export_xlsform"):
        ok, msgs = validate_before_export()
        if not ok:
            for m in msgs:
                st.error(m)
        else:
            # 1) Asegurar consistencia survey↔choices (FIX Parte 5)
            ok2, msg2 = ensure_choice_lists_consistency()
            if ok2:
                st.success(msg2)
            else:
                st.warning(msg2)

            # 2) Construir DataFrames desde banks
            survey_bank = _ss_get("survey_bank", [])
            choices_bank = _ss_get("choices_bank", [])

            df_survey = build_df_survey_from_bank(survey_bank)
            df_choices = build_df_choices_from_bank(choices_bank)
            df_settings = build_df_settings(form_title=form_title, version=version, idioma=idioma)

            # 3) Export bytes
            xlsx_bytes = export_xlsform_xlsx(df_survey, df_choices, df_settings)

            # 4) Nombre archivo
            filename = f"{slugify_name(form_title)}_xlsform.xlsx"

            st.download_button(
                label=f"📥 Descargar XLSForm ({filename})",
                data=xlsx_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            # 5) Preview (opcional)
            with st.expander("👀 Vista previa rápida (survey / choices / settings)", expanded=False):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**survey**")
                    st.dataframe(df_survey, use_container_width=True, hide_index=True, height=320)
                with c2:
                    st.markdown("**choices**")
                    st.dataframe(df_choices, use_container_width=True, hide_index=True, height=320)
                with c3:
                    st.markdown("**settings**")
                    st.dataframe(df_settings, use_container_width=True, hide_index=True, height=320)

            # 6) Descargar logo para media/
            if st.session_state.get("_logo_bytes"):
                logo_name = st.session_state.get("_logo_name", "logo.png")
                st.download_button(
                    "📥 Descargar logo para carpeta media/",
                    data=st.session_state["_logo_bytes"],
                    file_name=logo_name,
                    mime="image/png",
                    use_container_width=True
                )

            st.info(
                "Uso en Survey123 Connect:\n"
                "1) Create New Survey → New survey from existing XLSForm.\n"
                "2) Selecciona el XLSX descargado.\n"
                "3) Si usas logo: cópialo en la carpeta media/ del proyecto con el mismo nombre.\n"
                "4) Publica o prueba. (settings.style = pages mantiene Next/Back)\n"
            )

# ==========================================================================================
# 4) Hook recomendado: si tenés un botón export en otro lugar, llama esto:
#    ok2, msg2 = ensure_choice_lists_consistency()
#    df_survey = build_df_survey_from_bank(st.session_state.survey_bank)
#    df_choices = build_df_choices_from_bank(st.session_state.choices_bank)
#    df_settings = build_df_settings(...)
# ==========================================================================================

# ==========================================================================================
# FIN PARTE 6/10
# ==========================================================================================

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 7/10) ==============================
# ====================== Editor FÁCIL de OPCIONES (choices) para cualquiera ================
# ==========================================================================================
#
# OBJETIVO:
# ✅ Que cualquier persona pueda editar las opciones SIN Excel:
#    - Ver listas (list_name) existentes
#    - Editar texto visible (label) de cada opción
#    - Agregar opción nueva
#    - Eliminar opción
#    - Reordenar opciones (arriba/abajo)
#    - Crear una lista nueva completa
#
# ✅ Especial para Cantón/Distrito:
#    - Mantiene columna 'canton_key' necesaria para choice_filter
#    - Permite agregar distritos con su canton_key (desde UI)
#
# REQUISITOS:
# - st.session_state.choices_bank (list[dict]) existe o se crea
# - slugify_name() existe (de tus helpers originales)
#
# NOTA:
# - Esto NO exporta. El export ya está en Parte 6/10.
# ==========================================================================================

# ==========================================================================================
# 1) Session + helpers
# ==========================================================================================
def _ss_get(name: str, default):
    if name not in st.session_state:
        st.session_state[name] = default
    return st.session_state[name]

def _row_get(r: dict, k: str, default=""):
    v = r.get(k, default)
    return "" if v is None else v

def _choices_get_lists(choices_bank: list[dict]) -> list[str]:
    lists = set()
    for r in choices_bank:
        ln = str(_row_get(r, "list_name")).strip()
        if ln:
            lists.add(ln)
    return sorted(list(lists))

def _choices_rows_for_list(choices_bank: list[dict], list_name: str) -> list[tuple[int, dict]]:
    out = []
    for i, r in enumerate(choices_bank):
        if str(_row_get(r, "list_name")).strip() == list_name:
            out.append((i, r))
    return out

def _dedupe_preserve_order(seq: list[str]) -> list[str]:
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out

def _move_choice_row(idx: int, direction: int):
    bank = _ss_get("choices_bank", [])
    j = idx + direction
    if not (0 <= idx < len(bank)) or not (0 <= j < len(bank)):
        return
    bank[idx], bank[j] = bank[j], bank[idx]
    st.session_state.choices_bank = bank

def _delete_choice_row(idx: int):
    bank = _ss_get("choices_bank", [])
    if 0 <= idx < len(bank):
        bank.pop(idx)
    st.session_state.choices_bank = bank

def _ensure_unique_choice_name_in_list(list_name: str, base_name: str) -> str:
    bank = _ss_get("choices_bank", [])
    used = set()
    for r in bank:
        if str(_row_get(r, "list_name")).strip() == list_name:
            used.add(str(_row_get(r, "name")).strip())
    nm = base_name
    k = 2
    while nm in used:
        nm = f"{base_name}_{k}"
        k += 1
    return nm

def _add_choice_row(list_name: str, label: str, extra: dict | None = None):
    bank = _ss_get("choices_bank", [])
    base = slugify_name(label)[:40] or "opcion"
    nm = _ensure_unique_choice_name_in_list(list_name, base)
    row = {"list_name": list_name, "name": nm, "label": label.strip()}
    if extra and isinstance(extra, dict):
        row.update(extra)
    bank.append(row)
    st.session_state.choices_bank = bank

# ==========================================================================================
# 2) UI principal (pestaña “Opciones”)
# ==========================================================================================
show_choices_ui = False
try:
    if "active_tab" in st.session_state:
        show_choices_ui = (st.session_state.active_tab == "Opciones")
except Exception:
    show_choices_ui = False

# Si tu menú aún no setea active_tab, podés forzar:
# show_choices_ui = True

if show_choices_ui:
    st.header("🧩 Editor de Opciones (choices) — fácil para cualquiera")
    st.caption("Aquí editás las listas y opciones que usan las preguntas select_one / select_multiple.")

    choices_bank = _ss_get("choices_bank", [])
    if not isinstance(choices_bank, list):
        st.session_state.choices_bank = []
        choices_bank = st.session_state.choices_bank

    # Asegurar yesno (por si alguien lo borró)
    ensure_list_yesno(choices_bank)
    st.session_state.choices_bank = choices_bank

    # Selector de lista
    lists = _choices_get_lists(choices_bank)
    if not lists:
        st.warning("No hay listas. Podés crear una nueva aquí abajo.")
        lists = ["yesno"]

    left, right = st.columns([1, 2])

    with left:
        st.markdown("### 📂 Listas")
        selected_list = st.selectbox(
            "Selecciona una lista (list_name)",
            options=lists,
            key="choices_list_select"
        )

        st.markdown("---")
        st.markdown("### ➕ Crear lista nueva")
        new_list_name = st.text_input("Nombre de lista (list_name)", value="", key="new_list_name")
        if st.button("Crear lista", use_container_width=True, key="btn_create_list"):
            ln = new_list_name.strip()
            if not ln:
                st.error("Escribe el nombre de la lista.")
            else:
                # Crear al menos una opción inicial
                _add_choice_row(ln, "Opción 1")
                st.success(f"Lista creada: {ln}")
                st.rerun()

        st.markdown("---")
        st.markdown("### 🔎 Buscar opción")
        search_txt = st.text_input("Buscar en labels/names", value="", key="choices_search")
        search_low = search_txt.strip().lower()

    # Mostrar/editar lista seleccionada
    with right:
        st.markdown(f"### 🧾 Opciones en: `{selected_list}`")

        rows = _choices_rows_for_list(choices_bank, selected_list)

        # Filtro
        filtered = []
        for idx, r in rows:
            blob = (str(_row_get(r, "label")) + " " + str(_row_get(r, "name"))).lower()
            if (not search_low) or (search_low in blob):
                filtered.append((idx, r))

        if not filtered:
            st.info("No hay opciones que coincidan con el filtro.")
        else:
            # Seleccionar una opción
            opts = []
            opt_map = {}
            for idx, r in filtered:
                lab = _row_get(r, "label")
                nm = _row_get(r, "name")
                extra = ""
                if selected_list == "list_distrito":
                    extra = f" | canton_key={_row_get(r,'canton_key')}"
                text = f"[{idx}] {lab} — ({nm}){extra}"
                opts.append(text)
                opt_map[text] = (idx, r)

            pick = st.selectbox(
                "Selecciona una opción",
                options=opts,
                key=f"pick_choice_{selected_list}"
            )
            idx, row = opt_map[pick]

            st.markdown("---")
            st.markdown("#### 👁️ Vista")
            st.caption(f"Índice: {idx} | list_name: `{selected_list}` | name: `{_row_get(row,'name')}`")

            # Editor simple
            st.markdown("#### ✏️ Editar (simple)")
            new_label = st.text_area(
                "Texto visible (label)",
                value=_row_get(row, "label"),
                height=80,
                key=f"choice_label_{selected_list}_{idx}"
            )

            # canton_key solo para list_distrito
            new_canton_key = None
            if selected_list == "list_distrito":
                new_canton_key = st.text_input(
                    "canton_key (debe coincidir con name del cantón)",
                    value=_row_get(row, "canton_key"),
                    key=f"choice_ck_{selected_list}_{idx}"
                )

            # Guardar
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("💾 Guardar", use_container_width=True, key=f"save_choice_{selected_list}_{idx}"):
                    bank = _ss_get("choices_bank", [])
                    if 0 <= idx < len(bank):
                        bank[idx] = dict(bank[idx])
                        bank[idx]["label"] = new_label.strip()
                        # Nota: name NO se cambia para no romper referencias
                        if selected_list == "list_distrito":
                            bank[idx]["canton_key"] = (new_canton_key or "").strip()
                        st.session_state.choices_bank = bank
                        st.success("Guardado.")
                        st.rerun()

            with c2:
                if st.button("⬆️", use_container_width=True, key=f"up_choice_{selected_list}_{idx}"):
                    _move_choice_row(idx, -1)
                    st.rerun()
            with c3:
                if st.button("⬇️", use_container_width=True, key=f"down_choice_{selected_list}_{idx}"):
                    _move_choice_row(idx, +1)
                    st.rerun()
            with c4:
                if st.button("🗑️", use_container_width=True, key=f"del_choice_{selected_list}_{idx}"):
                    _delete_choice_row(idx)
                    st.success("Eliminado.")
                    st.rerun()

            st.markdown("---")
            st.markdown("### ➕ Agregar opción nueva a esta lista")

            add_lab = st.text_input("Nuevo label", value="", key=f"add_choice_label_{selected_list}")
            if selected_list == "list_distrito":
                add_ck = st.text_input("canton_key para este distrito", value="", key=f"add_choice_ck_{selected_list}")
            else:
                add_ck = None

            if st.button("Agregar opción", use_container_width=True, key=f"btn_add_choice_{selected_list}"):
                if not add_lab.strip():
                    st.error("Escribe el label.")
                else:
                    extra = {}
                    if selected_list == "list_distrito":
                        extra["canton_key"] = (add_ck or "").strip()
                    _add_choice_row(selected_list, add_lab.strip(), extra=extra if extra else None)
                    st.success("Opción agregada.")
                    st.rerun()

            st.markdown("---")
            st.markdown("### 🧹 Acciones rápidas de la lista")

            colx1, colx2 = st.columns(2)
            with colx1:
                if st.button("Eliminar TODA la lista", use_container_width=True, key=f"btn_del_list_{selected_list}"):
                    if selected_list == "yesno":
                        st.error("No se puede eliminar yesno.")
                    else:
                        bank = _ss_get("choices_bank", [])
                        bank = [r for r in bank if str(_row_get(r, "list_name")).strip() != selected_list]
                        st.session_state.choices_bank = bank
                        st.success("Lista eliminada.")
                        st.rerun()

            with colx2:
                if st.button("Normalizar (quitar duplicados name)", use_container_width=True, key=f"btn_norm_list_{selected_list}"):
                    bank = _ss_get("choices_bank", [])
                    seen = set()
                    new_bank = []
                    for r in bank:
                        ln = str(_row_get(r, "list_name")).strip()
                        nm = str(_row_get(r, "name")).strip()
                        key = (ln, nm)
                        if key in seen:
                            # duplicado exacto: lo quitamos
                            continue
                        seen.add(key)
                        new_bank.append(r)
                    st.session_state.choices_bank = new_bank
                    st.success("Lista normalizada (duplicados removidos).")
                    st.rerun()

    st.markdown("---")
    st.info(
        "Consejo importante:\n"
        "- Evitá cambiar el `name` de una opción, porque las preguntas guardan esos valores.\n"
        "- Cambiar el `label` es seguro (es lo que ve la gente).\n"
        "- Para Cantón/Distrito: `list_canton.name` debe coincidir con `list_distrito.canton_key`.\n"
    )

# ==========================================================================================
# FIN PARTE 7/10
# ==========================================================================================

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 8/10) ==============================
# ======================= WIZARD de CONDICIONALES (relevant) sin escribir código ===========
# ==========================================================================================
#
# OBJETIVO:
# ✅ Que cualquier persona pueda crear dependencias/condicionales SIN escribir expresiones:
#    - “Mostrar esta pregunta SOLO si otra pregunta es igual a X”
#    - “Mostrar SOLO si la opción X está seleccionada (select_multiple)”
#    - “Mostrar SOLO si la otra pregunta NO está vacía”
#    - “Mostrar SOLO si la otra pregunta es Sí/No”
#
# ✅ Se aplica sobre survey_bank:
#    - Permite escoger “Pregunta origen” (la que controla)
#    - Escoger condición
#    - Escoger “Pregunta destino” (la que se va a mostrar/ocultar)
#    - Genera y guarda el campo 'relevant' de la pregunta destino
#
# REQUISITOS:
# - st.session_state.survey_bank (list[dict])
# - slugify_name() existe
# - choices_bank opcional para poblar valores (si existe)
#
# IMPORTANTE:
# - Para select_one y yesno: el relevant usa el VALUE 'name' de choices (no el label)
# - Para select_multiple: usa selected(${pregunta}, 'valor')
# - Este wizard evita romper lo que ya tenías: si ya hay relevant, te muestra y te deja reemplazar.
#
# ==========================================================================================

import re

# ==========================================================================================
# 1) Helpers base
# ==========================================================================================
def _ss_get(name: str, default):
    if name not in st.session_state:
        st.session_state[name] = default
    return st.session_state[name]

def _row_get(r: dict, k: str, default=""):
    v = r.get(k, default)
    return "" if v is None else v

_SELECT_RE = re.compile(r"^\s*(select_one|select_multiple)\s+([A-Za-z0-9_]+)\s*$")

def _get_question_type(row: dict) -> tuple[str, str]:
    """
    Retorna:
      (kind, list_name)
      kind ∈ {"select_one", "select_multiple", "text", "integer", "note", "other"}
    """
    t = str(_row_get(row, "type")).strip()
    m = _SELECT_RE.match(t)
    if m:
        return m.group(1), m.group(2)
    # otros
    tt = t.lower()
    if tt.startswith("text"):
        return "text", ""
    if tt.startswith("integer"):
        return "integer", ""
    if tt.startswith("note"):
        return "note", ""
    return "other", ""

def _survey_questions_index(survey_bank: list[dict]) -> list[dict]:
    """
    Devuelve lista de preguntas editables (excluye begin_group/end_group).
    """
    out = []
    for i, r in enumerate(survey_bank):
        t = str(_row_get(r, "type")).strip().lower()
        if t in ("begin_group", "end_group", "end"):
            continue
        nm = str(_row_get(r, "name")).strip()
        lb = str(_row_get(r, "label")).strip()
        if not nm:
            continue
        kind, list_name = _get_question_type(r)
        out.append({
            "idx": i,
            "name": nm,
            "label": lb,
            "kind": kind,
            "list_name": list_name,
            "row": r
        })
    return out

def _choices_values_for_list(list_name: str) -> list[tuple[str, str]]:
    """
    Retorna [(value_name, label), ...] de choices_bank para una list_name.
    """
    bank = _ss_get("choices_bank", [])
    out = []
    if not isinstance(bank, list):
        return out
    for r in bank:
        if str(_row_get(r, "list_name")).strip() == list_name:
            val = str(_row_get(r, "name")).strip()
            lab = str(_row_get(r, "label")).strip()
            if val:
                out.append((val, lab))
    return out

def _set_relevant(idx: int, relevant_expr: str):
    bank = _ss_get("survey_bank", [])
    if not (0 <= idx < len(bank)):
        return
    bank[idx] = dict(bank[idx])
    bank[idx]["relevant"] = relevant_expr.strip()
    st.session_state.survey_bank = bank

def _get_relevant(idx: int) -> str:
    bank = _ss_get("survey_bank", [])
    if not (0 <= idx < len(bank)):
        return ""
    return str(_row_get(bank[idx], "relevant")).strip()

def _format_ref(qname: str) -> str:
    return f"${{{qname}}}"

# ==========================================================================================
# 2) Construcción de expresiones relevant (plantillas seguras)
# ==========================================================================================
def build_relevant_expr(source_q: dict, condition_kind: str, condition_value: str | None = None) -> str:
    """
    source_q: dict con name/kind/list_name
    condition_kind:
      - "equals"          (select_one / text / integer)
      - "not_equals"
      - "is_selected"     (select_multiple)
      - "not_selected"    (select_multiple)
      - "is_yes"          (select_one yesno)
      - "is_no"           (select_one yesno)
      - "is_filled"       (cualquier tipo)
      - "is_empty"        (cualquier tipo)
    """
    src = source_q["name"]
    ref = _format_ref(src)

    kind = source_q["kind"]
    list_name = source_q["list_name"]

    if condition_kind == "is_filled":
        return f"string-length({ref}) > 0"
    if condition_kind == "is_empty":
        return f"string-length({ref}) = 0"

    # yes/no especial (list yesno)
    if condition_kind in ("is_yes", "is_no"):
        # El value real de yesno depende de choices: normalmente slugify("Sí") => "si" y "no" => "no"
        # Buscamos en choices si existe yesno:
        yes_vals = _choices_values_for_list("yesno")
        v_si = None
        v_no = None
        for val, lab in yes_vals:
            if lab.strip().lower() == "sí" or lab.strip().lower() == "si":
                v_si = val
            if lab.strip().lower() == "no":
                v_no = val
        if v_si is None:
            v_si = slugify_name("Sí")
        if v_no is None:
            v_no = slugify_name("No")
        return f"{ref}='{v_si}'" if condition_kind == "is_yes" else f"{ref}='{v_no}'"

    # select_multiple selected()
    if kind == "select_multiple":
        if condition_kind == "is_selected":
            return f"selected({ref}, '{condition_value}')"
        if condition_kind == "not_selected":
            return f"not(selected({ref}, '{condition_value}'))"

    # equals / not_equals para select_one o text/integer (string compare)
    if condition_kind == "equals":
        return f"{ref}='{condition_value}'"
    if condition_kind == "not_equals":
        return f"{ref}!='{condition_value}'"

    # fallback
    return "1=1"

# ==========================================================================================
# 3) UI Wizard (pestaña “Condicionales”)
# ==========================================================================================
show_cond_ui = False
try:
    if "active_tab" in st.session_state:
        show_cond_ui = (st.session_state.active_tab == "Condicionales")
except Exception:
    show_cond_ui = False

# Si no tenés esa pestaña aún, podés forzar:
# show_cond_ui = True

if show_cond_ui:
    st.header("🧠 Condicionales / Dependencias — sin escribir código")
    st.caption("Crea reglas de ‘mostrar solo si…’ y se guardan en el campo relevant de la pregunta destino.")

    survey_bank = _ss_get("survey_bank", [])
    if not isinstance(survey_bank, list) or len(survey_bank) == 0:
        st.error("No hay preguntas cargadas (survey_bank vacío).")
    else:
        questions = _survey_questions_index(survey_bank)

        if not questions:
            st.error("No se encontraron preguntas editables.")
        else:
            # Selector “origen”
            src_opts = []
            src_map = {}
            for q in questions:
                txt = f"[{q['idx']}] {q['label'][:60] + ('…' if len(q['label'])>60 else '')}  —  {q['name']} ({q['kind']})"
                src_opts.append(txt)
                src_map[txt] = q

            src_pick = st.selectbox("Pregunta ORIGEN (la que controla)", options=src_opts, key="cond_src_pick")
            src_q = src_map[src_pick]

            # Selector “destino”
            dst_opts = []
            dst_map = {}
            for q in questions:
                txt = f"[{q['idx']}] {q['label'][:60] + ('…' if len(q['label'])>60 else '')}  —  {q['name']} ({q['kind']})"
                dst_opts.append(txt)
                dst_map[txt] = q

            dst_pick = st.selectbox("Pregunta DESTINO (la que se muestra/oculta)", options=dst_opts, key="cond_dst_pick")
            dst_q = dst_map[dst_pick]

            st.markdown("---")

            # Condiciones posibles según tipo origen
            kind = src_q["kind"]
            list_name = src_q["list_name"]

            cond_options = ["is_filled", "is_empty"]
            cond_labels = {
                "is_filled": "No vacío (tiene respuesta)",
                "is_empty": "Vacío (sin respuesta)",
                "equals": "Es igual a…",
                "not_equals": "Es diferente a…",
                "is_selected": "Está seleccionada la opción…",
                "not_selected": "NO está seleccionada la opción…",
                "is_yes": "Es Sí",
                "is_no": "Es No",
            }

            # select_one
            if kind == "select_one":
                # si la lista es yesno, damos botones directos
                if list_name == "yesno":
                    cond_options += ["is_yes", "is_no"]
                # y también equals/no_equals con valores
                cond_options += ["equals", "not_equals"]

            # select_multiple
            if kind == "select_multiple":
                cond_options += ["is_selected", "not_selected"]

            # text/integer/other: equals/not_equals para valores libres
            if kind in ("text", "integer", "other"):
                cond_options += ["equals", "not_equals"]

            # UI condición
            cond_pick = st.selectbox(
                "Condición",
                options=cond_options,
                format_func=lambda x: cond_labels.get(x, x),
                key="cond_kind_pick"
            )

            cond_value = None

            # Si requiere valor:
            requires_value = cond_pick in ("equals", "not_equals", "is_selected", "not_selected")
            if requires_value:
                if kind in ("select_one", "select_multiple"):
                    # ofrecer valores desde choices si existen
                    vals = _choices_values_for_list(list_name)
                    if vals:
                        val_opts = []
                        val_map = {}
                        for v, lab in vals:
                            txt = f"{lab}  (valor: {v})"
                            val_opts.append(txt)
                            val_map[txt] = v
                        val_pick = st.selectbox("Valor", options=val_opts, key="cond_val_pick")
                        cond_value = val_map[val_pick]
                    else:
                        # fallback manual
                        cond_value = st.text_input("Valor (name en choices)", value="", key="cond_val_manual").strip()
                else:
                    # texto/integer manual
                    cond_value = st.text_input("Valor", value="", key="cond_val_free").strip()

            # Mostrar relevant actual
            current_rel = _get_relevant(dst_q["idx"])
            st.markdown("---")
            st.markdown("### 📌 Relevant actual en la pregunta destino")
            st.code(current_rel or "(vacío)")

            # Construir expresión
            expr = build_relevant_expr(src_q, cond_pick, cond_value)
            st.markdown("### ✅ Relevant propuesto")
            st.code(expr)

            # Combinar con relevant existente (AND)
            st.markdown("### 🔗 Opciones al guardar")
            combine_mode = st.radio(
                "¿Qué hacer con el relevant existente?",
                options=["Reemplazar", "Combinar con AND (mantener lo anterior)"],
                horizontal=True,
                key="cond_combine_mode"
            )

            if st.button("💾 Guardar condicional", use_container_width=True, key="btn_save_cond"):
                if requires_value and not cond_value:
                    st.error("Falta el valor de condición.")
                else:
                    if combine_mode == "Reemplazar" or not current_rel:
                        final_expr = expr
                    else:
                        final_expr = f"({current_rel}) and ({expr})"
                    _set_relevant(dst_q["idx"], final_expr)
                    st.success("Condicional guardado.")
                    st.rerun()

            # Borrar relevant
            if st.button("🧽 Quitar condicional (vaciar relevant)", use_container_width=True, key="btn_clear_rel"):
                _set_relevant(dst_q["idx"], "")
                st.success("Relevant eliminado.")
                st.rerun()

    st.info(
        "Tips:\n"
        "- Para preguntas de opciones (select_one), el relevant compara contra el VALUE (name) en choices.\n"
        "- Para select_multiple se usa selected(${pregunta}, 'valor').\n"
        "- Si combinás con AND, se conservan reglas anteriores.\n"
    )

# ==========================================================================================
# FIN PARTE 8/10
# ==========================================================================================

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 9/10) ==============================
# ======================= GUARDAR / CARGAR PROYECTO (JSON) + BACKUP =======================
# ==========================================================================================
#
# OBJETIVO:
# ✅ Guardar TODO lo editado en un archivo .json para:
#    - Continuar otro día sin perder cambios
#    - Compartirlo con otra persona
#    - Hacer backups antes de cambios grandes
#
# SE GUARDA:
# - form_title
# - survey_bank
# - choices_bank
# - glossary_definitions
# - glossary_by_page
# - glossary_order_by_page
# - catalog cantón→distrito (si aún usás choices_ext_rows)
# - logo metadata (nombre)  [NOTA: no guardamos bytes en JSON por tamaño]
#
# SE CARGA:
# - Restaura todo en st.session_state
#
# REQUISITOS:
# - st.session_state.* con estructuras ya creadas en partes anteriores.
# ==========================================================================================

import json

# ==========================================================================================
# 1) Helpers
# ==========================================================================================
def _ss_get(name: str, default):
    if name not in st.session_state:
        st.session_state[name] = default
    return st.session_state[name]

def _safe_list(x):
    return x if isinstance(x, list) else []

def _safe_dict(x):
    return x if isinstance(x, dict) else {}

def build_project_payload() -> dict:
    """
    Construye el JSON del proyecto con todo lo necesario.
    """
    payload = {
        "schema_version": "1.0",
        "form_title": str(_ss_get("form_title", "")),
        "logo_name": str(_ss_get("_logo_name", "")),
        # bancos principales
        "survey_bank": _safe_list(_ss_get("survey_bank", [])),
        "choices_bank": _safe_list(_ss_get("choices_bank", [])),
        # glosario
        "glossary_definitions": _safe_dict(_ss_get("glossary_definitions", {})),
        "glossary_by_page": _safe_dict(_ss_get("glossary_by_page", {})),
        "glossary_order_by_page": _safe_dict(_ss_get("glossary_order_by_page", {})),
        # compat: si aún usabas choices_ext_rows para cantón/distrito por lotes
        "choices_ext_rows": _safe_list(_ss_get("choices_ext_rows", [])),
    }
    return payload

def apply_project_payload(payload: dict):
    """
    Aplica el JSON del proyecto a session_state.
    """
    if not isinstance(payload, dict):
        raise ValueError("Proyecto inválido (no es dict).")

    st.session_state.form_title = str(payload.get("form_title", "")).strip() or _ss_get("form_title", "Encuesta comunidad")
    st.session_state._logo_name = str(payload.get("logo_name", "")).strip() or _ss_get("_logo_name", "001.png")

    st.session_state.survey_bank = _safe_list(payload.get("survey_bank", []))
    st.session_state.choices_bank = _safe_list(payload.get("choices_bank", []))

    st.session_state.glossary_definitions = _safe_dict(payload.get("glossary_definitions", {}))
    st.session_state.glossary_by_page = _safe_dict(payload.get("glossary_by_page", {}))
    st.session_state.glossary_order_by_page = _safe_dict(payload.get("glossary_order_by_page", {}))

    st.session_state.choices_ext_rows = _safe_list(payload.get("choices_ext_rows", []))

# ==========================================================================================
# 2) UI: Pestaña “Proyecto”
# ==========================================================================================
show_project_ui = False
try:
    if "active_tab" in st.session_state:
        show_project_ui = (st.session_state.active_tab == "Proyecto")
except Exception:
    show_project_ui = False

# Si no tenés esa pestaña aún, podés forzar:
# show_project_ui = True

if show_project_ui:
    st.header("💾 Proyecto — Guardar / Cargar (JSON)")
    st.caption("Guarda tu trabajo como archivo .json para continuar otro día o compartirlo.")

    # Guardar
    st.subheader("📥 Guardar proyecto")
    payload = build_project_payload()
    json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    default_name = slugify_name(payload.get("form_title", "proyecto")) or "proyecto"
    file_name = f"{default_name}_proyecto.json"

    st.download_button(
        label=f"📥 Descargar proyecto ({file_name})",
        data=json_bytes,
        file_name=file_name,
        mime="application/json",
        use_container_width=True,
        key="btn_download_project"
    )

    st.markdown("---")

    # Cargar
    st.subheader("📤 Cargar proyecto")
    up = st.file_uploader("Sube un .json de proyecto", type=["json"], key="uploader_project")
    if up is not None:
        try:
            content = up.getvalue().decode("utf-8")
            obj = json.loads(content)
            apply_project_payload(obj)
            st.success("Proyecto cargado correctamente. (Se restauraron preguntas, opciones y glosario).")
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo cargar el proyecto: {e}")

    st.markdown("---")
    st.subheader("🧯 Backup rápido (antes de cambios grandes)")
    st.info("Tip: descarga un backup antes de reordenar páginas o borrar listas completas.")

# ==========================================================================================
# FIN PARTE 9/10
# ==========================================================================================

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 10/10) =============================
# ===================== VALIDACIÓN FINAL + PANEL “Estado del XLSForm” ======================
# ==========================================================================================
#
# OBJETIVO:
# ✅ Detectar ANTES de exportar/subir a Survey123:
#    - names duplicados en survey
#    - select_one / select_multiple con list_name inexistente en choices
#    - choice_filter usa columna que no existe en choices (ej. canton_key)
#    - preguntas sin label (texto vacío)
#    - relevant que referencia preguntas inexistentes (${...})
#    - begin_group / end_group desbalanceados (páginas rotas)
#
# ✅ Panel visual: “Estado del XLSForm”
#    - muestra Errores (rojo) y Advertencias (amarillo)
#    - botón “Auto-fix seguro” para corregir lo que se puede sin romper
#
# REQUISITOS:
# - survey_bank / choices_bank en session_state
# - ensure_choice_lists_consistency() (Parte 5)  (para auto-fix de listas)
# - slugify_name()
#
# ==========================================================================================

import re

# ==========================================================================================
# 1) Helpers base
# ==========================================================================================
def _ss_get(name: str, default):
    if name not in st.session_state:
        st.session_state[name] = default
    return st.session_state[name]

def _row_get(r: dict, k: str, default=""):
    v = r.get(k, default)
    return "" if v is None else v

_SELECT_RE = re.compile(r"^\s*(select_one|select_multiple)\s+([A-Za-z0-9_]+)\s*$")
_REF_RE = re.compile(r"\$\{([A-Za-z0-9_]+)\}")

def _existing_choice_lists(choices_bank: list[dict]) -> set[str]:
    s = set()
    for r in choices_bank:
        ln = str(_row_get(r, "list_name")).strip()
        if ln:
            s.add(ln)
    return s

def _choices_columns(choices_bank: list[dict]) -> set[str]:
    cols = set()
    for r in choices_bank:
        if isinstance(r, dict):
            cols.update(r.keys())
    return cols

def _extract_used_lists(survey_bank: list[dict]) -> set[str]:
    used = set()
    for r in survey_bank:
        t = str(_row_get(r, "type")).strip()
        m = _SELECT_RE.match(t)
        if m:
            used.add(m.group(2))
    return used

def _extract_refs_from_expr(expr: str) -> set[str]:
    if not expr:
        return set()
    return set(m.group(1) for m in _REF_RE.finditer(expr))

# ==========================================================================================
# 2) Validadores
# ==========================================================================================
def validate_survey_names_unique(survey_bank: list[dict]) -> tuple[list[str], list[str]]:
    """
    returns (errors, warnings)
    """
    errors, warnings = [], []
    seen = {}
    for i, r in enumerate(survey_bank):
        t = str(_row_get(r, "type")).strip().lower()
        # nombres relevantes: casi todo menos begin/end?
        nm = str(_row_get(r, "name")).strip()
        if not nm:
            continue
        if nm in seen:
            errors.append(f"Name duplicado en survey: '{nm}' (índices {seen[nm]} y {i}).")
        else:
            seen[nm] = i
    return errors, warnings

def validate_select_lists_exist(survey_bank: list[dict], choices_bank: list[dict]) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    used = _extract_used_lists(survey_bank)
    existing = _existing_choice_lists(choices_bank)
    missing = sorted(list(used - existing))
    if missing:
        errors.append(f"Listas usadas en survey pero faltantes en choices: {', '.join(missing)}.")
    return errors, warnings

def validate_choice_filter_columns(survey_bank: list[dict], choices_bank: list[dict]) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    cols = _choices_columns(choices_bank)
    # Si hay algún choice_filter, validar columnas mencionadas (simple)
    for i, r in enumerate(survey_bank):
        cf = str(_row_get(r, "choice_filter")).strip()
        if not cf:
            continue
        # Heurística: tomar tokens antes de '=' o '!='
        # ej: "canton_key=${canton}" => columna "canton_key"
        col = cf.split("=")[0].strip()
        if col and col not in cols:
            errors.append(f"choice_filter en survey idx {i} usa columna '{col}' que no existe en choices.")
    return errors, warnings

def validate_labels_present(survey_bank: list[dict]) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    for i, r in enumerate(survey_bank):
        t = str(_row_get(r, "type")).strip().lower()
        if t in ("begin_group", "end_group", "end"):
            continue
        # notas pueden ser separadores; aún así, si no hay label es raro
        lb = str(_row_get(r, "label")).strip()
        nm = str(_row_get(r, "name")).strip()
        if nm and not lb:
            warnings.append(f"Pregunta sin label (texto vacío) en idx {i} name='{nm}'.")
    return errors, warnings

def validate_relevant_references(survey_bank: list[dict]) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    names = set(str(_row_get(r, "name")).strip() for r in survey_bank if str(_row_get(r, "name")).strip())
    for i, r in enumerate(survey_bank):
        rel = str(_row_get(r, "relevant")).strip()
        if not rel:
            continue
        refs = _extract_refs_from_expr(rel)
        missing = sorted([x for x in refs if x not in names])
        if missing:
            errors.append(f"Relevant en idx {i} referencia names inexistentes: {', '.join(missing)}.")
    return errors, warnings

def validate_groups_balanced(survey_bank: list[dict]) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    stack = []
    for i, r in enumerate(survey_bank):
        t = str(_row_get(r, "type")).strip().lower()
        if t == "begin_group":
            stack.append(i)
        elif t == "end_group":
            if not stack:
                errors.append(f"end_group sin begin_group (idx {i}).")
            else:
                stack.pop()
    if stack:
        errors.append(f"begin_group sin cerrar (idxs: {', '.join(map(str, stack))}).")
    return errors, warnings

def run_all_validations() -> dict:
    """
    Devuelve dict con errores y advertencias.
    """
    survey_bank = _ss_get("survey_bank", [])
    choices_bank = _ss_get("choices_bank", [])

    if not isinstance(survey_bank, list):
        survey_bank = []
    if not isinstance(choices_bank, list):
        choices_bank = []

    all_errors = []
    all_warnings = []

    for fn in (
        validate_survey_names_unique,
        validate_select_lists_exist,
        validate_choice_filter_columns,
        validate_labels_present,
        validate_relevant_references,
        validate_groups_balanced,
    ):
        if fn == validate_select_lists_exist or fn == validate_choice_filter_columns:
            e, w = fn(survey_bank, choices_bank)
        else:
            e, w = fn(survey_bank)
        all_errors.extend(e)
        all_warnings.extend(w)

    return {"errors": all_errors, "warnings": all_warnings}

# ==========================================================================================
# 3) Auto-fix seguro (sin romper)
# ==========================================================================================
def auto_fix_safe() -> list[str]:
    """
    Correcciones que no deberían romper:
    - ensure_choice_lists_consistency() (crea listas mínimas faltantes)
    - rellena required vacío como "no" si está vacío en preguntas editables
    - rellena bind::esri:fieldType="null" en notes si está vacío
    """
    changes = []
    ok, msg = ensure_choice_lists_consistency()
    if ok:
        changes.append(msg)
    else:
        changes.append(f"Consistencia survey↔choices: {msg}")

    bank = _ss_get("survey_bank", [])
    if isinstance(bank, list) and bank:
        for i, r in enumerate(bank):
            t = str(_row_get(r, "type")).strip().lower()
            if t in ("begin_group", "end_group", "end"):
                continue
            bank[i] = dict(bank[i])

            # required default
            req = str(_row_get(bank[i], "required")).strip().lower()
            if req == "":
                bank[i]["required"] = "no"

            # notes sin columnas
            if t == "note":
                if str(_row_get(bank[i], "bind::esri:fieldType")).strip() == "":
                    bank[i]["bind::esri:fieldType"] = "null"

        st.session_state.survey_bank = bank
        changes.append("Auto-fix aplicado: required vacío -> 'no', notes -> bind::esri:fieldType='null'.")
    return changes

# ==========================================================================================
# 4) UI: Panel “Estado del XLSForm” (pestaña “Estado”)
# ==========================================================================================
show_status_ui = False
try:
    if "active_tab" in st.session_state:
        show_status_ui = (st.session_state.active_tab == "Estado")
except Exception:
    show_status_ui = False

# Si no tenés esa pestaña aún, podés forzar:
# show_status_ui = True

if show_status_ui:
    st.header("✅ Estado del XLSForm — Validación antes de Survey123")
    st.caption("Esto detecta errores que causan que Survey123 Connect rechace el XLSForm o se comporte raro.")

    survey_bank = _ss_get("survey_bank", [])
    if not isinstance(survey_bank, list) or len(survey_bank) == 0:
        st.error("No hay survey_bank cargado.")
    else:
        if st.button("🔍 Ejecutar validación", use_container_width=True, key="btn_run_validation"):
            res = run_all_validations()
            errs = res["errors"]
            warns = res["warnings"]

            if errs:
                st.error(f"Errores encontrados: {len(errs)}")
                for e in errs:
                    st.write(f"❌ {e}")
            else:
                st.success("No se encontraron errores.")

            if warns:
                st.warning(f"Advertencias: {len(warns)}")
                for w in warns:
                    st.write(f"⚠️ {w}")
            else:
                st.info("No hay advertencias.")

            st.markdown("---")
            st.subheader("🛠️ Auto-fix seguro (recomendado)")
            if st.button("Aplicar Auto-fix", use_container_width=True, key="btn_autofix"):
                changes = auto_fix_safe()
                for c in changes:
                    st.success(c)
                st.info("Volvé a ejecutar la validación para ver el estado actualizado.")
                st.rerun()

    st.info(
        "Recomendación:\n"
        "- Si hay errores rojos, arreglalos antes de exportar.\n"
        "- Luego exportá en la pestaña Exportar (Parte 6).\n"
    )

# ==========================================================================================
# FIN PARTE 10/10
# ==========================================================================================




