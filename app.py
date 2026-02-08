# app.py
# ======================================================================================
# Encuesta Comunidad 2026 (V.4.1) - App Streamlit + Generador XLSForm (Survey123/ArcGIS)
#
# Requisitos:
#   pip install streamlit openpyxl
#
# Ejecutar:
#   streamlit run app.py
# ======================================================================================

import json
import re
from datetime import datetime
from io import BytesIO

import streamlit as st
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

# ----------------------------- Config -----------------------------
st.set_page_config(page_title="Encuesta Comunidad 2026", layout="wide")

# ----------------------------- Utils -----------------------------
def slug_code(label: str) -> str:
    """Convierte una etiqueta a un 'name' seguro para XLSForm."""
    if label is None:
        return "vacio"
    s = label.strip().lower()
    s = (
        s.replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    )
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s\-]+", "_", s).strip("_")
    if not s:
        s = "opcion"
    return s[:63]


def ss_init_answers():
    if "answers" not in st.session_state:
        st.session_state["answers"] = {}


def save_answer(qid, value):
    ss_init_answers()
    st.session_state["answers"][qid] = value


def read_answer(qid, default=None):
    ss_init_answers()
    return st.session_state["answers"].get(qid, default)


def divider():
    st.markdown("---")


def title_block(title, subtitle=None):
    st.markdown(f"## {title}")
    if subtitle:
        st.info(subtitle)


def multiselect_exclusive(label, options, exclusive_option, qid, help_text=None):
    """Multiselect con exclusión (si se elige la opción exclusiva, no se pueden combinar otras)."""
    current = read_answer(qid, [])
    if not isinstance(current, list):
        current = []
    sel = st.multiselect(label, options, default=current, help=help_text, key=f"ui_{qid}")

    if exclusive_option in sel and len(sel) > 1:
        sel = [exclusive_option]
        st.warning(f'La opción "{exclusive_option}" no puede combinarse con otras.')
        st.session_state[f"ui_{qid}"] = sel

    save_answer(qid, sel)
    return sel


def radio_required(label, options, qid, help_text=None, horizontal=False):
    current = read_answer(qid, None)
    if current not in options:
        current = options[0]
    sel = st.radio(
        label, options, index=options.index(current),
        help=help_text, horizontal=horizontal, key=f"ui_{qid}"
    )
    save_answer(qid, sel)
    return sel


def select_required(label, options, qid, help_text=None):
    current = read_answer(qid, None)
    if current not in options:
        current = options[0]
    sel = st.selectbox(
        label, options, index=options.index(current),
        help=help_text, key=f"ui_{qid}"
    )
    save_answer(qid, sel)
    return sel


def text_area_optional(label, qid, help_text=None, placeholder=""):
    current = read_answer(qid, "")
    val = st.text_area(
        label, value=current, help=help_text, placeholder=placeholder, key=f"ui_{qid}"
    )
    save_answer(qid, val)
    return val


def text_input_optional(label, qid, help_text=None, placeholder=""):
    current = read_answer(qid, "")
    val = st.text_input(
        label, value=current, help=help_text, placeholder=placeholder, key=f"ui_{qid}"
    )
    save_answer(qid, val)
    return val


def slider_int(label, min_v, max_v, qid, help_text=None):
    current = read_answer(qid, min_v)
    if not isinstance(current, int):
        current = min_v
    val = st.slider(
        label, min_value=min_v, max_value=max_v, value=current,
        help=help_text, key=f"ui_{qid}"
    )
    save_answer(qid, val)
    return val


# ======================================================================================
# Catálogos (mismos textos que usa la App) -> se reutilizan para generar XLSForm
# ======================================================================================

YESNO = ["Sí", "No"]

Q3_EDAD = ["18 a 29 años", "30 a 44 años", "45 a 64 años", "65 años o más"]

Q4_GENERO = ["Femenino", "Masculino", "Persona no Binaria", "Prefiero no decir"]

Q5_ESCOLARIDAD = [
    "Ninguna",
    "Primaria incompleta",
    "Primaria completa",
    "Secundaria incompleta",
    "Secundaria completa",
    "Técnico",
    "Universitaria incompleta",
    "Universitaria completa",
]

Q6_RELACION = ["Vivo en la zona", "Trabajo en la zona", "Visito la zona", "Estudio en la zona"]

Q7_ESCALA = ["Muy inseguro", "Inseguro", "Ni seguro ni inseguro", "Seguro", "Muy seguro"]

Q7_1_OPTS = [
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
    "Presencia de personas en situación de calle que influye en su percepción de seguridad",
    "Presencia de personas en situación de ocio (sin actividad laboral o educativa)",
    "Ventas informales (ambulantes)",
    "Problemas con transporte informal",
    "Falta de patrullajes visibles",
    "Falta de presencia policial en la zona",
    "Situaciones de violencia intrafamiliar",
    "Situaciones de violencia de género",
    "Otro problema que considere importante (especifique abajo)",
]
Q7_1_OTRO_LABEL = "Otro problema que considere importante (especifique abajo)"

Q8_CAMBIO = [
    "1 (Mucho menos seguro)",
    "2 (Menos seguro)",
    "3 (Se mantiene igual)",
    "4 (Más seguro)",
    "5 (Mucho más seguro)",
]

Q9_ZONAS = [
    "Discotecas, bares, sitios de entretenimiento",
    "Espacios recreativos (parques, play, plaza de deportes)",
    "Lugar de residencia (casa de habitación)",
    "Paradas y/o estaciones de buses, taxis, trenes",
    "Puentes peatonales",
    "Transporte público",
    "Zona bancaria",
    "Zona de comercio",
    "Zonas residenciales (calles y barrios, distinto a su casa)",
    "Zonas francas",
    "Lugares de interés turístico",
    "Centros educativos",
]
Q9_ESCALA = ["1 (Muy inseguro)", "2 (Inseguro)", "3 (Ni seguro ni inseguro)", "4 (Seguro)", "5 (Muy seguro)", "No aplica"]

Q10_OPTS = [
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
    "Otros (especifique abajo)",
]
Q10_OTRO = "Otros (especifique abajo)"

Q12_OPTS = [
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
    "Otro problema que considere importante (especifique abajo)",
    "No se observan estas problemáticas en el distrito",
]
Q12_EXCL = "No se observan estas problemáticas en el distrito"
Q12_OTRO_LABEL = "Otro problema que considere importante (especifique abajo)"

Q13_OPTS = [
    "Falta de oferta educativa",
    "Falta de oferta deportiva",
    "Falta de oferta recreativa",
    "Falta de actividades culturales",
    "Otro problema que considere importante (especifique abajo)",
]
Q13_OTRO_LABEL = "Otro problema que considere importante (especifique abajo)"

