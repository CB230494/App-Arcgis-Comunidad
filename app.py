# -*- coding: utf-8 -*-
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 1/10) ==============================
# ===== App: Encuesta Comunidad → Editor fácil + XLSForm Survey123 (P1 a P8) + Cascada =====
# ==========================================================================================
#
# PARTE 1/10:
# - Imports
# - Configuración UI base
# - Constantes de páginas (p1..p8)
# - Helpers base (slugify, nombres únicos, export excel)
# - Helpers NUEVOS:
#     * page_id_from_row(): detecta página por nombre interno (fallback)
#     * ensure_question_page_id(): asegura page_id explícito por pregunta
#     * sync_glossary_order_text(): sincroniza multiselect -> text_area (soluciona tu bug)
#
# NOTA:
# - En Partes posteriores, el editor de preguntas debe usar `page_id` (no el nombre del group).
# - Y el editor de glosario por página debe usar `sync_glossary_order_text()`.
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
st.set_page_config(page_title="Encuesta Comunidad — XLSForm (Editable P1 a P8)", layout="wide")
st.title("🏘️ Encuesta Comunidad → Editor fácil + XLSForm para ArcGIS Survey123 (P1 a P8)")

st.markdown("""
Esta app genera un **XLSForm** listo para **ArcGIS Survey123** con `settings.style = "pages"` y permite:
- **Ver** las preguntas como se ven en Survey123 (vista legible)
- **Editar** texto, orden, reglas (relevant/constraint), dependencias
- **Agregar / mover / eliminar** preguntas
- **Editar choices** (listas y opciones)
- **Editar glosario** (término → significado) y **asignarlo por página**
- **Editar catálogo Cantón→Distrito** con cascada (`choice_filter`)
""")

# ==========================================================================================
# Constantes: páginas (IDs y etiquetas)
# ==========================================================================================
pages = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]

pages_labels = {
    "p1": "P1 Introducción",
    "p2": "P2 Consentimiento",
    "p3": "P3 Datos demográficos",
    "p4": "P4 Percepción",
    "p5": "P5 Riesgos",
    "p6": "P6 Delitos",
    "p7": "P7 Victimización",
    "p8": "P8 Confianza y cierre",
}

# ==========================================================================================
# Helpers base
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

# ==========================================================================================
# Helpers NUEVOS: página por fila + asegurar page_id por pregunta
# ==========================================================================================
def page_id_from_row(row: dict) -> str:
    """
    Dado un row de survey (dict), intenta inferir a qué página pertenece.
    Fallback por prefijo del name (p1_, p2_, ..., p8_).
    """
    nm = str((row or {}).get("name", "")).strip().lower()

    # Caso típico: name empieza por "p5_" o "p5end" etc.
    m = re.match(r"^(p[1-8])[_\-]", nm)
    if m:
        pid = m.group(1)
        if pid in pages:
            return pid

    # Otros casos: begin_group name = p5_riesgos, p5_delitos, etc.
    m2 = re.match(r"^(p[1-8])", nm)
    if m2:
        pid = m2.group(1)
        if pid in pages:
            return pid

    # Si no se puede inferir, devolver vacío (luego se asigna por defecto)
    return ""

def ensure_question_page_id(q: dict) -> dict:
    """
    Asegura que cada pregunta del questions_bank tenga `page_id`.
    - Si ya existe: lo respeta.
    - Si no existe: intenta inferirlo desde row.name.
    - Si no se puede inferir: asigna p1 por defecto (pero esto lo evitamos editando seeds).
    """
    qq = dict(q or {})
    if "page_id" in qq and str(qq.get("page_id", "")).strip():
        return qq

    row = qq.get("row", {}) or {}
    inferred = page_id_from_row(row)
    qq["page_id"] = inferred if inferred in pages else "p1"
    return qq

# ==========================================================================================
# Helper NUEVO: sincronización multiselect -> text_area (soluciona tu bug del glosario)
# ==========================================================================================
def sync_glossary_order_text(page_id: str):
    """
    Cuando cambia el multiselect de términos por página, este callback:
    - recalcula el contenido del text_area "Orden (uno por línea)"
    - lo guarda en st.session_state usando el key correcto
    Así el usuario SIEMPRE ve el término nuevo agregado (ej. Arrebato).
    """
    ms_key = f"gl_terms_{page_id}"   # multiselect
    ta_key = f"gl_order_{page_id}"   # text_area

    selected = st.session_state.get(ms_key, []) or []
    # Si el usuario ya escribió un orden manual, NO lo pisamos si contiene algo distinto.
    # Pero si el text_area está vacío o solo tiene subset viejo, lo refrescamos.
    current_text = str(st.session_state.get(ta_key, "") or "").strip()
    current_lines = [ln.strip() for ln in current_text.splitlines() if ln.strip()]

    # Si no hay nada escrito, o si el text_area coincide exactamente con la selección anterior:
    if not current_lines:
        st.session_state[ta_key] = "\n".join(selected)
        return

    # Si agregaron términos nuevos, los anexamos al final (sin duplicar).
    seen = set(current_lines)
    appended = False
    for t in selected:
        if t not in seen:
            current_lines.append(t)
            seen.add(t)
            appended = True

    if appended:
        st.session_state[ta_key] = "\n".join(current_lines)

# ==========================================================================================
# FIN PARTE 1/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 2/10) ==============================
# ====================== Session State + Seeds (con page_id correcto) ======================
# ==========================================================================================
#
# PARTE 2/10:
# - Inicializa st.session_state para bancos editables:
#     questions_bank, choices_bank, glossary_bank, page_glossary_map
# - Seeds completos:
#     seed_choices_bank()  -> listas base + placeholders críticos (evita errores Survey123)
#     seed_glossary_bank() -> glosario inicial
#     seed_questions_bank(form_title, logo_media_name) -> P1..P8 con page_id explícito
#
# FIX CLAVE (tu bug de "no aparecen preguntas después de P5"):
# - Cada pregunta tendrá "page_id": "p1".."p8"
# - El editor (Parte 3) filtrará por q["page_id"] y ya NO se va a confundir.
#
# NOTA:
# - Aquí dejamos listo init_page_glossary_map() también (se usa en Parte 7).
# ==========================================================================================

# ==========================================================================================
# 1) Session State: inicialización
# ==========================================================================================
if "questions_bank" not in st.session_state:
    st.session_state.questions_bank = []

if "choices_bank" not in st.session_state:
    st.session_state.choices_bank = []

if "glossary_bank" not in st.session_state:
    st.session_state.glossary_bank = {}

if "page_glossary_map" not in st.session_state:
    st.session_state.page_glossary_map = {}

# (Opcional: compatibilidad si aún existe catálogo antiguo)
if "choices_ext_rows" not in st.session_state:
    st.session_state.choices_ext_rows = []

# ==========================================================================================
# 2) Generador de IDs únicos (evita StreamlitDuplicateElementKey)
# ==========================================================================================
def _new_qid(prefix: str = "q") -> str:
    st.session_state["_qid_counter"] = int(st.session_state.get("_qid_counter", 0)) + 1
    return f"{prefix}_{st.session_state['_qid_counter']}_{datetime.now().strftime('%H%M%S%f')}"

