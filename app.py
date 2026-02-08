# app.py
# ======================================================================================
# App Streamlit: Encuesta Comunidad 2026 (V.4.1) - Visualización con condicionales
# Fuente: "Formato de encuesta Comunidad 2026 V.4.1 cambios generales.docx"
#
# - Incluye todas las preguntas 1–46 con opciones y saltos condicionales descritos.
# - Incluye un resumen final + exportación a JSON.
# - Cantón/Distrito: por defecto se dejan como texto (puede cambiarse a listas reales).
# ======================================================================================

import json
from datetime import datetime
import streamlit as st

st.set_page_config(page_title="Encuesta Comunidad 2026", layout="wide")

# ----------------------------- Helpers -----------------------------

def ss_get(key, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

def ss_set(key, value):
    st.session_state[key] = value

def title_block(title, subtitle=None):
    st.markdown(f"## {title}")
    if subtitle:
        st.info(subtitle)

def divider():
    st.markdown("---")

def export_payload():
    payload = {
        "metadata": {
            "instrumento": "Encuesta de Percepción Comunidad 2026",
            "version": "V.4.1 (cambios generales)",
            "exported_at": datetime.now().isoformat(timespec="seconds"),
        },
        "respuestas": dict(st.session_state.get("answers", {})),
    }
    return payload

def ensure_answers_dict():
    if "answers" not in st.session_state:
        st.session_state["answers"] = {}

def save_answer(qid, value):
    ensure_answers_dict()
    st.session_state["answers"][qid] = value

def read_answer(qid, default=None):
    ensure_answers_dict()
    return st.session_state["answers"].get(qid, default)

def multiselect_exclusive(label, options, exclusive_option, qid, help_text=None):
    """
    Multiselect que evita combinar el valor 'exclusive_option' con otras opciones.
    """
    current = read_answer(qid, [])
    if not isinstance(current, list):
        current = []

    sel = st.multiselect(label, options, default=current, help=help_text, key=f"ui_{qid}")

    # Normalización exclusividad
    if exclusive_option in sel and len(sel) > 1:
        # si selecciona "No se observa..." se queda solo con esa
        sel = [exclusive_option]
        st.warning(f'La opción "{exclusive_option}" no puede combinarse con otras.')
        # fuerza UI
        ss_set(f"ui_{qid}", sel)

    save_answer(qid, sel)
    return sel

def radio_required(label, options, qid, help_text=None, horizontal=False):
    current = read_answer(qid, None)
    if current not in options:
        current = None

    sel = st.radio(label, options, index=options.index(current) if current in options else 0,
                   help=help_text, horizontal=horizontal, key=f"ui_{qid}")
    save_answer(qid, sel)
    return sel

def select_required(label, options, qid, help_text=None):
    current = read_answer(qid, options[0] if options else None)
    if current not in options and options:
        current = options[0]
    sel = st.selectbox(label, options, index=options.index(current) if current in options else 0,
                       help=help_text, key=f"ui_{qid}")
    save_answer(qid, sel)
    return sel

def text_area_optional(label, qid, help_text=None, placeholder=""):
    current = read_answer(qid, "")
    val = st.text_area(label, value=current, help=help_text, placeholder=placeholder, key=f"ui_{qid}")
    save_answer(qid, val)
    return val

def text_input_optional(label, qid, help_text=None, placeholder=""):
    current = read_answer(qid, "")
    val = st.text_input(label, value=current, help=help_text, placeholder=placeholder, key=f"ui_{qid}")
    save_answer(qid, val)
    return val

def slider_int(label, min_v, max_v, qid, help_text=None):
    current = read_answer(qid, None)
    if not isinstance(current, int):
        current = min_v
    val = st.slider(label, min_value=min_v, max_value=max_v, value=current, help=help_text, key=f"ui_{qid}")
    save_answer(qid, val)
    return val

# ----------------------------- Sidebar -----------------------------

st.sidebar.title("Encuesta Comunidad 2026")
st.sidebar.caption("Visualización + lógica condicional")

if st.sidebar.button("🧹 Reiniciar respuestas"):
    st.session_state["answers"] = {}
    # también limpiar controles UI
    for k in list(st.session_state.keys()):
        if k.startswith("ui_"):
            del st.session_state[k]
    st.rerun()

st.sidebar.markdown("### Navegación")
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

# ----------------------------- Main -----------------------------

st.title("📋 Encuesta de Percepción Comunidad 2026 (V.4.1)")
st.caption("App de revisión: preguntas + opciones + condicionales (según el formato).")

# ============================= Consentimiento =============================

if section == "Consentimiento":
    title_block("Consentimiento informado", "Participación voluntaria para personas mayores de 18 años.")
    st.markdown(
        """
Usted está siendo invitado(a) a participar de forma libre y voluntaria en una encuesta sobre seguridad, convivencia y percepción ciudadana.

La información recopilada será utilizada exclusivamente para fines estadísticos, analíticos y preventivos, conforme a la Ley N.º 8968.
"""
    )
    consent = radio_required("¿Acepta participar en esta encuesta?", ["Sí", "No"], "consent")
    if consent == "No":
        st.error("La encuesta finaliza porque no aceptó participar.")
        st.stop()

    st.success("Gracias. Puede continuar con la encuesta.")
    divider()

# ============================= I. Datos demográficos =============================

if section == "I. Datos demográficos":
    title_block("I. Datos demográficos")

    # 1 Cantón
    text_input_optional("1. Cantón (desplegable en el instrumento):", "q1_canton", placeholder="Ej. San José")
    # 2 Distrito
    text_input_optional("2. Distrito (desplegable en el instrumento):", "q2_distrito", placeholder="Ej. Catedral")

    # 3 Edad rango
    q3 = radio_required(
        "3. Edad (en años cumplidos):",
        ["18 a 29 años", "30 a 44 años", "45 a 64 años", "65 años o más"],
        "q3_edad_rango",
        horizontal=False,
    )

    # 4 Género / identidad
    q4 = radio_required(
        "4. ¿Con cuál de estas opciones se identifica?",
        ["Femenino", "Masculino", "Persona no Binaria", "Prefiero no decir"],
        "q4_genero",
    )

    # 5 Escolaridad
    q5 = radio_required(
        "5. Escolaridad:",
        [
            "Ninguna",
            "Primaria incompleta",
            "Primaria completa",
            "Secundaria incompleta",
            "Secundaria completa",
            "Técnico",
            "Universitaria incompleta",
            "Universitaria completa",
        ],
        "q5_escolaridad",
    )

    # 6 Relación con la zona (dice selección única)
    q6 = radio_required(
        "6. ¿Cuál es su relación con la zona?",
        ["Vivo en la zona", "Trabajo en la zona", "Visito la zona", "Estudio en la zona"],
        "q6_relacion_zona",
        horizontal=True,
    )
    divider()

# ============================= II. Percepción ciudadana =============================

if section == "II. Percepción ciudadana":
    title_block("II. Percepción ciudadana de seguridad en el distrito")

    # 7 percepción seguridad
    q7 = radio_required(
        "7. ¿Qué tan seguro percibe usted el distrito donde reside o transita?",
        ["Muy inseguro", "Inseguro", "Ni seguro ni inseguro", "Seguro", "Muy seguro"],
        "q7_seguridad_distrito",
        horizontal=True,
    )

    # 7.1 condicional si Muy inseguro o Inseguro
    if q7 in ("Muy inseguro", "Inseguro"):
        st.subheader("7.1. Indique por qué considera el distrito inseguro (selección múltiple)")
        opts_7_1 = [
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
        sel_7_1 = st.multiselect("Seleccione todo lo que corresponda:", opts_7_1, default=read_answer("q7_1", []), key="ui_q7_1")
        save_answer("q7_1", sel_7_1)
        if "Otro problema que considere importante (especifique abajo)" in sel_7_1:
            text_input_optional("Otro (especifique):", "q7_1_otro", placeholder="Escriba aquí...")

    divider()

    # 8 escala 1 a 5
    st.subheader("8. Cambio percibido de la seguridad (últimos 12 meses)")
    q8 = select_required(
        "8. En comparación con los 12 meses anteriores, ¿cómo percibe que ha cambiado la seguridad en este distrito?",
        ["1 (Mucho menos seguro)", "2 (Menos seguro)", "3 (Se mantiene igual)", "4 (Más seguro)", "5 (Mucho más seguro)"],
        "q8_cambio_seguridad",
    )

    # 8.1 siempre pasa a 8.1
    text_area_optional("8.1. Indique por qué (explique brevemente):", "q8_1_por_que", placeholder="Escriba aquí...")

    divider()

    # 9 matriz por fila (1 a 5 + No aplica)
    st.subheader("9. Matriz: seguridad por tipo de espacio")
    zonas = [
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
    escala_9 = ["1 (Muy inseguro)", "2 (Inseguro)", "3 (Ni seguro ni inseguro)", "4 (Seguro)", "5 (Muy seguro)", "No aplica"]

    grid = read_answer("q9_matriz", {})
    if not isinstance(grid, dict):
        grid = {}

    cols = st.columns(2)
    with cols[0]:
        st.caption("Seleccione una opción por cada espacio.")
    with cols[1]:
        st.caption("")

    for z in zonas:
        default_val = grid.get(z, escala_9[2])
        val = st.selectbox(z, escala_9, index=escala_9.index(default_val) if default_val in escala_9 else 2, key=f"ui_q9_{z}")
        grid[z] = val

    save_answer("q9_matriz", grid)

    divider()

    # 10 foco principal
    st.subheader("10. Principal foco de inseguridad (selección única)")
    q10_opts = [
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
    q10 = radio_required("10. Desde su percepción, ¿cuál considera que es el principal foco de inseguridad en el distrito?", q10_opts, "q10_foco")
    if q10 == "Otros (especifique abajo)":
        text_input_optional("10. Otros (especifique):", "q10_otro", placeholder="Escriba aquí...")

    # 11 razones
    text_area_optional("11. Describa brevemente las razones por las cuales considera inseguro el espacio seleccionado:", "q11_razones", placeholder="Escriba aquí...")
    divider()

# ============================= III. Riesgos / Delitos / Victimización =============================

if section == "III. Riesgos / delitos / victimización":
    title_block("III. Riesgos, delitos, victimización y evaluación policial")

    st.subheader("Riesgos sociales y situacionales")
    # 12 problemáticas múltiples con opción exclusiva "No se observan..."
    q12_opts = [
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
    q12 = multiselect_exclusive(
        "12. Según su percepción u observación, seleccione las problemáticas que afectan su distrito:",
        q12_opts,
        exclusive_option="No se observan estas problemáticas en el distrito",
        qid="q12_problematicas",
    )
    if "Otro problema que considere importante (especifique abajo)" in q12:
        text_input_optional("12. Otro (especifique):", "q12_otro", placeholder="Escriba aquí...")

    divider()

    # 13 carencias (inversión social)
    q13_opts = [
        "Falta de oferta educativa",
        "Falta de oferta deportiva",
        "Falta de oferta recreativa",
        "Falta de actividades culturales",
        "Otro problema que considere importante (especifique abajo)",
    ]
    q13 = st.multiselect("13. Carencias que identifica (Inversión social):", q13_opts, default=read_answer("q13_carencias", []), key="ui_q13")
    save_answer("q13_carencias", q13)
    if "Otro problema que considere importante (especifique abajo)" in q13:
        text_input_optional("13. Otro (especifique):", "q13_otro", placeholder="Escriba aquí...")

    divider()

    # 14 dónde ocurre consumo drogas (múltiple con "No se observa...")
    q14_opts = [
        "Áreas públicas (calles, parques, paradas, espacios abiertos)",
        "Áreas privadas (viviendas, locales, espacios cerrados)",
        "No se observa consumo de drogas",
    ]
    q14 = multiselect_exclusive(
        "14. En los casos en que se observa consumo de drogas, indique dónde ocurre:",
        q14_opts,
        exclusive_option="No se observa consumo de drogas",
        qid="q14_donde_consumo",
    )

    divider()

    # 15 deficiencias vial
    q15_opts = ["Calles en mal estado", "Falta de señalización de tránsito", "Carencia o inexistencia de aceras"]
    q15 = st.multiselect("15. Deficiencias de infraestructura vial:", q15_opts, default=read_answer("q15_vial", []), key="ui_q15")
    save_answer("q15_vial", q15)

    divider()

    # 16 puntos de venta drogas (múltiple con "No se observa")
    q16_opts = [
        "Casa de habitación (espacio cerrado)",
        "Edificación abandonada",
        "Lote baldío",
        "Otro tipo de espacio (especifique abajo)",
        "No se observa",
    ]
    q16 = multiselect_exclusive(
        "16. Espacios donde se identifica venta de drogas en el distrito:",
        q16_opts,
        exclusive_option="No se observa",
        qid="q16_venta_drogas_espacios",
    )
    if "Otro tipo de espacio (especifique abajo)" in q16:
        text_input_optional("16. Otro tipo de espacio (especifique):", "q16_otro", placeholder="Escriba aquí...")

    divider()

    # 17 transporte (múltiple con "No se observa")
    q17_opts = [
        "Transporte informal o no autorizado (taxis piratas)",
        "Plataformas de transporte digital",
        "Transporte público (buses)",
        "Servicios de reparto o mensajería “exprés” (por ejemplo, repartidores en motocicleta o bicimoto)",
        "Otro tipo de situación relacionada con el transporte (especifique abajo)",
        "No se observa",
    ]
    q17 = multiselect_exclusive(
        "17. Situaciones de inseguridad asociadas a transporte (según percepción/observación):",
        q17_opts,
        exclusive_option="No se observa",
        qid="q17_transporte_inseguridad",
    )
    if "Otro tipo de situación relacionada con el transporte (especifique abajo)" in q17:
        text_input_optional("17. Otro (especifique):", "q17_otro", placeholder="Escriba aquí...")

    divider()

    st.subheader("Delitos")
    # 18 delitos múltiples con No se observan delitos
    q18_opts = [
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
    q18 = multiselect_exclusive(
        "18. Delitos que se presentan en el distrito (según conocimiento/observación):",
        q18_opts,
        exclusive_option="No se observan delitos",
        qid="q18_delitos",
    )
    if "Otro delito (especifique abajo)" in q18:
        text_input_optional("18. Otro delito (especifique):", "q18_otro", placeholder="Escriba aquí...")

    divider()

    # 19 forma venta de drogas (múltiple con No se observa)
    q19_opts = [
        "En espacios cerrados (casas, edificaciones u otros inmuebles)",
        "En vía pública",
        "De forma ocasional o móvil (sin punto fijo)",
        "No se observa venta de drogas",
        "Otro (especifique abajo)",
    ]
    q19 = multiselect_exclusive(
        "19. ¿De qué forma se presenta la venta de drogas en el distrito?",
        q19_opts,
        exclusive_option="No se observa venta de drogas",
        qid="q19_forma_venta_drogas",
    )
    if "Otro (especifique abajo)" in q19:
        text_input_optional("19. Otro (especifique):", "q19_otro", placeholder="Escriba aquí...")

    divider()

    # 20 delitos contra la vida
    q20_opts = [
        "Homicidios (muerte intencional de una persona)",
        "Personas heridas de forma intencional (heridos)",
        "Femicidio (homicidio de una mujer por razones de género)",
        "No se observan delitos contra la vida",
    ]
    q20 = multiselect_exclusive(
        "20. Delitos contra la vida (según observación/conocimiento):",
        q20_opts,
        exclusive_option="No se observan delitos contra la vida",
        qid="q20_vida",
    )

    divider()

    # 21 delitos sexuales
    q21_opts = [
        "Abuso sexual (tocamientos u otros actos sexuales sin consentimiento)",
        "Violación (acceso sexual sin consentimiento)",
        "Acoso sexual (insinuaciones, solicitudes o conductas sexuales no deseadas)",
        "Acoso callejero (comentarios, gestos o conductas sexuales en espacios públicos)",
        "No se observan delitos sexuales",
    ]
    q21 = multiselect_exclusive(
        "21. Delitos sexuales (según observación/conocimiento):",
        q21_opts,
        exclusive_option="No se observan delitos sexuales",
        qid="q21_sexuales",
    )

    divider()

    # 22 asaltos
    q22_opts = [
        "Asalto a personas",
        "Asalto a comercio",
        "Asalto a vivienda",
        "Asalto a transporte público",
        "No se observan asaltos",
    ]
    q22 = multiselect_exclusive(
        "22. Asaltos (según observación/conocimiento):",
        q22_opts,
        exclusive_option="No se observan asaltos",
        qid="q22_asaltos",
    )

    divider()

    # 23 estafas
    q23_opts = [
        "Billetes falsos",
        "Documentos falsos",
        "Estafas relacionadas con la compra o venta de oro",
        "Lotería falsa",
        "Estafas informáticas (por internet, redes sociales o correos electrónicos)",
        "Estafas telefónicas",
        "Estafas con tarjetas (clonación, cargos no autorizados)",
        "No se observan estafas",
    ]
    q23 = multiselect_exclusive(
        "23. Estafas (según observación/conocimiento):",
        q23_opts,
        exclusive_option="No se observan estafas",
        qid="q23_estafas",
    )

    divider()

    # 24 robo (con fuerza)
    q24_opts = [
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
    q24 = multiselect_exclusive(
        "24. Robo (con fuerza) (según observación/conocimiento):",
        q24_opts,
        exclusive_option="No se observan robos",
        qid="q24_robos",
    )

    divider()

    # 25 abandono de personas
    q25_opts = [
        "Abandono de adulto mayor",
        "Abandono de menor de edad",
        "Abandono de incapaz",
        "No se observan situaciones de abandono",
    ]
    q25 = multiselect_exclusive(
        "25. Abandono de personas (según observación/conocimiento):",
        q25_opts,
        exclusive_option="No se observan situaciones de abandono",
        qid="q25_abandono",
    )

    divider()

    # 26 explotación infantil
    q26_opts = ["Sexual", "Laboral", "No se observan"]
    q26 = multiselect_exclusive(
        "26. Explotación infantil (según observación/conocimiento):",
        q26_opts,
        exclusive_option="No se observan",
        qid="q26_explotacion_infantil",
    )

    divider()

    # 27 delitos ambientales
    q27_opts = [
        "Caza ilegal",
        "Pesca ilegal",
        "Tala ilegal",
        "Extracción ilegal de material minero",
        "No se observan delitos ambientales",
    ]
    q27 = multiselect_exclusive(
        "27. Delitos ambientales (según observación/conocimiento):",
        q27_opts,
        exclusive_option="No se observan delitos ambientales",
        qid="q27_ambientales",
    )

    divider()

    # 28 trata de personas
    q28_opts = ["Con fines laborales", "Con fines sexuales", "No se observan situaciones de trata de personas"]
    q28 = multiselect_exclusive(
        "28. Trata de personas (según observación/conocimiento):",
        q28_opts,
        exclusive_option="No se observan situaciones de trata de personas",
        qid="q28_trata",
    )

    divider()

    st.subheader("Victimización - Apartado A: Violencia intrafamiliar")
    # 29 Sí/No => habilita 29.1-29.3
    q29 = radio_required(
        "29. Durante los últimos 12 meses, ¿usted o algún miembro de su hogar ha sido afectado por violencia intrafamiliar?",
        ["Sí", "No"],
        "q29_vif",
        horizontal=True,
    )
    if q29 == "Sí":
        # 29.1
        q29_1_opts = [
            "Violencia psicológica (gritos, amenazas, humillaciones, maltratos, entre otros)",
            "Violencia física (agresiones físicas, empujones, golpes, entre otros)",
            "Violencia vicaria (uso de hijas, hijos u otras personas para causar daño emocional)",
            "Violencia patrimonial (destrucción, retención o control de bienes, documentos o dinero)",
            "Violencia sexual (actos de carácter sexual sin consentimiento)",
        ]
        st.multiselect("29.1. ¿Qué tipo(s) de violencia se presentaron?", q29_1_opts, default=read_answer("q29_1", []), key="ui_q29_1")
        save_answer("q29_1", st.session_state["ui_q29_1"])

        # 29.2
        radio_required(
            "29.2. ¿Solicitó medidas de protección?",
            ["Sí", "No", "No recuerda"],
            "q29_2_medidas",
            horizontal=True,
        )

        # 29.3
        radio_required(
            "29.3. ¿Cómo valora el abordaje de la Fuerza Pública ante esta situación?",
            ["Excelente", "Bueno", "Regular", "Malo", "Muy malo"],
            "q29_3_abordaje",
            horizontal=True,
        )

    divider()

    st.subheader("Victimización - Apartado B: otros delitos")
    # 30 lógica 3 opciones
    q30 = radio_required(
        "30. Durante los últimos 12 meses, ¿usted o algún miembro de su hogar fue afectado por algún delito?",
        ["NO", "Sí, y denuncié", "Sí, pero no denuncié"],
        "q30_vict_delito",
        horizontal=True,
    )

    if q30 != "NO":
        # 30.1 selección múltiple
        st.markdown("**30.1. ¿Cuál de las siguientes situaciones afectó a usted o a algún miembro de su hogar? (Selección múltiple)**")
        q30_1_opts = [
            # A
            "Asalto a mano armada en la calle o espacio público",
            "Asalto en el transporte público",
            "Asalto o robo de su vehículo (coche, motocicleta, etc.)",
            "Robo de accesorios o partes de su vehículo (espejos, llantas, radio)",
            "Robo o intento de robo con fuerza a su vivienda (forzar puerta/ventana)",
            "Robo o intento de robo con fuerza a su comercio o negocio",
            # B
            "Hurto de su cartera, bolso o celular (sin darse cuenta)",
            "Daños a su propiedad (grafitis, rotura de cristales, cercas, etc.)",
            "Receptación (alguien en su hogar compró/recibió un artículo y luego supo que era robado)",
            "Pérdida de artículos por descuido (celular, bicicleta, etc.)",
            # C
            "Estafa telefónica",
            "Estafa o fraude informático (internet/redes/correo)",
            "Fraude con tarjetas bancarias (clonación/uso no autorizado)",
            "Ser víctima de billetes o documentos falsos",
            # D
            "Extorsión (intimidación o amenaza para obtener dinero u otro beneficio)",
            "Maltrato animal",
            "Acoso o intimidación sexual en un espacio público",
            "Algún tipo de delito sexual (abuso, violación)",
            "Lesiones personales (herido en riña o agresión)",
            "Otro (especifique abajo)",
        ]
        q30_1 = st.multiselect("Seleccione todo lo que corresponda:", q30_1_opts, default=read_answer("q30_1", []), key="ui_q30_1")
        save_answer("q30_1", q30_1)
        if "Otro (especifique abajo)" in q30_1:
            text_input_optional("30.1 Otro (especifique):", "q30_1_otro", placeholder="Escriba aquí...")

        # 30.2 solo si NO denunció
        if q30 == "Sí, pero no denuncié":
            q30_2_opts = [
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
            q30_2 = st.multiselect("30.2 Motivo(s) de no denunciar (selección múltiple):", q30_2_opts, default=read_answer("q30_2", []), key="ui_q30_2")
            save_answer("q30_2", q30_2)
            if "Otro motivo (especifique abajo)" in q30_2:
                text_input_optional("30.2 Otro motivo (especifique):", "q30_2_otro", placeholder="Escriba aquí...")

        # 30.3 horario
        q30_3_opts = [
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
        radio_required("30.3 Horario del hecho (rango):", q30_3_opts, "q30_3_horario")

        # 30.4 modo/forma (múltiple)
        q30_4_opts = [
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
        q30_4 = st.multiselect("30.4 Forma o modo en que ocurrió (selección múltiple):", q30_4_opts, default=read_answer("q30_4", []), key="ui_q30_4")
        save_answer("q30_4", q30_4)
        if "Otro (especifique abajo)" in q30_4:
            text_input_optional("30.4 Otro (especifique):", "q30_4_otro", placeholder="Escriba aquí...")

    divider()

# ============================= Confianza policial =============================

if section == "Confianza policial":
    title_block("Confianza policial")

    q31 = radio_required(
        "31. ¿Identifica usted a los policías de la Fuerza Pública de Costa Rica en su comunidad?",
        ["Sí", "No"],
        "q31_identifica_policias",
        horizontal=True,
    )

    if q31 == "Sí":
        q31_1_opts = [
            "Solicitud de ayuda o auxilio",
            "Atención relacionada con una denuncia",
            "Atención cordial o preventiva durante un patrullaje",
            "Fui abordado o registrado para identificación",
            "Fui objeto de una infracción o conflicto",
            "Evento preventivo (cívico policial, reunión comunitaria)",
            "Otra (especifique abajo)",
        ]
        q31_1 = st.multiselect("31.1 ¿Cuáles de los siguientes tipos de atención ha tenido? (Selección múltiple)", q31_1_opts, default=read_answer("q31_1", []), key="ui_q31_1")
        save_answer("q31_1", q31_1)
        if "Otra (especifique abajo)" in q31_1:
            text_input_optional("31.1 Otra (especifique):", "q31_1_otro", placeholder="Escriba aquí...")

        # 32 escala 1-10
        slider_int("32. Nivel de confianza en la policía (1=Ninguna, 10=Mucha):", 1, 10, "q32_confianza")

    # Si NO, según nota pasa a 33 (igual mostramos 33 siempre)
    slider_int("33. Profesionalidad de la Fuerza Pública en su distrito (1–10):", 1, 10, "q33_profesionalidad")
    slider_int("34. Calidad del servicio policial en su distrito (1–10):", 1, 10, "q34_calidad_servicio")
    slider_int("35. Satisfacción con el trabajo preventivo (1–10):", 1, 10, "q35_satisfaccion")
    slider_int("36. Contribución de la presencia policial para reducir crimen (1–10):", 1, 10, "q36_contribucion")

    q37 = radio_required(
        "37. ¿Con qué frecuencia observa presencia policial en su distrito?",
        ["Todos los días", "Varias veces por semana", "Una vez por semana", "Casi nunca", "Nunca"],
        "q37_frecuencia_presencia",
        horizontal=True,
    )

    q38 = radio_required(
        "38. ¿Considera que la presencia policial es consistente a lo largo del día en su distrito?",
        ["Sí", "No", "A veces"],
        "q38_consistencia",
        horizontal=True,
    )

    q39 = radio_required(
        "39. ¿Considera que la policía trata a las personas de manera justa e imparcial en su distrito?",
        ["Sí", "No", "A veces"],
        "q39_justicia",
        horizontal=True,
    )

    q40 = radio_required(
        "40. ¿Cree que puede expresar preocupaciones o quejas a la policía sin temor a represalias?",
        ["Sí", "No", "No estoy seguro(a)"],
        "q40_quejas",
        horizontal=True,
    )

    q41 = radio_required(
        "41. ¿Considera que la policía proporciona información veraz, clara y oportuna a la comunidad?",
        ["Sí", "No", "A veces"],
        "q41_info",
        horizontal=True,
    )

    divider()

# ============================= Propuestas =============================

if section == "Propuestas":
    title_block("Propuestas ciudadanas para la mejora de la seguridad")

    # 42 (nota dice selección múltiple + otro + "no opinión")
    q42_opts = [
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
    q42 = multiselect_exclusive(
        "42. ¿Qué actividad considera que deba realizar la Fuerza Pública para mejorar la seguridad en su comunidad?",
        q42_opts,
        exclusive_option="No tiene una opinión al respecto",
        qid="q42_fp_acciones",
    )
    if "Otro (especifique abajo)" in q42:
        text_input_optional("42. Otro (especifique):", "q42_otro", placeholder="Escriba aquí...")

    divider()

    q43_opts = [
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
    q43 = multiselect_exclusive(
        "43. ¿Qué actividad considera que deba realizar la municipalidad para mejorar la seguridad en su comunidad?",
        q43_opts,
        exclusive_option="No tiene una opinión al respecto",
        qid="q43_muni_acciones",
    )
    if "Otro (especifique abajo)" in q43:
        text_input_optional("43. Otro (especifique):", "q43_otro", placeholder="Escriba aquí...")

    divider()

# ============================= Información adicional =============================

if section == "Información adicional":
    title_block("Información adicional y contacto voluntario")

    q44 = radio_required(
        "44. ¿Usted tiene información de alguna persona o grupo que se dedique a realizar algún delito en su comunidad?",
        ["Sí", "No"],
        "q44_info_delito",
        horizontal=True,
    )

    if q44 == "Sí":
        text_area_optional(
            "44.1. Si su respuesta es 'Sí', describa características (nombre de estructura/banda, alias, domicilio, vehículos, etc.):",
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

    st.success("Fin de la encuesta (según el formato).")
    divider()

# ============================= Resumen y exportación =============================

if section == "Resumen y exportación":
    title_block("Resumen y exportación")

    ensure_answers_dict()
    answers = st.session_state["answers"]

    # resumen bonito
    st.markdown("### Respuestas registradas")
    st.caption("Esto sirve para validar saltos/condicionales y revisar consistencia.")
    st.json(answers)

    payload = export_payload()
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)

    st.download_button(
        label="⬇️ Descargar respuestas (JSON)",
        data=json_str.encode("utf-8"),
        file_name="respuestas_encuesta_comunidad_2026.json",
        mime="application/json",
    )

    divider()
    st.markdown("### Nota rápida sobre condicionales implementados")
    st.write(
        "- **7.1** aparece si en **7** selecciona *Muy inseguro* o *Inseguro*.\n"
        "- **29.1–29.3** aparecen si en **29** selecciona *Sí*.\n"
        "- **30.1–30.4** aparecen si en **30** selecciona alguna opción distinta de *NO*.\n"
        "- **30.2** aparece solo si en **30** selecciona *Sí, pero no denuncié*.\n"
        "- **31.1 y 32** aparecen si en **31** selecciona *Sí*.\n"
        "- **44.1** aparece si en **44** selecciona *Sí*."
    )