Q14_OPTS = [
    "Áreas públicas (calles, parques, paradas, espacios abiertos)",
    "Áreas privadas (viviendas, locales, espacios cerrados)",
    "No se observa consumo de drogas",
]
Q14_EXCL = "No se observa consumo de drogas"

Q15_OPTS = ["Calles en mal estado", "Falta de señalización de tránsito", "Carencia o inexistencia de aceras"]

Q16_OPTS = ["Casa de habitación (espacio cerrado)", "Edificación abandonada", "Lote baldío", "Otro tipo de espacio (especifique abajo)", "No se observa"]
Q16_EXCL = "No se observa"
Q16_OTRO_LABEL = "Otro tipo de espacio (especifique abajo)"

Q17_OPTS = [
    "Transporte informal o no autorizado (taxis piratas)",
    "Plataformas de transporte digital",
    "Transporte público (buses)",
    "Servicios de reparto o mensajería “exprés” (por ejemplo, repartidores en motocicleta o bicimoto)",
    "Otro tipo de situación relacionada con el transporte (especifique abajo)",
    "No se observa",
]
Q17_EXCL = "No se observa"
Q17_OTRO_LABEL = "Otro tipo de situación relacionada con el transporte (especifique abajo)"

Q18_OPTS = [
    "Disturbios en vía pública (riñas o agresiones)",
    "Daños a la propiedad (viviendas, comercios, vehículos u otros bienes)",
    "Daños al poliducto (perforaciones, tomas ilegales o vandalismo)",
    "Extorsión (amenazas o intimidación para exigir dinero u otros beneficios)",
    "Hurto (sustracción de artículos mediante el descuido)",
    "Compra o venta de artículos robados (receptación)",
    "Contrabando (licor, cigarrillos, medicinas, ropa, calzado, etc.)",
    "Maltrato animal",
    "Tráfico de personas (coyotaje)",
    "Otro delito (especifique abajo)",
    "No se observan delitos",
]
Q18_EXCL = "No se observan delitos"
Q18_OTRO_LABEL = "Otro delito (especifique abajo)"

Q19_OPTS = [
    "En espacios cerrados (casas, edificaciones u otros inmuebles)",
    "En vía pública",
    "De forma ocasional o móvil (sin punto fijo)",
    "No se observa venta de drogas",
    "Otro (especifique abajo)",
]
Q19_EXCL = "No se observa venta de drogas"
Q19_OTRO_LABEL = "Otro (especifique abajo)"

Q20_OPTS = [
    "Homicidios (muerte intencional de una persona)",
    "Personas heridas de forma intencional (heridos)",
    "Femicidio (homicidio de una mujer por razones de género)",
    "No se observan delitos contra la vida",
]
Q20_EXCL = "No se observan delitos contra la vida"

Q21_OPTS = [
    "Abuso sexual (tocamientos u otros actos sexuales sin consentimiento)",
    "Violación (acceso sexual sin consentimiento)",
    "Acoso sexual (insinuaciones, solicitudes o conductas sexuales no deseadas)",
    "Acoso callejero (comentarios, gestos o conductas sexuales en espacios públicos)",
    "No se observan delitos sexuales",
]
Q21_EXCL = "No se observan delitos sexuales"

Q22_OPTS = ["Asalto a personas", "Asalto a comercio", "Asalto a vivienda", "Asalto a transporte público", "No se observan asaltos"]
Q22_EXCL = "No se observan asaltos"

Q23_OPTS = [
    "Billetes falsos",
    "Documentos falsos",
    "Estafas relacionadas con la compra o venta de oro",
    "Lotería falsa",
    "Estafas informáticas (por internet, redes sociales o correos electrónicos)",
    "Estafas telefónicas",
    "Estafas con tarjetas (clonación, cargos no autorizados)",
    "No se observan estafas",
]
Q23_EXCL = "No se observan estafas"

Q24_OPTS = [
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
]
Q24_EXCL = "No se observan robos"

Q25_OPTS = ["Abandono de adulto mayor", "Abandono de menor de edad", "Abandono de incapaz", "No se observan situaciones de abandono"]
Q25_EXCL = "No se observan situaciones de abandono"

Q26_OPTS = ["Sexual", "Laboral", "No se observan"]
Q26_EXCL = "No se observan"

Q27_OPTS = ["Caza ilegal", "Pesca ilegal", "Tala ilegal", "Extracción ilegal de material minero", "No se observan delitos ambientales"]
Q27_EXCL = "No se observan delitos ambientales"

Q28_OPTS = ["Con fines laborales", "Con fines sexuales", "No se observan situaciones de trata de personas"]
Q28_EXCL = "No se observan situaciones de trata de personas"

Q29_1_OPTS = [
    "Violencia psicológica (gritos, amenazas, humillaciones, maltratos, entre otros)",
    "Violencia física (agresiones físicas, empujones, golpes, entre otros)",
    "Violencia vicaria (uso de hijas, hijos u otras personas para causar daño emocional)",
    "Violencia patrimonial (destrucción, retención o control de bienes, documentos o dinero)",
    "Violencia sexual (actos de carácter sexual sin consentimiento)",
]

Q29_2_OPTS = ["Sí", "No", "No recuerda"]

Q29_3_OPTS = ["Excelente", "Bueno", "Regular", "Malo", "Muy malo"]

Q30_OPTS = ["NO", "Sí, y denuncié", "Sí, pero no denuncié"]

Q30_1_OPTS = [
    "Asalto a mano armada en la calle o espacio público",
    "Asalto en el transporte público",
    "Asalto o robo de su vehículo (coche, motocicleta, etc.)",
    "Robo de accesorios o partes de su vehículo (espejos, llantas, radio)",
    "Robo o intento de robo con fuerza a su vivienda (forzar puerta/ventana)",
    "Robo o intento de robo con fuerza a su comercio o negocio",
    "Hurto de su cartera, bolso o celular (sin darse cuenta)",
    "Daños a su propiedad (grafitis, rotura de cristales, cercas, etc.)",
    "Receptación (alguien en su hogar compró/recibió un artículo y luego supo que era robado)",
    "Pérdida de artículos por descuido (celular, bicicleta, etc.)",
    "Estafa telefónica",
    "Estafa o fraude informático (internet/redes/correo)",
    "Fraude con tarjetas bancarias (clonación/uso no autorizado)",
    "Ser víctima de billetes o documentos falsos",
    "Extorsión (intimidación o amenaza para obtener dinero u otro beneficio)",
    "Maltrato animal",
    "Acoso o intimidación sexual en un espacio público",
    "Algún tipo de delito sexual (abuso, violación)",
    "Lesiones personales (herido en riña o agresión)",
    "Otro (especifique abajo)",
]
Q30_1_OTRO_LABEL = "Otro (especifique abajo)"

