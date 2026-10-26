# CLAUDE.md · contexto del proyecto Rita

Leé esto entero antes de tocar nada. Es el estado real del proyecto al 2026-10-26.

## Qué es

**Rita** es la compañera de piso con inteligencia artificial de **SomosAsi**, un programa de radio y stream en vivo. Está al aire: los conductores le hablan por micrófono, ella busca en internet lo que haga falta y contesta por voz, con voz de mujer y en español rioplatense. Es un personaje (porteña, treinta y pico, cabeza de productora de radio, irónica, memoriosa), no un asistente.

Dueño del proyecto: Julián Rodino. Repo: https://github.com/julianrodino/BOTsomosasi (rama `main`, CI con pytest en GitHub Actions).

## Cómo funciona (pipeline)

```
micrófono ─► Whisper local ─► Claude + web_search ─► edge-tts ─► parlantes
             rita/oido.py      rita/cerebro.py        rita/voz.py
```

1. **Oído** (`rita/oido.py`): graba con `sounddevice` a 16 kHz. Dos modos: push-to-talk (Enter / Enter) o automático (energía RMS por encima de `RITA_UMBRAL`, corta tras `RITA_SILENCIO` segundos). Transcribe con `faster-whisper` en CPU (`int8`), modelo `small` por defecto, descargado a `modelos/` (gitignored). Filtra las alucinaciones típicas de Whisper en silencio.
2. **Cerebro** (`rita/cerebro.py`): Claude vía SDK oficial `anthropic` (2.x). Modelo `claude-opus-5-5`, `output_config.effort="low"` por latencia al aire. Herramienta del servidor `web_search_20260209` con `user_location` en Buenos Aires y `max_uses=3`. `fallbacks="default"` con beta `server-side-fallback-2026-07-01` para que una respuesta declinada por política se reintente sola en otro modelo. Maneja `pause_turn` reenviando el turno y `refusal` con una frase fija. Respuesta en streaming: cada frase completa se pasa a un callback para que la voz arranque antes de que termine el texto.
3. **Voz** (`rita/voz.py`): `edge-tts`, voz `es-AR-ElenaNeural`, velocidad `+8%`. Dos hilos: uno sintetiza la frase N+1 mientras el otro reproduce la N con `afplay` (macOS), `ffplay` o `mpv`. Si edge-tts falla, cae a la voz `say` del sistema. `callar()` interrumpe todo lo pendiente.
4. **Texto** (`rita/texto.py`): `Segmentador` parte el stream por frases (mínimo 25 caracteres para no cortar "Sí." suelto); `limpiar_para_voz` saca markdown, URLs y viñetas.
5. **Registro** (`rita/registro.py`): una línea JSON por intervención en `logs/AAAA-MM-DD.jsonl` (hora, lo que dijo el piso, respuesta, segundos). `logs/` está gitignored.
6. **Web** (`rita/web.py` + `rita/estatico/index.html`): `uv run -m rita --web` sirve una página (Starlette + uvicorn) para hablarle desde el celular o la compu como a un asistente de voz. Mismo `Cerebro` y mismo `Registro` que la consola. El navegador escucha (Web Speech API si la tiene; si no, graba y `POST /api/transcribir` lo pasa por Whisper vía `faster_whisper.audio.decode_audio`) y manda el texto a `POST /api/preguntar`, que responde por server-sent events: `frase` (texto apenas se cierra), `audio` (MP3 de edge-tts en base64, o `null` si falló y entonces lo lee la voz del navegador), `fin`, `error`, `listo`. Un candado permite una charla a la vez (409 si está ocupada); lo suelta el hilo del cerebro al terminar, aunque la página corte. Acceso por código (`RITA_CODIGO`, o uno aleatorio impreso al arrancar) verificado en el servidor, que deja una cookie. La página tiene "Manos libres" (vuelve a escuchar sola al terminar de hablar). El micrófono del navegador necesita HTTPS o localhost: para el celular, túnel de Cloudflare (ver README). Tests en `tests/test_web.py` con cerebro y voz inyectados.
7. **Prompt** (`rita/prompt.py` + `prompts/rita.md` + `config/programa.yaml`): la plantilla tiene variables `{{asi}}` que se completan con el YAML del programa. La fecha y hora de Buenos Aires van en un **segundo bloque** del system prompt, separado del bloque grande que lleva `cache_control`, para no romper el caché.

## Cómo se corre

Siempre parado en la raíz del repo y **siempre con `-m`**:

```bash
uv sync                                  # entorno (Python 3.12, lo maneja uv)
uv run -m rita --texto --mudo            # probar el personaje sin micrófono ni audio
uv run -m rita --texto                   # escribirle, responde por voz
uv run -m rita                           # modo radio: Enter para hablar, Enter para cortar
uv run -m rita --auto                    # detección automática de voz
uv run -m rita --web                     # página para hablarle desde el celular (--sin-whisper para no cargar Whisper)
uv run -m rita --prompt                  # ver el system prompt armado
uv run -m rita --probar-voz "Hola"       # probar la voz
uv run -m rita --dispositivos            # listar micrófonos
uv run pytest -q                         # tests (no llaman a la API)
```

