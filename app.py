# -*- coding: utf-8 -*-
# ==========================================================================================
# ====== App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 8) + Cantón→Distrito =====
# ==========================================================================================
#
# Páginas:
# - P1: Introducción (logo + texto EXACTO)
# - P2: Consentimiento + ¿Acepta participar? (Sí/No) + Si NO => end
# - P3: Datos demográficos (Cantón→Distrito cascada + edad + género + escolaridad + relación zona)
# - P4: Percepción ciudadana (7 a 11) + Glosario por página (si aplica)
# - P5: Riesgos/Factores situacionales (12 a 18) + Glosario por página (si aplica)
# - P6: Delitos (19 a 29) + Glosario por página (si aplica)
# - P7: Victimización (30 a 31.4) + Glosario por página (si aplica)
# - P8: Confianza Policial + Acciones + Info adicional y cierre (32 a 47) + Glosario por página (si aplica)
#
# Reglas mantenidas:
# - settings.style = "pages" (páginas reales Next/Back)
# - Notas NO crean columnas: bind::esri:fieldType="null"
# - Glosario por página: aparece solo si la persona marca "Sí" (NO obligatorio) y queda DENTRO de la página
# - Catálogo Cantón→Distrito: por lotes, con placeholders y choice_filter
#
# Ajustes solicitados:
# - Eliminadas notas tipo “La respuesta es abierta…” y similares.
# - Eliminada la nota relacionada a 7.1 (no se agrega nota adicional para 7.1).
# ==========================================================================================

import re
from io import BytesIO
from datetime import datetime

import streamlit as st
import pandas as pd

# ==========================================================================================
# Configuración UI
# ==========================================================================================
st.set_page_config(page_title="Encuesta Comunidad — XLSForm (P1 a P8)", layout="wide")
st.title("🏘️ Encuesta Comunidad → XLSForm para ArcGIS Survey123 (Páginas 1 a 8)")

st.markdown("""
Genera un **XLSForm** listo para **ArcGIS Survey123** con páginas reales (Next/Back):
- **Página 1**: Introducción (logo + texto).
- **Página 2**: Consentimiento Informado + aceptación (Sí/No) y finalización si responde “No”.
- **Página 3**: Datos demográficos (Cantón/Distrito en cascada).
- **Página 4**: Percepción ciudadana (7 a 11) + glosario por página.
- **Página 5**: Riesgos y factores situacionales (12 a 18) + glosario por página.
- **Página 6**: Delitos (19 a 29) + glosario por página.
- **Página 7**: Victimización (30 a 31.4) + glosario por página.
- **Página 8**: Confianza policial + acciones + información adicional y cierre (32 a 47) + glosario por página.
""")

# ==========================================================================================
# Helpers
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
# Logo + Delegación
# ==========================================================================================
DEFAULT_LOGO_PATH = "001.png"

col_logo, col_txt = st.columns([1, 3], vertical_alignment="center")