Q30_2_OPTS = [
    "Distancia o dificultad de acceso a oficinas para denunciar",
    "Miedo a represalias",
    "Falta de respuesta o seguimiento en denuncias anteriores",
    "Complejidad o dificultad para realizar la denuncia (trámites, requisitos, tiempo)",
    "Desconocimiento de dónde colocar la denuncia (falta de información)",
    "El policía me dijo que era mejor no denunciar",
    "Falta de tiempo para colocar la denuncia",
    "Desconfianza en las autoridades o en el proceso de denuncia",
    "Otro motivo (especifique abajo)",
]
Q30_2_OTRO_LABEL = "Otro motivo (especifique abajo)"

Q30_3_OPTS = [
    "00:00 – 02:59 (madrugada)",
    "03:00 – 05:59 (madrugada)",
    "06:00 – 08:59 (mañana)",
    "09:00 – 11:59 (mañana)",
    "12:00 – 14:59 (mediodía / tarde)",
    "15:00 – 17:59 (tarde)",
    "18:00 – 20:59 (noche)",
    "21:00 – 23:59 (noche)",
    "Desconocido",
]

Q30_4_OPTS = [
    "Arma blanca (cuchillo, machete, tijeras)",
    "Arma de fuego",
    "Amenazas o intimidación",
    "Arrebato (le quitaron un objeto de forma rápida o sorpresiva)",
    "Boquete (apertura de huecos en paredes/techos/estructuras)",
    "Ganzúa (pata de chancho, llaves falsas u objetos similares)",
    "Engaño (mentiras, falsas ofertas o distracción)",
    "Escalamiento (trepando muros, rejas o techos)",
    "Otro (especifique abajo)",
    "No sabe / No recuerda",
]
Q30_4_OTRO_LABEL = "Otro (especifique abajo)"

Q31_1_OPTS = [
    "Solicitud de ayuda o auxilio",
    "Atención relacionada con una denuncia",
    "Atención cordial o preventiva durante un patrullaje",
    "Fui abordado o registrado para identificación",
    "Fui objeto de una infracción o conflicto",
    "Evento preventivo (cívico policial, reunión comunitaria)",
    "Otra (especifique abajo)",
]
Q31_1_OTRO_LABEL = "Otra (especifique abajo)"

Q37_OPTS = ["Todos los días", "Varias veces por semana", "Una vez por semana", "Casi nunca", "Nunca"]

Q38_OPTS = ["Sí", "No", "A veces"]
Q39_OPTS = ["Sí", "No", "A veces"]
Q40_OPTS = ["Sí", "No", "No estoy seguro(a)"]
Q41_OPTS = ["Sí", "No", "A veces"]

Q42_OPTS = [
    "Mayor presencia policial y patrullaje",
    "Acciones disuasivas en puntos conflictivos",
    "Acciones contra consumo y venta de drogas",
    "Mejorar el servicio policial a la comunidad",
    "Acercamiento comunitario y comercial",
    "Actividades de prevención y educación",
    "Coordinación interinstitucional",
    "Integridad y credibilidad policial",
    "Otro (especifique abajo)",
    "No tiene una opinión al respecto",
]
Q42_EXCL = "No tiene una opinión al respecto"
Q42_OTRO_LABEL = "Otro (especifique abajo)"

Q43_OPTS = [
    "Mantenimiento e iluminación del espacio público",
    "Limpieza y ordenamiento urbano",
    "Instalación de cámaras y seguridad municipal",
    "Control del comercio informal y transporte",
    "Creación y mejoramiento de espacios públicos",
    "Desarrollo social y generación de empleo",
    "Coordinación interinstitucional",
    "Acercamiento municipal a comercio y comunidad",
    "Otro (especifique abajo)",
    "No tiene una opinión al respecto",
]
Q43_EXCL = "No tiene una opinión al respecto"
Q43_OTRO_LABEL = "Otro (especifique abajo)"

# ======================================================================================
# XLSForm Generator (Survey123)
# ======================================================================================

def _autosize(ws, max_col=20):
    for col in range(1, max_col + 1):
        ws.column_dimensions[get_column_letter(col)].width = 32


