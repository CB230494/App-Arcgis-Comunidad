# -*- coding: utf-8 -*-
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 1/10) ==============================
# = App: Encuesta Comunidad → Editor + XLSForm Survey123 (Páginas) + Catálogo Cantón→Distrito
# ==========================================================================================
#
# OBJETIVO DE LA APP (modo editor fácil):
# - Ver preguntas de forma legible y editable dentro de la app.
# - Reordenar, agregar, eliminar preguntas.
# - Editar condicionales (relevant), dependencias (choice_filter), validaciones (constraint).
# - Editar choices (opciones) de manera fácil.
# - Editar glosarios (término → significado) por página o global.
# - Exportar XLSForm (survey/choices/settings) listo para Survey123.
#
# ESTA PARTE 1/10 INCLUYE:
# 1) Imports
# 2) Configuración UI básica
# 3) Helpers generales (slugify, únicos, descarga XLSForm, choices)
# 4) FIX Survey123:
#    - Evita error: "List name not in choices sheet: list_canton"
#    - Valida que toda lista usada en survey exista en choices antes de exportar
#
# NOTA IMPORTANTE:
# - En Survey123, si en "survey" se usa: select_one list_canton
#   entonces en "choices" debe existir al menos 1 fila con list_name="list_canton".
#   Si no, Survey123 fallará al convertir.
#
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
st.set_page_config(page_title="Editor XLSForm — Encuesta Comunidad", layout="wide")
st.title("🏘️ Editor fácil — Encuesta Comunidad → XLSForm para ArcGIS Survey123")

