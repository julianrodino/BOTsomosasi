"""Punto de entrada: `rita`."""

from __future__ import annotations

import argparse
import sys
import time

import anthropic

from .config import Ajustes
from .prompt import construir_system

BANNER = """
  ┌──────────────────────────────────────────┐
  │  RITA · compañera de piso de SomosAsi    │
  └──────────────────────────────────────────┘
"""


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rita", description="Rita, la IA del piso de SomosAsi.")
    modo = p.add_mutually_exclusive_group()
    modo.add_argument("--texto", action="store_true", help="escribirle en vez de hablarle (responde por voz igual)")
    modo.add_argument("--auto", action="store_true", help="detección automática de voz, sin apretar Enter")
    p.add_argument("--mudo", action="store_true", help="no reproduce audio, solo imprime")
    p.add_argument("--sin-registro", action="store_true", help="no guarda la charla en logs/")
    p.add_argument("--probar-voz", metavar="FRASE", help="dice una frase y sale (para probar la voz)")
    p.add_argument("--dispositivos", action="store_true", help="lista los micrófonos y sale")
    p.add_argument("--prompt", action="store_true", help="imprime el system prompt armado y sale")
    return p.parse_args()


def main() -> int:
    args = _args()
    ajustes = Ajustes()

    if args.dispositivos:
        from .oido import listar_dispositivos

        print(listar_dispositivos())
        return 0

    if args.prompt:
        print(construir_system(ajustes))
        return 0

    from .voz import Locutora

    if args.probar_voz:
        loc = Locutora(ajustes)
        loc.decir(args.probar_voz)
        loc.esperar()
        loc.cerrar()
        return 0

    from .cerebro import Cerebro
    from .registro import Registro

    system = construir_system(ajustes)
    cerebro = Cerebro(ajustes, system)
    locutora = Locutora(ajustes, muda=args.mudo)
    registro = Registro(activo=not args.sin_registro)

    oido = None
    if not args.texto:
        from .oido import Oido

        oido = Oido(ajustes)
        oido.preparar()

    print(BANNER)
    print(f"  modelo {ajustes.modelo} · esfuerzo {ajustes.esfuerzo} · voz {ajustes.voz}")
    if registro.activo:
        print(f"  registro en {registro.archivo.relative_to(registro.carpeta.parent)}")
    if args.texto:
        print("  Escribí y Enter. Comandos: /reset (olvida la charla), /salir")
    elif args.auto:
        print(f"  Modo automático: hablá y Rita contesta (umbral {ajustes.umbral:.0%}). Ctrl+C para salir.")
    else:
        print("  Enter para hablar, Enter para cortar. Ctrl+C para salir.")

    try:
        while True:
            if args.texto:
                try:
                    dicho = input("\nVos: ").strip()
                except EOFError:
                    break
                if not dicho:
                    continue
                if dicho in ("/salir", "/exit", "/q"):
                    break
                if dicho == "/reset":
                    cerebro.olvidar()
                    print("  (Rita olvidó la charla)")
                    continue
                locutora.callar()
            else:
                if args.auto:
                    audio = oido.grabar_automatico(al_detectar_voz=locutora.callar)
                else:
                    audio = oido.grabar_pulsando(antes_de_grabar=locutora.callar)
                dicho = oido.transcribir(audio)
                if not dicho:
                    print("  (no entendí nada)")
                    continue
                print(f"Vos: {dicho}")

            print("Rita: ", end="", flush=True)

            def al_recibir_frase(frase: str) -> None:
                print(frase, end=" ", flush=True)
                locutora.decir(frase)

            inicio = time.monotonic()
            try:
                respuesta = cerebro.responder(dicho, al_recibir_frase)
                registro.anotar(dicho, respuesta, segundos=time.monotonic() - inicio)
            except anthropic.AuthenticationError:
                print("\n[error] la ANTHROPIC_API_KEY es inválida (ver .env.example).", file=sys.stderr)
                return 1
            except TypeError as e:
                if "authentication" not in str(e).lower():
                    raise
                print("\n[error] falta la ANTHROPIC_API_KEY: copiá .env.example a .env y pegala ahí.", file=sys.stderr)
                return 1
            except anthropic.RateLimitError:
                frase = "Me saturaron, dame un respiro y preguntame de nuevo."
                print(frase)
                locutora.decir(frase)
            except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
                print(f"\n[error] {e}", file=sys.stderr)
                frase = "Se me cortó la conexión, repetime eso."
                print(frase)
                locutora.decir(frase)
            print()
            locutora.esperar()
    except KeyboardInterrupt:
        print("\n  chau.")
    finally:
        locutora.cerrar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