Configuración por variables de entorno en `.env` (documentadas en `.env.example`): `ANTHROPIC_API_KEY` (obligatoria), `RITA_MODELO`, `RITA_ESFUERZO`, `RITA_MAX_BUSQUEDAS`, `RITA_VOZ`, `RITA_VELOCIDAD_VOZ`, `RITA_WHISPER`, `RITA_MIC`, `RITA_UMBRAL`, `RITA_SILENCIO`, `RITA_CODIGO`, `RITA_PUERTO`.

## Decisiones técnicas y por qué (no las deshagas sin motivo)

- **Python 3.12 fijo** (`.python-version`, `requires-python = ">=3.12,<3.13"`). El Python de Homebrew de la máquina es 3.15 y `faster-whisper`/`ctranslate2`/`onnxruntime` no tienen wheels para 3.15. No subir la versión.
- **`av>=11,<16`** pineado: `faster-whisper` 1.2 rompe al decodificar archivos con PyAV 16+ (`metadata_errors` desconocido). En producción pasamos arrays de numpy, pero el pin evita sorpresas.
- **`uv run -m rita` en vez de `uv run rita`.** En esta Mac algo vuelve a marcar como ocultos (`UF_HIDDEN`) los archivos `.pth` dentro de `.venv` a los pocos segundos, y Python 3.12 saltea los `.pth` ocultos. El atajo `rita` que instala uv (editable, vía `.pth`) falla con `No module named 'rita'`. `python -m rita` carga el paquete desde la raíz del repo y no depende del `.pth`. Existe `rita/__main__.py` para eso. No pasar a instalación no editable: `rita/config.py` calcula la raíz del repo a partir de `rita/__init__.py` para encontrar `prompts/` y `config/`.
- **Historial solo de texto.** En `cerebro.py` se guarda la respuesta de Rita como texto plano, no `response.content` completo. Así no se reenvían bloques de thinking ni de búsqueda, el historial es liviano, el prefijo de caché es estable y no hay problemas con la verificación de thinking preservado al recortar turnos viejos. Dentro de un mismo turno con `pause_turn` sí se reenvía el `content` completo.
- **Claude hace de cerebro y de buscador.** No agregar otra API de búsqueda: `web_search` del servidor alcanza y es una sola clave. Antes de este repo hubo un intento con Gemini (clave gratis) y edge-tts; se descartó. Si hay que bajar costos, el camino es `RITA_ESFUERZO`/`RITA_MODELO` por entorno, no cambiar de proveedor.
- **Streaming por frases** es lo que hace que la latencia sea tolerable al aire (uno o dos segundos hasta la primera frase). Cualquier cambio en `cerebro.responder` o en `Segmentador` tiene que mantener eso.
- **Todo en castellano**: código, comentarios, mensajes, commits, README. Rita habla rioplatense con voseo; su salida es texto corrido sin formato porque se lee en voz alta.

## Estado actual (2026-10-26)

Hecho y verificado:
- Tests: 18 pasan local (11 originales + 7 del modo web).
- Modo web: la página se probó en el navegador con un cerebro falso y la voz real de edge-tts (puerta, streaming por frases, audio en orden, cortar, nueva charla). No se probó todavía con Claude real ni el micrófono desde un celular por túnel.
- Hubo una versión de Rita como artefacto de claude.ai: sin búsqueda, sin micrófono en la app de Claude, voces del navegador. El modo web la reemplaza; el personaje ahí es copia de `prompts/rita.md` y no se mantiene.
- Voz: edge-tts sintetiza bien; Whisper `tiny` transcribió esa misma voz sin errores (ida y vuelta completa).
- SDK: la forma del pedido a la API es aceptada (con clave falsa la API devolvió 401, no un error de parámetros).

**No verificado todavía: una conversación real con Claude.** Hace falta `ANTHROPIC_API_KEY` en `.env` (confirmar con `grep -c '^ANTHROPIC_API_KEY=' .env`, tiene que dar 1). Nunca imprimir ni pegar el valor de la clave.

Pendiente de completar: los corchetes de `config/programa.yaml` (horario, emisora, conductores, rasgos del piso, historia, público).

## Pendientes / ideas

- Primera prueba en vivo: `uv run -m rita --texto --mudo` con una pregunta estable ("¿quién inventó el bidet?") y una que obligue a buscar ("¿a cuánto está el dólar blue hoy?"). Revisar tono, largo (2 a 4 oraciones) y que no haya formato ni URLs. Después probar con voz y medir latencia en `logs/`.
- Entrada de audio desde la consola de la radio (hoy toma el micrófono del sistema; `RITA_MIC` elige el dispositivo).
- Interrupción por voz mientras habla en modo push-to-talk (en `--auto` ya interrumpe al detectar voz).
- Afinar el prompt con lo que salga de los logs reales. El personaje vive en `prompts/rita.md`; los datos del programa en `config/programa.yaml`. No mezclar las dos cosas.

## Cosas que no hay que hacer

- No commitear `.env`, `logs/` ni `modelos/` (están en `.gitignore`).
- No cambiar el modelo, el `effort` o el pin de `av` sin decirlo explícitamente.
- No agregar formato (listas, negritas, emojis) a lo que dice Rita: se lee en voz alta.
- No hacer que Rita se presente como asistente ni use frases de relleno; el prompt ya lo prohíbe y es parte del personaje.