def build_xlsform_bytes(include_geopoint: bool = True) -> bytes:
    """
    Genera XLSForm (.xlsx) en memoria con:
      - settings, survey, choices
      - condicionales (relevant)
    """
    wb = Workbook()

    # ---------------- settings ----------------
    ws_settings = wb.active
    ws_settings.title = "settings"
    ws_settings.append(["form_title", "form_id", "version", "default_language"])
    ws_settings.append(["Encuesta Comunidad 2026", "encuesta_comunidad_2026", "v4_1", "es"])
    _autosize(ws_settings, 6)

    # ---------------- choices ----------------
    ws_choices = wb.create_sheet("choices")
    ws_choices.append(["list_name", "name", "label"])

    def add_choice_list(list_name: str, labels: list[str]):
        seen = set()
        for lab in labels:
            base = slug_code(lab)
            code = base
            i = 2
            while code in seen:
                code = f"{base}_{i}"
                i += 1
            seen.add(code)
            ws_choices.append([list_name, code, lab])

    # cargar listas
    add_choice_list("yesno", YESNO)
    add_choice_list("edad_rango", Q3_EDAD)
    add_choice_list("genero", Q4_GENERO)
    add_choice_list("escolaridad", Q5_ESCOLARIDAD)
    add_choice_list("relacion_zona", Q6_RELACION)
    add_choice_list("seguridad_5", Q7_ESCALA)
    add_choice_list("razones_inseguridad", Q7_1_OPTS)
    add_choice_list("cambio_5", Q8_CAMBIO)
    add_choice_list("espacios", Q9_ZONAS)
    add_choice_list("seguridad_5_na", Q9_ESCALA)
    add_choice_list("foco_inseguridad", Q10_OPTS)
    add_choice_list("prob_12", Q12_OPTS)
    add_choice_list("car_13", Q13_OPTS)
    add_choice_list("donde_14", Q14_OPTS)
    add_choice_list("vial_15", Q15_OPTS)
    add_choice_list("venta_16", Q16_OPTS)
    add_choice_list("transp_17", Q17_OPTS)
    add_choice_list("delitos_18", Q18_OPTS)
    add_choice_list("ventaforma_19", Q19_OPTS)
    add_choice_list("vida_20", Q20_OPTS)
    add_choice_list("sex_21", Q21_OPTS)
    add_choice_list("asaltos_22", Q22_OPTS)
    add_choice_list("estafas_23", Q23_OPTS)
    add_choice_list("robos_24", Q24_OPTS)
    add_choice_list("abandono_25", Q25_OPTS)
    add_choice_list("explinf_26", Q26_OPTS)
    add_choice_list("amb_27", Q27_OPTS)
    add_choice_list("trata_28", Q28_OPTS)
    add_choice_list("vif_29_1", Q29_1_OPTS)
    add_choice_list("medidas_29_2", Q29_2_OPTS)
    add_choice_list("val_29_3", Q29_3_OPTS)
    add_choice_list("vict_30", Q30_OPTS)
    add_choice_list("vict_30_1", Q30_1_OPTS)
    add_choice_list("noden_30_2", Q30_2_OPTS)
    add_choice_list("horario_30_3", Q30_3_OPTS)
    add_choice_list("modo_30_4", Q30_4_OPTS)
    add_choice_list("at_31_1", Q31_1_OPTS)
    add_choice_list("freq_37", Q37_OPTS)
    add_choice_list("sionoaveces", Q38_OPTS)
    add_choice_list("quejas_40", Q40_OPTS)
    add_choice_list("fp_42", Q42_OPTS)
    add_choice_list("muni_43", Q43_OPTS)

    _autosize(ws_choices, 3)

    # maps label->name por list
    list_maps = {}
    for row in ws_choices.iter_rows(min_row=2, values_only=True):
        list_name, name, label = row
        list_maps.setdefault(list_name, {})[label] = name

    def code(list_name: str, label: str) -> str:
        return list_maps[list_name][label]

    # ---------------- survey ----------------
    ws_survey = wb.create_sheet("survey")
    headers = [
        "type", "name", "label", "hint", "required",
        "relevant", "constraint", "constraint_message",
        "appearance", "calculation"
    ]
    ws_survey.append(headers)

    def add_q(qtype, name, label, hint="", required="no", relevant="", constraint="", constraint_msg="", appearance="", calc=""):
        ws_survey.append([qtype, name, label, hint, required, relevant, constraint, constraint_msg, appearance, calc])

    if include_geopoint:
        add_q("geopoint", "location", "Ubicación (marque en el mapa)", required="no")

    add_q("select_one yesno", "consent", "¿Acepta participar en esta encuesta?", required="yes")
    rel_form = f"${{consent}}='{code('yesno','Sí')}'"

    # I
    add_q("begin_group", "g_demo", "I. Datos demográficos", relevant=rel_form)
    add_q("text", "canton", "1. Cantón:", relevant=rel_form)
    add_q("text", "distrito", "2. Distrito:", relevant=rel_form)
    add_q("select_one edad_rango", "edad_rango", "3. Edad (en años cumplidos):", required="yes", relevant=rel_form)
    add_q("select_one genero", "genero", "4. ¿Con cuál de estas opciones se identifica?", required="yes", relevant=rel_form)
    add_q("select_one escolaridad", "escolaridad", "5. Escolaridad:", required="yes", relevant=rel_form)
    add_q("select_one relacion_zona", "relacion_zona", "6. ¿Cuál es su relación con la zona?", required="yes", relevant=rel_form)
    add_q("end_group", "g_demo_end", "")

    # II
    add_q("begin_group", "g_perc", "II. Percepción ciudadana de seguridad en el distrito", relevant=rel_form)
    add_q("select_one seguridad_5", "seg_distrito", "7. ¿Qué tan seguro percibe usted el distrito donde reside o transita?", required="yes", relevant=rel_form)

    rel_7_1 = (
        f"{rel_form} and ("
        f"${{seg_distrito}}='{code('seguridad_5','Muy inseguro')}' or "
        f"${{seg_distrito}}='{code('seguridad_5','Inseguro')}'"
        f")"
    )
    add_q("select_multiple razones_inseguridad", "razones_inseguridad",
          "7.1. Indique por qué considera el distrito inseguro (selección múltiple)", relevant=rel_7_1)
    add_q(
        "text", "razones_inseguridad_otro", "7.1 Otro (especifique):",
        relevant=f"{rel_7_1} and selected(${{razones_inseguridad}}, '{code('razones_inseguridad', Q7_1_OTRO_LABEL)}')"
    )

    add_q("select_one cambio_5", "cambio_seg",
          "8. En comparación con los 12 meses anteriores, ¿cómo percibe que ha cambiado la seguridad en este distrito?",
          required="yes", relevant=rel_form)
    add_q("text", "cambio_seg_porque", "8.1. Indique por qué (explique brevemente):", relevant=rel_form)

    add_q("begin_repeat", "r_matriz_9", "9. Seguridad por tipo de espacio (una fila por espacio)", relevant=rel_form)
    add_q("select_one espacios", "espacio_9", "Espacio", required="yes", relevant=rel_form)
    add_q("select_one seguridad_5_na", "valor_9", "Nivel de seguridad percibida", required="yes", relevant=rel_form)
    add_q("end_repeat", "r_matriz_9_end", "")

    add_q("select_one foco_inseguridad", "foco_10", "10. Principal foco de inseguridad en el distrito", required="yes", relevant=rel_form)
    add_q("text", "foco_10_otro", "10. Otros (especifique):", relevant=f"{rel_form} and ${{foco_10}}='{code('foco_inseguridad', Q10_OTRO)}'")
    add_q("text", "razones_11",
          "11. Describa brevemente las razones por las cuales considera inseguro el espacio seleccionado:", relevant=rel_form)
    add_q("end_group", "g_perc_end", "")

    # III
    add_q("begin_group", "g_riesgos", "III. Riesgos, delitos, victimización y evaluación policial", relevant=rel_form)
    add_q("select_multiple prob_12", "prob_12", "12. Problemáticas que afectan su distrito (selección múltiple)", relevant=rel_form)
    add_q("text", "prob_12_otro", "12. Otro (especifique):", relevant=f"{rel_form} and selected(${{prob_12}}, '{code('prob_12', Q12_OTRO_LABEL)}')")

    add_q("select_multiple car_13", "car_13", "13. Carencias que identifica (selección múltiple)", relevant=rel_form)
    add_q("text", "car_13_otro", "13. Otro (especifique):", relevant=f"{rel_form} and selected(${{car_13}}, '{code('car_13', Q13_OTRO_LABEL)}')")

    add_q("select_multiple donde_14", "donde_14", "14. ¿Dónde ocurre el consumo de drogas? (selección múltiple)", relevant=rel_form)
    add_q("select_multiple vial_15", "vial_15", "15. Deficiencias de infraestructura vial (selección múltiple)", relevant=rel_form)

    add_q("select_multiple venta_16", "venta_16", "16. Espacios donde se identifica venta de drogas (selección múltiple)", relevant=rel_form)
    add_q("text", "venta_16_otro", "16. Otro (especifique):", relevant=f"{rel_form} and selected(${{venta_16}}, '{code('venta_16', Q16_OTRO_LABEL)}')")

    add_q("select_multiple transp_17", "transp_17", "17. Inseguridad asociada a transporte (selección múltiple)", relevant=rel_form)
    add_q("text", "transp_17_otro", "17. Otro (especifique):", relevant=f"{rel_form} and selected(${{transp_17}}, '{code('transp_17', Q17_OTRO_LABEL)}')")

    add_q("select_multiple delitos_18", "delitos_18", "18. Delitos que se presentan en el distrito (selección múltiple)", relevant=rel_form)
    add_q("text", "delitos_18_otro", "18. Otro delito (especifique):", relevant=f"{rel_form} and selected(${{delitos_18}}, '{code('delitos_18', Q18_OTRO_LABEL)}')")

    add_q("select_multiple ventaforma_19", "ventaforma_19", "19. Forma de venta de drogas (selección múltiple)", relevant=rel_form)
    add_q("text", "ventaforma_19_otro", "19. Otro (especifique):", relevant=f"{rel_form} and selected(${{ventaforma_19}}, '{code('ventaforma_19', Q19_OTRO_LABEL)}')")

    add_q("select_multiple vida_20", "vida_20", "20. Delitos contra la vida (selección múltiple)", relevant=rel_form)
    add_q("select_multiple sex_21", "sex_21", "21. Delitos sexuales (selección múltiple)", relevant=rel_form)
    add_q("select_multiple asaltos_22", "asaltos_22", "22. Asaltos (selección múltiple)", relevant=rel_form)
    add_q("select_multiple estafas_23", "estafas_23", "23. Estafas (selección múltiple)", relevant=rel_form)
    add_q("select_multiple robos_24", "robos_24", "24. Robos (selección múltiple)", relevant=rel_form)
    add_q("select_multiple abandono_25", "abandono_25", "25. Abandono de personas (selección múltiple)", relevant=rel_form)
    add_q("select_multiple explinf_26", "explinf_26", "26. Explotación infantil (selección múltiple)", relevant=rel_form)
    add_q("select_multiple amb_27", "amb_27", "27. Delitos ambientales (selección múltiple)", relevant=rel_form)
    add_q("select_multiple trata_28", "trata_28", "28. Trata de personas (selección múltiple)", relevant=rel_form)

    add_q("select_one yesno", "vif_29", "29. En los últimos 12 meses, ¿su hogar fue afectado por violencia intrafamiliar?", required="yes", relevant=rel_form)
    rel_29 = f"{rel_form} and ${{vif_29}}='{code('yesno','Sí')}'"
    add_q("select_multiple vif_29_1", "vif_29_1", "29.1 Tipo(s) de violencia (selección múltiple)", relevant=rel_29)
    add_q("select_one medidas_29_2", "medidas_29_2", "29.2 ¿Solicitó medidas de protección?", relevant=rel_29)
    add_q("select_one val_29_3", "abordaje_29_3", "29.3 Abordaje de Fuerza Pública", relevant=rel_29)

    add_q("select_one vict_30", "vict_30", "30. En los últimos 12 meses, ¿su hogar fue afectado por algún delito?", required="yes", relevant=rel_form)
    rel_30 = f"{rel_form} and ${{vict_30}}!='{code('vict_30','NO')}'"
    add_q("select_multiple vict_30_1", "vict_30_1", "30.1 Situación(es) (selección múltiple)", relevant=rel_30)
    add_q("text", "vict_30_1_otro", "30.1 Otro (especifique):", relevant=f"{rel_30} and selected(${{vict_30_1}}, '{code('vict_30_1', Q30_1_OTRO_LABEL)}')")

    rel_30_2 = f"{rel_form} and ${{vict_30}}='{code('vict_30','Sí, pero no denuncié')}'"
    add_q("select_multiple noden_30_2", "noden_30_2", "30.2 Motivo(s) de no denunciar (selección múltiple)", relevant=rel_30_2)
    add_q("text", "noden_30_2_otro", "30.2 Otro (especifique):", relevant=f"{rel_30_2} and selected(${{noden_30_2}}, '{code('noden_30_2', Q30_2_OTRO_LABEL)}')")

    add_q("select_one horario_30_3", "horario_30_3", "30.3 Horario del hecho", relevant=rel_30)
    add_q("select_multiple modo_30_4", "modo_30_4", "30.4 Forma o modo (selección múltiple)", relevant=rel_30)
    add_q("text", "modo_30_4_otro", "30.4 Otro (especifique):", relevant=f"{rel_30} and selected(${{modo_30_4}}, '{code('modo_30_4', Q30_4_OTRO_LABEL)}')")

    add_q("end_group", "g_riesgos_end", "")

    # Confianza (31–41)
    add_q("begin_group", "g_conf", "Confianza policial", relevant=rel_form)
    add_q("select_one yesno", "idpol_31", "31. ¿Identifica a los policías en su comunidad?", required="yes", relevant=rel_form)
    rel_31 = f"{rel_form} and ${{idpol_31}}='{code('yesno','Sí')}'"
    add_q("select_multiple at_31_1", "at_31_1", "31.1 Tipo de atención (selección múltiple)", relevant=rel_31)
    add_q("text", "at_31_1_otro", "31.1 Otra (especifique):", relevant=f"{rel_31} and selected(${{at_31_1}}, '{code('at_31_1', Q31_1_OTRO_LABEL)}')")

    add_q("integer", "conf_32", "32. Nivel de confianza (1 a 10)", relevant=rel_31, constraint=".>=1 and .<=10", constraint_msg="Debe estar entre 1 y 10")

    for nm, lbl in [
        ("prof_33", "33. Profesionalidad de la Fuerza Pública (1 a 10)"),
        ("cal_34", "34. Calidad del servicio policial (1 a 10)"),
        ("sat_35", "35. Satisfacción con el trabajo preventivo (1 a 10)"),
        ("contrib_36", "36. Contribución de la presencia policial para reducir crimen (1 a 10)"),
    ]:
        add_q("integer", nm, lbl, relevant=rel_form, constraint=".>=1 and .<=10", constraint_msg="Debe estar entre 1 y 10")

    add_q("select_one freq_37", "freq_37", "37. Frecuencia de presencia policial", required="yes", relevant=rel_form)
    add_q("select_one sionoaveces", "cons_38", "38. Presencia consistente a lo largo del día", required="yes", relevant=rel_form)
    add_q("select_one sionoaveces", "just_39", "39. Trato justo e imparcial", required="yes", relevant=rel_form)
    add_q("select_one quejas_40", "quejas_40", "40. Puede expresar quejas sin temor", required="yes", relevant=rel_form)
    add_q("select_one sionoaveces", "info_41", "41. Información veraz, clara y oportuna", required="yes", relevant=rel_form)
    add_q("end_group", "g_conf_end", "")

    # Propuestas
    add_q("begin_group", "g_prop", "Propuestas", relevant=rel_form)
    add_q("select_multiple fp_42", "fp_42", "42. ¿Qué actividad debe realizar la Fuerza Pública? (selección múltiple)", relevant=rel_form)
    add_q("text", "fp_42_otro", "42. Otro (especifique):", relevant=f"{rel_form} and selected(${{fp_42}}, '{code('fp_42', Q42_OTRO_LABEL)}')")

    add_q("select_multiple muni_43", "muni_43", "43. ¿Qué actividad debe realizar la Municipalidad? (selección múltiple)", relevant=rel_form)
    add_q("text", "muni_43_otro", "43. Otro (especifique):", relevant=f"{rel_form} and selected(${{muni_43}}, '{code('muni_43', Q43_OTRO_LABEL)}')")
    add_q("end_group", "g_prop_end", "")

    # Info adicional
    add_q("begin_group", "g_extra", "Información adicional", relevant=rel_form)
    add_q("select_one yesno", "info_44", "44. ¿Tiene información de persona o grupo que se dedique a delitos?", required="yes", relevant=rel_form)
    add_q("text", "info_44_1", "44.1 Describa características:", relevant=f"{rel_form} and ${{info_44}}='{code('yesno','Sí')}'")
    add_q("text", "contacto_45", "45. (Voluntario) Contacto:", relevant=rel_form)
    add_q("text", "extra_46", "46. Otra información pertinente:", relevant=rel_form)
    add_q("end_group", "g_extra_end", "")

    _autosize(ws_survey, len(headers))

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


