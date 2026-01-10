# -*- coding: utf-8 -*-
# ==========================================================================================
# App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 8) + Cantón→Distrito (cascada)
# ==========================================================================================
#
# OBJETIVO:
# - Generar un XLSForm (Excel) con: sheets "survey", "choices", "settings"
# - Estilo: pages (páginas reales Next/Back)
# - P1 Intro (logo + texto EXACTO)
# - P2 Consentimiento + ¿Acepta participar? (Si NO => end)
# - P3 Datos demográficos (Cantón→Distrito cascada + Edad + Género + Escolaridad + Relación zona)
# - P4 Percepción (7 a 11) + Glosario por página (si aplica)
# - P5 Riesgos/Factores (12 a 18) + Glosario por página (si aplica)
# - P6 Delitos (19 a 29) + Glosario por página (si aplica)
# - P7 Victimización (30 a 31.4) + Glosario por página (si aplica)
# - P8 Confianza policial + Acciones + Info adicional y cierre (32 a 47) + Glosario por página (si aplica)
#
# AJUSTES SOLICITADOS:
# - Eliminar textos visibles tipo "Nota: ..." (guías internas).
# - En Cantón/Distrito: NO placeholders "— escoja un cantón —".
# - En Edad: solo "Edad".
# - Arreglo del “error al llegar a una página”: en cascadas, NO validar “Distrito” requerido
#   mientras el Cantón aún no esté seleccionado (relevant adicional).
#
# IMPORTANTE:
# - Notas informativas reales para el encuestado se dejan (sin prefijo "Nota:").
# - Todas las notas que no deben crear columnas usan bind::esri:fieldType="null"
# ==========================================================================================

import re
from io import BytesIO
import streamlit as st
import pandas as pd

# ==========================================================================================
# Configuración UI
# ==========================================================================================
st.set_page_config(page_title="Encuesta Comunidad — XLSForm (P1 a P8)", layout="wide")
st.title("🏘️ Encuesta Comunidad → XLSForm para ArcGIS Survey123 (Páginas 1 a 8)")

st.markdown("""
Genera un **XLSForm** listo para **ArcGIS Survey123** con páginas reales (Next/Back).
Incluye **glosario por sección** (opcional) y **Cantón→Distrito** en cascada.
""")

# ==========================================================================================
# Helpers
# ==========================================================================================
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

def add_choice_list(choices_rows, list_name: str, labels: list[str]):
    usados = set((r.get("list_name"), r.get("name")) for r in choices_rows)
    for lab in labels:
        row = {"list_name": list_name, "name": slugify_name(lab), "label": lab}
        key = (row["list_name"], row["name"])
        if key not in usados:
            choices_rows.append(row)
            usados.add(key)

