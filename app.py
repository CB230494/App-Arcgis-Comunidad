# -*- coding: utf-8 -*-
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (1/10) ====================================
# ====== App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 8) + Cantón→Distrito =====
# ==========================================================================================
#
# OBJETIVO DE ESTA VERSIÓN (CON EDITOR):
# - Mantener TODA tu lógica actual (export XLSForm, pages, glosarios por página, cascada cantón→distrito)
# - Agregar un "Editor" dentro de la app para:
#   1) Editar textos de preguntas (label), nombres (name), tipo (type), requerido (required), etc.
#   2) Reordenar preguntas dentro de cada página.
#   3) Agregar nuevas preguntas (select_one, select_multiple, text, integer, note, begin_group/end_group, etc.)
#   4) Agregar o modificar dependencias/condicionales (relevant), constraints y choice_filter.
#   5) Extender glosarios: agregar términos + definiciones y asignarlos a páginas.
#
# ENFOQUE DE IMPLEMENTACIÓN (EN PARTES):
# - Parte 1: Base intacta + Modelo editable en session_state (preguntas/glosarios) + utilidades.
# - Parte 2-4: Construir "Banco de Preguntas" editable por páginas (P1..P8), con UI de edición.
# - Parte 5-6: Editor de choices (listas) + validaciones (nombres únicos, slugify, conflictos).
# - Parte 7: Integración del Editor con el constructor del XLSForm (survey_rows dinámico).
# - Parte 8: Editor de glosarios por página (términos, definiciones, asignación).
# - Parte 9: UI final (reordenar, duplicar, borrar, preview, export) + seguridad de datos.
# - Parte 10: Pulido, documentación final, y checklist Survey123 Connect.
#
# ------------------------------------------------------------------------------------------
# Páginas del formulario (sin cambios en el objetivo):
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
# - Catálogo Cantón→Distrito: por lotes, con choice_filter
#
# Limpieza solicitada (ya aplicada en tu base):
# - Eliminar textos internos "Nota: ..." para que NO se vean en Survey123
# - Mantener introducciones útiles por página (ej. "Delitos...")
# - En Cantón/Distrito: no mostrar "— escoja un cantón —"
# - En Edad: que diga solo "Edad"
# - Evitar error al entrar a una página (validación de requeridos): Distrito solo aparece si ya hay Cantón
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
# Helpers (base SIN CAMBIOS)
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
# NUEVO (EDITOR) — Modelo editable en session_state (BASE)
# ==========================================================================================
# En las próximas partes vamos a:
# - Construir un "banco de preguntas" por páginas: P1..P8
# - Permitir editar cada fila como si fuera un renglón del XLSForm (type/name/label/required/etc.)
#
# Aquí solo dejamos la base: keys de session_state y utilidades generales.

def ss_init_key(key: str, default):
    """Inicializa una key en session_state si no existe."""
    if key not in st.session_state:
        st.session_state[key] = default

def build_question_row(
    *,
    qid: str,
    page: str,
    order: int,
    row: dict
) -> dict:
    """
    Estructura estándar de una 'pregunta' editable dentro del Editor.

    - qid: id interno estable (no se exporta; sirve para editar/reordenar/borrar sin perder referencia)
    - page: "p1"..."p8"
    - order: entero para orden dentro de la página
    - row: dict con columnas estilo XLSForm (type,name,label,required,relevant,choice_filter,constraint,...)
    """
    return {
        "qid": qid,
        "page": page,
        "order": order,
        "row": dict(row),
    }

def sort_questions(questions: list[dict]) -> list[dict]:
    """Ordena por página y luego por 'order'."""
    return sorted(questions, key=lambda x: (x.get("page", ""), int(x.get("order", 0))))

def next_order_for_page(questions: list[dict], page: str) -> int:
    """Calcula el siguiente 'order' disponible dentro de una página."""
    orders = [int(q.get("order", 0)) for q in questions if q.get("page") == page]
    return (max(orders) + 1) if orders else 1

def ensure_unique_name_in_page(questions: list[dict], page: str, proposed_name: str, ignore_qid: str | None = None) -> str:
    """
    Garantiza que el 'name' (XLSForm) sea único dentro del banco editable.
    - Si choca, agrega sufijos _2, _3, ...
    """
    used = set()
    for q in questions:
        if q.get("page") != page:
            continue
        if ignore_qid and q.get("qid") == ignore_qid:
            continue
        nm = (q.get("row", {}) or {}).get("name", "")
        if nm:
            used.add(nm)

    if proposed_name not in used:
        return proposed_name

    i = 2
    while f"{proposed_name}_{i}" in used:
        i += 1
    return f"{proposed_name}_{i}"

# Keys principales del Editor (persisten mientras la app esté abierta)
ss_init_key("editor_enabled", True)     # luego haremos un toggle en UI
ss_init_key("questions_bank", [])       # lista[dict] build_question_row(...)
ss_init_key("glosario_defs", {})        # dict[término] = definición
ss_init_key("glosario_pages", {})       # dict["p4"/"p5"/...] = list[términos]
ss_init_key("choices_ext_rows", [])     # tu catálogo cantón→distrito (ya lo usas)

# ==========================================================================================
# Logo + Delegación (SIN CAMBIOS)
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
        help="Debe coincidir con el archivo dentro de la carpeta `media/` del proyecto Survey123 (Connect指出)."
    )

form_title = f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad"
st.markdown(f"### {form_title}")

# ==========================================================================================
# FIN PARTE 1/10
# - En la Parte 2:
#   1) Traemos tus constantes (INTRO, CONSENT, GLOSARIO, etc.) sin cambios
#   2) Inicializamos el banco de preguntas con tu formulario actual (P1..P8)
#   3) Creamos el menú "Modo: Editor / Exportar" en la UI
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (2/10) ====================================
# ====== App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 8) + Cantón→Distrito =====
# ==========================================================================================
#
# PARTE 2/10 — Qué agrega:
# 1) Constantes del formulario (INTRO, CONSENTIMIENTO, GLOSARIO) SIN CAMBIOS.
# 2) Catálogo Cantón→Distrito por lotes (tu lógica SIN CAMBIOS).
# 3) UI base del “Modo Editor / Modo Exportar”.
# 4) Inicialización del glosario editable en session_state.
# 5) “Seed” (precarga) del banco de preguntas: en esta Parte 2 se precargan P1 y P2.
#    (En Parte 3 se precargan P3–P8 para no hacer esta sección gigantesca en una sola parte).
#
# NOTA: No se elimina nada de tu flujo actual. Solo se prepara el terreno del Editor.
# ==========================================================================================

# ==========================================================================================
# Página 1: Introducción (EXACTO indicado) — SIN CAMBIOS
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
# Página 2: Consentimiento (MISMO de la app anterior) — SIN CAMBIOS
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
# Glosario (se alimenta por página SOLO si hay términos definidos) — SIN CAMBIOS
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
# NUEVO (EDITOR) — Inicialización de glosario editable por página en session_state
# ==========================================================================================
# - glosario_defs: definiciones base (editable)
# - glosario_pages: términos por página (editable)
#
# Nota: esto no cambia tu export todavía; en Partes 7-8 lo conectamos al constructor final.

def init_glosario_editor():
    # Definiciones base
    if not st.session_state.get("glosario_defs"):
        st.session_state["glosario_defs"] = dict(GLOSARIO_DEFINICIONES)

    # Asignación por página (según tu formulario original)
    if not st.session_state.get("glosario_pages"):
        st.session_state["glosario_pages"] = {
            "p4": ["Extorsión", "Daños/vandalismo"],
            "p5": [
                "Búnkeres",
                "Receptación",
                "Contrabando",
                "Trata de personas",
                "Explotación infantil",
                "Acoso callejero",
                "Tráfico de personas (coyotaje)",
                "Estafa",
                "Tacha"
            ],
            "p6": [
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
            ],
            "p7": [
                "Ganzúa (pata de chancho)",
                "Boquete",
                "Arrebato",
                "Receptación",
                "Extorsión",
            ],
            "p8": [
                "Patrullaje",
                "Acciones disuasivas",
                "Coordinación interinstitucional",
                "Integridad y credibilidad policial",
            ],
        }

init_glosario_editor()

# ==========================================================================================
# Catálogo Cantón → Distrito (por lotes) — TU CÓDIGO SIN CAMBIOS
# ==========================================================================================
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
# NUEVO (EDITOR) — Selector de modo de trabajo (Editor vs Exportar)
# ==========================================================================================
st.markdown("---")
st.subheader("🧩 Modo de trabajo")

# Guardamos el modo en session_state
if "ui_mode" not in st.session_state:
    st.session_state["ui_mode"] = "Editor"

st.session_state["ui_mode"] = st.radio(
    "Seleccione un modo:",
    options=["Editor", "Exportar"],
    index=0 if st.session_state["ui_mode"] == "Editor" else 1,
    horizontal=True
)

# ==========================================================================================
# NUEVO (EDITOR) — Precarga del banco de preguntas (P1 y P2 en esta Parte 2)
# ==========================================================================================
# IMPORTANTE:
# - questions_bank es la lista que luego se mostrará en la UI del Editor.
# - Cada item representa UNA fila "tipo XLSForm" (type/name/label/required/relevant/etc.)
# - Para no hacer un bloque enorme, en Parte 3 se precargan P3..P8.

def seed_questions_bank_p1_p2_if_empty(form_title: str, logo_media_name: str):
    if st.session_state.get("questions_bank"):
        return

    qb = []

    # =========================
    # P1: Introducción
    # =========================
    page = "p1"
    qb.append(build_question_row(
        qid="p1_begin_group",
        page=page,
        order=1,
        row={"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"}
    ))
    qb.append(build_question_row(
        qid="p1_logo_note",
        page=page,
        order=2,
        row={"type": "note", "name": "p1_logo", "label": form_title, "media::image": logo_media_name, "bind::esri:fieldType": "null"}
    ))
    qb.append(build_question_row(
        qid="p1_texto_note",
        page=page,
        order=3,
        row={"type": "note", "name": "p1_texto", "label": INTRO_COMUNIDAD_EXACTA, "bind::esri:fieldType": "null"}
    ))
    qb.append(build_question_row(
        qid="p1_end_group",
        page=page,
        order=4,
        row={"type": "end_group", "name": "p1_end"}
    ))

    # =========================
    # P2: Consentimiento Informado
    # =========================
    page = "p2"
    qb.append(build_question_row(
        qid="p2_begin_group",
        page=page,
        order=1,
        row={"type": "begin_group", "name": "p2_consent", "label": "Consentimiento Informado", "appearance": "field-list"}
    ))

    qb.append(build_question_row(
        qid="p2_titulo_note",
        page=page,
        order=2,
        row={"type": "note", "name": "p2_titulo", "label": CONSENT_TITLE, "bind::esri:fieldType": "null"}
    ))

    # Párrafos
    base_order = 3
    for i, p in enumerate(CONSENT_PARRAFOS, start=1):
        qb.append(build_question_row(
            qid=f"p2_p_{i}",
            page=page,
            order=base_order + (i - 1),
            row={"type": "note", "name": f"p2_p_{i}", "label": p, "bind::esri:fieldType": "null"}
        ))

    # Bullets
    base_order = base_order + len(CONSENT_PARRAFOS)
    for j, b in enumerate(CONSENT_BULLETS, start=1):
        qb.append(build_question_row(
            qid=f"p2_b_{j}",
            page=page,
            order=base_order + (j - 1),
            row={"type": "note", "name": f"p2_b_{j}", "label": f"• {b}", "bind::esri:fieldType": "null"}
        ))

    # Cierre
    base_order = base_order + len(CONSENT_BULLETS)
    for k, c in enumerate(CONSENT_CIERRE, start=1):
        qb.append(build_question_row(
            qid=f"p2_c_{k}",
            page=page,
            order=base_order + (k - 1),
            row={"type": "note", "name": f"p2_c_{k}", "label": c, "bind::esri:fieldType": "null"}
        ))

    # Acepta participar
    base_order = base_order + len(CONSENT_CIERRE)
    qb.append(build_question_row(
        qid="p2_acepta_participar",
        page=page,
        order=base_order + 1,
        row={
            "type": "select_one yesno",
            "name": "acepta_participar",
            "label": "¿Acepta participar en esta encuesta?",
            "required": "yes",
            "appearance": "minimal"
        }
    ))

    # End group P2
    qb.append(build_question_row(
        qid="p2_end_group",
        page=page,
        order=base_order + 2,
        row={"type": "end_group", "name": "p2_end"}
    ))

    # End (fin por no)
    # Nota: se mantiene el relevant, pero el valor exacto ('no') se termina de amarrar al yes/no
    # en Partes 7-8, donde generaremos v_si/v_no de forma consistente.
    qb.append(build_question_row(
        qid="p2_fin_por_no",
        page=page,
        order=base_order + 3,
        row={
            "type": "end",
            "name": "fin_por_no",
            "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.",
            "relevant": "${acepta_participar}='no'"
        }
    ))

    st.session_state["questions_bank"] = sort_questions(qb)

seed_questions_bank_p1_p2_if_empty(form_title=form_title, logo_media_name=logo_media_name)

# ==========================================================================================
# Vista rápida (solo para confirmar que YA SE ESTÁN VIENDO las preguntas precargadas)
# - En Parte 3 hacemos el Editor completo (lista por páginas, seleccionar, editar, reordenar, etc.)
# ==========================================================================================
if st.session_state["ui_mode"] == "Editor":
    st.info("Modo Editor activo. En Parte 3 aparecerá la interfaz completa de edición (P1..P8).")
    df_prev = pd.DataFrame([
        {
            "page": q.get("page"),
            "order": q.get("order"),
            "type": (q.get("row") or {}).get("type", ""),
            "name": (q.get("row") or {}).get("name", ""),
            "label": (q.get("row") or {}).get("label", ""),
        }
        for q in st.session_state.get("questions_bank", [])
    ])
    st.dataframe(df_prev, use_container_width=True, hide_index=True, height=240)

