# -*- coding: utf-8 -*-
# ==========================================================================================
# App: XLSForm Survey123 — Comunidad (3 páginas)
# - Página 1: Introducción con logo + texto EXACTO
# - Página 2: Consentimiento Informado ORDENADO + ¿Acepta participar? (Sí/No)
#            + Si responde "No" => finaliza (end)
# - Página 3: Datos Demográficos (según imagen):
#            1) Cantón (desplegable)  [catálogo manual por lotes]
#            2) Distrito (desplegable) [cascada por cantón]
#            3) Edad (rango) (select_one)
#            4) Identidad (select_one)
#            5) Escolaridad (select_one)
#            6) Relación con la zona (select_one)
# - Exporta XLSForm (Excel) con hojas: survey / choices / settings
# - Incluye sección para cargar Cantón → Distrito (manual por lotes) para integrar en ArcGIS Survey123
# - NO genera Word / NO genera PDF
# - Glosario por página: SOLO si hay similitudes (en estas 3 páginas NO se agrega glosario)
# ==========================================================================================

import re
from io import BytesIO
from datetime import datetime

import streamlit as st
import pandas as pd

# ==========================================================================================
# Configuración UI
# ==========================================================================================
st.set_page_config(page_title="XLSForm Survey123 — Comunidad (P1 a P3)", layout="wide")
st.title("XLSForm Survey123 — Comunidad (Introducción + Consentimiento + Datos Demográficos)")