# ======================================================================================
# Sidebar
# ======================================================================================
st.sidebar.title("Encuesta Comunidad 2026")
st.sidebar.caption("Condicionales + exportar XLSForm")

if st.sidebar.button("🧹 Reiniciar respuestas"):
    st.session_state["answers"] = {}
    for k in list(st.session_state.keys()):
        if k.startswith("ui_"):
            del st.session_state[k]
    st.rerun()

section = st.sidebar.radio(
    "Ir a sección",
    [
        "Consentimiento",
        "I. Datos demográficos",
        "II. Percepción ciudadana",
        "III. Riesgos / delitos / victimización",
        "Confianza policial",
        "Propuestas",
        "Información adicional",
        "Resumen y exportación",
    ],
)

# ======================================================================================
# Main
# ======================================================================================
st.title("📋 Encuesta de Percepción Comunidad 2026 (V.4.1)")
st.caption("App: preguntas + opciones + condicionales + descarga XLSForm (Survey123/ArcGIS).")

# ---------------- Consentimiento ----------------
if section == "Consentimiento":
    title_block("Consentimiento informado", "Participación voluntaria para personas mayores de 18 años.")
    st.markdown(
        """
Usted está siendo invitado(a) a participar de forma libre y voluntaria en una encuesta sobre seguridad, convivencia y percepción ciudadana.

La información recopilada será utilizada exclusivamente para fines estadísticos, analíticos y preventivos, conforme a la Ley N.º 8968.
"""
    )
    consent = radio_required("¿Acepta participar en esta encuesta?", YESNO, "consent", horizontal=True)
    if consent == "No":
        st.error("La encuesta finaliza porque no aceptó participar.")
        st.stop()
    st.success("Gracias. Puede continuar.")
    divider()

