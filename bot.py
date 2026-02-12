# bot.py - Katana ELITE7 (Evolution 1.8.2 FIXED)

import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIG ====================
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4-turbo-preview")

EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "")

BOT_PERSONALITY = os.environ.get(
    "BOT_PERSONALITY",
    "Você é Katana ELITE7, debochada, sarcástica, engraçada e estilo melhor amiga gamer."
)
# =================================================


# ==================== HELPERS ====================

def normalize_phone(raw):
    if not raw:
        return ""

    s = str(raw)
    s = (
        s.replace("@s.whatsapp.net", "")
        .replace("@c.us", "")
        .replace("@lid", "")
        .replace("@g.us", "")
    )

    digits = re.sub(r"\D", "", s)
    return digits


# ==================== EVOLUTION SEND ====================
def send_via_evolution(phone, message):
    """
    Compatível com Evolution v1.8.2
    Agora usa textMessage (obrigatório)
    Suporta número normal + grupos
    """

    base_url = EVOLUTION_API_URL.rstrip('/')
    url = f"{base_url}/message/sendText/{EVOLUTION_INSTANCE}"

    original = str(phone or "")
    clean_number = normalize_phone(original)

    # ===== GRUPO =====
    if "@g.us" in original:
        payload = {
            "groupJid": original,
            "textMessage": {
                "text": message
            }
        }

    # ===== PRIVADO =====
    else:
        payload = {
            "number": clean_number,
            "textMessage": {
                "text": message
            }
        }

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }

    try:
        print(f"\n🚀 Enviando mensagem")
        print("URL:", url)
        print("Payload:", payload)

        r = requests.post(url, headers=headers, json=payload, timeout=15)

        print("Status:", r.status_code)
        print("Resposta:", r.text[:500])

        return r.ok

    except Exception as e:
        print("❌ Erro Evolution:", e)
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

        if isinstance(data, list):
            if not data:
                return jsonify({"status": "empty"}), 200
            data = data[0]

        key = data.get("key", {})

        # ignora mensagens do próprio bot
        if key.get("fromMe"):
            return jsonify({"status": "self"}), 200

        remote_jid = key.get("remoteJid")
        sender = body.get("sender")

        phone = remote_jid

        # FIX LID
        if remote_jid and "@lid" in remote_jid:
            phone = sender or data.get("owner")

        msg = data.get("message", {})

        text = (
            msg.get("conversation")
            or msg.get("extendedTextMessage", {}).get("text")
            or msg.get("imageMessage", {}).get("caption")
        )

        if not text:
            return jsonify({"status": "no_text"}), 200

        print(f"\n📩 Mensagem recebida de {phone}: {text}")

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
            reply = resp.json()['choices'][0]['message']['content']
        else:
            print("Erro OpenRouter:", resp.text)
            reply = "Tô bugada agora, tenta de novo 😵"

        # ================= SEND =================
        send_via_evolution(phone, reply)

        return jsonify({"status": "sent"}), 200

    except Exception as e:
        print("❌ Erro crítico:", e)
        return jsonify({"error": str(e)}), 200


# ==================== RUN ====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)