"""La voz de Rita: sintetiza con edge-tts y reproduce, en cadena, frase por frase.

Dos hilos: uno sintetiza la frase N+1 mientras el otro reproduce la frase N.
Así la voz no se corta entre oraciones y arranca en cuanto llega la primera.
"""

from __future__ import annotations

import asyncio
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from .config import Ajustes

_FIN = object()


def _reproductor() -> list[str] | None:
    if shutil.which("afplay"):
        return ["afplay"]
    if shutil.which("ffplay"):
        return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
    if shutil.which("mpv"):
        return ["mpv", "--no-video", "--really-quiet"]
    return None


class Locutora:
    def __init__(self, ajustes: Ajustes, muda: bool = False):
        self.ajustes = ajustes
        self.muda = muda
        self._dir = Path(tempfile.mkdtemp(prefix="rita-voz-"))
        self._reproductor = _reproductor()
        if not muda and self._reproductor is None:
            print("[voz] no encuentro afplay, ffplay ni mpv: Rita va a hablar solo por texto.", file=sys.stderr)
            self.muda = True

        self._frases: queue.Queue = queue.Queue()
        self._archivos: queue.Queue = queue.Queue()
        self._pendientes = 0
        self._cond = threading.Condition()
        self._proceso: subprocess.Popen | None = None
        self._n = 0

        self._hilo_sintesis = threading.Thread(target=self._sintetizar_loop, daemon=True)
        self._hilo_audio = threading.Thread(target=self._reproducir_loop, daemon=True)
        self._hilo_sintesis.start()
        self._hilo_audio.start()

    # ---------- API ----------

    def decir(self, frase: str) -> None:
        if self.muda or not frase.strip():
            return
        with self._cond:
            self._pendientes += 1
        self._frases.put(frase)

    def esperar(self) -> None:
        """Bloquea hasta que Rita terminó de decir todo lo encolado."""
        with self._cond:
            self._cond.wait_for(lambda: self._pendientes == 0)

    def callar(self) -> None:
        """Interrumpe: vacía lo pendiente y corta lo que se esté reproduciendo."""
        vaciadas = 0
        for cola in (self._frases, self._archivos):
            while True:
                try:
                    item = cola.get_nowait()
                except queue.Empty:
                    break
                if item is not _FIN:
                    vaciadas += 1
                    if isinstance(item, Path):
                        item.unlink(missing_ok=True)
        with self._cond:
            self._pendientes = max(0, self._pendientes - vaciadas)
            self._cond.notify_all()
        proc = self._proceso
        if proc and proc.poll() is None:
            proc.terminate()

    def cerrar(self) -> None:
        self.callar()
        self._frases.put(_FIN)
        self._hilo_sintesis.join(timeout=2)
        self._hilo_audio.join(timeout=2)
        shutil.rmtree(self._dir, ignore_errors=True)

    # ---------- hilos ----------

    def _sintetizar_loop(self) -> None:
        while True:
            frase = self._frases.get()
            if frase is _FIN:
                self._archivos.put(_FIN)
                return
            archivo = self._sintetizar(frase)
            if archivo is None:
                self._terminada()
            else:
                self._archivos.put(archivo)

    def _reproducir_loop(self) -> None:
        while True:
            archivo = self._archivos.get()
            if archivo is _FIN:
                return
            try:
                self._proceso = subprocess.Popen(
                    [*self._reproductor, str(archivo)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._proceso.wait()
            finally:
                self._proceso = None
                archivo.unlink(missing_ok=True)
                self._terminada()

    def _terminada(self) -> None:
        with self._cond:
            self._pendientes = max(0, self._pendientes - 1)
            self._cond.notify_all()

    # ---------- síntesis ----------

    def _sintetizar(self, frase: str) -> Path | None:
        self._n += 1
        destino = self._dir / f"{self._n:05d}.mp3"
        try:
            asyncio.run(self._edge(frase, destino))
            return destino
        except Exception as e:  # sin internet, voz inexistente, etc.
            print(f"[voz] edge-tts falló ({e}); uso la voz del sistema.", file=sys.stderr)
            return self._say(frase, destino.with_suffix(".aiff"))

    async def _edge(self, frase: str, destino: Path) -> None:
        import edge_tts

        com = edge_tts.Communicate(frase, voice=self.ajustes.voz, rate=self.ajustes.velocidad_voz)
        await com.save(str(destino))

    @staticmethod
    def _say(frase: str, destino: Path) -> Path | None:
        if not shutil.which("say"):
            return None
        try:
            subprocess.run(["say", "-v", "Mónica", "-o", str(destino), frase], check=True, capture_output=True)
            return destino
        except subprocess.CalledProcessError:
            return None
