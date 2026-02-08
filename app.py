# app.py
# =====================================================================================
# Editor XLSForm (Survey123) - Encuesta Comunidad 2026 (v4.1)
# - CRUD de preguntas (editar, eliminar, duplicar)
# - Reordenar preguntas (subir/bajar + mover a índice)
# - CRUD de listas de opciones (choices)
# - Exportar XLSForm a Excel (survey / choices / settings)
#
# Requisitos:
#   streamlit, pandas, openpyxl
#
# Ejecutar:
#   streamlit run app.py
# =====================================================================================

from __future__ import annotations

import io
import re
from copy import deepcopy
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

import pandas as pd
import streamlit as st


# ---------------------------
# Utilidades
# ---------------------------

def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s[:60] if s else "item"


def make_choice(list_name: str, name: str, label: str) -> Dict[str, str]:
    return {"list_name": list_name, "name": name, "label": label}


def validate_unique_question_names(questions: List[Dict[str, Any]]) -> List[str]:
    seen = {}
    errors = []
    for i, q in enumerate(questions):
        n = (q.get("name") or "").strip()
        if not n:
            errors.append(f"Fila #{i+1}: pregunta sin 'name'.")
            continue
        if n in seen:
            errors.append(f"Duplicado 'name': {n} (filas {seen[n]} y {i+1}).")
        else:
            seen[n] = i + 1
    return errors


def constraint_none_and_others(field: str, none_value: str) -> str:
    # XLSForm: no permitir "none" junto con otras en select_multiple
    # Ejemplo: not(selected(${q12}, 'no_observa') and count-selected(${q12}) > 1)
    return f"not(selected(${{{field}}}, '{none_value}') and count-selected(${{{field}}}) > 1)"