st.markdown("""
Genera un **XLSForm** listo para **ArcGIS Survey123** con páginas reales (Next/Back):
- **Página 1**: Introducción (logo + texto exacto).
- **Página 2**: Consentimiento Informado (ordenado) + aceptación.
- **Página 3**: Datos Demográficos (cantón/distrito en cascada + preguntas de la imagen).
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
                ws.set_column(col_idx, col_idx, max(14, min(70, len(str(col_name)) + 10)))

    buffer.seek(0)
    st.download_button(
        label=f"📥 Descargar XLSForm ({nombre_archivo})",
        data=buffer,
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

def add_choice_list(choices_rows, list_name: str, labels: list[str]):
    for lab in labels:
        choices_rows.append({
            "list_name": list_name,
            "name": slugify_name(lab),
            "label": lab
        })

def _append_choice_unique(store_rows, row: dict):
    key = (row.get("list_name"), row.get("name"))
    exists = any((r.get("list_name"), r.get("name")) == key for r in store_rows)
    if not exists:
        store_rows.append(row)

# ==========================================================================================
# Estado: catálogo Cantón → Distrito
# ==========================================================================================
if "choices_ext_rows_cd" not in st.session_state:
    st.session_state.choices_ext_rows_cd = []
if "choices_extra_cols_cd" not in st.session_state:
    st.session_state.choices_extra_cols_cd = set()

st.markdown("### 📚 Catálogo Cantón → Distrito (por lotes) — para ArcGIS Survey123")
with st.expander("Agrega un lote (un Cantón y varios Distritos)", expanded=True):
    col_a, col_b = st.columns(2)
    canton_txt = col_a.text_input("Cantón (una vez)", value="")
    distritos_txt = col_b.text_area("Distritos del cantón (uno por línea)", value="", height=120)

    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
    add_lote = col_btn1.button("Agregar lote", type="primary", use_container_width=True)
    clear_all = col_btn2.button("Limpiar catálogo", use_container_width=True)

    if clear_all:
        st.session_state.choices_ext_rows_cd = []
        st.session_state.choices_extra_cols_cd = set()
        st.success("Catálogo limpiado.")

    if add_lote:
        c = canton_txt.strip()
        distritos = [d.strip() for d in distritos_txt.splitlines() if d.strip()]

        if not c or not distritos:
            st.error("Debes indicar Cantón y al menos un Distrito.")
        else:
            slug_c = slugify_name(c)

            # columnas extra para filtro y placeholder
            st.session_state.choices_extra_cols_cd.update({"canton_key", "any"})

            # placeholders (una sola vez por lista)
            _append_choice_unique(st.session_state.choices_ext_rows_cd, {
                "list_name": "list_canton",
                "name": "__pick_canton__",
                "label": "— escoja un cantón —"
            })
            _append_choice_unique(st.session_state.choices_ext_rows_cd, {
                "list_name": "list_distrito",
                "name": "__pick_distrito__",
                "label": "— escoja un cantón —",
                "any": "1"
            })

            # Cantón
            _append_choice_unique(st.session_state.choices_ext_rows_cd, {
                "list_name": "list_canton",
                "name": slug_c,
                "label": c
            })

            # Distritos (cascada por canton_key)
            usados = set()
            for d in distritos:
                slug_d = slugify_name(d)
                if slug_d in usados:
                    # si el mismo distrito se repite en el lote, lo ignoramos
                    continue
                usados.add(slug_d)

                _append_choice_unique(st.session_state.choices_ext_rows_cd, {
                    "list_name": "list_distrito",
                    "name": slug_d,
                    "label": d,
                    "canton_key": slug_c
                })

            st.success(f"Lote agregado: {c} → {len(usados)} distritos.")

if st.session_state.choices_ext_rows_cd:
    st.dataframe(
        pd.DataFrame(st.session_state.choices_ext_rows_cd),
        use_container_width=True,
        hide_index=True,
        height=240
    )

# ==========================================================================================
# Inputs (logo + lugar)
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
INTRO_COMUNIDAD_EXACTO = (
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
# Construcción XLSForm
# ==========================================================================================
def construir_xlsform(form_title: str, logo_media_name: str, idioma: str, version: str):
    survey_rows = []
    choices_rows = []

    # -------------------------
    # Choices base
    # -------------------------
    list_yesno = "yesno"
    v_si = slugify_name("Sí")
    v_no = slugify_name("No")
    add_choice_list(choices_rows, list_yesno, ["Sí", "No"])

    list_edad = "edad_rangos"
    add_choice_list(choices_rows, list_edad, ["18 a 29 años", "30 a 44 años", "45 a 59 años", "60 años o más"])

    list_identidad = "identidad"
    add_choice_list(choices_rows, list_identidad, ["Femenino", "Masculino", "Persona No Binaria", "Prefiero no decir"])

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

    # -------------------------
    # Página 1: Introducción
    # -------------------------
    survey_rows.append({"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"})
    survey_rows.append({"type": "note", "name": "p1_logo", "label": form_title, "media::image": logo_media_name})
    survey_rows.append({"type": "note", "name": "p1_texto", "label": INTRO_COMUNIDAD_EXACTO})
    survey_rows.append({"type": "end_group", "name": "p1_end"})

    # -------------------------
    # Página 2: Consentimiento + aceptación
    # -------------------------
    survey_rows.append({"type": "begin_group", "name": "p2_consent", "label": "Consentimiento Informado", "appearance": "field-list"})
    survey_rows.append({"type": "note", "name": "p2_titulo", "label": CONSENT_TITLE})

    for i, p in enumerate(CONSENT_PARRAFOS, start=1):
        survey_rows.append({"type": "note", "name": f"p2_p_{i}", "label": p})

    for j, b in enumerate(CONSENT_BULLETS, start=1):
        survey_rows.append({"type": "note", "name": f"p2_b_{j}", "label": f"• {b}"})

    for k, c in enumerate(CONSENT_CIERRE, start=1):
        survey_rows.append({"type": "note", "name": f"p2_c_{k}", "label": c})

    survey_rows.append({
        "type": f"select_one {list_yesno}",
        "name": "acepta_participar",
        "label": "¿Acepta participar en esta encuesta?",
        "required": "yes",
        "appearance": "minimal"
    })
    survey_rows.append({"type": "end_group", "name": "p2_end"})

    # Si NO acepta => finaliza
    survey_rows.append({
        "type": "end",
        "name": "fin_por_no",
        "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.",
        "relevant": f"${{acepta_participar}}='{v_no}'"
    })

    rel_si = f"${{acepta_participar}}='{v_si}'"

    # -------------------------
    # Página 3: Datos Demográficos
    # (Cantón/Distrito se cargan desde el catálogo manual)
    # -------------------------
    survey_rows.append({
        "type": "begin_group",
        "name": "p3_demograficos",
        "label": "I. DATOS DEMOGRÁFICOS",
        "appearance": "field-list",
        "relevant": rel_si
    })

    # 1. Cantón (desplegable) — lista list_canton
    survey_rows.append({
        "type": "select_one list_canton",
        "name": "canton",
        "label": "1. Cantón:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si,
        "constraint": ". != '__pick_canton__'",
        "constraint_message": "Seleccione un cantón válido."
    })

    # 2. Distrito (desplegable) — cascada por canton_key
    survey_rows.append({
        "type": "select_one list_distrito",
        "name": "distrito",
        "label": "2. Distrito:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si,
        "choice_filter": "canton_key=${canton} or any='1'",
        "constraint": ". != '__pick_distrito__'",
        "constraint_message": "Seleccione un distrito válido."
    })

    # 3. Edad (rango)
    survey_rows.append({
        "type": f"select_one {list_edad}",
        "name": "edad_rango",
        "label": "3. Edad (en años cumplidos): marque con una X la categoría que incluya su edad.",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si,
        "hint": "Esta pregunta se responde mediante rangos de edad. Solo pueden participar personas adultas (18 años o más), por lo que las personas menores de edad quedan excluidas conforme al consentimiento informado."
    })

    # 4. Identidad
    survey_rows.append({
        "type": f"select_one {list_identidad}",
        "name": "identidad",
        "label": "4. ¿Con cuál de estas opciones se identifica?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 5. Escolaridad
    survey_rows.append({
        "type": f"select_one {list_escolaridad}",
        "name": "escolaridad",
        "label": "5. Escolaridad:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    # 6. Relación con la zona
    survey_rows.append({
        "type": f"select_one {list_relacion}",
        "name": "relacion_zona",
        "label": "6. ¿Cuál es su relación con la zona?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    survey_rows.append({"type": "end_group", "name": "p3_end"})

    # -------------------------
    # Choices: agregar catálogo Cantón/Distrito manual
    # -------------------------
    for r in st.session_state.choices_ext_rows_cd:
        choices_rows.append(dict(r))

    # -------------------------
    # DataFrames
    # -------------------------
    survey_cols = [
        "type", "name", "label", "required", "appearance",
        "relevant", "choice_filter", "media::image",
        "constraint", "constraint_message", "hint"
    ]
    df_survey = pd.DataFrame(survey_rows, columns=survey_cols).fillna("")
    # choices: columnas base + extras
    extra_cols = sorted(list(st.session_state.choices_extra_cols_cd)) if st.session_state.choices_extra_cols_cd else []
    base_choice_cols = ["list_name", "name", "label"] + extra_cols
    # asegurar que las columnas existan aunque algunas filas no tengan extras
    df_choices = pd.DataFrame(choices_rows)
    if df_choices.empty:
        df_choices = pd.DataFrame(columns=base_choice_cols)
    else:
        for col in base_choice_cols:
            if col not in df_choices.columns:
                df_choices[col] = ""
        df_choices = df_choices[base_choice_cols].fillna("")

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
    if not st.session_state.choices_ext_rows_cd:
        st.error("Debes cargar al menos un Cantón con sus Distritos en el catálogo (Cantón → Distrito) antes de generar el XLSForm.")
    else:
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
""")
