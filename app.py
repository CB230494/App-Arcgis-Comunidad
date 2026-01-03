```python
# -*- coding: utf-8 -*-
# ==========================================================================================
# App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 4)
# - Página 1: Introducción con logo + texto (exacto)
# - Página 2: Consentimiento Informado (mismo texto) + ¿Acepta participar? (Sí/No)
#            + Si responde "No" => finaliza (end)
# - Página 3: Datos demográficos (Cantón/Distrito en cascada + edad + género + escolaridad + relación zona)
# - Página 4: Percepción ciudadana de seguridad (preguntas 7, 7.1, 8, 8.1, 9 (matriz por filas), 10)
# - Glosario por sección SOLO si hay coincidencias con el glosario proporcionado:
#            + En esta versión, se detectan coincidencias en Página 4 (términos como Extorsión, Hurto, etc.)
#            + Se agrega una página adicional "Glosario — <Sección>" a la que se accede de forma opcional
# - Catálogo Cantón → Distrito (por lotes) para integrarlo al XLSForm (choices + choice_filter)
# - Exporta XLSForm (Excel) con hojas: survey / choices / settings
# ==========================================================================================

import re
from io import BytesIO
from datetime import datetime

import streamlit as st
import pandas as pd

# ==========================================================================================
# Configuración
# ==========================================================================================
st.set_page_config(page_title="Encuesta Comunidad — XLSForm Survey123 (P1 a P4)", layout="wide")
st.title("Encuesta Comunidad — XLSForm Survey123 (Introducción + Consentimiento + Datos Demográficos + Percepción)")

st.markdown("""
Genera un **XLSForm** listo para **ArcGIS Survey123** con páginas reales (Next/Back):
- **Página 1**: Introducción (logo + texto).
- **Página 2**: Consentimiento Informado (ordenado) + aceptación.
- **Página 3**: Datos demográficos (Cantón/Distrito en cascada + demás preguntas).
- **Página 4**: Percepción ciudadana de seguridad (preguntas 7 a 10, con condicionales y matriz).
- **Glosario**: se agrega **solo** en secciones donde haya términos coincidentes (opcional).
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
    for lab in labels:
        choices_rows.append({
            "list_name": list_name,
            "name": slugify_name(lab),
            "label": lab
        })

# ==========================================================================================
# Catálogo Cantón → Distrito (por lotes)
# ==========================================================================================
if "choices_cd_rows" not in st.session_state:
    st.session_state.choices_cd_rows = []
if "choices_cd_extra_cols" not in st.session_state:
    st.session_state.choices_cd_extra_cols = set()

def _append_choice_unique(row: dict):
    """Inserta fila en choices evitando duplicados por (list_name,name)."""
    key = (row.get("list_name"), row.get("name"))
    exists = any((r.get("list_name"), r.get("name")) == key for r in st.session_state.choices_cd_rows)
    if not exists:
        st.session_state.choices_cd_rows.append(row)

st.markdown("### 📚 Catálogo Cantón → Distrito (por lotes)")
with st.expander("Agrega un lote (un Cantón, un Distrito)", expanded=True):
    col_c1, col_c2 = st.columns(2)
    canton_txt = col_c1.text_input("Cantón (una vez)", value="")
    distrito_txt = col_c2.text_input("Distrito (una vez)", value="")

    col_b1, col_b2, col_b3 = st.columns([1, 1, 2])
    add_lote = col_b1.button("Agregar lote", type="primary", use_container_width=True)
    clear_all = col_b2.button("Limpiar catálogo", use_container_width=True)

    if clear_all:
        st.session_state.choices_cd_rows = []
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
            st.session_state.choices_cd_extra_cols.update({"canton_key", "any"})

            # Placeholders (una sola vez por lista)
            _append_choice_unique({"list_name": "list_canton",  "name": "__pick_canton__",  "label": "— escoja un cantón —"})
            _append_choice_unique({"list_name": "list_distrito","name": "__pick_distrito__","label": "— escoja un cantón —", "any": "1"})

            # Cantón
            _append_choice_unique({"list_name": "list_canton", "name": slug_c, "label": c})

            # Distrito con llave cantón
            _append_choice_unique({"list_name": "list_distrito", "name": slug_d, "label": d, "canton_key": slug_c})

            st.success(f"Lote agregado: {c} → {d}")

if st.session_state.choices_cd_rows:
    st.dataframe(pd.DataFrame(st.session_state.choices_cd_rows), use_container_width=True, hide_index=True, height=240)

# ==========================================================================================
# Inputs (logo + lugar/delegación)
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
    lugar = st.text_input("Nombre del lugar / comunidad", value="San Carlos Oeste")
    logo_media_name = st.text_input(
        "Nombre de archivo para `media::image`",
        value=st.session_state.get("_logo_name", "001.png"),
        help="Debe coincidir con el archivo dentro de la carpeta `media/` del proyecto Survey123 (Connect)."
    )

form_title = f"Encuesta Comunidad – {lugar.strip()}" if lugar.strip() else "Encuesta Comunidad"
st.markdown(f"### {form_title}")

# ==========================================================================================
# Textos EXACTOS solicitados (P1 y P2)
# ==========================================================================================
INTRO_COMUNIDAD_EXACTA = (
    "Con el fin de hacer más segura nuestra comunidad, deseamos concentrarnos en los \n"
    "problemas de seguridad más importantes. Queremos trabajar en conjunto con el gobierno \n"
    "local, otras instituciones y la comunidad para reducir los delitos y riesgos que afectan a las \n"
    "personas.\n"
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
# Glosario (solo términos coincidentes con Página 4 en este bloque)
# ==========================================================================================
GLOSARIO_DEFINICIONES = {
    "Extorsión": "Quien, para procurar un lucro injusto, obligue a otra persona, mediante intimidación o amenaza, a realizar u omitir un acto con un perjuicio patrimonial para sí mismo o para un tercero.",
    "Hurto": "Quien se apodere ilegítimamente de una cosa mueble, total o parcialmente ajena, aprovechándose del descuido o sin emplear fuerza sobre las cosas ni violencia o intimidación sobre las personas.",
    "Receptación": "Quien adquiera, reciba u oculte dinero, cosas o bienes de origen ilícito, o intervenga en su adquisición, recepción u ocultación, con conocimiento de que provienen de un hecho delictivo.",
    "Contrabando": "Quien introduzca o extraiga mercancías, o las transporte, almacene, adquiera o comercialice, eludiendo el control aduanero o incumpliendo las formalidades y controles exigidos por la normativa aplicable.",
    "Delitos sexuales": "Conductas que atentan contra la libertad e integridad sexual de las personas; incluyen, entre otros, violación, abusos sexuales y acoso sexual.",
    "Daños/Vandalismo": "Quien destruya, inutilice, haga desaparecer o deteriore bienes ajenos o de dominio público (bienes del Estado), contra persona física o jurídica.",
    "Estafa o defraudación": "Quien, induciendo o manteniendo en error a otra persona, obtenga un provecho patrimonial indebido para sí o para un tercero, causando un perjuicio al patrimonio ajeno."
}

# ==========================================================================================
# Construcción XLSForm
# ==========================================================================================
def construir_xlsform(form_title: str, logo_media_name: str, idioma: str, version: str):
    survey_rows = []
    choices_rows = []

    # =========================
    # Choices (listas)
    # =========================
    list_yesno = "yesno"
    v_si = slugify_name("Sí")
    v_no = slugify_name("No")
    add_choice_list(choices_rows, list_yesno, ["Sí", "No"])

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

    list_relacion = "relacion_zona"
    add_choice_list(choices_rows, list_relacion, ["Vivo en la zona", "Trabajo en la zona", "Visito la zona", "Estudio en la zona"])

    list_edad = "edad_rangos"
    add_choice_list(choices_rows, list_edad, ["18 a 29 años", "30 a 44 años", "45 a 59 años", "60 años o más"])

    # Página 4 - escala 1..5 + No aplica
    list_escala_1_5_na = "escala_1_5_na"
    add_choice_list(choices_rows, list_escala_1_5_na, [
        "Muy inseguro (1)",
        "Inseguro (2)",
        "Ni seguro ni inseguro (3)",
        "Seguro (4)",
        "Muy seguro (5)",
        "No aplica"
    ])

    # Página 4 - pregunta 7 (única)
    list_perc_7 = "perc_seg_7"
    add_choice_list(choices_rows, list_perc_7, [
        "Muy inseguro",
        "Inseguro",
        "Ni seguro ni inseguro",
        "Seguro",
        "Muy seguro"
    ])

    # Página 4 - 7.1 (múltiple)
    list_71 = "situaciones_71"
    add_choice_list(choices_rows, list_71, [
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

    # Página 4 - 8 (ordinal)
    list_8 = "comparacion_8"
    add_choice_list(choices_rows, list_8, [
        "1 (Mucho Menos Seguro)",
        "2 (Menos Seguro)",
        "3 (Se mantiene igual)",
        "4 (Más Seguro)",
        "5 (Mucho Más Seguro)"
    ])

    # Página 4 - 10 (única)
    list_10 = "espacio_mas_inseguro_10"
    add_choice_list(choices_rows, list_10, [
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

    # =========================
    # Catálogo Cantón → Distrito (choices)
    # =========================
    for r in st.session_state.choices_cd_rows:
        choices_rows.append(dict(r))

    # =========================
    # Helpers internos para “no guardar columnas” en notas (reduce columnas vacías)
    # =========================
    def _note(name: str, label: str, relevant: str = ""):
        return {
            "type": "note",
            "name": name,
            "label": label,
            "relevant": relevant,
            "bind::esri:fieldType": "null"
        }

    # =========================
    # Página 1: Introducción
    # =========================
    survey_rows.append({"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list", "bind::esri:fieldType": "null"})
    survey_rows.append({"type": "note", "name": "p1_logo", "label": form_title, "media::image": logo_media_name, "bind::esri:fieldType": "null"})
    survey_rows.append(_note("p1_texto", INTRO_COMUNIDAD_EXACTA))
    survey_rows.append({"type": "end_group", "name": "p1_end", "bind::esri:fieldType": "null"})

    # =========================
    # Página 2: Consentimiento
    # =========================
    survey_rows.append({"type": "begin_group", "name": "p2_consent", "label": "Consentimiento Informado", "appearance": "field-list", "bind::esri:fieldType": "null"})
    survey_rows.append(_note("p2_titulo", CONSENT_TITLE))

    for i, p in enumerate(CONSENT_PARRAFOS, start=1):
        survey_rows.append(_note(f"p2_p_{i}", p))

    for j, b in enumerate(CONSENT_BULLETS, start=1):
        survey_rows.append(_note(f"p2_b_{j}", f"• {b}"))

    for k, c in enumerate(CONSENT_CIERRE, start=1):
        survey_rows.append(_note(f"p2_c_{k}", c))

    survey_rows.append({
        "type": f"select_one {list_yesno}",
        "name": "acepta_participar",
        "label": "¿Acepta participar en esta encuesta?",
        "required": "yes",
        "appearance": "minimal"
    })
    survey_rows.append({"type": "end_group", "name": "p2_end", "bind::esri:fieldType": "null"})

    # Finalizar si NO acepta
    survey_rows.append({
        "type": "end",
        "name": "fin_por_no",
        "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.",
        "relevant": f"${{acepta_participar}}='{v_no}'",
        "bind::esri:fieldType": "null"
    })

    # Base relevante: solo si acepta Sí
    rel_si = f"${{acepta_participar}}='{v_si}'"

    # =========================
    # Página 3: Datos demográficos
    # =========================
    survey_rows.append({"type": "begin_group", "name": "p3_datos_demograficos", "label": "I. DATOS DEMOGRÁFICOS", "appearance": "field-list", "relevant": rel_si, "bind::esri:fieldType": "null"})

    # Cantón (select_one list_canton) + constraint para placeholder
    survey_rows.append({
        "type": "select_one list_canton",
        "name": "canton",
        "label": "1. Cantón:",
        "required": "yes",
        "appearance": "minimal",
        "constraint": ". != '__pick_canton__'",
        "constraint_message": "Seleccione un cantón válido.",
        "relevant": rel_si
    })

    # Distrito (select_one list_distrito) con filtro cascada + placeholder
    survey_rows.append({
        "type": "select_one list_distrito",
        "name": "distrito",
        "label": "2. Distrito:",
        "required": "yes",
        "appearance": "minimal",
        "choice_filter": "canton_key=${canton} or any='1'",
        "constraint": ". != '__pick_distrito__'",
        "constraint_message": "Seleccione un distrito válido.",
        "relevant": rel_si
    })

    # Edad por rangos (como en el formato)
    survey_rows.append({
        "type": f"select_one {list_edad}",
        "name": "edad_rango",
        "label": "3. Edad (en años cumplidos): marque con una X la categoría que incluya su edad.",
        "required": "yes",
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
        "type": f"select_one {list_relacion}",
        "name": "relacion_zona",
        "label": "6. ¿Cuál es su relación con la zona?",
        "required": "yes",
        "relevant": rel_si
    })

    survey_rows.append({"type": "end_group", "name": "p3_end", "bind::esri:fieldType": "null"})

    # =========================
    # Página 4: Percepción ciudadana
    # =========================
    survey_rows.append({"type": "begin_group", "name": "p4_percepcion", "label": "II. PERCEPCIÓN CIUDADANA DE SEGURIDAD EN EL DISTRITO", "appearance": "field-list", "relevant": rel_si, "bind::esri:fieldType": "null"})

    # 7
    survey_rows.append({
        "type": f"select_one {list_perc_7}",
        "name": "p7_percepcion_seguridad",
        "label": "7. ¿Qué tan seguro percibe usted el distrito donde reside o transita?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_7_inseguro = f"({rel_si}) and (${{p7_percepcion_seguridad}}='{slugify_name('Muy inseguro')}' or ${{p7_percepcion_seguridad}}='{slugify_name('Inseguro')}')"

    # 7.1
    survey_rows.append({
        "type": f"select_multiple {list_71}",
        "name": "p71_motivos_inseguridad",
        "label": "7.1. Indique por qué considera el distrito inseguro (Marque todas las situaciones que usted percibe que ocurren con mayor frecuencia en su comunidad):",
        "required": "yes",
        "relevant": rel_7_inseguro
    })

    # 7.1 (otro) si selecciona “Otro problema…”
    rel_71_otro = f"({rel_7_inseguro}) and selected(${{p71_motivos_inseguridad}}, '{slugify_name('Otro problema que considere importante')}')"
    survey_rows.append({
        "type": "text",
        "name": "p71_otro_detalle",
        "label": "Indique el otro problema que considere importante:",
        "required": "yes",
        "appearance": "multiline",
        "relevant": rel_71_otro
    })

    # Nota (no constituye denuncia)
    survey_rows.append(_note(
        "p7_nota_no_denuncia",
        "Esta pregunta recoge percepción general y no constituye denuncia.",
        relevant=rel_si
    ))

    # 8
    survey_rows.append({
        "type": f"select_one {list_8}",
        "name": "p8_comparacion_anno",
        "label": "8. ¿Cómo se percibe la seguridad en este distrito este año en comparación con el año anterior?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 8.1 (siempre después de 8)
    survey_rows.append({
        "type": "text",
        "name": "p81_indique_porque",
        "label": "8.1. Indique por qué:",
        "required": "yes",
        "appearance": "multiline",
        "relevant": rel_si
    })

    # 9 (matriz: selección única por fila con escala 1 a 5 + No aplica)
    survey_rows.append(_note(
        "p9_instr",
        "9. Indique qué tan seguros percibe, en términos de seguridad, en los siguientes espacios de su Distrito: (Usar matriz de selección única por fila con la escala 1 a 5.)",
        relevant=rel_si
    ))

    filas_p9 = [
        ("p9_discotecas", "Discotecas, bares, sitios de entretenimiento"),
        ("p9_recreativos", "Espacios recreativos (parques, play, plaza de deportes)"),
        ("p9_residencia", "Lugar de residencia (casa de habitación)"),
        ("p9_paradas", "Paradas y/o estaciones de buses, taxis, trenes"),
        ("p9_puentes", "Puentes peatonales"),
        ("p9_transporte", "Transporte público"),
        ("p9_bancaria", "Zona bancaria"),
        ("p9_comercio", "Zona de comercio"),
        ("p9_residenciales", "Zonas residenciales (calles y barrios, distinto a su casa)"),
        ("p9_zonas_francas", "Zonas francas"),
        ("p9_turisticos", "Lugares de interés turístico"),
        ("p9_centros_educ", "Centros educativos"),
        ("p9_iluminacion", "Zonas con deficiencia de iluminación"),
    ]

    for nm, lab in filas_p9:
        survey_rows.append({
            "type": f"select_one {list_escala_1_5_na}",
            "name": nm,
            "label": lab,
            "required": "yes",
            "appearance": "minimal",
            "relevant": rel_si
        })

    survey_rows.append(_note(
        "p9_nota_filas",
        "Nota: La persona encuestada podrá seleccionar una de las opciones por cada línea de zona.",
        relevant=rel_si
    ))

    # 10
    survey_rows.append({
        "type": f"select_one {list_10}",
        "name": "p10_tipo_mas_inseguro",
        "label": "10. Según su percepción, ¿cuál de los siguientes tipos de espacios del distrito considera más inseguro?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_10_otros = f"({rel_si}) and (${{p10_tipo_mas_inseguro}}='{slugify_name('Otros')}')"
    survey_rows.append({
        "type": "text",
        "name": "p10_otro_especifique",
        "label": "Especifique cuál otro:",
        "required": "yes",
        "appearance": "multiline",
        "relevant": rel_10_otros
    })

    # =========================
    # Glosario opcional SOLO si hay coincidencias (aquí: Página 4)
    # =========================
    # Términos que coinciden con texto/opciones de P4:
    glosario_p4_terminos = [
        "Extorsión",
        "Hurto",
        "Receptación",
        "Contrabando",
        "Delitos sexuales",
        "Daños/Vandalismo",
        "Estafa o defraudación",
    ]

    # Acceso opcional (no requerido)
    survey_rows.append({
        "type": f"select_one {list_yesno}",
        "name": "p4_ir_glosario",
        "label": "¿Desea acceder al glosario de esta sección?",
        "required": "",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_p4_glos = f"({rel_si}) and (${{p4_ir_glosario}}='{v_si}')"

    # Página “Glosario — Sección”
    survey_rows.append({"type": "end_group", "name": "p4_end", "bind::esri:fieldType": "null"})

    survey_rows.append({
        "type": "begin_group",
        "name": "p4_glosario",
        "label": "Glosario — II. Percepción ciudadana de seguridad",
        "appearance": "field-list",
        "relevant": rel_p4_glos,
        "bind::esri:fieldType": "null"
    })

    survey_rows.append(_note(
        "p4_glosario_nota",
        "A continuación se muestran definiciones de términos utilizados en esta sección.",
        relevant=rel_p4_glos
    ))

    for i, termino in enumerate(glosario_p4_terminos, start=1):
        definicion = GLOSARIO_DEFINICIONES.get(termino, "")
        survey_rows.append(_note(
            f"p4_glos_{i}",
            f"{termino}: {definicion}",
            relevant=rel_p4_glos
        ))

    survey_rows.append(_note(
        "p4_glosario_volver",
        "Para regresar, utilice el botón «Atrás» y continúe con la encuesta.",
        relevant=rel_p4_glos
    ))

    survey_rows.append({"type": "end_group", "name": "p4_glosario_end", "bind::esri:fieldType": "null"})

    # =========================
    # DataFrames
    # =========================
    survey_cols = [
        "type", "name", "label", "required", "appearance",
        "relevant", "choice_filter", "media::image",
        "constraint", "constraint_message", "hint",
        "bind::esri:fieldType"
    ]
    df_survey = pd.DataFrame(survey_rows, columns=survey_cols).fillna("")

    # choices: incluir columnas extra si existen
    choices_cols_base = ["list_name", "name", "label"]
    extra_cols = sorted(set().union(*[set(r.keys()) for r in choices_rows]) - set(choices_cols_base)) if choices_rows else []
    df_choices = pd.DataFrame(choices_rows, columns=choices_cols_base + extra_cols).fillna("")

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
            "📥 Descargar logo para carpeta media/ (Survey123 Connect)",
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
""")
```
