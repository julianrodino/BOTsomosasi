import json

from rita.registro import Registro


def test_registro_escribe_una_linea_json_por_intervencion(tmp_path):
    reg = Registro(carpeta=tmp_path)
    reg.anotar("¿quién inventó el bidet?", "Los franceses.", segundos=2.34)
    reg.anotar("¿y el inodoro?", "Más viejo todavía.")
    lineas = reg.archivo.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 2
    primera = json.loads(lineas[0])
    assert primera["piso"] == "¿quién inventó el bidet?"
    assert primera["rita"] == "Los franceses."
    assert primera["segundos"] == 2.3
    assert "segundos" not in json.loads(lineas[1])


def test_registro_desactivado_no_escribe(tmp_path):
    reg = Registro(carpeta=tmp_path / "nada", activo=False)
    reg.anotar("hola", "hola")
    assert not (tmp_path / "nada").exists()