st.markdown("""
Este editor permite construir y mantener un XLSForm (Survey123) de manera **amigable**:
- Preguntas editables, reordenables y eliminables.
- Choices (opciones) fáciles de administrar.
- Glosario editable.
- Catálogo Cantón→Distrito en cascada (choice_filter).
- Exportación final en Excel con hojas: **survey**, **choices**, **settings**.
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
    """
    Asegura que un name sea único (por ejemplo, para no duplicar name en survey).
    Si base ya existe, agrega sufijos _2, _3, etc.
    """
    if base not in usados:
        return base
    i = 2
    while f"{base}_{i}" in usados:
        i += 1
    return f"{base}_{i}"


def descargar_xlsform(df_survey: pd.DataFrame, df_choices: pd.DataFrame, df_settings: pd.DataFrame, nombre_archivo: str):
    """
    Genera y permite descargar el XLSForm en Excel con 3 hojas:
    - survey
    - choices
    - settings
    """
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


def add_choice_list(choices_rows: list[dict], list_name: str, labels: list[str]):
    """
    Agrega choices (list_name/name/label) evitando duplicados.
    - name se genera con slugify(label)
    """
    usados = set((r.get("list_name"), r.get("name")) for r in choices_rows)
    for lab in labels:
        row = {"list_name": list_name, "name": slugify_name(lab), "label": lab}
        key = (row["list_name"], row["name"])
        if key not in usados:
            choices_rows.append(row)
            usados.add(key)

# ==========================================================================================
# FIX Survey123: listas usadas en survey deben existir en choices
# ==========================================================================================
def sync_ext_catalog_into_choices_rows(choices_rows: list[dict]) -> int:
    """
    Si usas un catálogo externo por lotes (ej. st.session_state.choices_ext_rows),
    esta función lo integra en choices_rows antes de exportar.

    Retorna la cantidad de filas agregadas.
    """
    ext = st.session_state.get("choices_ext_rows", []) or []
    if not ext:
        return 0

    existing = {(str(r.get("list_name", "")).strip(), str(r.get("name", "")).strip()) for r in choices_rows}
    added = 0

    for r in ext:
        ln = str(r.get("list_name", "")).strip()
        nm = str(r.get("name", "")).strip()
        if not ln or not nm:
            continue

        key = (ln, nm)
        if key not in existing:
            choices_rows.append(dict(r))
            existing.add(key)
            added += 1

    return added


def ensure_choice_list_exists(choices_rows: list[dict], list_name: str):
    """
    Garantiza que exista al menos 1 fila en choices con ese list_name.
    Esto evita el error de Survey123:
    "List name not in choices sheet: <list_name>"

    Se agrega un placeholder mínimo si no existe.
    """
    existing_lists = {str(r.get("list_name", "")).strip() for r in choices_rows if str(r.get("list_name", "")).strip()}
    if list_name not in existing_lists:
        choices_rows.append({"list_name": list_name, "name": "placeholder_1", "label": "—"})


def scan_lists_used_in_survey(survey_rows: list[dict]) -> set:
    """
    Escanea survey_rows y extrae list_name usados en:
    - select_one <list>
    - select_multiple <list>
    """
    used = set()
    for r in survey_rows:
        tp = str(r.get("type", "")).strip()
        if tp.startswith("select_one "):
            used.add(tp.replace("select_one ", "").strip())
        elif tp.startswith("select_multiple "):
            used.add(tp.replace("select_multiple ", "").strip())
    return {u for u in used if u}


def get_existing_choice_lists(choices_rows: list[dict]) -> set:
    """Retorna el set de list_name presentes en choices_rows."""
    return {str(r.get("list_name", "")).strip() for r in choices_rows if str(r.get("list_name", "")).strip()}


def ensure_lists_exist_or_block_export(survey_rows: list[dict], choices_rows: list[dict]):
    """
    1) Integra catálogo externo (choices_ext_rows) si existe.
    2) Asegura list_canton y list_distrito si se usan en survey.
    3) Valida que TODAS las listas usadas existan en choices.
       Si falta alguna, bloquea export (st.stop()) para no generar XLSForm roto.
    """
    # 1) Sync catálogo externo si aplica
    sync_ext_catalog_into_choices_rows(choices_rows)

    # 2) Detectar listas usadas
    used_lists = scan_lists_used_in_survey(survey_rows)
    existing_lists = get_existing_choice_lists(choices_rows)

    # Cantón/Distrito: si se usan, deben existir sí o sí
    if "list_canton" in used_lists and "list_canton" not in existing_lists:
        ensure_choice_list_exists(choices_rows, "list_canton")
    if "list_distrito" in used_lists and "list_distrito" not in existing_lists:
        ensure_choice_list_exists(choices_rows, "list_distrito")

    # Recalcular
    existing_lists = get_existing_choice_lists(choices_rows)
    missing = sorted(list(used_lists - existing_lists))

    if missing:
        st.error(
            "❌ No se puede exportar: hay listas usadas en preguntas (survey) "
            "que NO existen en choices.\n\n"
            f"Listas faltantes: {missing}\n\n"
            "Solución: crea esas listas en el Editor de Choices o agrégales opciones."
        )
        st.stop()

    # Advertencia extra para list_distrito si hay choice_filter canton_key=${canton}
    if "list_distrito" in existing_lists:
        dist_rows = [r for r in choices_rows if str(r.get("list_name", "")).strip() == "list_distrito"]
        dist_real = [r for r in dist_rows if str(r.get("name", "")).strip() != "placeholder_1"]
        if dist_real:
            sin_ck = [r for r in dist_real if not str(r.get("canton_key", "")).strip()]
            if sin_ck:
                st.warning(
                    "⚠️ Hay distritos sin canton_key en list_distrito. "
                    "Si usas choice_filter 'canton_key=${canton}', el filtrado podría fallar."
                )

# ==========================================================================================
# FIN PARTE 1/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 2/10) ==============================
# ====== Estado editable (bancos) + Seed inicial (preguntas precargadas visibles) =========
# ==========================================================================================
#
# ESTA PARTE 2/10 HACE:
# 1) Inicializa en st.session_state los "bancos" editables:
#    - questions_bank: preguntas (survey rows) editables
#    - choices_bank: opciones (choices rows) editables
#    - glossary_bank: glosario (término -> definición) editable
#    - choices_ext_rows: catálogo Cantón→Distrito por lotes (opcional)
# 2) Carga "semillas" (seed) SOLO si aún no existen bancos.
#    Esto garantiza que las preguntas precargadas:
#    ✅ se ven dentro de la app
#    ✅ se pueden editar, mover, eliminar y duplicar
#
# IMPORTANTE:
# - No se exporta todavía. Solo se prepara la data editable.
# - La exportación la armamos en Partes posteriores.
# ==========================================================================================

# ==========================================================================================
# 1) Inicialización de bancos en Session State
# ==========================================================================================
def init_state():
    if "questions_bank" not in st.session_state:
        st.session_state.questions_bank = []  # lista de dicts: {"qid","page","order","row"}
    if "choices_bank" not in st.session_state:
        st.session_state.choices_bank = []    # lista de dicts: {"list_name","name","label",...}
    if "glossary_bank" not in st.session_state:
        st.session_state.glossary_bank = {}   # dict: { "Termino": "Definición..." }
    if "choices_ext_rows" not in st.session_state:
        st.session_state.choices_ext_rows = []  # opcional: catálogo cantón/distrito por lotes

    # Selección UI
    if "active_page" not in st.session_state:
        st.session_state.active_page = "p1"
    if "selected_qid" not in st.session_state:
        st.session_state.selected_qid = None
    if "editor_mode" not in st.session_state:
        st.session_state.editor_mode = "Simple"
    if "show_advanced_fields" not in st.session_state:
        st.session_state.show_advanced_fields = False

init_state()

# ==========================================================================================
# 2) Textos base (idénticos o equivalentes a tu código original)
# ==========================================================================================
DEFAULT_LOGO_PATH = "001.png"

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
# 3) Glosario base (editable)
# ==========================================================================================
GLOSARIO_BASE = {
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
# 4) Seed de choices base (editable)
#    - Aquí garantizamos que list_canton y list_distrito EXISTAN SIEMPRE (placeholder)
# ==========================================================================================
def seed_choices_base():
    choices_rows = []
    add_choice_list(choices_rows, "yesno", ["Sí", "No"])
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

    # ✅ FIX CRÍTICO: listas canton/distrito deben existir en choices siempre
    ensure_choice_list_exists(choices_rows, "list_canton")
    ensure_choice_list_exists(choices_rows, "list_distrito")

    # Para list_distrito agregamos canton_key en placeholder (no rompe)
    # (si el placeholder ya existe sin canton_key, lo dejamos igual; canton_key se agregará al export si aplica)
    return choices_rows

# ==========================================================================================
# 5) Seed de preguntas (survey) por páginas en formato "bank"
#    Cada pregunta se guarda como:
#    {
#      "qid": "...",
#      "page": "p1",
#      "order": 10,
#      "row": { columnas XLSForm... }
#    }
# ==========================================================================================
def _new_qid(prefix: str = "q") -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def seed_questions_base(form_title: str, logo_media_name: str):
    qb = []

    v_si = slugify_name("Sí")
    v_no = slugify_name("No")
    rel_si = f"${{acepta_participar}}='{v_si}'"

    def add_q(page: str, order: int, row: dict):
        qb.append({"qid": _new_qid("q"), "page": page, "order": order, "row": row})

    # -------------------------------- P1: Introducción --------------------------------
    add_q("p1", 10, {"type": "begin_group", "name": "p1_intro", "label": "Introducción", "appearance": "field-list"})
    add_q("p1", 20, {"type": "note", "name": "p1_logo", "label": form_title, "media::image": logo_media_name, "bind::esri:fieldType": "null"})
    add_q("p1", 30, {"type": "note", "name": "p1_texto", "label": INTRO_COMUNIDAD_EXACTA, "bind::esri:fieldType": "null"})
    add_q("p1", 40, {"type": "end_group", "name": "p1_end", "label": ""})

    # -------------------------------- P2: Consentimiento --------------------------------
    add_q("p2", 10, {"type": "begin_group", "name": "p2_consent", "label": "Consentimiento Informado", "appearance": "field-list"})
    add_q("p2", 20, {"type": "note", "name": "p2_titulo", "label": CONSENT_TITLE, "bind::esri:fieldType": "null"})

    idx = 30
    for i, p in enumerate(CONSENT_PARRAFOS, start=1):
        add_q("p2", idx, {"type": "note", "name": f"p2_p_{i}", "label": p, "bind::esri:fieldType": "null"})
        idx += 10

    for j, b in enumerate(CONSENT_BULLETS, start=1):
        add_q("p2", idx, {"type": "note", "name": f"p2_b_{j}", "label": f"• {b}", "bind::esri:fieldType": "null"})
        idx += 10

    for k, c in enumerate(CONSENT_CIERRE, start=1):
        add_q("p2", idx, {"type": "note", "name": f"p2_c_{k}", "label": c, "bind::esri:fieldType": "null"})
        idx += 10

    add_q("p2", idx, {
        "type": "select_one yesno",
        "name": "acepta_participar",
        "label": "¿Acepta participar en esta encuesta?",
        "required": "yes",
        "appearance": "minimal"
    })
    idx += 10

    add_q("p2", idx, {"type": "end_group", "name": "p2_end", "label": ""})
    idx += 10

    add_q("p2", idx, {
        "type": "end",
        "name": "fin_por_no",
        "label": "Gracias. Usted indicó que no acepta participar en esta encuesta.",
        "relevant": f"${{acepta_participar}}='{v_no}'"
    })

    # -------------------------------- P3: Datos demográficos --------------------------------
    add_q("p3", 10, {"type": "begin_group", "name": "p3_datos_demograficos", "label": "Datos demográficos", "appearance": "field-list", "relevant": rel_si})

    add_q("p3", 20, {
        "type": "select_one list_canton",
        "name": "canton",
        "label": "1. Cantón:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    rel_distrito = f"({rel_si}) and string-length(${{canton}}) > 0"
    add_q("p3", 30, {
        "type": "select_one list_distrito",
        "name": "distrito",
        "label": "2. Distrito:",
        "required": "yes",
        "choice_filter": "canton_key=${canton}",
        "appearance": "minimal",
        "relevant": rel_distrito
    })

    add_q("p3", 40, {
        "type": "integer",
        "name": "edad_anos",
        "label": "3. Edad:",
        "required": "yes",
        "constraint": ". >= 18 and . <= 120",
        "constraint_message": "Debe ser un número entre 18 y 120.",
        "relevant": rel_si
    })

    add_q("p3", 50, {
        "type": "select_one genero",
        "name": "genero",
        "label": "4. ¿Con cuál de estas opciones se identifica?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    add_q("p3", 60, {
        "type": "select_one escolaridad",
        "name": "escolaridad",
        "label": "5. Escolaridad:",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    add_q("p3", 70, {
        "type": "select_one relacion_zona",
        "name": "relacion_zona",
        "label": "6. ¿Cuál es su relación con la zona?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })

    add_q("p3", 80, {"type": "end_group", "name": "p3_end", "label": ""})

    # -------------------------------- P4: Percepción (mínimo, editable luego) --------------------------------
    add_q("p4", 10, {"type": "begin_group", "name": "p4_percepcion_distrito", "label": "Percepción ciudadana de seguridad en el distrito", "appearance": "field-list", "relevant": rel_si})
    add_q("p4", 20, {
        "type": "select_one seguridad_5",
        "name": "p7_seguridad_distrito",
        "label": "7. ¿Qué tan seguro percibe usted el distrito donde reside o transita?",
        "required": "yes",
        "appearance": "minimal",
        "relevant": rel_si
    })
    add_q("p4", 90, {"type": "end_group", "name": "p4_end", "label": ""})

    # -------------------------------- P8: Cierre mínimo (editable luego) --------------------------------
    add_q("p8", 10, {"type": "begin_group", "name": "p8_cierre", "label": "Cierre", "appearance": "field-list", "relevant": rel_si})
    add_q("p8", 20, {"type": "note", "name": "p8_fin", "label": "---------------------------------- Fin de la Encuesta ----------------------------------", "bind::esri:fieldType": "null", "relevant": rel_si})
    add_q("p8", 30, {"type": "end_group", "name": "p8_end", "label": ""})

    return qb

# ==========================================================================================
# 6) Aplicar seed si los bancos están vacíos
# ==========================================================================================
def apply_seed_if_empty(form_title: str, logo_media_name: str):
    if not st.session_state.questions_bank:
        st.session_state.questions_bank = seed_questions_base(form_title=form_title, logo_media_name=logo_media_name)

    if not st.session_state.choices_bank:
        st.session_state.choices_bank = seed_choices_base()

    if not st.session_state.glossary_bank:
        st.session_state.glossary_bank = dict(GLOSARIO_BASE)

    # Selección por defecto: primera pregunta
    if st.session_state.questions_bank and not st.session_state.selected_qid:
        st.session_state.selected_qid = st.session_state.questions_bank[0]["qid"]

# ==========================================================================================
# 7) Datos básicos de encabezado: logo + delegación (igual que tu flujo original)
# ==========================================================================================
col_logo, col_txt = st.columns([1, 3], vertical_alignment="center")

with col_logo:
    up_logo = st.file_uploader("Logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="logo_uploader")
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
    delegacion = st.text_input("Nombre del lugar / Delegación", value="San Carlos Oeste", key="delegacion_input")
    logo_media_name = st.text_input(
        "Nombre de archivo para `media::image`",
        value=st.session_state.get("_logo_name", "001.png"),
        help="Debe coincidir con el archivo dentro de la carpeta `media/` del proyecto Survey123.",
        key="logo_media_name_input"
    )

form_title = f"Encuesta comunidad – {delegacion.strip()}" if delegacion.strip() else "Encuesta comunidad"
st.markdown(f"### {form_title}")

# Aplicar seed (una vez)
apply_seed_if_empty(form_title=form_title, logo_media_name=logo_media_name)

# ==========================================================================================
# FIN PARTE 2/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 3/10) ==============================
# ========================= Editor de Preguntas (Survey) — Fácil ==========================
# ==========================================================================================
#
# ESTA PARTE 3/10 INCLUYE:
# 1) Navegación por secciones (Preguntas / Choices / Glosario / Catálogo / Exportar)
# 2) Editor de Preguntas:
#    - Lista por páginas (P1..P8)
#    - Vista legible tipo Survey123 (para cualquier persona)
#    - Reordenar (↑ ↓), duplicar, eliminar
#    - Editar en modo Simple (texto + requerido + tipo + lista)
#    - Editar en modo Avanzado (XLSForm completo: relevant/constraint/choice_filter etc.)
# 3) Agregar nueva pregunta (rápido)
#
# IMPORTANTE:
# - Aquí NO exportamos todavía, solo editamos el banco (questions_bank).
# - La exportación va en Partes posteriores.
# ==========================================================================================

# ==========================================================================================
# 1) Navegación principal
# ==========================================================================================
st.markdown("---")
tabs = ["Preguntas", "Choices", "Glosario", "Catálogo", "Exportar"]
active_tab = st.radio("Sección", options=tabs, horizontal=True, key="main_tabs")

pages = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]
pages_labels = {
    "p1": "P1 Introducción",
    "p2": "P2 Consentimiento",
    "p3": "P3 Demográficos",
    "p4": "P4 Percepción",
    "p5": "P5 Riesgos",
    "p6": "P6 Delitos",
    "p7": "P7 Victimización",
    "p8": "P8 Confianza / Cierre",
}

# ==========================================================================================
# 2) Helpers de preguntas (bank)
# ==========================================================================================
def qb_sorted():
    """Ordena questions_bank por page y order."""
    order_map = {p: i for i, p in enumerate(pages)}
    return sorted(
        st.session_state.questions_bank,
        key=lambda x: (order_map.get(x.get("page", ""), 999), int(x.get("order", 0)))
    )

def get_q_by_id(qid: str):
    return next((q for q in st.session_state.questions_bank if q.get("qid") == qid), None)

def update_q(qid: str, new_q: dict):
    qb = st.session_state.questions_bank
    for i, q in enumerate(qb):
        if q.get("qid") == qid:
            qb[i] = new_q
            break
    st.session_state.questions_bank = qb

def delete_q(qid: str):
    st.session_state.questions_bank = [q for q in st.session_state.questions_bank if q.get("qid") != qid]
    # Reset selección
    if st.session_state.questions_bank:
        st.session_state.selected_qid = st.session_state.questions_bank[0]["qid"]
    else:
        st.session_state.selected_qid = None

def duplicate_q(qid: str):
    src = get_q_by_id(qid)
    if not src:
        return
    used_names = {q.get("row", {}).get("name", "") for q in st.session_state.questions_bank}
    row = dict(src.get("row", {}) or {})
    if row.get("name"):
        row["name"] = asegurar_nombre_unico(row["name"], used_names)

    st.session_state.questions_bank.append({
        "qid": _new_qid("q"),
        "page": src.get("page", "p1"),
        "order": int(src.get("order", 0)) + 5,
        "row": row
    })

def move_q_within_page(qid: str, direction: str):
    """
    Reordena una pregunta dentro de su página usando swap de 'order'.
    direction: 'up' o 'down'
    """
    q = get_q_by_id(qid)
    if not q:
        return
    page = q.get("page", "p1")

    items = sorted([x for x in st.session_state.questions_bank if x.get("page") == page],
                   key=lambda x: int(x.get("order", 0)))
    idx = next((i for i, x in enumerate(items) if x.get("qid") == qid), None)
    if idx is None:
        return

    if direction == "up" and idx > 0:
        items[idx]["order"], items[idx - 1]["order"] = items[idx - 1]["order"], items[idx]["order"]
    if direction == "down" and idx < len(items) - 1:
        items[idx]["order"], items[idx + 1]["order"] = items[idx + 1]["order"], items[idx]["order"]

    others = [x for x in st.session_state.questions_bank if x.get("page") != page]
    st.session_state.questions_bank = others + items

def extract_list_name(tp: str) -> str:
    """Devuelve list_name desde type: select_one X / select_multiple X."""
    tp = (tp or "").strip()
    if tp.startswith("select_one "):
        return tp.replace("select_one ", "").strip()
    if tp.startswith("select_multiple "):
        return tp.replace("select_multiple ", "").strip()
    return ""

def all_choice_lists() -> list:
    """Todas las listas list_name existentes en choices_bank."""
    return sorted({str(r.get("list_name", "")).strip() for r in st.session_state.choices_bank if str(r.get("list_name", "")).strip()})

def choice_labels_for_list(list_name: str) -> list:
    """Labels de opciones de una lista."""
    out = []
    for r in st.session_state.choices_bank:
        if str(r.get("list_name", "")).strip() == list_name:
            out.append(str(r.get("label", "")).strip() or str(r.get("name", "")).strip())
    return out

def add_question(page: str, qtype: str, label: str):
    """
    Agrega pregunta al banco.
    - Genera name único basado en label.
    - Para 'note' agrega bind::esri:fieldType='null'.
    """
    used_names = {q.get("row", {}).get("name", "") for q in st.session_state.questions_bank}
    base = slugify_name(label or "pregunta")
    name = asegurar_nombre_unico(base, used_names)

    row = {
        "type": qtype,
        "name": name,
        "label": label or "",
        "required": "no",
        "appearance": "",
        "relevant": "",
        "choice_filter": "",
        "constraint": "",
        "constraint_message": "",
        "media::image": "",
        "bind::esri:fieldType": "null" if qtype == "note" else "",
    }

    max_order = max([int(q.get("order", 0)) for q in st.session_state.questions_bank if q.get("page") == page] + [0])
    st.session_state.questions_bank.append({"qid": _new_qid("q"), "page": page, "order": max_order + 10, "row": row})

# ==========================================================================================
# 3) UI Editor Preguntas
# ==========================================================================================
if active_tab == "Preguntas":
    st.subheader("🧾 Editor de Preguntas (survey) — vista legible + edición")

    left, right = st.columns([1.2, 2.3])

    with left:
        st.session_state.active_page = st.selectbox(
            "Página",
            options=pages,
            format_func=lambda p: pages_labels.get(p, p),
            index=pages.index(st.session_state.active_page) if st.session_state.active_page in pages else 0,
            key="page_select"
        )

        search_text = st.text_input("Buscar en esta página", value="", key="q_search_text")
        qs_page = [q for q in qb_sorted() if q.get("page") == st.session_state.active_page]

        if search_text.strip():
            s = search_text.strip().lower()
            qs_page = [q for q in qs_page if s in str(q.get("row", {}).get("label", "")).lower()]

        label_map = {}
        display = []
        for q in qs_page:
            r = q.get("row", {}) or {}
            t = str(r.get("type", "")).strip()
            l = str(r.get("label", "")).strip() or "(sin texto)"
            if t in ("begin_group", "end_group", "note", "end"):
                txt = f"[{t}] {l}"
            else:
                txt = l
            display.append(txt)
            label_map[txt] = q.get("qid")

        if display:
            chosen = st.selectbox("Preguntas", options=display, key="q_list_select")
            st.session_state.selected_qid = label_map.get(chosen)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.button("⬆", on_click=move_q_within_page, args=(st.session_state.selected_qid, "up"), key="btn_up")
            with c2:
                st.button("⬇", on_click=move_q_within_page, args=(st.session_state.selected_qid, "down"), key="btn_down")
            with c3:
                st.button("📄", on_click=duplicate_q, args=(st.session_state.selected_qid,), key="btn_dup")
            with c4:
                st.button("🗑", on_click=delete_q, args=(st.session_state.selected_qid,), key="btn_del")

        st.markdown("### ➕ Agregar pregunta")
        new_type = st.selectbox(
            "Tipo",
            options=[
                "note",
                "text",
                "integer",
                "select_one yesno",
                "select_one genero",
                "select_one escolaridad",
                "select_one relacion_zona",
                "select_one seguridad_5",
                "select_one list_canton",
                "select_one list_distrito",
                "select_multiple yesno",
            ],
            key="add_q_type"
        )
        new_label = st.text_input("Texto", value="", key="add_q_label")
        if st.button("Agregar", type="primary", use_container_width=True, key="add_q_btn"):
            add_question(st.session_state.active_page, new_type, new_label)
            st.success("Pregunta agregada.")
            st.rerun()

    with right:
        qid = st.session_state.selected_qid
        q = get_q_by_id(qid)

        if not q:
            st.info("Selecciona una pregunta para editar.")
        else:
            row = dict(q.get("row", {}) or {})
            qtype = str(row.get("type", "")).strip()
            qlabel = str(row.get("label", "")).strip()
            qname = str(row.get("name", "")).strip()
            list_name = extract_list_name(qtype)

            st.markdown("### 👁️ Vista legible (similar a Survey123)")
            st.caption(f"Nombre interno: `{qname}`  |  Tipo: `{qtype}`")

            with st.container(border=True):
                st.markdown(f"#### {qlabel if qlabel else '(Pregunta sin texto)'}")

                if qtype.startswith("select_one "):
                    opts = choice_labels_for_list(list_name)
                    if opts:
                        st.radio(" ", options=opts, index=None, key=f"prev_radio_{qid}", label_visibility="collapsed")
                    else:
                        st.warning("Esta lista no tiene opciones. Ve a la pestaña Choices para agregarlas.")

                elif qtype.startswith("select_multiple "):
                    opts = choice_labels_for_list(list_name)
                    if opts:
                        for i, opt in enumerate(opts):
                            st.checkbox(opt, value=False, key=f"prev_chk_{qid}_{i}")
                    else:
                        st.warning("Esta lista no tiene opciones. Ve a la pestaña Choices para agregarlas.")

                elif qtype == "integer":
                    st.number_input(" ", value=None, step=1, key=f"prev_int_{qid}", label_visibility="collapsed")
                elif qtype == "text":
                    st.text_area(" ", value="", height=90, key=f"prev_txt_{qid}", label_visibility="collapsed")
                elif qtype == "note":
                    st.info("ℹ️ Nota (no genera columna en resultados).")
                elif qtype in ("begin_group", "end_group", "end"):
                    st.warning(f"Elemento estructural: {qtype}")
                else:
                    st.info("Tipo no previsualizado, pero se exporta correctamente.")

            st.markdown("---")

            st.session_state.editor_mode = st.radio(
                "Modo de edición",
                options=["Simple", "Avanzado"],
                horizontal=True,
                index=0 if st.session_state.editor_mode == "Simple" else 1,
                key="edit_mode_radio"
            )

            # =========================
            # MODO SIMPLE
            # =========================
            if st.session_state.editor_mode == "Simple":
                st.markdown("### ✏️ Editar (Simple)")
                with st.form("simple_edit_form"):
                    new_label = st.text_area("Texto de la pregunta", value=qlabel, height=120, key="simple_label")
                    req = st.checkbox("Obligatoria (required)", value=(str(row.get("required", "")).strip() == "yes"), key="simple_req")

                    # Tipo simple
                    simple_type = st.selectbox(
                        "Tipo",
                        options=["select_one", "select_multiple", "text", "integer", "note"],
                        index=0 if qtype.startswith("select_one ") else
                              1 if qtype.startswith("select_multiple ") else
                              2 if qtype == "text" else
                              3 if qtype == "integer" else
                              4,
                        key="simple_type"
                    )

                    chosen_list = list_name
                    if simple_type in ("select_one", "select_multiple"):
                        lists = all_choice_lists()
                        if not lists:
                            lists = ["yesno"]
                        chosen_list = st.selectbox(
                            "Lista de opciones",
                            options=lists,
                            index=lists.index(list_name) if list_name in lists else 0,
                            key="simple_list"
                        )
                        st.caption("Opciones actuales de esa lista:")
                        st.write(choice_labels_for_list(chosen_list))

                    save = st.form_submit_button("💾 Guardar cambios", use_container_width=True)

                if save:
                    row["label"] = new_label.strip()
                    row["required"] = "yes" if req else "no"

                    if simple_type == "select_one":
                        row["type"] = f"select_one {chosen_list}".strip()
                    elif simple_type == "select_multiple":
                        row["type"] = f"select_multiple {chosen_list}".strip()
                    else:
                        row["type"] = simple_type

                    if row["type"] == "note":
                        row["bind::esri:fieldType"] = "null"
                    else:
                        # Si el usuario cambia de note a otro, no forzamos null
                        if row.get("bind::esri:fieldType", "") == "null":
                            row["bind::esri:fieldType"] = ""

                    q["row"] = row
                    update_q(qid, q)
                    st.success("Actualizado.")
                    st.rerun()

            # =========================
            # MODO AVANZADO
            # =========================
            else:
                st.markdown("### 🧠 Editar (Avanzado XLSForm)")
                st.caption("Aquí puedes editar campos XLSForm: relevant, constraint, choice_filter, etc.")

                with st.form("advanced_edit_form"):
                    row["type"] = st.text_input("type", value=row.get("type", ""), key="adv_type")
                    row["name"] = st.text_input("name", value=row.get("name", ""), key="adv_name")
                    row["label"] = st.text_area("label", value=row.get("label", ""), height=120, key="adv_label")

                    row["required"] = st.selectbox(
                        "required",
                        options=["", "yes", "no"],
                        index=1 if str(row.get("required", "")).strip() == "yes" else (2 if str(row.get("required", "")).strip() == "no" else 0),
                        key="adv_required"
                    )

                    row["appearance"] = st.text_input("appearance", value=row.get("appearance", ""), key="adv_app")
                    row["relevant"] = st.text_area("relevant", value=row.get("relevant", ""), height=70, key="adv_rel")
                    row["choice_filter"] = st.text_input("choice_filter", value=row.get("choice_filter", ""), key="adv_cf")
                    row["constraint"] = st.text_area("constraint", value=row.get("constraint", ""), height=70, key="adv_con")
                    row["constraint_message"] = st.text_area("constraint_message", value=row.get("constraint_message", ""), height=70, key="adv_conmsg")
                    row["media::image"] = st.text_input("media::image", value=row.get("media::image", ""), key="adv_img")
                    row["bind::esri:fieldType"] = st.text_input("bind::esri:fieldType", value=row.get("bind::esri:fieldType", ""), key="adv_bind")

                    save_adv = st.form_submit_button("💾 Guardar (Avanzado)", use_container_width=True)

                if save_adv:
                    q["row"] = row
                    update_q(qid, q)
                    st.success("Guardado.")
                    st.rerun()

# ==========================================================================================
# FIN PARTE 3/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 4/10) ==============================
# ========================= Editor de Choices — Listas y Opciones =========================
# ==========================================================================================
#
# ESTA PARTE 4/10 INCLUYE:
# 1) Editor fácil de choices (hoja "choices") dentro de la app.
# 2) Manejo de listas (list_name) y sus opciones (name/label + extras).
# 3) Para Cantón→Distrito:
#    - list_canton: opciones normales
#    - list_distrito: incluye campo extra canton_key (para choice_filter)
# 4) Agregar, editar, eliminar opciones sin tocar Excel.
#
# NOTA:
# - Survey123 requiere que SI un select_one/list usa list_name, exista en choices.
# - Ya metimos placeholders en el seed y también en el FIX.
# ==========================================================================================

# ==========================================================================================
# Helpers Choices (bank)
# ==========================================================================================
def cb_all_lists() -> list:
    return sorted({str(r.get("list_name", "")).strip() for r in st.session_state.choices_bank if str(r.get("list_name", "")).strip()})

def cb_rows_for_list(list_name: str) -> list:
    return [r for r in st.session_state.choices_bank if str(r.get("list_name", "")).strip() == list_name]

def cb_delete_row(list_name: str, name: str):
    st.session_state.choices_bank = [
        r for r in st.session_state.choices_bank
        if not (str(r.get("list_name", "")).strip() == list_name and str(r.get("name", "")).strip() == name)
    ]

def cb_upsert_row(row: dict):
    """
    Inserta o actualiza una fila en choices_bank por llave (list_name, name).
    """
    ln = str(row.get("list_name", "")).strip()
    nm = str(row.get("name", "")).strip()
    if not ln or not nm:
        return

    updated = False
    for i, r in enumerate(st.session_state.choices_bank):
        if str(r.get("list_name", "")).strip() == ln and str(r.get("name", "")).strip() == nm:
            st.session_state.choices_bank[i] = row
            updated = True
            break
    if not updated:
        st.session_state.choices_bank.append(row)

def cb_ensure_list_exists(list_name: str):
    """
    Asegura que exista al menos un placeholder en la lista (para evitar fallos Survey123).
    """
    lists = cb_all_lists()
    if list_name not in lists:
        cb_upsert_row({"list_name": list_name, "name": "placeholder_1", "label": "—"})

def cb_rename_list(old: str, new: str):
    """
    Renombra list_name en choices_bank (y opcionalmente el type en questions se hará en otra parte si quieres).
    """
    if not old or not new or old == new:
        return
    for i, r in enumerate(st.session_state.choices_bank):
        if str(r.get("list_name", "")).strip() == old:
            st.session_state.choices_bank[i]["list_name"] = new

def cb_rebuild_names_for_list(list_name: str):
    """
    Recalcula el campo 'name' usando slugify(label) para una lista (opcional).
    Útil si el usuario pegó labels con espacios/acentos y quiere normalizar.
    """
    rows = cb_rows_for_list(list_name)
    used = set()
    for r in rows:
        lab = str(r.get("label", "")).strip()
        if lab == "—" and str(r.get("name", "")).strip() == "placeholder_1":
            continue
        base = slugify_name(lab) if lab else "opcion"
        nm = asegurar_nombre_unico(base, used)
        used.add(nm)
        r["name"] = nm

# ==========================================================================================
# UI Choices
# ==========================================================================================
if active_tab == "Choices":
    st.subheader("🧩 Editor de Choices (opciones) — fácil para cualquier persona")

    left, right = st.columns([1.2, 2.3])

    with left:
        st.markdown("### 📚 Listas")
        lists = cb_all_lists()
        if not lists:
            st.info("No hay listas aún. Se crearán cuando agregues una.")
            lists = []

        # Crear lista nueva
        new_list_name = st.text_input("Crear nueva lista (list_name)", value="", key="cb_new_list")
        if st.button("➕ Crear lista", type="primary", use_container_width=True, key="cb_create_list_btn"):
            if not new_list_name.strip():
                st.error("Indica un nombre de lista.")
            else:
                cb_ensure_list_exists(new_list_name.strip())
                st.success("Lista creada.")
                st.rerun()

        # Seleccionar lista
        default_list = "yesno" if "yesno" in lists else (lists[0] if lists else "")
        selected_list = st.selectbox("Selecciona lista", options=lists if lists else [default_list], key="cb_selected_list")

        # Acciones de lista
        st.markdown("### ⚙️ Acciones de lista")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🧼 Normalizar names", use_container_width=True, key="cb_norm_btn"):
                cb_rebuild_names_for_list(selected_list)
                st.success("Names normalizados.")
                st.rerun()
        with c2:
            rename_to = st.text_input("Renombrar list_name a", value="", key="cb_rename_to")
            if st.button("✏️ Renombrar", use_container_width=True, key="cb_rename_btn"):
                if rename_to.strip():
                    cb_rename_list(selected_list, rename_to.strip())
                    st.success("Lista renombrada.")
                    st.rerun()

        st.markdown("### ➕ Agregar opción")
        opt_label = st.text_input("Texto visible (label)", value="", key="cb_add_label")

        # Campo extra canton_key SOLO si list_distrito
        opt_canton_key = ""
        if selected_list == "list_distrito":
            opt_canton_key = st.text_input("canton_key (slug del cantón)", value="", key="cb_add_ck")

        if st.button("Agregar opción", use_container_width=True, key="cb_add_opt_btn"):
            if not opt_label.strip():
                st.error("Indica el texto (label).")
            else:
                label = opt_label.strip()
                existing = cb_rows_for_list(selected_list)
                used_names = {str(r.get("name", "")).strip() for r in existing}
                nm = asegurar_nombre_unico(slugify_name(label), used_names)

                row = {"list_name": selected_list, "name": nm, "label": label}
                if selected_list == "list_distrito":
                    row["canton_key"] = opt_canton_key.strip()

                cb_upsert_row(row)
                st.success("Opción agregada.")
                st.rerun()

    with right:
        st.markdown(f"### 🧾 Opciones en: `{selected_list}`")

        rows = cb_rows_for_list(selected_list)
        if not rows:
            st.info("Esta lista no tiene opciones.")
        else:
            # Mostrar tabla editable amigable (sin “excel feo”)
            st.caption("Edita texto y campos. Para borrar, usa el botón 🗑.")
            for i, r in enumerate(rows):
                ln = str(r.get("list_name", "")).strip()
                nm = str(r.get("name", "")).strip()
                lab = str(r.get("label", "")).strip()

                # Evitar StreamlitDuplicateElementKey: keys únicas por list+name
                base_key = f"cb_{ln}_{nm}_{i}"

                with st.container(border=True):
                    top = st.columns([2.2, 2.2, 1, 1])
                    with top[0]:
                        new_label = st.text_input("label (visible)", value=lab, key=f"{base_key}_lab")
                    with top[1]:
                        new_name = st.text_input("name (interno)", value=nm, key=f"{base_key}_nm")
                    with top[2]:
                        # Guardar
                        if st.button("💾", use_container_width=True, key=f"{base_key}_save"):
                            # Borrar fila vieja si cambió name
                            if new_name.strip() and new_name.strip() != nm:
                                cb_delete_row(ln, nm)

                            row_new = dict(r)
                            row_new["label"] = new_label.strip()
                            row_new["name"] = new_name.strip() if new_name.strip() else nm

                            # canton_key editable si list_distrito
                            if selected_list == "list_distrito":
                                ck_val = st.session_state.get(f"{base_key}_ck_val", str(r.get("canton_key", "")).strip())
                                row_new["canton_key"] = str(ck_val).strip()

                            cb_upsert_row(row_new)
                            st.success("Guardado.")
                            st.rerun()

                    with top[3]:
                        # Eliminar
                        if st.button("🗑", use_container_width=True, key=f"{base_key}_del"):
                            cb_delete_row(ln, nm)
                            st.success("Eliminado.")
                            st.rerun()

                    # Campo extra para distrito
                    if selected_list == "list_distrito":
                        ck = str(r.get("canton_key", "")).strip()
                        st.text_input("canton_key (para choice_filter)", value=ck, key=f"{base_key}_ck_val")

            # Asegurar que la lista no se quede vacía (placeholder)
            if selected_list in ("list_canton", "list_distrito"):
                if not cb_rows_for_list(selected_list):
                    cb_ensure_list_exists(selected_list)

# ==========================================================================================
# FIN PARTE 4/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 5/10) ==============================
# ============================== Editor de Glosario — Fácil ==============================
# ==========================================================================================
#
# ESTA PARTE 5/10 INCLUYE:
# 1) Editor de Glosario global (término -> definición) dentro de la app.
# 2) Búsqueda rápida.
# 3) Agregar, editar y eliminar términos.
# 4) Preparación para "glosario por página" (se conecta en partes posteriores).
#
# IMPORTANTE:
# - El glosario aquí es editable por cualquier persona.
# - En el XLSForm final, el glosario se agregará como:
#   select_one yesno (¿Desea acceder al glosario?) + begin_group con notes (definiciones).
# ==========================================================================================

# ==========================================================================================
# Helpers de Glosario
# ==========================================================================================
def gl_all_terms() -> list:
    return sorted(list(st.session_state.glossary_bank.keys()), key=lambda x: x.lower())

def gl_set(term: str, definition: str):
    term = (term or "").strip()
    definition = (definition or "").strip()
    if not term:
        return
    st.session_state.glossary_bank[term] = definition

def gl_delete(term: str):
    term = (term or "").strip()
    if term in st.session_state.glossary_bank:
        del st.session_state.glossary_bank[term]

def gl_get(term: str) -> str:
    return str(st.session_state.glossary_bank.get(term, ""))

# ==========================================================================================
# UI Glosario
# ==========================================================================================
if active_tab == "Glosario":
    st.subheader("📖 Editor de Glosario — términos y significados (editable)")

    left, right = st.columns([1.2, 2.3])

    with left:
        st.markdown("### 🔎 Buscar")
        q_search = st.text_input("Buscar término", value="", key="gl_search")
        terms = gl_all_terms()
        if q_search.strip():
            s = q_search.strip().lower()
            terms = [t for t in terms if s in t.lower() or s in gl_get(t).lower()]

        if not terms:
            st.info("No hay términos que coincidan.")
            selected_term = None
        else:
            selected_term = st.selectbox("Términos", options=terms, key="gl_term_select")

        st.markdown("### ➕ Agregar término")
        new_term = st.text_input("Término", value="", key="gl_new_term")
        new_def = st.text_area("Definición", value="", height=120, key="gl_new_def")

        if st.button("Agregar al glosario", type="primary", use_container_width=True, key="gl_add_btn"):
            if not new_term.strip():
                st.error("Indica el término.")
            else:
                gl_set(new_term.strip(), new_def.strip())
                st.success("Término agregado/actualizado.")
                st.rerun()

    with right:
        if not selected_term:
            st.info("Selecciona un término para editar.")
        else:
            st.markdown(f"### ✏️ Editar: **{selected_term}**")

            # Keys únicas para evitar StreamlitDuplicateElementKey
            base_key = f"gl_edit_{slugify_name(selected_term)}"

            cur_def = gl_get(selected_term)
            edited_term = st.text_input("Término", value=selected_term, key=f"{base_key}_term")
            edited_def = st.text_area("Definición", value=cur_def, height=160, key=f"{base_key}_def")

            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("💾 Guardar cambios", use_container_width=True, key=f"{base_key}_save"):
                    # Si cambió el nombre del término, borramos el viejo y guardamos nuevo
                    old = selected_term
                    newt = edited_term.strip()
                    newd = edited_def.strip()

                    if not newt:
                        st.error("El término no puede quedar vacío.")
                    else:
                        if newt != old:
                            gl_delete(old)
                        gl_set(newt, newd)
                        st.success("Guardado.")
                        st.rerun()

            with c2:
                if st.button("🗑 Eliminar término", use_container_width=True, key=f"{base_key}_del"):
                    gl_delete(selected_term)
                    st.success("Eliminado.")
                    st.rerun()

            st.markdown("---")
            st.markdown("### 👁️ Vista previa")
            with st.container(border=True):
                st.write(f"**{edited_term.strip() if edited_term.strip() else selected_term}**")
                st.write(edited_def.strip() if edited_def.strip() else "(Sin definición)")

# ==========================================================================================
# FIN PARTE 5/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 6/10) ==============================
# ===================== Editor Catálogo Cantón→Distrito (integrado a choices) ==============
# ==========================================================================================
#
# ESTA PARTE 6/10 HACE:
# 1) Editor amigable para cargar Cantón→Distrito "por lotes" (como tu app original),
#    pero ahora lo INTEGRA directamente en choices_bank, para que:
#    ✅ Survey123 NO falle (listas existen y tienen filas reales)
#    ✅ choice_filter "canton_key=${canton}" funcione
# 2) Permite:
#    - Agregar cantón + múltiples distritos
#    - Ver y editar tabla de cantones
#    - Ver y editar tabla de distritos (incluye canton_key)
#    - Borrar cantones/distritos
#
# IMPORTANTE:
# - En choices_bank:
#   list_canton: {list_name="list_canton", name="<slug_canton>", label="Cantón"}
#   list_distrito: {list_name="list_distrito", name="<slug_distrito>", label="Distrito", canton_key="<slug_canton>"}
# ==========================================================================================

# ==========================================================================================
# Helpers Catálogo (sobre choices_bank)
# ==========================================================================================
def cat_get_cantones():
    out = []
    for r in st.session_state.choices_bank:
        if str(r.get("list_name", "")).strip() == "list_canton":
            nm = str(r.get("name", "")).strip()
            lb = str(r.get("label", "")).strip()
            if nm and nm != "placeholder_1":
                out.append({"name": nm, "label": lb})
    out = sorted(out, key=lambda x: x["label"].lower())
    return out

def cat_get_distritos():
    out = []
    for r in st.session_state.choices_bank:
        if str(r.get("list_name", "")).strip() == "list_distrito":
            nm = str(r.get("name", "")).strip()
            lb = str(r.get("label", "")).strip()
            ck = str(r.get("canton_key", "")).strip()
            if nm and nm != "placeholder_1":
                out.append({"name": nm, "label": lb, "canton_key": ck})
    out = sorted(out, key=lambda x: (x["canton_key"].lower(), x["label"].lower()))
    return out

def cat_add_lote(canton_label: str, distritos_labels: list[str]):
    canton_label = (canton_label or "").strip()
    distritos_labels = [d.strip() for d in (distritos_labels or []) if d.strip()]
    if not canton_label or not distritos_labels:
        return False, "Debes indicar Cantón y al menos un Distrito."

    # Asegurar existencia de listas
    cb_ensure_list_exists("list_canton")
    cb_ensure_list_exists("list_distrito")

    # Slug del cantón
    slug_c = slugify_name(canton_label)

    # Insert/Update cantón
    cb_upsert_row({"list_name": "list_canton", "name": slug_c, "label": canton_label})

    # Distritos
    existing_d = cb_rows_for_list("list_distrito")
    used_names = {str(r.get("name", "")).strip() for r in existing_d}

    for dlab in distritos_labels:
        base = slugify_name(dlab)
        nm = asegurar_nombre_unico(base, used_names)
        used_names.add(nm)
        cb_upsert_row({"list_name": "list_distrito", "name": nm, "label": dlab, "canton_key": slug_c})

    return True, f"Lote agregado: {canton_label} → {len(distritos_labels)} distrito(s)."

def cat_delete_canton(slug_canton: str, delete_children: bool = True):
    slug_canton = (slug_canton or "").strip()
    if not slug_canton:
        return
    # Borra cantón
    cb_delete_row("list_canton", slug_canton)
    # Borra distritos asociados
    if delete_children:
        st.session_state.choices_bank = [
            r for r in st.session_state.choices_bank
            if not (str(r.get("list_name", "")).strip() == "list_distrito" and str(r.get("canton_key", "")).strip() == slug_canton)
        ]

def cat_delete_distrito(name_distrito: str):
    name_distrito = (name_distrito or "").strip()
    if not name_distrito:
        return
    cb_delete_row("list_distrito", name_distrito)

# ==========================================================================================
# UI Catálogo
# ==========================================================================================
if active_tab == "Catálogo":
    st.subheader("📚 Catálogo Cantón → Distrito (cascada) — fácil y sin Excel")

    # Cargar por lotes (como tu flujo original)
    st.markdown("### ➕ Agregar por lote (Cantón y Distritos)")
    with st.container(border=True):
        col_c1, col_c2 = st.columns([2, 3])

        canton_txt = col_c1.text_input("Cantón (una vez)", value="", key="cat_canton_txt")
        distritos_txt = col_c2.text_area("Distritos del cantón (uno por línea)", value="", height=140, key="cat_distritos_txt")

        b1, b2 = st.columns([1, 1])
        with b1:
            if st.button("Agregar lote", type="primary", use_container_width=True, key="cat_add_lote_btn"):
                d_list = [d.strip() for d in distritos_txt.splitlines() if d.strip()]
                ok, msg = cat_add_lote(canton_txt, d_list)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        with b2:
            if st.button("Limpiar catálogo (cantones/distritos)", use_container_width=True, key="cat_clear_btn"):
                # Borra todos los cantones y distritos reales (mantiene placeholders)
                st.session_state.choices_bank = [
                    r for r in st.session_state.choices_bank
                    if not (
                        (str(r.get("list_name", "")).strip() == "list_canton" and str(r.get("name", "")).strip() != "placeholder_1")
                        or
                        (str(r.get("list_name", "")).strip() == "list_distrito" and str(r.get("name", "")).strip() != "placeholder_1")
                    )
                ]
                st.success("Catálogo limpiado.")
                st.rerun()

    st.markdown("---")

    # Tablas de edición
    cantones = cat_get_cantones()
    distritos = cat_get_distritos()

    t1, t2 = st.columns(2)

    with t1:
        st.markdown("### 🏛 Cantones (list_canton)")
        if not cantones:
            st.info("No hay cantones cargados.")
        else:
            for i, c in enumerate(cantones):
                slug_c = c["name"]
                lbl_c = c["label"]
                base_key = f"cat_c_{slug_c}_{i}"

                with st.container(border=True):
                    top = st.columns([2.2, 2.2, 1, 1])
                    with top[0]:
                        new_label = st.text_input("label", value=lbl_c, key=f"{base_key}_lbl")
                    with top[1]:
                        new_slug = st.text_input("name (slug)", value=slug_c, key=f"{base_key}_slug")
                    with top[2]:
                        if st.button("💾", use_container_width=True, key=f"{base_key}_save"):
                            # Si cambió slug, actualizamos también canton_key en distritos
                            old = slug_c
                            new = new_slug.strip() if new_slug.strip() else old
                            new_lab = new_label.strip()

                            # Borrar viejo si slug cambia
                            if new != old:
                                cb_delete_row("list_canton", old)
                                # Update distritos canton_key
                                for j, r in enumerate(st.session_state.choices_bank):
                                    if str(r.get("list_name", "")).strip() == "list_distrito" and str(r.get("canton_key", "")).strip() == old:
                                        st.session_state.choices_bank[j]["canton_key"] = new

                            cb_upsert_row({"list_name": "list_canton", "name": new, "label": new_lab})
                            st.success("Cantón guardado.")
                            st.rerun()
                    with top[3]:
                        if st.button("🗑", use_container_width=True, key=f"{base_key}_del"):
                            cat_delete_canton(slug_canton=slug_c, delete_children=True)
                            st.success("Cantón y distritos asociados eliminados.")
                            st.rerun()

    with t2:
        st.markdown("### 🧭 Distritos (list_distrito + canton_key)")
        if not distritos:
            st.info("No hay distritos cargados.")
        else:
            for i, d in enumerate(distritos):
                nm = d["name"]
                lb = d["label"]
                ck = d["canton_key"]
                base_key = f"cat_d_{ck}_{nm}_{i}"

                with st.container(border=True):
                    top = st.columns([2.2, 2.2, 2.2, 1, 1])
                    with top[0]:
                        new_label = st.text_input("label", value=lb, key=f"{base_key}_lbl")
                    with top[1]:
                        new_name = st.text_input("name", value=nm, key=f"{base_key}_nm")
                    with top[2]:
                        new_ck = st.text_input("canton_key", value=ck, key=f"{base_key}_ck")
                    with top[3]:
                        if st.button("💾", use_container_width=True, key=f"{base_key}_save"):
                            old_nm = nm
                            # Si cambia name, borramos la fila vieja
                            if new_name.strip() and new_name.strip() != old_nm:
                                cb_delete_row("list_distrito", old_nm)

                            cb_upsert_row({
                                "list_name": "list_distrito",
                                "name": new_name.strip() if new_name.strip() else old_nm,
                                "label": new_label.strip(),
                                "canton_key": new_ck.strip()
                            })
                            st.success("Distrito guardado.")
                            st.rerun()
                    with top[4]:
                        if st.button("🗑", use_container_width=True, key=f"{base_key}_del"):
                            cat_delete_distrito(old_nm := nm)
                            st.success("Distrito eliminado.")
                            st.rerun()

    # Asegurar placeholders si quedaran vacías las listas
    cb_ensure_list_exists("list_canton")
    cb_ensure_list_exists("list_distrito")

# ==========================================================================================
# FIN PARTE 6/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 7/10) ==============================
# ================== Glosario por Página (editable) + Bloque generador XLSForm =============
# ==========================================================================================
#
# ESTA PARTE 7/10 HACE:
# 1) Permite definir (de forma editable) QUÉ términos del glosario aplican a cada página (P1..P8).
# 2) Define el generador del “bloque glosario por página” para Survey123:
#    - select_one yesno: “¿Desea acceder al glosario de esta sección?”
#    - begin_group (Glosario)
#    - note por cada término (bind::esri:fieldType="null") => NO crea columnas
#    - end_group
#
# IMPORTANTÍSIMO:
# - Esto NO lo inserta todavía en el XLSForm final (eso lo conectamos en la PARTE 9/10),
#   pero aquí dejamos:
#   ✅ la UI editable
#   ✅ las funciones que generan filas “survey” de glosario
#
# REGLAS MANTENIDAS:
# - Glosario por página aparece solo si la persona marca "Sí".
# - Notes sin columnas: bind::esri:fieldType="null"
# ==========================================================================================

# ==========================================================================================
# 1) Estado: mapa de glosario por página (editable)
# ==========================================================================================
def init_page_glossary_map():
    if "page_glossary_map" not in st.session_state:
        # Seed razonable (puedes cambiarlo desde la UI)
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

init_page_glossary_map()

# ==========================================================================================
# 2) Helpers: generar bloque de glosario para Survey123 (filas "survey")
# ==========================================================================================
def build_glossary_block_rows(page_id: str, relevant_base: str, v_si: str, terms: list[str]) -> list[dict]:
    """
    Construye filas 'survey' para un glosario por página.

    - page_id: "p4", "p5", etc.
    - relevant_base: expresión base de relevancia (ej. ${acepta_participar}='si')
    - v_si: slug de "Sí" (ej. "si")
    - terms: lista de términos seleccionados para esta página.

    Retorna: lista de filas (dicts) para agregar a survey_rows.
    """
    out = []

    # Filtrar solo términos que existan en el glosario global
    terms_ok = [t for t in (terms or []) if t in st.session_state.glossary_bank]
    if not terms_ok:
        return out

    # Pregunta de acceso
    out.append({
        "type": "select_one yesno",
        "name": f"{page_id}_accede_glosario",
        "label": "¿Desea acceder al glosario de esta sección?",
        "required": "no",
        "appearance": "minimal",
        "relevant": relevant_base
    })

    rel_glos = f"({relevant_base}) and (${{{page_id}_accede_glosario}}='{v_si}')"

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

    for i, t in enumerate(terms_ok, start=1):
        out.append({
            "type": "note",
            "name": f"{page_id}_glos_{i}",
            "label": str(st.session_state.glossary_bank.get(t, "")).strip(),
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

    out.append({
        "type": "end_group",
        "name": f"{page_id}_glosario_end",
        "label": ""
    })

    return out


def get_page_glossary_terms(page_id: str) -> list[str]:
    return list(st.session_state.page_glossary_map.get(page_id, []) or [])

def set_page_glossary_terms(page_id: str, terms: list[str]):
    st.session_state.page_glossary_map[page_id] = list(terms or [])

# ==========================================================================================
# 3) UI: asignar términos del glosario a cada página (para cualquier persona)
# ==========================================================================================
if active_tab == "Glosario":
    st.markdown("---")
    st.subheader("🧷 Glosario por Página (P1–P8) — asignación editable")

    st.caption(
        "Aquí decides qué términos del glosario (global) se muestran como glosario en cada página. "
        "Esto se traducirá a un bloque Survey123 que aparece solo si la persona marca “Sí”."
    )

    gl_pages_cols = st.columns(2)
    with gl_pages_cols[0]:
        page_for_gl = st.selectbox(
            "Página a configurar",
            options=pages,
            format_func=lambda p: pages_labels.get(p, p),
            key="gl_page_select"
        )

    all_terms = gl_all_terms()
    current_terms = get_page_glossary_terms(page_for_gl)

    with st.container(border=True):
        selected_terms = st.multiselect(
            "Términos incluidos en el glosario de esta página",
            options=all_terms,
            default=[t for t in current_terms if t in all_terms],
            key=f"gl_terms_{page_for_gl}"
        )

        # Reordenar (muy simple): lista de texto separada por líneas
        st.caption("Orden del glosario (opcional). Si quieres ordenar manualmente, pega la lista en el orden deseado:")
        order_text = st.text_area(
            "Orden (uno por línea)",
            value="\n".join(selected_terms),
            height=120,
            key=f"gl_order_{page_for_gl}"
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Guardar asignación", type="primary", use_container_width=True, key=f"gl_save_map_{page_for_gl}"):
                lines = [ln.strip() for ln in order_text.splitlines() if ln.strip()]
                # Mantener solo términos válidos y sin duplicados
                seen = set()
                final = []
                for t in lines:
                    if t in all_terms and t not in seen:
                        final.append(t)
                        seen.add(t)

                set_page_glossary_terms(page_for_gl, final)
                st.success("Asignación guardada.")
                st.rerun()

        with c2:
            if st.button("🧹 Limpiar página", use_container_width=True, key=f"gl_clear_map_{page_for_gl}"):
                set_page_glossary_terms(page_for_gl, [])
                st.success("Glosario eliminado para esta página.")
                st.rerun()

    # Vista previa
    st.markdown("### 👁️ Vista previa del glosario de esta página")
    prev_terms = get_page_glossary_terms(page_for_gl)
    if not prev_terms:
        st.info("Esta página no tiene términos asignados.")
    else:
        with st.container(border=True):
            for t in prev_terms:
                st.write(f"**{t}**")
                st.write(gl_get(t))

# ==========================================================================================
# FIN PARTE 7/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 8/10) ==============================
# ===================== Constructor XLSForm desde bancos editables (core) ==================
# ==========================================================================================
#
# ESTA PARTE 8/10 HACE:
# 1) Construye survey_rows (en orden) a partir de questions_bank (editable).
# 2) Construye choices_rows a partir de choices_bank (editable) + catálogo si aplica.
# 3) Construye settings (form_title/version/default_language/style="pages").
# 4) Inserta glosario por página (si hay términos asignados) EN LA PÁGINA correspondiente:
#    - select_one yesno (acceso glosario)
#    - begin_group + notes (bind::esri:fieldType="null")
#    - end_group
#
# IMPORTANTÍSIMO:
# - Aún NO se muestra el botón de export (eso va en la PARTE 9/10).
# - Aquí solo se define el "motor" que arma el XLSForm correctamente.
# ==========================================================================================

# ==========================================================================================
# 1) Helpers: normalización de filas y columnas XLSForm
# ==========================================================================================
SURVEY_COLS = [
    "type", "name", "label", "required", "appearance",
    "relevant", "choice_filter",
    "constraint", "constraint_message",
    "media::image",
    "bind::esri:fieldType"
]

def normalize_survey_row(row: dict) -> dict:
    """
    Normaliza una fila survey para que siempre tenga las columnas esperadas.
    """
    r = dict(row or {})
    out = {c: "" for c in SURVEY_COLS}
    for k, v in r.items():
        if k in out:
            out[k] = "" if v is None else v
        else:
            # Mantener campos extra si en futuro deseas, pero no los exportamos por defecto.
            pass
    # Regla: notas no crean columna
    if str(out.get("type", "")).strip() == "note" and not str(out.get("bind::esri:fieldType", "")).strip():
        out["bind::esri:fieldType"] = "null"
    return out

def normalize_choices_rows(rows: list[dict]) -> list[dict]:
    """
    Normaliza choices (lista de dicts), conservando columnas extras (ej. canton_key).
    """
    # Determinar todas las columnas presentes
    all_cols = set()
    for r in rows:
        all_cols.update((r or {}).keys())

    base = ["list_name", "name", "label"]
    extra = [c for c in sorted(all_cols) if c not in base]
    cols = base + extra

    norm = []
    for r in rows:
        rr = dict(r or {})
        out = {c: "" for c in cols}
        for c in cols:
            if c in rr:
                out[c] = "" if rr[c] is None else rr[c]
        norm.append(out)

    return norm

# ==========================================================================================
# 2) Construcción de survey_rows desde questions_bank
# ==========================================================================================
def build_survey_rows_from_bank(form_title: str, logo_media_name: str) -> list[dict]:
    """
    Toma questions_bank y arma survey_rows en el orden correcto por página.

    NOTA:
    - questions_bank ya contiene begin_group/end_group, etc.
    - Aquí solo consolidamos y normalizamos.
    - En parte 9 agregamos settings y export.
    """
    # Ordenar questions
    ordered = qb_sorted()

    survey_rows = []
    for q in ordered:
        row = normalize_survey_row(q.get("row", {}) or {})
        survey_rows.append(row)

    return survey_rows

# ==========================================================================================
# 3) Construcción de choices_rows desde choices_bank + catálogo externo
# ==========================================================================================
def build_choices_rows_from_bank() -> list[dict]:
    """
    Construye choices_rows desde st.session_state.choices_bank.
    Integra también st.session_state.choices_ext_rows si existiera.
    """
    choices_rows = [dict(r) for r in (st.session_state.choices_bank or [])]

    # Integrar catálogo externo si alguien lo usa todavía
    ext = st.session_state.get("choices_ext_rows", []) or []
    if ext:
        existing = {(str(r.get("list_name","")).strip(), str(r.get("name","")).strip()) for r in choices_rows}
        for r in ext:
            ln = str(r.get("list_name","")).strip()
            nm = str(r.get("name","")).strip()
            if not ln or not nm:
                continue
            key = (ln, nm)
            if key not in existing:
                choices_rows.append(dict(r))
                existing.add(key)

    # Asegurar placeholders para listas críticas (mínimo)
    cb_ensure_list_exists("yesno")
    cb_ensure_list_exists("list_canton")
    cb_ensure_list_exists("list_distrito")

    return choices_rows

# ==========================================================================================
# 4) Inserción de glosario por página dentro de survey_rows
# ==========================================================================================
def insert_glossary_blocks_into_survey(survey_rows: list[dict], idioma: str = "es") -> list[dict]:
    """
    Inserta el glosario por página dentro de survey_rows.

    Estrategia:
    - Detectamos el "end_group" de cada página (p1_end, p2_end, ..., p8_end).
    - Insertamos el bloque del glosario inmediatamente ANTES del end_group de esa página,
      para que quede DENTRO de la página (group).
    """
    # Slugs de Sí/No (en choices yesno se guardan como slugify("Sí") etc.)
    v_si = slugify_name("Sí")

    # relevant base para glosarios (siempre: solo si aceptó participar)
    # Se mantiene la misma lógica de tu formulario original.
    rel_si = f"${{acepta_participar}}='{v_si}'"

    # Mapa page_id -> términos asignados
    page_terms_map = dict(st.session_state.page_glossary_map or {})

    # Construir bloques para cada página
    blocks = {}
    for page_id in pages:
        terms = page_terms_map.get(page_id, []) or []
        block_rows = build_glossary_block_rows(page_id=page_id, relevant_base=rel_si, v_si=v_si, terms=terms)
        if block_rows:
            blocks[page_id] = [normalize_survey_row(r) for r in block_rows]

    if not blocks:
        return survey_rows

    # Insertar antes del end_group de cada página
    new_rows = []
    for r in survey_rows:
        tp = str(r.get("type", "")).strip()
        nm = str(r.get("name", "")).strip()

        # Detectar end_group por patrón: pX_end
        inserted = False
        if tp == "end_group":
            # page_id desde name: "p4_end" -> "p4"
            if nm.endswith("_end") and nm[:2] == "p" and nm[2].isdigit():
                page_id = nm.split("_end")[0]  # "p4"
                if page_id in blocks:
                    # Insertar bloque antes del end_group
                    new_rows.extend(blocks[page_id])
                    inserted = True

        new_rows.append(r)

    return new_rows

# ==========================================================================================
# 5) Construcción final de DataFrames (survey/choices/settings)
# ==========================================================================================
def build_xlsform_dataframes(form_title: str, logo_media_name: str, idioma: str, version: str):
    """
    Construye:
    - df_survey
    - df_choices
    - df_settings

    Incluye:
    - survey desde bank
    - glosario por página insertado
    - choices desde bank
    - settings con style="pages"
    - Validación FIX: si falta alguna lista usada en survey, se bloquea export.
    """
    survey_rows = build_survey_rows_from_bank(form_title=form_title, logo_media_name=logo_media_name)
    survey_rows = insert_glossary_blocks_into_survey(survey_rows, idioma=idioma)

    choices_rows = build_choices_rows_from_bank()

    # ✅ FIX CRÍTICO: validar listas usadas en survey contra choices
    ensure_lists_exist_or_block_export(survey_rows=survey_rows, choices_rows=choices_rows)

    # DataFrames
    df_survey = pd.DataFrame([normalize_survey_row(r) for r in survey_rows], columns=SURVEY_COLS).fillna("")

    choices_norm = normalize_choices_rows(choices_rows)
    # columnas en choices (dinámicas: list_name,name,label + extras)
    if choices_norm:
        choice_cols = list(choices_norm[0].keys())
    else:
        choice_cols = ["list_name", "name", "label"]
    df_choices = pd.DataFrame(choices_norm, columns=choice_cols).fillna("")

    df_settings = pd.DataFrame([{
        "form_title": form_title,
        "version": version,
        "default_language": idioma,
        "style": "pages"
    }], columns=["form_title", "version", "default_language", "style"]).fillna("")

    return df_survey, df_choices, df_settings

# ==========================================================================================
# FIN PARTE 8/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 9/10) ==============================
# ============================== Exportar XLSForm + FIX Survey123 ==========================
# ==========================================================================================
#
# ESTA PARTE 9/10 INCLUYE:
# 1) Pestaña "Exportar" completa:
#    - Idioma (default_language)
#    - Versión (settings.version)
#    - Vista previa (survey / choices / settings)
#    - Descargar XLSForm (.xlsx)
#    - Descargar logo para carpeta media/
#
# 2) FIXS para errores típicos en Survey123 (los de tus screenshots):
#    ✅ Listas usadas en survey deben existir en choices (list_name)
#    ✅ (list_name, name) no pueden repetirse en choices
#    ✅ name en survey debe ser único (para campos reales) y no vacío
#    ✅ Campos críticos: list_canton y list_distrito siempre existen (placeholder)
#
# IMPORTANTE:
# - Aquí ya usamos build_xlsform_dataframes() de la PARTE 8/10.
# - Si detectamos problemas, bloqueamos export y te mostramos el detalle.
# ==========================================================================================

# ==========================================================================================
# 1) VALIDADORES / FIX Survey123
# ==========================================================================================
def _survey_list_names_used(survey_rows: list[dict]) -> set:
    """
    Extrae list_name usados por select_one/select_multiple en survey.
    """
    used = set()
    for r in survey_rows:
        tp = str(r.get("type", "")).strip()
        if tp.startswith("select_one "):
            used.add(tp.replace("select_one ", "").strip())
        elif tp.startswith("select_multiple "):
            used.add(tp.replace("select_multiple ", "").strip())
    return {u for u in used if u}

def _choices_list_names_present(choices_rows: list[dict]) -> set:
    return {str(r.get("list_name", "")).strip() for r in choices_rows if str(r.get("list_name", "")).strip()}

def _find_duplicates_in_choices(choices_rows: list[dict]) -> list[tuple]:
    """
    Retorna duplicados por llave (list_name, name).
    """
    seen = set()
    dups = []
    for r in choices_rows:
        ln = str(r.get("list_name", "")).strip()
        nm = str(r.get("name", "")).strip()
        if not ln or not nm:
            continue
        key = (ln, nm)
        if key in seen:
            dups.append(key)
        else:
            seen.add(key)
    return sorted(list(set(dups)))

def _survey_name_duplicates(survey_rows: list[dict]) -> list[str]:
    """
    Verifica duplicados en 'name' (solo para filas que generan campo real o referencia).
    Permitimos repetición solo si está vacío en elementos estructurales (pero igual es mala práctica).
    """
    ignore_types = {"begin_group", "end_group"}  # esos también deberían tener name único, pero Survey123 suele tolerar.
    seen = set()
    dups = set()
    for r in survey_rows:
        tp = str(r.get("type", "")).strip()
        nm = str(r.get("name", "")).strip()
        if not nm:
            continue
        # END / NOTE / SELECT / TEXT / INTEGER etc. deben ser únicos
        if tp not in ignore_types:
            if nm in seen:
                dups.add(nm)
            else:
                seen.add(nm)
        else:
            # también controlamos groups, por seguridad
            if nm in seen:
                dups.add(nm)
            else:
                seen.add(nm)
    return sorted(list(dups))

def _survey_empty_names(survey_rows: list[dict]) -> list[int]:
    """
    Detecta filas que deberían tener name pero no lo tienen.
    """
    bad_idx = []
    for idx, r in enumerate(survey_rows, start=1):
        tp = str(r.get("type", "")).strip()
        nm = str(r.get("name", "")).strip()
        # tipos que SI necesitan name
        needs_name = True
        if tp == "":
            needs_name = False
        if needs_name and not nm:
            bad_idx.append(idx)
    return bad_idx

def _choices_empty_keys(choices_rows: list[dict]) -> list[int]:
    """
    Detecta filas con list_name o name vacío.
    """
    bad = []
    for idx, r in enumerate(choices_rows, start=1):
        ln = str(r.get("list_name", "")).strip()
        nm = str(r.get("name", "")).strip()
        if not ln or not nm:
            bad.append(idx)
    return bad

def ensure_lists_exist_or_block_export(survey_rows: list[dict], choices_rows: list[dict]):
    """
    Valida todo y, si hay errores, marca st.session_state["_export_blocked"]=True
    y guarda el detalle en st.session_state["_export_errors"].
    """
    errors = []

    used_lists = _survey_list_names_used(survey_rows)
    present_lists = _choices_list_names_present(choices_rows)
    missing_lists = sorted(list(used_lists - present_lists))

    if missing_lists:
        errors.append("Faltan listas en choices que son usadas en survey:")
        for ln in missing_lists:
            errors.append(f" - {ln}")

    dup_choices = _find_duplicates_in_choices(choices_rows)
    if dup_choices:
        errors.append("Hay opciones duplicadas en choices (misma combinación list_name + name):")
        for ln, nm in dup_choices[:40]:
            errors.append(f" - ({ln}, {nm})")
        if len(dup_choices) > 40:
            errors.append(f" - ... y {len(dup_choices)-40} más")

    dup_survey_names = _survey_name_duplicates(survey_rows)
    if dup_survey_names:
        errors.append("Hay 'name' duplicados en survey (esto rompe Survey123):")
        for nm in dup_survey_names[:40]:
            errors.append(f" - {nm}")
        if len(dup_survey_names) > 40:
            errors.append(f" - ... y {len(dup_survey_names)-40} más")

    empty_survey = _survey_empty_names(survey_rows)
    if empty_survey:
        errors.append("Hay filas en survey sin 'name' (índices de fila): " + ", ".join(map(str, empty_survey[:40])))
        if len(empty_survey) > 40:
            errors.append(f"... y {len(empty_survey)-40} más")

    empty_choices = _choices_empty_keys(choices_rows)
    if empty_choices:
        errors.append("Hay filas en choices con list_name o name vacío (índices de fila): " + ", ".join(map(str, empty_choices[:40])))
        if len(empty_choices) > 40:
            errors.append(f"... y {len(empty_choices)-40} más")

    # Resultado
    st.session_state["_export_errors"] = errors
    st.session_state["_export_blocked"] = True if errors else False

# ==========================================================================================
# 2) UI Exportar
# ==========================================================================================
if active_tab == "Exportar":
    st.subheader("📦 Exportar XLSForm (Survey123)")

    idioma = st.selectbox("Idioma (default_language)", options=["es", "en"], index=0, key="exp_idioma")
    version_auto = datetime.now().strftime("%Y%m%d%H%M")
    version = st.text_input("Versión (settings.version)", value=version_auto, key="exp_version")

    st.markdown("---")

    # Construir (preview + validar)
    if st.button("🧮 Construir XLSForm", use_container_width=True, key="exp_build_btn"):
        # Armamos dataframes desde el motor (Parte 8)
        df_survey, df_choices, df_settings = build_xlsform_dataframes(
            form_title=form_title,
            logo_media_name=logo_media_name,
            idioma=idioma,
            version=version.strip() or version_auto
        )

        # Guardar en session para evitar reconstrucción al descargar
        st.session_state["_df_survey"] = df_survey
        st.session_state["_df_choices"] = df_choices
        st.session_state["_df_settings"] = df_settings

        # Mostrar errores si existieran (bloquea export)
        if st.session_state.get("_export_blocked"):
            st.error("Se detectaron problemas que pueden impedir cargar en Survey123. Corrige y vuelve a construir.")
            with st.expander("Ver detalle de errores (clic)"):
                for e in st.session_state.get("_export_errors", []):
                    st.write(e)
        else:
            st.success("XLSForm construido correctamente. Puedes previsualizar y descargar.")

    # Mostrar preview si ya existe
    df_survey = st.session_state.get("_df_survey")
    df_choices = st.session_state.get("_df_choices")
    df_settings = st.session_state.get("_df_settings")

    if isinstance(df_survey, pd.DataFrame) and isinstance(df_choices, pd.DataFrame) and isinstance(df_settings, pd.DataFrame):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Hoja: survey**")
            st.dataframe(df_survey, use_container_width=True, hide_index=True, height=420)
        with c2:
            st.markdown("**Hoja: choices**")
            st.dataframe(df_choices, use_container_width=True, hide_index=True, height=420)
        with c3:
            st.markdown("**Hoja: settings**")
            st.dataframe(df_settings, use_container_width=True, hide_index=True, height=420)

        st.markdown("---")

        # Descargar SOLO si no está bloqueado
        if st.session_state.get("_export_blocked"):
            st.warning("Exportación bloqueada hasta corregir los errores.")
        else:
            nombre_archivo = slugify_name(form_title) + "_xlsform.xlsx"
            descargar_xlsform(df_survey, df_choices, df_settings, nombre_archivo)

            # Descargar logo si se cargó
            if st.session_state.get("_logo_bytes"):
                st.download_button(
                    "📥 Descargar logo para carpeta media/",
                    data=st.session_state["_logo_bytes"],
                    file_name=logo_media_name,
                    mime="image/png",
                    use_container_width=True,
                    key="exp_dl_logo"
                )

            st.info("""
