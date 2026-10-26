"""El cerebro de Rita: Claude con búsqueda web, memoria de la charla y streaming por frases."""

from __future__ import annotations

from typing import Callable

import anthropic

from .config import Ajustes
from .prompt import bloque_fecha
from .texto import Segmentador

# Si Claude declina por política, lo que Rita dice al aire en vez de quedarse muda.
FRASE_SI_DECLINA = "Eso no lo voy a contestar al aire, sigamos con otra cosa."

# Cuántos mensajes de historial se conservan (pares usuario/Rita). Más allá de esto se
# recortan los más viejos. Se guarda solo texto, así el historial es liviano y estable.
MAX_MENSAJES = 40


class Cerebro:
    def __init__(self, ajustes: Ajustes, system: str):
        self.ajustes = ajustes
        self.system = system
        self.client = anthropic.Anthropic()
        self.historial: list[dict] = []
        self.tools = [
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": ajustes.max_busquedas,
                "user_location": {
                    "type": "approximate",
                    "city": "Buenos Aires",
                    "country": "AR",
                    "timezone": "America/Argentina/Buenos_Aires",
                },
            }
        ]

    def olvidar(self) -> None:
        self.historial.clear()

    def responder(self, dicho: str, al_recibir_frase: Callable[[str], None] | None = None) -> str:
        """Manda lo que dijeron en el piso y devuelve la respuesta completa de Rita.

        Mientras llega el stream, cada frase terminada se pasa a `al_recibir_frase`
        (ahí se engancha la voz), así Rita empieza a hablar antes de terminar de pensar.
        """
        self.historial.append({"role": "user", "content": dicho})
        self._recortar()

        partes: list[str] = []

        def emitir(frase: str) -> None:
            partes.append(frase)
            if al_recibir_frase:
                al_recibir_frase(frase)

        segmentador = Segmentador(emitir)
        mensajes = list(self.historial)
        system = [
            {"type": "text", "text": self.system, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": bloque_fecha()},
        ]

        final = None
        # Con herramientas del servidor el turno puede pausarse (pause_turn): se reenvía
        # tal cual y el servidor retoma donde quedó. Tope de reintentos por las dudas.
        for _ in range(4):
            with self.client.beta.messages.stream(
                model=self.ajustes.modelo,
                max_tokens=8000,
                system=system,
                messages=mensajes,
                tools=self.tools,
                output_config={"effort": self.ajustes.esfuerzo},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                for trozo in stream.text_stream:
                    segmentador.alimentar(trozo)
                final = stream.get_final_message()

            if final.stop_reason == "pause_turn":
                mensajes.append({"role": "assistant", "content": final.content})
                continue
            break

        segmentador.cerrar()

        if final is not None and final.stop_reason == "refusal" and not partes:
            emitir(FRASE_SI_DECLINA)

        respuesta = " ".join(partes).strip()
        if respuesta:
            self.historial.append({"role": "assistant", "content": respuesta})
        else:
            # Sin respuesta no dejamos un turno de usuario colgado.
            self.historial.pop()
        return respuesta

    def _recortar(self) -> None:
        if len(self.historial) <= MAX_MENSAJES:
            return
        sobra = len(self.historial) - MAX_MENSAJES
        del self.historial[:sobra]
        # El historial tiene que arrancar con un turno de usuario.
        while self.historial and self.historial[0]["role"] != "user":
            del self.historial[0]