# ==========================================================================================
# FIN PARTE 2/10
# - En la Parte 3:
#   1) Precargamos P3–P8 (todas tus preguntas actuales) dentro del questions_bank
#   2) Construimos la UI del Editor: seleccionar página, lista de preguntas, editar campos, reordenar
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (3/10) ====================================
# ====== App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 8) + Cantón→Distrito =====
# ==========================================================================================
#
# PARTE 3/10 — Qué agrega:
# 1) Precarga al banco editable (questions_bank) de:
#    - P3: Datos demográficos
#    - P4: Percepción (7–11)
#    (Para que no sea gigantesco, P5–P8 se precargan en la Parte 4)
#
# 2) Editor REAL en la UI:
#    - Seleccionar página (P1..P8)
#    - Ver lista de preguntas de esa página
#    - Editar campos XLSForm (type/name/label/required/appearance/relevant/choice_filter/constraint/etc.)
#    - Reordenar (subir/bajar)
#    - Duplicar / eliminar
#    - Agregar nuevas preguntas
#
# 3) Normalización básica yes/no:
#    - Asegura que fin_por_no use el valor real del choice "No" (slugify_name("No"))
# ==========================================================================================

# ==========================================================================================
# NUEVO — Utilidades del Editor (UI + acciones)
# ==========================================================================================
def get_pages_catalog():
    """Catálogo fijo de páginas (para navegación y orden)."""
    return [
        ("p1", "P1 — Introducción"),
        ("p2", "P2 — Consentimiento"),
        ("p3", "P3 — Datos demográficos"),
        ("p4", "P4 — Percepción ciudadana"),
        ("p5", "P5 — Riesgos / Factores situacionales"),
        ("p6", "P6 — Delitos"),
        ("p7", "P7 — Victimización"),
        ("p8", "P8 — Confianza policial y cierre"),
    ]

def find_question_index_by_qid(qid: str) -> int | None:
    """Retorna el índice en questions_bank para un qid dado."""
    for i, q in enumerate(st.session_state.get("questions_bank", [])):
        if q.get("qid") == qid:
            return i
    return None

def get_questions_by_page(page: str) -> list[dict]:
    """Lista de preguntas en una página, ordenadas por 'order'."""
    qs = [q for q in st.session_state.get("questions_bank", []) if q.get("page") == page]
    return sorted(qs, key=lambda x: int(x.get("order", 0)))

def update_orders_compact(page: str):
    """
    Compacta órdenes de una página para que queden 1..N sin saltos.
    Esto evita duplicados o huecos tras reordenar/borrar.
    """
    qb = st.session_state.get("questions_bank", [])
    page_qs = sorted([q for q in qb if q.get("page") == page], key=lambda x: int(x.get("order", 0)))
    for idx, q in enumerate(page_qs, start=1):
        q["order"] = idx
    st.session_state["questions_bank"] = sort_questions(qb)

def move_question(page: str, qid: str, direction: str):
    """
    Mueve una pregunta en el orden:
    - direction: "up" o "down"
    """
    qs = get_questions_by_page(page)
    pos = next((i for i, q in enumerate(qs) if q.get("qid") == qid), None)
    if pos is None:
        return
    if direction == "up" and pos > 0:
        qs[pos]["order"], qs[pos - 1]["order"] = qs[pos - 1]["order"], qs[pos]["order"]
    if direction == "down" and pos < (len(qs) - 1):
        qs[pos]["order"], qs[pos + 1]["order"] = qs[pos + 1]["order"], qs[pos]["order"]
    update_orders_compact(page)

def delete_question(qid: str):
    qb = st.session_state.get("questions_bank", [])
    st.session_state["questions_bank"] = [q for q in qb if q.get("qid") != qid]

def duplicate_question(page: str, qid: str):
    qb = st.session_state.get("questions_bank", [])
    idx = find_question_index_by_qid(qid)
    if idx is None:
        return
    orig = qb[idx]
    new_qid = f"{qid}_copy_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    new_order = next_order_for_page(qb, page)

    row_copy = dict(orig.get("row", {}) or {})
    # name debe ser único
    if row_copy.get("name"):
        row_copy["name"] = ensure_unique_name_in_page(qb, page, row_copy["name"], ignore_qid=None)

    qb.append(build_question_row(qid=new_qid, page=page, order=new_order, row=row_copy))
    st.session_state["questions_bank"] = sort_questions(qb)
    update_orders_compact(page)

def add_new_question(page: str, q_type: str, q_name: str, q_label: str):
    qb = st.session_state.get("questions_bank", [])
    new_qid = f"new_{page}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    new_order = next_order_for_page(qb, page)

    base_name = slugify_name(q_name) if q_name else "campo"
    unique_name = ensure_unique_name_in_page(qb, page, base_name, ignore_qid=None)

    new_row = {
        "type": q_type,
        "name": unique_name,
        "label": q_label or ""
    }

    # Para notes, mantener bind null (no crea columna)
    if q_type == "note":
        new_row["bind::esri:fieldType"] = "null"

    qb.append(build_question_row(qid=new_qid, page=page, order=new_order, row=new_row))
    st.session_state["questions_bank"] = sort_questions(qb)
    update_orders_compact(page)

def normalize_yesno_relevants():
    """
    Asegura consistencia para comparaciones de acepta_participar con el valor real "No".
    Esto corrige el seed anterior que tenía '${acepta_participar}='no'' literal.
    """
    v_no = slugify_name("No")
    qb = st.session_state.get("questions_bank", [])
    for q in qb:
        row = q.get("row", {}) or {}
        if row.get("name") == "fin_por_no":
            if row.get("relevant", "") == "${acepta_participar}='no'":
                row["relevant"] = f"${{acepta_participar}}='{v_no}'"
    st.session_state["questions_bank"] = qb

normalize_yesno_relevants()

