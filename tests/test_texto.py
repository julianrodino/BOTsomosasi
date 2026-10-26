from rita.texto import Segmentador, limpiar_para_voz


def test_segmentador_emite_frases_a_medida_que_llegan():
    frases = []
    seg = Segmentador(frases.append, minimo=10)
    for trozo in ["Ganó dos a uno, con gol sobre el fi", "nal. Lo dice el sitio de la Liga. Igual jugó", " mal, eh"]:
        seg.alimentar(trozo)
    assert frases == ["Ganó dos a uno, con gol sobre el final.", "Lo dice el sitio de la Liga."]
    seg.cerrar()
    assert frases[-1] == "Igual jugó mal, eh"


def test_segmentador_no_corta_frases_demasiado_cortas():
    frases = []
    seg = Segmentador(frases.append, minimo=25)
    seg.alimentar("Sí. Ni idea, dame un segundo que lo busco. ")
    assert frases == ["Sí. Ni idea, dame un segundo que lo busco."]


def test_segmentador_respeta_signos_de_pregunta_y_admiracion():
    frases = []
    seg = Segmentador(frases.append, minimo=5)
    seg.alimentar("¿El partido de anoche o el del domingo? Decime y te digo. ")
    assert frases == ["¿El partido de anoche o el del domingo?", "Decime y te digo."]


def test_limpiar_para_voz_saca_markdown_y_urls():
    sucio = "**El oficial** está a mil pesos según https://ambito.com/dolar hoy.\n\n- primero\n- segundo"
    assert limpiar_para_voz(sucio) == "El oficial está a mil pesos según hoy.\nprimero\nsegundo"
