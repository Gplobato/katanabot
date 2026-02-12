# bot.py — Katana ELITE7 (Logs da IA de volta + Fix 404)

import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIG ====================

OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4-turbo-preview")

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
    """Remove caracteres não numéricos e limpa sufixos"""
    if not raw:
        return ""
    cleaned = str(raw).split("@")[0]
    return re.sub(r"\D", "", cleaned)


# ==================== EVOLUTION SEND ====================

def send_via_evolution(phone: str, message: str):
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    
    number = normalize_phone(phone)

    # Formato simples (funciona na v1.8 e na maioria das v2 configuradas com text simples)
    payload = {
        "number": number,
        "text": message
    }

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }

    try:
        print(f"🚀 Enviando para {number}...")
        
        r = requests.post(url, headers=headers, json=payload, timeout=20)

        print(f"📊 Status Envio: {r.status_code}")
        
        if not r.ok:
            print(f"❌ Erro da Evolution: {r.text[:300]}")
            # Fallback para formato textMessage se der erro 400
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

# Rota extra para silenciar o erro 404 do log (Evento SEND_MESSAGE)
@app.route("/webhook/send-message", methods=["POST"])
def webhook_send_message_ignore():
    return jsonify({"status": "ignored"}), 200

@app.route("/webhook", methods=["POST", "GET"])
@app.route("/webhook/messages-upsert", methods=["POST"])
def webhook():

    if request.method == "GET":
        return jsonify({"status": "ok"}), 200

    body = request.get_json(force=True, silent=True)
    if not body:
        return jsonify({"status": "ignored"}), 200

    # Filtra evento (aceita mensagens novas)
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

        if not isinstance(data, dict):
            return jsonify({"status": "invalid_data"}), 200

        key = data.get("key", {})

        # Ignora o próprio bot
        if key.get("fromMe"):
            return jsonify({"status": "self"}), 200

        # === RESOLUÇÃO DE NÚMERO ===
        phone = body.get("sender") or data.get("pushName")
        remote_jid = key.get("remoteJid")
        
        if not phone:
            phone = remote_jid
            
        # Tratamento anti-LID (iPhone)
        if remote_jid and "@lid" in remote_jid:
             if body.get("sender"):
                 phone = body.get("sender")
             else:
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

        print(f"📩 Usuário disse: {text}")

        # ================= IA (OpenRouter) =================

        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://katanabot.com",
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
            # AQUI ESTÁ A MÁGICA DE VOLTA 👇
            print(f"🤖 Katana respondeu: {reply}") 
        else:
            print(f"❌ Erro na IA: {resp.text}")
            reply = "Tô meio bugada agora, tenta já já! 😵"

        # ================= ENVIAR =================

        send_via_evolution(phone, reply)

        return jsonify({"status": "sent"}), 200

    except Exception as e:
        print(f"❌ ERRO CRÍTICO NO WEBHOOK: {e}")
        return jsonify({"error": str(e)}), 200


# ==================== RUN ====================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