# ---------------- I. Datos demográficos ----------------
if section == "I. Datos demográficos":
    title_block("I. Datos demográficos")

    text_input_optional("1. Cantón:", "q1_canton", placeholder="Ej. San José")
    text_input_optional("2. Distrito:", "q2_distrito", placeholder="Ej. Catedral")

    radio_required("3. Edad (en años cumplidos):", Q3_EDAD, "q3_edad_rango")
    radio_required("4. ¿Con cuál de estas opciones se identifica?", Q4_GENERO, "q4_genero")
    radio_required("5. Escolaridad:", Q5_ESCOLARIDAD, "q5_escolaridad")
    radio_required("6. ¿Cuál es su relación con la zona?", Q6_RELACION, "q6_relacion_zona", horizontal=True)

    divider()

# ---------------- II. Percepción ciudadana ----------------
if section == "II. Percepción ciudadana":
    title_block("II. Percepción ciudadana de seguridad en el distrito")

    q7 = radio_required(
        "7. ¿Qué tan seguro percibe usted el distrito donde reside o transita?",
        Q7_ESCALA,
        "q7_seguridad_distrito",
        horizontal=True,
    )

    if q7 in ("Muy inseguro", "Inseguro"):
        st.subheader("7.1. Indique por qué considera el distrito inseguro (selección múltiple)")
        sel_7_1 = st.multiselect(
            "Seleccione todo lo que corresponda:",
            Q7_1_OPTS,
            default=read_answer("q7_1", []),
            key="ui_q7_1",
        )
        save_answer("q7_1", sel_7_1)
        if Q7_1_OTRO_LABEL in sel_7_1:
            text_input_optional("7.1 Otro (especifique):", "q7_1_otro", placeholder="Escriba aquí...")

    divider()

    select_required(
        "8. En comparación con los 12 meses anteriores, ¿cómo percibe que ha cambiado la seguridad en este distrito?",
        Q8_CAMBIO,
        "q8_cambio_seguridad",
    )
    text_area_optional("8.1. Indique por qué (explique brevemente):", "q8_1_por_que", placeholder="Escriba aquí...")

    divider()

    st.subheader("9. Matriz: seguridad por tipo de espacio")
    grid = read_answer("q9_matriz", {})
    if not isinstance(grid, dict):
        grid = {}
    for z in Q9_ZONAS:
        default_val = grid.get(z, Q9_ESCALA[2])
        val = st.selectbox(
            z,
            Q9_ESCALA,
            index=Q9_ESCALA.index(default_val) if default_val in Q9_ESCALA else 2,
            key=f"ui_q9_{z}",
        )
        grid[z] = val
    save_answer("q9_matriz", grid)

    divider()

    q10 = radio_required(
        "10. Desde su percepción, ¿cuál considera que es el principal foco de inseguridad en el distrito?",
        Q10_OPTS,
        "q10_foco",
    )
    if q10 == Q10_OTRO:
        text_input_optional("10. Otros (especifique):", "q10_otro", placeholder="Escriba aquí...")

    text_area_optional(
        "11. Describa brevemente las razones por las cuales considera inseguro el espacio seleccionado:",
        "q11_razones",
        placeholder="Escriba aquí...",
    )
    divider()

