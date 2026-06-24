"""
Zenith Watch - Cloud Function Principal
Roda a cada 5 minutos via Cloud Scheduler.
Verifica alertas e envia notificações via Firebase Cloud Messaging.
"""

import json
import os
import functions_framework
from firebase_admin import initialize_app, firestore, messaging
from astronomia import verificar_alertas, analisar_catalogo, objetos_zenite, melhor_alvo_agora
from datetime import datetime, time


# ─────────────────────────────────────────
# INICIALIZAÇÃO FIREBASE
# ─────────────────────────────────────────

app = initialize_app()
db  = firestore.client()


# ─────────────────────────────────────────
# CARREGAR CATÁLOGO
# ─────────────────────────────────────────

def carregar_catalogo() -> dict:
    """Carrega o catálogo JSON do Firestore ou do arquivo local."""
    try:
        doc = db.collection("config").document("catalogo").get()
        if doc.exists:
            return doc.to_dict()
    except Exception:
        pass

    # Fallback: arquivo local
    caminho = os.path.join(os.path.dirname(__file__), "..", "catalogo", "catalogo.json")
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def carregar_config_usuario(user_id: str = "default") -> dict:
    """Carrega configurações do usuário do Firestore."""
    try:
        doc = db.collection("usuarios").document(user_id).get()
        if doc.exists:
            return doc.to_dict().get("config", {})
    except Exception:
        pass
    return {}


# ─────────────────────────────────────────
# CONTROLE DE SILÊNCIO
# ─────────────────────────────────────────

def em_horario_silencio(config: dict) -> bool:
    """Verifica se está no horário de silêncio configurado."""
    inicio_str = config.get("silencio_inicio", "00:00")
    fim_str    = config.get("silencio_fim", "06:00")

    agora = datetime.now().time()

    try:
        h_ini, m_ini = map(int, inicio_str.split(":"))
        h_fim, m_fim = map(int, fim_str.split(":"))
        t_ini = time(h_ini, m_ini)
        t_fim = time(h_fim, m_fim)

        if t_ini <= t_fim:
            return t_ini <= agora <= t_fim
        else:
            # Passa da meia-noite
            return agora >= t_ini or agora <= t_fim
    except Exception:
        return False


# ─────────────────────────────────────────
# ENVIO DE NOTIFICAÇÕES
# ─────────────────────────────────────────

MENSAGENS_NIVEL = {
    "zenite": {
        "titulo": "🚨🚨🚨 CINEMA ABSOLUTO",
        "emoji":  "🎯",
    },
    "prioritario": {
        "titulo": "🚨 ALERTA PRIORITÁRIO",
        "emoji":  "⭐",
    },
    "normal": {
        "titulo": "🔭 Alerta Celeste",
        "emoji":  "🌌",
    },
}


def enviar_notificacao(token_fcm: str, alerta: dict) -> bool:
    """Envia notificação push via Firebase Cloud Messaging."""
    nivel  = alerta["nivel"]
    objeto = alerta["objeto"]
    pos    = objeto["posicao"]
    janela = objeto["janela"]

    cfg_msg = MENSAGENS_NIVEL.get(nivel, MENSAGENS_NIVEL["normal"])

    titulo = cfg_msg["titulo"]
    corpo  = (
        f"{cfg_msg['emoji']} {objeto['nome']}\n"
        f"Altitude: {pos['altitude_graus']}°\n"
        f"Janela: {janela['minutos_restantes']} minutos"
    )

    mensagem = messaging.Message(
        notification=messaging.Notification(title=titulo, body=corpo),
        data={
            "objeto_id":   objeto["id"],
            "altitude":    str(pos["altitude_graus"]),
            "nivel":       nivel,
            "minutos":     str(janela["minutos_restantes"]),
        },
        token=token_fcm,
        android=messaging.AndroidConfig(priority="high"),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default")
            )
        ),
    )

    try:
        messaging.send(mensagem)
        return True
    except Exception as e:
        print(f"Erro ao enviar notificação: {e}")
        return False


# ─────────────────────────────────────────
# CONTROLE DE ALERTAS JÁ ENVIADOS
# ─────────────────────────────────────────