# ==========================================================================================
# NUEVO (EDITOR) — Precarga P3 y P4 si aún no existen en questions_bank
# ==========================================================================================
def seed_questions_bank_p3_p4_if_missing():
    qb = st.session_state.get("questions_bank", [])
    pages_present = set(q.get("page") for q in qb)

    v_si = slugify_name("Sí")
    v_no = slugify_name("No")

    # Relevant base si acepta participar
    rel_si = f"${{acepta_participar}}='{v_si}'"

    # ======================================================================================
    # P3: Datos demográficos (SI NO EXISTE)
    # ======================================================================================
    if "p3" not in pages_present:
        page = "p3"
        qb.append(build_question_row(
            qid="p3_begin_group",
            page=page,
            order=1,
            row={
                "type": "begin_group",
                "name": "p3_datos_demograficos",
                "label": "Datos demográficos",
                "appearance": "field-list",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p3_canton",
            page=page,
            order=2,
            row={
                "type": "select_one list_canton",
                "name": "canton",
                "label": "1. Cantón:",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        rel_distrito = f"({rel_si}) and string-length(${{canton}}) > 0"
        qb.append(build_question_row(
            qid="p3_distrito",
            page=page,
            order=3,
            row={
                "type": "select_one list_distrito",
                "name": "distrito",
                "label": "2. Distrito:",
                "required": "yes",
                "choice_filter": "canton_key=${canton}",
                "appearance": "minimal",
                "relevant": rel_distrito
            }
        ))

        qb.append(build_question_row(
            qid="p3_edad",
            page=page,
            order=4,
            row={
                "type": "integer",
                "name": "edad_anos",
                "label": "3. Edad:",
                "required": "yes",
                "constraint": ". >= 18 and . <= 120",
                "constraint_message": "Debe ser un número entre 18 y 120.",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p3_genero",
            page=page,
            order=5,
            row={
                "type": "select_one genero",
                "name": "genero",
                "label": "4. ¿Con cuál de estas opciones se identifica?",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p3_escolaridad",
            page=page,
            order=6,
            row={
                "type": "select_one escolaridad",
                "name": "escolaridad",
                "label": "5. Escolaridad:",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p3_relacion_zona",
            page=page,
            order=7,
            row={
                "type": "select_one relacion_zona",
                "name": "relacion_zona",
                "label": "6. ¿Cuál es su relación con la zona?",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p3_end_group",
            page=page,
            order=8,
            row={"type": "end_group", "name": "p3_end"}
        ))

    # ======================================================================================
    # P4: Percepción (7–11) (SI NO EXISTE)
    # ======================================================================================
    if "p4" not in pages_present:
        page = "p4"

        qb.append(build_question_row(
            qid="p4_begin_group",
            page=page,
            order=1,
            row={
                "type": "begin_group",
                "name": "p4_percepcion_distrito",
                "label": "Percepción ciudadana de seguridad en el distrito",
                "appearance": "field-list",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p4_p7",
            page=page,
            order=2,
            row={
                "type": "select_one seguridad_5",
                "name": "p7_seguridad_distrito",
                "label": "7. ¿Qué tan seguro percibe usted el distrito donde reside o transita?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        rel_71 = (
            f"({rel_si}) and ("
            f"${{p7_seguridad_distrito}}='{slugify_name('Muy inseguro')}' or "
            f"${{p7_seguridad_distrito}}='{slugify_name('Inseguro')}'"
            f")"
        )

        qb.append(build_question_row(
            qid="p4_p71",
            page=page,
            order=3,
            row={
                "type": "select_multiple causas_inseguridad",
                "name": "p71_causas_inseguridad",
                "label": "7.1. Indique por qué considera el distrito inseguro (Marque todas las situaciones que usted percibe que ocurren con mayor frecuencia en su comunidad):",
                "required": "yes",
                "relevant": rel_71
            }
        ))

        qb.append(build_question_row(
            qid="p4_p71_note",
            page=page,
            order=4,
            row={
                "type": "note",
                "name": "p71_no_denuncia",
                "label": "Esta pregunta recoge percepción general y no constituye denuncia.",
                "relevant": rel_71,
                "bind::esri:fieldType": "null"
            }
        ))

        qb.append(build_question_row(
            qid="p4_p71_otro",
            page=page,
            order=5,
            row={
                "type": "text",
                "name": "p71_otro_detalle",
                "label": "Otro problema que considere importante (detalle):",
                "required": "no",
                "appearance": "multiline",
                "relevant": f"({rel_71}) and selected(${{p71_causas_inseguridad}}, '{slugify_name('Otro problema que considere importante')}')"
            }
        ))

        qb.append(build_question_row(
            qid="p4_p8",
            page=page,
            order=6,
            row={
                "type": "select_one escala_1_5",
                "name": "p8_comparacion_anno",
                "label": "8. ¿Cómo se percibe la seguridad en este distrito este año en comparación con el año anterior?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        rel_81 = f"({rel_si}) and string-length(${{p8_comparacion_anno}}) > 0"
        qb.append(build_question_row(
            qid="p4_p81",
            page=page,
            order=7,
            row={
                "type": "text",
                "name": "p81_indique_por_que",
                "label": "8.1. Indique por qué:",
                "required": "yes",
                "appearance": "multiline",
                "relevant": rel_81
            }
        ))

        qb.append(build_question_row(
            qid="p4_p9_instr",
            page=page,
            order=8,
            row={
                "type": "note",
                "name": "p9_instr",
                "label": "9. Indique qué tan seguros percibe, en términos de seguridad, en los siguientes espacios de su Distrito:",
                "relevant": rel_si,
                "bind::esri:fieldType": "null"
            }
        ))

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
        base_order = 9
        for i, (nm, lab) in enumerate(matriz_filas, start=0):
            qb.append(build_question_row(
                qid=f"p4_{nm}",
                page=page,
                order=base_order + i,
                row={
                    "type": "select_one matriz_1_5_na",
                    "name": nm,
                    "label": lab,
                    "required": "yes",
                    "appearance": "minimal",
                    "relevant": rel_si
                }
            ))

        base_order = base_order + len(matriz_filas)
        qb.append(build_question_row(
            qid="p4_p10",
            page=page,
            order=base_order + 1,
            row={
                "type": "select_one tipo_espacio",
                "name": "p10_tipo_espacio_mas_inseguro",
                "label": "10. Según su percepción, ¿cuál de los siguientes tipos de espacios del distrito considera más inseguro?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p4_p10_otro",
            page=page,
            order=base_order + 2,
            row={
                "type": "text",
                "name": "p10_otros_detalle",
                "label": "Otros (detalle):",
                "required": "no",
                "appearance": "multiline",
                "relevant": f"({rel_si}) and (${{p10_tipo_espacio_mas_inseguro}}='{slugify_name('Otros')}')"
            }
        ))

        qb.append(build_question_row(
            qid="p4_p11",
            page=page,
            order=base_order + 3,
            row={
                "type": "text",
                "name": "p11_por_que_inseguro_tipo_espacio",
                "label": "11. Según su percepción, describa brevemente por qué considera inseguro el tipo de espacio seleccionado en la pregunta anterior.",
                "required": "no",
                "appearance": "multiline",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p4_end_group",
            page=page,
            order=base_order + 4,
            row={"type": "end_group", "name": "p4_end"}
        ))

    st.session_state["questions_bank"] = sort_questions(qb)
    update_orders_compact("p3")
    update_orders_compact("p4")

seed_questions_bank_p3_p4_if_missing()

# ==========================================================================================
# EDITOR UI (real) — Solo se muestra si ui_mode == "Editor"
# ==========================================================================================
if st.session_state["ui_mode"] == "Editor":
    st.markdown("---")
    st.subheader("🛠️ Editor de preguntas (XLSForm)")

    # Selector de página
    pages = get_pages_catalog()
    page_ids = [p[0] for p in pages]
    page_labels = {p[0]: p[1] for p in pages}

    if "editor_page" not in st.session_state:
        st.session_state["editor_page"] = "p3"

    st.session_state["editor_page"] = st.selectbox(
        "Seleccione la página a editar:",
        options=page_ids,
        format_func=lambda x: page_labels.get(x, x),
        index=page_ids.index(st.session_state["editor_page"]) if st.session_state["editor_page"] in page_ids else 0
    )
    current_page = st.session_state["editor_page"]

    # Lista de preguntas de la página
    page_qs = get_questions_by_page(current_page)
    if not page_qs:
        st.warning("Esta página aún no tiene preguntas precargadas. (Se cargará en siguientes partes o puedes agregar nuevas).")

    # Dataframe de vista rápida
    df_list = pd.DataFrame([
        {
            "order": q.get("order", ""),
            "qid": q.get("qid", ""),
            "type": (q.get("row") or {}).get("type", ""),
            "name": (q.get("row") or {}).get("name", ""),
            "label": ((q.get("row") or {}).get("label", "") or "")[:90],
        }
        for q in page_qs
    ])
    st.dataframe(df_list, use_container_width=True, hide_index=True, height=260)

    # Selector de pregunta (por qid)
    if "selected_qid" not in st.session_state:
        st.session_state["selected_qid"] = page_qs[0].get("qid") if page_qs else ""

    # Si cambió de página, reajusta selección si no existe
    if page_qs:
        qids_page = [q.get("qid") for q in page_qs]
        if st.session_state["selected_qid"] not in qids_page:
            st.session_state["selected_qid"] = qids_page[0]

    st.session_state["selected_qid"] = st.selectbox(
        "Seleccione una pregunta para editar:",
        options=[q.get("qid") for q in page_qs] if page_qs else [""],
        format_func=lambda qid: (
            f"[{next((q.get('order') for q in page_qs if q.get('qid') == qid), '')}] "
            f"{(next((q.get('row', {}) for q in page_qs if q.get('qid') == qid), {}) or {}).get('type', '')} — "
            f"{(next((q.get('row', {}) for q in page_qs if q.get('qid') == qid), {}) or {}).get('name', '')}"
        ) if qid else "—",
    )

    selected_qid = st.session_state["selected_qid"]
    sel_idx = find_question_index_by_qid(selected_qid)
    selected = st.session_state["questions_bank"][sel_idx] if (sel_idx is not None and selected_qid) else None

    # Controles (mover / duplicar / borrar)
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        if st.button("⬆️ Subir", use_container_width=True, disabled=(not selected_qid)):
            move_question(current_page, selected_qid, "up")
            st.rerun()
    with col_b:
        if st.button("⬇️ Bajar", use_container_width=True, disabled=(not selected_qid)):
            move_question(current_page, selected_qid, "down")
            st.rerun()
    with col_c:
        if st.button("📄 Duplicar", use_container_width=True, disabled=(not selected_qid)):
            duplicate_question(current_page, selected_qid)
            st.rerun()
    with col_d:
        if st.button("🗑️ Eliminar", use_container_width=True, disabled=(not selected_qid)):
            delete_question(selected_qid)
            update_orders_compact(current_page)
            st.session_state["selected_qid"] = ""
            st.rerun()

    st.markdown("#### ✏️ Editar campos de la pregunta seleccionada")

    if selected:
        row = selected.get("row", {}) or {}

        # Campos XLSForm editables (los más usados)
        col1, col2 = st.columns(2)
        with col1:
            new_type = st.text_input("type", value=row.get("type", ""))
            new_name = st.text_input("name", value=row.get("name", ""))
            new_required = st.text_input("required", value=row.get("required", ""))
            new_appearance = st.text_input("appearance", value=row.get("appearance", ""))
            new_media = st.text_input("media::image", value=row.get("media::image", ""))
        with col2:
            new_label = st.text_area("label", value=row.get("label", ""), height=140)
            new_relevant = st.text_area("relevant", value=row.get("relevant", ""), height=90)
            new_choice_filter = st.text_input("choice_filter", value=row.get("choice_filter", ""))
            new_bind_null = st.text_input("bind::esri:fieldType", value=row.get("bind::esri:fieldType", ""))

        col3, col4 = st.columns(2)
        with col3:
            new_constraint = st.text_area("constraint", value=row.get("constraint", ""), height=90)
        with col4:
            new_constraint_msg = st.text_area("constraint_message", value=row.get("constraint_message", ""), height=90)

        # Guardar cambios
        if st.button("💾 Guardar cambios en esta pregunta", use_container_width=True):
            # name único dentro de la página (cuando exista name)
            if new_name:
                new_name = ensure_unique_name_in_page(
                    st.session_state.get("questions_bank", []),
                    current_page,
                    new_name,
                    ignore_qid=selected.get("qid")
                )

            row["type"] = new_type
            row["name"] = new_name
            row["label"] = new_label
            row["required"] = new_required
            row["appearance"] = new_appearance
            row["relevant"] = new_relevant
            row["choice_filter"] = new_choice_filter
            row["constraint"] = new_constraint
            row["constraint_message"] = new_constraint_msg
            row["media::image"] = new_media
            row["bind::esri:fieldType"] = new_bind_null

            selected["row"] = row
            st.session_state["questions_bank"][sel_idx] = selected
            st.success("Cambios guardados.")
            st.rerun()

    st.markdown("---")
    st.subheader("➕ Agregar una pregunta nueva a esta página")

    coln1, coln2, coln3 = st.columns([2, 2, 4])
    with coln1:
        new_q_type = st.selectbox(
            "type (nuevo)",
            options=[
                "text",
                "integer",
                "note",
                "select_one yesno",
                "select_one list_canton",
                "select_one list_distrito",
                "select_one genero",
                "select_one escolaridad",
                "select_one relacion_zona",
                "select_one seguridad_5",
                "select_multiple causas_inseguridad",
                "select_one escala_1_5",
                "select_one matriz_1_5_na",
                "select_one tipo_espacio",
                "begin_group",
                "end_group",
                "end",
            ],
            index=0
        )
    with coln2:
        new_q_name = st.text_input("name (nuevo)", value="")
    with coln3:
        new_q_label = st.text_input("label (nuevo)", value="")

    if st.button("✅ Agregar pregunta", use_container_width=True):
        add_new_question(current_page, new_q_type, new_q_name, new_q_label)
        st.success("Pregunta agregada.")
        st.rerun()

    st.info(
        "En la Parte 4 se precargan P5–P8 (todas las preguntas restantes) en el questions_bank, "
        "para que el Editor ya muestre el formulario completo."
    )

# ==========================================================================================
# FIN PARTE 3/10
# - En la Parte 4:
#   1) Precargamos P5–P8 (Riesgos, Delitos, Victimización, Confianza y cierre) dentro de questions_bank
#   2) Dejamos el Editor listo con TODAS las preguntas originales visibles y editables
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (4/10) ====================================
# ====== App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 8) + Cantón→Distrito =====
# ==========================================================================================
#
# PARTE 4/10 — Qué agrega:
# 1) Precarga al banco editable (questions_bank) de TODO lo que falta:
#    - P5: Riesgos / Factores situacionales (12–18)
#    - P6: Delitos (19–29)
#    - P7: Victimización (30–31.4)
#    - P8: Confianza Policial + acciones + info adicional + cierre (32–47)
#
# Resultado:
# - Ya tendrás el formulario COMPLETO dentro del Editor (P1..P8) y podrás:
#   editar, reordenar, duplicar, borrar y agregar preguntas.
#
# Nota:
# - El glosario se mantiene como "configuración por página" en session_state (Parte 2).
# - Aún NO conectamos glosario al export dinámico (eso va en Partes 7–8).
# ==========================================================================================

# ==========================================================================================
# NUEVO (EDITOR) — Precarga P5..P8 si aún no existen en questions_bank
# ==========================================================================================
def seed_questions_bank_p5_p8_if_missing():
    qb = st.session_state.get("questions_bank", [])
    pages_present = set(q.get("page") for q in qb)

    v_si = slugify_name("Sí")
    v_no = slugify_name("No")

    # Relevant base si acepta participar
    rel_si = f"${{acepta_participar}}='{v_si}'"

    # ======================================================================================
    # P5 Riesgos / factores situacionales (12–18)
    # ======================================================================================
    if "p5" not in pages_present:
        page = "p5"

        qb.append(build_question_row(
            qid="p5_begin_group",
            page=page,
            order=1,
            row={
                "type": "begin_group",
                "name": "p5_riesgos",
                "label": "III. RIESGOS, DELITOS, VICTIMIZACIÓN Y EVALUACIÓN POLICIAL",
                "appearance": "field-list",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p5_subtitulo",
            page=page,
            order=2,
            row={
                "type": "note",
                "name": "p5_subtitulo",
                "label": "Riesgos sociales y situacionales en el distrito",
                "relevant": rel_si,
                "bind::esri:fieldType": "null"
            }
        ))

        qb.append(build_question_row(
            qid="p5_intro",
            page=page,
            order=3,
            row={
                "type": "note",
                "name": "p5_intro",
                "label": "A continuación, se presentará una lista de problemáticas que se catalogan como factores situacionales, con la finalidad de que seleccione aquellos que considere que ocurren en su distrito.",
                "relevant": rel_si,
                "bind::esri:fieldType": "null"
            }
        ))

        qb.append(build_question_row(
            qid="p5_p12",
            page=page,
            order=4,
            row={
                "type": "select_multiple p12_prob_situacionales",
                "name": "p12_problematicas_distrito",
                "label": "12. Según su percepción u observación, seleccione las problemáticas que afectan su distrito:",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p5_p12_otro",
            page=page,
            order=5,
            row={
                "type": "text",
                "name": "p12_otro_detalle",
                "label": "Otro problema que considere importante:",
                "required": "no",
                "appearance": "multiline",
                "relevant": f"({rel_si}) and selected(${{p12_problematicas_distrito}}, '{slugify_name('Otro problema que considere importante')}')"
            }
        ))

        qb.append(build_question_row(
            qid="p5_p13",
            page=page,
            order=6,
            row={
                "type": "select_multiple p13_carencias_inversion",
                "name": "p13_carencias_inversion_social",
                "label": "13. En relación con la inversión social en su distrito, indique cuáles de las siguientes carencias identifica:",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        n_no_obs = slugify_name("No se observa consumo")
        n_priv = slugify_name("Área privada")
        n_pub = slugify_name("Área pública")
        constraint_p14 = f"not(selected(., '{n_no_obs}') and (selected(., '{n_priv}') or selected(., '{n_pub}')))"

        qb.append(build_question_row(
            qid="p5_p14",
            page=page,
            order=7,
            row={
                "type": "select_multiple p14_consumo_drogas_donde",
                "name": "p14_donde_consumo_drogas",
                "label": "14. Según su percepción u observación, indique dónde se presenta consumo de drogas en el distrito:",
                "required": "yes",
                "constraint": constraint_p14,
                "constraint_message": "Si selecciona “No se observa consumo”, no puede seleccionar “Área privada” ni “Área pública”.",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p5_p15",
            page=page,
            order=8,
            row={
                "type": "select_multiple p15_def_infra_vial",
                "name": "p15_deficiencias_infra_vial",
                "label": "15. Indique las principales deficiencias de infraestructura vial que afectan su distrito:",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p5_p16",
            page=page,
            order=9,
            row={
                "type": "select_multiple p16_bunkeres_espacios",
                "name": "p16_bunkeres_espacios",
                "label": "16. Según su percepción u observación, indique en qué tipo de espacios se identifica la existencia de puntos de venta de drogas (búnkeres) en el distrito:",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p5_p16_otro",
            page=page,
            order=10,
            row={
                "type": "text",
                "name": "p16_otro_detalle",
                "label": "Otro:",
                "required": "no",
                "appearance": "multiline",
                "relevant": f"({rel_si}) and selected(${{p16_bunkeres_espacios}}, '{slugify_name('Otro')}')"
            }
        ))

        qb.append(build_question_row(
            qid="p5_p17",
            page=page,
            order=11,
            row={
                "type": "select_multiple p17_transporte_afect",
                "name": "p17_transporte_afectacion",
                "label": "17. En relación con el transporte en su distrito, indique cuáles situaciones representan una afectación:",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        n_no_pres = slugify_name("No observa presencia policial")
        n_falta = slugify_name("Falta de presencia policial")
        n_insuf = slugify_name("Presencia policial insuficiente")
        n_hor = slugify_name("Presencia policial solo en ciertos horarios")
        constraint_p18 = f"not(selected(., '{n_no_pres}') and (selected(., '{n_falta}') or selected(., '{n_insuf}') or selected(., '{n_hor}')))"

        qb.append(build_question_row(
            qid="p5_p18",
            page=page,
            order=12,
            row={
                "type": "select_multiple p18_presencia_policial",
                "name": "p18_presencia_policial",
                "label": "18. En relación con la presencia policial en su distrito, indique cuál de las siguientes situaciones identifica:",
                "required": "yes",
                "constraint": constraint_p18,
                "constraint_message": "Si selecciona “No observa presencia policial”, no seleccione otras opciones simultáneamente.",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p5_end_group",
            page=page,
            order=13,
            row={"type": "end_group", "name": "p5_end"}
        ))

    # ======================================================================================
    # P6 Delitos (19–29)
    # ======================================================================================
    if "p6" not in pages_present:
        page = "p6"

        qb.append(build_question_row(
            qid="p6_begin_group",
            page=page,
            order=1,
            row={
                "type": "begin_group",
                "name": "p6_delitos",
                "label": "Delitos",
                "appearance": "field-list",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p6_intro",
            page=page,
            order=2,
            row={
                "type": "note",
                "name": "p6_intro",
                "label": "A continuación, se presentará una lista de delitos y situaciones delictivas para que seleccione aquellos que, según su percepción u observación, considera que se presentan en su comunidad. Esta información no constituye denuncia formal ni confirmación de hechos delictivos.",
                "relevant": rel_si,
                "bind::esri:fieldType": "null"
            }
        ))

        qb.append(build_question_row(
            qid="p6_p19",
            page=page,
            order=3,
            row={
                "type": "select_multiple p19_delitos_general",
                "name": "p19_delitos_general",
                "label": "19. Selección múltiple de los siguientes delitos:",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p6_p19_otro",
            page=page,
            order=4,
            row={
                "type": "text",
                "name": "p19_otro_detalle",
                "label": "Otro:",
                "required": "no",
                "appearance": "multiline",
                "relevant": f"({rel_si}) and selected(${{p19_delitos_general}}, '{slugify_name('Otro')}')"
            }
        ))

        n20_no_percibe = slugify_name("No se percibe consumo o venta")
        n20_cerrado = slugify_name("En espacios cerrados (casas, edificaciones u otros inmuebles)")
        n20_via = slugify_name("En vía pública")
        n20_movil = slugify_name("De forma ocasional o móvil (sin punto fijo)")
        n20_otro = slugify_name("Otro")
        constraint_p20 = f"not(selected(., '{n20_no_percibe}') and (selected(., '{n20_cerrado}') or selected(., '{n20_via}') or selected(., '{n20_movil}') or selected(., '{n20_otro}')))"

        qb.append(build_question_row(
            qid="p6_p20",
            page=page,
            order=5,
            row={
                "type": "select_multiple p20_bunker_percepcion",
                "name": "p20_bunker_percepcion",
                "label": "20. Percepción de consumo o venta de drogas en el entorno (Bunker)",
                "required": "yes",
                "constraint": constraint_p20,
                "constraint_message": "Si selecciona “No se percibe consumo o venta”, no seleccione otras opciones simultáneamente.",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p6_p20_otro",
            page=page,
            order=6,
            row={
                "type": "text",
                "name": "p20_otro_detalle",
                "label": "Otro:",
                "required": "no",
                "appearance": "multiline",
                "relevant": f"({rel_si}) and selected(${{p20_bunker_percepcion}}, '{slugify_name('Otro')}')"
            }
        ))

        qb.append(build_question_row(
            qid="p6_p21",
            page=page,
            order=7,
            row={
                "type": "select_multiple p21_vida",
                "name": "p21_delitos_vida",
                "label": "21. Delitos contra la vida",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p6_p22",
            page=page,
            order=8,
            row={
                "type": "select_multiple p22_sexuales",
                "name": "p22_delitos_sexuales",
                "label": "22. Delitos sexuales",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p6_p23",
            page=page,
            order=9,
            row={
                "type": "select_multiple p23_asaltos",
                "name": "p23_asaltos_percibidos",
                "label": "23. Asaltos percibidos",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p6_p24",
            page=page,
            order=10,
            row={
                "type": "select_multiple p24_estafas",
                "name": "p24_estafas_percibidas",
                "label": "24. Estafas percibidas",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p6_p25",
            page=page,
            order=11,
            row={
                "type": "select_multiple p25_robo_fuerza",
                "name": "p25_robo_percibidos",
                "label": "25. Robo percibidos (Sustracción de artículos mediante la utilización de la fuerza)",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p6_p26",
            page=page,
            order=12,
            row={
                "type": "select_multiple p26_abandono",
                "name": "p26_abandono_personas",
                "label": "26. Abandono de personas",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p6_p27",
            page=page,
            order=13,
            row={
                "type": "select_multiple p27_explotacion_infantil",
                "name": "p27_explotacion_infantil",
                "label": "27. Explotación infantil",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p6_p28",
            page=page,
            order=14,
            row={
                "type": "select_multiple p28_ambientales",
                "name": "p28_delitos_ambientales",
                "label": "28. Delitos ambientales percibidos",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p6_p29",
            page=page,
            order=15,
            row={
                "type": "select_multiple p29_trata",
                "name": "p29_trata_personas",
                "label": "29. Trata de personas",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p6_end_group",
            page=page,
            order=16,
            row={"type": "end_group", "name": "p6_end"}
        ))

    # ======================================================================================
    # P7 Victimización (30–31.4)
    # ======================================================================================
    if "p7" not in pages_present:
        page = "p7"

        qb.append(build_question_row(
            qid="p7_begin_group",
            page=page,
            order=1,
            row={
                "type": "begin_group",
                "name": "p7_victimizacion",
                "label": "Victimización",
                "appearance": "field-list",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p7_intro",
            page=page,
            order=2,
            row={
                "type": "note",
                "name": "p7_intro",
                "label": "A continuación, se presentará una lista de situaciones para que indique si usted o algún miembro de su hogar ha sido afectado por alguna de ellas en su distrito durante el último año.",
                "relevant": rel_si,
                "bind::esri:fieldType": "null"
            }
        ))

        qb.append(build_question_row(
            qid="p7_p30",
            page=page,
            order=3,
            row={
                "type": "select_one p30_vif",
                "name": "p30_vif",
                "label": "30. Durante el último año, ¿usted o algún miembro de su hogar ha sido afectado por alguna situación de violencia intrafamiliar (violencia doméstica)?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        rel_30_si = f"({rel_si}) and (${{p30_vif}}='{v_si}')"

        qb.append(build_question_row(
            qid="p7_p301",
            page=page,
            order=4,
            row={
                "type": "select_multiple p301_tipos_vif",
                "name": "p301_tipos_vif",
                "label": "30.1. ¿Qué tipo(s) de violencia intrafamiliar (violencia doméstica) se presentaron?",
                "required": "yes",
                "relevant": rel_30_si
            }
        ))

        qb.append(build_question_row(
            qid="p7_p302",
            page=page,
            order=5,
            row={
                "type": "select_one p302_medidas",
                "name": "p302_medidas_proteccion",
                "label": "30.2. ¿En relación con la situación de violencia intrafamiliar indicada anteriormente, usted o algún miembro de su hogar solicitó medidas de protección?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_30_si
            }
        ))

        qb.append(build_question_row(
            qid="p7_p303",
            page=page,
            order=6,
            row={
                "type": "select_one p303_valoracion_fp",
                "name": "p303_valoracion_fp",
                "label": "30.3. ¿Cómo valora el abordaje de la Fuerza Pública ante esta situación?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_30_si
            }
        ))

        qb.append(build_question_row(
            qid="p7_p31",
            page=page,
            order=7,
            row={
                "type": "select_one p31_delito_12m",
                "name": "p31_delito_12m",
                "label": "31. Durante los últimos 12 meses, ¿usted o algún miembro de su hogar fue afectado por algún delito?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        val_31_si_den = slugify_name("Sí, y denuncié")
        val_31_si_no_den = slugify_name("Sí, pero no denuncié.")
        rel_31_si = f"({rel_si}) and (${{p31_delito_12m}}='{val_31_si_den}' or ${{p31_delito_12m}}='{val_31_si_no_den}')"
        rel_31_si_no_den = f"({rel_si}) and (${{p31_delito_12m}}='{val_31_si_no_den}')"

        qb.append(build_question_row(
            qid="p7_p311",
            page=page,
            order=8,
            row={
                "type": "select_multiple p311_situaciones",
                "name": "p311_situaciones_afecto",
                "label": "31.1. ¿Cuál de las siguientes situaciones afectó a usted o a algún miembro de su hogar?",
                "required": "yes",
                "relevant": rel_31_si
            }
        ))

        qb.append(build_question_row(
            qid="p7_p312",
            page=page,
            order=9,
            row={
                "type": "select_multiple p312_motivos_no_denuncia",
                "name": "p312_motivo_no_denuncia",
                "label": "31.2. En caso de NO haber realizado la denuncia, indique ¿cuál fue el motivo?",
                "required": "yes",
                "relevant": rel_31_si_no_den
            }
        ))

        qb.append(build_question_row(
            qid="p7_p313",
            page=page,
            order=10,
            row={
                "type": "select_one p313_horario",
                "name": "p313_horario_hecho",
                "label": "31.3. ¿Tiene conocimiento sobre el horario en el cual se presentó el hecho o situación que le afectó a usted o un familiar?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_31_si
            }
        ))

        qb.append(build_question_row(
            qid="p7_p314",
            page=page,
            order=11,
            row={
                "type": "select_multiple p314_modo",
                "name": "p314_modo_ocurrio",
                "label": "31.4. ¿Cuál fue la forma o modo en que ocurrió la situación que afectó a usted o a algún miembro de su hogar?",
                "required": "yes",
                "relevant": rel_31_si
            }
        ))

        qb.append(build_question_row(
            qid="p7_p314_otro",
            page=page,
            order=12,
            row={
                "type": "text",
                "name": "p314_otro_detalle",
                "label": "Otro (detalle):",
                "required": "no",
                "appearance": "multiline",
                "relevant": f"({rel_31_si}) and selected(${{p314_modo_ocurrio}}, '{slugify_name('Otro')}')"
            }
        ))

        qb.append(build_question_row(
            qid="p7_end_group",
            page=page,
            order=13,
            row={"type": "end_group", "name": "p7_end"}
        ))

    # ======================================================================================
    # P8 Confianza Policial + acciones + info adicional + cierre (32–47)
    # ======================================================================================
    if "p8" not in pages_present:
        page = "p8"

        qb.append(build_question_row(
            qid="p8_begin_group",
            page=page,
            order=1,
            row={
                "type": "begin_group",
                "name": "p8_confianza_policial",
                "label": "Confianza Policial",
                "appearance": "field-list",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_intro",
            page=page,
            order=2,
            row={
                "type": "note",
                "name": "p8_intro",
                "label": "A continuación, se presentará una lista de afirmaciones relacionadas con su percepción y confianza en el cuerpo de policía que opera en su (Distrito) barrio.",
                "relevant": rel_si,
                "bind::esri:fieldType": "null"
            }
        ))

        qb.append(build_question_row(
            qid="p8_p32",
            page=page,
            order=3,
            row={
                "type": "select_one p32_identifica_policias",
                "name": "p32_identifica_policias",
                "label": "32. ¿Identifica usted a los policías de la Fuerza Pública de Costa Rica en su comunidad?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        rel_321 = f"({rel_si}) and (${{p32_identifica_policias}}='{v_si}')"

        qb.append(build_question_row(
            qid="p8_p321",
            page=page,
            order=4,
            row={
                "type": "select_multiple p321_interacciones",
                "name": "p321_tipos_atencion",
                "label": "32.1 ¿Cuáles de los siguientes tipos de atención ha tenido?",
                "required": "yes",
                "relevant": rel_321
            }
        ))

        qb.append(build_question_row(
            qid="p8_p321_otro",
            page=page,
            order=5,
            row={
                "type": "text",
                "name": "p321_otro_detalle",
                "label": "Otra (especifique):",
                "required": "no",
                "appearance": "multiline",
                "relevant": f"({rel_321}) and selected(${{p321_tipos_atencion}}, '{slugify_name('Otra (especifique)')}')"
            }
        ))

        qb.append(build_question_row(
            qid="p8_p33",
            page=page,
            order=6,
            row={
                "type": "select_one escala_1_10",
                "name": "p33_confianza_policial",
                "label": "33. ¿Cuál es el nivel de confianza en la policía de la Fuerza Pública de Costa Rica de su comunidad? (1=Ninguna Confianza, 10=Mucha Confianza)",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p34",
            page=page,
            order=7,
            row={
                "type": "select_one escala_1_10",
                "name": "p34_profesionalidad",
                "label": "34. En una escala del 1 al 10, donde 1 es “Nada profesional” y 10 es “Muy profesional”, ¿cómo calificaría la profesionalidad de la Fuerza Pública en su distrito?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p35",
            page=page,
            order=8,
            row={
                "type": "select_one escala_1_10",
                "name": "p35_calidad_servicio",
                "label": "35. En una escala del 1 al 10, donde 1 es “Muy mala” y 10 es “Muy buena”, ¿cómo califica la calidad del servicio policial en su distrito?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p36",
            page=page,
            order=9,
            row={
                "type": "select_one escala_1_10",
                "name": "p36_satisfaccion_preventivo",
                "label": "36. En una escala del 1 al 10, donde 1 es “Nada satisfecho(a)” y 10 es “Muy satisfecho(a)”, ¿qué tan satisfecho(a) está con el trabajo preventivo que realiza la Fuerza Pública en su distrito?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p37",
            page=page,
            order=10,
            row={
                "type": "select_one escala_1_10",
                "name": "p37_contribucion_reduccion_crimen",
                "label": "37. En una escala del 1 al 10, donde 1 es “No contribuye en nada” y 10 es “Contribuye muchísimo”, indique: ¿En qué medida considera que la presencia policial ayuda a reducir el crimen en su distrito?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p38",
            page=page,
            order=11,
            row={
                "type": "select_one p38_frecuencia",
                "name": "p38_frecuencia_presencia",
                "label": "38. ¿Con qué frecuencia observa presencia policial en su distrito?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p39",
            page=page,
            order=12,
            row={
                "type": "select_one p39_si_no_aveces",
                "name": "p39_presencia_consistente",
                "label": "39. ¿Considera que la presencia policial es consistente a lo largo del día en su distrito?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p40",
            page=page,
            order=13,
            row={
                "type": "select_one p39_si_no_aveces",
                "name": "p40_trato_justo",
                "label": "40. ¿Considera que la policía trata a las personas de manera justa e imparcial en su distrito?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p41",
            page=page,
            order=14,
            row={
                "type": "select_one p41_opciones",
                "name": "p41_quejas_sin_temor",
                "label": "41. ¿Cree usted que puede expresar preocupaciones o quejas a la policía sin temor a represalias?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p42",
            page=page,
            order=15,
            row={
                "type": "select_one p39_si_no_aveces",
                "name": "p42_info_veraz_clara",
                "label": "42. ¿Considera que la policía proporciona información veraz, clara y oportuna a la comunidad?",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p43",
            page=page,
            order=16,
            row={
                "type": "select_multiple p43_acciones_fp",
                "name": "p43_accion_fp_mejorar",
                "label": "43. ¿Qué actividad considera que debe realizar la Fuerza Pública para mejorar la seguridad en su comunidad?",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p43_otro",
            page=page,
            order=17,
            row={
                "type": "text",
                "name": "p43_otro_detalle",
                "label": "Otro (detalle):",
                "required": "no",
                "appearance": "multiline",
                "relevant": f"({rel_si}) and selected(${{p43_accion_fp_mejorar}}, '{slugify_name('Otro')}')"
            }
        ))

        qb.append(build_question_row(
            qid="p8_p44",
            page=page,
            order=18,
            row={
                "type": "select_multiple p44_acciones_muni",
                "name": "p44_accion_muni_mejorar",
                "label": "44. ¿Qué actividad considera que debe realizar la municipalidad para mejorar la seguridad en su comunidad?",
                "required": "yes",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p44_otro",
            page=page,
            order=19,
            row={
                "type": "text",
                "name": "p44_otro_detalle",
                "label": "Otro (detalle):",
                "required": "no",
                "appearance": "multiline",
                "relevant": f"({rel_si}) and selected(${{p44_accion_muni_mejorar}}, '{slugify_name('Otro')}')"
            }
        ))

        qb.append(build_question_row(
            qid="p8_info_adicional_titulo",
            page=page,
            order=20,
            row={
                "type": "note",
                "name": "p8_info_adicional_titulo",
                "label": "Información Adicional y Contacto Voluntario",
                "relevant": rel_si,
                "bind::esri:fieldType": "null"
            }
        ))

        qb.append(build_question_row(
            qid="p8_p45",
            page=page,
            order=21,
            row={
                "type": "select_one p45_info_delito",
                "name": "p45_info_delito",
                "label": "45. ¿Usted tiene información de alguna persona o grupo que se dedique a realizar algún delito en su comunidad? (Recuerde, su información es confidencial.)",
                "required": "yes",
                "appearance": "minimal",
                "relevant": rel_si
            }
        ))

        rel_451 = f"({rel_si}) and (${{p45_info_delito}}='{v_si}')"

        qb.append(build_question_row(
            qid="p8_p451",
            page=page,
            order=22,
            row={
                "type": "text",
                "name": "p451_detalle_info",
                "label": "45.1. Si su respuesta es \"Sí\", describa aquellas características que pueda aportar tales como nombre de estructura o banda criminal... (nombre de personas, alias, domicilio, vehículos, etc.)",
                "required": "yes",
                "appearance": "multiline",
                "relevant": rel_451
            }
        ))

        qb.append(build_question_row(
            qid="p8_p46",
            page=page,
            order=23,
            row={
                "type": "text",
                "name": "p46_contacto_voluntario",
                "label": "46. En el siguiente espacio de forma voluntaria podrá anotar su nombre, teléfono o correo electrónico en el cual desee ser contactado y continuar colaborando de forma confidencial con Fuerza Pública.",
                "required": "no",
                "appearance": "multiline",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_p47",
            page=page,
            order=24,
            row={
                "type": "text",
                "name": "p47_info_adicional",
                "label": "47. En el siguiente espacio podrá registrar alguna otra información que estime pertinente.",
                "required": "no",
                "appearance": "multiline",
                "relevant": rel_si
            }
        ))

        qb.append(build_question_row(
            qid="p8_fin_note",
            page=page,
            order=25,
            row={
                "type": "note",
                "name": "p8_fin",
                "label": "---------------------------------- Fin de la Encuesta ----------------------------------",
                "relevant": rel_si,
                "bind::esri:fieldType": "null"
            }
        ))

        qb.append(build_question_row(
            qid="p8_end_group",
            page=page,
            order=26,
            row={"type": "end_group", "name": "p8_end"}
        ))

    # Guardar y compactar órdenes
    st.session_state["questions_bank"] = sort_questions(qb)
    for p in ["p5", "p6", "p7", "p8"]:
        update_orders_compact(p)

seed_questions_bank_p5_p8_if_missing()

# ==========================================================================================
# Confirmación visual (opcional): ya debe estar todo P1..P8 en el Editor
# ==========================================================================================
if st.session_state["ui_mode"] == "Editor":
    st.success("✅ Formulario completo precargado en el Editor (P1 a P8). Ya puedes editar y reordenar todo.")
    st.caption("Siguiente paso (Parte 5): Editor de listas 'choices' (yesno, genero, escolaridad, etc.) + validaciones y catálogo editable.")

# ==========================================================================================
# FIN PARTE 4/10
# - En la Parte 5:
#   1) Construimos el Editor de CHOICES (listas) para que puedas editar opciones sin tocar código
#   2) Validaciones: evitar duplicados list_name/name, reconstruir slugs, etc.
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (5/10) ====================================
# ====== App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 8) + Cantón→Distrito =====
# ==========================================================================================
#
# PARTE 5/10 — Qué agrega:
# 1) Editor de CHOICES (listas):
#    - Ver todas las listas (list_name)
#    - Editar opciones (name/label y columnas extra si existen)
#    - Agregar / duplicar / eliminar opciones
#    - Validar duplicados (list_name + name)
#    - Re-generar slug (name) desde label si lo deseas
#
# 2) Integración con Cantón→Distrito:
#    - list_canton y list_distrito se pueden ver/editar desde el mismo editor
#    - Mantiene la columna extra "canton_key" en list_distrito
#
# IMPORTANTE:
# - Esto NO exporta todavía (eso en Partes 7–8).
# - Esto deja TODO editable en UI (preguntas + listas).
# ==========================================================================================

# ==========================================================================================
# NUEVO — Inicialización del banco editable de choices en session_state
# ==========================================================================================
def seed_choices_bank_if_empty(form_title: str, logo_media_name: str):
    """
    Crea st.session_state["choices_bank"] si no existe.
    Fuente:
      - choices base vienen de tu _construir_choices_y_base(...)
      - + se agregan list_canton/list_distrito desde st.session_state.choices_ext_rows
    """
    if st.session_state.get("choices_bank"):
        return

    # choices base del formulario (tu catálogo original)
    _survey_rows_unused, choices_rows, _v_si, _v_no = _construir_choices_y_base(form_title, logo_media_name)

    # integrar catálogo Cantón→Distrito si existe
    for r in st.session_state.get("choices_ext_rows", []):
        choices_rows.append(dict(r))

    st.session_state["choices_bank"] = choices_rows

seed_choices_bank_if_empty(form_title=form_title, logo_media_name=logo_media_name)

# ==========================================================================================
# NUEVO — Helpers de edición de choices
# ==========================================================================================
def _choice_key(r: dict) -> tuple[str, str]:
    return (str(r.get("list_name", "")).strip(), str(r.get("name", "")).strip())

def get_all_list_names() -> list[str]:
    bank = st.session_state.get("choices_bank", [])
    names = sorted({str(r.get("list_name", "")).strip() for r in bank if str(r.get("list_name", "")).strip()})
    return names

def get_choices_for_list(list_name: str) -> list[dict]:
    bank = st.session_state.get("choices_bank", [])
    items = [r for r in bank if str(r.get("list_name", "")).strip() == list_name]
    return items

def ensure_unique_choice_name(list_name: str, base_name: str, ignore_index: int | None = None) -> str:
    bank = st.session_state.get("choices_bank", [])
    used = set()
    for i, r in enumerate(bank):
        if ignore_index is not None and i == ignore_index:
            continue
        if str(r.get("list_name", "")).strip() == list_name:
            used.add(str(r.get("name", "")).strip())

    if base_name not in used:
        return base_name

    i = 2
    while f"{base_name}_{i}" in used:
        i += 1
    return f"{base_name}_{i}"

def validate_choices_bank() -> list[str]:
    """
    Devuelve lista de errores/warnings (strings).
    """
    msgs = []
    bank = st.session_state.get("choices_bank", [])

    # Duplicados list_name+name
    seen = {}
    for i, r in enumerate(bank):
        k = _choice_key(r)
        if not k[0] or not k[1]:
            continue
        if k in seen:
            msgs.append(f"Duplicado en choices: list_name='{k[0]}' name='{k[1]}' (filas {seen[k]} y {i})")
        else:
            seen[k] = i

    # list_distrito debe tener canton_key
    for i, r in enumerate(bank):
        if str(r.get("list_name", "")).strip() == "list_distrito":
            if not str(r.get("canton_key", "")).strip():
                msgs.append(f"list_distrito sin canton_key en fila {i} (name='{r.get('name','')}')")

    return msgs

def rebuild_choice_name_from_label(index: int):
    """
    Recalcula 'name' usando slugify_name(label) y asegura unicidad en su list_name.
    """
    bank = st.session_state.get("choices_bank", [])
    if index < 0 or index >= len(bank):
        return

    r = bank[index]
    list_name = str(r.get("list_name", "")).strip()
    label = str(r.get("label", "")).strip()

    if not list_name:
        return

    base = slugify_name(label) if label else "opcion"
    unique = ensure_unique_choice_name(list_name, base, ignore_index=index)
    r["name"] = unique
    bank[index] = r
    st.session_state["choices_bank"] = bank

def add_choice_row(list_name: str, label: str, name: str = "", extras: dict | None = None):
    bank = st.session_state.get("choices_bank", [])
    ln = str(list_name).strip()
    if not ln:
        return

    lab = str(label).strip()
    nm = str(name).strip()

    if not nm:
        nm = slugify_name(lab) if lab else "opcion"

    nm = ensure_unique_choice_name(ln, nm, ignore_index=None)

    row = {"list_name": ln, "name": nm, "label": lab}
    if extras:
        for k, v in extras.items():
            row[k] = v

    bank.append(row)
    st.session_state["choices_bank"] = bank

def delete_choice_row(index: int):
    bank = st.session_state.get("choices_bank", [])
    if index < 0 or index >= len(bank):
        return
    bank.pop(index)
    st.session_state["choices_bank"] = bank

def duplicate_choice_row(index: int):
    bank = st.session_state.get("choices_bank", [])
    if index < 0 or index >= len(bank):
        return

    r = dict(bank[index])
    ln = str(r.get("list_name", "")).strip()
    nm = str(r.get("name", "")).strip()

    if ln and nm:
        nm2 = ensure_unique_choice_name(ln, nm, ignore_index=None)
        r["name"] = nm2

    bank.append(r)
    st.session_state["choices_bank"] = bank

def sync_canton_distrito_to_choices_ext_rows():
    """
    Toma del choices_bank las filas list_canton y list_distrito y las coloca en st.session_state.choices_ext_rows.
    Esto mantiene compatibilidad con la UI original de catálogo (por lotes).
    """
    bank = st.session_state.get("choices_bank", [])
    ext = []
    for r in bank:
        ln = str(r.get("list_name", "")).strip()
        if ln in ("list_canton", "list_distrito"):
            ext.append(dict(r))
    st.session_state["choices_ext_rows"] = ext

# ==========================================================================================
# EDITOR UI — CHOICES (solo en modo Editor)
# ==========================================================================================
if st.session_state["ui_mode"] == "Editor":
    st.markdown("---")
    st.subheader("🧾 Editor de listas (choices)")

    # Validaciones
    msgs = validate_choices_bank()
    if msgs:
        with st.expander("⚠️ Advertencias / validaciones", expanded=True):
            for m in msgs:
                st.warning(m)
    else:
        st.success("✅ Choices sin duplicados críticos detectados.")

    # Selector de lista
    list_names = get_all_list_names()
    if not list_names:
        st.warning("No hay listas en choices_bank.")
    else:
        if "choices_list_selected" not in st.session_state:
            st.session_state["choices_list_selected"] = list_names[0]

        # si desaparece, reponer
        if st.session_state["choices_list_selected"] not in list_names:
            st.session_state["choices_list_selected"] = list_names[0]

        st.session_state["choices_list_selected"] = st.selectbox(
            "Seleccione la lista (list_name):",
            options=list_names,
            index=list_names.index(st.session_state["choices_list_selected"])
        )

        current_list = st.session_state["choices_list_selected"]
        items = get_choices_for_list(current_list)

        # Mostrar tabla
        df_items = pd.DataFrame(items).fillna("")
        st.dataframe(df_items, use_container_width=True, hide_index=True, height=260)

        # Seleccionar fila por índice dentro del banco global (para editar con precisión)
        bank = st.session_state.get("choices_bank", [])
        indices_list = [i for i, r in enumerate(bank) if str(r.get("list_name", "")).strip() == current_list]

        if "choice_row_selected_idx" not in st.session_state:
            st.session_state["choice_row_selected_idx"] = indices_list[0] if indices_list else -1

        if indices_list and st.session_state["choice_row_selected_idx"] not in indices_list:
            st.session_state["choice_row_selected_idx"] = indices_list[0]

        st.markdown("#### ✏️ Editar una opción")

        if not indices_list:
            st.info("Esta lista está vacía. Puedes agregar nuevas opciones abajo.")
        else:
            def _fmt_choice_idx(i: int) -> str:
                r = bank[i]
                return f"[{i}] {r.get('name','')} — {r.get('label','')}".strip()

            st.session_state["choice_row_selected_idx"] = st.selectbox(
                "Seleccione la opción (fila):",
                options=indices_list,
                format_func=_fmt_choice_idx,
                index=indices_list.index(st.session_state["choice_row_selected_idx"])
            )

            sel_i = st.session_state["choice_row_selected_idx"]
            row = dict(bank[sel_i])

            colx1, colx2 = st.columns(2)
            with colx1:
                new_list_name = st.text_input("list_name", value=str(row.get("list_name", "")))
                new_name = st.text_input("name", value=str(row.get("name", "")))
            with colx2:
                new_label = st.text_input("label", value=str(row.get("label", "")))

            # Campos extra (si existen)
            extras_keys = [k for k in row.keys() if k not in ("list_name", "name", "label")]
            extras_updates = {}
            if extras_keys:
                st.markdown("**Campos extra:**")
                for k in extras_keys:
                    extras_updates[k] = st.text_input(k, value=str(row.get(k, "")))

            colbtn1, colbtn2, colbtn3, colbtn4 = st.columns(4)
            with colbtn1:
                if st.button("💾 Guardar opción", use_container_width=True):
                    # normalizar list_name
                    ln = str(new_list_name).strip()
                    nm = str(new_name).strip()
                    lab = str(new_label).strip()

                    if not ln:
                        st.error("list_name no puede estar vacío.")
                        st.stop()

                    if not nm:
                        nm = slugify_name(lab) if lab else "opcion"

                    # asegurar unicidad (en la lista ln)
                    nm = ensure_unique_choice_name(ln, nm, ignore_index=sel_i)

                    row["list_name"] = ln
                    row["name"] = nm
                    row["label"] = lab

                    for k, v in extras_updates.items():
                        row[k] = v

                    bank[sel_i] = row
                    st.session_state["choices_bank"] = bank

                    # Si editaste list_canton/list_distrito, sincronizar
                    if ln in ("list_canton", "list_distrito") or str(row.get("list_name", "")).strip() in ("list_canton", "list_distrito"):
                        sync_canton_distrito_to_choices_ext_rows()

                    st.success("Opción guardada.")
                    st.rerun()

            with colbtn2:
                if st.button("🔁 name desde label (slug)", use_container_width=True):
                    rebuild_choice_name_from_label(sel_i)
                    if str(bank[sel_i].get("list_name", "")).strip() in ("list_canton", "list_distrito"):
                        sync_canton_distrito_to_choices_ext_rows()
                    st.success("name regenerado desde label.")
                    st.rerun()

            with colbtn3:
                if st.button("📄 Duplicar opción", use_container_width=True):
                    duplicate_choice_row(sel_i)
                    if str(bank[sel_i].get("list_name", "")).strip() in ("list_canton", "list_distrito"):
                        sync_canton_distrito_to_choices_ext_rows()
                    st.success("Opción duplicada.")
                    st.rerun()

            with colbtn4:
                if st.button("🗑️ Eliminar opción", use_container_width=True):
                    delete_choice_row(sel_i)
                    sync_canton_distrito_to_choices_ext_rows()
                    st.success("Opción eliminada.")
                    st.rerun()

        st.markdown("---")
        st.subheader("➕ Agregar opción a esta lista")

        coln1, coln2, coln3 = st.columns([2, 3, 3])
        with coln1:
            add_list_name = st.text_input("list_name (nuevo)", value=current_list)
        with coln2:
            add_label = st.text_input("label (nuevo)", value="")
        with coln3:
            add_name = st.text_input("name (opcional)", value="", help="Si lo dejas vacío se genera desde label con slugify_name().")

        # canton_key para list_distrito
        extras = {}
        if str(add_list_name).strip() == "list_distrito":
            extras["canton_key"] = st.text_input("canton_key (solo para list_distrito)", value="", help="Debe coincidir con el name del cantón (slug).")

        if st.button("✅ Agregar opción", use_container_width=True):
            add_choice_row(add_list_name, add_label, add_name, extras=extras if extras else None)
            if str(add_list_name).strip() in ("list_canton", "list_distrito"):
                sync_canton_distrito_to_choices_ext_rows()
            st.success("Opción agregada.")
            st.rerun()

        st.caption(
            "Tip: Si trabajas en list_distrito, asegúrate de completar canton_key para que el choice_filter funcione."
        )

# ==========================================================================================
# FIN PARTE 5/10
# - En la Parte 6:
#   1) Editor del GLOSARIO (términos + definiciones) y asignación por página
#   2) Botones para agregar términos al glosario de cada página desde la app
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (6/10) ====================================
# ====== App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 8) + Cantón→Distrito =====
# ==========================================================================================
#
# PARTE 6/10 — Qué agrega:
# 1) Editor del GLOSARIO (término -> definición):
#    - Agregar / editar / eliminar términos
#    - Mantener definiciones por página (qué términos aparecen en P4, P5, P6, P7, P8)
#
# 2) UI para asignación por página:
#    - Multiselect por página para seleccionar términos del glosario
#    - Botón para "aplicar" y guardar
#
# IMPORTANTE:
# - Todavía NO exportamos glosario dinámicamente al XLSForm (eso en Parte 8).
# - Aquí solo dejamos todo editable y persistente en session_state.
# ==========================================================================================

# ==========================================================================================
# NUEVO — Inicialización / semillas del glosario editable
# ==========================================================================================
def seed_glosario_bank_if_missing():
    """
    Crea:
      - st.session_state["glosario_bank"] : dict termino->definición
      - st.session_state["glosario_pages"]: dict page_id->list de términos
    Solo si no existe ya.
    """
    if "glosario_bank" not in st.session_state:
        st.session_state["glosario_bank"] = dict(GLOSARIO_DEFINICIONES)

    if "glosario_pages" not in st.session_state:
        # Si ya existía la config anterior (Parte 2), la respetamos
        if "glosario_config" in st.session_state:
            st.session_state["glosario_pages"] = dict(st.session_state["glosario_config"])
        else:
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
# NUEVO — Helpers glosario
# ==========================================================================================
def get_glosario_terms() -> list[str]:
    gb = st.session_state.get("glosario_bank", {})
    return sorted([t for t in gb.keys() if str(t).strip()])

def add_glosario_term(term: str, definition: str):
    t = str(term).strip()
    d = str(definition).strip()
    if not t:
        return
    gb = st.session_state.get("glosario_bank", {})
    gb[t] = d
    st.session_state["glosario_bank"] = gb

def delete_glosario_term(term: str):
    t = str(term).strip()
    gb = st.session_state.get("glosario_bank", {})
    if t in gb:
        gb.pop(t, None)
    st.session_state["glosario_bank"] = gb

    # quitar de asignaciones por página
    gp = st.session_state.get("glosario_pages", {})
    for p, arr in gp.items():
        gp[p] = [x for x in arr if x != t]
    st.session_state["glosario_pages"] = gp

def set_glosario_page_terms(page_id: str, terms: list[str]):
    gp = st.session_state.get("glosario_pages", {})
    gp[page_id] = list(terms)
    st.session_state["glosario_pages"] = gp

def get_glosario_page_terms(page_id: str) -> list[str]:
    gp = st.session_state.get("glosario_pages", {})
    return list(gp.get(page_id, []))

# ==========================================================================================
# EDITOR UI — GLOSARIO (solo en modo Editor)
# ==========================================================================================
if st.session_state["ui_mode"] == "Editor":
    st.markdown("---")
    st.subheader("📚 Editor del glosario (términos y definiciones)")

    gb = st.session_state.get("glosario_bank", {})
    terms = get_glosario_terms()

    # Vista rápida
    df_glos = pd.DataFrame(
        [{"Término": t, "Definición": gb.get(t, "")} for t in terms]
    ).fillna("")
    st.dataframe(df_glos, use_container_width=True, hide_index=True, height=260)

    st.markdown("#### ➕ Agregar nuevo término")
    colg1, colg2 = st.columns([2, 4])
    with colg1:
        new_term = st.text_input("Término (nuevo)", value="")
    with colg2:
        new_def = st.text_area("Definición (nuevo)", value="", height=90)

    if st.button("✅ Agregar término al glosario", use_container_width=True):
        if not str(new_term).strip():
            st.error("El término no puede estar vacío.")
        else:
            add_glosario_term(new_term, new_def)
            st.success("Término agregado/actualizado.")
            st.rerun()

    st.markdown("---")
    st.subheader("✏️ Editar / eliminar un término existente")

    if terms:
        if "glosario_term_selected" not in st.session_state:
            st.session_state["glosario_term_selected"] = terms[0]

        if st.session_state["glosario_term_selected"] not in terms:
            st.session_state["glosario_term_selected"] = terms[0]

        st.session_state["glosario_term_selected"] = st.selectbox(
            "Seleccione término:",
            options=terms,
            index=terms.index(st.session_state["glosario_term_selected"])
        )

        sel_term = st.session_state["glosario_term_selected"]
        sel_def = gb.get(sel_term, "")

        edit_def = st.text_area("Definición", value=sel_def, height=120)

        colg3, colg4 = st.columns(2)
        with colg3:
            if st.button("💾 Guardar definición", use_container_width=True):
                add_glosario_term(sel_term, edit_def)
                st.success("Definición guardada.")
                st.rerun()
        with colg4:
            if st.button("🗑️ Eliminar término", use_container_width=True):
                delete_glosario_term(sel_term)
                st.success("Término eliminado.")
                st.rerun()
    else:
        st.info("Aún no hay términos en el glosario. Agrega el primero arriba.")

    st.markdown("---")
    st.subheader("🧩 Asignar términos del glosario por página")

    pages = [("p4", "P4 — Percepción"), ("p5", "P5 — Riesgos"), ("p6", "P6 — Delitos"), ("p7", "P7 — Victimización"), ("p8", "P8 — Confianza/Cierre")]

    for pid, plab in pages:
        with st.expander(f"{plab} — términos del glosario", expanded=False):
            current_terms = get_glosario_page_terms(pid)
            chosen = st.multiselect(
                "Seleccione términos a mostrar en esta página:",
                options=get_glosario_terms(),
                default=[t for t in current_terms if t in get_glosario_terms()],
                key=f"glos_page_{pid}"
            )
            if st.button(f"💾 Guardar glosario de {plab}", key=f"save_glos_{pid}", use_container_width=True):
                set_glosario_page_terms(pid, chosen)
                st.success(f"Glosario guardado para {plab}.")
                st.rerun()

    st.caption("Siguiente paso (Parte 7): export dinámico: construir df_survey/df_choices/df_settings desde questions_bank + choices_bank.")

# ==========================================================================================
# FIN PARTE 6/10
# - En la Parte 7:
#   1) Dejamos de construir el XLSForm “hardcodeado”
#   2) Generamos el XLSForm desde lo que edites en la UI:
#      - survey = questions_bank
#      - choices = choices_bank (incluye cantón/distrito)
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (7/10) ====================================
# ====== App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 8) + Cantón→Distrito =====
# ==========================================================================================
#
# PARTE 7/10 — Qué agrega:
# 1) Export dinámico (SIN hardcode):
#    - df_survey se arma desde st.session_state["questions_bank"]
#    - df_choices se arma desde st.session_state["choices_bank"]
#    - df_settings se arma desde inputs (form_title, version, idioma, style=pages)
#
# 2) Mantiene compatibilidad con tu UI original:
#    - Botón "🧮 Construir XLSForm" sigue existiendo
#    - Descarga XLSForm (Excel) sigue usando descargar_xlsform(...)
#
# IMPORTANTE:
# - Todavía NO insertamos glosario dinámico dentro del survey (eso en Parte 8).
# - Pero ya se exporta TODO lo que edites: preguntas, orden, condicionales, constraints, etc.
# ==========================================================================================

# ==========================================================================================
# NUEVO — Helper: convertir questions_bank a DataFrame survey
# ==========================================================================================
def build_df_survey_from_bank():
    """
    Construye el df_survey (hoja survey) basado en questions_bank.
    Respeta orden por page y por 'order' dentro de page.

    Estructura base de cada item del banco:
      {"qid":..., "page":..., "order":..., "row":{...}}
    """
    qb = st.session_state.get("questions_bank", [])

    # Orden global: por page_order (st.session_state["page_order"]) y luego por order
    page_order = st.session_state.get("page_order", ["p1","p2","p3","p4","p5","p6","p7","p8"])
    page_rank = {p: i for i, p in enumerate(page_order)}

    qb_sorted = sorted(
        qb,
        key=lambda x: (page_rank.get(x.get("page", ""), 999), int(x.get("order", 0)))
    )

    survey_rows = []
    for item in qb_sorted:
        row = dict(item.get("row", {}) or {})
        # Limpieza mínima: si es note y no trae bind null, lo ponemos
        if str(row.get("type", "")).strip() == "note":
            if str(row.get("bind::esri:fieldType", "")).strip() == "":
                row["bind::esri:fieldType"] = "null"
        survey_rows.append(row)

    survey_cols = [
        "type", "name", "label", "required", "appearance",
        "relevant", "choice_filter",
        "constraint", "constraint_message",
        "media::image",
        "bind::esri:fieldType"
    ]
    df_survey = pd.DataFrame(survey_rows, columns=survey_cols).fillna("")
    return df_survey

# ==========================================================================================
# NUEVO — Helper: construir df_choices desde choices_bank
# ==========================================================================================
def build_df_choices_from_bank():
    """
    Construye df_choices (hoja choices) desde st.session_state["choices_bank"].
    Mantiene columnas extra (ej. canton_key).
    """
    bank = st.session_state.get("choices_bank", [])
    if not bank:
        return pd.DataFrame(columns=["list_name", "name", "label"])

    # columnas
    cols = set()
    for r in bank:
        cols.update((r or {}).keys())

    base_cols = ["list_name", "name", "label"]
    for c in sorted(cols):
        if c not in base_cols:
            base_cols.append(c)

    df_choices = pd.DataFrame(bank, columns=base_cols).fillna("")
    return df_choices

# ==========================================================================================
# NUEVO — Helper: construir df_settings
# ==========================================================================================
def build_df_settings(form_title: str, version: str, idioma: str):
    df_settings = pd.DataFrame([{
        "form_title": form_title,
        "version": version,
        "default_language": idioma,
        "style": "pages"
    }], columns=["form_title", "version", "default_language", "style"]).fillna("")
    return df_settings

# ==========================================================================================
# NUEVO — Validaciones pre-export (para evitar XLSForm roto)
# ==========================================================================================
def validate_before_export() -> list[str]:
    """
    Valida cosas básicas:
      - name vacío en preguntas (excepto end_group/end/begin_group pueden tener)
      - duplicados de name en survey (muy importante)
      - duplicados list_name+name en choices
      - list_distrito debe tener canton_key
    """
    errs = []

    # survey: duplicados name (solo para filas que tengan name)
    qb = st.session_state.get("questions_bank", [])
    names = []
    for q in qb:
        row = q.get("row", {}) or {}
        nm = str(row.get("name", "")).strip()
        tp = str(row.get("type", "")).strip()
        # begin/end groups pueden tener name (normalmente tienen), end suele tener name también
        # lo importante es evitar duplicados si hay name
        if nm:
            names.append(nm)

        # name vacío en tipos que deberían tenerlo
        if tp not in ("",) and tp not in ("end_group",) and tp != "":
            # allow empty name for some edge cases, pero en XLSForm normalmente debe existir
            if tp not in ("",) and tp not in ("end_group",) and tp not in ("end",) and tp not in ("begin_group",):
                if not nm:
                    errs.append(f"Pregunta con type='{tp}' sin name (qid='{q.get('qid','')}').")

    # duplicados
    seen = set()
    dups = set()
    for nm in names:
        if nm in seen:
            dups.add(nm)
        seen.add(nm)
    for nm in sorted(dups):
        errs.append(f"Duplicado en survey: name='{nm}'.")

    # choices: duplicados list_name+name y canton_key requerido en list_distrito
    errs.extend(validate_choices_bank())

    return errs

# ==========================================================================================
# NUEVO — Export dinámico (reemplaza construir_xlsform_final al exportar)
# ==========================================================================================
def construir_xlsform_final_dinamico(form_title: str, logo_media_name: str, idioma: str, version: str):
    """
    Construye df_survey/df_choices/df_settings usando los bancos editables.
    El logo en sí:
      - P1 ya tiene un note con media::image editable en questions_bank
      - Aquí solo construimos dataframes
    """
    # Asegurar que list_canton/list_distrito también esté sincronizado
    sync_canton_distrito_to_choices_ext_rows()

    df_survey = build_df_survey_from_bank()
    df_choices = build_df_choices_from_bank()
    df_settings = build_df_settings(form_title=form_title, version=version, idioma=idioma)
    return df_survey, df_choices, df_settings

# ==========================================================================================
# MODIFICACIÓN — Sección Exportar (UI) ahora usa el constructor dinámico
# ==========================================================================================
st.markdown("---")
st.subheader("📦 Generar XLSForm (Survey123) — Export dinámico (editable)")

idioma = st.selectbox("Idioma (default_language)", options=["es", "en"], index=0, key="idioma_export")
version_auto = datetime.now().strftime("%Y%m%d%H%M")
version = st.text_input("Versión (settings.version)", value=version_auto, key="version_export")

if st.button("🧮 Construir XLSForm", use_container_width=True, key="btn_build_xlsform"):
    # Validar antes de exportar
    errors = validate_before_export()
    if errors:
        st.error("Hay validaciones pendientes. Corrige esto antes de exportar:")
        for e in errors:
            st.write(f"- {e}")
        st.stop()

    # Construir dinámico desde lo editado
    df_survey, df_choices, df_settings = construir_xlsform_final_dinamico(
        form_title=form_title,
        logo_media_name=logo_media_name,
        idioma=idioma,
        version=version.strip() or version_auto
    )

    st.success("XLSForm construido (dinámico). Vista previa rápida:")
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
4) El glosario aparece solo si la persona marca **Sí** (en Parte 8 lo inyectamos dinámicamente según lo que edites).
""")

# ==========================================================================================
# FIN PARTE 7/10
# - En la Parte 8:
#   1) Inyectamos el GLOSARIO dinámico dentro del survey al exportar:
#      - Para cada página (p4..p8): agrega pregunta "¿Desea acceder al glosario?"
#      - Agrega begin_group/end_group y notes con definiciones según glosario_pages
#   2) Mantenerlo "dentro" de la página para pages style (field-list)
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (8/10) ====================================
# ====== App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 8) + Cantón→Distrito =====
# ==========================================================================================
#
# PARTE 8/10 — Qué agrega:
# 1) INYECCIÓN dinámica del GLOSARIO al exportar:
#    - Usa:
#        st.session_state["glosario_bank"]  (término -> definición)
#        st.session_state["glosario_pages"] (página -> lista de términos)
#    - Inserta dentro de cada página (P4..P8) un bloque:
#        a) select_one yesno: "{page}_accede_glosario"
#        b) begin_group: "{page}_glosario"
#        c) note intro
#        d) notes de definiciones
#        e) note cierre
#        f) end_group
#
# 2) Mantiene el glosario dentro de la página (pages style + field-list),
#    porque lo inyectamos ANTES del end_group de la página.
#
# IMPORTANTE:
# - No rompe tu formulario: solo agrega filas extra al df_survey antes de exportar.
# ==========================================================================================

# ==========================================================================================
# NUEVO — Helpers para inyección de glosario en df_survey (DataFrame)
# ==========================================================================================
def _build_glosario_rows_for_page(page_id: str, relevant_base: str, v_si: str) -> list[dict]:
    """
    Construye filas (dicts) para insertar el glosario en la hoja survey.
    Se basa en glosario_pages[page_id] y glosario_bank[termino].
    """
    gb = st.session_state.get("glosario_bank", {}) or {}
    gp = st.session_state.get("glosario_pages", {}) or {}

    terminos = [t for t in gp.get(page_id, []) if t in gb and str(t).strip()]
    if not terminos:
        return []

    # pregunta para abrir glosario
    q_open = {
        "type": "select_one yesno",
        "name": f"{page_id}_accede_glosario",
        "label": "¿Desea acceder al glosario de esta sección?",
        "required": "no",
        "appearance": "minimal",
        "relevant": relevant_base
    }

    rel_glos = f"({relevant_base}) and (${{{page_id}_accede_glosario}}='{v_si}')"

    rows = [q_open]

    rows.append({
        "type": "begin_group",
        "name": f"{page_id}_glosario",
        "label": "Glosario",
        "relevant": rel_glos
    })

    rows.append({
        "type": "note",
        "name": f"{page_id}_glosario_intro",
        "label": "A continuación, se muestran definiciones de términos que aparecen en esta sección.",
        "relevant": rel_glos,
        "bind::esri:fieldType": "null"
    })

    for idx, t in enumerate(terminos, start=1):
        rows.append({
            "type": "note",
            "name": f"{page_id}_glos_{idx}",
            "label": str(gb.get(t, "")).strip(),
            "relevant": rel_glos,
            "bind::esri:fieldType": "null"
        })

    rows.append({
        "type": "note",
        "name": f"{page_id}_glosario_cierre",
        "label": "Para continuar con la encuesta, desplácese hacia arriba y continúe con normalidad.",
        "relevant": rel_glos,
        "bind::esri:fieldType": "null"
    })

    rows.append({
        "type": "end_group",
        "name": f"{page_id}_glosario_end"
    })

    return rows

def inject_glosario_into_df_survey(df_survey: pd.DataFrame) -> pd.DataFrame:
    """
    Inserta el glosario por página (p4..p8) justo ANTES del end_group de cada página.
    Para poder ubicar el end_group de cada página, nos apoyamos en:
      - begin_group name: p4_percepcion_distrito / p5_riesgos / p6_delitos / p7_victimizacion / p8_confianza_policial
      - end_group name:   p4_end / p5_end / p6_end / p7_end / p8_end

    Si no encuentra el end_group, no inserta (para no romper).
    """
    # Importantísimo: df_survey ya viene ordenado (Parte 7)
    rows = df_survey.to_dict(orient="records")

    v_si = slugify_name("Sí")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    page_to_endname = {
        "p4": "p4_end",
        "p5": "p5_end",
        "p6": "p6_end",
        "p7": "p7_end",
        "p8": "p8_end",
    }

    # Insertar en orden p4..p8 para mantener estabilidad
    for pid in ["p4", "p5", "p6", "p7", "p8"]:
        end_name = page_to_endname.get(pid)
        if not end_name:
            continue

        # encontrar índice del end_group correspondiente
        idx_end = None
        for i, r in enumerate(rows):
            if str(r.get("type", "")).strip() == "end_group" and str(r.get("name", "")).strip() == end_name:
                idx_end = i
                break

        if idx_end is None:
            continue

        # construir glosario rows
        glos_rows = _build_glosario_rows_for_page(page_id=pid, relevant_base=rel_si, v_si=v_si)
        if not glos_rows:
            continue

        # insertar antes del end_group de la página
        rows = rows[:idx_end] + glos_rows + rows[idx_end:]

    # reconstruir DataFrame con mismas columnas
    survey_cols = [
        "type", "name", "label", "required", "appearance",
        "relevant", "choice_filter",
        "constraint", "constraint_message",
        "media::image",
        "bind::esri:fieldType"
    ]
    df_new = pd.DataFrame(rows, columns=survey_cols).fillna("")
    return df_new

# ==========================================================================================
# MODIFICACIÓN — constructor dinámico ahora inyecta glosario antes de exportar
# ==========================================================================================
def construir_xlsform_final_dinamico(form_title: str, logo_media_name: str, idioma: str, version: str):
    """
    Construye df_survey/df_choices/df_settings usando los bancos editables
    + Inyecta glosario por página según lo editado en la UI.
    """
    sync_canton_distrito_to_choices_ext_rows()

    df_survey = build_df_survey_from_bank()
    df_survey = inject_glosario_into_df_survey(df_survey)  # <-- NUEVO (Parte 8)

    df_choices = build_df_choices_from_bank()
    df_settings = build_df_settings(form_title=form_title, version=version, idioma=idioma)
    return df_survey, df_choices, df_settings

# ==========================================================================================
# MEJORA — Validación adicional: evitar duplicados de name tras inyectar glosario
# ==========================================================================================
def validate_before_export_with_glosario() -> list[str]:
    errs = validate_before_export()

    # Simular export para detectar duplicados post-inyección
    df_survey_tmp = build_df_survey_from_bank()
    df_survey_tmp = inject_glosario_into_df_survey(df_survey_tmp)

    names = [str(x).strip() for x in df_survey_tmp["name"].tolist() if str(x).strip()]
    seen = set()
    dups = set()
    for nm in names:
        if nm in seen:
            dups.add(nm)
        seen.add(nm)
    for nm in sorted(dups):
        errs.append(f"Duplicado en survey (post-glosario): name='{nm}'.")

    return errs

# ==========================================================================================
# MODIFICACIÓN — Botón export ahora usa validación con glosario
# ==========================================================================================
# (Reemplaza el bloque del if st.button("🧮 Construir XLSForm"... ) de la Parte 7)
if st.button("🧮 Construir XLSForm", use_container_width=True, key="btn_build_xlsform"):
    errors = validate_before_export_with_glosario()
    if errors:
        st.error("Hay validaciones pendientes. Corrige esto antes de exportar:")
        for e in errors:
            st.write(f"- {e}")
        st.stop()

    df_survey, df_choices, df_settings = construir_xlsform_final_dinamico(
        form_title=form_title,
        logo_media_name=logo_media_name,
        idioma=idioma,
        version=version.strip() or version_auto
    )

    st.success("XLSForm construido (dinámico + glosario). Vista previa rápida:")
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
4) El glosario aparece solo si la persona marca **Sí** (se inyecta automáticamente por página).
""")

# ==========================================================================================
# FIN PARTE 8/10
# - En la Parte 9:
#   1) Editor de "Dependencias y Condicionales" asistido:
#      - Wizard para construir relevant/constraint sin escribir expresiones a mano
#      - Botón "aplicar" que actualiza el row["relevant"] o row["constraint"]
#   2) Reglas rápidas (exclusión tipo: "No se observa" vs otras) como plantillas
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (9/10) ====================================
# ====== App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 8) + Cantón→Distrito =====
# ==========================================================================================
#
# PARTE 9/10 — Qué agrega:
# 1) Asistente (Wizard) para crear CONDICIONALES y VALIDACIONES sin escribir fórmulas:
#    - Construir 'relevant' (mostrar/ocultar) basado en otra pregunta
#    - Construir 'constraint' (reglas) basado en exclusión de opciones
#
# 2) Plantillas rápidas:
#    A) Relevant: "Mostrar si Q == valor"
#    B) Relevant: "Mostrar si Q contiene selección (select_multiple)"
#    C) Constraint: "Si marca 'No se observa', no marque otras"
#
# IMPORTANTE:
# - Esto NO reemplaza el editor manual: solo te ayuda a generar expresiones.
# - Se aplica sobre la pregunta seleccionada en el Editor de Preguntas (Parte 3).
# ==========================================================================================

# ==========================================================================================
# NUEVO — Helpers para wizard (trabaja sobre questions_bank)
# ==========================================================================================
def get_question_by_qid(qid: str) -> dict | None:
    qb = st.session_state.get("questions_bank", [])
    for q in qb:
        if q.get("qid") == qid:
            return q
    return None

def update_question_row_by_qid(qid: str, updates: dict):
    qb = st.session_state.get("questions_bank", [])
    for i, q in enumerate(qb):
        if q.get("qid") == qid:
            row = dict(q.get("row", {}) or {})
            row.update(updates)
            q["row"] = row
            qb[i] = q
            st.session_state["questions_bank"] = qb
            return

def list_questions_for_wizard() -> list[dict]:
    """
    Devuelve lista simplificada de preguntas (solo las que tienen name y type distinto de groups).
    """
    qb = st.session_state.get("questions_bank", [])
    out = []
    for q in qb:
        row = q.get("row", {}) or {}
        tp = str(row.get("type", "")).strip()
        nm = str(row.get("name", "")).strip()
        if not nm:
            continue
        # excluir grupos y notas por defecto (pero puedes cambiar esto)
        if tp in ("begin_group", "end_group", "note"):
            continue
        out.append({
            "qid": q.get("qid"),
            "page": q.get("page"),
            "order": q.get("order"),
            "type": tp,
            "name": nm,
            "label": str(row.get("label", "")).strip()
        })
    # orden por páginas
    page_order = st.session_state.get("page_order", ["p1","p2","p3","p4","p5","p6","p7","p8"])
    rank = {p:i for i,p in enumerate(page_order)}
    out.sort(key=lambda x: (rank.get(x["page"], 999), int(x["order"])))
    return out

def _choice_values_for_list(list_name: str) -> list[tuple[str, str]]:
    """
    Retorna lista de (value(name), label) para un list_name.
    """
    bank = st.session_state.get("choices_bank", [])
    vals = []
    for r in bank:
        if str(r.get("list_name","")).strip() == str(list_name).strip():
            vals.append((str(r.get("name","")).strip(), str(r.get("label","")).strip()))
    return vals

def _infer_list_name_from_type(type_str: str) -> str | None:
    """
    type_str puede ser:
      - "select_one yesno"
      - "select_multiple p19_delitos_general"
    Devuelve el list_name ("yesno", "p19_delitos_general") si aplica.
    """
    t = str(type_str).strip()
    if t.startswith("select_one "):
        return t.replace("select_one ", "", 1).strip()
    if t.startswith("select_multiple "):
        return t.replace("select_multiple ", "", 1).strip()
    return None

def wizard_build_relevant_equal(source_name: str, value_name: str) -> str:
    return f"${{{source_name}}}='{value_name}'"

def wizard_build_relevant_or_equals(source_name: str, values: list[str]) -> str:
    parts = [f"${{{source_name}}}='{v}'" for v in values if str(v).strip()]
    return " or ".join(parts) if parts else ""

def wizard_build_relevant_selected(source_name: str, value_name: str) -> str:
    return f"selected(${{{source_name}}}, '{value_name}')"

def wizard_build_constraint_exclusive_no_observa(target_name: str, no_obs_value: str, other_values: list[str]) -> str:
    """
    Regla:
      not( selected(., 'no_obs') and (selected(., 'a') or selected(., 'b') ... ) )
    En constraints de XLSForm, el punto '.' se refiere a la respuesta actual.
    """
    ors = " or ".join([f"selected(., '{v}')" for v in other_values if str(v).strip()])
    if not ors:
        return ""
    return f"not(selected(., '{no_obs_value}') and ({ors}))"

# ==========================================================================================
# WIZARD UI (solo en modo Editor)
# ==========================================================================================
if st.session_state["ui_mode"] == "Editor":
    st.markdown("---")
    st.subheader("🧙‍♂️ Asistente de condicionales y validaciones (Wizard)")

    # A qué pregunta vamos a aplicar el relevant/constraint?
    # Usamos la misma selección del Editor (Parte 3), si existe:
    target_qid = st.session_state.get("selected_qid", None)

    qs = list_questions_for_wizard()
    if not qs:
        st.info("No hay preguntas elegibles para el wizard aún.")
    else:
        # Selector de objetivo (si no hay uno, escoger primero)
        qid_options = [q["qid"] for q in qs]
        def _fmt_qid(qid: str) -> str:
            q = next((x for x in qs if x["qid"] == qid), None)
            if not q:
                return qid
            return f"{q['page'].upper()} | {q['name']} — {q['label'][:60]}"

        if not target_qid or target_qid not in qid_options:
            target_qid = qid_options[0]
            st.session_state["selected_qid"] = target_qid

        target_qid = st.selectbox(
            "Pregunta OBJETIVO (aquí se aplicará la fórmula):",
            options=qid_options,
            index=qid_options.index(target_qid),
            format_func=_fmt_qid,
            key="wizard_target_qid"
        )

        st.session_state["selected_qid"] = target_qid
        target_q = get_question_by_qid(target_qid)
        target_row = dict((target_q or {}).get("row", {}) or {})
        target_name = str(target_row.get("name", "")).strip()
        target_type = str(target_row.get("type", "")).strip()

        st.caption(f"Objetivo: type='{target_type}' name='{target_name}'")

        tab1, tab2 = st.tabs(["🧩 Crear relevant", "✅ Crear constraint"])

        # ==================================================================================
        # TAB 1 — relevant
        # ==================================================================================
        with tab1:
            st.markdown("#### 1) Mostrar/ocultar (relevant)")

            # Seleccionar pregunta fuente
            source_qid_options = [q["qid"] for q in qs if q["qid"] != target_qid]
            if not source_qid_options:
                st.info("No hay otra pregunta fuente disponible.")
            else:
                source_qid = st.selectbox(
                    "Pregunta FUENTE (condición se basa en esta):",
                    options=source_qid_options,
                    format_func=_fmt_qid,
                    key="wizard_source_qid"
                )

                source_q = get_question_by_qid(source_qid)
                source_row = dict((source_q or {}).get("row", {}) or {})
                source_name = str(source_row.get("name", "")).strip()
                source_type = str(source_row.get("type", "")).strip()

                st.caption(f"Fuente: type='{source_type}' name='{source_name}'")

                list_name = _infer_list_name_from_type(source_type)
                vals = _choice_values_for_list(list_name) if list_name else []

                mode = st.radio(
                    "Tipo de condición:",
                    options=[
                        "Igual a (select_one)",
                        "Es una de (OR)",
                        "Contiene selección (select_multiple)"
                    ],
                    index=0,
                    horizontal=True,
                    key="wizard_relevant_mode"
                )

                expr = ""

                if mode == "Igual a (select_one)":
                    if not vals:
                        value_raw = st.text_input("Valor (name) para comparar:", value="")
                        expr = wizard_build_relevant_equal(source_name, value_raw.strip())
                    else:
                        value_name = st.selectbox(
                            "Seleccione valor:",
                            options=[v[0] for v in vals],
                            format_func=lambda x: f"{x} — {dict(vals).get(x,'')}",
                            key="wizard_relevant_value_eq"
                        )
                        expr = wizard_build_relevant_equal(source_name, value_name)

                elif mode == "Es una de (OR)":
                    if not vals:
                        values_raw = st.text_area("Valores (name) uno por línea:", value="")
                        values = [x.strip() for x in values_raw.splitlines() if x.strip()]
                        expr = wizard_build_relevant_or_equals(source_name, values)
                    else:
                        chosen = st.multiselect(
                            "Seleccione uno o más valores:",
                            options=[v[0] for v in vals],
                            default=[],
                            format_func=lambda x: f"{x} — {dict(vals).get(x,'')}",
                            key="wizard_relevant_value_or"
                        )
                        expr = wizard_build_relevant_or_equals(source_name, chosen)

                else:  # contains selection
                    if not vals:
                        value_raw = st.text_input("Valor (name) requerido dentro del multiselect:", value="")
                        expr = wizard_build_relevant_selected(source_name, value_raw.strip())
                    else:
                        value_name = st.selectbox(
                            "Seleccione valor que debe estar seleccionado:",
                            options=[v[0] for v in vals],
                            format_func=lambda x: f"{x} — {dict(vals).get(x,'')}",
                            key="wizard_relevant_value_sel"
                        )
                        expr = wizard_build_relevant_selected(source_name, value_name)

                st.markdown("**Expresión generada:**")
                st.code(expr if expr else "", language="text")

                # Combinar con relevant existente
                existing_rel = str(target_row.get("relevant", "")).strip()
                combine = st.selectbox(
                    "¿Cómo aplicar?",
                    options=[
                        "Reemplazar relevant",
                        "AND con relevant existente",
                        "OR con relevant existente"
                    ],
                    index=0,
                    key="wizard_relevant_apply_mode"
                )

                final_expr = expr
                if existing_rel and expr:
                    if combine == "AND con relevant existente":
                        final_expr = f"({existing_rel}) and ({expr})"
                    elif combine == "OR con relevant existente":
                        final_expr = f"({existing_rel}) or ({expr})"

                col_apply1, col_apply2 = st.columns(2)
                with col_apply1:
                    if st.button("✅ Aplicar relevant a la pregunta objetivo", use_container_width=True, key="apply_relevant_btn"):
                        if not final_expr.strip():
                            st.error("No hay expresión para aplicar.")
                        else:
                            update_question_row_by_qid(target_qid, {"relevant": final_expr})
                            st.success("relevant aplicado.")
                            st.rerun()

                with col_apply2:
                    if st.button("🧹 Limpiar relevant (vaciar)", use_container_width=True, key="clear_relevant_btn"):
                        update_question_row_by_qid(target_qid, {"relevant": ""})
                        st.success("relevant eliminado.")
                        st.rerun()

        # ==================================================================================
        # TAB 2 — constraint
        # ==================================================================================
        with tab2:
            st.markdown("#### 2) Validación (constraint)")

            # Plantilla de exclusión "No observa" para select_multiple
            st.info("Plantilla rápida: exclusión tipo “No se observa…” vs otras opciones (select_multiple).")

            # Debe ser select_multiple
            if not str(target_type).startswith("select_multiple"):
                st.warning("Esta plantilla aplica mejor cuando la pregunta objetivo es select_multiple.")
            else:
                list_name_t = _infer_list_name_from_type(target_type)
                vals_t = _choice_values_for_list(list_name_t) if list_name_t else []

                if not vals_t:
                    st.warning("No pude encontrar choices para esta lista. Asegúrate de que list_name exista en choices.")
                else:
                    no_obs = st.selectbox(
                        "Seleccione la opción exclusiva (ej. 'No se observa...'):",
                        options=[v[0] for v in vals_t],
                        format_func=lambda x: f"{x} — {dict(vals_t).get(x,'')}",
                        key="wizard_constraint_noobs"
                    )

                    others = st.multiselect(
                        "Seleccione opciones que NO deben combinarse con la exclusiva:",
                        options=[v[0] for v in vals_t if v[0] != no_obs],
                        default=[v[0] for v in vals_t if v[0] != no_obs],
                        format_func=lambda x: f"{x} — {dict(vals_t).get(x,'')}",
                        key="wizard_constraint_others"
                    )

                    expr_c = wizard_build_constraint_exclusive_no_observa(
                        target_name=target_name,
                        no_obs_value=no_obs,
                        other_values=others
                    )

                    st.markdown("**Constraint generado:**")
                    st.code(expr_c if expr_c else "", language="text")

                    msg = st.text_input(
                        "constraint_message",
                        value="Si selecciona la opción exclusiva, no seleccione otras opciones simultáneamente.",
                        key="wizard_constraint_msg"
                    )

                    # Combinar con constraint existente
                    existing_c = str(target_row.get("constraint", "")).strip()
                    c_apply_mode = st.selectbox(
                        "¿Cómo aplicar constraint?",
                        options=[
                            "Reemplazar constraint",
                            "AND con constraint existente"
                        ],
                        index=0,
                        key="wizard_constraint_apply_mode"
                    )

                    final_c = expr_c
                    if existing_c and expr_c and c_apply_mode == "AND con constraint existente":
                        final_c = f"({existing_c}) and ({expr_c})"

                    colc1, colc2 = st.columns(2)
                    with colc1:
                        if st.button("✅ Aplicar constraint", use_container_width=True, key="apply_constraint_btn"):
                            if not final_c.strip():
                                st.error("No hay constraint para aplicar.")
                            else:
                                update_question_row_by_qid(target_qid, {
                                    "constraint": final_c,
                                    "constraint_message": msg
                                })
                                st.success("constraint aplicado.")
                                st.rerun()

                    with colc2:
                        if st.button("🧹 Limpiar constraint (vaciar)", use_container_width=True, key="clear_constraint_btn"):
                            update_question_row_by_qid(target_qid, {"constraint": "", "constraint_message": ""})
                            st.success("constraint eliminado.")
                            st.rerun()

# ==========================================================================================
# FIN PARTE 9/10
# - En la Parte 10:
#   1) Guardar/Cargar proyecto (JSON):
#      - Exportar configuración completa (questions_bank, choices_bank, glosario_bank, glosario_pages, page_order)
#      - Importar para continuar editando sin perder nada
#   2) Botón "Reset a defaults" (volver al formulario precargado)
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (10/10) ===================================
# ====== App: Encuesta Comunidad → XLSForm Survey123 (Páginas 1 a 8) + Cantón→Distrito =====
# ==========================================================================================
#
# PARTE 10/10 — Qué agrega:
# 1) Guardar / Cargar PROYECTO (JSON):
#    - Exporta toda la configuración editable:
#        - questions_bank
#        - choices_bank
#        - glosario_bank
#        - glosario_pages
#        - page_order
#    - Importa el JSON y restaura el editor EXACTO como estaba.
#
# 2) Reset a defaults:
#    - Vuelve a cargar el formulario precargado (preguntas base)
#    - Vuelve a cargar choices base
#    - Mantiene (opcional) el catálogo Cantón→Distrito si quieres
#
# IMPORTANTE:
# - Esto NO toca tu export Excel: solo guarda/recupera el "proyecto" del editor.
# ==========================================================================================

import json

# ==========================================================================================
# NUEVO — Helpers: defaults completos (volver al formulario base)
# ==========================================================================================
def reset_to_defaults(keep_canton_distrito: bool = True):
    """
    Reinicia el proyecto a los valores base:
      - questions_bank (desde tu construcción original, Parte 2)
      - choices_bank (choices base + opcional cantón/distrito)
      - glosario_bank / glosario_pages a valores iniciales
      - page_order default

    keep_canton_distrito:
      - True: conserva list_canton/list_distrito actuales
      - False: los elimina y deja solo choices base
    """
    # 1) reset page_order
    st.session_state["page_order"] = ["p1","p2","p3","p4","p5","p6","p7","p8"]

    # 2) reset questions_bank
    # reutiliza la semilla base de Parte 2
    st.session_state["questions_bank"] = []
    seed_questions_bank_if_missing(form_title=form_title, logo_media_name=logo_media_name)

    # 3) reset glosario
    st.session_state["glosario_bank"] = dict(GLOSARIO_DEFINICIONES)
    st.session_state["glosario_pages"] = {
        "p4": ["Extorsión", "Daños/vandalismo"],
        "p5": ["Búnkeres", "Receptación", "Contrabando", "Trata de personas", "Explotación infantil",
               "Acoso callejero", "Tráfico de personas (coyotaje)", "Estafa", "Tacha"],
        "p6": ["Receptación", "Contrabando", "Tráfico de personas (coyotaje)", "Acoso callejero",
               "Estafa", "Tacha", "Trata de personas", "Explotación infantil", "Extorsión", "Búnkeres"],
        "p7": ["Ganzúa (pata de chancho)", "Boquete", "Arrebato", "Receptación", "Extorsión"],
        "p8": ["Patrullaje", "Acciones disuasivas", "Coordinación interinstitucional", "Integridad y credibilidad policial"],
    }

    # 4) reset choices_bank
    # Primero base
    _survey_rows_unused, base_choices, _v_si, _v_no = _construir_choices_y_base(form_title, logo_media_name)

    if keep_canton_distrito:
        # conservar las filas list_canton/list_distrito existentes (si hay)
        current_ext = st.session_state.get("choices_ext_rows", [])
        for r in current_ext:
            base_choices.append(dict(r))
        st.session_state["choices_bank"] = base_choices
    else:
        st.session_state["choices_ext_rows"] = []
        st.session_state["choices_bank"] = base_choices

    # Limpia selecciones de UI
    st.session_state.pop("selected_qid", None)
    st.session_state.pop("choice_row_selected_idx", None)
    st.session_state.pop("choices_list_selected", None)
    st.session_state.pop("glosario_term_selected", None)

# ==========================================================================================
# NUEVO — Exportar proyecto a JSON
# ==========================================================================================
def build_project_payload() -> dict:
    payload = {
        "meta": {
            "app": "Encuesta Comunidad XLSForm Builder",
            "exported_at": datetime.now().isoformat(),
            "form_title": form_title,
        },
        "page_order": st.session_state.get("page_order", []),
        "questions_bank": st.session_state.get("questions_bank", []),
        "choices_bank": st.session_state.get("choices_bank", []),
        "glosario_bank": st.session_state.get("glosario_bank", {}),
        "glosario_pages": st.session_state.get("glosario_pages", {}),
    }
    return payload

def load_project_payload(payload: dict):
    """
    Carga proyecto desde dict ya parseado (JSON).
    Valida llaves mínimas antes de aplicar.
    """
    required = ["page_order", "questions_bank", "choices_bank", "glosario_bank", "glosario_pages"]
    for k in required:
        if k not in payload:
            raise ValueError(f"Falta la llave requerida en el proyecto: {k}")

    st.session_state["page_order"] = payload.get("page_order", ["p1","p2","p3","p4","p5","p6","p7","p8"])
    st.session_state["questions_bank"] = payload.get("questions_bank", [])
    st.session_state["choices_bank"] = payload.get("choices_bank", [])
    st.session_state["glosario_bank"] = payload.get("glosario_bank", {})
    st.session_state["glosario_pages"] = payload.get("glosario_pages", {})

    # mantener sincronizado choices_ext_rows (list_canton/list_distrito)
    sync_canton_distrito_to_choices_ext_rows()

    # limpiar selecciones
    st.session_state.pop("selected_qid", None)

# ==========================================================================================
# UI — Guardar / Cargar proyecto
# ==========================================================================================
st.markdown("---")
st.subheader("💾 Proyecto (Guardar / Cargar)")

colp1, colp2, colp3 = st.columns([2, 2, 2])

with colp1:
    st.markdown("### ⬇️ Guardar")
    if st.button("📦 Generar JSON del proyecto", use_container_width=True):
        payload = build_project_payload()
        st.session_state["_project_json"] = json.dumps(payload, ensure_ascii=False, indent=2)
        st.success("Proyecto listo para descargar.")

    if st.session_state.get("_project_json"):
        st.download_button(
            "📥 Descargar proyecto (.json)",
            data=st.session_state["_project_json"].encode("utf-8"),
            file_name=f"{slugify_name(form_title)}_proyecto.json",
            mime="application/json",
            use_container_width=True
        )

with colp2:
    st.markdown("### ⬆️ Cargar")
    up = st.file_uploader("Subir proyecto (.json)", type=["json"], key="upload_project_json")
    if up:
        try:
            raw = up.getvalue().decode("utf-8")
            payload = json.loads(raw)
            load_project_payload(payload)
            st.success("Proyecto cargado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo cargar el proyecto: {e}")

with colp3:
    st.markdown("### ♻️ Reset")
    keep_cd = st.checkbox("Conservar Cantón→Distrito", value=True, key="keep_cd_reset")
    if st.button("🧹 Volver a defaults", use_container_width=True):
        reset_to_defaults(keep_canton_distrito=keep_cd)
        st.success("Proyecto reiniciado a defaults.")
        st.rerun()

st.info("""
**Qué se guarda en el proyecto JSON**
- Orden de páginas y preguntas  
- Todas las preguntas (type/name/label/required/relevant/constraint/choice_filter/etc.)  
- Todas las listas (choices) incluyendo columnas extra como `canton_key`  
- Glosario completo y qué términos aparecen por página  
""")

# ==========================================================================================
# FIN PARTE 10/10
# ==========================================================================================

