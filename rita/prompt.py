"""Arma el system prompt de Rita a partir de la plantilla y los datos del programa."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Ajustes, cargar_programa

ZONA_BA = ZoneInfo("America/Argentina/Buenos_Aires")

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _lista_hablada(items: list[str]) -> str:
    items = [i.strip() for i in items if i and i.strip()]
    if not items:
        return "ninguna por ahora"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " y " + items[-1]


def variables(programa: dict) -> dict[str, str]:
    """Convierte el YAML del programa en las variables de la plantilla."""
    p = programa.get("programa", {})
    piso = programa.get("piso") or []
    piso_txt = _lista_hablada(
        [f"{c.get('nombre', '').strip()} es {c.get('rasgo', '').strip()}" for c in piso if c.get("nombre")]
    )
    if programa.get("programa", {}).get("malas_palabras"):
        registro = "en este programa se pueden decir malas palabras suaves al aire, con criterio."
    else:
        registro = "en este programa no se dicen malas palabras al aire; podés ser filosa sin putear."

    historia = (programa.get("historia") or "").strip().replace("\n", " ")
    return {
        "nombre": str(p.get("nombre", "SomosAsi")),
        "dias_y_horario": str(p.get("dias_y_horario", "")),
        "emisora": str(p.get("emisora", "")),
        "conductores": str(p.get("conductores", "")),
        "productor": str(p.get("productor", "")),
        "tono": str(p.get("tono", "")),
        "secciones": _lista_hablada([str(s) for s in programa.get("secciones") or []]),
        "piso": piso_txt,
        "historia": historia or "todavía no me contaron la historia del programa.",
        "oyentes": str(programa.get("oyentes", "")),
        "registro": registro,
    }


def renderizar(plantilla: str, programa: dict) -> str:
    texto = plantilla
    for clave, valor in variables(programa).items():
        texto = texto.replace("{{" + clave + "}}", valor)
    sobrantes = re.findall(r"{{\s*[\w]+\s*}}", texto)
    if sobrantes:
        raise ValueError(f"Quedaron variables sin completar en el prompt: {sobrantes}")
    return texto.strip()


def construir_system(ajustes: Ajustes) -> str:
    plantilla = ajustes.prompt_md.read_text(encoding="utf-8")
    programa = cargar_programa(ajustes.programa_yaml)
    return renderizar(plantilla, programa)


def bloque_fecha(ahora: datetime | None = None) -> str:
    """Texto corto con la fecha y hora actual en Buenos Aires. Va en un bloque aparte
    del system prompt para no romper el caché del bloque grande."""
    ahora = ahora or datetime.now(ZONA_BA)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=ZONA_BA)
    ahora = ahora.astimezone(ZONA_BA)
    return (
        f"Ahora en Buenos Aires son las {ahora.hour:02d}:{ahora.minute:02d} "
        f"del {DIAS[ahora.weekday()]} {ahora.day} de {MESES[ahora.month - 1]} de {ahora.year}."
    )
