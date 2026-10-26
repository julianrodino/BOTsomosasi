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
uv run rita --probar-voz "Hola, soy Rita, probando la voz del piso."
```

## Uso

| Comando | Qué hace |
|---|---|
| `uv run rita` | Modo radio: Enter para hablarle, Enter para cortar. Rita contesta por voz. |
| `uv run rita --auto` | Sin teclado: detecta cuando alguien habla y corta tras un silencio. Calibrar con `RITA_UMBRAL`. |
| `uv run rita --texto` | Escribirle en vez de hablarle. Sirve para probar el personaje sin micrófono. |
| `uv run rita --texto --mudo` | Solo texto, sin audio. Lo más barato para iterar el prompt. |
| `uv run rita --prompt` | Imprime el system prompt ya armado con los datos del programa. |
| `uv run rita --dispositivos` | Lista los micrófonos disponibles. |
| `... --sin-registro` | No guarda la charla en `logs/`. |

La primera vez que arranca en modo voz descarga el modelo de Whisper a `modelos/` (unos 500 MB para `small`).

Mientras Rita habla, apretar Enter (o empezar a hablar, en `--auto`) la interrumpe.

Cada intervención queda anotada en `logs/AAAA-MM-DD.jsonl` (hora, lo que dijo el piso, lo que contestó Rita y cuánto tardó). Sirve para revisar el programa y para afinar el prompt.

## Ajustes

Todo se configura por variables de entorno en `.env`; están documentadas en [.env.example](.env.example). Las que más importan al aire:

- `RITA_ESFUERZO`: `low` es lo más rápido. Subirlo mejora respuestas largas pero agrega segundos de silencio.
- `RITA_WHISPER`: `small` es el equilibrio. `large-v3-turbo` entiende mejor con ruido de fondo pero tarda más en CPU.
- `RITA_UMBRAL` y `RITA_SILENCIO`: sensibilidad del modo automático.

## Editar a Rita

- El personaje vive en [prompts/rita.md](prompts/rita.md). Las variables `{{asi}}` se completan desde el YAML; el resto es texto libre.
- Para cambiar cómo se nombra a los conductores, las secciones o la historia, tocá solo [config/programa.yaml](config/programa.yaml).
- Chequeá cómo quedó con `uv run rita --prompt`.

## Tests

```bash
uv run pytest
```

Prueban el armado del prompt, la fecha en castellano y el corte de frases para la voz. No llaman a la API.

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
rita/main.py           el comando `rita`
tests/                 pytest
```

## Pendientes

- Entrada de audio desde la consola de la radio (hoy toma el micrófono del sistema).
- Interrupción por voz mientras habla en modo push-to-talk.
