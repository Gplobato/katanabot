# bot.py - Katana ELITE7 (Corrigido para rota messages-upsert)
import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIGURAÇÃO ====================
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4-turbo-preview") # Coloquei um default bom
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
    s = str(raw).split('@')[0]
    digits = re.sub(r"\D", "", s)
    if not s.endswith('@s.whatsapp.net'):
        return f"{digits}@s.whatsapp.net"
    return s

def send_via_evolution(phone, message):
    # Ajuste na URL para garantir que não tenha barra dupla
    base_url = EVOLUTION_API_URL.rstrip('/')
    url = f"{base_url}/message/sendText/{EVOLUTION_INSTANCE}"
    
    payload = {
        "number": phone,
        "text": message,
        "delay": 1200,
        "linkPreview": False
    }
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    try:
        print(f"🚀 Enviando para: {phone}")
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"📊 Status Evolution: {r.status_code}")
        return r.ok, r.text
    except Exception as e:
        print(f"❌ Erro no envio Evolution: {e}")
        return False, str(e)

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "online", "bot": "Katana ELITE7"}), 200

# === CORREÇÃO AQUI: Adicionei /messages-upsert ===
@app.route("/webhook/messages-upsert", methods=["POST"])
def webhook():
    # O Evolution manda o JSON direto, às vezes sem content-type correto, o force=True ajuda
    incoming = request.get_json(force=True, silent=True)
    
    print("=" * 30)
    print("📥 WEBHOOK RECEBIDO")

    if not incoming:
        return jsonify({"status": "ignored"}), 200

    phone = None
    message = None
    
    try:
        # Lógica para pegar dados do Evolution (Message Upsert)
        data = incoming.get("data", {})
        
        # Ignora status update ou outros eventos que não têm 'key'
        if not data or 'key' not in data:
            return jsonify({"status": "ignored", "reason": "not a message"}), 200

        # Verifica se fui EU que mandei (fromMe)
        if data['key'].get('fromMe', False):
            print("⚠️ Mensagem própria ignorada.")
            return jsonify({"status": "ignored_self"}), 200

        phone = data['key'].get('remoteJid')
        
        # Extração de mensagem (Texto, Extended, Conversation)
        msg_obj = data.get('message', {})
        
        if 'conversation' in msg_obj:
            message = msg_obj['conversation']
        elif 'extendedTextMessage' in msg_obj:
            message = msg_obj['extendedTextMessage'].get('text')
        elif 'imageMessage' in msg_obj:
             message = msg_obj['imageMessage'].get('caption')
        
        if not message:
            return jsonify({"status": "no_text"}), 200

    except Exception as e:
        print(f"❌ Erro parsing: {e}")
        return jsonify({"error": "parse_error"}), 200

    phone = normalize_phone(phone)
    print(f"👤 De: {phone}")
    print(f"💬 Diz: {message}")

    # ===== OPENROUTER =====
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://katana-bot.site", # Exigido pelo OpenRouter as vezes
            "X-Title": "Katana Bot"
        }
        
        data_ai = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": BOT_PERSONALITY},
                {"role": "user", "content": message}
            ]
        }
        
        print("🤖 Perguntando pra IA...")
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data_ai, timeout=20)
        
        if resp.status_code == 200:
            reply = resp.json()['choices'][0]['message']['content']
        else:
            print(f"Erro IA: {resp.text}")
            reply = "Oxe, buguei aqui. Tenta de novo."
            
    except Exception as e:
        print(f"Erro request IA: {e}")
        reply = "Deu ruim no meu cérebro."

    # ===== RESPOSTA =====
    send_via_evolution(phone, reply)
    
    return jsonify({"status": "sent"}), 200

if __name__ == "__main__":
    # O Render define a porta na variável PORT (geralmente 10000)
    # Se não definir, usamos 8080.
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
