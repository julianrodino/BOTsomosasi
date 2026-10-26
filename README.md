# Rita · la compañera de piso de SomosAsi

Rita es la inteligencia artificial del programa. Está al aire: le hablan por el micrófono, busca lo que haga falta en internet y contesta por voz, con voz de mujer y en rioplatense. Personalidad, reglas y tono están en [prompts/rita.md](prompts/rita.md); los datos del programa (horario, conductores, secciones, historia) en [config/programa.yaml](config/programa.yaml).

## Cómo funciona

```
micrófono ──► Whisper (local) ──► Claude + búsqueda web ──► edge-tts ──► parlantes
              "oído"              "cerebro"                 "voz"
```

- **Oído** ([rita/oido.py](rita/oido.py)): graba del micrófono y transcribe con `faster-whisper` en la compu, sin mandar audio a ningún lado.
- **Cerebro** ([rita/cerebro.py](rita/cerebro.py)): Claude con la herramienta de búsqueda web del servidor de Anthropic. Recibe la fecha y hora de Buenos Aires en cada mensaje y recuerda la charla del programa.
- **Voz** ([rita/voz.py](rita/voz.py)): la respuesta llega en streaming y se parte por frases; cada frase se sintetiza con `edge-tts` (voz `es-AR-ElenaNeural`) mientras se reproduce la anterior, así Rita empieza a hablar en uno o dos segundos. Si Rita dice "dame un segundo que lo busco", eso sale al aire mientras busca.

## Requisitos

