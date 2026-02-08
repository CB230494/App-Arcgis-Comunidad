# -*- coding: utf-8 -*-
import io
import zipfile
import streamlit as st
import pandas as pd

st.set_page_config(page_title="P1 + P2 XLSForm (Comunidad)", layout="wide")
st.title("Generador XLSForm — Encuesta Comunidad (Solo Página 1 y 2)")

st.caption("Esta versión SOLO construye Página 1 (logo + intro) y Página 2 (consentimiento Sí/No) correctamente para Survey123.")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    form_title = st.text_input("form_title", "Encuesta Comunidad 2026")
    form_id = st.text_input("form_id", "encuesta_comunidad_2026")
    version = st.text_input("version", "1")

    lugar = st.text_input("Nombre del lugar / Delegación", "San Carlos Oeste")
    logo_file = st.file_uploader("Logo (PNG/JPG) — se exporta como archivo de media", type=["png", "jpg", "jpeg"])

with col2:
    st.markdown("### Texto Página 1 (Introducción)")
    intro_text = st.text_area(
        "Intro (editable)",
        value=(
            "El presente formato corresponde a la Encuesta de Percepción de Comunidad 2026, diseñada para recopilar información clave "
            "sobre seguridad ciudadana, convivencia y factores de riesgo en el territorio nacional. Este documento se remite para su revisión "
            "y validación por parte de las direcciones, departamentos u oficinas con competencia técnica, con el fin de asegurar su coherencia "
            "metodológica, normativa y operativa con los lineamientos institucionales vigentes. Las observaciones recibidas permitirán fortalecer "
            "el instrumento antes de su aplicación en territorio."
        ),
        height=160
    )

    st.markdown("### Texto Página 2 (Consentimiento informado)")
    consent_text = st.text_area(
        "Consentimiento (editable)",
        value=(
            "Usted está siendo invitado(a) a participar de forma libre y voluntaria en una encuesta sobre seguridad, convivencia y percepción ciudadana, "
            "dirigida a personas mayores de 18 años.\n\n"
            "El objetivo de esta encuesta es recopilar información de carácter preventivo y estadístico, con el fin de apoyar la planificación de acciones "
            "de prevención, mejora de la convivencia y fortalecimiento de la seguridad en comunidades.\n\n"
            "La participación es totalmente voluntaria. Puede negarse a responder cualquier pregunta, así como retirarse de la encuesta en cualquier momento, "
            "sin que ello genere consecuencia alguna.\n\n"
            "De conformidad con lo dispuesto en el artículo 5 de la Ley N.° 8968, Ley de Protección de la Persona frente al Tratamiento de sus Datos Personales, "
            "se le informa que los datos serán utilizados exclusivamente para fines estadísticos, analíticos y preventivos."
        ),
        height=240
    )

