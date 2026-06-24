"""
Zenith Watch - Módulo de Cálculo Astronômico
Calcula posição, altitude e janela de observação de objetos celestes.
"""

import ephem
import json
from datetime import datetime, timedelta
from typing import Optional


# ─────────────────────────────────────────
# CONFIGURAÇÃO DO OBSERVADOR
# ─────────────────────────────────────────

def criar_observador(
    latitude: float = -3.7172,
    longitude: float = -38.5433,
    altitude_m: float = 20.0
) -> ephem.Observer:
    """Cria um observador ephem com a localização fornecida."""
    obs = ephem.Observer()
    obs.lat = str(latitude)
    obs.lon = str(longitude)
    obs.elevation = altitude_m
    obs.pressure = 0       # ignora refração atmosférica
    obs.epoch = ephem.J2000
    return obs


# ─────────────────────────────────────────
# OBJETOS DO SISTEMA SOLAR
# ─────────────────────────────────────────

PLANETAS_EPHEM = {
    "lua":     ephem.Moon,
    "saturno": ephem.Saturn,
    "jupiter": ephem.Jupiter,
    "marte":   ephem.Mars,
    "venus":   ephem.Venus,
}


def _corpo_solar(ephem_nome: str):
    """Retorna o corpo ephem do Sistema Solar pelo nome."""
    nome = ephem_nome.lower()
    mapa = {
        "moon":    ephem.Moon,
        "saturn":  ephem.Saturn,
        "jupiter": ephem.Jupiter,
        "mars":    ephem.Mars,
        "venus":   ephem.Venus,
        "mercury": ephem.Mercury,
        "uranus":  ephem.Uranus,
        "neptune": ephem.Neptune,
    }
    cls = mapa.get(nome)
    if cls is None:
        raise ValueError(f"Planeta '{ephem_nome}' não reconhecido.")
    return cls()


def _corpo_profundo(ra: str, dec: str, magnitude: float, nome: str) -> ephem.FixedBody:
    """Cria um objeto de céu profundo (estrela fixa) no ephem."""
    corpo = ephem.FixedBody()
    corpo._ra  = ephem.hours(ra.replace("h", ":").replace("m", ":").replace("s", ""))
    corpo._dec = ephem.degrees(dec.replace("d", ":").replace("m", ":").replace("s", ""))
    corpo._epoch = ephem.J2000
    corpo.name = nome
    return corpo


# ─────────────────────────────────────────
# CÁLCULO DE POSIÇÃO
# ─────────────────────────────────────────

def calcular_posicao(objeto: dict, obs: ephem.Observer, quando: Optional[datetime] = None) -> dict:
    """
    Calcula altitude e azimute de um objeto celeste.

    Retorna:
        {
            "altitude_graus": float,
            "azimute_graus": float,
            "distancia_zenite": float,
            "visivel": bool,        # acima de altitude_minima
            "observavel": bool,     # acima de 45° (padrão do quintal)
        }
    """
    if quando is None:
        quando = datetime.utcnow()

    obs = ephem.Observer()
    obs.lat  = str(obs.lat)  if hasattr(obs, '_lat_str') else obs.lat
    obs.date = ephem.Date(quando)

    # Recria o observador pra garantir o horário
    observador = ephem.Observer()
    observador.lat  = obs.lat
    observador.lon  = obs.lon
    observador.elevation = obs.elevation
    observador.pressure  = 0
    observador.epoch     = ephem.J2000
    observador.date      = ephem.Date(quando)

    if objeto.get("objeto_solar") and objeto.get("ephem_nome"):
        corpo = _corpo_solar(objeto["ephem_nome"])
    elif objeto.get("ra") and objeto.get("dec"):
        corpo = _corpo_profundo(objeto["ra"], objeto["dec"], objeto.get("magnitude", 99), objeto["nome"])
    else:
        return {"erro": f"Objeto '{objeto['nome']}' sem coordenadas válidas."}

    corpo.compute(observador)

    altitude_graus    = float(corpo.alt) * 180 / 3.14159265
    azimute_graus     = float(corpo.az)  * 180 / 3.14159265
    distancia_zenite  = 90.0 - altitude_graus

    return {
        "altitude_graus":   round(altitude_graus, 1),
        "azimute_graus":    round(azimute_graus, 1),
        "distancia_zenite": round(distancia_zenite, 1),
        "visivel":          altitude_graus > 0,
        "observavel":       altitude_graus >= 45.0,
    }


