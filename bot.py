# bot.py — Katana ELITE7 (Stable Edition • Evolution 1.8.2 safe)

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
    """Remove qualquer coisa que não seja número"""
    if not raw:
        return ""

    return re.sub(r"\D", "", str(raw))


# ==================== EVOLUTION SEND ====================

def send_via_evolution(phone: str, message: str):

    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"

    number = normalize_phone(phone)

    payload = {
        "number": number,   # sua instância exige number (não groupJid)
        "textMessage": {
            "text": message
        }
    }

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }

    try:
        print("\n🚀 Enviando mensagem")
        print("Número:", number)
        print("Payload:", payload)

        r = requests.post(url, headers=headers, json=payload, timeout=20)

        print("Status:", r.status_code)
        print("Resposta:", r.text[:800])

        return r.ok

    except Exception as e:
        print("❌ ERRO Evolution:", e)
        return False


# ==================== HEALTH ====================

@app.route("/", methods=["GET"])
def health():
    return "Katana ELITE7 Online 🔪", 200


# ==================== WEBHOOK ====================

@app.route("/webhook", methods=["POST", "GET"])
@app.route("/webhook/messages-upsert", methods=["POST"])
def webhook():

    if request.method == "GET":
        return jsonify({"status": "ok"}), 200

    body = request.get_json(force=True, silent=True)

    if not body:
        return jsonify({"status": "ignored"}), 200

    event = body.get("event")

    # só reage a mensagens novas
    if event not in ["messages.upsert", "MESSAGES_UPSERT"]:
        return jsonify({"status": "ignored_event"}), 200

    try:
        data = body.get("data", {})

        # às vezes vem lista
        if isinstance(data, list):
            if not data:
                return jsonify({"status": "empty"}), 200
            data = data[0]

        key = data.get("key", {})

        # ignora mensagens enviadas pelo próprio bot
        if key.get("fromMe"):
            return jsonify({"status": "self"}), 200

        # 🔥 USAR SENDER SEMPRE (anti-LID definitivo)
        phone = body.get("sender")

        if not phone:
            phone = key.get("remoteJid")

        print("\n📞 Número resolvido:", phone)

        # ================= EXTRAIR TEXTO =================

        msg = data.get("message", {})

        text = (
            msg.get("conversation")
            or msg.get("extendedTextMessage", {}).get("text")
            or msg.get("imageMessage", {}).get("caption")
        )

        if not text:
            return jsonify({"status": "no_text"}), 200

        print("📩 Mensagem:", text)

        # ================= OPENROUTER =================

        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
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
            print("❌ OpenRouter erro:", resp.text)
            reply = "Buguei aqui, tenta de novo 😵"

        # ================= ENVIAR =================

        send_via_evolution(phone, reply)

        return jsonify({"status": "sent"}), 200

    except Exception as e:
        print("❌ ERRO CRÍTICO:", e)
        return jsonify({"error": str(e)}), 200


# ==================== RUN ====================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)