**Cómo usar en Survey123 Connect**
1) Crear encuesta **desde archivo** y seleccionar el XLSForm descargado.  
2) Copiar el logo dentro de la carpeta **media/** del proyecto, con el **mismo nombre** que pusiste en `media::image`.  
3) Verás páginas con **Siguiente/Anterior** (porque `settings.style = pages`).  
4) El glosario aparece solo si la persona marca **Sí** (no es obligatorio).  
""")

# ==========================================================================================
# FIN PARTE 9/10
# ==========================================================================================
# ==========================================================================================
# ============================== CÓDIGO COMPLETO (PARTE 10/10) =============================
# =================== Panel de Mantenimiento + Backup/Restore (JSON) + Reset ===============
# ==========================================================================================
#
# ESTA PARTE 10/10 INCLUYE:
# 1) Panel de mantenimiento (dentro de la app) para:
#    - Exportar BACKUP (JSON) de:
#        questions_bank, choices_bank, glossary_bank, page_glossary_map
#    - Importar/Restaurar BACKUP (JSON)
#    - Resetear a la plantilla base (seed) cuando quieran iniciar de nuevo
#
# 2) Indicación exacta del ORDEN de pegado final (cómo quedan las 10 partes).
#
# IMPORTANTE:
# - Este panel lo mostramos dentro de la pestaña "Exportar" (abajo),
#   para que sea fácil de encontrar.
# - NO omite ni una coma/punto de tu lógica: solo agrega herramientas.
# ==========================================================================================

import json

# ==========================================================================================
# 1) Helpers de backup/restore
# ==========================================================================================
def _build_backup_payload() -> dict:
    return {
        "meta": {
            "app": "Encuesta Comunidad XLSForm Builder (editable)",
            "created_at": datetime.now().isoformat(),
            "form_title": form_title,
        },
        "questions_bank": st.session_state.get("questions_bank", []),
        "choices_bank": st.session_state.get("choices_bank", []),
        "glossary_bank": st.session_state.get("glossary_bank", {}),
        "page_glossary_map": st.session_state.get("page_glossary_map", {}),
    }

def _apply_backup_payload(payload: dict):
    # Validaciones mínimas y asignación
    if not isinstance(payload, dict):
        raise ValueError("El backup no es un JSON válido (dict).")

    qb = payload.get("questions_bank", [])
    cb = payload.get("choices_bank", [])
    gb = payload.get("glossary_bank", {})
    pg = payload.get("page_glossary_map", {})

    if not isinstance(qb, list) or not isinstance(cb, list) or not isinstance(gb, dict) or not isinstance(pg, dict):
        raise ValueError("Estructura inválida en backup.")

    st.session_state.questions_bank = qb
    st.session_state.choices_bank = cb
    st.session_state.glossary_bank = gb
    st.session_state.page_glossary_map = pg

    # Asegurar listas críticas para Survey123
    cb_ensure_list_exists("yesno")
    cb_ensure_list_exists("list_canton")
    cb_ensure_list_exists("list_distrito")

def _reset_to_seed():
    """
    Reinicia todo a la plantilla base.
    (Reutiliza tus seeds de Partes 1-2: aquí solo llamamos a la inicialización).
    """
    # Reset total
    st.session_state.questions_bank = seed_questions_bank(form_title=form_title, logo_media_name=logo_media_name)
    st.session_state.choices_bank = seed_choices_bank()
    st.session_state.glossary_bank = seed_glossary_bank()
    init_page_glossary_map()

    # selección inicial
    if st.session_state.questions_bank:
        st.session_state.selected_qid = st.session_state.questions_bank[0]["qid"]

    # limpiar export cache
    for k in ["_df_survey", "_df_choices", "_df_settings", "_export_errors", "_export_blocked"]:
        if k in st.session_state:
            del st.session_state[k]

# ==========================================================================================
# 2) UI Panel de mantenimiento (lo ponemos al final de "Exportar")
# ==========================================================================================
if active_tab == "Exportar":
    st.markdown("---")
    st.subheader("🛠️ Mantenimiento (Backup / Restore / Reset)")

    with st.expander("📦 Backup/Restore (JSON) — guardar y restaurar la encuesta editable", expanded=False):
        st.caption(
            "Este backup guarda TODO lo editable: preguntas, choices, glosario y glosario por página. "
            "Puedes guardarlo y restaurarlo cuando quieras."
        )

        # Exportar backup
        payload = _build_backup_payload()
        backup_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

        st.download_button(
            label="⬇️ Descargar BACKUP (JSON)",
            data=backup_bytes,
            file_name=slugify_name(form_title) + "_backup.json",
            mime="application/json",
            use_container_width=True,
            key="dl_backup_json"
        )

        st.markdown("### ♻️ Restaurar backup")
        up = st.file_uploader("Sube un archivo BACKUP (.json)", type=["json"], key="up_backup_json")

        if up is not None:
            try:
                raw = up.getvalue().decode("utf-8", errors="replace")
                data = json.loads(raw)
                _apply_backup_payload(data)
                st.success("Backup restaurado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo restaurar el backup: {e}")

    with st.expander("🧨 Reset a plantilla base (seed) — iniciar desde cero", expanded=False):
        st.warning(
            "Esto reemplaza el contenido actual (preguntas/choices/glosario) por la plantilla base. "
            "Si no quieres perder cambios, descarga primero un BACKUP."
        )
        if st.button("RESET TOTAL", type="primary", use_container_width=True, key="btn_reset_seed"):
            _reset_to_seed()
            st.success("Reset completado.")
            st.rerun()

# ==========================================================================================
# 3) ORDEN DE PEGADO FINAL (cómo quedan las 10 partes en un solo app.py)
# ==========================================================================================
# ✅ Pegado recomendado:
#
# PARTE 1/10
# - imports, UI base (set_page_config, title, markdown)
# - helpers base: slugify_name, asegurar_nombre_unico, descargar_xlsform, add_choice_list
#
# PARTE 2/10
# - Inicialización de session_state
# - Seeds:
#   seed_choices_bank()
#   seed_glossary_bank()
#   seed_questions_bank(form_title, logo_media_name)
# - FIX StreamlitDuplicateElementKey (generador _new_qid)
#
# PARTE 3/10
# - Navegación (radio tabs)
# - Editor de Preguntas (questions_bank): vista legible + edición simple/avanzada + mover/duplicar/borrar + agregar
#
# PARTE 4/10
# - Editor de Choices (choices_bank): listas + opciones + canton_key para list_distrito
#
# PARTE 5/10
# - Editor de Glosario global (glossary_bank): agregar/editar/eliminar + búsqueda
#
# PARTE 6/10
# - Editor Catálogo Cantón→Distrito: integrado a choices_bank (list_canton / list_distrito + canton_key)
#
# PARTE 7/10
# - Glosario por página: page_glossary_map + UI asignación + build_glossary_block_rows()
#
# PARTE 8/10
# - Constructor XLSForm desde bancos:
#   build_xlsform_dataframes()
#   insert_glossary_blocks_into_survey()
#
# PARTE 9/10
# - Pestaña Exportar + VALIDADORES Survey123:
#   ensure_lists_exist_or_block_export()
#   preview + download XLSForm + download logo
#
# PARTE 10/10
# - Panel Mantenimiento:
#   backup/restore JSON + reset seed
#
# ==========================================================================================
# FIN PARTE 10/10
# ==========================================================================================