- macOS (usa `afplay` para reproducir; en Linux sirve `ffplay` o `mpv`).
- [uv](https://docs.astral.sh/uv/). Python 3.12 lo instala uv solo.
- Una clave de API de Anthropic ([console.anthropic.com](https://console.anthropic.com)). Es la única clave: Claude hace de cerebro y de buscador.
- Internet para Claude y para la voz. Whisper corre local.

## Instalación

```bash
uv sync
```

```bash
cp .env.example .env
```

Pegá tu `ANTHROPIC_API_KEY` en `.env`. Después completá [config/programa.yaml](config/programa.yaml) con los datos reales del programa: todo lo que está entre corchetes.

Probá que la voz suene:

```bash
uv run -m rita --probar-voz "Hola, soy Rita, probando la voz del piso."
```

## Uso

| Comando | Qué hace |
|---|---|
| `uv run -m rita` | Modo radio: Enter para hablarle, Enter para cortar. Rita contesta por voz. |
| `uv run -m rita --auto` | Sin teclado: detecta cuando alguien habla y corta tras un silencio. Calibrar con `RITA_UMBRAL`. |
| `uv run -m rita --texto` | Escribirle en vez de hablarle. Sirve para probar el personaje sin micrófono. |
| `uv run -m rita --texto --mudo` | Solo texto, sin audio. Lo más barato para iterar el prompt. |
| `uv run -m rita --web` | Sirve una página para hablarle desde el celular o la compu, como a un asistente de voz. Ver [Modo web](#modo-web). |
| `uv run -m rita --prompt` | Imprime el system prompt ya armado con los datos del programa. |
| `uv run -m rita --dispositivos` | Lista los micrófonos disponibles. |
| `... --sin-registro` | No guarda la charla en `logs/`. |

La primera vez que arranca en modo voz descarga el modelo de Whisper a `modelos/` (unos 500 MB para `small`).

Mientras Rita habla, apretar Enter (o empezar a hablar, en `--auto`) la interrumpe.

Cada intervención queda anotada en `logs/AAAA-MM-DD.jsonl` (hora, lo que dijo el piso, lo que contestó Rita y cuánto tardó). Sirve para revisar el programa y para afinar el prompt.

## Modo web

```bash
uv run -m rita --web
```

Levanta un servidor en la Mac y muestra dos URLs y un código de acceso. Abrís la URL en Chrome o Safari, ponés el código y queda un botón grande: lo tocás, hablás, y Rita contesta por los parlantes del dispositivo con la misma voz argentina del modo consola. Con **Manos libres** prendido no hace falta tocar nada: termina de hablar y vuelve a escuchar sola. Tocar el botón mientras habla la corta. En la compu también sirven Espacio o Enter para hablar y Escape para cortar.

```
navegador ──► (reconocimiento del navegador, o Whisper acá) ──► Claude + búsqueda ──► edge-tts ──► navegador
```

- **El cerebro es el mismo** que en la consola ([rita/cerebro.py](rita/cerebro.py)): busca en internet, recuerda la charla, responde por frases en streaming. La página empieza a hablar con la primera frase.
- **Escuchar:** si el navegador tiene reconocimiento de voz (Chrome, Safari), lo usa, es instantáneo y se ve lo que entiende mientras hablás. Si no, graba y lo transcribe Whisper en la Mac. Con `--sin-whisper` no carga Whisper y queda solo el del navegador.
- **La clave de Anthropic no sale de la Mac.** El navegador solo habla con este servidor.
- **Acceso:** el código se verifica en el servidor. Fijalo con `RITA_CODIGO` en `.env`; si no, se genera uno nuevo en cada arranque y se imprime en la consola. Puerto con `RITA_PUERTO` o `--puerto` (8765 por defecto).
- Cada intervención queda en `logs/` igual que en la consola.

### Desde el celular: hace falta HTTPS

Los navegadores solo dan acceso al micrófono en páginas seguras: `localhost` en la propia Mac, o cualquier URL `https://`. La URL `http://192.168.x.x:8765` de la red local sirve para escribirle, pero no para hablarle. La forma más simple de tener HTTPS es un túnel de Cloudflare, gratis y sin cuenta:

```bash
brew install cloudflared
```

Con Rita corriendo en una terminal, en otra:

```bash
cloudflared tunnel --url http://localhost:8765
```

Imprime una URL `https://algo.trycloudflare.com`. Esa se abre en el celular (y se puede agregar a la pantalla de inicio). La URL cambia en cada arranque del túnel; el código de acceso es lo que protege a Rita, así que conviene fijar `RITA_CODIGO`.

Si en el estudio usan [Tailscale](https://tailscale.com), `tailscale serve 8765` da una URL https estable dentro de la red privada, sin exponer nada a internet.

## Ajustes

Todo se configura por variables de entorno en `.env`; están documentadas en [.env.example](.env.example). Las que más importan al aire:

- `RITA_ESFUERZO`: `low` es lo más rápido. Subirlo mejora respuestas largas pero agrega segundos de silencio.
- `RITA_WHISPER`: `small` es el equilibrio. `large-v3-turbo` entiende mejor con ruido de fondo pero tarda más en CPU.
- `RITA_UMBRAL` y `RITA_SILENCIO`: sensibilidad del modo automático.

## Editar a Rita

- El personaje vive en [prompts/rita.md](prompts/rita.md). Las variables `{{asi}}` se completan desde el YAML; el resto es texto libre.
- Para cambiar cómo se nombra a los conductores, las secciones o la historia, tocá solo [config/programa.yaml](config/programa.yaml).
- Chequeá cómo quedó con `uv run -m rita --prompt`.

## Si `rita` no arranca

El comando es `uv run -m rita` y no `uv run rita` a propósito: en macOS reciente el sistema marca como ocultos los archivos `.pth` del entorno virtual y Python los ignora, con lo que el atajo `rita` instalado por uv falla con `No module named 'rita'`. `-m rita` carga el paquete desde la carpeta del proyecto y no depende de eso. Hay que correrlo parado en la raíz del repo.

## Tests

```bash
uv run pytest
```

Prueban el armado del prompt, la fecha en castellano, el corte de frases para la voz y el servidor del modo web (con cerebro y voz falsos). No llaman a la API.

## Estructura

```
prompts/rita.md        personalidad y reglas (system prompt)
config/programa.yaml   datos del programa
rita/config.py         .env y YAML
rita/prompt.py         arma el system prompt + bloque de fecha
rita/cerebro.py        Claude + búsqueda web + memoria de la charla
rita/oido.py           micrófono + Whisper
rita/voz.py            edge-tts + reproducción encadenada
rita/texto.py          corte por frases y limpieza para voz
rita/registro.py       log de lo dicho al aire (logs/, un archivo por día)
rita/web.py            servidor del modo web (streaming por frases, acceso por código)
rita/estatico/         la página del modo web (botón de asistente, manos libres)
rita/main.py           la interfaz de línea de comandos (`uv run -m rita`)
tests/                 pytest
```

## Pendientes

- Entrada de audio desde la consola de la radio (hoy toma el micrófono del sistema).
- Interrupción por voz mientras habla en modo push-to-talk.
