# bot.py — Katana ELITE7 (Corrigido para erro "Requires Property Text")

import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIG ====================

OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4-turbo-preview")

# Garante que a URL não tenha barra no final para evitar erro de rota //
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "")

BOT_PERSONALITY = os.environ.get(
    "BOT_PERSONALITY",
    "Você é Katana ELITE7, sarcástica, zoeira, estilo melhor amiga gamer, respostas curtas e engraçadas."
)

# =================================================


# ==================== HELPERS ====================

def normalize_phone(raw: str) -> str:
    """Remove qualquer coisa que não seja número"""
    if not raw:
        return ""
    # Remove @s.whatsapp.net e outros sufixos antes de limpar
    cleaned = str(raw).split("@")[0]
    return re.sub(r"\D", "", cleaned)


# ==================== EVOLUTION SEND ====================

def send_via_evolution(phone: str, message: str):
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    
    number = normalize_phone(phone)

    # CORREÇÃO DO ERRO 400:
    # O log disse "instance requires property 'text'".
    # Então enviamos o formato simples (flat), sem 'textMessage'.
    payload = {
        "number": number,
        "text": message
    }

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }

    try:
        print(f"\n🚀 Enviando para {number}...")
        
        r = requests.post(url, headers=headers, json=payload, timeout=20)

        print(f"📊 Status Envio: {r.status_code}")
        
        if not r.ok:
            print(f"❌ Erro da Evolution: {r.text[:300]}")
            # Se der erro 400 de novo, tenta o formato alternativo (fallback)
            if r.status_code == 400 and "textMessage" in r.text:
                print("⚠️ Tentando formato alternativo v2...")
                payload_v2 = {
                    "number": number,
                    "textMessage": {"text": message}
                }
                r = requests.post(url, headers=headers, json=payload_v2, timeout=20)

        return r.ok

    except Exception as e:
        print(f"❌ Erro de Conexão Evolution: {e}")
        return False


# ==================== HEALTH ====================

@app.route("/", methods=["GET"])
def health():
    return "Katana ELITE7 Online 🔪", 200


# ==================== WEBHOOK ====================

@app.route("/webhook", methods=["POST", "GET"])
@app.route("/webhook/messages-upsert", methods=["POST"])
def webhook():

    # Evolution v2 as vezes faz check de saúde com GET
    if request.method == "GET":
        return jsonify({"status": "ok"}), 200

    body = request.get_json(force=True, silent=True)
    if not body:
        return jsonify({"status": "ignored"}), 200

    # Filtro de evento (Case insensitive)
    event = body.get("event", "")
    if event.upper() != "MESSAGES.UPSERT":
        return jsonify({"status": "ignored_event"}), 200

    try:
        data = body.get("data", {})

        # Tratamento de lista (comum na v2)
        if isinstance(data, list):
            if not data:
                return jsonify({"status": "empty_list"}), 200
            data = data[0]

        # Se depois disso não for dict, aborta
        if not isinstance(data, dict):
            return jsonify({"status": "invalid_data"}), 200

        key = data.get("key", {})

        # Ignora mensagens enviadas pelo próprio bot
        if key.get("fromMe"):
            return jsonify({"status": "self"}), 200

        # === RESOLUÇÃO DE NÚMERO (LID/SENDER) ===
        # A v2 costuma mandar o sender na raiz ou dentro de data
        phone = body.get("sender") or data.get("pushName")
        
        remote_jid = key.get("remoteJid")
        
        # Se não achou sender fácil, usa o remoteJid
        if not phone:
            phone = remote_jid
            
        # Se for LID (iPhone), tenta pegar o user real
        if remote_jid and "@lid" in remote_jid:
             if body.get("sender"):
                 phone = body.get("sender")
             else:
                 # Fallback: tenta pegar do owner ou deixa o LID mesmo
                 phone = data.get("owner", remote_jid)

        print(f"\n📞 Mensagem de: {phone}")

        # ================= EXTRAIR TEXTO =================

        msg = data.get("message", {})
        if not msg:
             return jsonify({"status": "no_message_content"}), 200

        text = (
            msg.get("conversation")
            or msg.get("extendedTextMessage", {}).get("text")
            or msg.get("imageMessage", {}).get("caption")
        )

        if not text:
            return jsonify({"status": "no_text"}), 200

        print(f"📩 Conteúdo: {text}")

        # ================= OPENROUTER (IA) =================

        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://katanabot.com", # Boa prática OpenRouter
        }

        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": BOT_PERSONALITY},
                    {"role": "user", "content": text}
                ]
            },
            timeout=25
        )

        if resp.ok:
            reply = resp.json()["choices"][0]["message"]["content"]
        else:
            print(f"❌ OpenRouter erro: {resp.text}")
            reply = "Tô meio bugada agora, tenta já já! 😵"

        # ================= ENVIAR RESPOSTA =================

        send_via_evolution(phone, reply)

        return jsonify({"status": "sent"}), 200

    except Exception as e:
        print(f"❌ ERRO CRÍTICO NO WEBHOOK: {e}")
        return jsonify({"error": str(e)}), 200


# ==================== RUN ====================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