with col_logo:
    up_logo = st.file_uploader("Logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="uploader_logo")
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
    delegacion = st.text_input("Nombre del lugar / Delegación", value="San Carlos Oeste", key="txt_delegacion")
    logo_media_name = st.text_input(
        "Nombre de archivo para `media::image`",
        value=st.session_state.get("_logo_name", "001.png"),
        help="Debe coincidir con el archivo dentro de la carpeta `media/` del proyecto Survey123 (Connect).",
        key="txt_logo_media_name"
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
# Página 2: Consentimiento (MISMO de la app anterior)
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
# Glosario (se alimenta por página SOLO si hay términos definidos)
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
# Catálogo Cantón → Distrito (por lotes) — permite múltiples distritos por cantón
# ==========================================================================================
if "choices_ext_rows" not in st.session_state:
    st.session_state.choices_ext_rows = []

def _append_choice_unique(row: dict):
    key = (row.get("list_name"), row.get("name"))
    exists = any((r.get("list_name"), r.get("name")) == key for r in st.session_state.choices_ext_rows)
    if not exists:
        st.session_state.choices_ext_rows.append(row)

st.markdown("### 📚 Catálogo Cantón → Distrito (por lotes)")
with st.expander("Agrega un lote (un Cantón y uno o varios Distritos)", expanded=True):
    col_c1, col_c2 = st.columns([2, 3])
    canton_txt = col_c1.text_input("Cantón (una vez)", value="", key="txt_canton_lote")
    distritos_txt = col_c2.text_area("Distritos del cantón (uno por línea)", value="", height=120, key="txt_distritos_lote")

    col_b1, col_b2, col_b3 = st.columns([1, 1, 2])
    add_lote = col_b1.button("Agregar lote", type="primary", use_container_width=True, key="btn_add_lote")
    clear_all = col_b2.button("Limpiar catálogo", use_container_width=True, key="btn_clear_catalogo")

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

            # Placeholders (una sola vez por lista)
            _append_choice_unique({"list_name": "list_canton", "name": "__pick_canton__", "label": "— escoja un cantón —"})
            _append_choice_unique({"list_name": "list_distrito", "name": "__pick_distrito__", "label": "— escoja un cantón —", "any": "1"})

            # Cantón
            _append_choice_unique({"list_name": "list_canton", "name": slug_c, "label": c})

            # Distritos (múltiples por líneas)
            usados_d = set()
            for d in distritos:
                slug_d_base = slugify_name(d)
                slug_d = asegurar_nombre_unico(slug_d_base, usados_d)
                usados_d.add(slug_d)
                _append_choice_unique({"list_name": "list_distrito", "name": slug_d, "label": d, "canton_key": slug_c})

            st.success(f"Lote agregado: {c} → {len(distritos)} distrito(s).")

if st.session_state.choices_ext_rows:
    st.dataframe(pd.DataFrame(st.session_state.choices_ext_rows),
                 use_container_width=True, hide_index=True, height=240)

# ==========================================================================================
# ============================== CHOICES BASE =============================================
# ==========================================================================================
def _construir_choices_y_base(form_title: str, logo_media_name: str):
    """
    Retorna:
      survey_rows (vacío por ahora), choices_rows (con TODAS las listas), v_si, v_no
    """
    survey_rows = []
    choices_rows = []

    # Yes/No (base)
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

    # Página 4: Percepción
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

    # Página 5: Riesgos / factores situacionales
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

    # Página 6: Delitos
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

    # Página 7: Victimización
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

    # Página 8: Confianza Policial + Acciones + Info adicional y cierre
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
# ============================== CONSTRUIR XLSFORM ========================================
# ==========================================================================================
def construir_xlsform(form_title: str, logo_media_name: str, idioma: str, version: str):
    # Base + choices
    survey_rows, choices_rows, v_si, v_no = _construir_choices_y_base(form_title, logo_media_name)

    # Notes sin columnas
    def add_note(name: str, label: str, relevant: str | None = None, media_image: str | None = None):
        row = {"type": "note", "name": name, "label": label, "bind::esri:fieldType": "null"}
        if relevant:
            row["relevant"] = relevant
        if media_image:
            row["media::image"] = media_image
        survey_rows.append(row)

    # Glosario por página (solo si términos existen en el diccionario)
    def add_glosario_por_pagina(page_id: str, relevant_base: str, terminos: list[str]):
        terminos_existentes = [t for t in terminos if t in GLOSARIO_DEFINICIONES]
        if not terminos_existentes:
            return

        survey_rows.append({
            "type": "select_one yesno",
            "name": f"{page_id}_accede_glosario",
            "label": "¿Desea acceder al glosario de esta sección?",
            "required": "no",
            "appearance": "minimal",
            "relevant": relevant_base
        })

        rel_glos = f"({relevant_base}) and (${{{page_id}_accede_glosario}}='{v_si}')"

        survey_rows.append({
            "type": "begin_group",
            "name": f"{page_id}_glosario",
            "label": "Glosario",
            "relevant": rel_glos
        })

        add_note(f"{page_id}_glosario_intro",
                 "A continuación, se muestran definiciones de términos que aparecen en esta sección.",
                 relevant=rel_glos)

        for idx, t in enumerate(terminos_existentes, start=1):
            add_note(f"{page_id}_glos_{idx}", GLOSARIO_DEFINICIONES[t], relevant=rel_glos)

        add_note(f"{page_id}_glosario_cierre",
                 "Para continuar con la encuesta, desplácese hacia arriba y continúe con normalidad.",
                 relevant=rel_glos)

        survey_rows.append({"type": "end_group", "name": f"{page_id}_glosario_end"})

    # Relevant base si acepta participar
    rel_si = f"${{acepta_participar}}='{v_si}'"

    # ======================================================================================
    # P1: Introducción
    # ======================================================================================
    survey_rows.append({"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"})
    add_note("p1_logo", form_title, media_image=logo_media_name)
    add_note("p1_texto", INTRO_COMUNIDAD_EXACTA)
    survey_rows.append({"type": "end_group", "name": "p1_end"})

    # ======================================================================================
    # P2: Consentimiento
    # ======================================================================================
    survey_rows.append({"type": "begin_group", "name": "p2_consent", "label": "Consentimiento Informado", "appearance": "field-list"})
    add_note("p2_titulo", CONSENT_TITLE)
    for i, p in enumerate(CONSENT_PARRAFOS, start=1):
        add_note(f"p2_p_{i}", p)
    for j, b in enumerate(CONSENT_BULLETS, start=1):
        add_note(f"p2_b_{j}", f"• {b}")
    for k, c in enumerate(CONSENT_CIERRE, start=1):
        add_note(f"p2_c_{k}", c)

    survey_rows.append({
        "type": "select_one yesno",
        "name": "acepta_participar",
        "label": "¿Acepta participar en esta encuesta?",
        "required": "yes",
        "appearance": "minimal"
    })
    survey_rows.append({"type": "end_group", "name": "p2_end"})

    # End si NO acepta
    survey_rows.append({
        "type": "end",
        "name": "fin_por_no",
        "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.",
        "relevant": f"${{acepta_participar}}='{v_no}'"
    })

    # ======================================================================================
    # P3: Datos demográficos
    # ======================================================================================
    survey_rows.append({
        "type": "begin_group",
        "name": "p3_datos_demograficos",
        "label": "Datos demográficos",
        "appearance": "field-list",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one list_canton",
        "name": "canton",
        "label": "1. Cantón:",
        "required": "yes",
        "constraint": ". != '__pick_canton__'",
        "constraint_message": "Seleccione un cantón válido.",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one list_distrito",
        "name": "distrito",
        "label": "2. Distrito:",
        "required": "yes",
        "choice_filter": "canton_key=${canton} or any='1'",
        "constraint": ". != '__pick_distrito__'",
        "constraint_message": "Seleccione un distrito válido.",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "integer",
        "name": "edad_anos",
        "label": "3. Edad (en años cumplidos):",
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

    # ======================================================================================
    # P4: Percepción ciudadana (7 a 11) — 11 incluida y NO condicionada
    # ======================================================================================
    survey_rows.append({
        "type": "begin_group",
        "name": "p4_percepcion_distrito",
        "label": "Percepción ciudadana de seguridad en el distrito",
        "appearance": "field-list",
        "relevant": rel_si
    })

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

    rel_81 = f"({rel_si})"

    survey_rows.append({
        "type": "text",
        "name": "p81_indique_por_que",
        "label": "8.1. Indique por qué:",
        "required": "yes",
        "appearance": "multiline",
        "relevant": rel_81
    })

    add_note("p9_instr",
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

    add_glosario_por_pagina("p4", rel_si, ["Extorsión", "Daños/vandalismo"])
    survey_rows.append({"type": "end_group", "name": "p4_end"})

    # ======================================================================================
    # P5: Riesgos / factores situacionales (12 a 18)
    # ======================================================================================
    survey_rows.append({
        "type": "begin_group",
        "name": "p5_riesgos",
        "label": "III. RIESGOS, DELITOS, VICTIMIZACIÓN Y EVALUACIÓN POLICIAL",
        "appearance": "field-list",
        "relevant": rel_si
    })

    add_note("p5_subtitulo", "Riesgos sociales y situacionales en el distrito", relevant=rel_si)
    add_note("p5_intro",
             "A continuación, se presentará una lista de problemáticas que se catalogan como factores situacionales, con la finalidad de que seleccione aquellos que considere que ocurren en su distrito.",
             relevant=rel_si)

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

    add_glosario_por_pagina("p5", rel_si, [
        "Cuarterías",
        "Asentamientos informales o precarios",
        "Desvinculación escolar (deserción escolar)",
        "Búnkeres",
        "Lotes baldíos",
        "Presencia de personas en situación de calle",
        "Personas en situación de ocio"
    ])

    survey_rows.append({"type": "end_group", "name": "p5_end"})

    # ======================================================================================
    # P6: Delitos (19 a 29)
    # ======================================================================================
    survey_rows.append({
        "type": "begin_group",
        "name": "p6_delitos",
        "label": "Delitos",
        "appearance": "field-list",
        "relevant": rel_si
    })

    add_note(
        "p6_intro",
        "A continuación, se presentará una lista de delitos y situaciones delictivas para que seleccione aquellos que, según su percepción u observación, considera que se presentan en su comunidad. Esta información no constituye denuncia formal ni confirmación de hechos delictivos.",
        relevant=rel_si
    )

    survey_rows.append({
        "type": "select_multiple p19_delitos_general",
        "name": "p19_delitos_general",
        "label": "19. Selección múltiple de los siguientes delitos:",
        "required": "yes",
        "relevant": rel_si
    })
    add_note(
        "p19_nota",
        "Nota: esta pregunta es de selección múltiple, se engloba estos delitos en una sola pregunta ya que ninguno de ellos se subdivide.",
        relevant=rel_si
    )

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

    survey_rows.append({
        "type": "select_multiple p21_vida",
        "name": "p21_delitos_vida",
        "label": "21. Delitos contra la vida",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p22_sexuales",
        "name": "p22_delitos_sexuales",
        "label": "22. Delitos sexuales",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p23_asaltos",
        "name": "p23_asaltos_percibidos",
        "label": "23. Asaltos percibidos",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p24_estafas",
        "name": "p24_estafas_percibidas",
        "label": "24. Estafas percibidas",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p25_robo_fuerza",
        "name": "p25_robo_percibidos",
        "label": "25. Robo percibidos (Sustracción de artículos mediante la utilización de la fuerza)",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p26_abandono",
        "name": "p26_abandono_personas",
        "label": "26. Abandono de personas",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p27_explotacion_infantil",
        "name": "p27_explotacion_infantil",
        "label": "27. Explotación infantil",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p28_ambientales",
        "name": "p28_delitos_ambientales",
        "label": "28. Delitos ambientales percibidos",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p29_trata",
        "name": "p29_trata_personas",
        "label": "29. Trata de personas",
        "required": "yes",
        "relevant": rel_si
    })
    add_note(
        "p29_nota",
        "Nota: esta pregunta es de selección múltiple, se engloba estos delitos en una sola pregunta ya que ninguno de ellos se subdivide.",
        relevant=rel_si
    )

    add_glosario_por_pagina("p6", rel_si, [
        "Receptación",
        "Contrabando",
        "Tráfico de personas (coyotaje)",
        "Acoso callejero",
        "Estafa",
        "Tacha",
        "Trata de personas",
        "Explotación infantil",
        "Extorsión",
        "Búnkeres"
    ])

    survey_rows.append({"type": "end_group", "name": "p6_end"})

    # ======================================================================================
    # P7: Victimización (30 a 31.4)
    # ======================================================================================
    survey_rows.append({
        "type": "begin_group",
        "name": "p7_victimizacion",
        "label": "Victimización",
        "appearance": "field-list",
        "relevant": rel_si
    })

    add_note(
        "p7_intro",
        "A continuación, se presentará una lista de situaciones para que indique si usted o algún miembro de su hogar ha sido afectado por alguna de ellas en su distrito durante el último año.",
        relevant=rel_si
    )

    survey_rows.append({
        "type": "select_one p30_vif",
        "name": "p30_vif",
        "label": "30. Durante el último año, ¿usted o algún miembro de su hogar ha sido afectado por alguna situación de violencia intrafamiliar (violencia doméstica)?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_30_si = f"({rel_si}) and (${{p30_vif}}='{slugify_name('Sí')}')"

    survey_rows.append({
        "type": "select_multiple p301_tipos_vif",
        "name": "p301_tipos_vif",
        "label": "30.1. ¿Qué tipo(s) de violencia intrafamiliar (violencia doméstica) se presentaron?",
        "required": "yes",
        "relevant": rel_30_si
    })

    survey_rows.append({
        "type": "select_one p302_medidas",
        "name": "p302_medidas_proteccion",
        "label": "30.2. ¿En relación con la situación de violencia intrafamiliar indicada anteriormente, usted o algún miembro de su hogar solicitó medidas de protección?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_30_si
    })

    survey_rows.append({
        "type": "select_one p303_valoracion_fp",
        "name": "p303_valoracion_fp",
        "label": "30.3. ¿Cómo valora el abordaje de la Fuerza Pública ante esta situación?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_30_si
    })

    # 31
    survey_rows.append({
        "type": "select_one p31_delito_12m",
        "name": "p31_delito_12m",
        "label": "31. Durante los últimos 12 meses, ¿usted o algún miembro de su hogar fue afectado por algún delito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })
    add_note(
        "p31_nota",
        "Nota: la respuesta es de selección única. En el caso que la persona encuestada seleccione la opción “No” pasar a la siguiente sección. En el caso que seleccione “Sí, y denuncié” se habilita la pregunta 31.1, 31.3 y 31.4. En el caso que seleccione “Sí, pero no denuncié” se habilita la pregunta 31.1, 31.2, 31.3 y 31.4.",
        relevant=rel_si
    )

    val_31_si_den = slugify_name("Sí, y denuncié")
    val_31_si_no_den = slugify_name("Sí, pero no denuncié.")

    rel_31_si = f"({rel_si}) and (${{p31_delito_12m}}='{val_31_si_den}' or ${{p31_delito_12m}}='{val_31_si_no_den}')"
    rel_31_si_no_den = f"({rel_si}) and (${{p31_delito_12m}}='{val_31_si_no_den}')"

    survey_rows.append({
        "type": "select_multiple p311_situaciones",
        "name": "p311_situaciones_afecto",
        "label": "31.1. ¿Cuál de las siguientes situaciones afectó a usted o a algún miembro de su hogar?",
        "required": "yes",
        "relevant": rel_31_si
    })

    survey_rows.append({
        "type": "select_multiple p312_motivos_no_denuncia",
        "name": "p312_motivo_no_denuncia",
        "label": "31.2. En caso de NO haber realizado la denuncia, indique ¿cuál fue el motivo?",
        "required": "yes",
        "relevant": rel_31_si_no_den
    })

    survey_rows.append({
        "type": "select_one p313_horario",
        "name": "p313_horario_hecho",
        "label": "31.3. ¿Tiene conocimiento sobre el horario en el cual se presentó el hecho o situación que le afectó a usted o un familiar?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_31_si
    })

    survey_rows.append({
        "type": "select_multiple p314_modo",
        "name": "p314_modo_ocurrio",
        "label": "31.4. ¿Cuál fue la forma o modo en que ocurrió la situación que afectó a usted o a algún miembro de su hogar?",
        "required": "yes",
        "relevant": rel_31_si
    })

    survey_rows.append({
        "type": "text",
        "name": "p314_otro_detalle",
        "label": "Otro (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_31_si}) and selected(${{p314_modo_ocurrio}}, '{slugify_name('Otro')}')"
    })

    add_glosario_por_pagina("p7", rel_si, [
        "Ganzúa (pata de chancho)",
        "Boquete",
        "Arrebato",
        "Receptación",
        "Extorsión",
    ])

    survey_rows.append({"type": "end_group", "name": "p7_end"})

    return survey_rows, choices_rows, v_si, v_no, add_note, add_glosario_por_pagina, rel_si

# ==========================================================================================
# ============================== P8 + EXPORT ==============================================
# ==========================================================================================
def construir_xlsform_final(form_title: str, logo_media_name: str, idioma: str, version: str):
    # Construye P1-P7 y trae helpers internos
    survey_rows, choices_rows, v_si, v_no, add_note, add_glosario_por_pagina, rel_si = construir_xlsform(
        form_title=form_title,
        logo_media_name=logo_media_name,
        idioma=idioma,
        version=version
    )

    # ======================================================================================
    # P8: Confianza Policial + Acciones + Información adicional y cierre (32 a 47)
    # ======================================================================================
    survey_rows.append({
        "type": "begin_group",
        "name": "p8_confianza_policial",
        "label": "Confianza Policial",
        "appearance": "field-list",
        "relevant": rel_si
    })

    add_note(
        "p8_intro",
        "A continuación, se presentará una lista de afirmaciones relacionadas con su percepción y confianza en el cuerpo de policía que opera en su (Distrito) barrio.",
        relevant=rel_si
    )

    # 32 (Sí/No)
    survey_rows.append({
        "type": "select_one p32_identifica_policias",
        "name": "p32_identifica_policias",
        "label": "32. ¿Identifica usted a los policías de la Fuerza Pública de Costa Rica en su comunidad?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 32.1 (multi) si 32=Sí
    rel_321 = f"({rel_si}) and (${{p32_identifica_policias}}='{slugify_name('Sí')}')"
    survey_rows.append({
        "type": "select_multiple p321_interacciones",
        "name": "p321_tipos_atencion",
        "label": "32.1 ¿Cuáles de los siguientes tipos de atención ha tenido?",
        "required": "yes",
        "relevant": rel_321
    })

    survey_rows.append({
        "type": "text",
        "name": "p321_otro_detalle",
        "label": "Otra (especifique):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_321}) and selected(${{p321_tipos_atencion}}, '{slugify_name('Otra (especifique)')}')"
    })

    # 33 escala 1-10
    survey_rows.append({
        "type": "select_one escala_1_10",
        "name": "p33_confianza_policial",
        "label": "33. ¿Cuál es el nivel de confianza en la policía de la Fuerza Pública de Costa Rica de su comunidad? (1=Ninguna Confianza, 10=Mucha Confianza)",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 34
    survey_rows.append({
        "type": "select_one escala_1_10",
        "name": "p34_profesionalidad",
        "label": "34. En una escala del 1 al 10, donde 1 es “Nada profesional” y 10 es “Muy profesional”, ¿cómo calificaría la profesionalidad de la Fuerza Pública en su distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 35
    survey_rows.append({
        "type": "select_one escala_1_10",
        "name": "p35_calidad_servicio",
        "label": "35. En una escala del 1 al 10, donde 1 es “Muy mala” y 10 es “Muy buena”, ¿cómo califica la calidad del servicio policial en su distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 36
    survey_rows.append({
        "type": "select_one escala_1_10",
        "name": "p36_satisfaccion_preventivo",
        "label": "36. En una escala del 1 al 10, donde 1 es “Nada satisfecho(a)” y 10 es “Muy satisfecho(a)”, ¿qué tan satisfecho(a) está con el trabajo preventivo que realiza la Fuerza Pública en su distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 37
    survey_rows.append({
        "type": "select_one escala_1_10",
        "name": "p37_contribucion_reduccion_crimen",
        "label": "37. En una escala del 1 al 10, donde 1 es “No contribuye en nada” y 10 es “Contribuye muchísimo”, indique: ¿En qué medida considera que la presencia policial ayuda a reducir el crimen en su distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 38
    survey_rows.append({
        "type": "select_one p38_frecuencia",
        "name": "p38_frecuencia_presencia",
        "label": "38. ¿Con qué frecuencia observa presencia policial en su distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 39
    survey_rows.append({
        "type": "select_one p39_si_no_aveces",
        "name": "p39_presencia_consistente",
        "label": "39. ¿Considera que la presencia policial es consistente a lo largo del día en su distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 40
    survey_rows.append({
        "type": "select_one p39_si_no_aveces",
        "name": "p40_trato_justo",
        "label": "40. ¿Considera que la policía trata a las personas de manera justa e imparcial en su distrito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 41
    survey_rows.append({
        "type": "select_one p41_opciones",
        "name": "p41_quejas_sin_temor",
        "label": "41. ¿Cree usted que puede expresar preocupaciones o quejas a la policía sin temor a represalias?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 42
    survey_rows.append({
        "type": "select_one p39_si_no_aveces",
        "name": "p42_info_veraz_clara",
        "label": "42. ¿Considera que la policía proporciona información veraz, clara y oportuna a la comunidad?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 43 multiselect + Otro (detalle)
    survey_rows.append({
        "type": "select_multiple p43_acciones_fp",
        "name": "p43_accion_fp_mejorar",
        "label": "43. ¿Qué actividad considera que debe realizar la Fuerza Pública para mejorar la seguridad en su comunidad?",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "text",
        "name": "p43_otro_detalle",
        "label": "Otro (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p43_accion_fp_mejorar}}, '{slugify_name('Otro')}')"
    })

    # 44 multiselect + Otro (detalle)
    survey_rows.append({
        "type": "select_multiple p44_acciones_muni",
        "name": "p44_accion_muni_mejorar",
        "label": "44. ¿Qué actividad considera que debe realizar la municipalidad para mejorar la seguridad en su comunidad?",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "text",
        "name": "p44_otro_detalle",
        "label": "Otro (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p44_accion_muni_mejorar}}, '{slugify_name('Otro')}')"
    })

    # Sección: Información Adicional y Contacto Voluntario
    add_note("p8_info_adicional_titulo", "Información Adicional y Contacto Voluntario", relevant=rel_si)

    # 45 Sí/No
    survey_rows.append({
        "type": "select_one p45_info_delito",
        "name": "p45_info_delito",
        "label": "45. ¿Usted tiene información de alguna persona o grupo que se dedique a realizar algún delito en su comunidad? (Recuerde, su información es confidencial.)",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 45.1 texto si 45=Sí
    rel_451 = f"({rel_si}) and (${{p45_info_delito}}='{slugify_name('Sí')}')"
    survey_rows.append({
        "type": "text",
        "name": "p451_detalle_info",
        "label": "45.1. Si su respuesta es \"Sí\", describa aquellas características que pueda aportar tales como nombre de estructura o banda criminal... (nombre de personas, alias, domicilio, vehículos, etc.)",
        "required": "yes",
        "appearance": "multiline",
        "relevant": rel_451
    })

    # 46 contacto voluntario (abierta) — SIN nota “respuesta abierta”
    survey_rows.append({
        "type": "text",
        "name": "p46_contacto_voluntario",
        "label": "46. En el siguiente espacio de forma voluntaria podrá anotar su nombre, teléfono o correo electrónico en el cual desee ser contactado y continuar colaborando de forma confidencial con Fuerza Pública.",
        "required": "no",
        "appearance": "multiline",
        "relevant": rel_si
    })

    # 47 otra info (abierta) — SIN nota “respuesta abierta”
    survey_rows.append({
        "type": "text",
        "name": "p47_info_adicional",
        "label": "47. En el siguiente espacio podrá registrar alguna otra información que estime pertinente.",
        "required": "no",
        "appearance": "multiline",
        "relevant": rel_si
    })

    # Cierre (nota)
    add_note("p8_fin", "---------------------------------- Fin de la Encuesta ----------------------------------", relevant=rel_si)

    # Glosario Página 8 (si hay términos en diccionario)
    add_glosario_por_pagina("p8", rel_si, [
        "Patrullaje",
        "Acciones disuasivas",
        "Coordinación interinstitucional",
        "Integridad y credibilidad policial",
    ])

    survey_rows.append({"type": "end_group", "name": "p8_end"})

    # ======================================================================================
    # Integrar catálogo Cantón→Distrito en choices (con columnas extra canton_key/any)
    # ======================================================================================
    for r in st.session_state.choices_ext_rows:
        choices_rows.append(dict(r))

    # ======================================================================================
    # DataFrames finales
    # ======================================================================================
    survey_cols = [
        "type", "name", "label", "required", "appearance",
        "relevant", "choice_filter",
        "constraint", "constraint_message",
        "media::image",
        "bind::esri:fieldType"
    ]
    df_survey = pd.DataFrame(survey_rows, columns=survey_cols).fillna("")

    choices_cols_all = set()
    for r in choices_rows:
        choices_cols_all.update(r.keys())
    base_choice_cols = ["list_name", "name", "label"]
    for extra in sorted(choices_cols_all):
        if extra not in base_choice_cols:
            base_choice_cols.append(extra)
    df_choices = pd.DataFrame(choices_rows, columns=base_choice_cols).fillna("")

    df_settings = pd.DataFrame([{
        "form_title": form_title,
        "version": version,
        "default_language": idioma,
        "style": "pages"
    }], columns=["form_title", "version", "default_language", "style"]).fillna("")

    return df_survey, df_choices, df_settings

# ==========================================================================================
# Exportar (UI)
# ==========================================================================================
st.markdown("---")
st.subheader("📦 Generar XLSForm (Survey123)")

idioma = st.selectbox("Idioma (default_language)", options=["es", "en"], index=0, key="sel_idioma")
version_auto = datetime.now().strftime("%Y%m%d%H%M")
version = st.text_input("Versión (settings.version)", value=version_auto, key="txt_version")

if st.button("🧮 Construir XLSForm", use_container_width=True, key="btn_build_xlsform"):
    has_canton = any(
        r.get("list_name") == "list_canton" and r.get("name") not in ("__pick_canton__",)
        for r in st.session_state.choices_ext_rows
    )
    has_distrito = any(
        r.get("list_name") == "list_distrito" and r.get("name") not in ("__pick_distrito__",)
        for r in st.session_state.choices_ext_rows
    )

    if not has_canton or not has_distrito:
        st.warning("Aún no has cargado catálogo Cantón→Distrito. Puedes construir igual, pero en Survey123 verás solo placeholders.")

    df_survey, df_choices, df_settings = construir_xlsform_final(
        form_title=form_title,
        logo_media_name=logo_media_name,
        idioma=idioma,
        version=version.strip() or version_auto
    )

    st.success("XLSForm construido. Vista previa rápida:")
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

    if st.session_state.get("_logo_bytes"):
        st.download_button(
            "📥 Descargar logo para carpeta media/",
            data=st.session_state["_logo_bytes"],
            file_name=logo_media_name,
            mime="image/png",
            use_container_width=True,
            key="btn_download_logo"
        )

    st.info("""
**Cómo usar en Survey123 Connect**
1) Crear encuesta **desde archivo** y seleccionar el XLSForm descargado.  
2) Copiar el logo dentro de la carpeta **media/** del proyecto, con el **mismo nombre** que pusiste en `media::image`.  
3) Verás páginas con **Siguiente/Anterior** (porque `settings.style = pages`).  
4) El glosario aparece solo si la persona marca **Sí** (no es obligatorio).  
5) Las **notas** no generan columnas vacías en la tabla (porque usan `bind::esri:fieldType = null`).  
""")






