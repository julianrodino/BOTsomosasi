"""Registro de lo que pasó al aire: una línea JSON por intervención, un archivo por día."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import RAIZ
from .prompt import ZONA_BA

CARPETA = RAIZ / "logs"


class Registro:
    def __init__(self, carpeta: Path = CARPETA, activo: bool = True):
        self.carpeta = carpeta
        self.activo = activo
        if activo:
            self.carpeta.mkdir(exist_ok=True)

    @property
    def archivo(self) -> Path:
        return self.carpeta / f"{datetime.now(ZONA_BA):%Y-%m-%d}.jsonl"

    def anotar(self, dicho: str, respuesta: str, segundos: float | None = None) -> None:
        if not self.activo:
            return
        fila = {
            "hora": datetime.now(ZONA_BA).isoformat(timespec="seconds"),
            "piso": dicho,
            "rita": respuesta,
        }
        if segundos is not None:
            fila["segundos"] = round(segundos, 1)
        with open(self.archivo, "a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
