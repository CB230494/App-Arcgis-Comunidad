# -*- coding: utf-8 -*-
# ==========================================================================================
# App: Encuesta Comunidad → XLSForm para ArcGIS Survey123 (Páginas 1 a 5) + Cantón→Distrito + Glosario por página
#
# - Página 1: Introducción (logo + texto EXACTO indicado por el usuario)
# - Página 2: Consentimiento Informado (mismo texto) + ¿Acepta participar? (Sí/No)
#            + Si responde "No" => finaliza (end)
# - Página 3: Datos demográficos (Cantón/Distrito + Edad + Género + Escolaridad + Relación con la zona)
#            + Cantón→Distrito en cascada (choice_filter) con catálogo por lotes dentro de la app
# - Página 4: Percepción ciudadana de seguridad en el distrito (Preguntas 7, 7.1, 8, 8.1, 9, 10, 11)
#            + 7.1 relevante si 7 ∈ {"Muy inseguro","Inseguro"}
#            + 8.1 relevante si 8 ∈ {1,2,3,4,5}
#            + 9 con matriz (select_one por fila)
#            + 11 (ABIERTO) SIEMPRE (según la imagen: explica por qué considera inseguro el espacio elegido en 10)
# - Página 5: III. RIESGOS, DELITOS, VICTIMIZACIÓN Y EVALUACIÓN POLICIAL (Preguntas 12 a 18)
#            + Notas (note) como en las imágenes (sin crear columnas: bind::esri:fieldType="null")
#            + Condicionales: “Otro: ____” donde corresponde
#            + Validaciones para evitar contradicciones (“No se observa consumo” vs áreas; “No observa presencia” vs otras)
#
# - Glosario por página:
#   + Se agrega SOLO si hay coincidencias con términos del glosario en esa página
#   + El glosario queda DENTRO de la misma página (no crea navegación hacia adelante)
#   + Se muestra al final de la página si la persona elige "Sí" (NO obligatorio)
#
# - Exporta XLSForm (Excel) con hojas: survey / choices / settings
# - Importante: notas (note) NO crean columnas en la tabla (bind::esri:fieldType="null")
# ==========================================================================================

import re
from io import BytesIO
from datetime import datetime

import streamlit as st
import pandas as pd

# ==========================================================================================
# Configuración
# ==========================================================================================
st.set_page_config(page_title="Encuesta Comunidad — XLSForm (P1 a P5)", layout="wide")
st.title("🏘️ Encuesta Comunidad → XLSForm para ArcGIS Survey123 (Páginas 1 a 5)")

