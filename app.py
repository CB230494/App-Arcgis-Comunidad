# -*- coding: utf-8 -*-
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (1/10) ====================================
# ====== App: Encuesta Comunidad → XLSForm Survey123 (Editor fácil + Export + Glosario) =====
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
st.set_page_config(page_title="Encuesta Comunidad — XLSForm (Editor fácil)", layout="wide")
st.title("🏘️ Encuesta Comunidad → XLSForm para ArcGIS Survey123 (Editor fácil + Export)")

st.markdown("""
Esta app genera un **XLSForm** listo para **ArcGIS Survey123** con `settings.style = pages` (Next/Back).
Además incluye un **editor fácil**, para que cualquier persona pueda:
- ✏️ Editar preguntas (texto, requerido, condicionales, constraints, etc.)
- ↕️ Mover preguntas (subir/bajar)
- ➕ Agregar preguntas
- 🗑️ Eliminar preguntas
- 📄 Duplicar preguntas
- 📚 Editar glosario por página
- 🧾 Editar listas (choices) sin usar Excel
""")

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

def add_choice_list(choices_rows, list_name: str, labels: list[str]):
    """Agrega choices (list_name/name/label) evitando duplicados."""
    usados = set((r.get("list_name"), r.get("name")) for r in choices_rows)
    for lab in labels:
        row = {"list_name": list_name, "name": slugify_name(lab), "label": lab}
        key = (row["list_name"], row["name"])
        if key not in usados:
            choices_rows.append(row)
            usados.add(key)

# ==========================================================================================
# Estado UI
# ==========================================================================================
if "ui_mode" not in st.session_state:
    st.session_state["ui_mode"] = "Editor"

st.session_state["ui_mode"] = st.radio(
    "Modo:",
    options=["Editor", "Exportar"],
    index=0 if st.session_state["ui_mode"] == "Editor" else 1,
    horizontal=True
)
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (2/10) ====================================
# ==========================================================================================

# ==========================================================================================
# Logo + Delegación
# ==========================================================================================
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
    delegacion = st.text_input("Nombre del lugar / Delegación", value="San Carlos Oeste")
    logo_media_name = st.text_input(
        "Nombre de archivo para `media::image`",
        value=st.session_state.get("_logo_name", "001.png"),
        help="Debe coincidir con el archivo dentro de la carpeta `media/` del proyecto Survey123."
    )

form_title = f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad"
st.markdown(f"### {form_title}")

# ==========================================================================================
# Página 1: Introducción (EXACTO indicado)
# ==========================================================================================
INTRO_COMUNIDAD_EXACTA = (
    "Con el fin de hacer más segura nuestra comunidad, deseamos concentrarnos en los \n"
    "problemas de seguridad más importantes. Queremos trabajar en conjunto con el gobierno \n"
    "local, otras instituciones y la comunidad para reducir los delitos y riesgos que afectan a las \n"
    "personas. \n"
    "Es importante recordarle que la información que usted nos proporcione es confidencial y se \n"
    "utilizará únicamente para mejorar la seguridad en nuestra área."
)

