"""Utilidades de texto: partir en frases mientras llega el stream y limpiar para la voz."""

from __future__ import annotations

import re
from typing import Callable

_FIN_FRASE = re.compile(r"[.!?…]+[\"”»)]?\s+")
_URL = re.compile(r"https?://\S+|www\.\S+")
_MARCAS = re.compile(r"[*_`#>|]+")
_VINETAS = re.compile(r"^\s*(?:[-•]|\d+[.)])\s+", re.MULTILINE)
_ESPACIOS = re.compile(r"[ \t]+")


def limpiar_para_voz(texto: str) -> str:
    """Saca lo que no se puede leer en voz alta: URLs, marcas de markdown, viñetas."""
    texto = _URL.sub("", texto)
    texto = _VINETAS.sub("", texto)
    texto = _MARCAS.sub("", texto)
    texto = _ESPACIOS.sub(" ", texto)
    texto = re.sub(r"\n{2,}", "\n", texto)
    return texto.strip()


class Segmentador:
    """Recibe pedacitos de texto y emite frases completas apenas se cierran.

    Así la voz arranca con la primera oración mientras el modelo sigue escribiendo.
    """

    def __init__(self, emitir: Callable[[str], None], minimo: int = 25):
        self.emitir = emitir
        self.minimo = minimo
        self._buffer = ""

    def alimentar(self, trozo: str) -> None:
        self._buffer += trozo
        while True:
            m = _FIN_FRASE.search(self._buffer)
            if not m or m.end() < self.minimo:
                # Frase demasiado corta ("Ok. " / "Sí. "): esperar a que se junte con la siguiente.
                if m and m.end() < self.minimo and _FIN_FRASE.search(self._buffer, m.end()):
                    pass  # hay otra frase después, cortar en esa
                else:
                    return
                m = _FIN_FRASE.search(self._buffer, m.end())
                if not m:
                    return
            frase, self._buffer = self._buffer[: m.end()], self._buffer[m.end():]
            frase = limpiar_para_voz(frase)
            if frase:
                self.emitir(frase)

    def cerrar(self) -> None:
        resto = limpiar_para_voz(self._buffer)
        self._buffer = ""
        if resto:
            self.emitir(resto)