def build_xlsform(form_title: str, form_id: str, version: str, lugar: str, intro_text: str, consent_text: str, logo_filename: str | None):
    # ============ SETTINGS ============
    settings_df = pd.DataFrame([{
        "form_title": form_title.strip(),
        "form_id": form_id.strip(),
        "version": version.strip(),
    }])

    # ============ CHOICES ============
    choices_df = pd.DataFrame([
        {"list_name": "yesno", "name": "si", "label": "Sí"},
        {"list_name": "yesno", "name": "no", "label": "No"},
    ])

    # ============ SURVEY ============
    # Usamos columnas de media para mostrar imagen estática en una NOTE.
    survey_cols = [
        "type", "name", "label", "hint", "required", "relevant",
        "calculation", "constraint", "constraint_message",
        "label::media::image"
    ]

    rows = []

    # ---- PÁGINA 1 ----
    rows.append({"type": "begin_group", "name": "p1_intro", "label": f"Página 1 — Introducción ({lugar})"})
    rows.append({"type": "note", "name": "p1_titulo", "label": f"ENCUESTA COMUNIDAD — {lugar}"})
    rows.append({"type": "note", "name": "p1_intro_texto", "label": intro_text})

    if logo_filename:
        # NOTE con imagen estática (lo correcto en Survey123 es label::media::image)
        rows.append({
            "type": "note",
            "name": "p1_logo",
            "label": " ",
            "label::media::image": logo_filename
        })

    rows.append({"type": "end_group", "name": "", "label": ""})

    # ---- PÁGINA 2 ----
    rows.append({"type": "begin_group", "name": "p2_consentimiento_grp", "label": "Página 2 — Consentimiento informado"})
    rows.append({"type": "note", "name": "p2_texto", "label": consent_text})

    # Pregunta REAL (marcar Sí/No) — name único y válido
    rows.append({
        "type": "select_one yesno",
        "name": "p2_acepta_participar",
        "label": "¿Acepta participar en esta encuesta?",
        "required": "yes"
    })

    # Nota final si NO acepta
    rows.append({
        "type": "note",
        "name": "p2_no_fin",
        "label": "Gracias. Al no aceptar participar, la encuesta finaliza aquí.",
        "relevant": "${p2_acepta_participar} = 'no'"
    })

    rows.append({"type": "end_group", "name": "", "label": ""})

    survey_df = pd.DataFrame(rows)
    for c in survey_cols:
        if c not in survey_df.columns:
            survey_df[c] = ""
    survey_df = survey_df[survey_cols]

    return survey_df, choices_df, settings_df


def export_package_xlsx_and_media(survey_df, choices_df, settings_df, logo_bytes: bytes | None, logo_filename: str | None) -> bytes:
    """
    Exporta un ZIP con:
    - form.xlsx (survey/choices/settings)
    - media/<logo> (si se subió)
    Esto es útil porque Survey123 requiere el archivo en la carpeta media.
    """
    xlsx_io = io.BytesIO()
    with pd.ExcelWriter(xlsx_io, engine="openpyxl") as writer:
        survey_df.to_excel(writer, index=False, sheet_name="survey")
        choices_df.to_excel(writer, index=False, sheet_name="choices")
        settings_df.to_excel(writer, index=False, sheet_name="settings")
    xlsx_bytes = xlsx_io.getvalue()

    zip_io = io.BytesIO()
    with zipfile.ZipFile(zip_io, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("form.xlsx", xlsx_bytes)
        if logo_bytes and logo_filename:
            z.writestr(f"media/{logo_filename}", logo_bytes)
    return zip_io.getvalue()


# ------------------ BOTÓN GENERAR ------------------
if st.button("✅ Generar XLSForm (P1 + P2)", type="primary"):
    if not form_title.strip() or not form_id.strip():
        st.error("Pon form_title y form_id.")
        st.stop()

    logo_bytes = None
    logo_filename = None
    if logo_file is not None:
        logo_bytes = logo_file.read()
        # Nombre fijo recomendado para media
        ext = (logo_file.name.split(".")[-1] or "png").lower()
        if ext not in ["png", "jpg", "jpeg"]:
            ext = "png"
        logo_filename = f"logo_p1.{ext}"

    survey_df, choices_df, settings_df = build_xlsform(
        form_title=form_title,
        form_id=form_id,
        version=version,
        lugar=lugar,
        intro_text=intro_text,
        consent_text=consent_text,
        logo_filename=logo_filename
    )

    st.success("Listo. Descargá el paquete ZIP (form.xlsx + media/).")
    st.dataframe(survey_df, use_container_width=True, height=420)

    zip_bytes = export_package_xlsx_and_media(
        survey_df, choices_df, settings_df,
        logo_bytes=logo_bytes,
        logo_filename=logo_filename
    )

    st.download_button(
        "⬇️ Descargar paquete (ZIP con XLSX + media)",
        data=zip_bytes,
        file_name=f"{form_id.strip()}_P1_P2.zip",
        mime="application/zip"
    )
