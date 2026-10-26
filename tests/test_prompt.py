from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from rita.config import Ajustes, cargar_programa
from rita.prompt import bloque_fecha, construir_system, renderizar


def test_el_prompt_del_repo_se_arma_sin_variables_sueltas():
    system = construir_system(Ajustes())
    assert "{{" not in system
    assert "Sos Rita" in system
    assert "SomosAsi" in system


def test_renderizar_mete_los_datos_del_programa():
    programa = {
        "programa": {
            "nombre": "SomosAsi",
            "dias_y_horario": "lunes a viernes de 18 a 20",
            "emisora": "Radio X",
            "conductores": "Ana y Beto",
            "productor": "Caro",
            "tono": "relajado",
            "malas_palabras": True,
        },
        "secciones": ["la efeméride", "el dato inútil"],
        "piso": [{"nombre": "Ana", "rasgo": "la que pregunta"}, {"nombre": "Beto", "rasgo": "el que tira el chiste"}],
        "historia": "Empezó en 2020.\nVuelve el chiste del bidet.",
        "oyentes": "gente de 25 a 45",
    }
    texto = renderizar("{{nombre}} sale {{dias_y_horario}} por {{emisora}}. {{secciones}}. {{piso}}. {{historia}} {{registro}}", programa)
    assert texto.startswith("SomosAsi sale lunes a viernes de 18 a 20 por Radio X.")
    assert "la efeméride y el dato inútil" in texto
    assert "Ana es la que pregunta y Beto es el que tira el chiste" in texto
    assert "Empezó en 2020. Vuelve el chiste del bidet." in texto
    assert "se pueden decir malas palabras" in texto


def test_renderizar_falla_si_queda_una_variable_sin_completar():
    with pytest.raises(ValueError):
        renderizar("hola {{inexistente}}", {"programa": {}})


def test_cargar_programa_del_repo():
    datos = cargar_programa(Ajustes().programa_yaml)
    assert datos["programa"]["nombre"] == "SomosAsi"


def test_bloque_fecha_en_castellano_y_hora_de_buenos_aires():
    # 26 de octubre de 2026 a las 21:05 UTC es 18:05 en Buenos Aires (UTC-3), domingo.
    ahora = datetime(2026, 10, 26, 21, 5, tzinfo=ZoneInfo("UTC"))
    assert bloque_fecha(ahora) == "Ahora en Buenos Aires son las 18:05 del lunes 26 de octubre de 2026."