# ─────────────────────────────────────────
# JANELA DE OBSERVAÇÃO
# ─────────────────────────────────────────

def calcular_janela(objeto: dict, obs_base: ephem.Observer, limite_graus: float = 75.0) -> dict:
    """
    Calcula por quantos minutos o objeto ainda ficará acima de `limite_graus`.

    Retorna:
        {
            "minutos_restantes": int,
            "pico_altitude": float,
            "minutos_para_pico": int,
        }
    """
    agora = datetime.utcnow()
    pico_alt   = -999
    pico_min   = 0
    fim_janela = 0

    for delta_min in range(0, 360, 2):  # próximas 6 horas, a cada 2 minutos
        quando = agora + timedelta(minutes=delta_min)
        pos = calcular_posicao_raw(objeto, obs_base, quando)
        alt = pos.get("altitude_graus", -999)

        if alt > pico_alt:
            pico_alt = alt
            pico_min = delta_min

        if alt >= limite_graus:
            fim_janela = delta_min

    # Minutos restantes acima do limite a partir de agora
    pos_agora = calcular_posicao_raw(objeto, obs_base, agora)
    alt_agora = pos_agora.get("altitude_graus", -999)

    if alt_agora < limite_graus:
        # Objeto ainda vai subir
        minutos_restantes = max(0, fim_janela)
    else:
        # Objeto já está acima, conta quanto tempo ainda resta
        minutos_restantes = max(0, fim_janela)

    return {
        "minutos_restantes": minutos_restantes,
        "pico_altitude":     round(pico_alt, 1),
        "minutos_para_pico": pico_min,
    }


def calcular_posicao_raw(objeto: dict, obs_ref: ephem.Observer, quando: datetime) -> dict:
    """Versão interna de calcular_posicao que aceita observer de referência."""
    observador = ephem.Observer()
    observador.lat       = obs_ref.lat
    observador.lon       = obs_ref.lon
    observador.elevation = obs_ref.elevation
    observador.pressure  = 0
    observador.epoch     = ephem.J2000
    observador.date      = ephem.Date(quando)

    if objeto.get("objeto_solar") and objeto.get("ephem_nome"):
        corpo = _corpo_solar(objeto["ephem_nome"])
    elif objeto.get("ra") and objeto.get("dec"):
        corpo = _corpo_profundo(objeto["ra"], objeto["dec"], objeto.get("magnitude", 99), objeto["nome"])
    else:
        return {"altitude_graus": -999}

    corpo.compute(observador)
    altitude_graus = float(corpo.alt) * 180 / 3.14159265
    azimute_graus  = float(corpo.az)  * 180 / 3.14159265

    return {
        "altitude_graus":   round(altitude_graus, 1),
        "azimute_graus":    round(azimute_graus, 1),
        "distancia_zenite": round(90.0 - altitude_graus, 1),
        "visivel":          altitude_graus > 0,
        "observavel":       altitude_graus >= 45.0,
    }


# ─────────────────────────────────────────
# ANÁLISE DO CATÁLOGO COMPLETO
# ─────────────────────────────────────────

def analisar_catalogo(catalogo: dict, config: Optional[dict] = None) -> list:
    """
    Analisa todos os objetos do catálogo e retorna lista ordenada por altitude.

    Retorna lista de dicts com posição + dados do objeto.
    """
    if config is None:
        config = catalogo.get("config_padrao", {})

    obs = ephem.Observer()
    obs.lat       = str(config.get("latitude", -3.7172))
    obs.lon       = str(config.get("longitude", -38.5433))
    obs.elevation = 20.0
    obs.pressure  = 0
    obs.epoch     = ephem.J2000
    obs.date      = ephem.Date(datetime.utcnow())

    altitude_minima = config.get("altitude_minima", 45)
    resultados = []

    for obj in catalogo["objetos"]:
        pos = calcular_posicao_raw(obj, obs, datetime.utcnow())
        alt = pos.get("altitude_graus", -999)

        if alt < altitude_minima:
            continue

        janela = calcular_janela(obj, obs, limite_graus=config.get("altitude_alerta", 75))

        resultados.append({
            **obj,
            "posicao": pos,
            "janela":  janela,
        })

    # Ordena por altitude (maior primeiro)
    resultados.sort(key=lambda x: x["posicao"]["altitude_graus"], reverse=True)
    return resultados