st.markdown("""
Genera un **XLSForm** listo para **ArcGIS Survey123** con páginas reales (Next/Back):
- **Página 1**: Introducción (logo + texto).
- **Página 2**: Consentimiento Informado (ordenado) + aceptación (Sí/No).
- **Página 3**: Datos demográficos (Cantón/Distrito en cascada).
- **Página 4**: Percepción ciudadana de seguridad en el distrito (7 a 11, con condicionales).
- **Página 5**: Riesgos sociales y situacionales en el distrito (12 a 18, con notas y validaciones).
- **Glosario por página**: solo se agrega cuando hay coincidencias con términos del glosario.
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
    """Genera y descarga el XLSForm (Excel)."""
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
    """Agrega una lista de choices (list_name/name/label)."""
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
        help="Debe coincidir con el archivo dentro de la carpeta `media/` del proyecto Survey123 (Connect)."
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
# Glosario (términos que coinciden por página)
# - Página 4: extorsión, daños/vandalismo (ya estaba)
# - Página 5: se agregan términos de “Riesgos sociales y situacionales…”
#   (Cuando nos pases el Word, aquí se amplía con el contenido exacto.)
# ==========================================================================================
GLOSARIO_DEFINICIONES = {
    # Página 4 (referencia ya existente)
    "Extorsión": (
        "Extorsión: El que, para procurar un lucro injusto, obligare a otro, mediante intimidación o amenaza, "
        "a realizar u omitir un acto o negocio en perjuicio de su patrimonio o del de un tercero."
    ),
    "Daños/vandalismo": (
        "Daños/vandalismo: El que destruyere, inutilizare, hiciere desaparecer o deteriorare bienes, "
        "sean de naturaleza pública o privada (incluidos bienes del Estado), en perjuicio de persona física o jurídica."
    ),

    # Página 5 (BASE – ampliable con tu Word)
    "Cuarterías": (
        "Cuarterías: Modalidad de alojamiento o vivienda en la que se alquilan cuartos o espacios reducidos, "
        "usualmente con servicios compartidos, pudiendo presentar condiciones de hacinamiento o informalidad."
    ),
    "Asentamientos informales o precarios": (
        "Asentamientos informales o precarios: Conjuntos habitacionales establecidos sin los permisos, "
        "planificación o infraestructura adecuados, con posibles carencias de servicios básicos y condiciones de habitabilidad."
    ),
    "Desvinculación escolar (deserción escolar)": (
        "Desvinculación escolar (deserción escolar): Interrupción o abandono del proceso educativo por parte "
        "de la persona estudiante, de manera temporal o definitiva."
    ),
    "Búnkeres": (
        "Búnkeres: Término usado para referirse a puntos o sitios identificados por la comunidad como lugares "
        "donde se presume la venta o distribución de drogas u otras actividades ilícitas (percepción/observación)."
    ),
    "Lotes baldíos": (
        "Lotes baldíos: Terrenos sin edificación o uso aparente, que pueden presentar abandono, maleza o falta de control."
    ),
    "Presencia de personas en situación de calle": (
        "Presencia de personas en situación de calle: Condición de personas que habitan o permanecen en espacios públicos "
        "por carecer de vivienda o alojamiento estable."
    ),
    "Personas en situación de ocio": (
        "Personas en situación de ocio: Presencia de personas sin actividad aparente en el espacio público; "
        "es una categoría descriptiva de percepción comunitaria, no un juicio de valor."
    ),
}

# ==========================================================================================
# Catálogo Cantón → Distrito (por lotes) — permitir múltiples distritos por cantón
# ==========================================================================================
if "choices_ext_rows" not in st.session_state:
    st.session_state.choices_ext_rows = []
if "choices_extra_cols" not in st.session_state:
    st.session_state.choices_extra_cols = set()

def _append_choice_unique(row: dict):
    key = (row.get("list_name"), row.get("name"))
    exists = any((r.get("list_name"), r.get("name")) == key for r in st.session_state.choices_ext_rows)
    if not exists:
        st.session_state.choices_ext_rows.append(row)

st.markdown("### 📚 Catálogo Cantón → Distrito (por lotes)")
with st.expander("Agrega un lote (un Cantón y uno o varios Distritos)", expanded=True):
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

            # columnas extra usadas por filtros/placeholder
            st.session_state.choices_extra_cols.update({"canton_key", "any"})

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
# Construcción XLSForm
# ==========================================================================================
def construir_xlsform(form_title: str, logo_media_name: str, idioma: str, version: str):
    survey_rows = []
    choices_rows = []

    # =========================
    # Choices base
    # =========================
    list_yesno = "yesno"
    add_choice_list(choices_rows, list_yesno, ["Sí", "No"])
    v_si = slugify_name("Sí")
    v_no = slugify_name("No")

    # Datos demográficos
    list_genero = "genero"
    add_choice_list(choices_rows, list_genero, ["Femenino", "Masculino", "Persona No Binaria", "Prefiero no decir"])

    list_escolaridad = "escolaridad"
    add_choice_list(choices_rows, list_escolaridad, [
        "Ninguna",
        "Primaria incompleta",
        "Primaria completa",
        "Secundaria incompleta",
        "Secundaria completa",
        "Técnico",
        "Universitaria incompleta",
        "Universitaria completa",
    ])

    list_relacion_zona = "relacion_zona"
    add_choice_list(choices_rows, list_relacion_zona, ["Vivo en la zona", "Trabajo en la zona", "Visito la zona", "Estudio en la zona"])

    # Página 4: Pregunta 7 (seguridad percibida)
    list_seguridad_5 = "seguridad_5"
    add_choice_list(choices_rows, list_seguridad_5, ["Muy inseguro", "Inseguro", "Ni seguro ni inseguro", "Seguro", "Muy seguro"])

    # Página 4: Pregunta 7.1 (multi)
    list_causas_inseguridad = "causas_inseguridad"
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
    add_choice_list(choices_rows, list_causas_inseguridad, causas_71)

    # Página 4: Pregunta 8 (escala 1-5)
    list_escala_1_5 = "escala_1_5"
    add_choice_list(choices_rows, list_escala_1_5, [
        "1 (Mucho Menos Seguro)",
        "2 (Menos Seguro)",
        "3 (Se mantiene igual)",
        "4 (Más Seguro)",
        "5 (Mucho Más Seguro)",
    ])

    # Página 4: Matriz
    list_matriz_1_5_na = "matriz_1_5_na"
    add_choice_list(choices_rows, list_matriz_1_5_na, [
        "Muy inseguro (1)",
        "Inseguro (2)",
        "Ni seguro ni inseguro (3)",
        "Seguro (4)",
        "Muy seguro (5)",
        "No aplica",
    ])

    # Página 4: Pregunta 10 (tipo de espacio más inseguro)
    list_tipo_espacio = "tipo_espacio"
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
    add_choice_list(choices_rows, list_tipo_espacio, tipos_10)

    # =========================
    # Página 5: Listas (12 a 18)
    # =========================
    list_prob_situacionales = "p12_prob_situacionales"
    p12_labels = [
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
    add_choice_list(choices_rows, list_prob_situacionales, p12_labels)

    list_carencias_inversion = "p13_carencias_inversion"
    p13_labels = [
        "Falta de oferta educativa",
        "Falta de oferta deportiva",
        "Falta de oferta recreativa",
        "Falta de actividades culturales",
    ]
    add_choice_list(choices_rows, list_carencias_inversion, p13_labels)

    list_consumo_drogas_donde = "p14_consumo_drogas_donde"
    p14_labels = [
        "Área privada",
        "Área pública",
        "No se observa consumo",
    ]
    add_choice_list(choices_rows, list_consumo_drogas_donde, p14_labels)

    list_def_infra_vial = "p15_def_infra_vial"
    p15_labels = [
        "Calles en mal estado",
        "Falta de señalización de tránsito",
        "Carencia o inexistencia de aceras",
    ]
    add_choice_list(choices_rows, list_def_infra_vial, p15_labels)

    list_bunkeres_espacios = "p16_bunkeres_espacios"
    p16_labels = [
        "Casa de habitación (Espacio Cerrado)",
        "Edificación abandonada",
        "Lote baldío",
        "Otro",
    ]
    add_choice_list(choices_rows, list_bunkeres_espacios, p16_labels)

    list_transporte_afect = "p17_transporte_afect"
    p17_labels = [
        "Informal (taxis piratas)",
        "Plataformas (digitales)",
    ]
    add_choice_list(choices_rows, list_transporte_afect, p17_labels)

    list_presencia_policial = "p18_presencia_policial"
    p18_labels = [
        "Falta de presencia policial",
        "Presencia policial insuficiente",
        "Presencia policial solo en ciertos horarios",
        "No observa presencia policial",
    ]
    add_choice_list(choices_rows, list_presencia_policial, p18_labels)

    # =========================
    # Utilidad: notes sin campo (para que NO salgan columnas vacías en la tabla)
    # =========================
    def add_note(name: str, label: str, relevant: str | None = None, media_image: str | None = None):
        row = {"type": "note", "name": name, "label": label, "bind::esri:fieldType": "null"}
        if relevant:
            row["relevant"] = relevant
        if media_image:
            row["media::image"] = media_image
        survey_rows.append(row)

    # =========================
    # Utilidad: glosario por página (solo términos que “coinciden”)
    # =========================
    def add_glosario_por_pagina(page_id: str, relevant_base: str, terminos: list[str]):
        """
        Agrega al final de la página un selector para ver glosario y, si marca Sí, muestra definiciones
        SOLO de los términos indicados que existan en GLOSARIO_DEFINICIONES.
        """
        terminos_existentes = [t for t in terminos if t in GLOSARIO_DEFINICIONES]
        if not terminos_existentes:
            return  # No hay coincidencias => no agregar glosario

        survey_rows.append({
            "type": f"select_one yesno",
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

    # =========================
    # Página 1: Introducción
    # =========================
    survey_rows.append({"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"})
    add_note("p1_logo", form_title, media_image=logo_media_name)
    add_note("p1_texto", INTRO_COMUNIDAD_EXACTA)
    survey_rows.append({"type": "end_group", "name": "p1_end"})

    # =========================
    # Página 2: Consentimiento
    # =========================
    survey_rows.append({"type": "begin_group", "name": "p2_consent", "label": "Consentimiento Informado", "appearance": "field-list"})
    add_note("p2_titulo", CONSENT_TITLE)

    for i, p in enumerate(CONSENT_PARRAFOS, start=1):
        add_note(f"p2_p_{i}", p)

    for j, b in enumerate(CONSENT_BULLETS, start=1):
        add_note(f"p2_b_{j}", f"• {b}")

    for k, c in enumerate(CONSENT_CIERRE, start=1):
        add_note(f"p2_c_{k}", c)

    survey_rows.append({
        "type": f"select_one {list_yesno}",
        "name": "acepta_participar",
        "label": "¿Acepta participar en esta encuesta?",
        "required": "yes",
        "appearance": "minimal"
    })
    survey_rows.append({"type": "end_group", "name": "p2_end"})

    # Finalizar si NO acepta
    survey_rows.append({
        "type": "end",
        "name": "fin_por_no",
        "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.",
        "relevant": f"${{acepta_participar}}='{v_no}'"
    })

    rel_si = f"${{acepta_participar}}='{v_si}'"

    # =========================
    # Página 3: Datos demográficos
    # =========================
    survey_rows.append({
        "type": "begin_group",
        "name": "p3_datos_demograficos",
        "label": "Datos demográficos",
        "appearance": "field-list",
        "relevant": rel_si
    })

    # Cantón
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

    # Distrito en cascada
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

    # Edad
    survey_rows.append({
        "type": "integer",
        "name": "edad_anos",
        "label": "3. Edad (en años cumplidos):",
        "required": "yes",
        "constraint": ". >= 18 and . <= 120",
        "constraint_message": "Debe ser un número entre 18 y 120.",
        "relevant": rel_si
    })

    # Género
    survey_rows.append({
        "type": f"select_one {list_genero}",
        "name": "genero",
        "label": "4. ¿Con cuál de estas opciones se identifica?",
        "required": "yes",
        "relevant": rel_si
    })

    # Escolaridad
    survey_rows.append({
        "type": f"select_one {list_escolaridad}",
        "name": "escolaridad",
        "label": "5. Escolaridad:",
        "required": "yes",
        "relevant": rel_si
    })

    # Relación con la zona
    survey_rows.append({
        "type": f"select_one {list_relacion_zona}",
        "name": "relacion_zona",
        "label": "6. ¿Cuál es su relación con la zona?",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({"type": "end_group", "name": "p3_end"})

    # =========================
    # Página 4: Percepción ciudadana de seguridad en el distrito (7 a 11)
    # =========================
    survey_rows.append({
        "type": "begin_group",
        "name": "p4_percepcion_distrito",
        "label": "Percepción ciudadana de seguridad en el distrito",
        "appearance": "field-list",
        "relevant": rel_si
    })

    # 7
    survey_rows.append({
        "type": f"select_one {list_seguridad_5}",
        "name": "p7_seguridad_distrito",
        "label": "7. ¿Qué tan seguro percibe usted el distrito donde reside o transita?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 7.1 relevante si 7 = Muy inseguro o Inseguro
    rel_71 = (
        f"({rel_si}) and ("
        f"${{p7_seguridad_distrito}}='{slugify_name('Muy inseguro')}' or "
        f"${{p7_seguridad_distrito}}='{slugify_name('Inseguro')}'"
        f")"
    )

    survey_rows.append({
        "type": f"select_multiple {list_causas_inseguridad}",
        "name": "p71_causas_inseguridad",
        "label": "7.1. Indique por qué considera el distrito inseguro (Marque todas las situaciones que usted percibe que ocurren con mayor frecuencia en su comunidad):",
        "required": "yes",
        "relevant": rel_71
    })

    add_note(
        "p71_nota_no_denuncia",
        "Esta pregunta recoge percepción general y no constituye denuncia.",
        relevant=rel_71
    )

    add_note(
        "p71_nota_descriptores",
        "Nota: Incluye descriptores (selección múltiple) además del espacio abierto. La respuesta abierta es para que la persona encuestada redacte su respuesta.",
        relevant=rel_71
    )

    survey_rows.append({
        "type": "text",
        "name": "p71_otro_detalle",
        "label": "Otro problema que considere importante (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_71}) and selected(${{p71_causas_inseguridad}}, '{slugify_name('Otro problema que considere importante')}')"
    })

    # 8
    survey_rows.append({
        "type": f"select_one {list_escala_1_5}",
        "name": "p8_comparacion_anno",
        "label": "8. ¿Cómo se percibe la seguridad en este distrito este año en comparación con el año anterior?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    add_note(
        "p8_nota_escala",
        "Nota: Se utiliza una escala ordinal del 1 al 5.",
        relevant=rel_si
    )

    # 8.1 relevante si p8 tiene cualquiera (1 a 5)
    rel_81 = (
        f"({rel_si}) and ("
        f"${{p8_comparacion_anno}}='{slugify_name('1 (Mucho Menos Seguro)')}' or "
        f"${{p8_comparacion_anno}}='{slugify_name('2 (Menos Seguro)')}' or "
        f"${{p8_comparacion_anno}}='{slugify_name('3 (Se mantiene igual)')}' or "
        f"${{p8_comparacion_anno}}='{slugify_name('4 (Más Seguro)')}' or "
        f"${{p8_comparacion_anno}}='{slugify_name('5 (Mucho Más Seguro)')}'"
        f")"
    )

    survey_rows.append({
        "type": "text",
        "name": "p81_indique_por_que",
        "label": "8.1. Indique por qué:",
        "required": "yes",
        "appearance": "multiline",
        "relevant": rel_81
    })

    # 9: Matriz
    add_note(
        "p9_instr",
        "9. Indique qué tan seguros percibe, en términos de seguridad, en los siguientes espacios de su Distrito:\n(Usar matriz de selección única por fila con la escala 1 a 5.)",
        relevant=rel_si
    )

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
            "type": f"select_one {list_matriz_1_5_na}",
            "name": name,
            "label": label,
            "required": "yes",
            "appearance": "minimal",
            "relevant": rel_si
        })

    add_note(
        "p9_nota",
        "Nota: La persona encuestada podrá seleccionar una de las opciones por cada línea de zona.",
        relevant=rel_si
    )

    # 10
    survey_rows.append({
        "type": f"select_one {list_tipo_espacio}",
        "name": "p10_tipo_espacio_mas_inseguro",
        "label": "10. Según su percepción, ¿cuál de los siguientes tipos de espacios del distrito considera más inseguro?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    add_note(
        "p10_nota",
        "Nota: Seleccione una única opción que, según su percepción, represente el tipo de espacio más inseguro del distrito.",
        relevant=rel_si
    )

    # 10 Otros (detalle)
    survey_rows.append({
        "type": "text",
        "name": "p10_otros_detalle",
        "label": "Otros (detalle):",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and (${{p10_tipo_espacio_mas_inseguro}}='{slugify_name('Otros')}')"
    })

    # 11 (ABIERTO) – SEGÚN IMAGEN: SIEMPRE (explica por qué es inseguro el espacio elegido en 10)
    survey_rows.append({
        "type": "text",
        "name": "p11_por_que_inseguro_tipo_espacio",
        "label": "11. Según su percepción, describa brevemente por qué considera inseguro el tipo de espacio seleccionado en la pregunta anterior.",
        "required": "no",
        "appearance": "multiline",
        "relevant": rel_si
    })
    add_note(
        "p11_nota",
        "Nota: La respuesta es de espacio abierto para detallar.",
        relevant=rel_si
    )

    # Glosario Página 4 (solo si hay coincidencias)
    # Referencia: extorsión y daños/vandalismo
    add_glosario_por_pagina(
        page_id="p4",
        relevant_base=rel_si,
        terminos=["Extorsión", "Daños/vandalismo"]
    )

    survey_rows.append({"type": "end_group", "name": "p4_end"})

    # =========================
    # Página 5: III. RIESGOS, DELITOS, VICTIMIZACIÓN Y EVALUACIÓN POLICIAL
    # =========================
    survey_rows.append({
        "type": "begin_group",
        "name": "p5_riesgos_delitos_victimizacion",
        "label": "III. RIESGOS, DELITOS, VICTIMIZACIÓN Y EVALUACIÓN POLICIAL",
        "appearance": "field-list",
        "relevant": rel_si
    })

    add_note(
        "p5_subtitulo",
        "Riesgos sociales y situacionales en el distrito",
        relevant=rel_si
    )

    add_note(
        "p5_intro",
        "A continuación, se presentará una lista de problemáticas que se catalogan como factores situacionales, con la finalidad de que seleccione aquellos que considere que ocurren en su distrito.",
        relevant=rel_si
    )

    # 12 (multi)
    survey_rows.append({
        "type": f"select_multiple {list_prob_situacionales}",
        "name": "p12_problematicas_distrito",
        "label": "12. Según su percepción u observación, seleccione las problemáticas que afectan su distrito:",
        "required": "yes",
        "relevant": rel_si
    })

    add_note(
        "p12_nota",
        "Nota: esta pregunta es de selección múltiple, se engloba estas problemáticas en una sola pregunta ya que ninguno de ellas se subdivide.",
        relevant=rel_si
    )

    # 12 Otro (detalle)
    survey_rows.append({
        "type": "text",
        "name": "p12_otro_detalle",
        "label": "Otro problema que considere importante:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p12_problematicas_distrito}}, '{slugify_name('Otro problema que considere importante')}')"
    })

    # 13 (multi)
    survey_rows.append({
        "type": f"select_multiple {list_carencias_inversion}",
        "name": "p13_carencias_inversion_social",
        "label": "13. En relación con la inversión social en su distrito, indique cuáles de las siguientes carencias identifica:",
        "required": "yes",
        "relevant": rel_si
    })

    add_note(
        "p13_nota",
        "Nota: esta pregunta es de selección múltiple",
        relevant=rel_si
    )

    # 14 (multi) + validación de coherencia
    # Si marca “No se observa consumo”, no debería marcar “Área privada” ni “Área pública”.
    n_no_obs = slugify_name("No se observa consumo")
    n_priv = slugify_name("Área privada")
    n_pub = slugify_name("Área pública")
    constraint_p14 = f"not(selected(., '{n_no_obs}') and (selected(., '{n_priv}') or selected(., '{n_pub}')))"

    survey_rows.append({
        "type": f"select_multiple {list_consumo_drogas_donde}",
        "name": "p14_donde_consumo_drogas",
        "label": "14. Según su percepción u observación, indique dónde se presenta consumo de drogas en el distrito:",
        "required": "yes",
        "constraint": constraint_p14,
        "constraint_message": "Si selecciona “No se observa consumo”, no puede seleccionar “Área privada” ni “Área pública”.",
        "relevant": rel_si
    })

    add_note(
        "p14_nota",
        "Nota: esta pregunta es de selección múltiple.",
        relevant=rel_si
    )

    # 15 (multi)
    survey_rows.append({
        "type": f"select_multiple {list_def_infra_vial}",
        "name": "p15_deficiencias_infra_vial",
        "label": "15. Indique las principales deficiencias de infraestructura vial que afectan su distrito:",
        "required": "yes",
        "relevant": rel_si
    })

    add_note(
        "p15_nota",
        "Nota: esta pregunta es de selección múltiple.",
        relevant=rel_si
    )

    # 16 (multi) + Otro (detalle)
    survey_rows.append({
        "type": f"select_multiple {list_bunkeres_espacios}",
        "name": "p16_bunkeres_espacios",
        "label": "16. Según su percepción u observación, indique en qué tipo de espacios se identifica la existencia de puntos de venta de drogas (búnkeres) en el distrito:",
        "required": "yes",
        "relevant": rel_si
    })

    add_note(
        "p16_nota",
        "Nota: esta pregunta es de selección múltiple",
        relevant=rel_si
    )

    survey_rows.append({
        "type": "text",
        "name": "p16_otro_detalle",
        "label": "Otro:",
        "required": "no",
        "appearance": "multiline",
        "relevant": f"({rel_si}) and selected(${{p16_bunkeres_espacios}}, '{slugify_name('Otro')}')"
    })

    # 17 (multi)
    survey_rows.append({
        "type": f"select_multiple {list_transporte_afect}",
        "name": "p17_transporte_afectacion",
        "label": "17. En relación con el transporte en su distrito, indique cuáles situaciones representan una afectación:",
        "required": "yes",
        "relevant": rel_si
    })

    add_note(
        "p17_nota",
        "Nota: esta pregunta es de selección múltiple",
        relevant=rel_si
    )

    # 18 (multi) + validación de coherencia
    # Si marca “No observa presencia policial”, no debería marcar las otras.
    n_no_pres = slugify_name("No observa presencia policial")
    n_falta = slugify_name("Falta de presencia policial")
    n_insuf = slugify_name("Presencia policial insuficiente")
    n_hor = slugify_name("Presencia policial solo en ciertos horarios")
    constraint_p18 = f"not(selected(., '{n_no_pres}') and (selected(., '{n_falta}') or selected(., '{n_insuf}') or selected(., '{n_hor}')))"

    survey_rows.append({
        "type": f"select_multiple {list_presencia_policial}",
        "name": "p18_presencia_policial",
        "label": "18. En relación con la presencia policial en su distrito, indique cuál de las siguientes situaciones identifica:",
        "required": "yes",
        "constraint": constraint_p18,
        "constraint_message": "Si selecciona “No observa presencia policial”, no seleccione otras opciones simultáneamente.",
        "relevant": rel_si
    })

    add_note(
        "p18_nota",
        "Nota: Selección múltiple.",
        relevant=rel_si
    )

    # Glosario Página 5 (solo si hay coincidencias)
    add_glosario_por_pagina(
        page_id="p5",
        relevant_base=rel_si,
        terminos=[
            "Cuarterías",
            "Asentamientos informales o precarios",
            "Desvinculación escolar (deserción escolar)",
            "Búnkeres",
            "Lotes baldíos",
            "Presencia de personas en situación de calle",
            "Personas en situación de ocio",
        ]
    )

    survey_rows.append({"type": "end_group", "name": "p5_end"})

    # =========================
    # Integrar catálogo Cantón→Distrito en choices
    # =========================
    for r in st.session_state.choices_ext_rows:
        choices_rows.append(dict(r))

    # =========================
    # DataFrames
    # =========================
    survey_cols = [
        "type", "name", "label", "required", "appearance",
        "relevant", "choice_filter",
        "constraint", "constraint_message",
        "media::image",
        "bind::esri:fieldType"
    ]
    df_survey = pd.DataFrame(survey_rows, columns=survey_cols).fillna("")

    # choices: incluir columnas extra si existen (canton_key, any)
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
# Exportar
# ==========================================================================================
st.markdown("---")
st.subheader("📦 Generar XLSForm (Survey123)")

idioma = st.selectbox("Idioma (default_language)", options=["es", "en"], index=0)
version_auto = datetime.now().strftime("%Y%m%d%H%M")
version = st.text_input("Versión (settings.version)", value=version_auto)

if st.button("🧮 Construir XLSForm", use_container_width=True):
    # Validación mínima: que exista al menos un cantón y un distrito
    has_canton = any(r.get("list_name") == "list_canton" and r.get("name") not in ("__pick_canton__",) for r in st.session_state.choices_ext_rows)
    has_distrito = any(r.get("list_name") == "list_distrito" and r.get("name") not in ("__pick_distrito__",) for r in st.session_state.choices_ext_rows)

    if not has_canton or not has_distrito:
        st.warning("Aún no has cargado catálogo Cantón→Distrito. Puedes construir igual, pero en Survey123 verás solo placeholders.")

    df_survey, df_choices, df_settings = construir_xlsform(
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
            use_container_width=True
        )

    st.info("""
**Cómo usar en Survey123 Connect**
1) Crear encuesta **desde archivo** y seleccionar el XLSForm descargado.  
2) Copiar el logo dentro de la carpeta **media/** del proyecto, con el **mismo nombre** que pusiste en `media::image`.  
3) Verás páginas con **Siguiente/Anterior** (porque `settings.style = pages`).  
4) El **glosario por página** aparece al final de cada sección solo si la persona marca **Sí** (no es obligatorio).  
5) Las **notas** no generarán columnas vacías en la tabla (porque usan `bind::esri:fieldType = null`).  
""")