def to_excel_bytes(survey_df: pd.DataFrame, choices_df: pd.DataFrame, settings_df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        survey_df.to_excel(writer, index=False, sheet_name="survey")
        choices_df.to_excel(writer, index=False, sheet_name="choices")
        settings_df.to_excel(writer, index=False, sheet_name="settings")
    return output.getvalue()


# ---------------------------
# Datos base (Encuesta Comunidad 2026 v4.1)
# ---------------------------

def base_settings() -> Dict[str, str]:
    return {
        "form_title": "Encuesta Comunidad 2026",
        "form_id": "encuesta_comunidad_2026",
        "version": "v4.1",
        "default_language": "Spanish",
    }


def base_choices() -> Dict[str, List[Dict[str, str]]]:
    # Nota: Cantón/Distrito normalmente se manejan con cascada (choice_filter) y listas grandes.
    # Aquí dejamos placeholders para que las cargues/edites desde la app.
    choices = {}

    # Sí/No
    choices["yesno"] = [
        make_choice("yesno", "si", "Sí"),
        make_choice("yesno", "no", "No"),
    ]

    # Sí/No/A veces
    choices["si_no_aveces"] = [
        make_choice("si_no_aveces", "si", "Sí"),
        make_choice("si_no_aveces", "no", "No"),
        make_choice("si_no_aveces", "aveces", "A veces"),
    ]

    # Sí/No/No estoy seguro
    choices["si_no_noseguro"] = [
        make_choice("si_no_noseguro", "si", "Sí"),
        make_choice("si_no_noseguro", "no", "No"),
        make_choice("si_no_noseguro", "no_seguro", "No estoy seguro(a)"),
    ]

    # Sí/No/No recuerda
    choices["si_no_norec"] = [
        make_choice("si_no_norec", "si", "Sí"),
        make_choice("si_no_norec", "no", "No"),
        make_choice("si_no_norec", "no_recuerda", "No recuerda"),
    ]

    # Edad
    choices["edad_rangos"] = [
        make_choice("edad_rangos", "18_29", "18 a 29 años"),
        make_choice("edad_rangos", "30_44", "30 a 44 años"),
        make_choice("edad_rangos", "45_64", "45 a 64 años"),
        make_choice("edad_rangos", "65_mas", "65 años o más"),
    ]

    # Género
    choices["genero"] = [
        make_choice("genero", "femenino", "Femenino"),
        make_choice("genero", "masculino", "Masculino"),
        make_choice("genero", "no_binaria", "Persona no Binaria"),
        make_choice("genero", "pref_no_decir", "Prefiero no decir"),
    ]

    # Escolaridad
    choices["escolaridad"] = [
        make_choice("escolaridad", "ninguna", "Ninguna"),
        make_choice("escolaridad", "prim_incomp", "Primaria incompleta"),
        make_choice("escolaridad", "prim_comp", "Primaria completa"),
        make_choice("escolaridad", "sec_incomp", "Secundaria incompleta"),
        make_choice("escolaridad", "sec_comp", "Secundaria completa"),
        make_choice("escolaridad", "tecnico", "Técnico"),
        make_choice("escolaridad", "uni_incomp", "Universitaria incompleta"),
        make_choice("escolaridad", "uni_comp", "Universitaria completa"),
    ]

    # Relación con la zona
    choices["relacion_zona"] = [
        make_choice("relacion_zona", "vivo", "Vivo en la zona"),
        make_choice("relacion_zona", "trabajo", "Trabajo en la zona"),
        make_choice("relacion_zona", "visito", "Visito la zona"),
        make_choice("relacion_zona", "estudio", "Estudio en la zona"),
    ]

    # Likert seguridad 1-5 con No aplica
    choices["likert_1_5_na"] = [
        make_choice("likert_1_5_na", "1", "Muy Inseguro (1)"),
        make_choice("likert_1_5_na", "2", "Inseguro (2)"),
        make_choice("likert_1_5_na", "3", "Ni seguro ni inseguro (3)"),
        make_choice("likert_1_5_na", "4", "Seguro (4)"),
        make_choice("likert_1_5_na", "5", "Muy Seguro (5)"),
        make_choice("likert_1_5_na", "na", "No Aplica"),
    ]

    # Q7: percepción seguridad del distrito (5 categorías)
    choices["q7_seguridad"] = [
        make_choice("q7_seguridad", "muy_inseguro", "Muy inseguro"),
        make_choice("q7_seguridad", "inseguro", "Inseguro"),
        make_choice("q7_seguridad", "neutral", "Ni seguro ni inseguro"),
        make_choice("q7_seguridad", "seguro", "Seguro"),
        make_choice("q7_seguridad", "muy_seguro", "Muy seguro"),
    ]

    # Q8: cambio 12 meses (1-5)
    choices["q8_cambio"] = [
        make_choice("q8_cambio", "1", "1 (Mucho Menos Seguro)"),
        make_choice("q8_cambio", "2", "2 (Menos Seguro)"),
        make_choice("q8_cambio", "3", "3 (Se mantiene igual)"),
        make_choice("q8_cambio", "4", "4 (Más Seguro)"),
        make_choice("q8_cambio", "5", "5 (Mucho Más Seguro)"),
    ]

    # Espacios (Q10 + lista matriz Q9)
    choices["espacios_distrito"] = [
        make_choice("espacios_distrito", "discotecas", "Discotecas, bares, sitios de entretenimiento"),
        make_choice("espacios_distrito", "recreativos", "Espacios recreativos (parques, play, plaza de deportes)"),
        make_choice("espacios_distrito", "residencia", "Lugar de residencia (casa de habitación)"),
        make_choice("espacios_distrito", "paradas", "Paradas y/o estaciones de buses, taxis, trenes"),
        make_choice("espacios_distrito", "puentes", "Puentes peatones"),
        make_choice("espacios_distrito", "transporte_publico", "Transporte público"),
        make_choice("espacios_distrito", "bancaria", "Zona bancaria"),
        make_choice("espacios_distrito", "comercio", "Zona de comercio"),
        make_choice("espacios_distrito", "residenciales", "Zonas residenciales (calles y barrios, distinto a su casa)"),
        make_choice("espacios_distrito", "zonas_francas", "Zonas francas"),
        make_choice("espacios_distrito", "turistico", "Lugares de interés turístico"),
        make_choice("espacios_distrito", "educativos", "Centros educativos"),
        make_choice("espacios_distrito", "otros", "Otros"),
    ]

    # Q7.1 (multiselect percepción inseguridad)
    choices["q7_1_inseg"] = [
        make_choice("q7_1_inseg", "venta_drogas", "Venta o distribución de drogas"),
        make_choice("q7_1_inseg", "consumo_drogas", "Consumo de drogas en espacios públicos"),
        make_choice("q7_1_inseg", "consumo_alcohol", "Consumo de alcohol en espacios públicos"),
        make_choice("q7_1_inseg", "rinas", "Riñas o peleas frecuentes"),
        make_choice("q7_1_inseg", "asaltos_personas", "Asaltos o robos a personas"),
        make_choice("q7_1_inseg", "robos_vivienda_comercio", "Robos a viviendas o comercios"),
        make_choice("q7_1_inseg", "amenazas_extorsion", "Amenazas o extorsiones"),
        make_choice("q7_1_inseg", "balaceras", "Balaceras, detonaciones o ruidos similares"),
        make_choice("q7_1_inseg", "grupos_temor", "Presencia de grupos que generan temor"),
        make_choice("q7_1_inseg", "vandalismo", "Vandalismo o daños intencionales"),
        make_choice("q7_1_inseg", "poca_iluminacion", "Poca iluminación en calles o espacios públicos"),
        make_choice("q7_1_inseg", "lotes_baldios", "Lotes baldíos o abandonados"),
        make_choice("q7_1_inseg", "casas_abandonadas", "Casas o edificios abandonados"),
        make_choice("q7_1_inseg", "calles_mal_estado", "Calles en mal estado"),
        make_choice("q7_1_inseg", "basura", "Falta de limpieza o acumulación de basura"),
        make_choice("q7_1_inseg", "paradas_inseguras", "Paradas de bus inseguras"),
        make_choice("q7_1_inseg", "sin_camaras", "Falta de cámaras de seguridad"),
        make_choice("q7_1_inseg", "comercios_sin_control", "Comercios inseguros o sin control"),
        make_choice("q7_1_inseg", "danos_propiedad", "Daños frecuentes a la propiedad"),
        make_choice("q7_1_inseg", "situacion_calle", "Presencia de personas en situación de calle que influye en su percepción de seguridad"),
        make_choice("q7_1_inseg", "situacion_ocio", "Presencia de personas en situación de ocio (sin actividad laboral o educativa)"),
        make_choice("q7_1_inseg", "ventas_informales", "Ventas informales (ambulantes)"),
        make_choice("q7_1_inseg", "transporte_informal", "Problemas con transporte informal"),
        make_choice("q7_1_inseg", "sin_patrullaje", "Falta de patrullajes visibles"),
        make_choice("q7_1_inseg", "sin_presencia_policial", "Falta de presencia policial en la zona"),
        make_choice("q7_1_inseg", "vif", "Situaciones de violencia intrafamiliar"),
        make_choice("q7_1_inseg", "violencia_genero", "Situaciones de violencia de género"),
        make_choice("q7_1_inseg", "otro", "Otro problema que considere importante"),
    ]

    # Q12 problemáticas (incluye "no_observa")
    choices["q12_problemas"] = [
        make_choice("q12_problemas", "conflictos_vecinales", "Problemas vecinales o conflictos entre vecinos"),
        make_choice("q12_problemas", "situacion_calle", "Presencia de personas en situación de calle (personas que viven permanentemente en la vía pública)"),
        make_choice("q12_problemas", "prostitucion", "Zona donde se ejerce prostitución"),
        make_choice("q12_problemas", "desercion", "Desvinculación escolar (deserción escolar)"),
        make_choice("q12_problemas", "falta_empleo", "Falta de oportunidades laborales"),
        make_choice("q12_problemas", "basura_aguas", "Acumulación de basura, aguas negras o mal alcantarillado"),
        make_choice("q12_problemas", "sin_alumbrado", "Carencia o inexistencia de alumbrado público"),
        make_choice("q12_problemas", "lotes_baldios", "Lotes baldíos"),
        make_choice("q12_problemas", "cuarterias", "Cuarterías"),
        make_choice("q12_problemas", "asentamientos", "Asentamientos informales o precarios"),
        make_choice("q12_problemas", "perdida_espacios", "Pérdida de espacios públicos (parques, polideportivos u otros)"),
        make_choice("q12_problemas", "alcohol_via_publica", "Consumo de alcohol en vía pública"),
        make_choice("q12_problemas", "drogas_publico", "Consumo de drogas en espacios públicos"),
        make_choice("q12_problemas", "ventas_informales", "Ventas informales (ambulantes)"),
        make_choice("q12_problemas", "ruidos", "Escándalos musicales o ruidos excesivos"),
        make_choice("q12_problemas", "otro", "Otro problema que considere importante"),
        make_choice("q12_problemas", "no_observa", "No se observan estas problemáticas en el distrito"),
    ]

    # Q13 carencias (inversión social)
    choices["q13_carencias"] = [
        make_choice("q13_carencias", "educativa", "Falta de oferta educativa"),
        make_choice("q13_carencias", "deportiva", "Falta de oferta deportiva"),
        make_choice("q13_carencias", "recreativa", "Falta de oferta recreativa"),
        make_choice("q13_carencias", "cultural", "Falta de actividades culturales"),
        make_choice("q13_carencias", "otro", "Otro problema que considere importante"),
    ]

    # Q14 consumo drogas dónde
    choices["q14_drogas_donde"] = [
        make_choice("q14_drogas_donde", "publicas", "Áreas públicas (calles, parques, paradas, espacios abiertos)"),
        make_choice("q14_drogas_donde", "privadas", "Áreas privadas (viviendas, locales, espacios cerrados)"),
        make_choice("q14_drogas_donde", "no_observa", "No se observa consumo de drogas"),
    ]

    # Q15 deficiencias vial
    choices["q15_vial"] = [
        make_choice("q15_vial", "calles_mal_estado", "Calles en mal estado"),
        make_choice("q15_vial", "sin_senalizacion", "Falta de señalización de tránsito"),
        make_choice("q15_vial", "sin_aceras", "Carencia o inexistencia de aceras"),
    ]

    # Q16 puntos venta drogas
    choices["q16_puntos_venta"] = [
        make_choice("q16_puntos_venta", "casa", "Casa de habitación (espacio cerrado)"),
        make_choice("q16_puntos_venta", "edificacion_abandonada", "Edificación abandonada"),
        make_choice("q16_puntos_venta", "lote_baldio", "Lote baldío"),
        make_choice("q16_puntos_venta", "otro", "Otro tipo de espacio"),
        make_choice("q16_puntos_venta", "no_observa", "No se observa"),
    ]

    # Q17 transporte inseguridad
    choices["q17_transporte"] = [
        make_choice("q17_transporte", "informal", "Transporte informal o no autorizado (taxis piratas)"),
        make_choice("q17_transporte", "plataformas", "Plataformas de transporte digital"),
        make_choice("q17_transporte", "buses", "Transporte público (buses)"),
        make_choice("q17_transporte", "reparto", "Servicios de reparto o mensajería “exprés” (por ejemplo, repartidores en motocicleta o bicimoto)"),
        make_choice("q17_transporte", "otro", "Otro tipo de situación relacionada con el transporte"),
        make_choice("q17_transporte", "no_observa", "No se observa"),
    ]

    # Q18 delitos generales
    choices["q18_delitos"] = [
        make_choice("q18_delitos", "disturbios", "Disturbios en vía pública (riñas o agresiones)"),
        make_choice("q18_delitos", "danos_propiedad", "Daños a la propiedad (viviendas, comercios, vehículos u otros bienes)"),
        make_choice("q18_delitos", "danos_poliducto", "Daños al poliducto (perforaciones, tomas ilegales o vandalismo)"),
        make_choice("q18_delitos", "extorsion", "Extorsión (amenazas o intimidación para exigir dinero u otros beneficios)"),
        make_choice("q18_delitos", "hurto", "Hurto (sustracción de artículos mediante el descuido)"),
        make_choice("q18_delitos", "receptacion", "Compra o venta de artículos robados (receptación)"),
        make_choice("q18_delitos", "contrabando", "Contrabando (licor, cigarrillos, medicinas, ropa, calzado, etc.)"),
        make_choice("q18_delitos", "maltrato_animal", "Maltrato animal"),
        make_choice("q18_delitos", "coyotaje", "Tráfico de personas (coyotaje)"),
        make_choice("q18_delitos", "otro", "Otro delito"),
        make_choice("q18_delitos", "no_observa", "No se observan delitos"),
    ]

    # Q19 forma venta drogas
    choices["q19_venta_drogas"] = [
        make_choice("q19_venta_drogas", "cerrados", "En espacios cerrados (casas, edificaciones u otros inmuebles)"),
        make_choice("q19_venta_drogas", "via_publica", "En vía pública"),
        make_choice("q19_venta_drogas", "movil", "De forma ocasional o móvil (sin punto fijo)"),
        make_choice("q19_venta_drogas", "no_observa", "No se observa venta de drogas"),
        make_choice("q19_venta_drogas", "otro", "Otro"),
    ]

    # Q20 vida
    choices["q20_vida"] = [
        make_choice("q20_vida", "homicidios", "Homicidios (muerte intencional de una persona)"),
        make_choice("q20_vida", "heridos", "Personas heridas de forma intencional (heridos)"),
        make_choice("q20_vida", "femicidio", "Femicidio (homicidio de una mujer por razones de género)"),
        make_choice("q20_vida", "no_observa", "No se observan delitos contra la vida"),
    ]

    # Q21 sexuales
    choices["q21_sexuales"] = [
        make_choice("q21_sexuales", "abuso", "Abuso sexual (tocamientos u otros actos sexuales sin consentimiento)"),
        make_choice("q21_sexuales", "violacion", "Violación (acceso sexual sin consentimiento)"),
        make_choice("q21_sexuales", "acoso", "Acoso sexual (insinuaciones, solicitudes o conductas sexuales no deseadas)"),
        make_choice("q21_sexuales", "acoso_callejero", "Acoso callejero (comentarios, gestos o conductas sexuales en espacios públicos)"),
        make_choice("q21_sexuales", "no_observa", "No se observan delitos sexuales"),
    ]

    # Q22 asaltos
    choices["q22_asaltos"] = [
        make_choice("q22_asaltos", "personas", "Asalto a personas"),
        make_choice("q22_asaltos", "comercio", "Asalto a comercio"),
        make_choice("q22_asaltos", "vivienda", "Asalto a vivienda"),
        make_choice("q22_asaltos", "transporte", "Asalto a transporte público"),
        make_choice("q22_asaltos", "no_observa", "No se observan asaltos"),
    ]

    # Q23 estafas
    choices["q23_estafas"] = [
        make_choice("q23_estafas", "billetes_falsos", "Billetes falsos"),
        make_choice("q23_estafas", "documentos_falsos", "Documentos falsos"),
        make_choice("q23_estafas", "oro", "Estafas relacionadas con la compra o venta de oro"),
        make_choice("q23_estafas", "loteria", "Lotería falsa"),
        make_choice("q23_estafas", "informatica", "Estafas informáticas (por internet, redes sociales o correos electrónicos)"),
        make_choice("q23_estafas", "telefonicas", "Estafas telefónicas"),
        make_choice("q23_estafas", "tarjetas", "Estafas con tarjetas (clonación, cargos no autorizados)"),
        make_choice("q23_estafas", "no_observa", "No se observan estafas"),
    ]

    # Q24 robos
    choices["q24_robos"] = [
        make_choice("q24_robos", "comercios", "Robo a comercios"),
        make_choice("q24_robos", "edificaciones", "Robo a edificaciones"),
        make_choice("q24_robos", "viviendas", "Robo a viviendas"),
        make_choice("q24_robos", "vehiculos_completos", "Robo de vehículos completos"),
        make_choice("q24_robos", "tacha", "Robo a vehículos (tacha)"),
        make_choice("q24_robos", "ganado", "Robo de ganado (destace)"),
        make_choice("q24_robos", "bienes_agricolas", "Robo de bienes agrícolas"),
        make_choice("q24_robos", "cultivos", "Robo de cultivos"),
        make_choice("q24_robos", "cable", "Robo de cable"),
        make_choice("q24_robos", "no_observa", "No se observan robos"),
    ]

    # Q25 abandono
    choices["q25_abandono"] = [
        make_choice("q25_abandono", "adulto_mayor", "Abandono de adulto mayor"),
        make_choice("q25_abandono", "menor", "Abandono de menor de edad"),
        make_choice("q25_abandono", "incapaz", "Abandono de incapaz"),
        make_choice("q25_abandono", "no_observa", "No se observan situaciones de abandono"),
    ]

    # Q26 explotación infantil
    choices["q26_explotacion"] = [
        make_choice("q26_explotacion", "sexual", "Sexual"),
        make_choice("q26_explotacion", "laboral", "Laboral"),
        make_choice("q26_explotacion", "no_observa", "No se observan"),
    ]

    # Q27 ambientales
    choices["q27_ambientales"] = [
        make_choice("q27_ambientales", "caza", "Caza ilegal"),
        make_choice("q27_ambientales", "pesca", "Pesca ilegal"),
        make_choice("q27_ambientales", "tala", "Tala ilegal"),
        make_choice("q27_ambientales", "extraccion", "Extracción ilegal de material minero"),
        make_choice("q27_ambientales", "no_observa", "No se observan delitos ambientales"),
    ]

    # Q28 trata personas
    choices["q28_trata"] = [
        make_choice("q28_trata", "laboral", "Con fines laborales"),
        make_choice("q28_trata", "sexual", "Con fines sexuales"),
        make_choice("q28_trata", "no_observa", "No se observan situaciones de trata de personas"),
    ]

    # Q29.1 tipos VIF
    choices["q29_1_vif_tipos"] = [
        make_choice("q29_1_vif_tipos", "psicologica", "Violencia psicológica (gritos, amenazas, humillaciones, maltratos, entre otros)"),
        make_choice("q29_1_vif_tipos", "fisica", "Violencia física (agresiones físicas, empujones, golpes, entre otros)"),
        make_choice("q29_1_vif_tipos", "vicaria", "Violencia vicaria (uso de hijas, hijos u otras personas para causar daño emocional)"),
        make_choice("q29_1_vif_tipos", "patrimonial", "Violencia patrimonial (destrucción, retención o control de bienes, documentos o dinero)"),
        make_choice("q29_1_vif_tipos", "sexual", "Violencia sexual (actos de carácter sexual sin consentimiento)"),
    ]

    # Q29.3 valoración FP
    choices["q29_3_valora"] = [
        make_choice("q29_3_valora", "excelente", "Excelente"),
        make_choice("q29_3_valora", "bueno", "Bueno"),
        make_choice("q29_3_valora", "regular", "Regular"),
        make_choice("q29_3_valora", "malo", "Malo"),
        make_choice("q29_3_valora", "muy_malo", "Muy malo"),
    ]

    # Q30 victimización por delitos (única)
    choices["q30_vict_delito"] = [
        make_choice("q30_vict_delito", "no", "NO"),
        make_choice("q30_vict_delito", "si_denuncio", "Sí, y denuncié"),
        make_choice("q30_vict_delito", "si_no_denuncio", "Sí, pero no denuncié"),
    ]

    # Q30.1 situaciones (multi)
    choices["q30_1_situaciones"] = [
        make_choice("q30_1_situaciones", "asalto_mano_armada", "Asalto a mano armada (amenaza con arma o uso de violencia) en la calle o espacio público"),
        make_choice("q30_1_situaciones", "asalto_transporte", "Asalto en el transporte público (bus, taxi, metro, etc.)"),
        make_choice("q30_1_situaciones", "robo_vehiculo", "Asalto o robo de su vehículo (coche, motocicleta, etc.)"),
        make_choice("q30_1_situaciones", "robo_partes", "Robo de accesorios o partes de su vehículo (espejos, llantas, radio)"),
        make_choice("q30_1_situaciones", "robo_vivienda_fuerza", "Robo o intento de robo con fuerza a su vivienda (ej. forzar una puerta o ventana)"),
        make_choice("q30_1_situaciones", "robo_comercio_fuerza", "Robo o intento de robo con fuerza a su comercio o negocio"),
        make_choice("q30_1_situaciones", "hurto_cartera", "Hurto de su cartera, bolso o celular (sin que se diera cuenta, por descuido)"),
        make_choice("q30_1_situaciones", "danos_propiedad", "Daños a su propiedad (ej. grafitis, rotura de cristales, destrucción de cercas)"),
        make_choice("q30_1_situaciones", "receptacion", "Receptación (Alguien en su hogar compró o recibió un artículo que luego supo que era robado)"),
        make_choice("q30_1_situaciones", "perdida_descuido", "Pérdida de artículos (celular, bicicleta, etc.) por descuido"),
        make_choice("q30_1_situaciones", "estafa_telefonica", "Estafa telefónica (ej. llamadas para pedir dinero o datos personales)"),
        make_choice("q30_1_situaciones", "fraude_informatico", "Estafa o fraude informático (ej. a través de internet, redes sociales o correo electrónico)"),
        make_choice("q30_1_situaciones", "fraude_tarjetas", "Fraude con tarjetas bancarias (clonación o uso no autorizado)"),
        make_choice("q30_1_situaciones", "billetes_documentos", "Ser víctima de billetes o documentos falsos"),
        make_choice("q30_1_situaciones", "extorsion", "Extorsión (intimidación o amenaza para obtener dinero u otro beneficio)"),
        make_choice("q30_1_situaciones", "maltrato_animal", "Maltrato animal (si usted o alguien de su hogar fue testigo o su mascota fue la víctima)"),
        make_choice("q30_1_situaciones", "acoso_sexual_publico", "Acoso o intimidación sexual en un espacio público"),
        make_choice("q30_1_situaciones", "delito_sexual", "Algún tipo de delito sexual (abuso, violación)"),
        make_choice("q30_1_situaciones", "lesiones", "Lesiones personales (haber sido herido en una riña o agresión)"),
        make_choice("q30_1_situaciones", "otro", "Otro"),
    ]

    # Q30.2 motivos no denunciar
    choices["q30_2_motivos"] = [
        make_choice("q30_2_motivos", "distancia", "Distancia o dificultad de acceso a oficinas para denunciar"),
        make_choice("q30_2_motivos", "miedo", "Miedo a represalias"),
        make_choice("q30_2_motivos", "sin_seguimiento", "Falta de respuesta o seguimiento en denuncias anteriores"),
        make_choice("q30_2_motivos", "tramites", "Complejidad o dificultad para realizar la denuncia (trámites, requisitos, tiempo)"),
        make_choice("q30_2_motivos", "desconoce", "Desconocimiento de dónde colocar la denuncia (falta de información)"),
        make_choice("q30_2_motivos", "policia_no", "El Policía me dijo que era mejor no denunciar"),
        make_choice("q30_2_motivos", "sin_tiempo", "Falta de tiempo para colocar la denuncia"),
        make_choice("q30_2_motivos", "desconfianza", "Desconfianza en las autoridades o en el proceso de denuncia"),
        make_choice("q30_2_motivos", "otro", "Otro motivo"),
    ]

    # Q30.3 rango horario
    choices["q30_3_horario"] = [
        make_choice("q30_3_horario", "00_02", "00:00 – 02:59 (madrugada)"),
        make_choice("q30_3_horario", "03_05", "03:00 – 05:59 (madrugada)"),
        make_choice("q30_3_horario", "06_08", "06:00 – 08:59 (mañana)"),
        make_choice("q30_3_horario", "09_11", "09:00 – 11:59 (mañana)"),
        make_choice("q30_3_horario", "12_14", "12:00 – 14:59 (mediodía / tarde)"),
        make_choice("q30_3_horario", "15_17", "15:00 – 17:59 (tarde)"),
        make_choice("q30_3_horario", "18_20", "18:00 – 20:59 (noche)"),
        make_choice("q30_3_horario", "21_23", "21:00 – 23:59 (noche)"),
        make_choice("q30_3_horario", "desconocido", "Desconocido"),
    ]

    # Q30.4 modo ocurrido (incluye Arrebato)
    choices["q30_4_modo"] = [
        make_choice("q30_4_modo", "arma_blanca", "Arma blanca (cuchillo, machete, tijeras)"),
        make_choice("q30_4_modo", "arma_fuego", "Arma de fuego"),
        make_choice("q30_4_modo", "amenazas", "Amenazas o intimidación"),
        make_choice("q30_4_modo", "arrebato", "Arrebato (le quitaron un objeto de forma rápida o sorpresiva)"),
        make_choice("q30_4_modo", "boquete", "Boquete (ingreso mediante apertura de huecos en paredes, techos o estructuras)"),
        make_choice("q30_4_modo", "ganzua", "Ganzúa (pata de chancho, llaves falsas u objetos similares)"),
        make_choice("q30_4_modo", "engano", "Engaño (mediante mentiras, falsas ofertas o distracción)"),
        make_choice("q30_4_modo", "escalamiento", "Escalamiento (ingreso trepando muros, rejas o techos)"),
        make_choice("q30_4_modo", "otro", "Otro"),
        make_choice("q30_4_modo", "no_sabe", "No sabe / No recuerda"),
    ]

    # Q31.1 tipos de atención
    choices["q31_1_atencion"] = [
        make_choice("q31_1_atencion", "auxilio", "Solicitud de ayuda o auxilio"),
        make_choice("q31_1_atencion", "denuncia", "Atención relacionada con una denuncia"),
        make_choice("q31_1_atencion", "cordial", "Atención cordial o preventiva durante un patrullaje"),
        make_choice("q31_1_atencion", "abordado", "Fui abordado o registrado para identificación"),
        make_choice("q31_1_atencion", "infraccion", "Fui objeto de una infracción o conflicto"),
        make_choice("q31_1_atencion", "evento", "Evento preventivos (Cívico policial, Reunión Comunitaria)"),
        make_choice("q31_1_atencion", "otro", "Otra (especifique)"),
    ]

    # Q37 frecuencia
    choices["q37_frecuencia"] = [
        make_choice("q37_frecuencia", "diario", "Todos los días"),
        make_choice("q37_frecuencia", "varias", "Varias veces por semana"),
        make_choice("q37_frecuencia", "una", "Una vez por semana"),
        make_choice("q37_frecuencia", "casi_nunca", "Casi nunca"),
        make_choice("q37_frecuencia", "nunca", "Nunca"),
    ]

    # Q42 (multi)
    choices["q42_fp_mejora"] = [
        make_choice("q42_fp_mejora", "patrullaje", "Mayor presencia policial y patrullaje"),
        make_choice("q42_fp_mejora", "disuasivas", "Acciones disuasivas en puntos conflictivos"),
        make_choice("q42_fp_mejora", "drogas", "Acciones contra consumo y venta de drogas"),
        make_choice("q42_fp_mejora", "servicio", "Mejorar el servicio policial a la comunidad"),
        make_choice("q42_fp_mejora", "acercamiento", "Acercamiento comunitario y comercial"),
        make_choice("q42_fp_mejora", "prevencion", "Actividades de prevención y educación"),
        make_choice("q42_fp_mejora", "coordinacion", "Coordinación interinstitucional"),
        make_choice("q42_fp_mejora", "integridad", "Integridad y credibilidad policial"),
        make_choice("q42_fp_mejora", "otro", "Otro"),
        make_choice("q42_fp_mejora", "sin_opinion", "No tiene una opinión al respecto"),
    ]

    # Q43 (multi)
    choices["q43_muni_mejora"] = [
        make_choice("q43_muni_mejora", "iluminacion", "Mantenimiento e iluminación del espacio público"),
        make_choice("q43_muni_mejora", "limpieza", "Limpieza y ordenamiento urbano"),
        make_choice("q43_muni_mejora", "camaras", "Instalación de cámaras y seguridad municipal"),
        make_choice("q43_muni_mejora", "informal", "Control del comercio informal y transporte"),
        make_choice("q43_muni_mejora", "espacios", "Creación y mejoramiento de espacios públicos"),
        make_choice("q43_muni_mejora", "desarrollo", "Desarrollo social y generación de empleo"),
        make_choice("q43_muni_mejora", "coordinacion", "Coordinación interinstitucional"),
        make_choice("q43_muni_mejora", "acercamiento", "Acercamiento municipal a comercio y comunidad"),
        make_choice("q43_muni_mejora", "otro", "Otro"),
        make_choice("q43_muni_mejora", "sin_opinion", "No tiene una opinión al respecto"),
    ]

    # Cantón/Distrito placeholders
    choices["canton"] = [make_choice("canton", "placeholder", "Cargar cantones aquí (editar en Choices)")]
    choices["distrito"] = [make_choice("distrito", "placeholder", "Cargar distritos aquí (editar en Choices)")]

    return choices


def base_questions() -> List[Dict[str, Any]]:
    q = []

    # --- Sección: Consentimiento
    q.append({"type": "begin_group", "name": "sec_consentimiento", "label": "Consentimiento informado", "hint": "", "required": "", "relevant": "", "constraint": "", "constraint_message": "", "appearance": "field-list", "choice_list": ""})

    q.append({
        "type": "select_one yesno",
        "name": "consent",
        "label": "¿Acepta participar en esta encuesta?",
        "hint": "Participación libre y voluntaria. Si responde “No”, finaliza la encuesta.",
        "required": "yes",
        "relevant": "",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "yesno",
    })
    q.append({
        "type": "end_group",
        "name": "",
        "label": "",
        "hint": "",
        "required": "",
        "relevant": "",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "",
    })

    # --- Sección I: Datos demográficos
    q.append({"type": "begin_group", "name": "sec_demograficos", "label": "I. Datos demográficos", "hint": "", "required": "", "relevant": "${consent} = 'si'", "constraint": "", "constraint_message": "", "appearance": "field-list", "choice_list": ""})

    q.append({"type": "select_one canton", "name": "canton", "label": "1. Cantón:", "hint": "", "required": "yes", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "canton"})
    q.append({"type": "select_one distrito", "name": "distrito", "label": "2. Distrito:", "hint": "", "required": "yes", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "distrito"})
    q.append({"type": "select_one edad_rangos", "name": "edad", "label": "3. Edad (en años cumplidos): marque una categoría que incluya su edad.", "hint": "", "required": "yes", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "edad_rangos"})
    q.append({"type": "select_one genero", "name": "genero", "label": "4. ¿Con cuál de estas opciones se identifica?", "hint": "", "required": "yes", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "genero"})
    q.append({"type": "select_one escolaridad", "name": "escolaridad", "label": "5. Escolaridad:", "hint": "", "required": "yes", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "escolaridad"})
    q.append({"type": "select_one relacion_zona", "name": "relacion_zona", "label": "6. ¿Cuál es su relación con la zona?", "hint": "", "required": "yes", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "relacion_zona"})

    q.append({"type": "end_group", "name": "", "label": "", "hint": "", "required": "", "relevant": "", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": ""})

    # --- Sección II: Percepción
    q.append({"type": "begin_group", "name": "sec_percepcion", "label": "II. Percepción ciudadana de seguridad en el distrito", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "field-list", "choice_list": ""})

    q.append({
        "type": "select_one q7_seguridad",
        "name": "q7",
        "label": "7. ¿Qué tan seguro percibe usted el distrito donde reside o transita?",
        "hint": "",
        "required": "yes",
        "relevant": "${consent}='si'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q7_seguridad",
    })

    q.append({
        "type": "select_multiple q7_1_inseg",
        "name": "q7_1",
        "label": "7.1. Indique por qué considera el distrito inseguro (marque todas las situaciones que percibe que ocurren con mayor frecuencia):",
        "hint": "Percepción general (no constituye denuncia).",
        "required": "",
        "relevant": "${q7}='muy_inseguro' or ${q7}='inseguro'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q7_1_inseg",
    })

    q.append({
        "type": "select_one q8_cambio",
        "name": "q8",
        "label": "8. En comparación con los 12 meses anteriores, ¿cómo percibe que ha cambiado la seguridad en este distrito?",
        "hint": "",
        "required": "yes",
        "relevant": "${consent}='si'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q8_cambio",
    })

    q.append({
        "type": "text",
        "name": "q8_1",
        "label": "8.1. Indique por qué (explique brevemente la razón de su respuesta anterior):",
        "hint": "",
        "required": "",
        "relevant": "${q8} != ''",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "",
    })

    # Q9 matriz -> se modela como varias preguntas select_one con misma lista
    q.append({"type": "begin_group", "name": "q9_matriz", "label": "9. En términos de seguridad, indique qué tan seguros percibe los siguientes espacios de su distrito:", "hint": "Seleccione una opción por cada espacio.", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "field-list", "choice_list": ""})

    espacios = [
        ("discotecas", "Discotecas, bares, sitios de entretenimiento"),
        ("recreativos", "Espacios recreativos (parques, play, plaza de deportes)"),
        ("residencia", "Lugar de residencia (casa de habitación)"),
        ("paradas", "Paradas y/o estaciones de buses, taxis, trenes"),
        ("puentes", "Puentes peatones"),
        ("transporte_publico", "Transporte público"),
        ("bancaria", "Zona bancaria"),
        ("comercio", "Zona de comercio"),
        ("residenciales", "Zonas residenciales (calles y barrios, distinto a su casa)"),
        ("zonas_francas", "Zonas francas"),
        ("turistico", "Lugares de interés turístico"),
        ("educativos", "Centros educativos"),
    ]
    for code, label in espacios:
        q.append({
            "type": "select_one likert_1_5_na",
            "name": f"q9_{code}",
            "label": label,
            "hint": "",
            "required": "",
            "relevant": "${consent}='si'",
            "constraint": "",
            "constraint_message": "",
            "appearance": "",
            "choice_list": "likert_1_5_na",
        })
    q.append({"type": "end_group", "name": "", "label": "", "hint": "", "required": "", "relevant": "", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": ""})

    q.append({
        "type": "select_one espacios_distrito",
        "name": "q10",
        "label": "10. Desde su percepción ¿cuál considera que es el principal foco de inseguridad en el distrito?",
        "hint": "",
        "required": "yes",
        "relevant": "${consent}='si'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "espacios_distrito",
    })

    q.append({
        "type": "text",
        "name": "q11",
        "label": "11. Describa brevemente las razones por las cuales considera inseguro el tipo de espacio seleccionado en la pregunta anterior.",
        "hint": "",
        "required": "",
        "relevant": "${q10} != ''",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "",
    })

    q.append({"type": "end_group", "name": "", "label": "", "hint": "", "required": "", "relevant": "", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": ""})

    # --- Sección III: Riesgos/Delitos/Victimización
    q.append({"type": "begin_group", "name": "sec_riesgos_delitos", "label": "III. Riesgos, delitos, victimización y evaluación policial", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "field-list", "choice_list": ""})

    # Q12
    q.append({
        "type": "select_multiple q12_problemas",
        "name": "q12",
        "label": "12. Según su percepción u observación, seleccione las problemáticas que afectan su distrito:",
        "hint": "Si marca “No se observan…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q12", "no_observa"),
        "constraint_message": "Si marca “No se observan…”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q12_problemas",
    })

    q.append({
        "type": "select_multiple q13_carencias",
        "name": "q13",
        "label": "13. En relación con la oferta de servicios y oportunidades en su distrito (inversión social), indique cuáles carencias identifica:",
        "hint": "",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q13_carencias",
    })

    q.append({
        "type": "select_multiple q14_drogas_donde",
        "name": "q14",
        "label": "14. En los casos en que se observa consumo de drogas en el distrito, indique dónde ocurre:",
        "hint": "Si marca “No se observa…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q14", "no_observa"),
        "constraint_message": "Si marca “No se observa…”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q14_drogas_donde",
    })

    q.append({
        "type": "select_multiple q15_vial",
        "name": "q15",
        "label": "15. Indique las principales deficiencias de infraestructura vial que afectan su distrito:",
        "hint": "",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q15_vial",
    })

    q.append({
        "type": "select_multiple q16_puntos_venta",
        "name": "q16",
        "label": "16. Según su percepción u observación, indique en qué tipo de espacios se identifica la existencia de puntos de venta de drogas en el distrito:",
        "hint": "Si marca “No se observa”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q16", "no_observa"),
        "constraint_message": "Si marca “No se observa”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q16_puntos_venta",
    })

    q.append({
        "type": "select_multiple q17_transporte",
        "name": "q17",
        "label": "17. Según su percepción u observación, indique si ha identificado situaciones de inseguridad asociadas al transporte en su distrito:",
        "hint": "Si marca “No se observa”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q17", "no_observa"),
        "constraint_message": "Si marca “No se observa”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q17_transporte",
    })

    # Delitos
    q.append({"type": "begin_group", "name": "grp_delitos", "label": "Delitos (observación/conocimiento)", "hint": "No constituye denuncia formal.", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "field-list", "choice_list": ""})

    q.append({
        "type": "select_multiple q18_delitos",
        "name": "q18",
        "label": "18. Seleccione los delitos que, según su conocimiento u observación, se presentan en el distrito:",
        "hint": "Si marca “No se observan…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q18", "no_observa"),
        "constraint_message": "Si marca “No se observan delitos”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q18_delitos",
    })

    q.append({
        "type": "select_multiple q19_venta_drogas",
        "name": "q19",
        "label": "19. Según su conocimiento u observación, ¿de qué forma se presenta la venta de drogas en el distrito?",
        "hint": "Si marca “No se observa…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q19", "no_observa"),
        "constraint_message": "Si marca “No se observa…”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q19_venta_drogas",
    })

    q.append({
        "type": "select_multiple q20_vida",
        "name": "q20",
        "label": "20. Delitos contra la vida:",
        "hint": "Si marca “No se observan…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q20", "no_observa"),
        "constraint_message": "Si marca “No se observan…”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q20_vida",
    })

    q.append({
        "type": "select_multiple q21_sexuales",
        "name": "q21",
        "label": "21. Delitos sexuales:",
        "hint": "Si marca “No se observan…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q21", "no_observa"),
        "constraint_message": "Si marca “No se observan…”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q21_sexuales",
    })

    q.append({
        "type": "select_multiple q22_asaltos",
        "name": "q22",
        "label": "22. Asaltos:",
        "hint": "Si marca “No se observan…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q22", "no_observa"),
        "constraint_message": "Si marca “No se observan…”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q22_asaltos",
    })

    q.append({
        "type": "select_multiple q23_estafas",
        "name": "q23",
        "label": "23. Estafas:",
        "hint": "Si marca “No se observan…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q23", "no_observa"),
        "constraint_message": "Si marca “No se observan…”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q23_estafas",
    })

    q.append({
        "type": "select_multiple q24_robos",
        "name": "q24",
        "label": "24. Robo (sustracción mediante la utilización de la fuerza):",
        "hint": "Si marca “No se observan…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q24", "no_observa"),
        "constraint_message": "Si marca “No se observan…”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q24_robos",
    })

    q.append({
        "type": "select_multiple q25_abandono",
        "name": "q25",
        "label": "25. Abandono de personas:",
        "hint": "Si marca “No se observan…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q25", "no_observa"),
        "constraint_message": "Si marca “No se observan…”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q25_abandono",
    })

    q.append({
        "type": "select_multiple q26_explotacion",
        "name": "q26",
        "label": "26. Explotación infantil:",
        "hint": "Si marca “No se observan…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q26", "no_observa"),
        "constraint_message": "Si marca “No se observan…”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q26_explotacion",
    })

    q.append({
        "type": "select_multiple q27_ambientales",
        "name": "q27",
        "label": "27. Delitos ambientales:",
        "hint": "Si marca “No se observan…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q27", "no_observa"),
        "constraint_message": "Si marca “No se observan…”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q27_ambientales",
    })

    q.append({
        "type": "select_multiple q28_trata",
        "name": "q28",
        "label": "28. Trata de personas:",
        "hint": "Si marca “No se observan…”, no seleccione otras opciones.",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": constraint_none_and_others("q28", "no_observa"),
        "constraint_message": "Si marca “No se observan…”, no puede seleccionar otras opciones.",
        "appearance": "",
        "choice_list": "q28_trata",
    })

    q.append({"type": "end_group", "name": "", "label": "", "hint": "", "required": "", "relevant": "", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": ""})

    # Victimización
    q.append({"type": "begin_group", "name": "grp_victim", "label": "Victimización", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "field-list", "choice_list": ""})

    q.append({
        "type": "select_one yesno",
        "name": "q29",
        "label": "29. Durante los últimos 12 meses, ¿usted o algún miembro de su hogar ha sido afectado por violencia intrafamiliar?",
        "hint": "",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "yesno",
    })

    q.append({
        "type": "select_multiple q29_1_vif_tipos",
        "name": "q29_1",
        "label": "29.1. ¿Qué tipo(s) de violencia intrafamiliar se presentaron?",
        "hint": "",
        "required": "",
        "relevant": "${q29}='si'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q29_1_vif_tipos",
    })

    q.append({
        "type": "select_one si_no_norec",
        "name": "q29_2",
        "label": "29.2. ¿Solicitó medidas de protección?",
        "hint": "",
        "required": "",
        "relevant": "${q29}='si'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "si_no_norec",
    })

    q.append({
        "type": "select_one q29_3_valora",
        "name": "q29_3",
        "label": "29.3. ¿Cómo valora el abordaje de la Fuerza Pública ante esta situación?",
        "hint": "",
        "required": "",
        "relevant": "${q29}='si'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q29_3_valora",
    })

    q.append({
        "type": "select_one q30_vict_delito",
        "name": "q30",
        "label": "30. Durante los últimos 12 meses, ¿usted o algún miembro de su hogar fue afectado por algún delito?",
        "hint": "",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q30_vict_delito",
    })

    q.append({
        "type": "select_multiple q30_1_situaciones",
        "name": "q30_1",
        "label": "30.1. ¿Cuál de las siguientes situaciones afectó a usted o a algún miembro de su hogar?",
        "hint": "",
        "required": "",
        "relevant": "${q30}!='no'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q30_1_situaciones",
    })

    q.append({
        "type": "select_multiple q30_2_motivos",
        "name": "q30_2",
        "label": "30.2. En caso de no haber realizado la denuncia, indique el/los motivo(s):",
        "hint": "",
        "required": "",
        "relevant": "${q30}='si_no_denuncio'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q30_2_motivos",
    })

    q.append({
        "type": "select_one q30_3_horario",
        "name": "q30_3",
        "label": "30.3. ¿Tiene conocimiento sobre el horario en el cual se presentó el hecho?",
        "hint": "",
        "required": "",
        "relevant": "${q30}!='no'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q30_3_horario",
    })

    q.append({
        "type": "select_multiple q30_4_modo",
        "name": "q30_4",
        "label": "30.4. ¿Cuál fue la forma o modo en que ocurrió la situación?",
        "hint": "",
        "required": "",
        "relevant": "${q30}!='no'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q30_4_modo",
    })

    q.append({"type": "end_group", "name": "", "label": "", "hint": "", "required": "", "relevant": "", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": ""})

    # Confianza policial
    q.append({"type": "begin_group", "name": "grp_confianza", "label": "Confianza policial", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "field-list", "choice_list": ""})

    q.append({
        "type": "select_one yesno",
        "name": "q31",
        "label": "31. ¿Identifica usted a los policías de la Fuerza Pública de Costa Rica en su comunidad?",
        "hint": "",
        "required": "",
        "relevant": "${consent}='si'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "yesno",
    })

    q.append({
        "type": "select_multiple q31_1_atencion",
        "name": "q31_1",
        "label": "31.1. ¿Cuáles de los siguientes tipos de atención ha tenido?",
        "hint": "",
        "required": "",
        "relevant": "${q31}='si'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "q31_1_atencion",
    })

    # Escalas 1-10 como integer con constraint
    scale_1_10 = "(. >= 1 and . <= 10)"
    q.append({"type": "integer", "name": "q32", "label": "32. Nivel de confianza en la policía (1=Ninguna, 10=Mucha confianza):", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": scale_1_10, "constraint_message": "Ingrese un valor entre 1 y 10.", "appearance": "", "choice_list": ""})
    q.append({"type": "integer", "name": "q33", "label": "33. Profesionalidad de Fuerza Pública (1=Nada profesional, 10=Muy profesional):", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": scale_1_10, "constraint_message": "Ingrese un valor entre 1 y 10.", "appearance": "", "choice_list": ""})
    q.append({"type": "integer", "name": "q34", "label": "34. Calidad del servicio policial (1=Muy mala, 10=Muy buena):", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": scale_1_10, "constraint_message": "Ingrese un valor entre 1 y 10.", "appearance": "", "choice_list": ""})
    q.append({"type": "integer", "name": "q35", "label": "35. Satisfacción con el trabajo preventivo (1=Nada satisfecho, 10=Muy satisfecho):", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": scale_1_10, "constraint_message": "Ingrese un valor entre 1 y 10.", "appearance": "", "choice_list": ""})
    q.append({"type": "integer", "name": "q36", "label": "36. Medida en que la presencia policial ayuda a reducir el crimen (1=No contribuye, 10=Contribuye muchísimo):", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": scale_1_10, "constraint_message": "Ingrese un valor entre 1 y 10.", "appearance": "", "choice_list": ""})

    q.append({"type": "select_one q37_frecuencia", "name": "q37", "label": "37. ¿Con qué frecuencia observa presencia policial en su distrito?", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "q37_frecuencia"})
    q.append({"type": "select_one si_no_aveces", "name": "q38", "label": "38. ¿La presencia policial es consistente a lo largo del día?", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "si_no_aveces"})
    q.append({"type": "select_one si_no_aveces", "name": "q39", "label": "39. ¿La policía trata a las personas de manera justa e imparcial?", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "si_no_aveces"})
    q.append({"type": "select_one si_no_noseguro", "name": "q40", "label": "40. ¿Puede expresar quejas a la policía sin temor a represalias?", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "si_no_noseguro"})
    q.append({"type": "select_one si_no_aveces", "name": "q41", "label": "41. ¿La policía proporciona información veraz, clara y oportuna a la comunidad?", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "si_no_aveces"})

    q.append({"type": "end_group", "name": "", "label": "", "hint": "", "required": "", "relevant": "", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": ""})

    # Propuestas
    q.append({"type": "begin_group", "name": "grp_propuestas", "label": "Propuestas ciudadanas", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "field-list", "choice_list": ""})

    q.append({"type": "select_multiple q42_fp_mejora", "name": "q42", "label": "42. ¿Qué actividad considera que deba realizar la Fuerza Pública para mejorar la seguridad en su comunidad?", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "q42_fp_mejora"})
    q.append({"type": "select_multiple q43_muni_mejora", "name": "q43", "label": "43. ¿Qué actividad considera que deba realizar la municipalidad para mejorar la seguridad en su comunidad?", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "q43_muni_mejora"})

    q.append({"type": "end_group", "name": "", "label": "", "hint": "", "required": "", "relevant": "", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": ""})

    # Contacto voluntario
    q.append({"type": "begin_group", "name": "grp_contacto", "label": "Información adicional y contacto voluntario", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "field-list", "choice_list": ""})

    q.append({"type": "select_one yesno", "name": "q44", "label": "44. ¿Usted tiene información de alguna persona o grupo que se dedique a realizar algún delito en su comunidad?", "hint": "Información confidencial y voluntaria (no constituye denuncia formal).", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": "yesno"})
    q.append({"type": "text", "name": "q44_1", "label": "44.1. Si su respuesta es “Sí”, describa características que pueda aportar (nombre de estructura/banda, alias, domicilio, vehículos, etc.).", "hint": "", "required": "", "relevant": "${q44}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": ""})
    q.append({"type": "text", "name": "q45", "label": "45. (Voluntario) Anote nombre/teléfono/correo para ser contactado de forma confidencial.", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": ""})
    q.append({"type": "text", "name": "q46", "label": "46. Registre cualquier otra información que estime pertinente.", "hint": "", "required": "", "relevant": "${consent}='si'", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": ""})

    q.append({"type": "end_group", "name": "", "label": "", "hint": "", "required": "", "relevant": "", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": ""})

    # Final (nota: en Survey123 para terminar en "No", se puede usar una nota y un end)
    q.insert(2, {
        "type": "begin_group",
        "name": "end_if_no",
        "label": "",
        "hint": "",
        "required": "",
        "relevant": "${consent}='no'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "",
    })
    q.insert(3, {
        "type": "note",
        "name": "msg_no",
        "label": "Gracias. No se continuará con la encuesta porque no otorgó consentimiento.",
        "hint": "",
        "required": "",
        "relevant": "${consent}='no'",
        "constraint": "",
        "constraint_message": "",
        "appearance": "",
        "choice_list": "",
    })
    q.insert(4, {"type": "end_group", "name": "", "label": "", "hint": "", "required": "", "relevant": "", "constraint": "", "constraint_message": "", "appearance": "", "choice_list": ""})

    return q


def init_state():
    if "settings" not in st.session_state:
        st.session_state.settings = base_settings()
    if "choices" not in st.session_state:
        st.session_state.choices = base_choices()
    if "questions" not in st.session_state:
        st.session_state.questions = base_questions()
    if "selected_q_index" not in st.session_state:
        st.session_state.selected_q_index = 0


# ---------------------------
# Conversión a DataFrames XLSForm
# ---------------------------

SURVEY_COLS = [
    "type", "name", "label", "hint", "required", "relevant",
    "constraint", "constraint_message", "appearance"
]
CHOICES_COLS = ["list_name", "name", "label"]


def build_survey_df(questions: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for q in questions:
        row = {c: q.get(c, "") for c in SURVEY_COLS}
        rows.append(row)
    return pd.DataFrame(rows, columns=SURVEY_COLS)


def build_choices_df(choices: Dict[str, List[Dict[str, str]]]) -> pd.DataFrame:
    rows = []
    for list_name, items in choices.items():
        for it in items:
            rows.append({"list_name": list_name, "name": it["name"], "label": it["label"]})
    return pd.DataFrame(rows, columns=CHOICES_COLS)


def build_settings_df(settings: Dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame([settings])


# ---------------------------
# UI (Streamlit)
# ---------------------------

st.set_page_config(page_title="Editor XLSForm - Comunidad 2026", layout="wide")
init_state()

st.title("🧩 Editor XLSForm (Survey123) — Encuesta Comunidad 2026 v4.1")
st.caption("Editar preguntas, opciones, condicionales (relevant/constraint), reordenar y exportar a Excel (XLSForm).")

tabs = st.tabs(["📝 Preguntas", "📚 Choices (Opciones)", "⚙️ Settings", "📤 Exportar", "✅ Validación"])

# ---------------------------
# TAB: Preguntas
# ---------------------------
with tabs[0]:
    col_left, col_right = st.columns([0.35, 0.65], gap="large")

    with col_left:
        st.subheader("Lista de preguntas")
        questions = st.session_state.questions

        labels = []
        for i, q in enumerate(questions):
            t = q.get("type", "")
            name = q.get("name", "")
            lbl = q.get("label", "")
            show = f"{i+1:03d} | {t} | {name} | {lbl[:55]}"
            labels.append(show)

        idx = st.selectbox(
            "Seleccionar",
            options=list(range(len(labels))),
            format_func=lambda i: labels[i],
            index=st.session_state.selected_q_index if len(labels) else 0
        )
        st.session_state.selected_q_index = idx

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("⬆️ Subir", use_container_width=True, disabled=(idx == 0)):
                questions[idx-1], questions[idx] = questions[idx], questions[idx-1]
                st.session_state.selected_q_index = idx - 1
                st.rerun()
        with c2:
            if st.button("⬇️ Bajar", use_container_width=True, disabled=(idx >= len(questions)-1)):
                questions[idx+1], questions[idx] = questions[idx], questions[idx+1]
                st.session_state.selected_q_index = idx + 1
                st.rerun()
        with c3:
            new_pos = st.number_input("Mover a índice", min_value=1, max_value=len(questions), value=idx+1)
            if st.button("🚚 Mover", use_container_width=True):
                new_i = int(new_pos) - 1
                item = questions.pop(idx)
                questions.insert(new_i, item)
                st.session_state.selected_q_index = new_i
                st.rerun()

        st.divider()

        st.subheader("Acciones")
        a1, a2 = st.columns(2)
        with a1:
            if st.button("➕ Nueva pregunta", use_container_width=True):
                questions.insert(idx+1, {
                    "type": "text",
                    "name": f"nueva_{len(questions)+1}",
                    "label": "Nueva pregunta",
                    "hint": "",
                    "required": "",
                    "relevant": "",
                    "constraint": "",
                    "constraint_message": "",
                    "appearance": "",
                    "choice_list": "",
                })
                st.session_state.selected_q_index = idx + 1
                st.rerun()
        with a2:
            if st.button("📄 Duplicar", use_container_width=True):
                questions.insert(idx+1, deepcopy(questions[idx]))
                st.session_state.selected_q_index = idx + 1
                st.rerun()

        if st.button("🗑️ Eliminar", type="secondary", use_container_width=True):
            if len(questions) > 1:
                questions.pop(idx)
                st.session_state.selected_q_index = max(0, idx - 1)
                st.rerun()
            else:
                st.warning("No puede eliminar la última pregunta.")

    with col_right:
        st.subheader("Editar pregunta seleccionada")
        q = st.session_state.questions[st.session_state.selected_q_index]

        # Campos base
        q["type"] = st.text_input("type", value=q.get("type", ""))
        q["name"] = st.text_input("name", value=q.get("name", ""))
        q["label"] = st.text_area("label", value=q.get("label", ""), height=90)
        q["hint"] = st.text_area("hint", value=q.get("hint", ""), height=60)

        c1, c2 = st.columns(2)
        with c1:
            q["required"] = st.text_input("required (ej: yes)", value=q.get("required", ""))
            q["appearance"] = st.text_input("appearance", value=q.get("appearance", ""))
        with c2:
            q["relevant"] = st.text_input("relevant (lógica/condicional)", value=q.get("relevant", ""))
            q["constraint"] = st.text_input("constraint", value=q.get("constraint", ""))

        q["constraint_message"] = st.text_input("constraint_message", value=q.get("constraint_message", ""))

        st.caption("Tips rápidos: para select_one/ select_multiple se usa 'type' como: `select_one lista` o `select_multiple lista`.")

        # Si es select_one/multiple, mostrar ayuda de lista
        m = re.match(r"^\s*(select_one|select_multiple)\s+([A-Za-z0-9_]+)\s*$", q.get("type", ""))
        if m:
            list_name = m.group(2)
            st.info(f"Esta pregunta usa la lista de opciones: **{list_name}** (edítala en la pestaña **Choices**).")


# ---------------------------
# TAB: Choices
# ---------------------------
with tabs[1]:
    st.subheader("Listas de opciones (choices)")
    choices = st.session_state.choices

    list_names = sorted(list(choices.keys()))
    sel_list = st.selectbox("Seleccionar lista", list_names, index=0)

    st.write(f"**Lista:** `{sel_list}`  |  **Opciones:** {len(choices[sel_list])}")

    ch_df = pd.DataFrame(choices[sel_list])
    edited = st.data_editor(
        ch_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "list_name": st.column_config.TextColumn(disabled=True),
            "name": st.column_config.TextColumn(),
            "label": st.column_config.TextColumn(),
        },
        hide_index=True
    )

    # Guardar cambios
    if st.button("💾 Guardar cambios en esta lista"):
        # Re-armar con list_name fijo
        new_items = []
        for _, row in edited.iterrows():
            nm = str(row.get("name", "")).strip()
            lb = str(row.get("label", "")).strip()
            if nm and lb:
                new_items.append(make_choice(sel_list, nm, lb))
        choices[sel_list] = new_items
        st.success("Lista guardada.")

    st.divider()
    st.subheader("Crear / Eliminar listas")
    c1, c2 = st.columns(2)
    with c1:
        new_list = st.text_input("Nueva lista (list_name)", value="")
        if st.button("➕ Crear lista"):
            ln = slugify(new_list)
            if not ln:
                st.warning("Nombre inválido.")
            elif ln in choices:
                st.warning("Esa lista ya existe.")
            else:
                choices[ln] = [make_choice(ln, "opcion_1", "Opción 1")]
                st.success(f"Lista creada: {ln}")
                st.rerun()
    with c2:
        del_list = st.selectbox("Eliminar lista", [""] + list_names)
        if st.button("🗑️ Eliminar lista seleccionada"):
            if del_list and del_list in choices:
                # OJO: si hay preguntas que la usan, el XLSForm quedará inválido.
                del choices[del_list]
                st.success("Lista eliminada.")
                st.rerun()


# ---------------------------
# TAB: Settings
# ---------------------------
with tabs[2]:
    st.subheader("Settings (XLSForm)")
    s = st.session_state.settings
    s["form_title"] = st.text_input("form_title", value=s.get("form_title", ""))
    s["form_id"] = st.text_input("form_id", value=s.get("form_id", ""))
    s["version"] = st.text_input("version", value=s.get("version", ""))
    s["default_language"] = st.text_input("default_language", value=s.get("default_language", "Spanish"))
    st.info("En Survey123, settings mínimos suelen ser suficientes (form_title, form_id, version).")


# ---------------------------
# TAB: Exportar
# ---------------------------
with tabs[3]:
    st.subheader("Exportar XLSForm a Excel")
    survey_df = build_survey_df(st.session_state.questions)
    choices_df = build_choices_df(st.session_state.choices)
    settings_df = build_settings_df(st.session_state.settings)

    st.write("Vista previa: **survey**")
    st.dataframe(survey_df, use_container_width=True, height=280)

    st.write("Vista previa: **choices**")
    st.dataframe(choices_df, use_container_width=True, height=200)

    excel_bytes = to_excel_bytes(survey_df, choices_df, settings_df)

    st.download_button(
        label="⬇️ Descargar XLSForm (Excel)",
        data=excel_bytes,
        file_name=f"{st.session_state.settings.get('form_id','encuesta')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.caption("Luego lo cargas en Survey123 Connect / ArcGIS para publicar la encuesta.")


# ---------------------------
# TAB: Validación
# ---------------------------
with tabs[4]:
    st.subheader("Validación básica")
    errs = validate_unique_question_names(st.session_state.questions)

    if errs:
        st.error("Hay problemas que conviene corregir antes de exportar:")
        for e in errs:
            st.write(f"- {e}")
    else:
        st.success("OK: no hay 'name' duplicados (validación básica).")

    st.info("Recomendación: evita espacios, acentos o símbolos raros en 'name'. Usa snake_case.")



