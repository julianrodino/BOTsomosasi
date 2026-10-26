"""Modo web: Rita servida en una página, para hablarle desde el celular o la compu del estudio.

El navegador escucha (con su propio reconocimiento de voz o grabando para que Whisper
transcriba acá) y manda el texto. El servidor piensa con el mismo cerebro de la consola
y devuelve la respuesta por streaming (server-sent events): cada frase sale como texto
apenas se cierra y, en cuanto edge-tts la sintetiza, como audio MP3. Así la página
empieza a hablar con la primera frase mientras Claude sigue escribiendo.

La clave de Anthropic nunca sale de esta máquina: la página solo habla con este servidor.
El acceso se protege con un código (RITA_CODIGO) verificado acá, no en el navegador.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import queue
import secrets
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Iterator

import anthropic
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from .config import Ajustes
from .voz import sintetizar_mp3

PAGINA = Path(__file__).resolve().parent / "estatico" / "index.html"
COOKIE = "rita"
DIAS_COOKIE = 30

# Sufijo de archivo según lo que graba cada navegador, para que PyAV sepa decodificarlo.
_SUFIJOS = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".mp4",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}


def _sse(evento: str, datos: dict | None) -> bytes:
    cuerpo = json.dumps(datos or {}, ensure_ascii=False)
    return f"event: {evento}\ndata: {cuerpo}\n\n".encode("utf-8")


def _explicar(e: Exception) -> str:
    """Lo que la página muestra (y Rita dice) cuando Claude falla."""
    if isinstance(e, anthropic.AuthenticationError):
        return "La ANTHROPIC_API_KEY es inválida. Revisá el .env del servidor."
    if isinstance(e, TypeError) and "authentication" in str(e).lower():
        return "Falta la ANTHROPIC_API_KEY en el .env del servidor."
    if isinstance(e, anthropic.RateLimitError):
        return "Me saturaron, dame un respiro y preguntame de nuevo."
    if isinstance(e, (anthropic.APIConnectionError, anthropic.APIStatusError)):
        return "Se me cortó la conexión, repetime eso."
    return f"Algo falló: {e}"


def _ip_local() -> str | None:
    """La IP de esta máquina en la red local, para mostrar la URL que sirve desde el celular."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def crear_app(
    ajustes: Ajustes,
    cerebro,
    codigo: str,
    oido=None,
    registro=None,
    sintetizar: Callable[[str], bytes] | None = None,
) -> Starlette:
    """Arma la aplicación. `cerebro`, `oido`, `registro` y `sintetizar` se inyectan
    para poder probarla sin API, sin Whisper y sin internet."""

    # La cookie es un derivado del código, no el código: así sobrevive a reinicios del
    # servidor (mientras el código sea el mismo) y no revela el código si se filtra.
    token = hashlib.sha256(f"rita-web:{codigo.lower()}".encode("utf-8")).hexdigest()
    ocupada = threading.Lock()  # una charla a la vez: el historial del cerebro es uno solo

    if sintetizar is None:

        def sintetizar(frase: str) -> bytes:
            return asyncio.run(sintetizar_mp3(frase, ajustes.voz, ajustes.velocidad_voz))

    def autorizado(request: Request) -> bool:
        return secrets.compare_digest(request.cookies.get(COOKIE, ""), token)

    def rechazo() -> JSONResponse:
        return JSONResponse({"error": "Hace falta el código de acceso."}, status_code=401)

    async def pagina(request: Request) -> Response:
        return FileResponse(PAGINA, headers={"Cache-Control": "no-store"})

    async def entrar(request: Request) -> Response:
        try:
            datos = await request.json()
        except Exception:
            datos = {}
        intento = str(datos.get("codigo", "")).strip()
        if not intento or not secrets.compare_digest(intento.lower(), codigo.lower()):
            return JSONResponse({"ok": False, "error": "Ese código no es. Pedíselo a la producción."}, status_code=403)
        resp = JSONResponse({"ok": True})
        resp.set_cookie(COOKIE, token, httponly=True, samesite="lax", max_age=DIAS_COOKIE * 24 * 3600)
        return resp

    async def estado(request: Request) -> Response:
        if not autorizado(request):
            return rechazo()
        return JSONResponse(
            {
                "ok": True,
                "modelo": ajustes.modelo,
                "voz": ajustes.voz,
                "whisper": oido is not None,
                "ocupada": ocupada.locked(),
            }
        )

    def _eventos(texto: str) -> Iterator[bytes]:
        """Corre el cerebro y la voz en hilos y va emitiendo eventos a medida que llegan.

        Eventos: `frase` (texto, apenas se cierra), `audio` (MP3 en base64, o null si la
        síntesis falló y el navegador tiene que leerla con su propia voz), `fin` (respuesta
        completa), `error`, y `listo` cuando no queda nada más por mandar.
        """
        cola: queue.Queue = queue.Queue()
        por_sintetizar: queue.Queue = queue.Queue()
        n = 0

        def al_recibir_frase(frase: str) -> None:
            nonlocal n
            n += 1
            cola.put(("frase", {"n": n, "texto": frase}))
            por_sintetizar.put((n, frase))

        def pensar() -> None:
            inicio = time.monotonic()
            try:
                respuesta = cerebro.responder(texto, al_recibir_frase)
                segundos = time.monotonic() - inicio
                if registro is not None:
                    registro.anotar(texto, respuesta, segundos=segundos)
                cola.put(("fin", {"texto": respuesta, "segundos": round(segundos, 1)}))
            except Exception as e:  # la página tiene que enterarse de cualquier falla
                print(f"[web] el cerebro falló: {e!r}", file=sys.stderr)
                cola.put(("error", {"mensaje": _explicar(e)}))
            finally:
                por_sintetizar.put(None)
                ocupada.release()

        def hablar() -> None:
            while True:
                item = por_sintetizar.get()
                if item is None:
                    cola.put(("voz_lista", None))
                    return
                num, frase = item
                try:
                    mp3 = base64.b64encode(sintetizar(frase)).decode("ascii")
                except Exception as e:  # sin internet, voz inexistente: que lea el navegador
                    print(f"[web] edge-tts falló ({e}); la frase la lee el navegador.", file=sys.stderr)
                    mp3 = None
                cola.put(("audio", {"n": num, "mp3": mp3}))

        threading.Thread(target=pensar, daemon=True).start()
        threading.Thread(target=hablar, daemon=True).start()

        falta_cerebro, falta_voz = True, True
        while falta_cerebro or falta_voz:
            tipo, datos = cola.get()
            if tipo == "voz_lista":
                falta_voz = False
                continue
            if tipo in ("fin", "error"):
                falta_cerebro = False
            yield _sse(tipo, datos)
        yield _sse("listo", {})

    async def preguntar(request: Request) -> Response:
        if not autorizado(request):
            return rechazo()
        try:
            datos = await request.json()
        except Exception:
            datos = {}
        texto = str(datos.get("texto", "")).strip()
        if not texto:
            return JSONResponse({"error": "No llegó ninguna pregunta."}, status_code=400)
        if not ocupada.acquire(blocking=False):
            return JSONResponse({"error": "Rita todavía está contestando la anterior."}, status_code=409)
        # El candado lo suelta el hilo del cerebro cuando termina, aunque la página corte.
        return StreamingResponse(
            _eventos(texto),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    async def transcribir(request: Request) -> Response:
        if not autorizado(request):
            return rechazo()
        if oido is None:
            return JSONResponse({"error": "Whisper no está habilitado en el servidor."}, status_code=501)
        cuerpo = await request.body()
        if len(cuerpo) < 500:
            return JSONResponse({"texto": ""})
        tipo = request.headers.get("content-type", "").split(";")[0].strip().lower()
        sufijo = _SUFIJOS.get(tipo, ".webm")

        def trabajo() -> str:
            from faster_whisper.audio import decode_audio

            with tempfile.NamedTemporaryFile(suffix=sufijo) as f:
                f.write(cuerpo)
                f.flush()
                audio = decode_audio(f.name, sampling_rate=16_000)
            return oido.transcribir(audio)

        try:
            texto = await run_in_threadpool(trabajo)
        except Exception as e:
            print(f"[web] no pude transcribir: {e!r}", file=sys.stderr)
            return JSONResponse({"error": "No pude entender el audio."}, status_code=422)
        return JSONResponse({"texto": texto})

    async def olvidar(request: Request) -> Response:
        if not autorizado(request):
            return rechazo()
        cerebro.olvidar()
        return JSONResponse({"ok": True})

    async def cortar(request: Request) -> Response:
        if not autorizado(request):
            return rechazo()
        if hasattr(cerebro, "cortar"):
            cerebro.cortar()
        return JSONResponse({"ok": True})

    return Starlette(
        routes=[
            Route("/", pagina),
            Route("/api/entrar", entrar, methods=["POST"]),
            Route("/api/estado", estado),
            Route("/api/preguntar", preguntar, methods=["POST"]),
            Route("/api/transcribir", transcribir, methods=["POST"]),
            Route("/api/olvidar", olvidar, methods=["POST"]),
            Route("/api/cortar", cortar, methods=["POST"]),
        ]
    )


def servir(ajustes: Ajustes, cerebro, registro=None, oido=None, puerto: int | None = None) -> int:
    """Levanta el servidor y muestra las URLs y el código de acceso."""
    import uvicorn

    puerto = puerto or ajustes.puerto_web
    codigo = ajustes.codigo_web or secrets.token_hex(3)
    if oido is not None:
        # Whisper tarda unos segundos en cargar: mejor ahora que en la primera pregunta.
        threading.Thread(target=oido.preparar, daemon=True).start()

    app = crear_app(ajustes, cerebro, codigo, oido=oido, registro=registro)

    print(f"  En esta compu:   http://localhost:{puerto}")
    ip = _ip_local()
    if ip:
        print(f"  En la red local: http://{ip}:{puerto}  (solo texto; el micrófono pide HTTPS, ver README)")
    print(f"  Código de acceso: {codigo}" + ("" if ajustes.codigo_web else "  (fijalo con RITA_CODIGO en .env)"))
    print("  Ctrl+C para salir.\n")

    uvicorn.run(app, host="0.0.0.0", port=puerto, log_level="warning")
    return 0
