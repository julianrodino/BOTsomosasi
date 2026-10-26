"""Configuración: variables de entorno (.env) y datos del programa (YAML)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent

load_dotenv(RAIZ / ".env")


def _porcentaje(valor: str, defecto: float) -> float:
    """Acepta "3%" o "0.03" y devuelve 0.03."""
    valor = (valor or "").strip()
    if not valor:
        return defecto
    try:
        if valor.endswith("%"):
            return float(valor[:-1]) / 100
        return float(valor)
    except ValueError:
        return defecto


@dataclass
class Ajustes:
    # Cerebro
    modelo: str = field(default_factory=lambda: os.getenv("RITA_MODELO", "claude-opus-5-5"))
    esfuerzo: str = field(default_factory=lambda: os.getenv("RITA_ESFUERZO", "low"))
    max_busquedas: int = field(default_factory=lambda: int(os.getenv("RITA_MAX_BUSQUEDAS", "3")))

    # Voz (edge-tts)
    voz: str = field(default_factory=lambda: os.getenv("RITA_VOZ", "es-AR-ElenaNeural"))
    velocidad_voz: str = field(default_factory=lambda: os.getenv("RITA_VELOCIDAD_VOZ", "+8%"))

    # Oído (faster-whisper + micrófono)
    whisper: str = field(default_factory=lambda: os.getenv("RITA_WHISPER", "small"))
    umbral: float = field(default_factory=lambda: _porcentaje(os.getenv("RITA_UMBRAL", "3%"), 0.03))
    microfono: str | None = field(default_factory=lambda: os.getenv("RITA_MIC") or None)
    silencio_corte: float = field(default_factory=lambda: float(os.getenv("RITA_SILENCIO", "1.0")))

    # Archivos
    prompt_md: Path = RAIZ / "prompts" / "rita.md"
    programa_yaml: Path = RAIZ / "config" / "programa.yaml"
    modelos_dir: Path = RAIZ / "modelos"


def cargar_programa(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f) or {}
    if "programa" not in datos:
        raise ValueError(f"{ruta} no tiene la sección 'programa'")
    return datos
