# bot.py - Katana ELITE7 (Correção DEFINITIVA DE LID/IPHONE)
import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIGURAÇÃO ====================
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "")
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "")
BOT_PERSONALITY = os.environ.get(
    "BOT_PERSONALITY",
    "Você é Katana ELITE7, uma chatbot muito divertida e zuadeira, que zoa todo mundo e é debochada."
)
# =======================================================

def normalize_phone(raw):
    if not raw:
        return ""
    # Remove sufixos para limpar
    phone = str(raw).replace("@s.whatsapp.net", "").replace("@c.us", "").replace("@g.us", "").replace("@lid", "")
    # Remove não-números
    digits = re.sub(r"\D", "", phone)
    return digits

def send_via_evolution(phone, message):
    # Garante que estamos enviando para o endpoint correto
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    
    # Limpa o número para envio (O Evolution v2 gosta apenas dos números)
    clean_number = normalize_phone(phone)
    
    payload = {
        "number": clean_number,
        "options": {
            "delay": 1200,
            "presence": "composing",
            "linkPreview": False
        },
        "textMessage": {
            "text": message
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    try:
        print(f"🚀 Enviando para REAL: {clean_number}")
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"📊 Status Envio: {r.status_code}")
        
        if r.status_code != 200 and r.status_code != 201:
            print(f"⚠️ Erro Evolution: {r.text}")
            
        return r.ok, r.text
    except Exception as e:
        print(f"❌ Erro Request: {e}")
        return False, str(e)

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "online", "bot": "Katana ELITE7"}), 200

@app.route("/webhook", methods=["POST"])
@app.route("/webhook/messages-upsert", methods=["POST"])
def webhook():
    # Pega o JSON forçando erro se vier vazio
    incoming = request.get_json(force=True, silent=True)
    
    if not incoming:
        return jsonify({"status": "ignored"}), 200

    # Log simplificado para não poluir
    print("📥 Webhook recebido...")

    phone = None
    message = None
    is_lid = False
    
    try:
        # Tenta pegar o SENDER (Remetente Real) que vem na raiz do JSON do Evolution
        # Isso salva a pátria quando o remoteJid é um LID (@lid)
        real_sender = incoming.get("sender")
        
        data = incoming.get("data", {})
        if not data:
            return jsonify({"status": "ignored"}), 200
            
        # Pega o remoteJid (que pode ser o tal do LID bugado)
        key = data.get("key", {})
        remote_jid = key.get("remoteJid")
        from_me = key.get("fromMe", False)
        
        if from_me:
            return jsonify({"status": "ignored_self"}), 200

        # === AQUI ESTÁ A CORREÇÃO MÁGICA ===
        if remote_jid and "@lid" in remote_jid:
            print(f"⚠️ Detectado ID de dispositivo (LID): {remote_jid}")
            is_lid = True
            if real_sender:
                print(f"🔄 Trocando LID pelo SENDER REAL: {real_sender}")
                phone = real_sender
            else:
                # Se não tiver sender, tenta pegar o user do owner (se existir)
                print("⚠️ Sender não encontrado, tentando owner...")
                phone = data.get("owner", remote_jid)
        else:
            # Se não for LID, usa o JID normal
            phone = remote_jid

        # Extração da mensagem
        msg_obj = data.get("message", {})
        message = (
            msg_obj.get("conversation") or
            msg_obj.get("extendedTextMessage", {}).get("text") or
            msg_obj.get("imageMessage", {}).get("caption")
        )

    except Exception as e:
        print(f"❌ Erro parsing: {e}")
        return jsonify({"error": "parse error"}), 200

    if not phone or not message:
        return jsonify({"status": "no_data"}), 200

    print(f"👤 De (Final): {phone}")
    print(f"💬 Diz: {message}")

    # === CÉREBRO DA KATANA (OpenRouter) ===
    reply = "Buguei."
    try:
        print("🤖 Pensando...")
        or_resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://katana.bot",
                "X-Title": "Katana"
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": BOT_PERSONALITY},
                    {"role": "user", "content": message}
                ]
            },
            timeout=20
        )
        if or_resp.ok:
            reply = or_resp.json()["choices"][0]["message"]["content"]
        else:
            print(f"❌ Erro AI: {or_resp.text}")
            reply = "To sem sinal no cérebro agora."
    except Exception as e:
        print(f"❌ Erro AI Request: {e}")
    
    # === ENVIO ===
    send_via_evolution(phone, reply)

    return jsonify({"status": "sent"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