# ==========================================================================================
# Página 2: Consentimiento (MISMO)
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
# Glosario base
# ==========================================================================================
GLOSARIO_DEFINICIONES = {
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
# Catálogo Cantón → Distrito (por lotes)
# ==========================================================================================
if "choices_ext_rows" not in st.session_state:
    st.session_state.choices_ext_rows = []

def _append_choice_unique(row: dict):
    key = (row.get("list_name"), row.get("name"))
    exists = any((r.get("list_name"), r.get("name")) == key for r in st.session_state.choices_ext_rows)
    if not exists:
        st.session_state.choices_ext_rows.append(row)

if st.session_state["ui_mode"] == "Editor":
    st.markdown("### 📚 Catálogo Cantón → Distrito (por lotes)")
    with st.expander("Agrega un lote (un Cantón y uno o varios Distritos)", expanded=False):
        col_c1, col_c2 = st.columns([2, 3])
        canton_txt = col_c1.text_input("Cantón (una vez)", value="")
        distritos_txt = col_c2.text_area("Distritos del cantón (uno por línea)", value="", height=120)

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
                st.error("Debes indicar Cantón y al menos un Distrito (uno por línea).")
            else:
                slug_c = slugify_name(c)
                _append_choice_unique({"list_name": "list_canton", "name": slug_c, "label": c})
                usados_d = set()
                for d in distritos:
                    slug_d_base = slugify_name(d)
                    slug_d = asegurar_nombre_unico(slug_d_base, usados_d)
                    usados_d.add(slug_d)
                    _append_choice_unique({"list_name": "list_distrito", "name": slug_d, "label": d, "canton_key": slug_c})
                st.success(f"Lote agregado: {c} → {len(distritos)} distrito(s).")
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (3/10) ====================================
# ====== PARTE 3: CHOICES BASE + Inicialización de bancos (questions/choices/glosario) =====
# ==========================================================================================
#
# ✅ Esta Parte 3 es CLAVE para corregir tu NameError:
# - Primero definimos _construir_choices_y_base(...)
# - Luego (más adelante) se “seed” choices_bank usando esa función
#
# Además:
# - Creamos page_order (orden de páginas)
# - Creamos el "bank" editable de choices (choices_bank) desde choices base + cantón/distrito
# - Dejamos el glosario listo en session_state (glosario_bank / glosario_pages)
#
# NOTA:
# - Aún NO creamos el questions_bank completo (eso va en Parte 4, porque es largo).
# ==========================================================================================

# ==========================================================================================
# PARTE choices base (función requerida por el editor)
# ==========================================================================================
def _construir_choices_y_base(form_title: str, logo_media_name: str):
    """
    Devuelve:
      - survey_rows (vacío aquí; se usa para compatibilidad)
      - choices_rows (todas las listas base)
      - v_si / v_no (valores slug de Sí/No)
    """
    survey_rows = []
    choices_rows = []

    # Yes/No
    add_choice_list(choices_rows, "yesno", ["Sí", "No"])
    v_si = slugify_name("Sí")
    v_no = slugify_name("No")

    # Demográficos
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
    add_choice_list(choices_rows, "relacion_zona", ["Vivo en la zona", "Trabajo en la zona", "Visito la zona", "Estudio en la zona"])

    # Página 4
    add_choice_list(choices_rows, "seguridad_5", ["Muy inseguro", "Inseguro", "Ni seguro ni inseguro", "Seguro", "Muy seguro"])

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
    add_choice_list(choices_rows, "causas_inseguridad", causas_71)

    add_choice_list(choices_rows, "escala_1_5", [
        "1 (Mucho Menos Seguro)",
        "2 (Menos Seguro)",
        "3 (Se mantiene igual)",
        "4 (Más Seguro)",
        "5 (Mucho Más Seguro)",
    ])

    add_choice_list(choices_rows, "matriz_1_5_na", [
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
    add_choice_list(choices_rows, "tipo_espacio", tipos_10)

    # Página 5
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
    add_choice_list(choices_rows, "p12_prob_situacionales", p12)

    p13 = [
        "Falta de oferta educativa",
        "Falta de oferta deportiva",
        "Falta de oferta recreativa",
        "Falta de actividades culturales",
    ]
    add_choice_list(choices_rows, "p13_carencias_inversion", p13)

    p14 = ["Área privada", "Área pública", "No se observa consumo"]
    add_choice_list(choices_rows, "p14_consumo_drogas_donde", p14)

    p15 = ["Calles en mal estado", "Falta de señalización de tránsito", "Carencia o inexistencia de aceras"]
    add_choice_list(choices_rows, "p15_def_infra_vial", p15)

    p16 = ["Casa de habitación (Espacio Cerrado)", "Edificación abandonada", "Lote baldío", "Otro"]
    add_choice_list(choices_rows, "p16_bunkeres_espacios", p16)

    p17 = ["Informal (taxis piratas)", "Plataformas (digitales)"]
    add_choice_list(choices_rows, "p17_transporte_afect", p17)

    p18 = ["Falta de presencia policial", "Presencia policial insuficiente", "Presencia policial solo en ciertos horarios", "No observa presencia policial"]
    add_choice_list(choices_rows, "p18_presencia_policial", p18)

    # Página 6
    p19 = [
        "Disturbios en vía pública. (Riñas o Agresión)",
        "Daños a la propiedad. (Destruir, inutilizar o desaparecer).",
        "Extorsión (intimidar o amenazar a otras personas con fines de lucro).",
        "Hurto. (sustracción de artículos mediante el descuido).",
        "Compra o venta de bienes de presunta procedencia ilícita (receptación)",
        "Contrabando (licor, cigarrillos, medicinas, ropa, calzado, etc.)",
        "Maltrato animal",
        "Tráfico de personas (coyotaje)",
        "Otro"
    ]
    add_choice_list(choices_rows, "p19_delitos_general", p19)

    p20 = [
        "En espacios cerrados (casas, edificaciones u otros inmuebles)",
        "En vía pública",
        "De forma ocasional o móvil (sin punto fijo)",
        "No se percibe consumo o venta",
        "Otro"
    ]
    add_choice_list(choices_rows, "p20_bunker_percepcion", p20)

    p21 = ["Homicidios", "Heridos (lesiones dolosas)", "Femicidio"]
    add_choice_list(choices_rows, "p21_vida", p21)

    p22 = ["Abuso sexual", "Acoso sexual", "Violación", "Acoso Callejero"]
    add_choice_list(choices_rows, "p22_sexuales", p22)

    p23 = ["Asalto a personas", "Asalto a comercio", "Asalto a vivienda", "Asalto a transporte público"]
    add_choice_list(choices_rows, "p23_asaltos", p23)

    p24 = ["Billetes falsos", "Documentos falsos", "Estafa (Oro)", "Lotería falsos", "Estafas informáticas", "Estafa telefónica", "Estafa con tarjetas"]
    add_choice_list(choices_rows, "p24_estafas", p24)

    p25 = [
        "Tacha a comercio",
        "Tacha a edificaciones",
        "Tacha a vivienda",
        "Tacha de vehículos",
        "Robo de ganado (destace de ganado)",
        "Robo de bienes agrícolas",
        "Robo de cultivo",
        "Robo de vehículos",
        "Robo de cable",
        "Robo de combustible",
    ]
    add_choice_list(choices_rows, "p25_robo_fuerza", p25)

    p26 = ["Abandono de adulto mayor", "Abandono de menor de edad", "Abandono de incapaz"]
    add_choice_list(choices_rows, "p26_abandono", p26)

    p27 = ["Sexual", "Laboral"]
    add_choice_list(choices_rows, "p27_explotacion_infantil", p27)

    p28 = ["Caza ilegal", "Pesca ilegal", "Tala ilegal", "Minería ilegal"]
    add_choice_list(choices_rows, "p28_ambientales", p28)

    p29 = ["Con fines laborales", "Con fines sexuales"]
    add_choice_list(choices_rows, "p29_trata", p29)

    # Página 7
    add_choice_list(choices_rows, "p30_vif", ["Sí", "No"])

    p301 = [
        "Violencia psicológica (gritos, amenazas, humillaciones, maltratos, entre otros)",
        "Violencia física (agresiones físicas, empujones, golpes, entre otros)",
        "Violencia vicaria (uso de hijas, hijos u otras personas para causar daño emocional)",
        "Violencia patrimonial (destrucción, retención o control de bienes, documentos o dinero)",
        "Violencia sexual (actos de carácter sexual sin consentimiento)"
    ]
    add_choice_list(choices_rows, "p301_tipos_vif", p301)

    add_choice_list(choices_rows, "p302_medidas", ["Sí", "No", "No recuerda"])
    add_choice_list(choices_rows, "p303_valoracion_fp", ["Excelente", "Bueno", "Regular", "Malo", "Muy malo"])

    add_choice_list(choices_rows, "p31_delito_12m", ["NO", "Sí, y denuncié", "Sí, pero no denuncié."])

    p311 = [
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
    ]
    add_choice_list(choices_rows, "p311_situaciones", p311)

    p312 = [
        "Distancia (falta de oficinas para recepción de denuncias).",
        "Miedo a represalias.",
        "Falta de respuesta oportuna.",
        "He realizado denuncias y no ha pasado nada.",
        "Complejidad al colocar la denuncia.",
        "Desconocimiento de dónde colocar la denuncia.",
        "El Policía me dijo que era mejor no denunciar.",
        "Falta de tiempo para colocar la denuncia."
    ]
    add_choice_list(choices_rows, "p312_motivos_no_denuncia", p312)

    p313 = [
        "00:00 - 02:59 a. m.",
        "03:00 - 05:59 a. m.",
        "06:00 - 08:59 a. m.",
        "09:00 - 11:59 a. m.",
        "12:00 - 14:59 p. m.",
        "15:00 - 17:59 p. m.",
        "18:00 - 20:59 p. m.",
        "21:00 - 23:59 p. m.",
        "DESCONOCIDO"
    ]
    add_choice_list(choices_rows, "p313_horario", p313)

    p314 = [
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
    ]
    add_choice_list(choices_rows, "p314_modo", p314)

    # Página 8
    add_choice_list(choices_rows, "p32_identifica_policias", ["Sí", "No"])

    p321 = [
        "Solicitud de ayuda o auxilio.",
        "Atención relacionada con una denuncia.",
        "Atención cordial o preventiva durante un patrullaje.",
        "Fui abordado o registrado para identificación.",
        "Fui objeto de una infracción o conflicto.",
        "Evento preventivos (Cívico policial, Reunión Comunitaria)",
        "Otra (especifique)"
    ]
    add_choice_list(choices_rows, "p321_interacciones", p321)

    escala_1_10 = [str(i) for i in range(1, 11)]
    add_choice_list(choices_rows, "escala_1_10", escala_1_10)

    p38 = ["Todos los días", "Varias veces por semana", "Una vez por semana", "Casi nunca", "Nunca"]
    add_choice_list(choices_rows, "p38_frecuencia", p38)

    add_choice_list(choices_rows, "p39_si_no_aveces", ["Sí", "No", "A veces"])
    add_choice_list(choices_rows, "p41_opciones", ["Sí", "No", "No estoy seguro(a)"])

    p43 = [
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
    ]
    add_choice_list(choices_rows, "p43_acciones_fp", p43)

    p44 = [
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
    ]
    add_choice_list(choices_rows, "p44_acciones_muni", p44)

    add_choice_list(choices_rows, "p45_info_delito", ["Sí", "No"])

    return survey_rows, choices_rows, v_si, v_no


# ==========================================================================================
# Orden de páginas (editable luego)
# ==========================================================================================
if "page_order" not in st.session_state:
    st.session_state["page_order"] = ["p1","p2","p3","p4","p5","p6","p7","p8"]


# ==========================================================================================
# Inicialización choices_bank (editable) — SIN NameError
# ==========================================================================================
def seed_choices_bank_if_empty(form_title: str, logo_media_name: str):
    """
    Crea st.session_state["choices_bank"] si no existe.
    Fuente:
      - choices base: _construir_choices_y_base(...)
      - + se agregan list_canton/list_distrito desde st.session_state.choices_ext_rows
    """
    if st.session_state.get("choices_bank"):
        return

    _survey_rows_unused, choices_rows, _v_si, _v_no = _construir_choices_y_base(form_title, logo_media_name)

    # integrar catálogo Cantón→Distrito si existe
    for r in st.session_state.get("choices_ext_rows", []):
        choices_rows.append(dict(r))

    st.session_state["choices_bank"] = choices_rows

seed_choices_bank_if_empty(form_title=form_title, logo_media_name=logo_media_name)


# ==========================================================================================
# Inicialización glosario editable
# ==========================================================================================
def seed_glosario_bank_if_missing():
    """
    Crea:
      - glosario_bank : dict termino->definición
      - glosario_pages: dict page_id->list de términos
    """
    if "glosario_bank" not in st.session_state:
        st.session_state["glosario_bank"] = dict(GLOSARIO_DEFINICIONES)

    if "glosario_pages" not in st.session_state:
        st.session_state["glosario_pages"] = {
            "p4": ["Extorsión", "Daños/vandalismo"],
            "p5": ["Búnkeres", "Receptación", "Contrabando", "Trata de personas", "Explotación infantil",
                   "Acoso callejero", "Tráfico de personas (coyotaje)", "Estafa", "Tacha"],
            "p6": ["Receptación", "Contrabando", "Tráfico de personas (coyotaje)", "Acoso callejero",
                   "Estafa", "Tacha", "Trata de personas", "Explotación infantil", "Extorsión", "Búnkeres"],
            "p7": ["Ganzúa (pata de chancho)", "Boquete", "Arrebato", "Receptación", "Extorsión"],
            "p8": ["Patrullaje", "Acciones disuasivas", "Coordinación interinstitucional", "Integridad y credibilidad policial"],
        }

seed_glosario_bank_if_missing()


# ==========================================================================================
# Helper: sincronizar list_canton/list_distrito desde choices_bank hacia choices_ext_rows
# (Para mantener compatibilidad con el catálogo por lotes)
# ==========================================================================================
def sync_canton_distrito_to_choices_ext_rows():
    bank = st.session_state.get("choices_bank", [])
    ext = []
    for r in bank:
        ln = str(r.get("list_name", "")).strip()
        if ln in ("list_canton", "list_distrito"):
            ext.append(dict(r))
    st.session_state["choices_ext_rows"] = ext
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (4/10) ====================================
# ====== PARTE 4: questions_bank precargado (P1 a P8) + seed_questions_bank_if_missing =====
# ==========================================================================================
#
# ✅ Aquí se crea el banco editable de preguntas:
#   st.session_state["questions_bank"] = [
#      {"qid": "...", "page":"p4", "order": 10, "row": {type/name/label/...}}
#   ]
#
# ✅ Importante:
# - NO metemos glosario dentro del survey aquí (eso se inyecta al export en Parte 8)
# - Sí dejamos TODO editable (label, required, relevant, constraint, etc.)
#
# ✅ También:
# - Mantiene reglas clave: notes con bind::esri:fieldType="null"
# - Distrito aparece solo si ya hay Cantón (relevant)
# - Exclusiones tipo “No se observa…” (constraints) como en tu código original
# ==========================================================================================

def seed_questions_bank_if_missing(form_title: str, logo_media_name: str):
    """
    Crea questions_bank si no existe.
    Si ya existe, NO lo sobreescribe.
    """
    if st.session_state.get("questions_bank"):
        return

    qb = []

    # Yes/No values
    v_si = slugify_name("Sí")
    v_no = slugify_name("No")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    def _new_qid():
        return f"q_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    def add_row(page: str, order: int, row: dict):
        qb.append({
            "qid": _new_qid(),
            "page": page,
            "order": int(order),
            "row": dict(row)
        })

    def add_note(page: str, order: int, name: str, label: str, relevant: str = "", media_image: str = ""):
        row = {
            "type": "note",
            "name": name,
            "label": label,
            "bind::esri:fieldType": "null"
        }
        if relevant:
            row["relevant"] = relevant
        if media_image:
            row["media::image"] = media_image
        add_row(page, order, row)

    # ======================================================================================
    # P1 Introducción
    # ======================================================================================
    add_row("p1", 10, {"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"})
    add_note("p1", 20, "p1_logo", form_title, media_image=logo_media_name)
    add_note("p1", 30, "p1_texto", INTRO_COMUNIDAD_EXACTA)
    add_row("p1", 40, {"type": "end_group", "name": "p1_end"})

    # ======================================================================================
    # P2 Consentimiento
    # ======================================================================================
    add_row("p2", 10, {"type": "begin_group", "name": "p2_consent", "label": "Consentimiento Informado", "appearance": "field-list"})
    add_note("p2", 20, "p2_titulo", CONSENT_TITLE)
    o = 30
    for i, p in enumerate(CONSENT_PARRAFOS, start=1):
        add_note("p2", o, f"p2_p_{i}", p); o += 10
    for j, b in enumerate(CONSENT_BULLETS, start=1):
        add_note("p2", o, f"p2_b_{j}", f"• {b}"); o += 10
    for k, c in enumerate(CONSENT_CIERRE, start=1):
        add_note("p2", o, f"p2_c_{k}", c); o += 10

    add_row("p2", o, {
        "type": "select_one yesno",
        "name": "acepta_participar",
        "label": "¿Acepta participar en esta encuesta?",
        "required": "yes",
        "appearance": "minimal"
    }); o += 10

    add_row("p2", o, {"type": "end_group", "name": "p2_end"}); o += 10

    add_row("p2", o, {
        "type": "end",
        "name": "fin_por_no",
        "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.",
        "relevant": f"${{acepta_participar}}='{v_no}'"
    })

    # ======================================================================================
    # P3 Datos demográficos
    # ======================================================================================
    add_row("p3", 10, {
        "type": "begin_group",
        "name": "p3_datos_demograficos",
        "label": "Datos demográficos",
        "appearance": "field-list",
        "relevant": rel_si
    })

    add_row("p3", 20, {
        "type": "select_one list_canton",
        "name": "canton",
        "label": "1. Cantón:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_distrito = f"({rel_si}) and string-length(${{canton}}) > 0"
    add_row("p3", 30, {
        "type": "select_one list_distrito",
        "name": "distrito",
        "label": "2. Distrito:",
        "required": "yes",
        "choice_filter": "canton_key=${canton}",
        "appearance": "minimal",
        "relevant": rel_distrito
    })

    add_row("p3", 40, {
        "type": "integer",
        "name": "edad_anos",
        "label": "3. Edad:",
        "required": "yes",
        "constraint": ". >= 18 and . <= 120",
        "constraint_message": "Debe ser un número entre 18 y 120.",
        "relevant": rel_si
    })

    add_row("p3", 50, {
        "type": "select_one genero",
        "name": "genero",
        "label": "4. ¿Con cuál de estas opciones se identifica?",
        "required": "yes",
        "relevant": rel_si
    })

    add_row("p3", 60, {
        "type": "select_one escolaridad",
        "name": "escolaridad",
        "label": "5. Escolaridad:",
        "required": "yes",
        "relevant": rel_si
    })

    add_row("p3", 70, {
        "type": "select_one relacion_zona",
        "name": "relacion_zona",
        "label": "6. ¿Cuál es su relación con la zona?",
        "required": "yes",
        "relevant": rel_si
    })

    add_row("p3", 80, {"type": "end_group", "name": "p3_end"})

    # ======================================================================================
    # P4 Percepción (7-11)
    # ======================================================================================
    add_row("p4", 10, {
        "type": "begin_group",
        "name": "p4_percepcion_distrito",
        "label": "Percepción ciudadana de seguridad en el distrito",
        "appearance": "field-list",
        "relevant": rel_si
    })

    add_row("p4", 20, {
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

    add_row("p4", 30, {
        "type": "select_multiple causas_inseguridad",
        "name": "p71_causas_inseguridad",
        "label": "7.1. Indique por qué considera el distrito inseguro (Marque todas las situaciones que usted percibe que ocurren con mayor frecuencia en su comunidad):",
        "required": "yes",
        "relevant": rel_71
    })

    add_note("p4", 40, "p71_no_denuncia", "Esta pregunta recoge percepción general y no constituye denuncia.", relevant=rel_71)

    add_row("p4", 50, {
        "type": "text",
        "name": "p71_otro_detalle",
        "label": "Otro problema que considere importante (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_71}) and selected(${{p71_causas_inseguridad}}, '{slugify_name('Otro problema que considere importante')}')"
    })

    add_row("p4", 60, {
        "type": "select_one escala_1_5",
        "name": "p8_comparacion_anno",
        "label": "8. ¿Cómo se percibe la seguridad en este distrito este año en comparación con el año anterior?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_81 = f"({rel_si}) and string-length(${{p8_comparacion_anno}}) > 0"
    add_row("p4", 70, {
        "type": "text",
        "name": "p81_indique_por_que",
        "label": "8.1. Indique por qué:",
        "required": "yes",
        "appearance": "multiline",
        "relevant": rel_81
    })

    add_note("p4", 80, "p9_instr",
             "9. Indique qué tan seguros percibe, en términos de seguridad, en los siguientes espacios de su Distrito:",
             relevant=rel_si)

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
    oo = 90
    for name, label in matriz_filas:
        add_row("p4", oo, {
            "type": "select_one matriz_1_5_na",
            "name": name,
            "label": label,
            "required": "yes",
            "appearance": "minimal",
            "relevant": rel_si
        })
        oo += 10

    add_row("p4", oo, {
        "type": "select_one tipo_espacio",
        "name": "p10_tipo_espacio_mas_inseguro",
        "label": "10. Según su percepción, ¿cuál de los siguientes tipos de espacios del distrito considera más inseguro?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    }); oo += 10

    add_row("p4", oo, {
        "type": "text",
        "name": "p10_otros_detalle",
        "label": "Otros (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and (${{p10_tipo_espacio_mas_inseguro}}='{slugify_name('Otros')}')"
    }); oo += 10

    add_row("p4", oo, {
        "type": "text",
        "name": "p11_por_que_inseguro_tipo_espacio",
        "label": "11. Según su percepción, describa brevemente por qué considera inseguro el tipo de espacio seleccionado en la pregunta anterior.",
        "required": "no",
        "appearance": "multiline",
        "relevant": rel_si
    })

    add_row("p4", 999, {"type": "end_group", "name": "p4_end"})

    # ======================================================================================
    # P5 Riesgos / factores situacionales (12-18)
    # ======================================================================================
    add_row("p5", 10, {
        "type": "begin_group",
        "name": "p5_riesgos",
        "label": "III. RIESGOS, DELITOS, VICTIMIZACIÓN Y EVALUACIÓN POLICIAL",
        "appearance": "field-list",
        "relevant": rel_si
    })

    add_note("p5", 20, "p5_subtitulo", "Riesgos sociales y situacionales en el distrito", relevant=rel_si)
    add_note("p5", 30, "p5_intro",
             "A continuación, se presentará una lista de problemáticas que se catalogan como factores situacionales, con la finalidad de que seleccione aquellos que considere que ocurren en su distrito.",
             relevant=rel_si)

    add_row("p5", 40, {
        "type": "select_multiple p12_prob_situacionales",
        "name": "p12_problematicas_distrito",
        "label": "12. Según su percepción u observación, seleccione las problemáticas que afectan su distrito:",
        "required": "yes",
        "relevant": rel_si
    })

    add_row("p5", 50, {
        "type": "text",
        "name": "p12_otro_detalle",
        "label": "Otro problema que considere importante:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p12_problematicas_distrito}}, '{slugify_name('Otro problema que considere importante')}')"
    })

    add_row("p5", 60, {
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

    add_row("p5", 70, {
        "type": "select_multiple p14_consumo_drogas_donde",
        "name": "p14_donde_consumo_drogas",
        "label": "14. Según su percepción u observación, indique dónde se presenta consumo de drogas en el distrito:",
        "required": "yes",
        "constraint": constraint_p14,
        "constraint_message": "Si selecciona “No se observa consumo”, no puede seleccionar “Área privada” ni “Área pública”.",
        "relevant": rel_si
    })

    add_row("p5", 80, {
        "type": "select_multiple p15_def_infra_vial",
        "name": "p15_deficiencias_infra_vial",
        "label": "15. Indique las principales deficiencias de infraestructura vial que afectan su distrito:",
        "required": "yes",
        "relevant": rel_si
    })

    add_row("p5", 90, {
        "type": "select_multiple p16_bunkeres_espacios",
        "name": "p16_bunkeres_espacios",
        "label": "16. Según su percepción u observación, indique en qué tipo de espacios se identifica la existencia de puntos de venta de drogas (búnkeres) en el distrito:",
        "required": "yes",
        "relevant": rel_si
    })

    add_row("p5", 100, {
        "type": "text",
        "name": "p16_otro_detalle",
        "label": "Otro:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p16_bunkeres_espacios}}, '{slugify_name('Otro')}')"
    })

    add_row("p5", 110, {
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

    add_row("p5", 120, {
        "type": "select_multiple p18_presencia_policial",
        "name": "p18_presencia_policial",
        "label": "18. En relación con la presencia policial en su distrito, indique cuál de las siguientes situaciones identifica:",
        "required": "yes",
        "constraint": constraint_p18,
        "constraint_message": "Si selecciona “No observa presencia policial”, no seleccione otras opciones simultáneamente.",
        "relevant": rel_si
    })

    add_row("p5", 999, {"type": "end_group", "name": "p5_end"})

    # ======================================================================================
    # P6 Delitos (19-29)
    # ======================================================================================
    add_row("p6", 10, {
        "type": "begin_group",
        "name": "p6_delitos",
        "label": "Delitos",
        "appearance": "field-list",
        "relevant": rel_si
    })

    add_note("p6", 20, "p6_intro",
             "A continuación, se presentará una lista de delitos y situaciones delictivas para que seleccione aquellos que, según su percepción u observación, considera que se presentan en su comunidad. Esta información no constituye denuncia formal ni confirmación de hechos delictivos.",
             relevant=rel_si)

    add_row("p6", 30, {
        "type": "select_multiple p19_delitos_general",
        "name": "p19_delitos_general",
        "label": "19. Selección múltiple de los siguientes delitos:",
        "required": "yes",
        "relevant": rel_si
    })

    add_row("p6", 40, {
        "type": "text",
        "name": "p19_otro_detalle",
        "label": "Otro:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p19_delitos_general}}, '{slugify_name('Otro')}')"
    })

    n20_no = slugify_name("No se percibe consumo o venta")
    n20_cerr = slugify_name("En espacios cerrados (casas, edificaciones u otros inmuebles)")
    n20_via = slugify_name("En vía pública")
    n20_movil = slugify_name("De forma ocasional o móvil (sin punto fijo)")
    n20_otro = slugify_name("Otro")
    constraint_p20 = f"not(selected(., '{n20_no}') and (selected(., '{n20_cerr}') or selected(., '{n20_via}') or selected(., '{n20_movil}') or selected(., '{n20_otro}')))"

    add_row("p6", 50, {
        "type": "select_multiple p20_bunker_percepcion",
        "name": "p20_bunker_percepcion",
        "label": "20. Percepción de consumo o venta de drogas en el entorno (Bunker)",
        "required": "yes",
        "constraint": constraint_p20,
        "constraint_message": "Si selecciona “No se percibe consumo o venta”, no seleccione otras opciones simultáneamente.",
        "relevant": rel_si
    })

    add_row("p6", 60, {
        "type": "text",
        "name": "p20_otro_detalle",
        "label": "Otro:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p20_bunker_percepcion}}, '{slugify_name('Otro')}')"
    })

    add_row("p6", 70, {"type": "select_multiple p21_vida", "name": "p21_delitos_vida", "label": "21. Delitos contra la vida", "required": "yes", "relevant": rel_si})
    add_row("p6", 80, {"type": "select_multiple p22_sexuales", "name": "p22_delitos_sexuales", "label": "22. Delitos sexuales", "required": "yes", "relevant": rel_si})
    add_row("p6", 90, {"type": "select_multiple p23_asaltos", "name": "p23_asaltos_percibidos", "label": "23. Asaltos percibidos", "required": "yes", "relevant": rel_si})
    add_row("p6", 100, {"type": "select_multiple p24_estafas", "name": "p24_estafas_percibidas", "label": "24. Estafas percibidas", "required": "yes", "relevant": rel_si})
    add_row("p6", 110, {"type": "select_multiple p25_robo_fuerza", "name": "p25_robo_percibidos", "label": "25. Robo percibidos (Sustracción de artículos mediante la utilización de la fuerza)", "required": "yes", "relevant": rel_si})
    add_row("p6", 120, {"type": "select_multiple p26_abandono", "name": "p26_abandono_personas", "label": "26. Abandono de personas", "required": "yes", "relevant": rel_si})
    add_row("p6", 130, {"type": "select_multiple p27_explotacion_infantil", "name": "p27_explotacion_infantil", "label": "27. Explotación infantil", "required": "yes", "relevant": rel_si})
    add_row("p6", 140, {"type": "select_multiple p28_ambientales", "name": "p28_delitos_ambientales", "label": "28. Delitos ambientales percibidos", "required": "yes", "relevant": rel_si})
    add_row("p6", 150, {"type": "select_multiple p29_trata", "name": "p29_trata_personas", "label": "29. Trata de personas", "required": "yes", "relevant": rel_si})

    add_row("p6", 999, {"type": "end_group", "name": "p6_end"})

    # ======================================================================================
    # P7 Victimización (30-31.4)
    # ======================================================================================
    add_row("p7", 10, {"type": "begin_group", "name": "p7_victimizacion", "label": "Victimización", "appearance": "field-list", "relevant": rel_si})

    add_note("p7", 20, "p7_intro",
             "A continuación, se presentará una lista de situaciones para que indique si usted o algún miembro de su hogar ha sido afectado por alguna de ellas en su distrito durante el último año.",
             relevant=rel_si)

    add_row("p7", 30, {
        "type": "select_one p30_vif",
        "name": "p30_vif",
        "label": "30. Durante el último año, ¿usted o algún miembro de su hogar ha sido afectado por alguna situación de violencia intrafamiliar (violencia doméstica)?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_30_si = f"({rel_si}) and (${{p30_vif}}='{v_si}')"

    add_row("p7", 40, {
        "type": "select_multiple p301_tipos_vif",
        "name": "p301_tipos_vif",
        "label": "30.1. ¿Qué tipo(s) de violencia intrafamiliar (violencia doméstica) se presentaron?",
        "required": "yes",
        "relevant": rel_30_si
    })

    add_row("p7", 50, {
        "type": "select_one p302_medidas",
        "name": "p302_medidas_proteccion",
        "label": "30.2. ¿En relación con la situación de violencia intrafamiliar indicada anteriormente, usted o algún miembro de su hogar solicitó medidas de protección?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_30_si
    })

    add_row("p7", 60, {
        "type": "select_one p303_valoracion_fp",
        "name": "p303_valoracion_fp",
        "label": "30.3. ¿Cómo valora el abordaje de la Fuerza Pública ante esta situación?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_30_si
    })

    add_row("p7", 70, {
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

    add_row("p7", 80, {
        "type": "select_multiple p311_situaciones",
        "name": "p311_situaciones_afecto",
        "label": "31.1. ¿Cuál de las siguientes situaciones afectó a usted o a algún miembro de su hogar?",
        "required": "yes",
        "relevant": rel_31_si
    })

    add_row("p7", 90, {
        "type": "select_multiple p312_motivos_no_denuncia",
        "name": "p312_motivo_no_denuncia",
        "label": "31.2. En caso de NO haber realizado la denuncia, indique ¿cuál fue el motivo?",
        "required": "yes",
        "relevant": rel_31_si_no_den
    })

    add_row("p7", 100, {
        "type": "select_one p313_horario",
        "name": "p313_horario_hecho",
        "label": "31.3. ¿Tiene conocimiento sobre el horario en el cual se presentó el hecho o situación que le afectó a usted o un familiar?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_31_si
    })

    add_row("p7", 110, {
        "type": "select_multiple p314_modo",
        "name": "p314_modo_ocurrio",
        "label": "31.4. ¿Cuál fue la forma o modo en que ocurrió la situación que afectó a usted o a algún miembro de su hogar?",
        "required": "yes",
        "relevant": rel_31_si
    })

    add_row("p7", 120, {
        "type": "text",
        "name": "p314_otro_detalle",
        "label": "Otro (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_31_si}) and selected(${{p314_modo_ocurrio}}, '{slugify_name('Otro')}')"
    })

    add_row("p7", 999, {"type": "end_group", "name": "p7_end"})

    # ======================================================================================
    # P8 Confianza Policial + cierre (32-47)
    # ======================================================================================
    add_row("p8", 10, {"type": "begin_group", "name": "p8_confianza_policial", "label": "Confianza Policial", "appearance": "field-list", "relevant": rel_si})

    add_note("p8", 20, "p8_intro",
             "A continuación, se presentará una lista de afirmaciones relacionadas con su percepción y confianza en el cuerpo de policía que opera en su (Distrito) barrio.",
             relevant=rel_si)

    add_row("p8", 30, {"type": "select_one p32_identifica_policias", "name": "p32_identifica_policias", "label": "32. ¿Identifica usted a los policías de la Fuerza Pública de Costa Rica en su comunidad?", "required": "yes", "appearance": "minimal", "relevant": rel_si})

    rel_321 = f"({rel_si}) and (${{p32_identifica_policias}}='{v_si}')"
    addictions = ""

    add_row("p8", 40, {"type": "select_multiple p321_interacciones", "name": "p321_tipos_atencion", "label": "32.1 ¿Cuáles de los siguientes tipos de atención ha tenido?", "required": "yes", "relevant": rel_321})

    add_row("p8", 50, {"type": "text", "name": "p321_otro_detalle", "label": "Otra (especifique):", "required": "no", "appearance": "multiline", "relevant": f"({rel_321}) and selected(${{p321_tipos_atencion}}, '{slugify_name('Otra (especifique)')}')"})
    add_row("p8", 60, {"type": "select_one escala_1_10", "name": "p33_confianza_policial", "label": "33. ¿Cuál es el nivel de confianza en la policía de la Fuerza Pública de Costa Rica de su comunidad? (1=Ninguna Confianza, 10=Mucha Confianza)", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row("p8", 70, {"type": "select_one escala_1_10", "name": "p34_profesionalidad", "label": "34. En una escala del 1 al 10, donde 1 es “Nada profesional” y 10 es “Muy profesional”, ¿cómo calificaría la profesionalidad de la Fuerza Pública en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row("p8", 80, {"type": "select_one escala_1_10", "name": "p35_calidad_servicio", "label": "35. En una escala del 1 al 10, donde 1 es “Muy mala” y 10 es “Muy buena”, ¿cómo califica la calidad del servicio policial en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row("p8", 90, {"type": "select_one escala_1_10", "name": "p36_satisfaccion_preventivo", "label": "36. En una escala del 1 al 10, donde 1 es “Nada satisfecho(a)” y 10 es “Muy satisfecho(a)”, ¿qué tan satisfecho(a) está con el trabajo preventivo que realiza la Fuerza Pública en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row("p8", 100, {"type": "select_one escala_1_10", "name": "p37_contribucion_reduccion_crimen", "label": "37. En una escala del 1 al 10, donde 1 es “No contribuye en nada” y 10 es “Contribuye muchísimo”, indique: ¿En qué medida considera que la presencia policial ayuda a reducir el crimen en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row("p8", 110, {"type": "select_one p38_frecuencia", "name": "p38_frecuencia_presencia", "label": "38. ¿Con qué frecuencia observa presencia policial en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row("p8", 120, {"type": "select_one p39_si_no_aveces", "name": "p39_presencia_consistente", "label": "39. ¿Considera que la presencia policial es consistente a lo largo del día en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row("p8", 130, {"type": "select_one p39_si_no_aveces", "name": "p40_trato_justo", "label": "40. ¿Considera que la policía trata a las personas de manera justa e imparcial en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row("p8", 140, {"type": "select_one p41_opciones", "name": "p41_quejas_sin_temor", "label": "41. ¿Cree usted que puede expresar preocupaciones o quejas a la policía sin temor a represalias?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row("p8", 150, {"type": "select_one p39_si_no_aveces", "name": "p42_info_veraz_clara", "label": "42. ¿Considera que la policía proporciona información veraz, clara y oportuna a la comunidad?", "required": "yes", "appearance": "minimal", "relevant": rel_si})

    add_row("p8", 160, {"type": "select_multiple p43_acciones_fp", "name": "p43_accion_fp_mejorar", "label": "43. ¿Qué actividad considera que debe realizar la Fuerza Pública para mejorar la seguridad en su comunidad?", "required": "yes", "relevant": rel_si})
    add_row("p8", 170, {"type": "text", "name": "p43_otro_detalle", "label": "Otro (detalle):", "required": "no", "appearance": "multiline", "relevant": f"({rel_si}) and selected(${{p43_accion_fp_mejorar}}, '{slugify_name('Otro')}')"})
    add_row("p8", 180, {"type": "select_multiple p44_acciones_muni", "name": "p44_accion_muni_mejorar", "label": "44. ¿Qué actividad considera que debe realizar la municipalidad para mejorar la seguridad en su comunidad?", "required": "yes", "relevant": rel_si})
    add_row("p8", 190, {"type": "text", "name": "p44_otro_detalle", "label": "Otro (detalle):", "required": "no", "appearance": "multiline", "relevant": f"({rel_si}) and selected(${{p44_accion_muni_mejorar}}, '{slugify_name('Otro')}')"})
    add_note("p8", 200, "p8_info_adicional_titulo", "Información Adicional y Contacto Voluntario", relevant=rel_si)

    add_row("p8", 210, {"type": "select_one p45_info_delito", "name": "p45_info_delito", "label": "45. ¿Usted tiene información de alguna persona o grupo que se dedique a realizar algún delito en su comunidad? (Recuerde, su información es confidencial.)", "required": "yes", "appearance": "minimal", "relevant": rel_si})

    rel_451 = f"({rel_si}) and (${{p45_info_delito}}='{v_si}')"
    add_row("p8", 220, {"type": "text", "name": "p451_detalle_info", "label": "45.1. Si su respuesta es \"Sí\", describa aquellas características que pueda aportar tales como nombre de estructura o banda criminal... (nombre de personas, alias, domicilio, vehículos, etc.)", "required": "yes", "appearance": "multiline", "relevant": rel_451})
    add_row("p8", 230, {"type": "text", "name": "p46_contacto_voluntario", "label": "46. En el siguiente espacio de forma voluntaria podrá anotar su nombre, teléfono o correo electrónico en el cual desee ser contactado y continuar colaborando de forma confidencial con Fuerza Pública.", "required": "no", "appearance": "multiline", "relevant": rel_si})
    add_row("p8", 240, {"type": "text", "name": "p47_info_adicional", "label": "47. En el siguiente espacio podrá registrar alguna otra información que estime pertinente.", "required": "no", "appearance": "multiline", "relevant": rel_si})
    add_note("p8", 250, "p8_fin", "---------------------------------- Fin de la Encuesta ----------------------------------", relevant=rel_si)

    add_row("p8", 999, {"type": "end_group", "name": "p8_end"})

    # Guardar en session_state
    st.session_state["questions_bank"] = qb


# ✅ Ejecutar seed (solo si no existe)
seed_questions_bank_if_missing(form_title=form_title, logo_media_name=logo_media_name)

# ==========================================================================================
# ============================== CÓDIGO COMPLETO (5/10) ====================================
# ====== PARTE 5: EDITOR FÁCIL de preguntas (lista + mover + editar + borrar + duplicar) ===
# ==========================================================================================
#
# ✅ Esto reemplaza el estilo "Excel".
# ✅ UX simple:
#   - Izquierda: lista de preguntas (por página) + buscador
#   - Derecha: editor de la pregunta seleccionada (formulario)
#   - Botones: ⬆ Subir ⬇ Bajar 🗑 Eliminar 📄 Duplicar
#   - Agregar pregunta nueva con plantillas simples
#
# Importante:
# - El "order" controla el orden dentro de su página.
# - No cambia la lógica del export: el export toma questions_bank y lo convierte a XLSForm.
# ==========================================================================================

# ==========================================================================================
# Helpers del editor de preguntas
# ==========================================================================================
def _qb_sorted():
    qb = st.session_state.get("questions_bank", [])
    page_order = st.session_state.get("page_order", ["p1","p2","p3","p4","p5","p6","p7","p8"])
    rank = {p:i for i,p in enumerate(page_order)}
    return sorted(qb, key=lambda x: (rank.get(x.get("page",""), 999), int(x.get("order", 0))))

def _get_q_by_id(qid: str):
    qb = st.session_state.get("questions_bank", [])
    return next((q for q in qb if q.get("qid")==qid), None)

def _update_q(qid: str, new_q: dict):
    qb = st.session_state.get("questions_bank", [])
    for i, q in enumerate(qb):
        if q.get("qid")==qid:
            qb[i] = new_q
            st.session_state["questions_bank"] = qb
            return

def _delete_qid(qid: str):
    qb = st.session_state.get("questions_bank", [])
    st.session_state["questions_bank"] = [q for q in qb if q.get("qid") != qid]

def _duplicate_qid(qid: str):
    qb = st.session_state.get("questions_bank", [])
    src = next((q for q in qb if q.get("qid")==qid), None)
    if not src:
        return
    used_names = {str(q.get("row",{}).get("name","")).strip() for q in qb}
    new = {
        "qid": f"q_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "page": src.get("page","p4"),
        "order": int(src.get("order",0)) + 1,
        "row": dict(src.get("row", {}) or {})
    }
    if new["row"].get("name"):
        new["row"]["name"] = asegurar_nombre_unico(new["row"]["name"], used_names)
    qb.append(new)
    st.session_state["questions_bank"] = qb

def _reorder_within_page(page: str):
    """Normaliza order 10,20,30.. dentro de página."""
    qb = st.session_state.get("questions_bank", [])
    items = [q for q in qb if q.get("page")==page]
    items_sorted = sorted(items, key=lambda x: int(x.get("order",0)))
    o = 10
    for q in items_sorted:
        q["order"] = o
        o += 10
    # reinsert
    others = [q for q in qb if q.get("page")!=page]
    st.session_state["questions_bank"] = others + items_sorted

def _move_up(qid: str):
    qb = st.session_state.get("questions_bank", [])
    q = _get_q_by_id(qid)
    if not q:
        return
    page = q.get("page")
    items = sorted([x for x in qb if x.get("page")==page], key=lambda x: int(x.get("order",0)))
    idx = next((i for i,x in enumerate(items) if x.get("qid")==qid), None)
    if idx is None or idx == 0:
        return
    # swap orders
    items[idx]["order"], items[idx-1]["order"] = items[idx-1]["order"], items[idx]["order"]
    # write back
    others = [x for x in qb if x.get("page")!=page]
    st.session_state["questions_bank"] = others + items
    _reorder_within_page(page)

def _move_down(qid: str):
    qb = st.session_state.get("questions_bank", [])
    q = _get_q_by_id(qid)
    if not q:
        return
    page = q.get("page")
    items = sorted([x for x in qb if x.get("page")==page], key=lambda x: int(x.get("order",0)))
    idx = next((i for i,x in enumerate(items) if x.get("qid")==qid), None)
    if idx is None or idx == len(items)-1:
        return
    items[idx]["order"], items[idx+1]["order"] = items[idx+1]["order"], items[idx]["order"]
    others = [x for x in qb if x.get("page")!=page]
    st.session_state["questions_bank"] = others + items
    _reorder_within_page(page)

def _add_new_question(page: str, qtype: str, label: str):
    qb = st.session_state.get("questions_bank", [])
    max_order = max([int(q.get("order",0)) for q in qb if q.get("page")==page] + [0])
    qid = f"q_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    base_name = slugify_name(label) if label else "pregunta"
    used_names = {str(q.get("row",{}).get("name","")).strip() for q in qb}
    name = asegurar_nombre_unico(base_name, used_names)

    row = {
        "type": qtype,
        "name": name,
        "label": label,
        "required": "no",
        "appearance": "",
        "relevant": "",
        "choice_filter": "",
        "constraint": "",
        "constraint_message": "",
        "media::image": "",
        "bind::esri:fieldType": ""
    }

    # Si es note, que no cree columna por defecto
    if qtype == "note":
        row["bind::esri:fieldType"] = "null"

    qb.append({"qid": qid, "page": page, "order": max_order + 10, "row": row})
    st.session_state["questions_bank"] = qb
    _reorder_within_page(page)
    st.session_state["selected_qid"] = qid

# ==========================================================================================
# UI — Editor Fácil (solo si modo Editor)
# ==========================================================================================
if st.session_state["ui_mode"] == "Editor":
    st.markdown("---")
    st.subheader("🧩 Editor fácil de preguntas (mover / editar / borrar / duplicar / agregar)")

    # Selector de página
    pages_labels = {
        "p1": "P1 Introducción",
        "p2": "P2 Consentimiento",
        "p3": "P3 Demográficos",
        "p4": "P4 Percepción",
        "p5": "P5 Riesgos",
        "p6": "P6 Delitos",
        "p7": "P7 Victimización",
        "p8": "P8 Confianza",
    }

    colA, colB = st.columns([1.2, 2.2])

    with colA:
        page_sel = st.selectbox(
            "Página",
            options=st.session_state.get("page_order", ["p1","p2","p3","p4","p5","p6","p7","p8"]),
            format_func=lambda x: pages_labels.get(x, x),
            key="page_sel_editor"
        )

        search = st.text_input("Buscar (por label o name)", value="", key="search_q")

        # Lista de preguntas filtradas por página
        qb_page = [q for q in _qb_sorted() if q.get("page")==page_sel]
        if search.strip():
            s = search.strip().lower()
            qb_page = [
                q for q in qb_page
                if s in str(q.get("row",{}).get("label","")).lower()
                or s in str(q.get("row",{}).get("name","")).lower()
                or s in str(q.get("row",{}).get("type","")).lower()
            ]

        # Mostrar lista (simple)
        options = []
        qid_map = {}
        for q in qb_page:
            r = q.get("row", {})
            txt = f"[{r.get('type','')}] {r.get('label','(sin label)')}"
            if r.get("name"):
                txt += f"  —  ({r.get('name')})"
            options.append(txt)
            qid_map[txt] = q.get("qid")

        if not options:
            st.info("No hay preguntas en esta página con ese filtro.")
            # UI para agregar pregunta igual
            st.markdown("### ➕ Agregar pregunta")
            new_type = st.selectbox("Tipo", options=[
                "note",
                "text",
                "integer",
                "select_one yesno",
                "select_one genero",
                "select_one escolaridad",
                "select_one relacion_zona",
                "select_one seguridad_5",
                "select_one escala_1_5",
                "select_one matriz_1_5_na",
                "select_one tipo_espacio",
                "select_multiple causas_inseguridad",
                "select_multiple p12_prob_situacionales",
                "select_multiple p13_carencias_inversion",
                "select_multiple p14_consumo_drogas_donde",
                "select_multiple p15_def_infra_vial",
                "select_multiple p16_bunkeres_espacios",
                "select_multiple p17_transporte_afect",
                "select_multiple p18_presencia_policial",
                "select_multiple p19_delitos_general",
                "select_multiple p20_bunker_percepcion",
                "select_multiple p21_vida",
                "select_multiple p22_sexuales",
                "select_multiple p23_asaltos",
                "select_multiple p24_estafas",
                "select_multiple p25_robo_fuerza",
                "select_multiple p26_abandono",
                "select_multiple p27_explotacion_infantil",
                "select_multiple p28_ambientales",
                "select_multiple p29_trata",
                "select_one p30_vif",
                "select_multiple p301_tipos_vif",
                "select_one p302_medidas",
                "select_one p303_valoracion_fp",
                "select_one p31_delito_12m",
                "select_multiple p311_situaciones",
                "select_multiple p312_motivos_no_denuncia",
                "select_one p313_horario",
                "select_multiple p314_modo",
                "select_one p32_identifica_policias",
                "select_multiple p321_interacciones",
                "select_one escala_1_10",
                "select_one p38_frecuencia",
                "select_one p39_si_no_aveces",
                "select_one p41_opciones",
                "select_multiple p43_acciones_fp",
                "select_multiple p44_acciones_muni",
                "select_one p45_info_delito",
                "begin_group",
                "end_group",
                "end"
            ], key="new_q_type_empty")
            new_label = st.text_input("Texto / Label", value="", key="new_q_label_empty")
            if st.button("Agregar", type="primary", use_container_width=True, key="btn_add_empty"):
                _add_new_question(page_sel, new_type, new_label)
                st.success("Pregunta agregada.")
                st.rerun()
        else:
            selected_label = st.selectbox("Preguntas", options=options, key="q_list_select")
            selected_qid = qid_map.get(selected_label)
            st.session_state["selected_qid"] = selected_qid

            # Botones acciones rápidas
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("⬆ Subir", use_container_width=True):
                    _move_up(selected_qid); st.rerun()
            with c2:
                if st.button("⬇ Bajar", use_container_width=True):
                    _move_down(selected_qid); st.rerun()
            with c3:
                if st.button("📄 Duplicar", use_container_width=True):
                    _duplicate_qid(selected_qid); st.rerun()
            with c4:
                if st.button("🗑 Eliminar", use_container_width=True):
                    _delete_qid(selected_qid)
                    st.session_state.pop("selected_qid", None)
                    st.rerun()

            st.markdown("### ➕ Agregar pregunta")
            new_type = st.selectbox("Tipo", options=[
                "note",
                "text",
                "integer",
                "select_one yesno",
                "select_one list_canton",
                "select_one list_distrito",
                "select_one genero",
                "select_one escolaridad",
                "select_one relacion_zona",
                "select_one seguridad_5",
                "select_one escala_1_5",
                "select_one matriz_1_5_na",
                "select_one tipo_espacio",
                "select_multiple causas_inseguridad",
                "select_multiple p12_prob_situacionales",
                "select_multiple p13_carencias_inversion",
                "select_multiple p14_consumo_drogas_donde",
                "select_multiple p15_def_infra_vial",
                "select_multiple p16_bunkeres_espacios",
                "select_multiple p17_transporte_afect",
                "select_multiple p18_presencia_policial",
                "select_multiple p19_delitos_general",
                "select_multiple p20_bunker_percepcion",
                "select_multiple p21_vida",
                "select_multiple p22_sexuales",
                "select_multiple p23_asaltos",
                "select_multiple p24_estafas",
                "select_multiple p25_robo_fuerza",
                "select_multiple p26_abandono",
                "select_multiple p27_explotacion_infantil",
                "select_multiple p28_ambientales",
                "select_multiple p29_trata",
                "select_one p30_vif",
                "select_multiple p301_tipos_vif",
                "select_one p302_medidas",
                "select_one p303_valoracion_fp",
                "select_one p31_delito_12m",
                "select_multiple p311_situaciones",
                "select_multiple p312_motivos_no_denuncia",
                "select_one p313_horario",
                "select_multiple p314_modo",
                "select_one p32_identifica_policias",
                "select_multiple p321_interacciones",
                "select_one escala_1_10",
                "select_one p38_frecuencia",
                "select_one p39_si_no_aveces",
                "select_one p41_opciones",
                "select_multiple p43_acciones_fp",
                "select_multiple p44_acciones_muni",
                "select_one p45_info_delito",
                "begin_group",
                "end_group",
                "end"
            ], key="new_q_type")
            new_label = st.text_input("Texto / Label", value="", key="new_q_label")
            if st.button("Agregar nueva", type="primary", use_container_width=True):
                _add_new_question(page_sel, new_type, new_label)
                st.success("Pregunta agregada.")
                st.rerun()

    with colB:
        st.markdown("### ✏️ Editor de la pregunta seleccionada")

        qid = st.session_state.get("selected_qid")
        qobj = _get_q_by_id(qid) if qid else None

        if not qobj:
            st.info("Selecciona una pregunta de la lista para editarla.")
        else:
            row = dict(qobj.get("row", {}) or {})

            with st.form("edit_question_form"):
                st.caption("Edita los campos principales del XLSForm (survey).")

                row_type = st.text_input("type", value=str(row.get("type","")).strip())
                row_name = st.text_input("name", value=str(row.get("name","")).strip())
                row_label = st.text_area("label", value=str(row.get("label","")).strip(), height=120)

                c_req, c_app = st.columns([1, 1.2])
                with c_req:
                    req = st.selectbox("required", options=["", "yes", "no"], index=0, help="Deja vacío si no aplica.")
                    if row.get("required") in ("yes","no"):
                        req = row.get("required")
                with c_app:
                    app = st.text_input("appearance", value=str(row.get("appearance","")).strip())

                relevant = st.text_area("relevant (condición)", value=str(row.get("relevant","")).strip(), height=80)
                choice_filter = st.text_input("choice_filter", value=str(row.get("choice_filter","")).strip())

                constraint = st.text_area("constraint", value=str(row.get("constraint","")).strip(), height=80)
                constraint_message = st.text_area("constraint_message", value=str(row.get("constraint_message","")).strip(), height=80)

                media_image = st.text_input("media::image", value=str(row.get("media::image","")).strip())
                bind_esri = st.text_input("bind::esri:fieldType", value=str(row.get("bind::esri:fieldType","")).strip())

                submitted = st.form_submit_button("💾 Guardar cambios", use_container_width=True)

            if submitted:
                # Guardar
                row["type"] = row_type.strip()
                row["name"] = row_name.strip()
                row["label"] = row_label
                row["appearance"] = app.strip()

                # required
                if req.strip():
                    row["required"] = req.strip()
                else:
                    row.pop("required", None)

                # relevant/choice_filter/constraint
                if relevant.strip():
                    row["relevant"] = relevant.strip()
                else:
                    row.pop("relevant", None)

                if choice_filter.strip():
                    row["choice_filter"] = choice_filter.strip()
                else:
                    row.pop("choice_filter", None)

                if constraint.strip():
                    row["constraint"] = constraint.strip()
                else:
                    row.pop("constraint", None)

                if constraint_message.strip():
                    row["constraint_message"] = constraint_message.strip()
                else:
                    row.pop("constraint_message", None)

                if media_image.strip():
                    row["media::image"] = media_image.strip()
                else:
                    row.pop("media::image", None)

                if bind_esri.strip():
                    row["bind::esri:fieldType"] = bind_esri.strip()
                else:
                    row.pop("bind::esri:fieldType", None)

                # aplicar
                new_q = dict(qobj)
                new_q["row"] = row
                _update_q(qid, new_q)

                st.success("Cambios guardados.")
                st.rerun()
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (6/10) ====================================
# ====== PARTE 6: EDITOR FÁCIL de CHOICES (opciones) + listas nuevas + cantón/distrito =====
# ==========================================================================================
#
# ✅ Permite que cualquier persona:
# - Edite opciones de una lista (list_name)
# - Agregue/elimine/reordene opciones
# - Cree una lista nueva (por ejemplo "p99_nueva_lista")
# - Edite catálogo cantón/distrito sin tocar Excel
#
# Nota:
# - choices_bank vive en st.session_state["choices_bank"]
# - list_name + name deben ser únicos por lista
# - label es lo que ve la persona encuestada
#
# ==========================================================================================

# ==========================================================================================
# Helpers para CHOICES editor
# ==========================================================================================
def _get_choices_bank():
    return st.session_state.get("choices_bank", [])

def _set_choices_bank(rows):
    st.session_state["choices_bank"] = rows

def _list_names():
    rows = _get_choices_bank()
    names = sorted({str(r.get("list_name","")).strip() for r in rows if str(r.get("list_name","")).strip()})
    return names

def _choices_for_list(list_name: str):
    rows = _get_choices_bank()
    return [r for r in rows if str(r.get("list_name","")).strip() == list_name]

def _delete_choice(list_name: str, name_value: str):
    rows = _get_choices_bank()
    rows = [r for r in rows if not (str(r.get("list_name","")).strip()==list_name and str(r.get("name","")).strip()==name_value)]
    _set_choices_bank(rows)

def _upsert_choice(row: dict):
    """Inserta o actualiza (list_name,name)."""
    rows = _get_choices_bank()
    ln = str(row.get("list_name","")).strip()
    nm = str(row.get("name","")).strip()
    updated = False
    for i, r in enumerate(rows):
        if str(r.get("list_name","")).strip()==ln and str(r.get("name","")).strip()==nm:
            rows[i] = row
            updated = True
            break
    if not updated:
        rows.append(row)
    _set_choices_bank(rows)

def _create_list_if_missing(list_name: str):
    if list_name not in _list_names():
        # crear placeholder mínimo para que aparezca
        _upsert_choice({"list_name": list_name, "name": "opcion_1", "label": "Opción 1"})

def _unique_name_in_list(list_name: str, desired: str):
    desired = slugify_name(desired) if desired else "opcion"
    rows = _choices_for_list(list_name)
    used = {str(r.get("name","")).strip() for r in rows}
    return asegurar_nombre_unico(desired, used)

def _reorder_choices_in_list(list_name: str, names_in_order: list[str]):
    """
    En XLSForm el orden es el orden de filas en choices.
    Aquí reordenamos el bank para que quede exactamente como names_in_order,
    y preservamos otras listas.
    """
    rows = _get_choices_bank()
    this = [r for r in rows if str(r.get("list_name","")).strip()==list_name]
    other = [r for r in rows if str(r.get("list_name","")).strip()!=list_name]

    m = {str(r.get("name","")).strip(): r for r in this}
    new_this = []
    for nm in names_in_order:
        if nm in m:
            new_this.append(m[nm])
    # agregar los que no estaban (por si acaso)
    for nm, r in m.items():
        if nm not in names_in_order:
            new_this.append(r)

    _set_choices_bank(other + new_this)

# ==========================================================================================
# UI — Editor Fácil de CHOICES
# ==========================================================================================
if st.session_state["ui_mode"] == "Editor":
    st.markdown("---")
    st.subheader("🧾 Editor fácil de opciones (choices)")

    colL, colR = st.columns([1.2, 2.2])

    with colL:
        st.markdown("### Listas disponibles")

        # Crear lista nueva
        new_list = st.text_input("➕ Crear lista nueva (list_name)", value="", placeholder="ej: p99_nueva_lista")
        if st.button("Crear lista", use_container_width=True):
            if not new_list.strip():
                st.warning("Escribe un list_name.")
            else:
                ln = slugify_name(new_list.strip())
                _create_list_if_missing(ln)
                st.session_state["selected_list_name"] = ln
                st.success(f"Lista creada: {ln}")
                st.rerun()

        lists = _list_names()
        if not lists:
            st.info("Aún no hay listas en choices_bank.")
        else:
            selected_list = st.selectbox("Selecciona una lista", options=lists, key="selected_list_name")
            st.caption("Tip: list_canton y list_distrito también se editan aquí.")

            # Búsqueda dentro de lista
            s2 = st.text_input("Buscar opción (label/name)", value="", key="search_choice")

            rows_list = _choices_for_list(selected_list)
            # filtrar
            if s2.strip():
                ss = s2.strip().lower()
                rows_list = [
                    remember for remember in rows_list
                    if ss in str(remember.get("label","")).lower()
                    or ss in str(remember.get("name","")).lower()
                ]

            # mostrar opciones como lista
            opt_labels = []
            for r in rows_list:
                opt_labels.append(f"{r.get('label','(sin label)')}  —  ({r.get('name','')})")

            if not opt_labels:
                st.info("No hay opciones con ese filtro.")
            else:
                selected_opt_display = st.selectbox("Opciones", options=opt_labels, key="selected_choice_display")

                # extraer name del display
                # display termina con "(name)"
                name_value = selected_opt_display.split("(")[-1].replace(")", "").strip()
                st.session_state["selected_choice_name"] = name_value

                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("⬆ Subir", use_container_width=True):
                        # reordenar
                        all_rows = _choices_for_list(selected_list)
                        all_names = [str(r.get("name","")).strip() for r in all_rows]
                        i = all_names.index(name_value) if name_value in all_names else -1
                        if i > 0:
                            all_names[i], all_names[i-1] = all_names[i-1], all_names[i]
                            _reorder_choices_in_list(selected_list, all_names)
                            st.rerun()
                with c2:
                    if st.button("⬇ Bajar", use_container_width=True):
                        all_rows = _choices_for_list(selected_list)
                        all_names = [str(r.get("name","")).strip() for r in all_rows]
                        i = all_names.index(name_value) if name_value in all_names else -1
                        if 0 <= i < len(all_names)-1:
                            all_names[i], all_names[i+1] = all_names[i+1], all_names[i]
                            _reorder_choices_in_list(selected_list, all_names)
                            st.rerun()
                with c3:
                    if st.button("🗑 Eliminar", use_container_width=True):
                        _delete_choice(selected_list, name_value)
                        st.session_state.pop("selected_choice_name", None)
                        st.rerun()

        # Agregar opción nueva a lista seleccionada
        if lists:
            st.markdown("### ➕ Agregar opción")
            add_label = st.text_input("Label (lo que ve la persona)", value="", key="add_choice_label")
            add_name_hint = st.text_input("Name (opcional, se autogenera si lo dejas vacío)", value="", key="add_choice_name")
            extra_col_key = st.text_input("Extra columna (opcional) ej: canton_key", value="", key="add_choice_extra_key")
            extra_col_val = st.text_input("Valor extra (opcional)", value="", key="add_choice_extra_val")

            if st.button("Agregar opción", type="primary", use_container_width=True):
                if not add_label.strip():
                    st.warning("Debes escribir el label.")
                else:
                    ln = st.session_state.get("selected_list_name")
                    if not ln:
                        st.warning("Selecciona una lista.")
                    else:
                        nm = add_name_hint.strip() or add_label.strip()
                        nm = _unique_name_in_list(ln, nm)
                        row = {"list_name": ln, "name": nm, "label": add_label.strip()}
                        if extra_col_key.strip():
                            row[extra_col_key.strip()] = extra_col_val.strip()
                        _upsert_choice(row)
                        st.success("Opción agregada.")
                        st.rerun()

    with colR:
        st.markdown("### ✏️ Editor de la opción seleccionada")

        ln = st.session_state.get("selected_list_name")
        nm = st.session_state.get("selected_choice_name")

        if not ln or not nm:
            st.info("Selecciona una lista y una opción para editar.")
        else:
            # buscar row exacta
            rows = _choices_for_list(ln)
            row = next((r for r in rows if str(r.get("name","")).strip()==nm), None)
            if not row:
                st.info("La opción ya no existe.")
            else:
                row = dict(row)

                # detectar columnas extra existentes en la lista (ej canton_key)
                extra_keys = [k for k in row.keys() if k not in ("list_name","name","label")]
                extra_key = extra_keys[0] if extra_keys else ""

                with st.form("edit_choice_form"):
                    list_name = st.text_input("list_name", value=str(row.get("list_name","")).strip(), disabled=True)
                    name_val = st.text_input("name", value=str(row.get("name","")).strip())
                    label_val = st.text_input("label", value=str(row.get("label","")).strip())

                    st.caption("Columnas extra (si las necesita, ej: canton_key para list_distrito)")
                    extra_k = st.text_input("extra key", value=extra_key)
                    extra_v = st.text_input("extra value", value=str(row.get(extra_key,"")) if extra_key else "")

                    save = st.form_submit_button("💾 Guardar opción", use_container_width=True)

                if save:
                    # si cambiaron name: validar unicidad
                    new_name = name_val.strip()
                    if not new_name:
                        st.warning("El 'name' no puede quedar vacío.")
                    else:
                        # si name cambió: asegurar no duplicar
                        if new_name != nm:
                            used = {str(r.get("name","")).strip() for r in rows}
                            if new_name in used:
                                st.warning("Ya existe una opción con ese 'name' en esta lista.")
                                st.stop()
                            # borrar la vieja
                            _delete_choice(ln, nm)

                        # construir row nueva
                        new_row = {"list_name": ln, "name": new_name, "label": label_val.strip()}

                        # extra
                        if extra_k.strip():
                            new_row[extra_k.strip()] = extra_v.strip()

                        _upsert_choice(new_row)

                        # si list_distrito/list_canton, sincronizar hacia choices_ext_rows (compatibilidad)
                        sync_canton_distrito_to_choices_ext_rows()

                        st.success("Opción actualizada.")
                        st.session_state["selected_choice_name"] = new_name
                        st.rerun()
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (7/10) ====================================
# ====== PARTE 7: EDITOR FÁCIL de GLOSARIOS (términos + definiciones por página) ============
# ==========================================================================================
#
# ✅ Permite:
# - Ver todos los glosarios existentes
# - Agregar términos nuevos con su definición
# - Editar definiciones existentes
# - Eliminar términos
# - Asignar qué términos aparecen en cada página (P4–P8, o cualquiera)
#
# Diseño:
# - Izquierda: lista de términos
# - Derecha: editor del término seleccionado
# - Abajo: selector por página (checkboxes)
#
# Datos:
# - st.session_state["glossary_bank"] = {
#       "Extorsión": {"def": "...", "pages": ["p4","p6"]},
#       ...
#   }
#
# ==========================================================================================

# ==========================================================================================
# Inicialización segura del glosario
# ==========================================================================================
if "glossary_bank" not in st.session_state:
    # Precarga desde el GLOSARIO_DEFINICIONES original
    st.session_state["glossary_bank"] = {
        k: {"def": v, "pages": []}
        for k, v in GLOSARIO_DEFINICIONES.items()
    }

# ==========================================================================================
# Helpers glosario
# ==========================================================================================
def _get_glossary():
    return st.session_state.get("glossary_bank", {})

def _set_glossary(g):
    st.session_state["glossary_bank"] = g

def _sorted_terms():
    return sorted(_get_glossary().keys(), key=lambda x: x.lower())

def _delete_term(term: str):
    g = _get_glossary()
    if term in g:
        g.pop(term)
        _set_glossary(g)

def _rename_term(old: str, new: str):
    g = _get_glossary()
    if old not in g or not new.strip():
        return
    g[new] = g.pop(old)
    _set_glossary(g)

# ==========================================================================================
# UI — Editor de Glosarios
# ==========================================================================================
if st.session_state["ui_mode"] == "Editor":
    st.markdown("---")
    st.subheader("📘 Editor de glosarios (términos y definiciones)")

    pages_labels = {
        "p1": "P1 Introducción",
        "p2": "P2 Consentimiento",
        "p3": "P3 Demográficos",
        "p4": "P4 Percepción",
        "p5": "P5 Riesgos",
        "p6": "P6 Delitos",
        "p7": "P7 Victimización",
        "p8": "P8 Confianza",
    }

    colL, colR = st.columns([1.2, 2.2])

    # --------------------------------------------------------------------------------------
    # Columna izquierda: términos
    # --------------------------------------------------------------------------------------
    with colL:
        st.markdown("### Términos")

        # Agregar término nuevo
        new_term = st.text_input("➕ Nuevo término", value="", placeholder="Ej: Microtráfico")
        if st.button("Agregar término", use_container_width=True):
            if not new_term.strip():
                st.warning("Escribe un término.")
            else:
                g = _get_glossary()
                if new_term.strip() in g:
                    st.warning("Ese término ya existe.")
                else:
                    g[new_term.strip()] = {"def": "", "pages": []}
                    _set_glossary(g)
                    st.session_state["selected_glossary_term"] = new_term.strip()
                    st.success("Término agregado.")
                    st.rerun()

        terms = _sorted_terms()
        if not terms:
            st.info("No hay términos en el glosario.")
        else:
            sel = st.selectbox(
                "Selecciona un término",
                options=terms,
                key="selected_glossary_term"
            )

            c1, c2 = st.columns(2)
            with c1:
                if st.button("🗑 Eliminar término", use_container_width=True):
                    _delete_term(sel)
                    st.session_state.pop("selected_glossary_term", None)
                    st.rerun()
            with c2:
                st.caption("Tip: puedes renombrar el término desde el editor.")

    # --------------------------------------------------------------------------------------
    # Columna derecha: editor del término
    # --------------------------------------------------------------------------------------
    with colR:
        term = st.session_state.get("selected_glossary_term")
        if not term or term not in _get_glossary():
            st.info("Selecciona un término para editarlo.")
        else:
            g = _get_glossary()
            data = dict(g.get(term, {}))

            with st.form("edit_glossary_form"):
                st.markdown(f"### ✏️ Editar término: **{term}**")

                new_name = st.text_input("Nombre del término", value=term)
                definition = st.text_area(
                    "Definición",
                    value=str(data.get("def","")),
                    height=180,
                    help="Esta definición se mostrará como NOTE dentro del glosario de la página."
                )

                st.markdown("### 📄 Páginas donde aparece este término")
                pages = st.session_state.get("page_order", ["p1","p2","p3","p4","p5","p6","p7","p8"])
                pages_sel = []
                for p in pages:
                    if st.checkbox(
                        pages_labels.get(p, p),
                        value=(p in data.get("pages", [])),
                        key=f"gloss_page_{p}"
                    ):
                        pages_sel.append(p)

                save = st.form_submit_button("💾 Guardar cambios", use_container_width=True)

            if save:
                # renombrar si aplica
                if new_name.strip() != term:
                    _rename_term(term, new_name.strip())
                    term = new_name.strip()

                # guardar definición y páginas
                g = _get_glossary()
                g[term]["def"] = definition.strip()
                g[term]["pages"] = pages_sel
                _set_glossary(g)

                st.success("Glosario actualizado.")
                st.session_state["selected_glossary_term"] = term
                st.rerun()
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (8/10) ====================================
# ====== PARTE 8: EXPORTADOR XLSForm desde BANKS + inyección glosarios por página ===========
# ==========================================================================================
#
# ✅ Esta parte es CLAVE:
# - Toma questions_bank (orden, páginas, rows editables)
# - Toma choices_bank (listas editables)
# - Toma glossary_bank (términos y páginas asignadas)
# - Construye df_survey, df_choices, df_settings
# - Descarga XLSForm + logo (igual que antes)
#
# Regla glosario:
# - Por cada página, si hay términos asignados:
#   - agrega select_one yesno "¿Desea acceder al glosario...?"
#   - si Sí => begin_group Glosario + notes con definiciones + end_group
#
# ==========================================================================================

def _survey_cols():
    return [
        "type", "name", "label", "required", "appearance",
        "relevant", "choice_filter",
        "constraint", "constraint_message",
        "media::image",
        "bind::esri:fieldType"
    ]

def _coerce_survey_row(row: dict) -> dict:
    """Normaliza llaves para que el export sea estable."""
    r = dict(row or {})
    # asegurar todas llaves
    for k in _survey_cols():
        if k not in r:
            r[k] = ""
    # si es note y bind vacío => null
    if str(r.get("type","")).strip() == "note" and not str(r.get("bind::esri:fieldType","")).strip():
        r["bind::esri:fieldType"] = "null"
    return r

def _build_survey_from_questions_bank():
    qb = _qb_sorted()
    survey_rows = []
    for q in qb:
        row = _coerce_survey_row(q.get("row", {}))
        survey_rows.append(row)
    return survey_rows

def _build_choices_from_bank():
    """choices_bank es la fuente principal."""
    return list(_get_choices_bank())

def _build_glossary_injections(v_si: str):
    """
    Construye un dict:
      page -> list of survey_rows adicionales (glosario)
    Se inyecta antes del end_group de cada página (si existe), o al final.
    """
    g = _get_glossary()
    injections = {}  # page -> [rows...]

    def add_for_page(page: str, rows: list[dict]):
        if page not in injections:
            injections[page] = []
        injections[page].extend(rows)

    # términos por página
    pages = st.session_state.get("page_order", ["p1","p2","p3","p4","p5","p6","p7","p8"])
    for p in pages:
        # encontrar términos que tienen esta página
        terms = [t for t, data in g.items() if p in (data.get("pages") or []) and str(data.get("def","")).strip()]
        if not terms:
            continue

        # relevant base: intentar tomar relevant del begin_group de esa página si existe, si no "".
        # (Esto mantiene tu lógica de "acepta participar" sin pedirlo manual.)
        rel_base = ""
        qb = _qb_sorted()
        for q in qb:
            rr = q.get("row", {})
            if str(q.get("page")) == p and str(rr.get("type","")).strip() == "begin_group":
                rel_base = str(rr.get("relevant","")).strip()
                break
        if not rel_base:
            rel_base = ""  # sin relevant

        # pregunta "accede glosario"
        acc_name = f"{p}_accede_glosario"
        rel_acc = rel_base if rel_base else ""

        rows_out = []
        rows_out.append(_coerce_survey_row({
            "type": "select_one yesno",
            "name": acc_name,
            "label": "¿Desea acceder al glosario de esta sección?",
            "required": "no",
            "appearance": "minimal",
            "relevant": rel_acc
        }))

        # relevant del bloque glosario
        if rel_base:
            rel_glos = f"({rel_base}) and (${{{acc_name}}}='{v_si}')"
        else:
            rel_glos = f"${{{acc_name}}}='{v_si}'"

        rows_out.append(_coerce_survey_row({
            "type": "begin_group",
            "name": f"{p}_glosario",
            "label": "Glosario",
            "relevant": rel_glos
        }))

        rows_out.append(_coerce_survey_row({
            "type": "note",
            "name": f"{p}_glosario_intro",
            "label": "A continuación, se muestran definiciones de términos que aparecen en esta sección.",
            "relevant": rel_glos,
            "bind::esri:fieldType": "null"
        }))

        for idx, t in enumerate(terms, start=1):
            rows_out.append(_coerce_survey_row({
                "type": "note",
                "name": f"{p}_glos_{idx}",
                "label": str(g[t]["def"]),
                "relevant": rel_glos,
                "bind::esri:fieldType": "null"
            }))

        rows_out.append(_coerce_survey_row({
            "type": "note",
            "name": f"{p}_glosario_cierre",
            "label": "Para continuar con la encuesta, desplácese hacia arriba y continúe con normalidad.",
            "relevant": rel_glos,
            "bind::esri:fieldType": "null"
        }))

        rows_out.append(_coerce_survey_row({
            "type": "end_group",
            "name": f"{p}_glosario_end"
        }))

        add_for_page(p, rows_out)

    return injections

def _inject_glossaries_into_survey(survey_rows: list[dict], injections: dict):
    """
    Inserta rows del glosario antes del end_group final de cada página (si existe).
    Las páginas se identifican por su begin_group name: pX_...
    Pero como el bank ya tiene page en qobj, aquí hacemos un truco:
    - Buscamos el "end_group" cuyo name sea "pX_end" si existe
    - Si no existe, lo agrega al final de la encuesta
    """
    out = []
    pages = st.session_state.get("page_order", ["p1","p2","p3","p4","p5","p6","p7","p8"])

    # indexar posición de inserción por name pX_end
    end_name_to_page = {f"{p}_end": p for p in pages}

    for r in survey_rows:
        # si encontramos end de página, antes inyectamos
        if str(r.get("type","")).strip() == "end_group":
            nm = str(r.get("name","")).strip()
            if nm in end_name_to_page:
                p = end_name_to_page[nm]
                if p in injections and injections[p]:
                    out.extend(injections[p])
        out.append(r)

    # si alguna página no tenía end_group detectado, inyectamos al final (fallback)
    for p, rows in injections.items():
        has_end = any(str(rr.get("type","")).strip()=="end_group" and str(rr.get("name","")).strip()==f"{p}_end" for rr in survey_rows)
        if not has_end:
            out.extend(rows)

    return out

def construir_xlsform_desde_banks(form_title: str, logo_media_name: str, idioma: str, version: str):
    # values yes/no: deben corresponder a choices yesno (name generado con slugify)
    v_si = slugify_name("Sí")

    survey_rows = _build_survey_from_questions_bank()
    injections = _build_glossary_injections(v_si=v_si)
    survey_rows = _inject_glossaries_into_survey(survey_rows, injections)

    choices_rows = _build_choices_from_bank()

    # DF survey
    df_survey = pd.DataFrame(survey_rows, columns=_survey_cols()).fillna("")

    # DF choices (respetar columnas extra)
    cols = set()
    for r in choices_rows:
        cols.update(r.keys())
    base = ["list_name", "name", "label"]
    for k in sorted(cols):
        if k not in base:
            base.append(k)
    df_choices = pd.DataFrame(choices_rows, columns=base).fillna("")

    # DF settings
    df_settings = pd.DataFrame([{
        "form_title": form_title,
        "version": version,
        "default_language": idioma,
        "style": "pages"
    }], columns=["form_title", "version", "default_language", "style"]).fillna("")

    return df_survey, df_choices, df_settings

# ==========================================================================================
# UI — Botón de export (usa banks)
# ==========================================================================================
st.markdown("---")
st.subheader("📦 Exportar XLSForm (desde el editor)")

idioma = st.selectbox("Idioma (default_language)", options=["es", "en"], index=0, key="export_lang")
version_auto = datetime.now().strftime("%Y%m%d%H%M")
version = st.text_input("Versión (settings.version)", value=version_auto, key="export_version")

if st.button("🧮 Construir XLSForm (Editor → XLSForm)", use_container_width=True, key="btn_export_banks"):
    # Validaciones básicas
    qb = st.session_state.get("questions_bank", [])
    if not qb:
        st.error("No hay preguntas en questions_bank. (seed falló o fue borrado).")
        st.stop()

    df_survey, df_choices, df_settings = construir_xlsform_desde_banks(
        form_title=form_title,
        logo_media_name=logo_media_name,
        idioma=idioma,
        version=version.strip() or version_auto
    )

    st.success("XLSForm construido desde el editor. Vista previa rápida:")
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
    descargar_xlsform(df_survey, df_choices, df_settings, nombre_archivo)

    # logo
    if st.session_state.get("_logo_bytes"):
        st.download_button(
            "📥 Descargar logo para carpeta media/",
            data=st.session_state["_logo_bytes"],
            file_name=logo_media_name,
            mime="image/png",
            use_container_width=True
        )

    st.info("""
**Cómo usar en Survey123 Connect**
1) Crear encuesta **desde archivo** y seleccionar el XLSForm descargado.  
2) Copiar el logo dentro de la carpeta **media/** del proyecto, con el **mismo nombre** que pusiste en `media::image`.  
3) Verás páginas con **Siguiente/Anterior** (porque `settings.style = pages`).  
4) Los glosarios aparecen por página solo si la persona marca **Sí**.
""")
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (9/10) ====================================
# ====== PARTE 9: GUARDAR / CARGAR “PROYECTO” (JSON) + VALIDACIONES + REPARACIÓN RÁPIDA =====
# ==========================================================================================
#
# ✅ Esto hace que cualquier persona pueda:
# - Guardar TODO lo que editó (preguntas + choices + glosarios + catálogo) en un JSON
# - Cargarlo después y seguir editando (sin perder nada)
# - Restaurar a “precargado original” (re-seed)
# - Correr validaciones para evitar errores en Survey123 (names duplicados, end_group faltante, etc.)
#
# 📌 Importante:
# - Guardar/Cargar es la forma más fácil de “persistir” cambios en Streamlit Cloud/local.
# - No dependes de Excel para editar.
#
# ==========================================================================================

import json

# ==========================================================================================
# Helpers de serialización
# ==========================================================================================
def _export_project_dict():
    return {
        "meta": {
            "app": "Encuesta Comunidad XLSForm Editor",
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "form_title": form_title,
            "logo_media_name": logo_media_name,
        },
        "page_order": st.session_state.get("page_order", ["p1","p2","p3","p4","p5","p6","p7","p8"]),
        "questions_bank": st.session_state.get("questions_bank", []),
        "choices_bank": st.session_state.get("choices_bank", []),
        "glossary_bank": st.session_state.get("glossary_bank", {}),
        # compatibilidad con tu catálogo anterior
        "choices_ext_rows": st.session_state.get("choices_ext_rows", []),
    }

def _load_project_dict(d: dict):
    # defensivo: si falta algo, no revienta
    st.session_state["page_order"] = d.get("page_order", ["p1","p2","p3","p4","p5","p6","p7","p8"])
    st.session_state["questions_bank"] = d.get("questions_bank", [])
    st.session_state["choices_bank"] = d.get("choices_bank", [])
    st.session_state["glossary_bank"] = d.get("glossary_bank", {})
    st.session_state["choices_ext_rows"] = d.get("choices_ext_rows", [])

    # seleccionar defaults
    if st.session_state["questions_bank"]:
        st.session_state["selected_qid"] = st.session_state["questions_bank"][0].get("qid")
    # sincronizar catálogo hacia choices_ext_rows si aplica
    sync_canton_distrito_to_choices_ext_rows()

def _download_project_json():
    d = _export_project_dict()
    data = json.dumps(d, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button(
        "💾 Descargar proyecto (JSON)",
        data=data,
        file_name=f"{slugify_name(form_title)}_proyecto.json",
        mime="application/json",
        use_container_width=True
    )

def _read_uploaded_json(uploaded_file):
    try:
        raw = uploaded_file.read()
        d = json.loads(raw.decode("utf-8"))
        return d, None
    except Exception as e:
        return None, str(e)

# ==========================================================================================
# Validaciones y reparación rápida
# ==========================================================================================
def _validate_unique_question_names():
    qb = st.session_state.get("questions_bank", [])
    seen = {}
    dupes = []
    for q in qb:
        r = q.get("row", {}) or {}
        nm = str(r.get("name","")).strip()
        tp = str(r.get("type","")).strip()
        # begin/end_group pueden repetir? normal: name debe ser único igual, mejor exigirlo.
        if nm:
            if nm in seen:
                dupes.append((nm, seen[nm], q.get("qid")))
            else:
                seen[nm] = q.get("qid")
        # type vacío es mala señal
        if not tp:
            dupes.append(("[type vacío]", q.get("qid"), q.get("qid")))
    return dupes

def _validate_groups_balance():
    """Revisa begin_group / end_group global."""
    qb = _qb_sorted()
    stack = []
    issues = []
    for q in qb:
        tp = str((q.get("row", {}) or {}).get("type","")).strip()
        nm = str((q.get("row", {}) or {}).get("name","")).strip()
        if tp == "begin_group":
            stack.append(nm or "(begin_group sin name)")
        elif tp == "end_group":
            if not stack:
                issues.append(f"end_group sin begin_group previo: {nm}")
            else:
                stack.pop()
    if stack:
        issues.append(f"Faltan end_group para {len(stack)} begin_group (ej: {stack[-1]})")
    return issues

def _validate_choices_unique_in_list():
    rows = st.session_state.get("choices_bank", [])
    seen = set()
    dupes = []
    for r in rows:
        ln = str(r.get("list_name","")).strip()
        nm = str(r.get("name","")).strip()
        if not ln or not nm:
            continue
        key = (ln, nm)
        if key in seen:
            dupes.append(key)
        else:
            seen.add(key)
    return dupes

def _repair_duplicate_question_names():
    """
    Si hay names duplicados en survey, los renombra automáticamente agregando _2 _3...
    (No toca references en relevant/constraints, así que úsalo solo si ocupas salir del paso).
    """
    qb = st.session_state.get("questions_bank", [])
    used = set()
    for q in qb:
        r = q.get("row", {}) or {}
        nm = str(r.get("name","")).strip()
        if not nm:
            continue
        if nm not in used:
            used.add(nm)
        else:
            new_nm = asegurar_nombre_unico(nm, used)
            r["name"] = new_nm
            q["row"] = r
            used.add(new_nm)
    st.session_state["questions_bank"] = qb

def _repair_missing_note_bind_null():
    """Asegura que notes no creen columnas."""
    qb = st.session_state.get("questions_bank", [])
    changed = 0
    for q in qb:
        r = q.get("row", {}) or {}
        if str(r.get("type","")).strip() == "note":
            if str(r.get("bind::esri:fieldType","")).strip() != "null":
                r["bind::esri:fieldType"] = "null"
                q["row"] = r
                changed += 1
    st.session_state["questions_bank"] = qb
    return changed

# ==========================================================================================
# UI — Guardar/Cargar + Validaciones
# ==========================================================================================
st.markdown("---")
st.subheader("🗂️ Guardar / Cargar proyecto (JSON) + Validaciones")

col1, col2 = st.columns([1.2, 1.8])

with col1:
    st.markdown("### 💾 Guardar")
    _download_project_json()
    st.caption("Guarda preguntas + choices + glosarios + catálogo para reutilizar y seguir editando.")

    st.markdown("### 📥 Cargar")
    up = st.file_uploader("Subir proyecto JSON", type=["json"], key="project_json_uploader")
    if up is not None:
        d, err = _read_uploaded_json(up)
        if err:
            st.error(f"Error leyendo JSON: {err}")
        else:
            if st.button("Cargar proyecto ahora", type="primary", use_container_width=True):
                _load_project_dict(d)
                st.success("Proyecto cargado.")
                st.rerun()

with col2:
    st.markdown("### ✅ Validaciones rápidas (recomendado antes de exportar)")

    if st.button("Validar proyecto", use_container_width=True):
        dup_q = _validate_unique_question_names()
        grp = _validate_groups_balance()
        dup_c = _validate_choices_unique_in_list()

        if not dup_q and not grp and not dup_c:
            st.success("Todo OK: no se detectaron problemas críticos.")
        else:
            if dup_q:
                st.warning("⚠️ Names duplicados o type vacío en survey (puede romper Survey123):")
                st.write(dup_q[:20])
                if len(dup_q) > 20:
                    st.caption(f"... y {len(dup_q)-20} más")

            if grp:
                st.warning("⚠️ Problemas de begin_group/end_group:")
                for x in grp:
                    st.write(f"- {x}")

            if dup_c:
                st.warning("⚠️ Duplicados en choices (mismo list_name+name):")
                st.write(dup_c[:25])
                if len(dup_c) > 25:
                    st.caption(f"... y {len(dup_c)-25} más")

    st.markdown("### 🛠️ Reparación rápida (si te salió un error como el de la imagen)")
    cA, cB, cC = st.columns(3)
    with cA:
        if st.button("Fix notes (null)", use_container_width=True):
            n = _repair_missing_note_bind_null()
            st.success(f"Listo: {n} note(s) ajustadas a bind::esri:fieldType='null'.")
            st.rerun()
    with cB:
        if st.button("Fix names duplicados", use_container_width=True):
            _repair_duplicate_question_names()
            st.success("Listo: names duplicados renombrados automáticamente.")
            st.rerun()
    with cC:
        if st.button("Re-seed precargado", use_container_width=True):
            # reinicia banks
            st.session_state.pop("questions_bank", None)
            st.session_state.pop("choices_bank", None)
            st.session_state.pop("glossary_bank", None)
            # vuelve a crear banks base
            init_banks_if_needed()
            seed_questions_bank_if_missing(form_title=form_title, logo_media_name=logo_media_name)
            st.success("Restaurado a versión precargada.")
            st.rerun()
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (10/10) ===================================
# ====== PARTE 10: ARRANQUE FINAL + CABLEADO COMPLETO (init + seed + menú + run) ===========
# ==========================================================================================
#
# ✅ Esta parte integra TODO para que:
# - Al abrir la app, las preguntas precargadas se vean en el editor (sí, se ven).
# - No aparezca la “tabla tipo Excel” como editor principal.
# - Funcione: Preguntas (Parte 5) + Choices (Parte 6) + Glosario (Parte 7) + Export (Parte 8)
# - Funcione guardar/cargar (Parte 9)
#
# 📌 Importantísimo:
# - NO borres tus helpers anteriores (slugify_name, asegurar_nombre_unico, descargar_xlsform, etc.)
# - Esta parte asume que ya pegaste Partes 1–9 en orden.
#
# ==========================================================================================

# ==========================================================================================
# 1) Inicialización de BANKS (si no existen)
# ==========================================================================================
def init_banks_if_needed():
    if "ui_mode" not in st.session_state:
        st.session_state["ui_mode"] = "Editor"   # por defecto, editor fácil

    if "page_order" not in st.session_state:
        st.session_state["page_order"] = ["p1","p2","p3","p4","p5","p6","p7","p8"]

    if "questions_bank" not in st.session_state:
        st.session_state["questions_bank"] = []

    if "choices_bank" not in st.session_state:
        st.session_state["choices_bank"] = []

    if "glossary_bank" not in st.session_state:
        st.session_state["glossary_bank"] = {}

    if "choices_ext_rows" not in st.session_state:
        st.session_state["choices_ext_rows"] = []


# ==========================================================================================
# 2) Seed de CHOICES (las listas base) — se hace una sola vez
# ==========================================================================================
def seed_choices_bank_if_missing():
    rows = st.session_state.get("choices_bank", [])
    if rows:
        return

    choices_rows = []
    # Reutilizamos tu función add_choice_list original (ya existente arriba)
    add_choice_list(choices_rows, "yesno", ["Sí", "No"])
    add_choice_list(choices_rows, "genero", ["Femenino", "Masculino", "Persona No Binaria", "Prefiero no decir"])
    add_choice_list(choices_rows, "escolaridad", [
        "Ninguna","Primaria incompleta","Primaria completa","Secundaria incompleta","Secundaria completa",
        "Técnico","Universitaria incompleta","Universitaria completa",
    ])
    add_choice_list(choices_rows, "relacion_zona", ["Vivo en la zona", "Trabajo en la zona", "Visito la zona", "Estudio en la zona"])

    add_choice_list(choices_rows, "seguridad_5", ["Muy inseguro", "Inseguro", "Ni seguro ni inseguro", "Seguro", "Muy seguro"])
    add_choice_list(choices_rows, "escala_1_5", [
        "1 (Mucho Menos Seguro)","2 (Menos Seguro)","3 (Se mantiene igual)","4 (Más Seguro)","5 (Mucho Más Seguro)",
    ])
    add_choice_list(choices_rows, "matriz_1_5_na", [
        "Muy inseguro (1)","Inseguro (2)","Ni seguro ni inseguro (3)","Seguro (4)","Muy seguro (5)","No aplica"
    ])
    add_choice_list(choices_rows, "tipo_espacio", [
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
    ])

    # Todas tus listas (causas_71, p12...p45) se mantienen como en tu código.
    # Para no duplicar enorme bloque aquí, asumo que ya las agregaste en Partes 1–4.
    # ✅ Si en tus Partes 1–4 ya existe _construir_choices_y_base o algo equivalente, úsalo.
    #
    # Aquí vamos a inyectar también el catálogo cantón/distrito desde choices_ext_rows (si existe):
    for r in st.session_state.get("choices_ext_rows", []):
        choices_rows.append(dict(r))

    st.session_state["choices_bank"] = choices_rows


# ==========================================================================================
# 3) Seed de QUESTIONS (preguntas precargadas en banks)
# ==========================================================================================
def seed_questions_bank_if_missing(form_title: str, logo_media_name: str):
    qb = st.session_state.get("questions_bank", [])
    if qb:
        return

    # tomamos tu XLSForm original y lo convertimos en bank editable
    # usando la función construir_xlsform_final (ya existe en tus partes anteriores)
    df_survey, df_choices, df_settings = construir_xlsform_final(
        form_title=form_title,
        logo_media_name=logo_media_name,
        idioma="es",
        version="seed"
    )

    # 1) choices_bank desde df_choices (para que coincida con el seed real)
    choices_rows = df_choices.to_dict(orient="records")
    st.session_state["choices_bank"] = choices_rows

    # 2) questions_bank desde df_survey: asignar página por heurística
    #    (en Partes 1–4 tu XLSForm ya tiene names p1_end, p2_end... etc)
    qb_out = []
    current_page = "p1"
    order = 10

    def _infer_page_from_name(nm: str):
        nm = (nm or "").strip()
        # detecta p1_..., p2_..., etc
        for p in st.session_state.get("page_order", ["p1","p2","p3","p4","p5","p6","p7","p8"]):
            if nm.startswith(p + "_"):
                return p
        return None

    for row in df_survey.to_dict(orient="records"):
        # inferir página por name
        nm = str(row.get("name",""))
        inferred = _infer_page_from_name(nm)
        if inferred:
            current_page = inferred

        # reset order si cambia página por primera vez
        # (solo cuando detecta un begin_group de esa página)
        if str(row.get("type","")).strip() == "begin_group":
            pg = _infer_page_from_name(nm) or current_page
            current_page = pg
            order = 10

        qid = f"q_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{len(qb_out)}"
        qb_out.append({
            "qid": qid,
            "page": current_page,
            "order": order,
            "row": dict(row)
        })
        order += 10

    st.session_state["questions_bank"] = qb_out

    # 3) glosario: precarga el tuyo
    if "glossary_bank" not in st.session_state or not st.session_state["glossary_bank"]:
        st.session_state["glossary_bank"] = {
            k: {"def": v, "pages": []}
            for k, v in GLOSARIO_DEFINICIONES.items()
        }

    # seleccionar la primera pregunta para edición
    if qb_out:
        st.session_state["selected_qid"] = qb_out[0]["qid"]


# ==========================================================================================
# 4) Sincronización catálogo cantón/distrito (compatibilidad)
# ==========================================================================================
def sync_canton_distrito_to_choices_ext_rows():
    """
    Mantiene choices_ext_rows actualizado desde choices_bank:
    - list_canton: list_name, name, label
    - list_distrito: list_name, name, label, canton_key
    """
    rows = st.session_state.get("choices_bank", [])
    ext = []
    for r in rows:
        ln = str(r.get("list_name","")).strip()
        if ln in ("list_canton", "list_distrito"):
            ext.append(dict(r))
    st.session_state["choices_ext_rows"] = ext


# ==========================================================================================
# 5) Menú principal
# ==========================================================================================
init_banks_if_needed()
seed_questions_bank_if_missing(form_title=form_title, logo_media_name=logo_media_name)
# choices ya viene del seed; si no, seed_choices_bank_if_missing() puede correr:
if not st.session_state.get("choices_bank"):
    seed_choices_bank_if_missing()

# Toggle modo
st.markdown("---")
st.subheader("🧭 Panel")

mode = st.radio(
    "Modo",
    options=["Editor", "Vista rápida"],
    horizontal=True,
    index=0 if st.session_state["ui_mode"]=="Editor" else 1
)
st.session_state["ui_mode"] = mode

if mode == "Vista rápida":
    st.info("Esta vista es solo para ver datos; edita en el modo Editor.")
    st.markdown("### Preguntas (resumen)")
    st.dataframe(pd.DataFrame(_qb_sorted()), use_container_width=True, height=260)
    st.markdown("### Choices (resumen)")
    st.dataframe(pd.DataFrame(st.session_state.get("choices_bank", [])), use_container_width=True, height=260)
    st.markdown("### Glosario (resumen)")
    st.dataframe(pd.DataFrame([
        {"termino": t, "def": d.get("def",""), "pages": ",".join(d.get("pages", []))}
        for t, d in _get_glossary().items()
    ]), use_container_width=True, height=260)

# ✅ El Editor real se construye con Partes 5–9, ya pegadas arriba.
#   - Parte 5: Editor fácil de preguntas
#   - Parte 6: Editor choices
#   - Parte 7: Editor glosario
#   - Parte 8: Exportador XLSForm desde banks
#   - Parte 9: Guardar/cargar + validaciones
#
# Con esto, la app queda “cableada” para funcionar end-to-end.
# ==========================================================================================