def descargar_xlsform(df_survey, df_choices, df_settings, nombre_archivo: str):
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
                ws.set_column(col_idx, col_idx, max(14, min(95, len(str(col_name)) + 10)))

    buffer.seek(0)
    st.download_button(
        label=f"📥 Descargar XLSForm ({nombre_archivo})",
        data=buffer,
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# ==========================================================================================
# Textos base
# ==========================================================================================
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
# Logo + Delegación
# ==========================================================================================
DEFAULT_LOGO_PATH = "001.png"

col_logo, col_txt = st.columns([1, 3], vertical_alignment="center")
with col_logo:
    up_logo = st.file_uploader("Logo (PNG/JPG)", type=["png", "jpg", "jpeg"])
    if up_logo:
        st.image(up_logo, caption="Logo cargado", use_container_width=True)
        logo_media_name_default = up_logo.name
    else:
        logo_media_name_default = "001.png"
        try:
            st.image(DEFAULT_LOGO_PATH, caption="Logo (001.png)", use_container_width=True)
        except Exception:
            st.warning("Sube un logo si no tienes 001.png en la carpeta del proyecto.")

with col_txt:
    delegacion = st.text_input("Nombre del lugar / Delegación", value="San Carlos Oeste")
    logo_media_name = st.text_input(
        "Nombre de archivo para `media::image`",
        value=logo_media_name_default,
        help="Debe coincidir con el archivo dentro de la carpeta `media/` en Survey123 Connect."
    )

form_title = f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad"
st.markdown(f"### {form_title}")

# ==========================================================================================
# Idioma / versión
# ==========================================================================================
col_a, col_b = st.columns(2)
with col_a:
    idioma = st.selectbox("Idioma (default_language)", ["es"], index=0)
with col_b:
    version = st.text_input("Versión (settings)", value="v1")

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

st.markdown("### 📚 Catálogo Cantón → Distrito (por lotes)")
with st.expander("Agrega un lote (un Cantón y uno o varios Distritos)", expanded=True):
    col_c1, col_c2 = st.columns([2, 3])
    canton_txt = col_c1.text_input("Cantón (una vez)", value="", key="canton_lote")
    distritos_txt = col_c2.text_area("Distritos del cantón (uno por línea)", value="", height=120, key="distritos_lote")

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

if st.session_state.choices_ext_rows:
    st.dataframe(pd.DataFrame(st.session_state.choices_ext_rows), use_container_width=True, hide_index=True, height=240)
else:
    st.info("Agrega al menos 1 cantón con sus distritos para que la cascada funcione (Cantón→Distrito).")

# ==========================================================================================
# Construcción del XLSForm
# ==========================================================================================
def construir_xlsform(form_title: str, logo_media_name: str, idioma: str, version: str, catalogo_rows: list[dict]):
    survey_rows = []
    choices_rows = []

    # ===========================
    # Choices base
    # ===========================
    add_choice_list(choices_rows, "yesno", ["Sí", "No"])
    v_si = slugify_name("Sí")
    v_no = slugify_name("No")

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

    # P5
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

    add_choice_list(choices_rows, "p13_carencias_inversion", [
        "Falta de oferta educativa",
        "Falta de oferta deportiva",
        "Falta de oferta recreativa",
        "Falta de actividades culturales",
    ])
    add_choice_list(choices_rows, "p14_consumo_drogas_donde", ["Área privada", "Área pública", "No se observa consumo"])
    add_choice_list(choices_rows, "p15_def_infra_vial", ["Calles en mal estado", "Falta de señalización de tránsito", "Carencia o inexistencia de aceras"])
    add_choice_list(choices_rows, "p16_bunkeres_espacios", ["Casa de habitación (Espacio Cerrado)", "Edificación abandonada", "Lote baldío", "Otro"])
    add_choice_list(choices_rows, "p17_transporte_afect", ["Informal (taxis piratas)", "Plataformas (digitales)"])
    add_choice_list(choices_rows, "p18_presencia_policial", ["Falta de presencia policial", "Presencia policial insuficiente", "Presencia policial solo en ciertos horarios", "No observa presencia policial"])

    # P6 Delitos
    add_choice_list(choices_rows, "p19_delitos_general", [
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
    add_choice_list(choices_rows, "p20_bunker_percepcion", [
        "En espacios cerrados (casas, edificaciones u otros inmuebles)",
        "En vía pública",
        "De forma ocasional o móvil (sin punto fijo)",
        "No se percibe consumo o venta",
        "Otro"
    ])
    add_choice_list(choices_rows, "p21_vida", ["Homicidios", "Heridos (lesiones dolosas)", "Femicidio"])
    add_choice_list(choices_rows, "p22_sexuales", ["Abuso sexual", "Acoso sexual", "Violación", "Acoso Callejero"])
    add_choice_list(choices_rows, "p23_asaltos", ["Asalto a personas", "Asalto a comercio", "Asalto a vivienda", "Asalto a transporte público"])
    add_choice_list(choices_rows, "p24_estafas", ["Billetes falsos", "Documentos falsos", "Estafa (Oro)", "Lotería falsos", "Estafas informáticas", "Estafa telefónica", "Estafa con tarjetas"])
    add_choice_list(choices_rows, "p25_robo_fuerza", [
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
    ])
    add_choice_list(choices_rows, "p26_abandono", ["Abandono de adulto mayor", "Abandono de menor de edad", "Abandono de incapaz"])
    add_choice_list(choices_rows, "p27_explotacion_infantil", ["Sexual", "Laboral"])
    add_choice_list(choices_rows, "p28_ambientales", ["Caza ilegal", "Pesca ilegal", "Tala ilegal", "Minería ilegal"])
    add_choice_list(choices_rows, "p29_trata", ["Con fines laborales", "Con fines sexuales"])

    # P7 Victimización
    add_choice_list(choices_rows, "p30_vif", ["Sí", "No"])
    add_choice_list(choices_rows, "p301_tipos_vif", [
        "Violencia psicológica (gritos, amenazas, humillaciones, maltratos, entre otros)",
        "Violencia física (agresiones físicas, empujones, golpes, entre otros)",
        "Violencia vicaria (uso de hijas, hijos u otras personas para causar daño emocional)",
        "Violencia patrimonial (destrucción, retención o control de bienes, documentos o dinero)",
        "Violencia sexual (actos de carácter sexual sin consentimiento)"
    ])
    add_choice_list(choices_rows, "p302_medidas", ["Sí", "No", "No recuerda"])
    add_choice_list(choices_rows, "p303_valoracion_fp", ["Excelente", "Bueno", "Regular", "Malo", "Muy malo"])
    add_choice_list(choices_rows, "p31_delito_12m", ["NO", "Sí, y denuncié", "Sí, pero no denuncié."])

    add_choice_list(choices_rows, "p311_situaciones", [
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
    add_choice_list(choices_rows, "p312_motivos_no_denuncia", [
        "Distancia (falta de oficinas para recepción de denuncias).",
        "Miedo a represalias.",
        "Falta de respuesta oportuna.",
        "He realizado denuncias y no ha pasado nada.",
        "Complejidad al colocar la denuncia.",
        "Desconocimiento de dónde colocar la denuncia.",
        "El Policía me dijo que era mejor no denunciar.",
        "Falta de tiempo para colocar la denuncia."
    ])
    add_choice_list(choices_rows, "p313_horario", [
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
    add_choice_list(choices_rows, "p314_modo", [
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

    # P8 Confianza + Acciones
    add_choice_list(choices_rows, "p32_identifica_policias", ["Sí", "No"])
    add_choice_list(choices_rows, "p321_interacciones", [
        "Solicitud de ayuda o auxilio.",
        "Atención relacionada con una denuncia.",
        "Atención cordial o preventiva durante un patrullaje.",
        "Fui abordado o registrado para identificación.",
        "Fui objeto de una infracción o conflicto.",
        "Evento preventivos (Cívico policial, Reunión Comunitaria)",
        "Otra (especifique)"
    ])
    add_choice_list(choices_rows, "escala_1_10", [str(i) for i in range(1, 11)])
    add_choice_list(choices_rows, "p38_frecuencia", ["Todos los días", "Varias veces por semana", "Una vez por semana", "Casi nunca", "Nunca"])
    add_choice_list(choices_rows, "p39_si_no_aveces", ["Sí", "No", "A veces"])
    add_choice_list(choices_rows, "p41_opciones", ["Sí", "No", "No estoy seguro(a)"])
    add_choice_list(choices_rows, "p43_acciones_fp", [
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
    add_choice_list(choices_rows, "p44_acciones_muni", [
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
    add_choice_list(choices_rows, "p45_info_delito", ["Sí", "No"])

    # ===========================
    # Integrar catálogo Cantón/Distrito (choices)
    # ===========================
    for r in catalogo_rows:
        if r.get("list_name") == "list_canton":
            choices_rows.append({"list_name": "list_canton", "name": r["name"], "label": r["label"]})
        elif r.get("list_name") == "list_distrito":
            choices_rows.append({"list_name": "list_distrito", "name": r["name"], "label": r["label"], "canton_key": r.get("canton_key", "")})

    # ===========================
    # Helpers survey
    # ===========================
    def add_note(name: str, label: str, relevant: str | None = None, media_image: str | None = None):
        row = {"type": "note", "name": name, "label": label, "bind::esri:fieldType": "null"}
        if relevant:
            row["relevant"] = relevant
        if media_image:
            row["media::image"] = media_image
        survey_rows.append(row)

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

    # Finaliza si NO acepta
    survey_rows.append({
        "type": "end",
        "name": "fin_por_no",
        "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.",
        "relevant": f"${{acepta_participar}}='{v_no}'"
    })

    # ======================================================================================
    # P3: Datos demográficos (con FIX de cascada para evitar error al entrar)
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
        "appearance": "minimal",
        "relevant": rel_si
    })

    # FIX: Distrito solo se vuelve relevante cuando canton NO está vacío.
    # Esto evita que Survey123 “valide requerido” apenas llegas a la página sin haber seleccionado cantón.
    rel_distrito = f"({rel_si}) and string-length(${{canton}}) > 0"

    survey_rows.append({
        "type": "select_one list_distrito",
        "name": "distrito",
        "label": "2. Distrito:",
        "required": "yes",
        "choice_filter": "canton_key=${canton}",
        "appearance": "minimal",
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

    # ======================================================================================
    # P4: Percepción (7 a 11) + glosario
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

    add_note("p71_info", "Esta pregunta recoge percepción general y no constituye denuncia.", relevant=rel_71)

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

    survey_rows.append({
        "type": "text",
        "name": "p81_indique_por_que",
        "label": "8.1. Indique por qué:",
        "required": "yes",
        "appearance": "multiline",
        "relevant": rel_si
    })

    add_note("p9_encabezado",
             "9. Indique qué tan seguros percibe, en términos de seguridad, en los siguientes espacios de su distrito:",
             relevant=rel_si)

    matriz_filas = [
        ("p9_discotecas", "Discotecas, bares, sitios de entretenimiento"),
        ("p9_espacios_recreativos", "Espacios recreativos (parques, play, plaza de deportes)"),
        ("p9_residencia", "Lugar de residencia (casa de habitación)"),
        ("p9_paradas", "Paradas y/o estaciones de buses, taxis, trenes"),
        ("p9_puentes", "Puentes peatonales"),
        ("p9_transporte", "Transporte público"),
        ("p9_bancaria", "Zona bancaria"),
        ("p9_comercio", "Zona comercial"),
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
    # P5: Riesgos / factores situacionales (12 a 18) + glosario
    # ======================================================================================
    survey_rows.append({
        "type": "begin_group",
        "name": "p5_riesgos_factores",
        "label": "Riesgos y factores situacionales",
        "appearance": "field-list",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p12_prob_situacionales",
        "name": "p12_problemas_situacionales",
        "label": "12. A continuación, se presentará una lista de problemáticas que se catalogan como factores situacionales. Marque todas las opciones que considere presentes en su comunidad:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p13_carencias_inversion",
        "name": "p13_carencias_inversion",
        "label": "13. Marque las carencias que considera presentes en su comunidad:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p14_consumo_drogas_donde",
        "name": "p14_consumo_drogas_donde",
        "label": "14. Según su percepción, el consumo/venta de drogas ocurre principalmente en:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p15_def_infra_vial",
        "name": "p15_deficiencias_infra_vial",
        "label": "15. Marque las deficiencias de infraestructura vial que observa en su comunidad:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p16_bunkeres_espacios",
        "name": "p16_bunkeres_espacios",
        "label": "16. Según su percepción, los puntos tipo “búnker” se ubican principalmente en:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p17_transporte_afect",
        "name": "p17_transporte_informal",
        "label": "17. En su comunidad, el transporte que más afecta la seguridad es:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p18_presencia_policial",
        "name": "p18_presencia_policial",
        "label": "18. En su comunidad, la presencia policial es:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    add_glosario_por_pagina("p5", rel_si, ["Búnkeres"])
    survey_rows.append({"type": "end_group", "name": "p5_end"})

    # ======================================================================================
    # P6: Delitos (19 a 29) + glosario
    # ======================================================================================
    survey_rows.append({
        "type": "begin_group",
        "name": "p6_delitos",
        "label": "Delitos",
        "appearance": "field-list",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p19_delitos_general",
        "name": "p19_delitos_general",
        "label": "19. Marque los delitos o situaciones delictivas que considere presentes en su comunidad:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p20_bunker_percepcion",
        "name": "p20_bunker_percepcion",
        "label": "20. Según su percepción, el consumo/venta de drogas se presenta:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p21_vida",
        "name": "p21_delitos_vida",
        "label": "21. Marque si en su comunidad ha existido presencia de:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p22_sexuales",
        "name": "p22_delitos_sexuales",
        "label": "22. Marque si en su comunidad ha existido presencia de:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p23_asaltos",
        "name": "p23_asaltos",
        "label": "23. Marque los tipos de asalto que considere presentes:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p24_estafas",
        "name": "p24_estafas",
        "label": "24. Marque los tipos de estafa/fraude que considere presentes:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p25_robo_fuerza",
        "name": "p25_robo_fuerza",
        "label": "25. Marque los robos con violencia/fuerza que considere presentes:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p26_abandono",
        "name": "p26_abandono",
        "label": "26. Marque si en su comunidad se ha observado:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p27_explotacion_infantil",
        "name": "p27_explotacion_infantil",
        "label": "27. Según su percepción, si existe explotación infantil, es principalmente:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p28_ambientales",
        "name": "p28_delitos_ambientales",
        "label": "28. Marque si en su comunidad se ha observado:",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p29_trata",
        "name": "p29_trata",
        "label": "29. Según su percepción, si existe trata de personas, es principalmente:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    add_glosario_por_pagina("p6", rel_si, [
        "Extorsión", "Receptación", "Contrabando", "Tráfico de personas (coyotaje)",
        "Estafa", "Tacha", "Ganzúa (pata de chancho)", "Boquete", "Arrebato",
        "Trata de personas", "Explotación infantil", "Acoso callejero"
    ])
    survey_rows.append({"type": "end_group", "name": "p6_end"})

    # ======================================================================================
    # P7: Victimización (30 a 31.4) + glosario
    # ======================================================================================
    survey_rows.append({
        "type": "begin_group",
        "name": "p7_victimizacion",
        "label": "Victimización",
        "appearance": "field-list",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p30_vif",
        "name": "p30_vif",
        "label": "30. En los últimos 12 meses, ¿usted o alguien de su hogar ha sido víctima de violencia intrafamiliar?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_vif = f"({rel_si}) and (${{p30_vif}}='{v_si}')"

    survey_rows.append({
        "type": "select_multiple p301_tipos_vif",
        "name": "p301_tipos_vif",
        "label": "30.1. Marque el/los tipo(s) de violencia que conoce:",
        "required": "yes",
        "relevant": rel_vif
    })

    survey_rows.append({
        "type": "select_one p302_medidas",
        "name": "p302_medidas",
        "label": "30.2. ¿Se aplicaron medidas de protección?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_vif
    })

    survey_rows.append({
        "type": "select_one p303_valoracion_fp",
        "name": "p303_valoracion_fp",
        "label": "30.3. ¿Cómo valora la atención brindada por Fuerza Pública?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_vif
    })

    survey_rows.append({
        "type": "select_one p31_delito_12m",
        "name": "p31_delito_12m",
        "label": "31. En los últimos 12 meses, ¿usted o alguien de su hogar fue víctima de algún delito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_si_vict = f"({rel_si}) and (${{p31_delito_12m}}='{slugify_name('Sí, y denuncié')}' or ${{p31_delito_12m}}='{slugify_name('Sí, pero no denuncié.')}')"

    survey_rows.append({
        "type": "select_multiple p311_situaciones",
        "name": "p311_situaciones",
        "label": "31.1. Marque la(s) situación(es) que aplica(n):",
        "required": "yes",
        "relevant": rel_si_vict
    })

    rel_no_denuncio = f"({rel_si}) and (${{p31_delito_12m}}='{slugify_name('Sí, pero no denuncié.')}')"

    survey_rows.append({
        "type": "select_multiple p312_motivos_no_denuncia",
        "name": "p312_motivos_no_denuncia",
        "label": "31.2. Si NO denunció, indique por qué (marque todas las que apliquen):",
        "required": "yes",
        "relevant": rel_no_denuncio
    })

    survey_rows.append({
        "type": "select_one p313_horario",
        "name": "p313_horario",
        "label": "31.3. Indique el horario aproximado del hecho:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si_vict
    })

    survey_rows.append({
        "type": "select_multiple p314_modo",
        "name": "p314_modo",
        "label": "31.4. Indique el modo o medio utilizado (marque todas las que apliquen):",
        "required": "yes",
        "relevant": rel_si_vict
    })

    add_glosario_por_pagina("p7", rel_si, ["Extorsión", "Tacha", "Ganzúa (pata de chancho)", "Boquete", "Arrebato", "Estafa"])
    survey_rows.append({"type": "end_group", "name": "p7_end"})

    # ======================================================================================
    # P8: Confianza policial + Acciones + Info adicional y cierre (32 a 47) + glosario
    # ======================================================================================
    survey_rows.append({
        "type": "begin_group",
        "name": "p8_confianza_acciones",
        "label": "Confianza policial, acciones y cierre",
        "appearance": "field-list",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p32_identifica_policias",
        "name": "p32_identifica_policias",
        "label": "32. ¿Usted identifica a los oficiales de Fuerza Pública que atienden su comunidad?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p321_interacciones",
        "name": "p321_interacciones",
        "label": "32.1. ¿En cuáles situaciones ha tenido interacción con Fuerza Pública? (marque todas las que apliquen):",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "text",
        "name": "p321_otra_detalle",
        "label": "Otra (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p321_interacciones}}, '{slugify_name('Otra (especifique)')}')"
    })

    survey_rows.append({
        "type": "select_one escala_1_10",
        "name": "p33_confianza_fp",
        "label": "33. En una escala del 1 al 10, ¿qué tanta confianza tiene en Fuerza Pública en su comunidad?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one escala_1_10",
        "name": "p34_atencion_fp",
        "label": "34. En una escala del 1 al 10, ¿cómo califica la atención brindada por Fuerza Pública cuando usted lo requiere?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one escala_1_10",
        "name": "p35_respuesta_fp",
        "label": "35. En una escala del 1 al 10, ¿cómo califica el tiempo de respuesta de Fuerza Pública?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one escala_1_10",
        "name": "p36_relacion_fp",
        "label": "36. En una escala del 1 al 10, ¿cómo califica la relación de Fuerza Pública con la comunidad?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one escala_1_10",
        "name": "p37_presencia_fp",
        "label": "37. En una escala del 1 al 10, ¿cómo califica la presencia policial en su comunidad?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p38_frecuencia",
        "name": "p38_frecuencia_patrullaje",
        "label": "38. ¿Con qué frecuencia observa patrullaje en su comunidad?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p39_si_no_aveces",
        "name": "p39_conoce_contacto",
        "label": "39. ¿Conoce cómo contactar a Fuerza Pública en su comunidad?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p39_si_no_aveces",
        "name": "p40_participa_actividades",
        "label": "40. ¿Usted participa en actividades preventivas o reuniones comunitarias sobre seguridad?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_one p41_opciones",
        "name": "p41_mejoro_seguridad",
        "label": "41. En los últimos meses, ¿considera que la seguridad en su comunidad ha mejorado?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "text",
        "name": "p42_por_que_mejoro",
        "label": "42. Explique brevemente por qué:",
        "required": "no",
        "appearance": "multiline",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "select_multiple p43_acciones_fp",
        "name": "p43_acciones_fp",
        "label": "43. ¿Qué acciones considera prioritarias por parte de Fuerza Pública? (marque todas las que apliquen):",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "text",
        "name": "p43_otro_detalle",
        "label": "Otro (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p43_acciones_fp}}, '{slugify_name('Otro')}')"
    })

    survey_rows.append({
        "type": "select_multiple p44_acciones_muni",
        "name": "p44_acciones_muni",
        "label": "44. ¿Qué acciones considera prioritarias por parte del Gobierno Local/Municipalidad? (marque todas las que apliquen):",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({
        "type": "text",
        "name": "p44_otro_detalle",
        "label": "Otro (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p44_acciones_muni}}, '{slugify_name('Otro')}')"
    })

    survey_rows.append({
        "type": "select_one p45_info_delito",
        "name": "p45_info_delito",
        "label": "45. ¿Usted cuenta con información sobre algún delito o situación de riesgo relevante en su comunidad?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_info = f"({rel_si}) and (${{p45_info_delito}}='{v_si}')"
    survey_rows.append({
        "type": "text",
        "name": "p46_detalle_info",
        "label": "46. Describa brevemente la información que considera importante:",
        "required": "no",
        "appearance": "multiline",
        "relevant": rel_info
    })

    survey_rows.append({
        "type": "text",
        "name": "p47_comentarios_finales",
        "label": "47. Comentarios finales (opcional):",
        "required": "no",
        "appearance": "multiline",
        "relevant": rel_si
    })

    add_glosario_por_pagina("p8", rel_si, ["Coordinación interinstitucional", "Integridad y credibilidad policial", "Acciones disuasivas", "Patrullaje"])
    survey_rows.append({"type": "end_group", "name": "p8_end"})

    # ===========================
    # DataFrames finales
    # ===========================
    # choices: normalizar columnas
    df_choices = pd.DataFrame(choices_rows)
    for col in ["list_name", "name", "label", "canton_key"]:
        if col not in df_choices.columns:
            df_choices[col] = ""
    df_choices = df_choices[["list_name", "name", "label", "canton_key"]]
    df_choices = df_choices.drop_duplicates(subset=["list_name", "name"], keep="first").reset_index(drop=True)

    df_survey = pd.DataFrame(survey_rows)

    df_settings = pd.DataFrame([{
        "form_title": form_title,
        "form_id": slugify_name(form_title)[:50],
        "version": version,
        "default_language": idioma,
        "style": "pages"
    }])

    return df_survey, df_choices, df_settings


# ==========================================================================================
# Generación / Descarga
# ==========================================================================================
st.markdown("## ✅ Generar XLSForm")

col_g1, col_g2 = st.columns([1, 2])
with col_g1:
    generar = st.button("Generar XLSForm", type="primary", use_container_width=True)
with col_g2:
    st.caption("Si el distrito te daba error apenas entrabas, ya quedó corregido con un `relevant` adicional.")

if generar:
    df_survey, df_choices, df_settings = construir_xlsform(
        form_title=form_title,
        logo_media_name=logo_media_name,
        idioma=idioma,
        version=version,
        catalogo_rows=st.session_state.choices_ext_rows
    )

    st.success("XLSForm generado. Revisa una vista previa abajo y descárgalo.")

    with st.expander("Vista previa — settings", expanded=False):
        st.dataframe(df_settings, use_container_width=True, hide_index=True)

    with st.expander("Vista previa — survey (primeras 60 filas)", expanded=False):
        st.dataframe(df_survey.head(60), use_container_width=True, hide_index=True, height=420)

    with st.expander("Vista previa — choices (primeras 80 filas)", expanded=False):
        st.dataframe(df_choices.head(80), use_container_width=True, hide_index=True, height=420)

    nombre_archivo = f"{slugify_name(form_title)}_{version}.xlsx"
    descargar_xlsform(df_survey, df_choices, df_settings, nombre_archivo)