def objetos_zenite(catalogo: dict, config: Optional[dict] = None) -> list:
    """
    Retorna objetos dentro da janela do zênite (distância <= janela_zenite_graus).
    Ordenados por distância ao zênite (menor primeiro).
    """
    if config is None:
        config = catalogo.get("config_padrao", {})

    janela_graus = config.get("janela_zenite_graus", 30)
    todos = analisar_catalogo(catalogo, config)

    zenite = [
        obj for obj in todos
        if obj["posicao"]["distancia_zenite"] <= janela_graus
    ]
    zenite.sort(key=lambda x: x["posicao"]["distancia_zenite"])
    return zenite


def melhor_alvo_agora(catalogo: dict, config: Optional[dict] = None) -> Optional[dict]:
    """Retorna o melhor objeto pra observar agora (maior altitude observável)."""
    todos = analisar_catalogo(catalogo, config)
    if not todos:
        return None
    return todos[0]


def verificar_alertas(catalogo: dict, config: Optional[dict] = None) -> list:
    """
    Verifica quais objetos merecem alerta.

    Retorna lista de alertas com nível:
        - 'prioritario': objeto prioritário acima de altitude_alerta
        - 'normal':      qualquer objeto acima de altitude_alerta_prioritario
        - 'zenite':      qualquer objeto acima de 88°
    """
    if config is None:
        config = catalogo.get("config_padrao", {})

    alt_alerta      = config.get("altitude_alerta", 75)
    alt_prioritario = config.get("altitude_alerta_prioritario", 85)
    alt_zenite      = config.get("altitude_zenite", 88)

    todos   = analisar_catalogo(catalogo, config)
    alertas = []

    for obj in todos:
        alt = obj["posicao"]["altitude_graus"]

        if alt >= alt_zenite:
            nivel = "zenite"
        elif alt >= alt_prioritario:
            nivel = "prioritario" if obj.get("prioritario") else "normal"
        elif alt >= alt_alerta and obj.get("prioritario"):
            nivel = "prioritario"
        else:
            continue

        alertas.append({
            "objeto": obj,
            "nivel":  nivel,
        })

    return alertas


# ─────────────────────────────────────────
# TESTE RÁPIDO NO TERMINAL
# ─────────────────────────────────────────

if __name__ == "__main__":
    import os

    caminho = os.path.join(os.path.dirname(__file__), "..", "catalogo", "catalogo.json")
    with open(caminho, "r", encoding="utf-8") as f:
        catalogo = json.load(f)

    print("=" * 50)
    print("🔭 ZENITH WATCH — Teste de Cálculo")
    print("=" * 50)

    print("\n🌌 OBJETOS VISÍVEIS AGORA (ordenados por altitude):")
    visiveis = analisar_catalogo(catalogo)
    for obj in visiveis:
        pos = obj["posicao"]
        print(f"  {obj['nome']:<25} Alt: {pos['altitude_graus']:>5.1f}°  Az: {pos['azimute_graus']:>6.1f}°")

    print("\n🎯 PRÓXIMOS AO ZÊNITE:")
    zenite = objetos_zenite(catalogo)
    if zenite:
        for i, obj in enumerate(zenite[:5], 1):
            dist = obj["posicao"]["distancia_zenite"]
            print(f"  {i}. {obj['nome']:<25} Distância: {dist:.1f}°")
    else:
        print("  Nenhum objeto na janela do zênite agora.")

    print("\n🏆 MELHOR ALVO AGORA:")
    melhor = melhor_alvo_agora(catalogo)
    if melhor:
        pos    = melhor["posicao"]
        janela = melhor["janela"]
        print(f"  {melhor['nome']}")
        print(f"  Altitude: {pos['altitude_graus']}°")
        print(f"  Janela:   {janela['minutos_restantes']} minutos acima de 75°")
        print(f"  Pico em:  {janela['minutos_para_pico']} min ({janela['pico_altitude']}°)")

    print("\n🚨 ALERTAS ATIVOS:")
    alertas = verificar_alertas(catalogo)
    if alertas:
        for a in alertas:
            nivel  = a["nivel"].upper()
            nome   = a["objeto"]["nome"]
            alt    = a["objeto"]["posicao"]["altitude_graus"]
            print(f"  [{nivel}] {nome} — {alt}°")
    else:
        print("  Nenhum alerta no momento.")

    print("\n" + "=" * 50)
