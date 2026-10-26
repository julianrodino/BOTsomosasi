"""Tests del modo web. No llaman a la API ni a edge-tts: se inyectan un cerebro y una voz falsos."""

import base64
import json

import pytest
from starlette.testclient import TestClient

from rita.config import Ajustes
from rita.web import COOKIE, crear_app


class CerebroFalso:
    def __init__(self):
        self.olvidado = False
        self.cortado = False

    def cortar(self):
        self.cortado = True

    def responder(self, dicho, al_recibir_frase=None):
        frases = ["Los franceses, a principios del mil setecientos.", "Y nosotros lo adoptamos."]
        for f in frases:
            al_recibir_frase(f)
        return " ".join(frases)

    def olvidar(self):
        self.olvidado = True


class RegistroFalso:
    def __init__(self):
        self.filas = []

    def anotar(self, dicho, respuesta, segundos=None):
        self.filas.append((dicho, respuesta))


def sintetizar_falso(frase):
    if frase.startswith("Y nosotros"):
        raise RuntimeError("sin internet")
    return b"MP3" + frase.encode()


def eventos(texto):
    """Parsea un cuerpo de server-sent events en una lista de (evento, datos)."""
    salida = []
    for bloque in texto.strip().split("\n\n"):
        evento, datos = None, ""
        for linea in bloque.splitlines():
            if linea.startswith("event: "):
                evento = linea[7:]
            elif linea.startswith("data: "):
                datos += linea[6:]
        salida.append((evento, json.loads(datos or "{}")))
    return salida


@pytest.fixture
def armado():
    cerebro, registro = CerebroFalso(), RegistroFalso()
    app = crear_app(Ajustes(), cerebro, "clave-estudio", registro=registro, sintetizar=sintetizar_falso)
    return TestClient(app), cerebro, registro


def entrar(cliente, codigo="clave-estudio"):
    return cliente.post("/api/entrar", json={"codigo": codigo})


def test_sin_codigo_no_hay_api_pero_si_pagina(armado):
    cliente, _, _ = armado
    assert cliente.get("/").status_code == 200
    assert "Rita" in cliente.get("/").text
    assert cliente.get("/api/estado").status_code == 401
    assert cliente.post("/api/preguntar", json={"texto": "hola"}).status_code == 401


def test_codigo_incorrecto_no_entra(armado):
    cliente, _, _ = armado
    r = entrar(cliente, "otra")
    assert r.status_code == 403
    assert COOKIE not in r.cookies
    assert cliente.get("/api/estado").status_code == 401


def test_codigo_correcto_deja_cookie_y_no_distingue_mayusculas(armado):
    cliente, _, _ = armado
    r = entrar(cliente, "  CLAVE-estudio ")
    assert r.status_code == 200
    assert COOKIE in r.cookies
    estado = cliente.get("/api/estado").json()
    assert estado["ok"] is True
    assert estado["whisper"] is False
    assert estado["ocupada"] is False


def test_preguntar_emite_frases_audio_fin_y_listo(armado):
    cliente, _, registro = armado
    entrar(cliente)
    r = cliente.post("/api/preguntar", json={"texto": "¿quién inventó el bidet?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    evs = eventos(r.text)

    frases = [d for e, d in evs if e == "frase"]
    assert [f["n"] for f in frases] == [1, 2]
    assert frases[0]["texto"].startswith("Los franceses")

    audios = {d["n"]: d["mp3"] for e, d in evs if e == "audio"}
    assert base64.b64decode(audios[1]).startswith(b"MP3")
    assert audios[2] is None  # la síntesis falló: la lee el navegador

    fin = next(d for e, d in evs if e == "fin")
    assert fin["texto"] == "Los franceses, a principios del mil setecientos. Y nosotros lo adoptamos."
    assert "segundos" in fin
    assert evs[-1][0] == "listo"
    assert registro.filas == [("¿quién inventó el bidet?", fin["texto"])]


def test_pregunta_vacia_y_olvidar(armado):
    cliente, cerebro, _ = armado
    entrar(cliente)
    assert cliente.post("/api/preguntar", json={"texto": "   "}).status_code == 400
    assert cliente.post("/api/olvidar").status_code == 200
    assert cerebro.olvidado
    assert cliente.post("/api/cortar").status_code == 200
    assert cerebro.cortado


def test_error_del_cerebro_llega_como_evento():
    class Roto:
        def responder(self, dicho, al_recibir_frase=None):
            raise RuntimeError("se cayó")

        def olvidar(self):
            pass

    cliente = TestClient(crear_app(Ajustes(), Roto(), "x", sintetizar=sintetizar_falso))
    entrar(cliente, "x")
    evs = eventos(cliente.post("/api/preguntar", json={"texto": "hola"}).text)
    assert [e for e, _ in evs] == ["error", "listo"]
    assert "se cayó" in evs[0][1]["mensaje"]
    # Y el candado quedó libre para la próxima.
    assert cliente.get("/api/estado").json()["ocupada"] is False


def test_transcribir_sin_whisper_avisa(armado):
    cliente, _, _ = armado
    entrar(cliente)
    r = cliente.post("/api/transcribir", content=b"x" * 1000, headers={"Content-Type": "audio/webm"})
    assert r.status_code == 501