def alerta_ja_enviado(user_id: str, objeto_id: str) -> bool:
    """Verifica se o alerta desse objeto já foi enviado na última hora."""
    try:
        doc = db.collection("alertas_enviados").document(f"{user_id}_{objeto_id}").get()
        if doc.exists:
            dados = doc.to_dict()
            ultimo = dados.get("timestamp")
            if ultimo:
                diff = datetime.utcnow() - ultimo.replace(tzinfo=None)
                return diff.total_seconds() < 3600  # 1 hora
    except Exception:
        pass
    return False


def registrar_alerta_enviado(user_id: str, objeto_id: str):
    """Registra que o alerta foi enviado pra não repetir em 1 hora."""
    try:
        db.collection("alertas_enviados").document(f"{user_id}_{objeto_id}").set({
            "timestamp": datetime.utcnow(),
            "user_id":   user_id,
            "objeto_id": objeto_id,
        })
    except Exception as e:
        print(f"Erro ao registrar alerta: {e}")


# ─────────────────────────────────────────
# CLOUD FUNCTION PRINCIPAL
# ─────────────────────────────────────────

@functions_framework.http
def verificar_e_alertar(request):
    """
    Endpoint chamado pelo Cloud Scheduler a cada 5 minutos.
    Verifica alertas e envia notificações para todos os usuários cadastrados.
    """
    catalogo = carregar_catalogo()
    erros    = []
    enviados = 0

    try:
        usuarios = db.collection("usuarios").stream()

        for usuario_doc in usuarios:
            user_id = usuario_doc.id
            dados   = usuario_doc.to_dict()

            token_fcm = dados.get("token_fcm")
            if not token_fcm:
                continue

            config_usuario = dados.get("config", {})
            config = {**catalogo.get("config_padrao", {}), **config_usuario}

            # Respeita horário de silêncio
            if em_horario_silencio(config):
                continue

            alertas = verificar_alertas(catalogo, config)

            for alerta in alertas:
                objeto_id = alerta["objeto"]["id"]

                if alerta_ja_enviado(user_id, objeto_id):
                    continue

                sucesso = enviar_notificacao(token_fcm, alerta)
                if sucesso:
                    registrar_alerta_enviado(user_id, objeto_id)
                    enviados += 1

    except Exception as e:
        erros.append(str(e))
        print(f"Erro na verificação: {e}")

    return {
        "status":   "ok" if not erros else "parcial",
        "enviados": enviados,
        "erros":    erros,
        "horario":  datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────
# ENDPOINTS DE API PARA O APP
# ─────────────────────────────────────────

@functions_framework.http
def api_hoje(request):
    """Retorna resumo da noite — todos os objetos visíveis."""
    catalogo = carregar_catalogo()
    visiveis = analisar_catalogo(catalogo)

    return {
        "objetos":   visiveis,
        "total":     len(visiveis),
        "horario":   datetime.utcnow().isoformat(),
    }


@functions_framework.http
def api_zenite(request):
    """Retorna objetos próximos ao zênite."""
    catalogo = carregar_catalogo()
    zenite   = objetos_zenite(catalogo)

    return {
        "objetos": zenite,
        "total":   len(zenite),
    }


@functions_framework.http
def api_melhor_agora(request):
    """Retorna o melhor alvo neste momento."""
    catalogo = carregar_catalogo()
    melhor   = melhor_alvo_agora(catalogo)

    return {"objeto": melhor}


@functions_framework.http
def api_objeto(request):
    """Retorna dados de um objeto específico por ID."""
    objeto_id = request.args.get("id", "").lower().replace(" ", "_")
    catalogo  = carregar_catalogo()

    objeto = next((o for o in catalogo["objetos"] if o["id"] == objeto_id), None)
    if not objeto:
        return {"erro": f"Objeto '{objeto_id}' não encontrado."}, 404

    import ephem as ep
    obs = ep.Observer()
    cfg = catalogo["config_padrao"]
    obs.lat       = str(cfg["latitude"])
    obs.lon       = str(cfg["longitude"])
    obs.elevation = 20.0
    obs.pressure  = 0
    obs.epoch     = ep.J2000
    obs.date      = ep.Date(datetime.utcnow())

    from astronomia import calcular_posicao_raw, calcular_janela
    pos    = calcular_posicao_raw(objeto, obs, datetime.utcnow())
    janela = calcular_janela(objeto, obs)

    return {
        "objeto": objeto,
        "posicao": pos,
        "janela":  janela,
    }