# ---------------- III. Riesgos / delitos / victimización ----------------
if section == "III. Riesgos / delitos / victimización":
    title_block("III. Riesgos, delitos, victimización y evaluación policial")

    st.subheader("Riesgos sociales y situacionales")
    q12 = multiselect_exclusive(
        "12. Según su percepción u observación, seleccione las problemáticas que afectan su distrito:",
        Q12_OPTS,
        exclusive_option=Q12_EXCL,
        qid="q12_problematicas",
    )
    if Q12_OTRO_LABEL in q12:
        text_input_optional("12. Otro (especifique):", "q12_otro", placeholder="Escriba aquí...")

    divider()

    q13 = st.multiselect(
        "13. Carencias que identifica (Inversión social):",
        Q13_OPTS,
        default=read_answer("q13_carencias", []),
        key="ui_q13",
    )
    save_answer("q13_carencias", q13)
    if Q13_OTRO_LABEL in q13:
        text_input_optional("13. Otro (especifique):", "q13_otro", placeholder="Escriba aquí...")

    divider()

    multiselect_exclusive(
        "14. En los casos en que se observa consumo de drogas, indique dónde ocurre:",
        Q14_OPTS,
        Q14_EXCL,
        "q14_donde_consumo",
    )
    divider()

    q15 = st.multiselect(
        "15. Deficiencias de infraestructura vial:",
        Q15_OPTS,
        default=read_answer("q15_vial", []),
        key="ui_q15",
    )
    save_answer("q15_vial", q15)
    divider()

    q16 = multiselect_exclusive(
        "16. Espacios donde se identifica venta de drogas en el distrito:",
        Q16_OPTS,
        Q16_EXCL,
        "q16_venta_drogas_espacios",
    )
    if Q16_OTRO_LABEL in q16:
        text_input_optional("16. Otro tipo de espacio (especifique):", "q16_otro", placeholder="Escriba aquí...")
    divider()

    q17 = multiselect_exclusive(
        "17. Situaciones de inseguridad asociadas a transporte (según percepción/observación):",
        Q17_OPTS,
        Q17_EXCL,
        "q17_transporte_inseguridad",
    )
    if Q17_OTRO_LABEL in q17:
        text_input_optional("17. Otro (especifique):", "q17_otro", placeholder="Escriba aquí...")
    divider()

    st.subheader("Delitos")
    q18 = multiselect_exclusive(
        "18. Delitos que se presentan en el distrito (según conocimiento/observación):",
        Q18_OPTS,
        Q18_EXCL,
        "q18_delitos",
    )
    if Q18_OTRO_LABEL in q18:
        text_input_optional("18. Otro delito (especifique):", "q18_otro", placeholder="Escriba aquí...")
    divider()

    q19 = multiselect_exclusive(
        "19. ¿De qué forma se presenta la venta de drogas en el distrito?",
        Q19_OPTS,
        Q19_EXCL,
        "q19_forma_venta_drogas",
    )
    if Q19_OTRO_LABEL in q19:
        text_input_optional("19. Otro (especifique):", "q19_otro", placeholder="Escriba aquí...")
    divider()

    multiselect_exclusive("20. Delitos contra la vida:", Q20_OPTS, Q20_EXCL, "q20_vida")
    divider()

    multiselect_exclusive("21. Delitos sexuales:", Q21_OPTS, Q21_EXCL, "q21_sexuales")
    divider()

    multiselect_exclusive("22. Asaltos:", Q22_OPTS, Q22_EXCL, "q22_asaltos")
    divider()

    multiselect_exclusive("23. Estafas:", Q23_OPTS, Q23_EXCL, "q23_estafas")
    divider()

    multiselect_exclusive("24. Robo (con fuerza):", Q24_OPTS, Q24_EXCL, "q24_robos")
    divider()

    multiselect_exclusive("25. Abandono de personas:", Q25_OPTS, Q25_EXCL, "q25_abandono")
    divider()

    multiselect_exclusive("26. Explotación infantil:", Q26_OPTS, Q26_EXCL, "q26_explotacion_infantil")
    divider()

    multiselect_exclusive("27. Delitos ambientales:", Q27_OPTS, Q27_EXCL, "q27_ambientales")
    divider()

    multiselect_exclusive("28. Trata de personas:", Q28_OPTS, Q28_EXCL, "q28_trata")
    divider()

    st.subheader("Victimización - Apartado A: Violencia intrafamiliar")
    q29 = radio_required(
        "29. Durante los últimos 12 meses, ¿usted o algún miembro de su hogar ha sido afectado por violencia intrafamiliar?",
        YESNO,
        "q29_vif",
        horizontal=True,
    )
    if q29 == "Sí":
        q29_1 = st.multiselect(
            "29.1. ¿Qué tipo(s) de violencia se presentaron?",
            Q29_1_OPTS,
            default=read_answer("q29_1", []),
            key="ui_q29_1",
        )
        save_answer("q29_1", q29_1)

        radio_required("29.2. ¿Solicitó medidas de protección?", Q29_2_OPTS, "q29_2_medidas", horizontal=True)
        radio_required("29.3. ¿Cómo valora el abordaje de la Fuerza Pública ante esta situación?", Q29_3_OPTS, "q29_3_abordaje", horizontal=True)

    divider()

    st.subheader("Victimización - Apartado B: otros delitos")
    q30 = radio_required(
        "30. Durante los últimos 12 meses, ¿usted o algún miembro de su hogar fue afectado por algún delito?",
        Q30_OPTS,
        "q30_vict_delito",
        horizontal=True,
    )
    if q30 != "NO":
        q30_1 = st.multiselect(
            "30.1. Situación(es) (Selección múltiple):",
            Q30_1_OPTS,
            default=read_answer("q30_1", []),
            key="ui_q30_1",
        )
        save_answer("q30_1", q30_1)
        if Q30_1_OTRO_LABEL in q30_1:
            text_input_optional("30.1 Otro (especifique):", "q30_1_otro", placeholder="Escriba aquí...")

        if q30 == "Sí, pero no denuncié":
            q30_2 = st.multiselect(
                "30.2 Motivo(s) de no denunciar (selección múltiple):",
                Q30_2_OPTS,
                default=read_answer("q30_2", []),
                key="ui_q30_2",
            )
            save_answer("q30_2", q30_2)
            if Q30_2_OTRO_LABEL in q30_2:
                text_input_optional("30.2 Otro motivo (especifique):", "q30_2_otro", placeholder="Escriba aquí...")

        radio_required("30.3 Horario del hecho (rango):", Q30_3_OPTS, "q30_3_horario")

        q30_4 = st.multiselect(
            "30.4 Forma o modo en que ocurrió (selección múltiple):",
            Q30_4_OPTS,
            default=read_answer("q30_4", []),
            key="ui_q30_4",
        )
        save_answer("q30_4", q30_4)
        if Q30_4_OTRO_LABEL in q30_4:
            text_input_optional("30.4 Otro (especifique):", "q30_4_otro", placeholder="Escriba aquí...")

    divider()