# ==========================================================================================
# 3) Seeds: choices_bank
# ==========================================================================================
def seed_choices_bank() -> list[dict]:
    """
    Choices base + placeholders críticos.
    IMPORTANTE: list_canton y list_distrito SIEMPRE existen (aunque no carguen cantones),
    así Survey123 no falla con:
      'List name not in choices sheet: list_canton'
    """
    rows = []

    def add_list(list_name: str, labels: list[str], extra_cols: dict | None = None):
        used = set((r.get("list_name"), r.get("name")) for r in rows)
        for lab in labels:
            nm = slugify_name(lab)
            row = {"list_name": list_name, "name": nm, "label": lab}
            if extra_cols:
                row.update(extra_cols)
            key = (row["list_name"], row["name"])
            if key not in used:
                rows.append(row)
                used.add(key)

    # yesno
    add_list("yesno", ["Sí", "No"])

    # Demográficos
    add_list("genero", ["Femenino", "Masculino", "Persona No Binaria", "Prefiero no decir"])
    add_list("escolaridad", [
        "Ninguna",
        "Primaria incompleta",
        "Primaria completa",
        "Secundaria incompleta",
        "Secundaria completa",
        "Técnico",
        "Universitaria incompleta",
        "Universitaria completa",
    ])
    add_list("relacion_zona", ["Vivo en la zona", "Trabajo en la zona", "Visito la zona", "Estudio en la zona"])

    # Escalas y matrices
    add_list("seguridad_5", ["Muy inseguro", "Inseguro", "Ni seguro ni inseguro", "Seguro", "Muy seguro"])
    add_list("escala_1_5", [
        "1 (Mucho Menos Seguro)",
        "2 (Menos Seguro)",
        "3 (Se mantiene igual)",
        "4 (Más Seguro)",
        "5 (Mucho Más Seguro)",
    ])
    add_list("matriz_1_5_na", [
        "Muy inseguro (1)",
        "Inseguro (2)",
        "Ni seguro ni inseguro (3)",
        "Seguro (4)",
        "Muy seguro (5)",
        "No aplica",
    ])

    # Tipos espacio P10
    add_list("tipo_espacio", [
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

    # Causas inseguridad 7.1
    add_list("causas_inseguridad", [
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
    ])

    # P5 choices
    add_list("p12_prob_situacionales", [
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
    ])

    add_list("p13_carencias_inversion", [
        "Falta de oferta educativa",
        "Falta de oferta deportiva",
        "Falta de oferta recreativa",
        "Falta de actividades culturales",
    ])

    add_list("p14_consumo_drogas_donde", ["Área privada", "Área pública", "No se observa consumo"])
    add_list("p15_def_infra_vial", ["Calles en mal estado", "Falta de señalización de tránsito", "Carencia o inexistencia de aceras"])
    add_list("p16_bunkeres_espacios", ["Casa de habitación (Espacio Cerrado)", "Edificación abandonada", "Lote baldío", "Otro"])
    add_list("p17_transporte_afect", ["Informal (taxis piratas)", "Plataformas (digitales)"])
    add_list("p18_presencia_policial", ["Falta de presencia policial", "Presencia policial insuficiente", "Presencia policial solo en ciertos horarios", "No observa presencia policial"])

    # P6 delitos
    add_list("p19_delitos_general", [
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

    add_list("p20_bunker_percepcion", [
        "En espacios cerrados (casas, edificaciones u otros inmuebles)",
        "En vía pública",
        "De forma ocasional o móvil (sin punto fijo)",
        "No se percibe consumo o venta",
        "Otro"
    ])

    add_list("p21_vida", ["Homicidios", "Heridos (lesiones dolosas)", "Femicidio"])
    add_list("p22_sexuales", ["Abuso sexual", "Acoso sexual", "Violación", "Acoso Callejero"])
    add_list("p23_asaltos", ["Asalto a personas", "Asalto a comercio", "Asalto a vivienda", "Asalto a transporte público"])
    add_list("p24_estafas", ["Billetes falsos", "Documentos falsos", "Estafa (Oro)", "Lotería falsos", "Estafas informáticas", "Estafa telefónica", "Estafa con tarjetas"])
    add_list("p25_robo_fuerza", [
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
    add_list("p26_abandono", ["Abandono de adulto mayor", "Abandono de menor de edad", "Abandono de incapaz"])
    add_list("p27_explotacion_infantil", ["Sexual", "Laboral"])
    add_list("p28_ambientales", ["Caza ilegal", "Pesca ilegal", "Tala ilegal", "Minería ilegal"])
    add_list("p29_trata", ["Con fines laborales", "Con fines sexuales"])

    # P7 victimización
    add_list("p30_vif", ["Sí", "No"])
    add_list("p301_tipos_vif", [
        "Violencia psicológica (gritos, amenazas, humillaciones, maltratos, entre otros)",
        "Violencia física (agresiones físicas, empujones, golpes, entre otros)",
        "Violencia vicaria (uso de hijas, hijos u otras personas para causar daño emocional)",
        "Violencia patrimonial (destrucción, retención o control de bienes, documentos o dinero)",
        "Violencia sexual (actos de carácter sexual sin consentimiento)"
    ])
    add_list("p302_medidas", ["Sí", "No", "No recuerda"])
    add_list("p303_valoracion_fp", ["Excelente", "Bueno", "Regular", "Malo", "Muy malo"])
    add_list("p31_delito_12m", ["NO", "Sí, y denuncié", "Sí, pero no denuncié."])

    # P8 confianza
    add_list("p32_identifica_policias", ["Sí", "No"])
    add_list("p321_interacciones", [
        "Solicitud de ayuda o auxilio.",
        "Atención relacionada con una denuncia.",
        "Atención cordial o preventiva durante un patrullaje.",
        "Fui abordado o registrado para identificación.",
        "Fui objeto de una infracción o conflicto.",
        "Evento preventivos (Cívico policial, Reunión Comunitaria)",
        "Otra (especifique)"
    ])
    add_list("escala_1_10", [str(i) for i in range(1, 11)])
    add_list("p38_frecuencia", ["Todos los días", "Varias veces por semana", "Una vez por semana", "Casi nunca", "Nunca"])
    add_list("p39_si_no_aveces", ["Sí", "No", "A veces"])
    add_list("p41_opciones", ["Sí", "No", "No estoy seguro(a)"])
    add_list("p43_acciones_fp", [
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
    add_list("p44_acciones_muni", [
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
    add_list("p45_info_delito", ["Sí", "No"])

    # ✅ CRÍTICO: placeholders de cascada (evita error de list_name no existente)
    # list_canton
    rows.append({"list_name": "list_canton", "name": "placeholder_1", "label": "—"})
    # list_distrito (incluye canton_key para choice_filter)
    rows.append({"list_name": "list_distrito", "name": "placeholder_1", "label": "—", "canton_key": "placeholder_1"})

    return rows

# ==========================================================================================
# 4) Seeds: glossary_bank
# ==========================================================================================
def seed_glossary_bank() -> dict:
    return {
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
# 5) Page glossary map (asignación por página)
# ==========================================================================================
def init_page_glossary_map():
    st.session_state.page_glossary_map = {
        "p1": [],
        "p2": [],
        "p3": [],
        "p4": ["Extorsión", "Daños/vandalismo"],
        "p5": ["Búnkeres", "Receptación", "Contrabando", "Trata de personas", "Explotación infantil", "Acoso callejero", "Tráfico de personas (coyotaje)", "Estafa", "Tacha"],
        "p6": ["Receptación", "Contrabando", "Tráfico de personas (coyotaje)", "Acoso callejero", "Estafa", "Tacha", "Trata de personas", "Explotación infantil", "Extorsión", "Búnkeres"],
        "p7": ["Ganzúa (pata de chancho)", "Boquete", "Arrebato", "Receptación", "Extorsión"],
        "p8": ["Patrullaje", "Acciones disuasivas", "Coordinación interinstitucional", "Integridad y credibilidad policial"],
    }

# ==========================================================================================
# 6) Seeds: questions_bank (plantilla mínima de estructura por páginas con page_id)
# ==========================================================================================
# NOTA:
# Para no pegar 500+ líneas aquí, esta seed se arma “por piezas” en Parte 3/10,
# donde también va el editor. En esta Parte 2 dejamos el cascarón y en Parte 3
# pegamos todo el seed completo de preguntas (P1..P8) con page_id explícito.
#
# Si tu seed actual YA está completo, lo único que debes hacer es:
# - agregar "page_id": "pX" a cada entrada del questions_bank
# y listo. En Parte 3 te lo dejo exactamente implementado.
def seed_questions_bank(form_title: str, logo_media_name: str) -> list[dict]:
    """
    Seed placeholder: se completa en Parte 3 con el listado completo.
    """
    return []

# ==========================================================================================
# 7) Inicialización efectiva si está vacío
# ==========================================================================================
if not st.session_state.choices_bank:
    st.session_state.choices_bank = seed_choices_bank()

if not st.session_state.glossary_bank:
    st.session_state.glossary_bank = seed_glossary_bank()

if not st.session_state.page_glossary_map:
    init_page_glossary_map()

# questions_bank se llena en Parte 3 (seed completo). Si ya lo tienes, NO lo sobrescribas.
# Solo asegúrate de que cada q tenga page_id:
if st.session_state.questions_bank:
    st.session_state.questions_bank = [ensure_question_page_id(q) for q in st.session_state.questions_bank]

# ==========================================================================================
# FIN PARTE 2/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 3/10) ==============================
# =================== Navegación + Seed COMPLETO P1..P8 + Editor Preguntas FIX =============
# ==========================================================================================
#
# PARTE 3/10 (ACTUALIZADA) SOLUCIONA TUS 2 PROBLEMAS:
# ✅ (A) “No me aparecen preguntas después de P5”
#     - Causa: el filtro por página estaba basado en nombres de group o inferencias.
#     - Solución: cada pregunta en questions_bank tiene `page_id` explícito ("p1".."p8")
#       y el editor filtra ÚNICAMENTE por `q["page_id"]`.
#
# ✅ (B) Vista legible muestra begin_group de otra página
#     - Causa: page_sel ≠ group real por inferencia
#     - Solución: el render usa `page_id` y el selector muestra solo esas preguntas.
#
# Además:
# - Implementa seed_questions_bank() COMPLETO (P1..P8, Q1..Q47 y grupos).
# - Implementa editor legible tipo Survey123 + edición simple/avanzada.
#
# NOTA:
# - En Parte 7 ajustamos el glosario por página con on_change para que “Arrebato” aparezca
#   en Orden/Vista previa (tu bug del multiselect->text_area).
# ==========================================================================================

# ==========================================================================================
# 1) Navegación (Secciones)
# ==========================================================================================
tabs = ["Preguntas", "Choices", "Glosario", "Catálogo", "Exportar"]
active_tab = st.radio("Sección", tabs, horizontal=True, key="nav_tabs_main")

# ==========================================================================================
# 2) Logo + Delegación (UI básica)
# ==========================================================================================
DEFAULT_LOGO_PATH = "001.png"

col_logo, col_txt = st.columns([1, 3], vertical_alignment="center")

with col_logo:
    up_logo = st.file_uploader("Logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="upl_logo_main")
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
    delegacion = st.text_input("Nombre del lugar / Delegación", value="San Carlos Oeste", key="delegacion_main")
    logo_media_name = st.text_input(
        "Nombre de archivo para `media::image`",
        value=st.session_state.get("_logo_name", "001.png"),
        help="Debe coincidir con el archivo dentro de la carpeta `media/` del proyecto Survey123 (Connect).",
        key="logo_media_name_main"
    )

form_title = f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad"
st.markdown(f"### {form_title}")

# ==========================================================================================
# 3) Textos base (Introducción y Consentimiento)
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

# ==========================================================================================
# 4) Seed COMPLETO de preguntas (questions_bank) con page_id explícito
# ==========================================================================================
def _mk_q(page_id: str, row: dict) -> dict:
    """
    Crea una entrada de questions_bank con:
    - qid único
    - page_id explícito
    - row XLSForm
    """
    q = {"qid": _new_qid("q"), "page_id": page_id, "row": dict(row)}
    return ensure_question_page_id(q)

def seed_questions_bank(form_title: str, logo_media_name: str) -> list[dict]:
    """
    Seed completo P1..P8, replicando tu XLSForm original,
    pero guardado como banco editable en la app.
    """
    qb = []

    v_si = slugify_name("Sí")
    v_no = slugify_name("No")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    # ------------------------
    # P1 Introducción
    # ------------------------
    qb.append(_mk_q("p1", {"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"}))
    qb.append(_mk_q("p1", {"type": "note", "name": "p1_logo", "label": form_title, "media::image": logo_media_name, "bind::esri:fieldType": "null"}))
    qb.append(_mk_q("p1", {"type": "note", "name": "p1_texto", "label": INTRO_COMUNIDAD_EXACTA, "bind::esri:fieldType": "null"}))
    qb.append(_mk_q("p1", {"type": "end_group", "name": "p1_end"}))

    # ------------------------
    # P2 Consentimiento
    # ------------------------
    qb.append(_mk_q("p2", {"type": "begin_group", "name": "p2_consent", "label": "Consentimiento Informado", "appearance": "field-list"}))
    qb.append(_mk_q("p2", {"type": "note", "name": "p2_titulo", "label": CONSENT_TITLE, "bind::esri:fieldType": "null"}))
    for i, p in enumerate(CONSENT_PARRAFOS, start=1):
        qb.append(_mk_q("p2", {"type": "note", "name": f"p2_p_{i}", "label": p, "bind::esri:fieldType": "null"}))
    for j, b in enumerate(CONSENT_BULLETS, start=1):
        qb.append(_mk_q("p2", {"type": "note", "name": f"p2_b_{j}", "label": f"• {b}", "bind::esri:fieldType": "null"}))
    for k, c in enumerate(CONSENT_CIERRE, start=1):
        qb.append(_mk_q("p2", {"type": "note", "name": f"p2_c_{k}", "label": c, "bind::esri:fieldType": "null"}))

    qb.append(_mk_q("p2", {
        "type": "select_one yesno",
        "name": "acepta_participar",
        "label": "¿Acepta participar en esta encuesta?",
        "required": "yes",
        "appearance": "minimal"
    }))
    qb.append(_mk_q("p2", {"type": "end_group", "name": "p2_end"}))

    qb.append(_mk_q("p2", {
        "type": "end",
        "name": "fin_por_no",
        "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.",
        "relevant": f"${{acepta_participar}}='{v_no}'"
    }))

    # ------------------------
    # P3 Datos demográficos
    # ------------------------
    qb.append(_mk_q("p3", {
        "type": "begin_group",
        "name": "p3_datos_demograficos",
        "label": "Datos demográficos",
        "appearance": "field-list",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p3", {
        "type": "select_one list_canton",
        "name": "canton",
        "label": "1. Cantón:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    }))

    rel_distrito = f"({rel_si}) and string-length(${{canton}}) > 0"
    qb.append(_mk_q("p3", {
        "type": "select_one list_distrito",
        "name": "distrito",
        "label": "2. Distrito:",
        "required": "yes",
        "choice_filter": "canton_key=${canton}",
        "appearance": "minimal",
        "relevant": rel_distrito
    }))

    qb.append(_mk_q("p3", {
        "type": "integer",
        "name": "edad_anos",
        "label": "3. Edad:",
        "required": "yes",
        "constraint": ". >= 18 and . <= 120",
        "constraint_message": "Debe ser un número entre 18 y 120.",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p3", {
        "type": "select_one genero",
        "name": "genero",
        "label": "4. ¿Con cuál de estas opciones se identifica?",
        "required": "yes",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p3", {
        "type": "select_one escolaridad",
        "name": "escolaridad",
        "label": "5. Escolaridad:",
        "required": "yes",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p3", {
        "type": "select_one relacion_zona",
        "name": "relacion_zona",
        "label": "6. ¿Cuál es su relación con la zona?",
        "required": "yes",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p3", {"type": "end_group", "name": "p3_end"}))

    # ------------------------
    # P4 Percepción (7-11)
    # ------------------------
    qb.append(_mk_q("p4", {
        "type": "begin_group",
        "name": "p4_percepcion_distrito",
        "label": "Percepción ciudadana de seguridad en el distrito",
        "appearance": "field-list",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p4", {
        "type": "select_one seguridad_5",
        "name": "p7_seguridad_distrito",
        "label": "7. ¿Qué tan seguro percibe usted el distrito donde reside o transita?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    }))

    rel_71 = (
        f"({rel_si}) and ("
        f"${{p7_seguridad_distrito}}='{slugify_name('Muy inseguro')}' or "
        f"${{p7_seguridad_distrito}}='{slugify_name('Inseguro')}'"
        f")"
    )

    qb.append(_mk_q("p4", {
        "type": "select_multiple causas_inseguridad",
        "name": "p71_causas_inseguridad",
        "label": "7.1. Indique por qué considera el distrito inseguro (Marque todas las situaciones que usted percibe que ocurren con mayor frecuencia en su comunidad):",
        "required": "yes",
        "relevant": rel_71
    }))

    qb.append(_mk_q("p4", {
        "type": "note",
        "name": "p71_no_denuncia",
        "label": "Esta pregunta recoge percepción general y no constituye denuncia.",
        "relevant": rel_71,
        "bind::esri:fieldType": "null"
    }))

    qb.append(_mk_q("p4", {
        "type": "text",
        "name": "p71_otro_detalle",
        "label": "Otro problema que considere importante (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_71}) and selected(${{p71_causas_inseguridad}}, '{slugify_name('Otro problema que considere importante')}')"
    }))

    qb.append(_mk_q("p4", {
        "type": "select_one escala_1_5",
        "name": "p8_comparacion_anno",
        "label": "8. ¿Cómo se percibe la seguridad en este distrito este año en comparación con el año anterior?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    }))

    rel_81 = f"({rel_si}) and string-length(${{p8_comparacion_anno}}) > 0"
    qb.append(_mk_q("p4", {
        "type": "text",
        "name": "p81_indique_por_que",
        "label": "8.1. Indique por qué:",
        "required": "yes",
        "appearance": "multiline",
        "relevant": rel_81
    }))

    qb.append(_mk_q("p4", {
        "type": "note",
        "name": "p9_instr",
        "label": "9. Indique qué tan seguros percibe, en términos de seguridad, en los siguientes espacios de su Distrito:",
        "relevant": rel_si,
        "bind::esri:fieldType": "null"
    }))

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
    for nm, lab in matriz_filas:
        qb.append(_mk_q("p4", {
            "type": "select_one matriz_1_5_na",
            "name": nm,
            "label": lab,
            "required": "yes",
            "appearance": "minimal",
            "relevant": rel_si
        }))

    qb.append(_mk_q("p4", {
        "type": "select_one tipo_espacio",
        "name": "p10_tipo_espacio_mas_inseguro",
        "label": "10. Según su percepción, ¿cuál de los siguientes tipos de espacios del distrito considera más inseguro?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p4", {
        "type": "text",
        "name": "p10_otros_detalle",
        "label": "Otros (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and (${{p10_tipo_espacio_mas_inseguro}}='{slugify_name('Otros')}')"
    }))

    qb.append(_mk_q("p4", {
        "type": "text",
        "name": "p11_por_que_inseguro_tipo_espacio",
        "label": "11. Según su percepción, describa brevemente por qué considera inseguro el tipo de espacio seleccionado en la pregunta anterior.",
        "required": "no",
        "appearance": "multiline",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p4", {"type": "end_group", "name": "p4_end"}))

    # ------------------------
    # P5 Riesgos / factores situacionales (12-18)
    # ------------------------
    qb.append(_mk_q("p5", {
        "type": "begin_group",
        "name": "p5_riesgos",
        "label": "III. RIESGOS, DELITOS, VICTIMIZACIÓN Y EVALUACIÓN POLICIAL",
        "appearance": "field-list",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p5", {"type": "note", "name": "p5_subtitulo", "label": "Riesgos sociales y situacionales en el distrito", "relevant": rel_si, "bind::esri:fieldType": "null"}))
    qb.append(_mk_q("p5", {"type": "note", "name": "p5_intro", "label": "A continuación, se presentará una lista de problemáticas que se catalogan como factores situacionales, con la finalidad de que seleccione aquellos que considere que ocurren en su distrito.", "relevant": rel_si, "bind::esri:fieldType": "null"}))

    qb.append(_mk_q("p5", {
        "type": "select_multiple p12_prob_situacionales",
        "name": "p12_problematicas_distrito",
        "label": "12. Según su percepción u observación, seleccione las problemáticas que afectan su distrito:",
        "required": "yes",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p5", {
        "type": "text",
        "name": "p12_otro_detalle",
        "label": "Otro problema que considere importante:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p12_problematicas_distrito}}, '{slugify_name('Otro problema que considere importante')}')"
    }))

    qb.append(_mk_q("p5", {
        "type": "select_multiple p13_carencias_inversion",
        "name": "p13_carencias_inversion_social",
        "label": "13. En relación con la inversión social en su distrito, indique cuáles de las siguientes carencias identifica:",
        "required": "yes",
        "relevant": rel_si
    }))

    n_no_obs = slugify_name("No se observa consumo")
    n_priv = slugify_name("Área privada")
    n_pub = slugify_name("Área pública")
    constraint_p14 = f"not(selected(., '{n_no_obs}') and (selected(., '{n_priv}') or selected(., '{n_pub}')))"

    qb.append(_mk_q("p5", {
        "type": "select_multiple p14_consumo_drogas_donde",
        "name": "p14_donde_consumo_drogas",
        "label": "14. Según su percepción u observación, indique dónde se presenta consumo de drogas en el distrito:",
        "required": "yes",
        "constraint": constraint_p14,
        "constraint_message": "Si selecciona “No se observa consumo”, no puede seleccionar “Área privada” ni “Área pública”.",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p5", {
        "type": "select_multiple p15_def_infra_vial",
        "name": "p15_deficiencias_infra_vial",
        "label": "15. Indique las principales deficiencias de infraestructura vial que afectan su distrito:",
        "required": "yes",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p5", {
        "type": "select_multiple p16_bunkeres_espacios",
        "name": "p16_bunkeres_espacios",
        "label": "16. Según su percepción u observación, indique en qué tipo de espacios se identifica la existencia de puntos de venta de drogas (búnkeres) en el distrito:",
        "required": "yes",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p5", {
        "type": "text",
        "name": "p16_otro_detalle",
        "label": "Otro:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p16_bunkeres_espacios}}, '{slugify_name('Otro')}')"
    }))

    qb.append(_mk_q("p5", {
        "type": "select_multiple p17_transporte_afect",
        "name": "p17_transporte_afectacion",
        "label": "17. En relación con el transporte en su distrito, indique cuáles situaciones representan una afectación:",
        "required": "yes",
        "relevant": rel_si
    }))

    n_no_pres = slugify_name("No observa presencia policial")
    n_falta = slugify_name("Falta de presencia policial")
    n_insuf = slugify_name("Presencia policial insuficiente")
    n_hor = slugify_name("Presencia policial solo en ciertos horarios")
    constraint_p18 = f"not(selected(., '{n_no_pres}') and (selected(., '{n_falta}') or selected(., '{n_insuf}') or selected(., '{n_hor}')))"

    qb.append(_mk_q("p5", {
        "type": "select_multiple p18_presencia_policial",
        "name": "p18_presencia_policial",
        "label": "18. En relación con la presencia policial en su distrito, indique cuál de las siguientes situaciones identifica:",
        "required": "yes",
        "constraint": constraint_p18,
        "constraint_message": "Si selecciona “No observa presencia policial”, no seleccione otras opciones simultáneamente.",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p5", {"type": "end_group", "name": "p5_end"}))

    # ------------------------
    # P6 Delitos (19-29)
    # ------------------------
    qb.append(_mk_q("p6", {
        "type": "begin_group",
        "name": "p6_delitos",
        "label": "Delitos",
        "appearance": "field-list",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p6", {
        "type": "note",
        "name": "p6_intro",
        "label": "A continuación, se presentará una lista de delitos y situaciones delictivas para que seleccione aquellos que, según su percepción u observación, considera que se presentan en su comunidad. Esta información no constituye denuncia formal ni confirmación de hechos delictivos.",
        "relevant": rel_si,
        "bind::esri:fieldType": "null"
    }))

    qb.append(_mk_q("p6", {
        "type": "select_multiple p19_delitos_general",
        "name": "p19_delitos_general",
        "label": "19. Selección múltiple de los siguientes delitos:",
        "required": "yes",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p6", {
        "type": "text",
        "name": "p19_otro_detalle",
        "label": "Otro:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p19_delitos_general}}, '{slugify_name('Otro')}')"
    }))

    n20_no_percibe = slugify_name("No se percibe consumo o venta")
    n20_cerrado = slugify_name("En espacios cerrados (casas, edificaciones u otros inmuebles)")
    n20_via = slugify_name("En vía pública")
    n20_movil = slugify_name("De forma ocasional o móvil (sin punto fijo)")
    n20_otro = slugify_name("Otro")
    constraint_p20 = f"not(selected(., '{n20_no_percibe}') and (selected(., '{n20_cerrado}') or selected(., '{n20_via}') or selected(., '{n20_movil}') or selected(., '{n20_otro}')))"

    qb.append(_mk_q("p6", {
        "type": "select_multiple p20_bunker_percepcion",
        "name": "p20_bunker_percepcion",
        "label": "20. Percepción de consumo o venta de drogas en el entorno (Bunker)",
        "required": "yes",
        "constraint": constraint_p20,
        "constraint_message": "Si selecciona “No se percibe consumo o venta”, no seleccione otras opciones simultáneamente.",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p6", {
        "type": "text",
        "name": "p20_otro_detalle",
        "label": "Otro:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p20_bunker_percepcion}}, '{slugify_name('Otro')}')"
    }))

    qb.append(_mk_q("p6", {"type": "select_multiple p21_vida", "name": "p21_delitos_vida", "label": "21. Delitos contra la vida", "required": "yes", "relevant": rel_si}))
    qb.append(_mk_q("p6", {"type": "select_multiple p22_sexuales", "name": "p22_delitos_sexuales", "label": "22. Delitos sexuales", "required": "yes", "relevant": rel_si}))
    qb.append(_mk_q("p6", {"type": "select_multiple p23_asaltos", "name": "p23_asaltos_percibidos", "label": "23. Asaltos percibidos", "required": "yes", "relevant": rel_si}))
    qb.append(_mk_q("p6", {"type": "select_multiple p24_estafas", "name": "p24_estafas_percibidas", "label": "24. Estafas percibidas", "required": "yes", "relevant": rel_si}))
    qb.append(_mk_q("p6", {"type": "select_multiple p25_robo_fuerza", "name": "p25_robo_percibidos", "label": "25. Robo percibidos (Sustracción de artículos mediante la utilización de la fuerza)", "required": "yes", "relevant": rel_si}))
    qb.append(_mk_q("p6", {"type": "select_multiple p26_abandono", "name": "p26_abandono_personas", "label": "26. Abandono de personas", "required": "yes", "relevant": rel_si}))
    qb.append(_mk_q("p6", {"type": "select_multiple p27_explotacion_infantil", "name": "p27_explotacion_infantil", "label": "27. Explotación infantil", "required": "yes", "relevant": rel_si}))
    qb.append(_mk_q("p6", {"type": "select_multiple p28_ambientales", "name": "p28_delitos_ambientales", "label": "28. Delitos ambientales percibidos", "required": "yes", "relevant": rel_si}))
    qb.append(_mk_q("p6", {"type": "select_multiple p29_trata", "name": "p29_trata_personas", "label": "29. Trata de personas", "required": "yes", "relevant": rel_si}))

    qb.append(_mk_q("p6", {"type": "end_group", "name": "p6_end"}))

    # ------------------------
    # P7 Victimización (30-31.4)
    # ------------------------
    qb.append(_mk_q("p7", {
        "type": "begin_group",
        "name": "p7_victimizacion",
        "label": "Victimización",
        "appearance": "field-list",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p7", {
        "type": "note",
        "name": "p7_intro",
        "label": "A continuación, se presentará una lista de situaciones para que indique si usted o algún miembro de su hogar ha sido afectado por alguna de ellas en su distrito durante el último año.",
        "relevant": rel_si,
        "bind::esri:fieldType": "null"
    }))

    qb.append(_mk_q("p7", {
        "type": "select_one p30_vif",
        "name": "p30_vif",
        "label": "30. Durante el último año, ¿usted o algún miembro de su hogar ha sido afectado por alguna situación de violencia intrafamiliar (violencia doméstica)?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    }))

    rel_30_si = f"({rel_si}) and (${{p30_vif}}='{slugify_name('Sí')}')"

    qb.append(_mk_q("p7", {"type": "select_multiple p301_tipos_vif", "name": "p301_tipos_vif", "label": "30.1. ¿Qué tipo(s) de violencia intrafamiliar (violencia doméstica) se presentaron?", "required": "yes", "relevant": rel_30_si}))
    qb.append(_mk_q("p7", {"type": "select_one p302_medidas", "name": "p302_medidas_proteccion", "label": "30.2. ¿En relación con la situación de violencia intrafamiliar indicada anteriormente, usted o algún miembro de su hogar solicitó medidas de protección?", "required": "yes", "appearance": "minimal", "relevant": rel_30_si}))
    qb.append(_mk_q("p7", {"type": "select_one p303_valoracion_fp", "name": "p303_valoracion_fp", "label": "30.3. ¿Cómo valora el abordaje de la Fuerza Pública ante esta situación?", "required": "yes", "appearance": "minimal", "relevant": rel_30_si}))

    qb.append(_mk_q("p7", {
        "type": "select_one p31_delito_12m",
        "name": "p31_delito_12m",
        "label": "31. Durante los últimos 12 meses, ¿usted o algún miembro de su hogar fue afectado por algún delito?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    }))

    val_31_si_den = slugify_name("Sí, y denuncié")
    val_31_si_no_den = slugify_name("Sí, pero no denuncié.")
    rel_31_si = f"({rel_si}) and (${{p31_delito_12m}}='{val_31_si_den}' or ${{p31_delito_12m}}='{val_31_si_no_den}')"
    rel_31_si_no_den = f"({rel_si}) and (${{p31_delito_12m}}='{val_31_si_no_den}')"

    qb.append(_mk_q("p7", {"type": "select_multiple p311_situaciones", "name": "p311_situaciones_afecto", "label": "31.1. ¿Cuál de las siguientes situaciones afectó a usted o a algún miembro de su hogar?", "required": "yes", "relevant": rel_31_si}))
    qb.append(_mk_q("p7", {"type": "select_multiple p312_motivos_no_denuncia", "name": "p312_motivo_no_denuncia", "label": "31.2. En caso de NO haber realizado la denuncia, indique ¿cuál fue el motivo?", "required": "yes", "relevant": rel_31_si_no_den}))
    qb.append(_mk_q("p7", {"type": "select_one p313_horario", "name": "p313_horario_hecho", "label": "31.3. ¿Tiene conocimiento sobre el horario en el cual se presentó el hecho o situación que le afectó a usted o un familiar?", "required": "yes", "appearance": "minimal", "relevant": rel_31_si}))
    qb.append(_mk_q("p7", {"type": "select_multiple p314_modo", "name": "p314_modo_ocurrio", "label": "31.4. ¿Cuál fue la forma o modo en que ocurrió la situación que afectó a usted o a algún miembro de su hogar?", "required": "yes", "relevant": rel_31_si}))
    qb.append(_mk_q("p7", {"type": "text", "name": "p314_otro_detalle", "label": "Otro (detalle):", "required": "no", "appearance": "multiline", "relevant": f"({rel_31_si}) and selected(${{p314_modo_ocurrio}}, '{slugify_name('Otro')}')"}))

    qb.append(_mk_q("p7", {"type": "end_group", "name": "p7_end"}))

    # ------------------------
    # P8 Confianza + Cierre (32-47)
    # ------------------------
    qb.append(_mk_q("p8", {
        "type": "begin_group",
        "name": "p8_confianza_policial",
        "label": "Confianza Policial",
        "appearance": "field-list",
        "relevant": rel_si
    }))

    qb.append(_mk_q("p8", {"type": "note", "name": "p8_intro", "label": "A continuación, se presentará una lista de afirmaciones relacionadas con su percepción y confianza en el cuerpo de policía que opera en su (Distrito) barrio.", "relevant": rel_si, "bind::esri:fieldType": "null"}))

    qb.append(_mk_q("p8", {"type": "select_one p32_identifica_policias", "name": "p32_identifica_policias", "label": "32. ¿Identifica usted a los policías de la Fuerza Pública de Costa Rica en su comunidad?", "required": "yes", "appearance": "minimal", "relevant": rel_si}))

    rel_321 = f"({rel_si}) and (${{p32_identifica_policias}}='{slugify_name('Sí')}')"
    qb.append(_mk_q("p8", {"type": "select_multiple p321_interacciones", "name": "p321_tipos_atencion", "label": "32.1 ¿Cuáles de los siguientes tipos de atención ha tenido?", "required": "yes", "relevant": rel_321}))
    qb.append(_mk_q("p8", {"type": "text", "name": "p321_otro_detalle", "label": "Otra (especifique):", "required": "no", "appearance": "multiline", "relevant": f"({rel_321}) and selected(${{p321_tipos_atencion}}, '{slugify_name('Otra (especifique)')}')"}))

    qb.append(_mk_q("p8", {"type": "select_one escala_1_10", "name": "p33_confianza_policial", "label": "33. ¿Cuál es el nivel de confianza en la policía de la Fuerza Pública de Costa Rica de su comunidad? (1=Ninguna Confianza, 10=Mucha Confianza)", "required": "yes", "appearance": "minimal", "relevant": rel_si}))
    qb.append(_mk_q("p8", {"type": "select_one escala_1_10", "name": "p34_profesionalidad", "label": "34. En una escala del 1 al 10, donde 1 es “Nada profesional” y 10 es “Muy profesional”, ¿cómo calificaría la profesionalidad de la Fuerza Pública en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si}))
    qb.append(_mk_q("p8", {"type": "select_one escala_1_10", "name": "p35_calidad_servicio", "label": "35. En una escala del 1 al 10, donde 1 es “Muy mala” y 10 es “Muy buena”, ¿cómo califica la calidad del servicio policial en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si}))
    qb.append(_mk_q("p8", {"type": "select_one escala_1_10", "name": "p36_satisfaccion_preventivo", "label": "36. En una escala del 1 al 10, donde 1 es “Nada satisfecho(a)” y 10 es “Muy satisfecho(a)”, ¿qué tan satisfecho(a) está con el trabajo preventivo que realiza la Fuerza Pública en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si}))
    qb.append(_mk_q("p8", {"type": "select_one escala_1_10", "name": "p37_contribucion_reduccion_crimen", "label": "37. En una escala del 1 al 10, donde 1 es “No contribuye en nada” y 10 es “Contribuye muchísimo”, indique: ¿En qué medida considera que la presencia policial ayuda a reducir el crimen en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si}))
    qb.append(_mk_q("p8", {"type": "select_one p38_frecuencia", "name": "p38_frecuencia_presencia", "label": "38. ¿Con qué frecuencia observa presencia policial en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si}))
    qb.append(_mk_q("p8", {"type": "select_one p39_si_no_aveces", "name": "p39_presencia_consistente", "label": "39. ¿Considera que la presencia policial es consistente a lo largo del día en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si}))
    qb.append(_mk_q("p8", {"type": "select_one p39_si_no_aveces", "name": "p40_trato_justo", "label": "40. ¿Considera que la policía trata a las personas de manera justa e imparcial en su distrito?", "required": "yes", "appearance": "minimal", "relevant": rel_si}))
    qb.append(_mk_q("p8", {"type": "select_one p41_opciones", "name": "p41_quejas_sin_temor", "label": "41. ¿Cree usted que puede expresar preocupaciones o quejas a la policía sin temor a represalias?", "required": "yes", "appearance": "minimal", "relevant": rel_si}))
    qb.append(_mk_q("p8", {"type": "select_one p39_si_no_aveces", "name": "p42_info_veraz_clara", "label": "42. ¿Considera que la policía proporciona información veraz, clara y oportuna a la comunidad?", "required": "yes", "appearance": "minimal", "relevant": rel_si}))

    qb.append(_mk_q("p8", {"type": "select_multiple p43_acciones_fp", "name": "p43_accion_fp_mejorar", "label": "43. ¿Qué actividad considera que debe realizar la Fuerza Pública para mejorar la seguridad en su comunidad?", "required": "yes", "relevant": rel_si}))
    qb.append(_mk_q("p8", {"type": "text", "name": "p43_otro_detalle", "label": "Otro (detalle):", "required": "no", "appearance": "multiline", "relevant": f"({rel_si}) and selected(${{p43_accion_fp_mejorar}}, '{slugify_name('Otro')}')"}))

    qb.append(_mk_q("p8", {"type": "select_multiple p44_acciones_muni", "name": "p44_accion_muni_mejorar", "label": "44. ¿Qué actividad considera que debe realizar la municipalidad para mejorar la seguridad en su comunidad?", "required": "yes", "relevant": rel_si}))
    qb.append(_mk_q("p8", {"type": "text", "name": "p44_otro_detalle", "label": "Otro (detalle):", "required": "no", "appearance": "multiline", "relevant": f"({rel_si}) and selected(${{p44_accion_muni_mejorar}}, '{slugify_name('Otro')}')"}))

    qb.append(_mk_q("p8", {"type": "note", "name": "p8_info_adicional_titulo", "label": "Información Adicional y Contacto Voluntario", "relevant": rel_si, "bind::esri:fieldType": "null"}))

    qb.append(_mk_q("p8", {"type": "select_one p45_info_delito", "name": "p45_info_delito", "label": "45. ¿Usted tiene información de alguna persona o grupo que se dedique a realizar algún delito en su comunidad? (Recuerde, su información es confidencial.)", "required": "yes", "appearance": "minimal", "relevant": rel_si}))

    rel_451 = f"({rel_si}) and (${{p45_info_delito}}='{slugify_name('Sí')}')"
    qb.append(_mk_q("p8", {"type": "text", "name": "p451_detalle_info", "label": "45.1. Si su respuesta es \"Sí\", describa aquellas características que pueda aportar tales como nombre de estructura o banda criminal... (nombre de personas, alias, domicilio, vehículos, etc.)", "required": "yes", "appearance": "multiline", "relevant": rel_451}))
    qb.append(_mk_q("p8", {"type": "text", "name": "p46_contacto_voluntario", "label": "46. En el siguiente espacio de forma voluntaria podrá anotar su nombre, teléfono o correo electrónico en el cual desee ser contactado y continuar colaborando de forma confidencial con Fuerza Pública.", "required": "no", "appearance": "multiline", "relevant": rel_si}))
    qb.append(_mk_q("p8", {"type": "text", "name": "p47_info_adicional", "label": "47. En el siguiente espacio podrá registrar alguna otra información que estime pertinente.", "required": "no", "appearance": "multiline", "relevant": rel_si}))

    qb.append(_mk_q("p8", {"type": "note", "name": "p8_fin", "label": "---------------------------------- Fin de la Encuesta ----------------------------------", "relevant": rel_si, "bind::esri:fieldType": "null"}))
    qb.append(_mk_q("p8", {"type": "end_group", "name": "p8_end"}))

    # Asegurar page_id en todo
    qb = [ensure_question_page_id(q) for q in qb]
    return qb

# Cargar seed si aún está vacío (y NO sobreescribir si ya existe)
if not st.session_state.questions_bank:
    st.session_state.questions_bank = seed_questions_bank(form_title=form_title, logo_media_name=logo_media_name)

# Asegurar page_id siempre (por si restauraron backups viejos)
st.session_state.questions_bank = [ensure_question_page_id(q) for q in st.session_state.questions_bank]

# ==========================================================================================
# 5) Funciones de banco: ordenar y filtrar por página (FIX)
# ==========================================================================================
def qb_sorted() -> list[dict]:
    """
    Mantiene orden actual en questions_bank (lista).
    """
    return list(st.session_state.questions_bank or [])

def qb_by_page(page_id: str) -> list[dict]:
    """
    FILTRO CORRECTO: usa q["page_id"].
    """
    return [q for q in qb_sorted() if str(q.get("page_id", "")).strip() == page_id]

def qb_index_by_qid(qid: str) -> int:
    for i, q in enumerate(st.session_state.questions_bank or []):
        if q.get("qid") == qid:
            return i
    return -1

def qb_get(qid: str) -> dict | None:
    for q in st.session_state.questions_bank or []:
        if q.get("qid") == qid:
            return q
    return None

# ==========================================================================================
# 6) Render legible (similar Survey123) + Editor (simple/avanzado)
# ==========================================================================================
def _is_structural(tp: str) -> bool:
    return tp in {"begin_group", "end_group"}

def render_legible(row: dict):
    tp = str(row.get("type", "")).strip()
    label = str(row.get("label", "")).strip()
    name = str(row.get("name", "")).strip()

    # Header pequeño de metadata
    st.caption(f"Nombre interno: `{name}` | Tipo: `{tp}`")

    if tp == "begin_group":
        st.markdown(f"## {label or 'Grupo'}")
        st.info("Elemento estructural: begin_group")
    elif tp == "end_group":
        st.success("Fin de página / grupo (end_group)")
    elif tp == "note":
        st.write(label)
    else:
        # Pregunta “normal”
        if label:
            st.markdown(f"### {label}")
        else:
            st.markdown("### (Sin texto visible)")
        # Mostrar indicaciones básicas
        chips = []
        if str(row.get("required", "")).strip().lower() == "yes":
            chips.append("Requerida")
        if str(row.get("appearance", "")).strip():
            chips.append(f"appearance={row.get('appearance')}")
        if str(row.get("relevant", "")).strip():
            chips.append("condicional (relevant)")
        if str(row.get("constraint", "")).strip():
            chips.append("validación (constraint)")
        if chips:
            st.caption(" • ".join(chips))

def editor_simple(row: dict) -> dict:
    """
    Edición simple: label, required, appearance, relevant, constraint.
    """
    r = dict(row)

    tp = st.text_input("type", value=str(r.get("type", "")), key="ed_tp")
    nm = st.text_input("name", value=str(r.get("name", "")), key="ed_nm")
    lb = st.text_area("label (texto visible)", value=str(r.get("label", "")), height=120, key="ed_lb")

    required = st.selectbox("required", options=["", "yes", "no"], index=["", "yes", "no"].index(str(r.get("required", "")) if str(r.get("required", "")) in ["", "yes", "no"] else ""), key="ed_req")
    appearance = st.text_input("appearance", value=str(r.get("appearance", "")), key="ed_app")
    relevant = st.text_area("relevant (condición)", value=str(r.get("relevant", "")), height=80, key="ed_rel")
    choice_filter = st.text_input("choice_filter", value=str(r.get("choice_filter", "")), key="ed_cf")
    constraint = st.text_input("constraint", value=str(r.get("constraint", "")), key="ed_con")
    constraint_msg = st.text_input("constraint_message", value=str(r.get("constraint_message", "")), key="ed_conmsg")
    media_image = st.text_input("media::image", value=str(r.get("media::image", "")), key="ed_img")
    bind_null = st.text_input("bind::esri:fieldType", value=str(r.get("bind::esri:fieldType", "")), key="ed_bind")

    r["type"] = tp
    r["name"] = nm
    r["label"] = lb
    r["required"] = required
    r["appearance"] = appearance
    r["relevant"] = relevant
    r["choice_filter"] = choice_filter
    r["constraint"] = constraint
    r["constraint_message"] = constraint_msg
    r["media::image"] = media_image
    r["bind::esri:fieldType"] = bind_null

    return r

def editor_avanzado(row: dict) -> dict:
    """
    Edición avanzada: JSON directo del row.
    """
    raw = json.dumps(row, ensure_ascii=False, indent=2)
    txt = st.text_area("Row (JSON)", value=raw, height=360, key="ed_json")
    try:
        data = json.loads(txt)
        if not isinstance(data, dict):
            st.error("El JSON debe ser un objeto (dict).")
            return dict(row)
        return data
    except Exception as e:
        st.error(f"JSON inválido: {e}")
        return dict(row)

# ==========================================================================================
# 7) UI Editor de Preguntas (FIX por page_id)
# ==========================================================================================
if active_tab == "Preguntas":
    st.header("🧾 Editor de Preguntas (survey) — vista legible + edición")

    # Selector de página (por page_id)
    page_sel_label = st.selectbox(
        "Página",
        options=[pages_labels[p] for p in pages],
        index=pages.index(st.session_state.get("_page_sel", "p5") if st.session_state.get("_page_sel", "p5") in pages else "p5"),
        key="page_sel_editor_fix"
    )
    page_sel = [p for p, lab in pages_labels.items() if lab == page_sel_label][0]
    st.session_state["_page_sel"] = page_sel

    q_list = qb_by_page(page_sel)
    if not q_list:
        st.warning("No hay preguntas en esta página. (Esto ya no debería pasar con el seed corregido).")

    # Buscar en página
    search_txt = st.text_input("Buscar en esta página", value="", key="search_in_page_fix").strip().lower()

    filtered = []
    for q in q_list:
        r = q.get("row", {}) or {}
        s = (str(r.get("label", "")) + " " + str(r.get("name", "")) + " " + str(r.get("type", ""))).lower()
        if (not search_txt) or (search_txt in s):
            filtered.append(q)

    # Lista izquierda: seleccionar pregunta
    left, right = st.columns([1.1, 1.9], vertical_alignment="top")

    with left:
        st.subheader("Lista")
        opts = []
        for q in filtered:
            r = q.get("row", {}) or {}
            tp = str(r.get("type", "")).strip()
            nm = str(r.get("name", "")).strip()
            lb = str(r.get("label", "")).strip().replace("\n", " ")
            if len(lb) > 60:
                lb = lb[:60] + "…"
            title = f"[{tp}] {lb or nm or '(sin texto)'}"
            opts.append((title, q.get("qid")))

        if opts:
            # Selección actual
            current_qid = st.session_state.get("selected_qid", opts[0][1])
            if current_qid not in [o[1] for o in opts]:
                current_qid = opts[0][1]
            idx = [o[1] for o in opts].index(current_qid)

            sel_title = st.selectbox(
                "Elemento",
                options=[o[0] for o in opts],
                index=idx,
                key="sel_qid_title_fix"
            )
            selected_qid = opts[[o[0] for o in opts].index(sel_title)][1]
            st.session_state.selected_qid = selected_qid

        st.markdown("---")
        st.subheader("➕ Agregar pregunta")
        add_type = st.text_input("Tipo (ej. text, note, select_one yesno)", value="note", key="add_tp_fix")
        add_label = st.text_area("Texto (label)", value="", height=90, key="add_lb_fix")

        if st.button("Agregar", use_container_width=True, key="btn_add_q_fix"):
            new_row = {
                "type": add_type.strip(),
                "name": f"{page_sel}_{slugify_name(add_label) or 'nuevo'}_{datetime.now().strftime('%H%M%S')}",
                "label": add_label.strip(),
                "required": "",
                "appearance": "",
                "relevant": rel_si if page_sel != "p1" else "",
                "choice_filter": "",
                "constraint": "",
                "constraint_message": "",
                "media::image": "",
                "bind::esri:fieldType": "null" if add_type.strip() == "note" else "",
            }
            st.session_state.questions_bank.append(_mk_q(page_sel, new_row))
            st.success("Agregado.")
            st.rerun()

    with right:
        st.subheader("👁️ Vista legible (similar a Survey123)")

        selected = qb_get(st.session_state.get("selected_qid", "")) if st.session_state.get("selected_qid") else None
        if not selected:
            st.info("Selecciona un elemento en la lista.")
        else:
            row = selected.get("row", {}) or {}
            render_legible(row)

            st.markdown("---")
            st.subheader("✏️ Editar")
            mode = st.radio("Modo de edición", ["Simple", "Avanzado"], horizontal=True, key="edit_mode_fix")

            if mode == "Simple":
                new_row = editor_simple(row)
            else:
                new_row = editor_avanzado(row)

            cA, cB, cC, cD = st.columns(4)

            with cA:
                if st.button("💾 Guardar cambios", use_container_width=True, key="btn_save_q_fix"):
                    idx = qb_index_by_qid(selected.get("qid"))
                    if idx >= 0:
                        st.session_state.questions_bank[idx]["row"] = dict(new_row)
                        # asegurar page_id siempre
                        st.session_state.questions_bank[idx] = ensure_question_page_id(st.session_state.questions_bank[idx])
                        st.success("Guardado.")
                        st.rerun()

            with cB:
                if st.button("⬆️ Subir", use_container_width=True, key="btn_up_q_fix"):
                    idx = qb_index_by_qid(selected.get("qid"))
                    if idx > 0:
                        st.session_state.questions_bank[idx-1], st.session_state.questions_bank[idx] = st.session_state.questions_bank[idx], st.session_state.questions_bank[idx-1]
                        st.rerun()

            with cC:
                if st.button("⬇️ Bajar", use_container_width=True, key="btn_down_q_fix"):
                    idx = qb_index_by_qid(selected.get("qid"))
                    if 0 <= idx < len(st.session_state.questions_bank) - 1:
                        st.session_state.questions_bank[idx+1], st.session_state.questions_bank[idx] = st.session_state.questions_bank[idx], st.session_state.questions_bank[idx+1]
                        st.rerun()

            with cD:
                if st.button("🗑️ Eliminar", use_container_width=True, key="btn_del_q_fix"):
                    idx = qb_index_by_qid(selected.get("qid"))
                    if idx >= 0:
                        st.session_state.questions_bank.pop(idx)
                        st.success("Eliminado.")
                        st.rerun()

# ==========================================================================================
# FIN PARTE 3/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 4/10) ==============================
# ===================== Editor de CHOICES (listas) — simple, legible y seguro ==============
# ==========================================================================================
#
# PARTE 4/10 (ACTUALIZADA)
# ✅ Editor fácil para cualquier persona (sin “modo Excel complicado”):
#    - Elegís una lista (yesno, genero, escolaridad, etc.)
#    - Ves opciones como tabla editable (label y name)
#    - Podés agregar, editar, borrar
#    - Valida duplicados de "name" por list_name
#
# ✅ Incluye “listas obligatorias” para evitar el error de ArcGIS:
#    - list_canton y list_distrito SIEMPRE existen en choices_bank
#    - Si el usuario no cargó catálogo, se crea placeholder mínimo
#
# IMPORTANTE:
# - Este editor NO genera el XLSForm todavía (eso va en Parte 8/10),
#   pero deja los choices listos y consistentes para export.
# ==========================================================================================

# ==========================================================================================
# 1) Inicialización: choices_bank (diccionario de listas)
# ==========================================================================================
if "choices_bank" not in st.session_state:
    st.session_state.choices_bank = {}  # dict[str, list[dict]]

def _seed_choices_bank_minimo():
    """
    Crea choices_bank si está vacío con listas base.
    NOTA: list_canton/list_distrito se crean SIEMPRE para evitar error en Survey123.
    """
    if st.session_state.choices_bank:
        return

    cb = {}

    # Listas base (misma lógica del XLSForm original)
    cb["yesno"] = [
        {"name": slugify_name("Sí"), "label": "Sí"},
        {"name": slugify_name("No"), "label": "No"},
    ]

    cb["genero"] = [
        {"name": slugify_name("Femenino"), "label": "Femenino"},
        {"name": slugify_name("Masculino"), "label": "Masculino"},
        {"name": slugify_name("Persona No Binaria"), "label": "Persona No Binaria"},
        {"name": slugify_name("Prefiero no decir"), "label": "Prefiero no decir"},
    ]

    cb["escolaridad"] = [
        {"name": slugify_name("Ninguna"), "label": "Ninguna"},
        {"name": slugify_name("Primaria incompleta"), "label": "Primaria incompleta"},
        {"name": slugify_name("Primaria completa"), "label": "Primaria completa"},
        {"name": slugify_name("Secundaria incompleta"), "label": "Secundaria incompleta"},
        {"name": slugify_name("Secundaria completa"), "label": "Secundaria completa"},
        {"name": slugify_name("Técnico"), "label": "Técnico"},
        {"name": slugify_name("Universitaria incompleta"), "label": "Universitaria incompleta"},
        {"name": slugify_name("Universitaria completa"), "label": "Universitaria completa"},
    ]

    cb["relacion_zona"] = [
        {"name": slugify_name("Vivo en la zona"), "label": "Vivo en la zona"},
        {"name": slugify_name("Trabajo en la zona"), "label": "Trabajo en la zona"},
        {"name": slugify_name("Visito la zona"), "label": "Visito la zona"},
        {"name": slugify_name("Estudio en la zona"), "label": "Estudio en la zona"},
    ]

    cb["seguridad_5"] = [
        {"name": slugify_name("Muy inseguro"), "label": "Muy inseguro"},
        {"name": slugify_name("Inseguro"), "label": "Inseguro"},
        {"name": slugify_name("Ni seguro ni inseguro"), "label": "Ni seguro ni inseguro"},
        {"name": slugify_name("Seguro"), "label": "Seguro"},
        {"name": slugify_name("Muy seguro"), "label": "Muy seguro"},
    ]

    cb["escala_1_5"] = [
        {"name": slugify_name("1 (Mucho Menos Seguro)"), "label": "1 (Mucho Menos Seguro)"},
        {"name": slugify_name("2 (Menos Seguro)"), "label": "2 (Menos Seguro)"},
        {"name": slugify_name("3 (Se mantiene igual)"), "label": "3 (Se mantiene igual)"},
        {"name": slugify_name("4 (Más Seguro)"), "label": "4 (Más Seguro)"},
        {"name": slugify_name("5 (Mucho Más Seguro)"), "label": "5 (Mucho Más Seguro)"},
    ]

    cb["matriz_1_5_na"] = [
        {"name": slugify_name("Muy inseguro (1)"), "label": "Muy inseguro (1)"},
        {"name": slugify_name("Inseguro (2)"), "label": "Inseguro (2)"},
        {"name": slugify_name("Ni seguro ni inseguro (3)"), "label": "Ni seguro ni inseguro (3)"},
        {"name": slugify_name("Seguro (4)"), "label": "Seguro (4)"},
        {"name": slugify_name("Muy seguro (5)"), "label": "Muy seguro (5)"},
        {"name": slugify_name("No aplica"), "label": "No aplica"},
    ]

    cb["escala_1_10"] = [{"name": str(i), "label": str(i)} for i in range(1, 11)]

    # --- Listas del formulario (ejemplos; el resto se mantiene y puede ampliarse en Parte 8)
    cb["p38_frecuencia"] = [
        {"name": slugify_name("Todos los días"), "label": "Todos los días"},
        {"name": slugify_name("Varias veces por semana"), "label": "Varias veces por semana"},
        {"name": slugify_name("Una vez por semana"), "label": "Una vez por semana"},
        {"name": slugify_name("Casi nunca"), "label": "Casi nunca"},
        {"name": slugify_name("Nunca"), "label": "Nunca"},
    ]

    cb["p39_si_no_aveces"] = [
        {"name": slugify_name("Sí"), "label": "Sí"},
        {"name": slugify_name("No"), "label": "No"},
        {"name": slugify_name("A veces"), "label": "A veces"},
    ]

    cb["p41_opciones"] = [
        {"name": slugify_name("Sí"), "label": "Sí"},
        {"name": slugify_name("No"), "label": "No"},
        {"name": slugify_name("No estoy seguro(a)"), "label": "No estoy seguro(a)"},
    ]

    # ======================================================================================
    # LISTAS OBLIGATORIAS PARA EVITAR ERROR "list_canton not in choices sheet"
    # - Aunque el usuario no cargue catálogo, existen como placeholder mínimo.
    # ======================================================================================
    cb["list_canton"] = [{"name": "sin_catalogo", "label": "Sin catálogo (agregar cantones en Catálogo)"}]
    cb["list_distrito"] = [{"name": "sin_catalogo", "label": "Sin catálogo (agregar distritos en Catálogo)", "canton_key": "sin_catalogo"}]

    st.session_state.choices_bank = cb

def _ensure_mandatory_choice_lists():
    """
    Garantiza que siempre existan list_canton y list_distrito para export/ArcGIS.
    """
    cb = st.session_state.choices_bank

    if "list_canton" not in cb or not isinstance(cb.get("list_canton"), list) or len(cb.get("list_canton")) == 0:
        cb["list_canton"] = [{"name": "sin_catalogo", "label": "Sin catálogo (agregar cantones en Catálogo)"}]

    if "list_distrito" not in cb or not isinstance(cb.get("list_distrito"), list) or len(cb.get("list_distrito")) == 0:
        cb["list_distrito"] = [{"name": "sin_catalogo", "label": "Sin catálogo (agregar distritos en Catálogo)", "canton_key": "sin_catalogo"}]

    st.session_state.choices_bank = cb

def _normalize_choice_rows(list_name: str, rows: list[dict]) -> list[dict]:
    """
    Normaliza filas asegurando columnas mínimas:
    - name, label
    - extras (ej. canton_key)
    """
    out = []
    for r in rows or []:
        rr = dict(r or {})
        rr.setdefault("name", "")
        rr.setdefault("label", "")
        if list_name == "list_distrito":
            rr.setdefault("canton_key", "")
        out.append(rr)
    return out

def _validate_choices_unique_names(list_name: str, rows: list[dict]) -> tuple[bool, str]:
    """
    Valida:
    - name no vacío
    - no duplicados en name
    """
    seen = set()
    for i, r in enumerate(rows, start=1):
        nm = str(r.get("name", "")).strip()
        lb = str(r.get("label", "")).strip()
        if not nm:
            return False, f"Fila {i}: 'name' está vacío."
        if not lb:
            return False, f"Fila {i}: 'label' está vacío."
        if nm in seen:
            return False, f"Duplicado en 'name': {nm}"
        seen.add(nm)
    return True, "OK"

def _make_name_from_label(label: str) -> str:
    return slugify_name(label.strip()) or "opcion"

# Seed inicial
_seed_choices_bank_minimo()
_ensure_mandatory_choice_lists()

# ==========================================================================================
# 2) UI: Tab "Choices"
# ==========================================================================================
if active_tab == "Choices":
    st.header("🧩 Editor de listas (choices) — fácil y legible")

    cb = st.session_state.choices_bank
    all_lists = sorted(cb.keys())

    top1, top2 = st.columns([2, 1], vertical_alignment="center")

    with top1:
        list_sel = st.selectbox("Lista", options=all_lists, index=0, key="choices_list_sel")

    with top2:
        st.caption("Crear lista nueva")
        new_list_name = st.text_input("Nombre de lista (list_name)", value="", key="new_list_name")
        if st.button("➕ Crear lista", use_container_width=True, key="btn_new_list"):
            nl = new_list_name.strip()
            if not nl:
                st.error("Indica un nombre de lista.")
            elif nl in cb:
                st.error("Esa lista ya existe.")
            else:
                cb[nl] = [{"name": "opcion_1", "label": "Opción 1"}]
                st.session_state.choices_bank = cb
                st.success("Lista creada.")
                st.rerun()

    st.markdown("---")

    rows = _normalize_choice_rows(list_sel, cb.get(list_sel, []))

    # Mostrar ayuda especial para distrito
    if list_sel == "list_distrito":
        st.info("📌 Esta lista usa la columna adicional **canton_key** para el choice_filter (cascada Cantón→Distrito).")

    # Tabla editable (más “humana” que Excel)
    df = pd.DataFrame(rows)

    # Asegurar columnas visibles ordenadas
    if list_sel == "list_distrito":
        df = df[[c for c in ["name", "label", "canton_key"] if c in df.columns]]
    else:
        df = df[[c for c in ["name", "label"] if c in df.columns]]

    st.subheader("Opciones de la lista (editable)")

    edited = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",
        key=f"de_choices_{list_sel}",
        hide_index=True
    )

    # Controles para ayudar a usuarios no técnicos
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("✨ Autogenerar 'name' desde 'label'", use_container_width=True, key=f"btn_autoname_{list_sel}"):
            ed2 = edited.copy()
            for i in range(len(ed2)):
                lab = str(ed2.loc[i, "label"]) if "label" in ed2.columns else ""
                nm = str(ed2.loc[i, "name"]) if "name" in ed2.columns else ""
                if (not str(nm).strip()) and str(lab).strip():
                    ed2.loc[i, "name"] = _make_name_from_label(str(lab))
            st.session_state[f"de_choices_{list_sel}"] = ed2
            st.success("Listo. Ahora guarda.")
            st.rerun()

    with c2:
        if st.button("➕ Agregar opción rápida", use_container_width=True, key=f"btn_quickadd_{list_sel}"):
            ed2 = edited.copy()
            # agrega una fila al final
            next_n = len(ed2) + 1
            row_new = {"name": f"opcion_{next_n}", "label": f"Opción {next_n}"}
            if list_sel == "list_distrito":
                row_new["canton_key"] = ""
            ed2 = pd.concat([ed2, pd.DataFrame([row_new])], ignore_index=True)
            st.session_state[f"de_choices_{list_sel}"] = ed2
            st.rerun()

    with c3:
        if st.button("🧹 Limpiar filas vacías", use_container_width=True, key=f"btn_clean_{list_sel}"):
            ed2 = edited.copy()
            if "name" in ed2.columns:
                ed2 = ed2[ed2["name"].astype(str).str.strip() != ""]
            if "label" in ed2.columns:
                ed2 = ed2[ed2["label"].astype(str).str.strip() != ""]
            ed2 = ed2.reset_index(drop=True)
            st.session_state[f"de_choices_{list_sel}"] = ed2
            st.rerun()

    with c4:
        if st.button("💾 Guardar lista", use_container_width=True, key=f"btn_save_{list_sel}"):
            # Convertir DataFrame a lista de dict
            out_rows = []
            for _, rr in edited.iterrows():
                rdict = {k: ("" if pd.isna(v) else str(v)) for k, v in rr.to_dict().items()}
                # Trim
                for k in rdict:
                    rdict[k] = str(rdict[k]).strip()
                out_rows.append(rdict)

            ok, msg = _validate_choices_unique_names(list_sel, out_rows)
            if not ok:
                st.error(msg)
            else:
                # Guardar
                cb[list_sel] = _normalize_choice_rows(list_sel, out_rows)
                st.session_state.choices_bank = cb
                _ensure_mandatory_choice_lists()
                st.success("Lista guardada.")

    st.markdown("---")

    # Zona de administración (renombrar / eliminar)
    with st.expander("⚙️ Administración de listas (avanzado)", expanded=False):
        st.caption("Recomendación: no elimines yesno ni list_canton/list_distrito.")
        colA, colB = st.columns(2)

        with colA:
            rename_to = st.text_input("Renombrar lista a:", value="", key=f"rename_{list_sel}")
            if st.button("🔁 Renombrar", use_container_width=True, key=f"btn_rename_{list_sel}"):
                rt = rename_to.strip()
                if not rt:
                    st.error("Indica el nuevo nombre.")
                elif rt in cb:
                    st.error("Ya existe una lista con ese nombre.")
                elif list_sel in ["yesno", "list_canton", "list_distrito"]:
                    st.error("Esa lista está protegida.")
                else:
                    cb[rt] = cb.pop(list_sel)
                    st.session_state.choices_bank = cb
                    st.success("Renombrada.")
                    st.rerun()

        with colB:
            if st.button("🗑️ Eliminar lista", use_container_width=True, key=f"btn_delete_{list_sel}"):
                if list_sel in ["yesno", "list_canton", "list_distrito"]:
                    st.error("No se puede eliminar esta lista (protegida).")
                else:
                    cb.pop(list_sel, None)
                    st.session_state.choices_bank = cb
                    _ensure_mandatory_choice_lists()
                    st.success("Eliminada.")
                    st.rerun()

# ==========================================================================================
# FIN PARTE 4/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 5/10) ==============================
# ===================== Editor de GLOSARIO — agregar términos + asignar por página =========
# ==========================================================================================
#
# PARTE 5/10 (ACTUALIZADA)
# ✅ Soluciona tu bug de “agrego Arrebato pero NO aparece en orden/vista previa”
#    - Ahora el glosario tiene 2 cosas separadas:
#      1) Definiciones (diccionario global): término -> significado
#      2) Asignación por página: qué términos salen en P4, P5, P6, etc.
#    - Si agregás un término nuevo (ej. “Arrebato”), queda en definiciones globales
#      y automáticamente ya es seleccionable en cualquier página.
#    - La vista previa y el “orden (uno por línea)” se alimentan del estado guardado
#      (no de una lista “por defecto”), por eso SIEMPRE refleja lo que asignás.
#
# ✅ Diseño “fácil” (no Excel):
#    - Seleccionás Página
#    - Elegís términos en multiselect
#    - Podés definir el orden pegando uno por línea
#    - Guardás y ves la vista previa legible
#
# REQUISITOS:
# - Ya existen: slugify_name, st, pd
# - Debe existir `active_tab` (radio/menú superior) como en partes anteriores
# ==========================================================================================

# ==========================================================================================
# 1) Estado: glosario global + asignaciones por página
# ==========================================================================================
if "glossary_definitions" not in st.session_state:
    # Definiciones base (las mismas que tenías en tu código original)
    st.session_state.glossary_definitions = {
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

if "glossary_by_page" not in st.session_state:
    # Asignación inicial (como en tu código original, pero editable)
    st.session_state.glossary_by_page = {
        "p4": ["Extorsión", "Daños/vandalismo"],
        "p5": ["Búnkeres", "Receptación", "Contrabando", "Trata de personas", "Explotación infantil", "Acoso callejero", "Tráfico de personas (coyotaje)", "Estafa", "Tacha"],
        "p6": ["Receptación", "Contrabando", "Tráfico de personas (coyotaje)", "Acoso callejero", "Estafa", "Tacha", "Trata de personas", "Explotación infantil", "Extorsión", "Búnkeres"],
        "p7": ["Ganzúa (pata de chancho)", "Boquete", "Arrebato", "Receptación", "Extorsión"],
        "p8": ["Patrullaje", "Acciones disuasivas", "Coordinación interinstitucional", "Integridad y credibilidad policial"],
    }

if "glossary_order_by_page" not in st.session_state:
    # Orden opcional (si el usuario pega “uno por línea”, se guarda aquí)
    st.session_state.glossary_order_by_page = {
        # "p5": ["Búnkeres", "Receptación", ...]
    }

# ==========================================================================================
# 2) Helpers glosario
# ==========================================================================================
def _all_glossary_terms_sorted() -> list[str]:
    terms = list(st.session_state.glossary_definitions.keys())
    terms = [t for t in terms if str(t).strip() != ""]
    return sorted(terms, key=lambda x: x.lower())

def _page_list_for_glossary() -> list[tuple[str, str]]:
    """
    Devuelve lista de páginas (id, label).
    Si tu app ya tiene un catálogo global de páginas, úsalo.
    Si no, usa estas páginas del formulario.
    """
    # Si en otras partes ya definiste un catálogo de páginas, se respeta.
    pages_meta = st.session_state.get("pages_meta")
    if isinstance(pages_meta, list) and pages_meta:
        # Espera formato: [{"id":"p1", "label":"P1 Introducción"}, ...]
        out = []
        for p in pages_meta:
            pid = str(p.get("id", "")).strip()
            plb = str(p.get("label", pid)).strip()
            if pid:
                out.append((pid, plb))
        if out:
            return out

    # Fallback estable:
    return [
        ("p1", "P1 Introducción"),
        ("p2", "P2 Consentimiento"),
        ("p3", "P3 Demográficos"),
        ("p4", "P4 Percepción"),
        ("p5", "P5 Riesgos"),
        ("p6", "P6 Delitos"),
        ("p7", "P7 Victimización"),
        ("p8", "P8 Confianza/Acciones"),
    ]

def _get_terms_for_page(page_id: str) -> list[str]:
    assigned = st.session_state.glossary_by_page.get(page_id, [])
    assigned = [t for t in assigned if t in st.session_state.glossary_definitions]
    return assigned

def _get_order_for_page(page_id: str, assigned_terms: list[str]) -> list[str]:
    """
    Orden final para vista previa:
    - Si hay orden manual guardado, se usa (filtrando términos inexistentes)
    - Si no, se usa el orden de asignación
    """
    manual = st.session_state.glossary_order_by_page.get(page_id)
    if isinstance(manual, list) and manual:
        final = [t for t in manual if t in assigned_terms]
        # Añadir al final los asignados que no estén en manual
        for t in assigned_terms:
            if t not in final:
                final.append(t)
        return final
    return assigned_terms

def _parse_order_lines(text_area_value: str) -> list[str]:
    """
    Convierte el text area (uno por línea) a lista de términos.
    Mantiene el texto exacto, pero limpia vacíos.
    """
    lines = [ln.strip() for ln in (text_area_value or "").splitlines()]
    return [ln for ln in lines if ln]

def _save_page_glossary(page_id: str, selected_terms: list[str], order_lines: list[str]):
    # Guardar asignación
    st.session_state.glossary_by_page[page_id] = list(selected_terms)

    # Guardar orden opcional solo si el usuario escribió algo
    if order_lines:
        st.session_state.glossary_order_by_page[page_id] = list(order_lines)
    else:
        # si dejó vacío, elimina orden manual para usar “orden de asignación”
        if page_id in st.session_state.glossary_order_by_page:
            st.session_state.glossary_order_by_page.pop(page_id, None)

# ==========================================================================================
# 3) UI: Tab "Glosario"
# ==========================================================================================
if active_tab == "Glosario":
    st.header("📚 Glosario — términos + significado + asignación por página")

    defs = st.session_state.glossary_definitions

    # ------------------------------------------------------------------------------
    # 3.1 Agregar/editar definiciones (global)
    # ------------------------------------------------------------------------------
    with st.expander("➕ Agregar o editar un término (definición global)", expanded=False):
        colA, colB = st.columns([1, 2], vertical_alignment="top")
        with colA:
            term_input = st.text_input("Término", value="", key="gl_term_input")
        with colB:
            def_input = st.text_area("Significado (definición)", value="", height=120, key="gl_def_input")

        colC, colD, colE = st.columns([1, 1, 2])
        with colC:
            if st.button("💾 Guardar término", use_container_width=True, key="gl_save_term"):
                t = (term_input or "").strip()
                d = (def_input or "").strip()
                if not t:
                    st.error("El término no puede ir vacío.")
                elif not d:
                    st.error("La definición no puede ir vacía.")
                else:
                    defs[t] = d
                    st.session_state.glossary_definitions = defs
                    st.success("Término guardado. Ya está disponible para asignarlo a páginas.")
                    st.rerun()

        with colD:
            if st.button("🧹 Limpiar", use_container_width=True, key="gl_clear_term"):
                st.session_state.gl_term_input = ""
                st.session_state.gl_def_input = ""
                st.rerun()

        with colE:
            st.caption("Tip: si agregás un término nuevo (ej. **Arrebato**), luego lo asignás en la sección de abajo.")

    st.markdown("---")

    # ------------------------------------------------------------------------------
    # 3.2 Asignación de términos por página + orden (uno por línea)
    # ------------------------------------------------------------------------------
    pages = _page_list_for_glossary()
    page_ids = [p[0] for p in pages]
    page_labels = [p[1] for p in pages]

    left, right = st.columns([1, 1], vertical_alignment="top")

    with left:
        page_sel_label = st.selectbox(
            "Página",
            options=page_labels,
            index=page_labels.index("P5 Riesgos") if "P5 Riesgos" in page_labels else 0,
            key="gl_page_sel"
        )
        page_sel = page_ids[page_labels.index(page_sel_label)]

        assigned_now = _get_terms_for_page(page_sel)
        all_terms = _all_glossary_terms_sorted()

        selected_terms = st.multiselect(
            "Términos incluidos en el glosario de esta página",
            options=all_terms,
            default=assigned_now,
            key=f"gl_terms_{page_sel}"
        )

        # Mostrar orden actual (si hay orden guardado, se imprime; si no, usa el orden de asignación)
        current_order = _get_order_for_page(page_sel, selected_terms)
        default_text_area = "\n".join(current_order) if current_order else ""

        st.caption("Orden del glosario (opcional). Si quieres ordenar manualmente, pega la lista en el orden deseado:")
        order_text = st.text_area(
            "Orden (uno por línea)",
            value=default_text_area,
            height=140,
            key=f"gl_order_{page_sel}"
        )

        colS1, colS2 = st.columns(2)
        with colS1:
            if st.button("💾 Guardar asignación", use_container_width=True, key=f"gl_save_page_{page_sel}"):
                # Parsear orden manual
                order_lines = _parse_order_lines(order_text)

                # Filtrar orden: solo términos realmente seleccionados y existentes
                order_lines = [t for t in order_lines if t in selected_terms]

                _save_page_glossary(page_sel, selected_terms, order_lines)
                st.success("Asignación guardada.")
                st.rerun()

        with colS2:
            if st.button("🧽 Limpiar página", use_container_width=True, key=f"gl_clear_page_{page_sel}"):
                st.session_state.glossary_by_page[page_sel] = []
                st.session_state.glossary_order_by_page.pop(page_sel, None)
                st.success("Página limpiada (sin glosario).")
                st.rerun()

    with right:
        st.subheader("👁️ Vista previa del glosario de esta página")

        preview_terms = _get_terms_for_page(page_sel)
        # Si el usuario todavía no guardó, usar el estado actual de selección para previsualizar
        preview_terms = selected_terms if selected_terms is not None else preview_terms

        final_order = _get_order_for_page(page_sel, preview_terms)

        if not final_order:
            st.info("Esta página no tiene términos asignados.")
        else:
            # Render legible
            for t in final_order:
                st.markdown(f"**{t}**")
                st.write(defs.get(t, "⚠️ No hay definición registrada para este término."))
                st.markdown("---")

    st.markdown("---")

    # ------------------------------------------------------------------------------
    # 3.3 Tabla rápida de términos (para que sea “editable por cualquiera”)
    # ------------------------------------------------------------------------------
    with st.expander("📋 Ver/editar todas las definiciones (tabla)", expanded=False):
        df_defs = pd.DataFrame(
            [{"Término": k, "Definición": v} for k, v in st.session_state.glossary_definitions.items()]
        ).sort_values("Término", key=lambda s: s.str.lower(), ignore_index=True)

        edited_defs = st.data_editor(
            df_defs,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="gl_defs_table"
        )

        colT1, colT2 = st.columns(2)
        with colT1:
            if st.button("💾 Guardar tabla de definiciones", use_container_width=True, key="gl_save_table"):
                new_defs = {}
                for _, rr in edited_defs.iterrows():
                    term = str(rr.get("Término", "")).strip()
                    defi = str(rr.get("Definición", "")).strip()
                    if term and defi:
                        new_defs[term] = defi

                if not new_defs:
                    st.error("La tabla quedó vacía o sin datos válidos.")
                else:
                    st.session_state.glossary_definitions = new_defs

                    # Limpieza: eliminar asignaciones a términos que ya no existen
                    for pid, terms in list(st.session_state.glossary_by_page.items()):
                        st.session_state.glossary_by_page[pid] = [t for t in terms if t in new_defs]
                    for pid, terms in list(st.session_state.glossary_order_by_page.items()):
                        st.session_state.glossary_order_by_page[pid] = [t for t in terms if t in new_defs]

                    st.success("Definiciones guardadas.")
                    st.rerun()

        with colT2:
            st.caption("Consejo: no borres términos que ya están asignados, a menos que también quieras quitarlos de páginas.")

# ==========================================================================================
# FIN PARTE 5/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 6/10) ==============================
# ===================== Editor de PREGUNTAS (survey) — por páginas, legible, editable ======
# ==========================================================================================
#
# PARTE 6/10 (ACTUALIZADA)
# ✅ Arregla tu problema de la “imagen 2”: después de P5 ya NO aparecen preguntas para editar.
#    Causa típica: el editor estaba “leyendo” páginas solo hasta donde encontraba cierto patrón,
#    o no estaba reconstruyendo el índice de páginas (begin_group/end_group) correctamente.
#
# SOLUCIÓN AQUÍ:
# - Se mantiene un “banco” de preguntas (survey_bank) como lista de filas tipo XLSForm.
# - Se construye un índice de páginas usando begin_group con appearance="field-list"
# - Se mapea cada fila a su página actual (p1..p8)
# - El editor SIEMPRE muestra todas las páginas encontradas (incluyendo p6/p7/p8)
# - Permite: editar, mover, eliminar, agregar preguntas, y agregar condicionales (relevant)
#
# DISEÑO “para cualquiera”:
# - Seleccionás la página (P4, P5, P6…)
# - Ves la lista de preguntas como “tarjetas”
# - Seleccionás una pregunta → panel de edición fácil (tipo, texto, requerido, relevant, etc.)
# - Botones: subir/bajar, duplicar, eliminar
#
# REQUISITOS:
# - Ya existen: slugify_name, asegurar_nombre_unico (de tus helpers), st, pd
# - Existe `active_tab` y debe incluir una opción tipo "Preguntas" (o similar)
#
# NOTA:
# - Este editor modifica `st.session_state.survey_bank`
# - La exportación final a XLSForm se hará en Parte 8/10 usando survey_bank + choices_bank + glosario
# ==========================================================================================

# ==========================================================================================
# 1) Estado: survey_bank (banco editable de filas survey)
# ==========================================================================================
if "survey_bank" not in st.session_state:
    st.session_state.survey_bank = []  # list[dict]

def _seed_survey_bank_minimo_si_vacio(form_title: str, logo_media_name: str):
    """
    Si survey_bank está vacío, lo llena con una versión base equivalente a tu formulario.
    IMPORTANTE: NO omite páginas P1..P8.
    """
    if st.session_state.survey_bank:
        return

    # Plantilla mínima con páginas (begin/end) + algunas preguntas clave
    # (En Parte 8/10 vamos a reconstruir TODO el survey final a partir del banco completo.)
    bank = []

    def add_row(r: dict):
        bank.append(r)

    # P1
    add_row({"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"})
    add_row({"type": "note", "name": "p1_logo", "label": form_title, "media::image": logo_media_name, "bind::esri:fieldType": "null"})
    add_row({"type": "note", "name": "p1_texto", "label": INTRO_COMUNIDAD_EXACTA, "bind::esri:fieldType": "null"})
    add_row({"type": "end_group", "name": "p1_end"})

    # P2
    add_row({"type": "begin_group", "name": "p2_consent", "label": "Consentimiento Informado", "appearance": "field-list"})
    add_row({"type": "note", "name": "p2_titulo", "label": CONSENT_TITLE, "bind::esri:fieldType": "null"})
    add_row({"type": "select_one yesno", "name": "acepta_participar", "label": "¿Acepta participar en esta encuesta?", "required": "yes", "appearance": "minimal"})
    add_row({"type": "end_group", "name": "p2_end"})
    add_row({"type": "end", "name": "fin_por_no", "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.", "relevant": f"${{acepta_participar}}='{slugify_name('No')}'"})

    # P3
    rel_si = f"${{acepta_participar}}='{slugify_name('Sí')}'"
    add_row({"type": "begin_group", "name": "p3_datos_demograficos", "label": "Datos demográficos", "appearance": "field-list", "relevant": rel_si})
    add_row({"type": "select_one list_canton", "name": "canton", "label": "1. Cantón:", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row({"type": "select_one list_distrito", "name": "distrito", "label": "2. Distrito:", "required": "yes", "appearance": "minimal",
             "choice_filter": "canton_key=${canton}", "relevant": f"({rel_si}) and string-length(${{canton}}) > 0"})
    add_row({"type": "integer", "name": "edad_anos", "label": "3. Edad:", "required": "yes", "constraint": ". >= 18 and . <= 120",
             "constraint_message": "Debe ser un número entre 18 y 120.", "relevant": rel_si})
    add_row({"type": "end_group", "name": "p3_end"})

    # P4
    add_row({"type": "begin_group", "name": "p4_percepcion_distrito", "label": "Percepción ciudadana de seguridad en el distrito", "appearance": "field-list", "relevant": rel_si})
    add_row({"type": "select_one seguridad_5", "name": "p7_seguridad_distrito", "label": "7. ¿Qué tan seguro percibe usted el distrito donde reside o transita?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row({"type": "end_group", "name": "p4_end"})

    # P5
    add_row({"type": "begin_group", "name": "p5_riesgos", "label": "III. RIESGOS, DELITOS, VICTIMIZACIÓN Y EVALUACIÓN POLICIAL", "appearance": "field-list", "relevant": rel_si})
    add_row({"type": "select_multiple p12_prob_situacionales", "name": "p12_problematicas_distrito", "label": "12. Según su percepción u observación, seleccione las problemáticas que afectan su distrito:", "required": "yes", "relevant": rel_si})
    add_row({"type": "end_group", "name": "p5_end"})

    # P6 (Delitos)
    add_row({"type": "begin_group", "name": "p6_delitos", "label": "Delitos", "appearance": "field-list", "relevant": rel_si})
    add_row({"type": "note", "name": "p6_intro", "label": "A continuación, se presentará una lista de delitos y situaciones delictivas...", "bind::esri:fieldType": "null", "relevant": rel_si})
    add_row({"type": "select_multiple p19_delitos_general", "name": "p19_delitos_general", "label": "19. Selección múltiple de los siguientes delitos:", "required": "yes", "relevant": rel_si})
    add_row({"type": "end_group", "name": "p6_end"})

    # P7 (Victimización)
    add_row({"type": "begin_group", "name": "p7_victimizacion", "label": "Victimización", "appearance": "field-list", "relevant": rel_si})
    add_row({"type": "select_one p30_vif", "name": "p30_vif", "label": "30. Durante el último año, ¿usted o algún miembro de su hogar ha sido afectado por violencia intrafamiliar?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row({"type": "end_group", "name": "p7_end"})

    # P8 (Confianza)
    add_row({"type": "begin_group", "name": "p8_confianza_policial", "label": "Confianza Policial", "appearance": "field-list", "relevant": rel_si})
    add_row({"type": "select_one escala_1_10", "name": "p33_confianza_policial", "label": "33. ¿Cuál es el nivel de confianza en la policía... (1-10)?", "required": "yes", "appearance": "minimal", "relevant": rel_si})
    add_row({"type": "end_group", "name": "p8_end"})

    st.session_state.survey_bank = bank

_seed_survey_bank_minimo_si_vacio(form_title=form_title, logo_media_name=logo_media_name)

# ==========================================================================================
# 2) Helpers: indexar páginas y filas editables
# ==========================================================================================
def _is_page_begin(row: dict) -> bool:
    return str(row.get("type", "")).strip() == "begin_group" and str(row.get("appearance", "")).strip() == "field-list"

def _is_group_end(row: dict) -> bool:
    return str(row.get("type", "")).strip() == "end_group"

def _extract_page_id_from_name(name: str) -> str:
    """
    Convención: begin_group name empieza por p1_, p2_, p3_, etc.
    Si no, intenta inferir.
    """
    n = (name or "").strip().lower()
    for pid in ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]:
        if n.startswith(pid + "_") or n == pid:
            return pid
    # fallback: si no calza, usa "otros"
    return "otros"

def _page_label(pid: str) -> str:
    mapping = {
        "p1": "P1 Introducción",
        "p2": "P2 Consentimiento",
        "p3": "P3 Demográficos",
        "p4": "P4 Percepción",
        "p5": "P5 Riesgos",
        "p6": "P6 Delitos",
        "p7": "P7 Victimización",
        "p8": "P8 Confianza/Acciones",
        "otros": "Otros (sin página)",
    }
    return mapping.get(pid, pid)

def _index_pages(bank: list[dict]) -> dict:
    """
    Retorna un dict:
    {
      "p5": {"start": idx_begin, "end": idx_end, "label": "..."},
      ...
    }
    Garantiza que p1..p8 existan aunque el banco esté raro (crea “virtual” si no existen).
    """
    pages = {}
    stack = []  # (pid, begin_idx)

    for i, row in enumerate(bank):
        if _is_page_begin(row):
            pid = _extract_page_id_from_name(str(row.get("name", "")))
            stack.append((pid, i))
        elif _is_group_end(row) and stack:
            pid, begin_idx = stack.pop()
            pages[pid] = {"start": begin_idx, "end": i, "label": _page_label(pid)}

    # asegurar p1..p8 aunque falte alguna
    for pid in ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]:
        if pid not in pages:
            pages[pid] = {"start": None, "end": None, "label": _page_label(pid)}

    return pages

def _rows_in_page(bank: list[dict], page_meta: dict, pid: str) -> list[int]:
    """
    Devuelve índices de filas que pertenecen a la página pid (entre begin_group y end_group),
    excluyendo el begin/end del grupo.
    """
    info = page_meta.get(pid, {})
    s, e = info.get("start"), info.get("end")
    if s is None or e is None:
        return []
    idxs = list(range(s + 1, e))  # dentro del grupo
    return idxs

def _is_editable_question(row: dict) -> bool:
    """
    Define qué filas editamos como “preguntas”:
    - Excluye begin_group/end_group
    - Excluye end
    """
    t = str(row.get("type", "")).strip()
    if t in ["begin_group", "end_group"]:
        return False
    if t == "end":
        return False
    # todo lo demás lo dejamos editable (note, select_one, integer, text, select_multiple, etc.)
    return True

def _safe_get(bank: list[dict], idx: int) -> dict:
    if idx < 0 or idx >= len(bank):
        return {}
    return bank[idx]

def _safe_set(bank: list[dict], idx: int, new_row: dict):
    if 0 <= idx < len(bank):
        bank[idx] = dict(new_row)

def _move_row(bank: list[dict], idx_from: int, idx_to: int):
    """
    Mueve una fila dentro del banco.
    """
    if idx_from == idx_to:
        return
    if idx_from < 0 or idx_from >= len(bank):
        return
    if idx_to < 0 or idx_to >= len(bank):
        return
    row = bank.pop(idx_from)
    bank.insert(idx_to, row)

def _unique_question_name(bank: list[dict], desired: str) -> str:
    usados = set(str(r.get("name", "")).strip() for r in bank if str(r.get("name", "")).strip())
    base = slugify_name(desired) if desired else "pregunta"
    return asegurar_nombre_unico(base, usados)

# ==========================================================================================
# 3) UI: Tab "Preguntas"
# ==========================================================================================
if active_tab == "Preguntas":
    st.header("📝 Editor de preguntas (survey) — por página")

    bank = st.session_state.survey_bank
    pages = _index_pages(bank)

    # Selector de página
    page_opts = [pages[p]["label"] for p in ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]]
    page_map = {pages[p]["label"]: p for p in ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]}

    default_label = "P6 Delitos" if "P6 Delitos" in page_map else page_opts[0]
    page_label_sel = st.selectbox("Página", options=page_opts, index=page_opts.index(default_label), key="pg_sel_label")
    pid = page_map[page_label_sel]

    st.markdown("---")

    # Mostrar advertencia si la página no existe físicamente (start/end None)
    if pages[pid]["start"] is None or pages[pid]["end"] is None:
        st.warning(
            "Esta página no está definida en el banco (no se encontró begin_group/end_group). "
            "En Parte 8/10 se reconstruye el XLSForm completo. Si querés, en Parte 7/10 "
            "te doy el editor para crear páginas/bloques."
        )

    idxs_all = _rows_in_page(bank, pages, pid)
    idxs_questions = [i for i in idxs_all if _is_editable_question(_safe_get(bank, i))]

    colL, colR = st.columns([1, 1], vertical_alignment="top")

    # ------------------------------------------------------------------------------
    # 3.1 Panel izquierdo: lista “legible” de preguntas
    # ------------------------------------------------------------------------------
    with colL:
        st.subheader("📄 Preguntas de la página")

        if not idxs_questions:
            st.info("No hay preguntas editables en esta página (o aún no está definida).")
        else:
            # Construir listado legible
            items = []
            for i in idxs_questions:
                r = _safe_get(bank, i)
                t = str(r.get("type", "")).strip()
                nm = str(r.get("name", "")).strip()
                lb = str(r.get("label", "")).strip()
                # Etiqueta corta
                title = lb if lb else nm
                title = title if len(title) <= 90 else title[:90] + "…"
                items.append((i, f"[{t}] {title}"))

            # selector de pregunta
            idx_selected = st.selectbox(
                "Seleccioná una pregunta para editar",
                options=[x[0] for x in items],
                format_func=lambda v: dict(items).get(v, str(v)),
                key="q_sel_idx"
            )

            rsel = _safe_get(bank, idx_selected)

            # Botones de orden
            b1, b2, b3, b4 = st.columns(4)
            with b1:
                if st.button("⬆️ Subir", use_container_width=True, key="btn_up"):
                    # mover dentro de la página: busca el índice anterior editable
                    pos = idxs_questions.index(idx_selected)
                    if pos > 0:
                        prev_idx = idxs_questions[pos - 1]
                        _move_row(bank, idx_selected, prev_idx)
                        st.session_state.survey_bank = bank
                        st.rerun()
            with b2:
                if st.button("⬇️ Bajar", use_container_width=True, key="btn_down"):
                    pos = idxs_questions.index(idx_selected)
                    if pos < len(idxs_questions) - 1:
                        next_idx = idxs_questions[pos + 1]
                        _move_row(bank, idx_selected, next_idx)
                        st.session_state.survey_bank = bank
                        st.rerun()
            with b3:
                if st.button("📄 Duplicar", use_container_width=True, key="btn_dup"):
                    copy_row = dict(rsel)
                    # nombre único
                    copy_row["name"] = _unique_question_name(bank, f"{copy_row.get('name','pregunta')}_copy")
                    bank.insert(idx_selected + 1, copy_row)
                    st.session_state.survey_bank = bank
                    st.rerun()
            with b4:
                if st.button("🗑️ Eliminar", use_container_width=True, key="btn_del"):
                    bank.pop(idx_selected)
                    st.session_state.survey_bank = bank
                    st.rerun()

        st.markdown("---")

        # Agregar pregunta nueva
        st.subheader("➕ Agregar pregunta nueva (fácil)")
        new_type = st.selectbox(
            "Tipo",
            options=[
                "text",
                "integer",
                "note",
                "select_one yesno",
                "select_multiple causas_inseguridad",
            ],
            index=0,
            key="new_q_type"
        )
        new_label = st.text_input("Texto de la pregunta (label)", value="", key="new_q_label")
        new_required = st.selectbox("¿Obligatoria?", options=["no", "yes"], index=0, key="new_q_req")

        if st.button("➕ Insertar al final de la página", use_container_width=True, key="btn_add_q"):
            if pages[pid]["start"] is None or pages[pid]["end"] is None:
                st.error("Esta página no está creada en el banco. En Parte 7/10 agregamos el creador de páginas.")
            else:
                nm = _unique_question_name(bank, new_label or "pregunta")
                row_new = {
                    "type": new_type,
                    "name": nm,
                    "label": new_label.strip() or nm,
                    "required": new_required,
                }
                # notas no crean columna
                if new_type == "note":
                    row_new["bind::esri:fieldType"] = "null"
                # insertar justo antes del end_group
                insert_pos = pages[pid]["end"]
                bank.insert(insert_pos, row_new)
                st.session_state.survey_bank = bank
                st.success("Pregunta agregada.")
                st.rerun()

    # ------------------------------------------------------------------------------
    # 3.2 Panel derecho: editor de la pregunta seleccionada
    # ------------------------------------------------------------------------------
    with colR:
        st.subheader("🛠️ Editor de la pregunta seleccionada")

        if not idxs_questions:
            st.info("Seleccioná una página con preguntas o agregá una nueva.")
        else:
            idx_selected = st.session_state.get("q_sel_idx", idxs_questions[0])
            row = dict(_safe_get(bank, idx_selected))

            # Campos básicos, legibles para cualquiera
            t = st.text_input("type", value=str(row.get("type", "")), key="edit_type")
            nm = st.text_input("name (ID interno)", value=str(row.get("name", "")), key="edit_name")
            lb = st.text_area("label (texto visible)", value=str(row.get("label", "")), height=120, key="edit_label")

            c1, c2 = st.columns(2)
            with c1:
                req = st.selectbox("required", options=["", "no", "yes"], index=["", "no", "yes"].index(str(row.get("required", "") or "")), key="edit_required")
            with c2:
                app = st.text_input("appearance (opcional)", value=str(row.get("appearance", "")), key="edit_appearance")

            relevant = st.text_input("relevant (condicional) — opcional", value=str(row.get("relevant", "")), key="edit_relevant")
            choice_filter = st.text_input("choice_filter (cascadas) — opcional", value=str(row.get("choice_filter", "")), key="edit_choice_filter")

            constraint = st.text_input("constraint — opcional", value=str(row.get("constraint", "")), key="edit_constraint")
            constraint_message = st.text_input("constraint_message — opcional", value=str(row.get("constraint_message", "")), key="edit_constraint_msg")

            media_image = st.text_input("media::image — opcional", value=str(row.get("media::image", "")), key="edit_media_image")
            esri_null = st.selectbox(
                "¿Es nota sin columna? (bind::esri:fieldType)",
                options=["", "null"],
                index=0 if str(row.get("bind::esri:fieldType", "")).strip() == "" else 1,
                key="edit_esri_null"
            )

            st.markdown("---")

            # Guardar cambios
            if st.button("💾 Guardar cambios de esta pregunta", use_container_width=True, key="btn_save_row"):
                # nombre único si cambió
                desired_name = nm.strip()
                if not desired_name:
                    desired_name = _unique_question_name(bank, lb.strip() or "pregunta")

                # Si el usuario cambió el name a uno ya existente, forzar único
                usados = set(str(r.get("name", "")).strip() for i, r in enumerate(bank) if i != idx_selected)
                if desired_name in usados:
                    desired_name = _unique_question_name(bank, desired_name)

                new_row = dict(row)
                new_row["type"] = t.strip()
                new_row["name"] = desired_name
                new_row["label"] = lb
                new_row["required"] = req
                new_row["appearance"] = app.strip()
                new_row["relevant"] = relevant.strip()
                new_row["choice_filter"] = choice_filter.strip()
                new_row["constraint"] = constraint.strip()
                new_row["constraint_message"] = constraint_message.strip()
                new_row["media::image"] = media_image.strip()

                # Nota sin columna
                if esri_null == "null":
                    new_row["bind::esri:fieldType"] = "null"
                else:
                    if "bind::esri:fieldType" in new_row:
                        new_row.pop("bind::esri:fieldType", None)

                _safe_set(bank, idx_selected, new_row)
                st.session_state.survey_bank = bank
                st.success("Pregunta actualizada.")
                st.rerun()

            # Vista previa legible
            st.markdown("---")
            st.subheader("👁️ Vista previa (como la vería una persona)")
            preview_title = str(row.get("label", "")).strip() or str(row.get("name", "")).strip()
            st.markdown(f"**{preview_title}**")
            st.caption(f"type: {row.get('type','')} | name: {row.get('name','')} | required: {row.get('required','')}")
            if str(row.get("relevant", "")).strip():
                st.caption(f"Condición (relevant): {row.get('relevant')}")

# ==========================================================================================
# FIN PARTE 6/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 7/10) ==============================
# ===================== Gestor de PÁGINAS (begin_group/end_group) + vista árbol ============
# ==========================================================================================
#
# PARTE 7/10 (ACTUALIZADA)
# ✅ Complementa la Parte 6:
#    - Si alguna página NO aparece (start/end None), aquí podés CREARLA correctamente.
#    - Podés reordenar páginas completas (mover P6 arriba/abajo, etc.)
#    - Podés renombrar etiqueta (label visible) del grupo/página
#    - Crea estructura correcta: begin_group (appearance field-list) + end_group
#
# ✅ Evita el error típico que te “corta” el editor en P5:
#    - Cuando falta end_group o el begin_group no tiene appearance="field-list",
#      el índice de páginas se rompe. Aquí lo reparamos fácil.
#
# REQUISITOS:
# - Ya existen en estado: st.session_state.survey_bank
# - Helpers de Parte 6: _index_pages, _page_label, _extract_page_id_from_name, etc.
#   (Si los pegaste tal cual, ya están disponibles.)
# ==========================================================================================

# ==========================================================================================
# 1) Helpers: crear y localizar páginas en survey_bank
# ==========================================================================================
def _find_page_begin_index(bank: list[dict], page_id: str) -> int | None:
    for i, r in enumerate(bank):
        if str(r.get("type","")).strip() == "begin_group" and str(r.get("appearance","")).strip() == "field-list":
            pid = _extract_page_id_from_name(str(r.get("name","")))
            if pid == page_id:
                return i
    return None

def _find_page_end_index(bank: list[dict], begin_idx: int) -> int | None:
    """
    Encuentra el end_group correspondiente al begin_idx
    (asume estructura correcta y sin anidamiento complejo en páginas).
    """
    if begin_idx is None:
        return None
    for j in range(begin_idx + 1, len(bank)):
        if str(bank[j].get("type","")).strip() == "end_group":
            return j
    return None

def _create_page_block(bank: list[dict], page_id: str, page_label: str, insert_at_end: bool = True):
    """
    Inserta una nueva página (begin_group+end_group) al final (o en posición específica en Parte 7).
    """
    # Nombre del grupo siguiendo convención
    group_name = f"{page_id}_grupo"
    group_name = _unique_question_name(bank, group_name)

    begin = {"type": "begin_group", "name": group_name, "label": page_label, "appearance": "field-list"}
    end = {"type": "end_group", "name": f"{page_id}_end"}

    if insert_at_end:
        bank.append(begin)
        # placeholder note dentro de la página para que no quede vacía
        bank.append({"type": "note", "name": f"{page_id}_nota", "label": "Página creada. Agregue preguntas aquí.", "bind::esri:fieldType": "null"})
        bank.append(end)
    else:
        # por si luego se quiere insertar en índice exacto
        bank.insert(0, begin)
        bank.insert(1, {"type": "note", "name": f"{page_id}_nota", "label": "Página creada. Agregue preguntas aquí.", "bind::esri:fieldType": "null"})
        bank.insert(2, end)

def _extract_whole_page_slice(bank: list[dict], page_id: str) -> tuple[int | None, int | None]:
    """
    Retorna (start,end) índices reales del bloque de página.
    """
    start = _find_page_begin_index(bank, page_id)
    if start is None:
        return None, None
    end = _find_page_end_index(bank, start)
    return start, end

def _move_page(bank: list[dict], page_id: str, direction: str):
    """
    Mueve una página completa (bloque begin..end) hacia arriba o abajo respecto a otras páginas.
    direction: "up" o "down"
    """
    pages = _index_pages(bank)

    # páginas reales presentes (con start/end)
    real = []
    for pid in ["p1","p2","p3","p4","p5","p6","p7","p8"]:
        s = pages.get(pid, {}).get("start")
        e = pages.get(pid, {}).get("end")
        if s is not None and e is not None:
            real.append((pid, s, e))

    # ordenar por start
    real.sort(key=lambda x: x[1])

    # localizar
    pos = None
    for i, (pid, s, e) in enumerate(real):
        if pid == page_id:
            pos = i
            break
    if pos is None:
        return

    if direction == "up" and pos == 0:
        return
    if direction == "down" and pos == len(real) - 1:
        return

    target_pos = pos - 1 if direction == "up" else pos + 1
    pid_a, s_a, e_a = real[pos]
    pid_b, s_b, e_b = real[target_pos]

    # extraer bloques completos
    block_a = bank[s_a:e_a+1]
    block_b = bank[s_b:e_b+1]

    # reconstruir bank sin esos bloques y reinsertar intercambiados
    # Nota: si s_a < s_b, quitar primero el bloque de mayor índice
    idxs = sorted([(s_a, e_a), (s_b, e_b)], key=lambda x: x[0])
    (s1, e1), (s2, e2) = idxs

    prefix = bank[:s1]
    mid = bank[e1+1:s2]
    suffix = bank[e2+1:]

    # decidir orden final
    if direction == "up":
        # A sube: se coloca A antes que B
        if s_a > s_b:
            # ya está abajo, sube => B luego A? No: A antes que B
            new_bank = prefix + block_a + mid + block_b + suffix
        else:
            # s_a < s_b, A ya estaba arriba, "up" no debería ocurrir, pero por seguridad:
            new_bank = prefix + block_a + mid + block_b + suffix
    else:
        # A baja: se coloca B antes que A
        if s_a < s_b:
            new_bank = prefix + block_b + mid + block_a + suffix
        else:
            new_bank = prefix + block_b + mid + block_a + suffix

    bank[:] = new_bank

def _repair_pages_structure(bank: list[dict]):
    """
    Reparación básica:
    - Si encuentra begin_group field-list sin end_group después, agrega end_group al final.
    - (Esto es una red de seguridad para casos raros)
    """
    i = 0
    while i < len(bank):
        r = bank[i]
        if _is_page_begin(r):
            # buscar end_group después
            end = _find_page_end_index(bank, i)
            if end is None:
                # agregar end_group
                bank.append({"type": "end_group", "name": f"auto_end_{i}"})
        i += 1

# ==========================================================================================
# 2) UI: Tab "Páginas"
# ==========================================================================================
if active_tab == "Páginas":
    st.header("📑 Gestor de páginas (P1–P8)")

    bank = st.session_state.survey_bank

    # Reparación rápida (si algo raro pasó)
    if st.button("🧯 Reparar estructura (begin/end) automáticamente", use_container_width=True, key="btn_repair_pages"):
        _repair_pages_structure(bank)
        st.session_state.survey_bank = bank
        st.success("Reparación aplicada.")
        st.rerun()

    pages = _index_pages(bank)

    st.markdown("---")
    st.subheader("Estado de páginas")

    # tabla resumen
    rows = []
    for pid in ["p1","p2","p3","p4","p5","p6","p7","p8"]:
        info = pages.get(pid, {})
        rows.append({
            "Página": _page_label(pid),
            "Existe en banco": "Sí" if info.get("start") is not None and info.get("end") is not None else "No",
            "start": info.get("start"),
            "end": info.get("end"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Crear páginas faltantes (1 clic)")

    missing = [pid for pid in ["p1","p2","p3","p4","p5","p6","p7","p8"]
               if pages.get(pid, {}).get("start") is None or pages.get(pid, {}).get("end") is None]

    colA, colB = st.columns([2, 1], vertical_alignment="center")
    with colA:
        if missing:
            st.warning(f"Faltan páginas: {', '.join(missing).upper()}")
        else:
            st.success("Todas las páginas P1–P8 existen correctamente.")

    with colB:
        if st.button("➕ Crear todas las faltantes", use_container_width=True, key="btn_create_missing"):
            for pid in missing:
                _create_page_block(bank, pid, _page_label(pid), insert_at_end=True)
            st.session_state.survey_bank = bank
            st.success("Páginas faltantes creadas.")
            st.rerun()

    st.markdown("---")
    st.subheader("Crear una página específica")

    colC, colD = st.columns([1, 2], vertical_alignment="center")
    with colC:
        pid_new = st.selectbox("ID de página", options=["p1","p2","p3","p4","p5","p6","p7","p8"], index=5, key="pid_new_page")
    with colD:
        label_new = st.text_input("Label (título visible)", value=_page_label(pid_new), key="label_new_page")

    if st.button("➕ Crear esta página", use_container_width=True, key="btn_create_this_page"):
        s, e = _extract_whole_page_slice(bank, pid_new)
        if s is not None and e is not None:
            st.error("Esa página ya existe en el banco.")
        else:
            _create_page_block(bank, pid_new, label_new.strip() or _page_label(pid_new), insert_at_end=True)
            st.session_state.survey_bank = bank
            st.success("Página creada.")
            st.rerun()

    st.markdown("---")
    st.subheader("Reordenar páginas completas (subir/bajar)")

    # lista de páginas reales existentes, en orden actual
    pages2 = _index_pages(bank)
    real_order = []
    for pid in ["p1","p2","p3","p4","p5","p6","p7","p8"]:
        s = pages2.get(pid, {}).get("start")
        e = pages2.get(pid, {}).get("end")
        if s is not None and e is not None:
            real_order.append((pid, s, e))
    real_order.sort(key=lambda x: x[1])

    if not real_order:
        st.info("Aún no hay páginas reales creadas en el banco.")
    else:
        for pid, s, e in real_order:
            c1, c2, c3, c4 = st.columns([3, 1, 1, 2], vertical_alignment="center")
            with c1:
                st.markdown(f"**{_page_label(pid)}**  \n`start={s}  end={e}`")
            with c2:
                if st.button("⬆️", use_container_width=True, key=f"pg_up_{pid}"):
                    _move_page(bank, pid, "up")
                    st.session_state.survey_bank = bank
                    st.rerun()
            with c3:
                if st.button("⬇️", use_container_width=True, key=f"pg_down_{pid}"):
                    _move_page(bank, pid, "down")
                    st.session_state.survey_bank = bank
                    st.rerun()
            with c4:
                # renombrar label del begin_group real
                new_lb = st.text_input("Título", value=_page_label(pid), key=f"pg_label_{pid}")
                if st.button("💾 Guardar título", use_container_width=True, key=f"pg_save_{pid}"):
                    begin_idx = _find_page_begin_index(bank, pid)
                    if begin_idx is None:
                        st.error("No se encontró begin_group de esta página.")
                    else:
                        bank[begin_idx]["label"] = new_lb.strip() or _page_label(pid)
                        st.session_state.survey_bank = bank
                        st.success("Título actualizado.")
                        st.rerun()

# ==========================================================================================
# FIN PARTE 7/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 8/10) ==============================
# ===================== Construcción XLSForm FINAL (survey/choices/settings) + Export =======
# ==========================================================================================
#
# PARTE 8/10 (ACTUALIZADA)
# ✅ Construye el XLSForm usando LO QUE SE EDITA EN LA APP:
#    - survey_bank  (preguntas/páginas editadas por cualquier persona)
#    - choices_bank (listas editadas fácil)
#    - glosario_definitions + glossary_by_page + glossary_order_by_page (glosario editable)
#
# ✅ Soluciona errores típicos al subir a ArcGIS Survey123:
#    - Garantiza que existan list_canton y list_distrito en choices
#    - Asegura names únicos en survey (sin duplicados)
#    - Mantiene settings.style="pages"
#    - Notas sin columnas: bind::esri:fieldType="null"
#
# ✅ Inserta el glosario “dentro de la página” automáticamente:
#    - Se inyecta antes del end_group de cada página que tenga términos asignados
#    - Respeta el orden manual “uno por línea” si existe
#
# REQUISITOS:
# - Ya existen (de partes anteriores): descargar_xlsform, slugify_name, asegurar_nombre_unico
# - Estado: st.session_state.survey_bank, st.session_state.choices_bank
# - Estado glosario: st.session_state.glossary_definitions, glossary_by_page, glossary_order_by_page
#
# NOTA:
# - Esta parte NO “reinventa” tus preguntas: exporta exactamente lo que esté en survey_bank.
# - En Parte 9/10 agregamos: import/export JSON de todo el formulario (backup) + “reset”.
# ==========================================================================================

# ==========================================================================================
# 1) Helpers: choices → rows (list_name/name/label + extras)
# ==========================================================================================
def _ensure_mandatory_lists_in_choices_bank():
    cb = st.session_state.get("choices_bank", {})
    if "list_canton" not in cb or not isinstance(cb.get("list_canton"), list) or len(cb.get("list_canton")) == 0:
        cb["list_canton"] = [{"name": "sin_catalogo", "label": "Sin catálogo (agregar cantones en Catálogo)"}]

    if "list_distrito" not in cb or not isinstance(cb.get("list_distrito"), list) or len(cb.get("list_distrito")) == 0:
        cb["list_distrito"] = [{"name": "sin_catalogo", "label": "Sin catálogo (agregar distritos en Catálogo)", "canton_key": "sin_catalogo"}]

    st.session_state.choices_bank = cb

def _sync_catalog_ext_rows_into_choices_bank():
    """
    Si todavía usás el editor de catálogo por lotes (choices_ext_rows),
    aquí se integra a choices_bank automáticamente antes de exportar.
    """
    if "choices_ext_rows" not in st.session_state:
        return

    ext = st.session_state.get("choices_ext_rows", [])
    if not isinstance(ext, list) or len(ext) == 0:
        return

    cb = st.session_state.choices_bank

    # construir sets para evitar duplicados
    cant_set = set((r.get("name",""), r.get("label","")) for r in cb.get("list_canton", []))
    dist_set = set((r.get("name",""), r.get("label",""), r.get("canton_key","")) for r in cb.get("list_distrito", []))

    for r in ext:
        ln = str(r.get("list_name","")).strip()
        if ln == "list_canton":
            nm = str(r.get("name","")).strip()
            lb = str(r.get("label","")).strip()
            if nm and lb and (nm, lb) not in cant_set:
                cb.setdefault("list_canton", []).append({"name": nm, "label": lb})
                cant_set.add((nm, lb))

        if ln == "list_distrito":
            nm = str(r.get("name","")).strip()
            lb = str(r.get("label","")).strip()
            ck = str(r.get("canton_key","")).strip()
            if nm and lb and ck and (nm, lb, ck) not in dist_set:
                cb.setdefault("list_distrito", []).append({"name": nm, "label": lb, "canton_key": ck})
                dist_set.add((nm, lb, ck))

    st.session_state.choices_bank = cb

def _choices_bank_to_rows() -> list[dict]:
    """
    Convierte choices_bank (dict) a lista rows para hoja choices.
    """
    cb = st.session_state.choices_bank
    rows = []
    for list_name, opts in cb.items():
        if not isinstance(opts, list):
            continue
        for o in opts:
            r = {"list_name": list_name, "name": str(o.get("name","")).strip(), "label": str(o.get("label","")).strip()}
            # extras
            for k, v in (o or {}).items():
                if k not in ["name", "label"]:
                    r[k] = "" if v is None else str(v)
            rows.append(r)
    return rows

# ==========================================================================================
# 2) Helpers: survey_bank → rows con glosario inyectado + names únicos
# ==========================================================================================
def _is_page_begin_group(row: dict) -> bool:
    return str(row.get("type","")).strip() == "begin_group" and str(row.get("appearance","")).strip() == "field-list"

def _inject_glossary_into_survey(bank: list[dict]) -> list[dict]:
    """
    Inserta el glosario dentro de cada página antes del end_group.
    Usa:
      - glossary_by_page
      - glossary_order_by_page (si existe)
      - glossary_definitions
    """
    defs = st.session_state.get("glossary_definitions", {})
    by_page = st.session_state.get("glossary_by_page", {})
    order_by_page = st.session_state.get("glossary_order_by_page", {})

    v_si = slugify_name("Sí")
    # “base” de relevant para glosario (como tu lógica original)
    rel_si = f"${{acepta_participar}}='{v_si}'"

    out = []
    current_pid = None
    current_page_rows = []

    def flush_page():
        """
        Emite current_page_rows + glosario (si aplica) + end_group ya contenido.
        Aquí NO se usa, porque añadimos todo a medida, pero lo dejamos claro.
        """
        return

    # Recorremos y cuando vemos begin_group field-list, cambiamos página.
    i = 0
    while i < len(bank):
        row = dict(bank[i])

        if _is_page_begin_group(row):
            # Iniciar nueva página
            current_pid = _extract_page_id_from_name(str(row.get("name","")))
            out.append(row)
            i += 1
            continue

        # Si es end_group y estamos dentro de una página -> antes de cerrarla inyectamos glosario
        if str(row.get("type","")).strip() == "end_group" and current_pid:
            page_id = current_pid

            # términos asignados y existentes
            assigned = by_page.get(page_id, [])
            assigned = [t for t in assigned if t in defs]

            # orden final
            manual = order_by_page.get(page_id)
            if isinstance(manual, list) and manual:
                final_terms = [t for t in manual if t in assigned]
                for t in assigned:
                    if t not in final_terms:
                        final_terms.append(t)
            else:
                final_terms = list(assigned)

            if final_terms:
                # Pregunta: “¿Desea acceder…?”
                out.append({
                    "type": "select_one yesno",
                    "name": f"{page_id}_accede_glosario",
                    "label": "¿Desea acceder al glosario de esta sección?",
                    "required": "no",
                    "appearance": "minimal",
                    "relevant": rel_si
                })

                rel_glos = f"({rel_si}) and (${{{page_id}_accede_glosario}}='{v_si}')"

                out.append({
                    "type": "begin_group",
                    "name": f"{page_id}_glosario",
                    "label": "Glosario",
                    "relevant": rel_glos
                })

                out.append({
                    "type": "note",
                    "name": f"{page_id}_glosario_intro",
                    "label": "A continuación, se muestran definiciones de términos que aparecen en esta sección.",
                    "relevant": rel_glos,
                    "bind::esri:fieldType": "null"
                })

                for idx, t in enumerate(final_terms, start=1):
                    out.append({
                        "type": "note",
                        "name": f"{page_id}_glos_{idx}",
                        "label": defs.get(t, ""),
                        "relevant": rel_glos,
                        "bind::esri:fieldType": "null"
                    })

                out.append({
                    "type": "note",
                    "name": f"{page_id}_glosario_cierre",
                    "label": "Para continuar con la encuesta, desplácese hacia arriba y continúe con normalidad.",
                    "relevant": rel_glos,
                    "bind::esri:fieldType": "null"
                })

                out.append({"type": "end_group", "name": f"{page_id}_glosario_end"})

            # Ahora sí cerramos la página
            out.append(row)
            current_pid = None
            i += 1
            continue

        # fila normal
        out.append(row)
        i += 1

    return out

def _ensure_unique_survey_names(rows: list[dict]) -> list[dict]:
    """
    Asegura que 'name' sea único en TODA la hoja survey.
    - Si se repite, agrega sufijo _2, _3...
    - Respeta filas sin name (pero casi todas deben tener)
    """
    used = set()
    out = []
    for r in rows:
        rr = dict(r)
        nm = str(rr.get("name","")).strip()
        if nm:
            if nm in used:
                nm2 = asegurar_nombre_unico(nm, used)
                rr["name"] = nm2
                used.add(nm2)
            else:
                used.add(nm)
        out.append(rr)
    return out

def _normalize_notes_no_column(rows: list[dict]) -> list[dict]:
    """
    Asegura que todas las filas type=note tengan bind::esri:fieldType="null"
    (para que NO creen columnas).
    """
    out = []
    for r in rows:
        rr = dict(r)
        if str(rr.get("type","")).strip() == "note":
            rr.setdefault("bind::esri:fieldType", "null")
        out.append(rr)
    return out

def _survey_rows_from_bank_final() -> list[dict]:
    """
    Construye survey final:
    - Usa survey_bank
    - Inyecta glosario por página (editable)
    - Normaliza notas
    - Asegura names únicos
    """
    bank = st.session_state.survey_bank
    rows = _inject_glossary_into_survey(bank)
    rows = _normalize_notes_no_column(rows)
    rows = _ensure_unique_survey_names(rows)
    return rows

# ==========================================================================================
# 3) Construir DataFrames (survey/choices/settings)
# ==========================================================================================
def construir_xlsform_desde_estado(form_title: str, logo_media_name: str, idioma: str, version: str):
    # choices: integrar catálogo externo si existe
    _sync_catalog_ext_rows_into_choices_bank()
    _ensure_mandatory_lists_in_choices_bank()

    # survey final
    survey_rows = _survey_rows_from_bank_final()

    # SI el logo fue editado por UI, asegurar que exista en p1_logo (si el usuario lo quiere)
    # (no forzamos nada: sólo si hay un p1_logo note, lo actualizamos)
    for r in survey_rows:
        if str(r.get("name","")).strip() == "p1_logo":
            r["media::image"] = logo_media_name
            r["label"] = form_title

    # columns estándar
    survey_cols = [
        "type", "name", "label", "required", "appearance",
        "relevant", "choice_filter",
        "constraint", "constraint_message",
        "media::image",
        "bind::esri:fieldType"
    ]
    df_survey = pd.DataFrame(survey_rows, columns=survey_cols).fillna("")

    # choices
    choices_rows = _choices_bank_to_rows()

    # determinar columnas extra (ej: canton_key)
    choices_cols_all = set()
    for r in choices_rows:
        choices_cols_all.update(r.keys())
    base_choice_cols = ["list_name", "name", "label"]
    for extra in sorted(choices_cols_all):
        if extra not in base_choice_cols:
            base_choice_cols.append(extra)
    df_choices = pd.DataFrame(choices_rows, columns=base_choice_cols).fillna("")

    # settings
    df_settings = pd.DataFrame([{
        "form_title": form_title,
        "version": version,
        "default_language": idioma,
        "style": "pages"
    }], columns=["form_title", "version", "default_language", "style"]).fillna("")

    return df_survey, df_choices, df_settings

# ==========================================================================================
# 4) UI: Tab "Exportar"
# ==========================================================================================
if active_tab == "Exportar":
    st.header("📦 Exportar XLSForm (Survey123) — desde lo editado en la app")

    idioma = st.selectbox("Idioma (default_language)", options=["es", "en"], index=0, key="exp_lang")
    version_auto = datetime.now().strftime("%Y%m%d%H%M")
    version = st.text_input("Versión (settings.version)", value=version_auto, key="exp_version")

    st.caption("Se exporta el XLSForm usando: survey_bank + choices_bank + glosario por página.")

    if st.button("🧮 Construir XLSForm FINAL", use_container_width=True, key="btn_build_final"):
        # Asegurar mínimos
        _ensure_mandatory_lists_in_choices_bank()

        df_survey, df_choices, df_settings = construir_xlsform_desde_estado(
            form_title=form_title,
            logo_media_name=logo_media_name,
            idioma=idioma,
            version=version.strip() or version_auto
        )

        st.success("XLSForm FINAL construido. Vista previa rápida:")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Hoja: survey**")
            st.dataframe(df_survey, use_container_width=True, hide_index=True, height=360)
        with c2:
            st.markdown("**Hoja: choices**")
            st.dataframe(df_choices, use_container_width=True, hide_index=True, height=360)
        with c3:
            st.markdown("**Hoja: settings**")
            st.dataframe(df_settings, use_container_width=True, hide_index=True, height=360)

        nombre_archivo = slugify_name(form_title) + "_xlsform.xlsx"
        descargar_xlsform(df_survey, df_choices, df_settings, nombre_archivo)

        # Descargar logo (si el usuario subió bytes)
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
1) Crear encuesta desde archivo y seleccionar el XLSForm descargado.  
2) Copiar el logo dentro de la carpeta media/ del proyecto con el mismo nombre de `media::image`.  
3) Verás páginas con Siguiente/Anterior porque `settings.style = pages`.  
4) El glosario aparece solo si la persona marca “Sí” (no es obligatorio).  
""")

# ==========================================================================================
# FIN PARTE 8/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 9/10) ==============================
# ===================== Backup/Restauración (JSON) + Import/Export de todo el editor =======
# ==========================================================================================
#
# PARTE 9/10 (ACTUALIZADA)
# ✅ Para que “cualquiera pueda editar” SIN miedo a perder nada:
#    - Exporta un JSON con TODO el estado editable:
#        • survey_bank
#        • choices_bank
#        • glossary_definitions
#        • glossary_by_page
#        • glossary_order_by_page
#        • choices_ext_rows (si lo usas)
#        • metadata (titulo, logo name, versión)
#    - Importa ese JSON y restaura el editor completo
#
# ✅ Esto también ayuda si algo “se rompe” y querés volver a un punto anterior.
#
# REQUISITOS:
# - Ya existen: st, pd, datetime, slugify_name
# - Estado: st.session_state.survey_bank, st.session_state.choices_bank, glosario...
# - Debe existir active_tab == "Backup" (o agrega esa opción a tu menú)
# ==========================================================================================

import json

# ==========================================================================================
# 1) Helpers de serialización
# ==========================================================================================
def _export_state_to_dict(form_title: str, logo_media_name: str, version: str, idioma: str) -> dict:
    return {
        "meta": {
            "form_title": form_title,
            "logo_media_name": logo_media_name,
            "exported_at": datetime.now().isoformat(),
            "version": version,
            "default_language": idioma,
        },
        "survey_bank": st.session_state.get("survey_bank", []),
        "choices_bank": st.session_state.get("choices_bank", {}),
        "glossary_definitions": st.session_state.get("glossary_definitions", {}),
        "glossary_by_page": st.session_state.get("glossary_by_page", {}),
        "glossary_order_by_page": st.session_state.get("glossary_order_by_page", {}),
        # si seguís usando el catálogo por lotes:
        "choices_ext_rows": st.session_state.get("choices_ext_rows", []),
    }

def _validate_import_payload(payload: dict) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "El archivo no contiene un objeto JSON válido."

    required = ["survey_bank", "choices_bank", "glossary_definitions", "glossary_by_page"]
    for k in required:
        if k not in payload:
            return False, f"Falta la clave requerida: {k}"

    if not isinstance(payload.get("survey_bank"), list):
        return False, "survey_bank debe ser una lista."
    if not isinstance(payload.get("choices_bank"), dict):
        return False, "choices_bank debe ser un diccionario."
    if not isinstance(payload.get("glossary_definitions"), dict):
        return False, "glossary_definitions debe ser un diccionario."
    if not isinstance(payload.get("glossary_by_page"), dict):
        return False, "glossary_by_page debe ser un diccionario."

    # opcionales
    if "glossary_order_by_page" in payload and not isinstance(payload.get("glossary_order_by_page"), dict):
        return False, "glossary_order_by_page debe ser un diccionario."

    if "choices_ext_rows" in payload and not isinstance(payload.get("choices_ext_rows"), list):
        return False, "choices_ext_rows debe ser una lista."

    return True, "OK"

def _restore_state_from_payload(payload: dict):
    st.session_state.survey_bank = payload.get("survey_bank", [])
    st.session_state.choices_bank = payload.get("choices_bank", {})
    st.session_state.glossary_definitions = payload.get("glossary_definitions", {})
    st.session_state.glossary_by_page = payload.get("glossary_by_page", {})
    st.session_state.glossary_order_by_page = payload.get("glossary_order_by_page", {})
    st.session_state.choices_ext_rows = payload.get("choices_ext_rows", [])

# ==========================================================================================
# 2) UI: Tab "Backup"
# ==========================================================================================
if active_tab == "Backup":
    st.header("🧰 Backup / Restaurar (JSON) — todo el editor")

    st.markdown("""
Aquí podés:
- **Descargar un respaldo** del formulario completo (JSON)
- **Cargar un respaldo** para recuperar todo (preguntas, choices, glosario, catálogo)
""")

    st.markdown("---")
    st.subheader("📤 Descargar respaldo")

    colA, colB = st.columns([1, 1], vertical_alignment="center")
    with colA:
        idioma_bk = st.selectbox("Idioma (solo para meta del backup)", options=["es", "en"], index=0, key="bk_lang")
    with colB:
        version_auto = datetime.now().strftime("%Y%m%d%H%M")
        version_bk = st.text_input("Versión (meta)", value=version_auto, key="bk_version")

    if st.button("📥 Generar y descargar JSON", use_container_width=True, key="btn_dl_json"):
        payload = _export_state_to_dict(
            form_title=form_title,
            logo_media_name=logo_media_name,
            version=version_bk.strip() or version_auto,
            idioma=idioma_bk
        )
        json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        filename = slugify_name(form_title) + "_backup.json"

        st.download_button(
            label=f"⬇️ Descargar {filename}",
            data=json_bytes,
            file_name=filename,
            mime="application/json",
            use_container_width=True
        )

    st.markdown("---")
    st.subheader("📥 Restaurar desde respaldo")

    up = st.file_uploader("Cargar archivo JSON de respaldo", type=["json"], key="bk_uploader")
    if up:
        try:
            data = json.loads(up.getvalue().decode("utf-8"))
            ok, msg = _validate_import_payload(data)
            if not ok:
                st.error(msg)
            else:
                # mostrar meta si existe
                meta = data.get("meta", {})
                if isinstance(meta, dict) and meta:
                    st.info(
                        f"Respaldo detectado: {meta.get('form_title','(sin título)')} | "
                        f"Exportado: {meta.get('exported_at','(sin fecha)')} | "
                        f"Versión: {meta.get('version','(sin versión)')}"
                    )

                colR1, colR2 = st.columns(2)
                with colR1:
                    if st.button("✅ Restaurar (aplicar)", use_container_width=True, key="btn_restore_apply"):
                        _restore_state_from_payload(data)
                        st.success("Respaldo restaurado. Se recargará la app para reflejar cambios.")
                        st.rerun()

                with colR2:
                    if st.button("👀 Vista previa del respaldo", use_container_width=True, key="btn_restore_preview"):
                        st.write("survey_bank filas:", len(data.get("survey_bank", [])))
                        st.write("choices_bank listas:", len(list(data.get("choices_bank", {}).keys())))
                        st.write("glosario términos:", len(list(data.get("glossary_definitions", {}).keys())))
                        st.write("glosario por página:", {k: len(v) for k, v in data.get("glossary_by_page", {}).items()})

        except Exception as e:
            st.error(f"No se pudo leer el JSON: {e}")

    st.markdown("---")
    st.subheader("🧹 Reset seguro (opcional)")

    st.caption("Esto borra el estado editable actual. Úsalo solo si vas a restaurar un backup o empezar de cero.")
    colX, colY = st.columns(2)
    with colX:
        if st.button("🗑️ Resetear TODO (preguntas/choices/glosario)", use_container_width=True, key="btn_reset_all"):
            st.session_state.survey_bank = []
            st.session_state.choices_bank = {}
            st.session_state.glossary_definitions = {}
            st.session_state.glossary_by_page = {}
            st.session_state.glossary_order_by_page = {}
            st.session_state.choices_ext_rows = []
            st.success("Estado reseteado. Se recargará la app.")
            st.rerun()
    with colY:
        st.info("Tip: primero descarga un JSON de respaldo antes de resetear.")

# ==========================================================================================
# FIN PARTE 9/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 10/10) =============================
# ===================== Menú final + Editor fácil de CHOICES + Validaciones antes export ===
# ==========================================================================================
#
# PARTE 10/10 (FINAL)
# ✅ Completa todo lo que faltaba para que el sistema sea “para cualquiera”:
#    1) Menú/Tabs (simple): Preguntas | Páginas | Choices | Glosario | Catálogo | Exportar | Backup
#    2) Editor de Choices fácil (sin Excel):
#       - Crear listas (list_name)
#       - Agregar/editar/eliminar opciones (name/label)
#       - Soporte extra para list_distrito con `canton_key`
#    3) Validaciones para evitar error al cargar en Survey123:
#       - names duplicados en survey
#       - choices sin list_name/name/label
#       - select_one/select_multiple referenciando listas que no existen
#       - list_distrito SIN canton_key (si se usa choice_filter)
#
# REQUISITOS:
# - Ya pegaste Partes 1..9 y existen:
#   - slugify_name, asegurar_nombre_unico, descargar_xlsform
#   - survey_bank editor (Parte 6)
#   - pages manager (Parte 7)
#   - export final (Parte 8)
#   - backup JSON (Parte 9)
#
# IMPORTANTE:
# - Esta Parte 10 incluye el “MENÚ” (active_tab).
# - Si ya tenías un menú, reemplazalo por este (o alinéalo) para que active_tab funcione igual.
# ==========================================================================================

# ==========================================================================================
# A) MENÚ PRINCIPAL (tabs simples)
# ==========================================================================================
st.markdown("---")
st.subheader("🧭 Navegación")

menu_tabs = [
    "Preguntas",   # Parte 6
    "Páginas",     # Parte 7
    "Choices",     # Parte 10 (esta)
    "Glosario",    # Parte 5
    "Catálogo",    # Parte 10 (esta) opcional
    "Exportar",    # Parte 8
    "Backup",      # Parte 9
]

active_tab = st.radio(
    "Secciones",
    options=menu_tabs,
    horizontal=True,
    key="main_tabs"
)

st.markdown("---")

# ==========================================================================================
# B) ESTADO: choices_bank si no existe
# ==========================================================================================
if "choices_bank" not in st.session_state:
    st.session_state.choices_bank = {}

def _init_default_choices_if_empty():
    """
    Crea listas básicas si no existen. No sobreescribe si ya hay algo.
    """
    cb = st.session_state.choices_bank
    if cb:
        return

    cb["yesno"] = [
        {"name": slugify_name("Sí"), "label": "Sí"},
        {"name": slugify_name("No"), "label": "No"},
    ]
    cb["seguridad_5"] = [{"name": slugify_name(x), "label": x} for x in [
        "Muy inseguro", "Inseguro", "Ni seguro ni inseguro", "Seguro", "Muy seguro"
    ]]
    cb["escala_1_10"] = [{"name": str(i), "label": str(i)} for i in range(1, 11)]

    # Cantón/Distrito placeholder mínimo (se reemplaza con Catálogo)
    cb["list_canton"] = [{"name": "sin_catalogo", "label": "Sin catálogo (agregar cantones en Catálogo)"}]
    cb["list_distrito"] = [{"name": "sin_catalogo", "label": "Sin catálogo (agregar distritos en Catálogo)", "canton_key": "sin_catalogo"}]

    st.session_state.choices_bank = cb

_init_default_choices_if_empty()

# ==========================================================================================
# C) EDITOR DE CHOICES (fácil)
# ==========================================================================================
def _choices_list_names() -> list[str]:
    cb = st.session_state.choices_bank
    names = sorted(list(cb.keys()), key=lambda x: x.lower())
    return names

def _ensure_choice_names_unique_in_list(list_name: str):
    cb = st.session_state.choices_bank
    opts = cb.get(list_name, [])
    used = set()
    for o in opts:
        nm = str(o.get("name","")).strip()
        if not nm:
            nm = slugify_name(str(o.get("label","")) or "opcion")
            o["name"] = nm
        if nm in used:
            o["name"] = asegurar_nombre_unico(nm, used)
        used.add(o["name"])
    cb[list_name] = opts
    st.session_state.choices_bank = cb

if active_tab == "Choices":
    st.header("🧩 Editor de Choices (listas y opciones) — fácil")

    cb = st.session_state.choices_bank

    colL, colR = st.columns([1, 1], vertical_alignment="top")

    with colL:
        st.subheader("📌 Listas")
        existing = _choices_list_names()

        list_sel = st.selectbox("Seleccionar lista (list_name)", options=existing, index=existing.index("yesno") if "yesno" in existing else 0, key="ch_list_sel")

        st.markdown("**Crear nueva lista**")
        new_list = st.text_input("Nuevo list_name", value="", key="ch_new_list")
        if st.button("➕ Crear lista", use_container_width=True, key="ch_btn_create_list"):
            ln = (new_list or "").strip()
            if not ln:
                st.error("El list_name no puede ir vacío.")
            elif ln in cb:
                st.error("Esa lista ya existe.")
            else:
                cb[ln] = []
                st.session_state.choices_bank = cb
                st.success("Lista creada.")
                st.rerun()

        st.markdown("---")
        if st.button("🗑️ Eliminar lista seleccionada", use_container_width=True, key="ch_btn_del_list"):
            if list_sel in ["yesno"]:  # proteger listas críticas
                st.error("No se recomienda borrar yesno.")
            else:
                cb.pop(list_sel, None)
                st.session_state.choices_bank = cb
                st.success("Lista eliminada.")
                st.rerun()

    with colR:
        st.subheader("🧷 Opciones de la lista")

        opts = cb.get(list_sel, [])
        # Mostrar en tabla editable
        # Si es list_distrito, requiere canton_key
        is_distrito = (list_sel == "list_distrito")

        if is_distrito:
            st.caption("Esta lista requiere la columna extra `canton_key` para que funcione el choice_filter Cantón→Distrito.")

        # construir dataframe
        if is_distrito:
            df = pd.DataFrame(opts, columns=["name", "label", "canton_key"]).fillna("")
        else:
            df = pd.DataFrame(opts, columns=["name", "label"]).fillna("")

        edited = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key=f"ch_editor_{list_sel}"
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Guardar opciones", use_container_width=True, key=f"ch_save_{list_sel}"):
                new_opts = []
                for _, rr in edited.iterrows():
                    nm = str(rr.get("name","")).strip()
                    lb = str(rr.get("label","")).strip()
                    if not lb and not nm:
                        continue
                    if not nm:
                        nm = slugify_name(lb or "opcion")
                    item = {"name": nm, "label": lb or nm}
                    if is_distrito:
                        ck = str(rr.get("canton_key","")).strip()
                        if not ck:
                            # no bloqueamos, pero advertimos; validaciones lo marcarán
                            item["canton_key"] = ""
                        else:
                            item["canton_key"] = ck
                    new_opts.append(item)

                cb[list_sel] = new_opts
                st.session_state.choices_bank = cb

                _ensure_choice_names_unique_in_list(list_sel)

                st.success("Opciones guardadas.")
                st.rerun()

        with c2:
            if st.button("➕ Agregar fila rápida", use_container_width=True, key=f"ch_addrow_{list_sel}"):
                # agregar una fila placeholder
                if is_distrito:
                    cb[list_sel].append({"name": "", "label": "", "canton_key": ""})
                else:
                    cb[list_sel].append({"name": "", "label": ""})
                st.session_state.choices_bank = cb
                st.rerun()

        with c3:
            if st.button("🧹 Normalizar names", use_container_width=True, key=f"ch_norm_{list_sel}"):
                _ensure_choice_names_unique_in_list(list_sel)
                st.success("Names normalizados.")
                st.rerun()

# ==========================================================================================
# D) CATÁLOGO Cantón→Distrito (UI fácil) — opcional, para quien no quiere tocar choices
# ==========================================================================================
if active_tab == "Catálogo":
    st.header("📚 Catálogo Cantón → Distrito (fácil)")

    cb = st.session_state.choices_bank
    cb.setdefault("list_canton", [])
    cb.setdefault("list_distrito", [])

    st.caption("Esto alimenta directamente choices_bank: list_canton y list_distrito (con canton_key).")

    colA, colB = st.columns([1, 2], vertical_alignment="top")
    with colA:
        canton = st.text_input("Cantón", value="", key="cat_canton")
        if st.button("➕ Agregar Cantón", use_container_width=True, key="cat_add_canton"):
            c = (canton or "").strip()
            if not c:
                st.error("Cantón vacío.")
            else:
                nm = slugify_name(c)
                # evitar duplicado
                exists = any(str(x.get("name","")) == nm for x in cb["list_canton"])
                if not exists:
                    cb["list_canton"].append({"name": nm, "label": c})
                    st.session_state.choices_bank = cb
                    st.success("Cantón agregado.")
                    st.rerun()
                else:
                    st.warning("Ese cantón ya existe (por name).")

    with colB:
        st.markdown("**Agregar distritos (uno por línea) al cantón seleccionado**")
        cantones_labels = [x.get("label","") for x in cb["list_canton"]] or ["(vacío)"]
        cantones_map = {x.get("label",""): x.get("name","") for x in cb["list_canton"]}

        canton_sel_label = st.selectbox("Cantón destino", options=cantones_labels, key="cat_canton_sel")
        canton_key = cantones_map.get(canton_sel_label, "")

        distritos_lines = st.text_area("Distritos (uno por línea)", value="", height=140, key="cat_distritos_lines")

        if st.button("➕ Agregar distritos", use_container_width=True, key="cat_add_distritos"):
            if not canton_key:
                st.error("Primero crea/selecciona un cantón válido.")
            else:
                dists = [d.strip() for d in (distritos_lines or "").splitlines() if d.strip()]
                if not dists:
                    st.error("No hay distritos.")
                else:
                    # evitar duplicados exactos por (name,canton_key)
                    existing = set((x.get("name",""), x.get("canton_key","")) for x in cb["list_distrito"])
                    for d in dists:
                        nm = slugify_name(d)
                        # si name existe para mismo cantón, hacerlo único
                        if (nm, canton_key) in existing:
                            nm = asegurar_nombre_unico(nm, set(x.get("name","") for x in cb["list_distrito"]))
                        cb["list_distrito"].append({"name": nm, "label": d, "canton_key": canton_key})
                        existing.add((nm, canton_key))

                    st.session_state.choices_bank = cb
                    st.success(f"Se agregaron {len(dists)} distrito(s).")
                    st.rerun()

    st.markdown("---")
    st.subheader("Vista rápida")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**list_canton**")
        st.dataframe(pd.DataFrame(cb["list_canton"]).fillna(""), use_container_width=True, hide_index=True, height=260)
    with c2:
        st.markdown("**list_distrito**")
        st.dataframe(pd.DataFrame(cb["list_distrito"]).fillna(""), use_container_width=True, hide_index=True, height=260)

    if st.button("🧹 Quitar placeholders 'sin_catalogo'", use_container_width=True, key="cat_rm_placeholders"):
        cb["list_canton"] = [x for x in cb["list_canton"] if x.get("name") != "sin_catalogo"]
        cb["list_distrito"] = [x for x in cb["list_distrito"] if x.get("name") != "sin_catalogo"]
        st.session_state.choices_bank = cb
        st.success("Placeholders removidos.")
        st.rerun()

# ==========================================================================================
# E) VALIDACIONES (antes exportar) — para evitar errores en Survey123
# ==========================================================================================
def _parse_list_from_type(t: str) -> str | None:
    """
    type puede ser: select_one X, select_multiple Y
    retorna X o Y, si aplica.
    """
    tt = (t or "").strip()
    if tt.startswith("select_one "):
        return tt.replace("select_one ", "", 1).strip()
    if tt.startswith("select_multiple "):
        return tt.replace("select_multiple ", "", 1).strip()
    return None

def validar_formulario_estado() -> list[str]:
    errors = []
    bank = st.session_state.get("survey_bank", [])
    cb = st.session_state.get("choices_bank", {})

    # 1) names duplicados en survey_bank
    seen = {}
    for i, r in enumerate(bank):
        nm = str(r.get("name","")).strip()
        if not nm:
            continue
        if nm in seen:
            errors.append(f"Name duplicado en survey: '{nm}' (filas {seen[nm]} y {i}).")
        else:
            seen[nm] = i

    # 2) select_one/select_multiple referencian listas que no existen
    for i, r in enumerate(bank):
        t = str(r.get("type","")).strip()
        ln = _parse_list_from_type(t)
        if ln:
            if ln not in cb:
                errors.append(f"Fila {i}: type='{t}' referencia lista '{ln}' que NO existe en choices_bank.")

    # 3) choices inválidos (sin name/label)
    for ln, opts in cb.items():
        if not isinstance(opts, list):
            errors.append(f"choices_bank['{ln}'] no es lista.")
            continue
        for j, o in enumerate(opts):
            nm = str(o.get("name","")).strip()
            lb = str(o.get("label","")).strip()
            if not nm or not lb:
                errors.append(f"choices '{ln}' opción #{j} inválida (name/label requeridos).")

    # 4) list_distrito: canton_key vacío
    if "list_distrito" in cb:
        for j, o in enumerate(cb["list_distrito"]):
            ck = str(o.get("canton_key","")).strip()
            if ck == "":
                errors.append(f"list_distrito opción #{j} sin canton_key (requerido para choice_filter Cantón→Distrito).")

    # 5) begin_group field-list sin end_group posterior (estructura)
    # (rápido)
    tmp_stack = 0
    for i, r in enumerate(bank):
        if str(r.get("type","")).strip() == "begin_group" and str(r.get("appearance","")).strip() == "field-list":
            tmp_stack += 1
        if str(r.get("type","")).strip() == "end_group" and tmp_stack > 0:
            tmp_stack -= 1
    if tmp_stack != 0:
        errors.append("Estructura de páginas: hay begin_group field-list sin su end_group correspondiente (usa 'Páginas' → Reparar).")

    return errors

# En la pestaña Exportar, mostrar botón de validación extra
if active_tab == "Exportar":
    st.markdown("---")
    st.subheader("✅ Validación antes de exportar")
    if st.button("🔎 Ejecutar validación", use_container_width=True, key="btn_validate"):
        errs = validar_formulario_estado()
        if not errs:
            st.success("Sin errores críticos detectados. Listo para exportar.")
        else:
            st.error("Se encontraron problemas que pueden dar error en Survey123:")
            for e in errs:
                st.write("• " + e)

# ==========================================================================================
# FIN PARTE 10/10
# ==========================================================================================






