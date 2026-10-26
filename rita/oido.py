"""El oído de Rita: graba del micrófono y transcribe con Whisper local."""

from __future__ import annotations

import queue
import sys
import time
from typing import Callable

import numpy as np

from .config import Ajustes

FRECUENCIA = 16_000  # Hz, lo que espera Whisper
BLOQUE = int(FRECUENCIA * 0.03)  # 30 ms por bloque
MAX_SEGUNDOS = 30
PRE_ROLL = 0.3  # segundos de audio previos al arranque de voz que se conservan

# Frases que Whisper alucina cuando hay silencio.
_ALUCINACIONES = (
    "subtítulos realizados por",
    "subtitulado por",
    "gracias por ver",
    "amara.org",
)


def _buscar_dispositivo(nombre: str | None):
    if nombre is None:
        return None
    if nombre.isdigit():
        return int(nombre)
    import sounddevice as sd

    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and nombre.lower() in d["name"].lower():
            return i
    raise ValueError(f"No encuentro un micrófono que se llame '{nombre}'. Probá `rita --dispositivos`.")


def listar_dispositivos() -> str:
    import sounddevice as sd

    return str(sd.query_devices())


class Oido:
    def __init__(self, ajustes: Ajustes):
        self.ajustes = ajustes
        self._modelo = None
        self._dispositivo = _buscar_dispositivo(ajustes.microfono)

    # ---------- transcripción ----------

    def preparar(self) -> None:
        """Carga Whisper (y lo descarga la primera vez). Conviene hacerlo antes de salir al aire."""
        if self._modelo is not None:
            return
        from faster_whisper import WhisperModel

        print(f"[oído] cargando Whisper '{self.ajustes.whisper}'...", file=sys.stderr)
        self._modelo = WhisperModel(
            self.ajustes.whisper,
            device="cpu",
            compute_type="int8",
            download_root=str(self.ajustes.modelos_dir),
        )

    def transcribir(self, audio: np.ndarray) -> str:
        if audio.size < FRECUENCIA * 0.3:
            return ""
        self.preparar()
        segmentos, _info = self._modelo.transcribe(
            audio,
            language="es",
            beam_size=2,
            vad_filter=True,
            initial_prompt="Programa de radio en Buenos Aires. Charla informal, voseo.",
        )
        texto = " ".join(s.text.strip() for s in segmentos).strip()
        if any(a in texto.lower() for a in _ALUCINACIONES):
            return ""
        return texto

    # ---------- grabación ----------

    def _stream(self, cola: queue.Queue):
        import sounddevice as sd

        def callback(indata, frames, tiempo, status):
            cola.put(indata[:, 0].copy())

        return sd.InputStream(
            samplerate=FRECUENCIA,
            channels=1,
            dtype="float32",
            blocksize=BLOQUE,
            device=self._dispositivo,
            callback=callback,
        )

    def grabar_pulsando(self, antes_de_grabar: Callable[[], None] | None = None) -> np.ndarray:
        """Push-to-talk por teclado: Enter para empezar a hablar, Enter para cortar."""
        input("\n[Enter] para hablarle a Rita... ")
        if antes_de_grabar:
            antes_de_grabar()
        cola: queue.Queue = queue.Queue()
        with self._stream(cola):
            input("🎙  grabando. [Enter] cuando termines. ")
        trozos = []
        while not cola.empty():
            trozos.append(cola.get_nowait())
        return np.concatenate(trozos) if trozos else np.zeros(0, dtype="float32")

    def grabar_automatico(self, al_detectar_voz: Callable[[], None] | None = None) -> np.ndarray:
        """Espera a que alguien hable (energía por encima del umbral) y corta tras un silencio."""
        cola: queue.Queue = queue.Queue()
        umbral = self.ajustes.umbral
        bloques_silencio_corte = int(self.ajustes.silencio_corte / 0.03)
        pre_roll_max = int(PRE_ROLL / 0.03)

        previos: list[np.ndarray] = []
        grabado: list[np.ndarray] = []
        hablando = False
        silencio = 0
        inicio = None

        print("\n🎧 escuchando (hablá cuando quieras)...", end=" ", flush=True)
        with self._stream(cola):
            while True:
                bloque = cola.get()
                rms = float(np.sqrt(np.mean(bloque**2)))
                if not hablando:
                    previos.append(bloque)
                    if len(previos) > pre_roll_max:
                        previos.pop(0)
                    if rms > umbral:
                        hablando = True
                        inicio = time.monotonic()
                        grabado.extend(previos)
                        print("🎙 ", end="", flush=True)
                        if al_detectar_voz:
                            al_detectar_voz()
                    continue

                grabado.append(bloque)
                silencio = silencio + 1 if rms <= umbral else 0
                if silencio >= bloques_silencio_corte or time.monotonic() - inicio > MAX_SEGUNDOS:
                    break
        print()
        return np.concatenate(grabado)
