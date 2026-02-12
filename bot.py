# bot.py - Katana ELITE7 (Blindado e Otimizado para Evolution v1.8.2)
import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIGURAÇÃO ====================
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4-turbo-preview")
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "")

BOT_PERSONALITY = os.environ.get(
    "BOT_PERSONALITY",
    "Você é Katana ELITE7, debochada e zoeira."
)
# =======================================================

def normalize_phone(raw):
    if not raw: return ""
    # Limpa todos os sufixos para garantir que o Evolution não se engasga
    s = str(raw).replace("@s.whatsapp.net", "").replace("@c.us", "").replace("@lid", "").replace("@g.us", "")
    digits = re.sub(r"\D", "", s)
    return digits

def send_via_evolution(phone, message):
    base_url = EVOLUTION_API_URL.rstrip('/')
    url = f"{base_url}/message/sendText/{EVOLUTION_INSTANCE}"
    
    clean_number = normalize_phone(phone)
    
    # 🎯 FIX DO ERRO 400: Payload exato da v1.8.2 (Simples e direto)
    payload = {
        "number": clean_number,
        "text": message
    }
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    try:
        print(f"🚀 A enviar para: {clean_number}")
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        
        print(f"📊 Status Envio: {r.status_code}")
        if not r.ok:
            print(f"❌ Erro da Evolution: {r.text[:200]}")
            
        return r.ok
    except Exception as e:
        print(f"❌ Erro de conexão Evolution: {e}")
        return False

@app.route("/", methods=["GET"])
def health():
    return "Katana ELITE7 (v1.8.2) Online 🔪", 200

# 🎯 FIX DO ERRO 404: Escuta ambas as rotas de webhook
@app.route("/webhook", methods=["POST", "GET"])
@app.route("/webhook/messages-upsert", methods=["POST"])
def webhook():
    if request.method == "GET":
        return jsonify({"status": "ok"}), 200

    body = request.get_json(force=True, silent=True)
    if not body: return jsonify({"status": "ignored"}), 200

    # 🎯 FIX DO ERRO 'list': Filtra apenas mensagens e ignora atualizações de status/chat
    event = body.get("event")
    if event and event != "messages.upsert" and event != "MESSAGES_UPSERT":
        return jsonify({"status": "ignored_event"}), 200

    try:
        data = body.get("data", {})
        
        # Proteção extra: se for uma lista (mesmo após o filtro), pega apenas o primeiro item
        if isinstance(data, list):
            if len(data) > 0:
                data = data[0]
            else:
                return jsonify({"status": "ignored_empty_list"}), 200

        # Se continuar a não ser um dicionário, aborta para não quebrar
        if not isinstance(data, dict):
            return jsonify({"status": "ignored_not_dict"}), 200

        key = data.get("key", {})
        
        # Ignora mensagens enviadas pelo próprio bot
        if key.get("fromMe"): return jsonify({"status": "ignored_self"}), 200

        # === FIX DO LID (iPhones/Dispositivos Vinculados) ===
        remote_jid = key.get("remoteJid")
        sender = body.get("sender")
        
        phone = remote_jid
        if remote_jid and "@lid" in remote_jid:
            if sender:
                phone = sender
            else:
                phone = data.get("owner", remote_jid)

        # === EXTRAÇÃO DA MENSAGEM ===
        msg = data.get("message", {})
        text = (
            msg.get("conversation") or 
            msg.get("extendedTextMessage", {}).get("text") or
            msg.get("imageMessage", {}).get("caption")
        )

        if not text: return jsonify({"status": "no_text"}), 200

        print(f"📩 Mensagem recebida de {phone}: {text}")

        # === CÉREBRO DA IA (OpenRouter) ===
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://katanabot.com",
            "X-Title": "Katana Bot",
        }
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": OPENROUTER_MODEL,
                "messages": [{"role": "system", "content": BOT_PERSONALITY}, {"role": "user", "content": text}]
            },
            timeout=20
        )
        reply = resp.json()['choices'][0]['message']['content'] if resp.ok else "Tô meio bugada agora."

        # === ENVIAR A RESPOSTA ===
        send_via_evolution(phone, reply)
        
        return jsonify({"status": "sent"}), 200

    except Exception as e:
        print(f"❌ Erro crítico no código: {e}")
        return jsonify({"error": str(e)}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