# ---------------- Confianza policial ----------------
if section == "Confianza policial":
    title_block("Confianza policial")

    q31 = radio_required(
        "31. ¿Identifica usted a los policías de la Fuerza Pública de Costa Rica en su comunidad?",
        YESNO,
        "q31_identifica_policias",
        horizontal=True,
    )

    if q31 == "Sí":
        q31_1 = st.multiselect(
            "31.1 ¿Cuáles de los siguientes tipos de atención ha tenido? (Selección múltiple)",
            Q31_1_OPTS,
            default=read_answer("q31_1", []),
            key="ui_q31_1",
        )
        save_answer("q31_1", q31_1)
        if Q31_1_OTRO_LABEL in q31_1:
            text_input_optional("31.1 Otra (especifique):", "q31_1_otro", placeholder="Escriba aquí...")

        slider_int("32. Nivel de confianza en la policía (1=Ninguna, 10=Mucha):", 1, 10, "q32_confianza")

    slider_int("33. Profesionalidad de la Fuerza Pública en su distrito (1–10):", 1, 10, "q33_profesionalidad")
    slider_int("34. Calidad del servicio policial en su distrito (1–10):", 1, 10, "q34_calidad_servicio")
    slider_int("35. Satisfacción con el trabajo preventivo (1–10):", 1, 10, "q35_satisfaccion")
    slider_int("36. Contribución de la presencia policial para reducir crimen (1–10):", 1, 10, "q36_contribucion")

    radio_required("37. ¿Con qué frecuencia observa presencia policial en su distrito?", Q37_OPTS, "q37_frecuencia_presencia", horizontal=True)
    radio_required("38. ¿Considera que la presencia policial es consistente a lo largo del día en su distrito?", Q38_OPTS, "q38_consistencia", horizontal=True)
    radio_required("39. ¿Considera que la policía trata a las personas de manera justa e imparcial en su distrito?", Q39_OPTS, "q39_justicia", horizontal=True)
    radio_required("40. ¿Cree que puede expresar preocupaciones o quejas a la policía sin temor a represalias?", Q40_OPTS, "q40_quejas", horizontal=True)
    radio_required("41. ¿Considera que la policía proporciona información veraz, clara y oportuna a la comunidad?", Q41_OPTS, "q41_info", horizontal=True)

    divider()

# ---------------- Propuestas ----------------
if section == "Propuestas":
    title_block("Propuestas ciudadanas para la mejora de la seguridad")

    q42 = multiselect_exclusive(
        "42. ¿Qué actividad considera que deba realizar la Fuerza Pública para mejorar la seguridad en su comunidad?",
        Q42_OPTS,
        exclusive_option=Q42_EXCL,
        qid="q42_fp_acciones",
    )
    if Q42_OTRO_LABEL in q42:
        text_input_optional("42. Otro (especifique):", "q42_otro", placeholder="Escriba aquí...")

    divider()

    q43 = multiselect_exclusive(
        "43. ¿Qué actividad considera que deba realizar la municipalidad para mejorar la seguridad en su comunidad?",
        Q43_OPTS,
        exclusive_option=Q43_EXCL,
        qid="q43_muni_acciones",
    )
    if Q43_OTRO_LABEL in q43:
        text_input_optional("43. Otro (especifique):", "q43_otro", placeholder="Escriba aquí...")

    divider()

# ---------------- Información adicional ----------------
if section == "Información adicional":
    title_block("Información adicional y contacto voluntario")

    q44 = radio_required(
        "44. ¿Usted tiene información de alguna persona o grupo que se dedique a realizar algún delito en su comunidad?",
        YESNO,
        "q44_info_delito",
        horizontal=True,
    )
    if q44 == "Sí":
        text_area_optional(
            "44.1. Describa características (nombre de estructura/banda, alias, domicilio, vehículos, etc.):",
            "q44_1_detalle",
            placeholder="Escriba aquí...",
        )

    divider()

    text_area_optional(
        "45. (Voluntario) Anote su nombre, teléfono o correo para ser contactado confidencialmente:",
        "q45_contacto",
        placeholder="Escriba aquí...",
    )
    text_area_optional(
        "46. Registre cualquier otra información que estime pertinente:",
        "q46_extra",
        placeholder="Escriba aquí...",
    )

    st.success("Fin de la encuesta.")
    divider()

# ---------------- Resumen y exportación ----------------
if section == "Resumen y exportación":
    title_block("Resumen y exportación")

    ss_init_answers()
    st.markdown("### Respuestas registradas")
    st.json(st.session_state["answers"])

    payload = {
        "metadata": {
            "instrumento": "Encuesta de Percepción Comunidad 2026",
            "version": "V.4.1 (cambios generales)",
            "exported_at": datetime.now().isoformat(timespec="seconds"),
        },
        "respuestas": dict(st.session_state["answers"]),
    }
    st.download_button(
        label="⬇️ Descargar respuestas (JSON)",
        data=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="respuestas_encuesta_comunidad_2026.json",
        mime="application/json",
    )

    divider()

    st.markdown("### Generar XLSForm (Excel para Survey123 / ArcGIS)")
    include_geo = st.checkbox("Incluir ubicación (geopoint) recomendado", value=True)

    xls_bytes = build_xlsform_bytes(include_geopoint=include_geo)
    st.download_button(
        "⬇️ Descargar XLSForm (Excel)",
        data=xls_bytes,
        file_name="Encuesta_Comunidad_2026_XLSForm.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    divider()
    st.markdown("### Condicionales implementados en la app")
    st.write(
        "- **7.1** aparece si en **7** selecciona *Muy inseguro* o *Inseguro*.\n"
        "- **29.1–29.3** aparece si en **29** selecciona *Sí*.\n"
        "- **30.1–30.4** aparece si en **30** selecciona distinto de *NO*.\n"
        "- **30.2** aparece solo si en **30** selecciona *Sí, pero no denuncié*.\n"
        "- **31.1 y 32** aparece si en **31** selecciona *Sí*.\n"
        "- **44.1** aparece si en **44** selecciona *Sí*."
    )



