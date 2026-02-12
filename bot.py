# bot.py - Katana ELITE7 (Evolution v1.8.2 + MongoDB Fix)
import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIGURAÇÃO ====================
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "")
# URL DO SEU EVOLUTION NO RENDER
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = "Lobato155"
EVOLUTION_INSTANCE = "KatanaBot" # Nome da instância que vamos criar

BOT_PERSONALITY = os.environ.get(
    "BOT_PERSONALITY",
    "Você é Katana ELITE7, debochada e zoeira."
)
# =======================================================

def send_via_evolution(phone, message):
    # A v1.8.2 usa esse endpoint padrão
    base_url = EVOLUTION_API_URL.rstrip('/')
    url = f"{base_url}/message/sendText/{EVOLUTION_INSTANCE}"
    
    # Payload Simples (Funciona PERFEITO na v1.8.2)
    payload = {
        "number": phone,
        "text": message
    }
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    try:
        print(f"🚀 Enviando para: {phone}")
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"📊 Status: {r.status_code}")
        return r.ok
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

@app.route("/", methods=["GET"])
def health():
    return "Katana v1.8.2 Online 🔪", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    # O Evolution v1 manda tudo no /webhook se configurado globalmente
    body = request.get_json(force=True, silent=True)
    if not body: return jsonify({"status": "ignored"}), 200

    try:
        # A v1.8.2 geralmente manda o evento type dentro do body ou data
        # Vamos focar em pegar a mensagem
        data = body.get("data", {})
        if not data: return jsonify({"status": "no_data"}), 200
        
        # Ignora mensagem própria
        key = data.get("key", {})
        if key.get("fromMe"): return jsonify({"status": "ignored_self"}), 200

        # Lógica do LID (iPhone)
        remote_jid = key.get("remoteJid")
        sender = body.get("sender") # v1.8.2 costuma mandar o sender na raiz
        
        phone = remote_jid
        if remote_jid and "@lid" in remote_jid:
            if sender:
                phone = sender
            else:
                # Tenta limpar o LID se não tiver sender
                phone = remote_jid # Vai tentar mandar pro LID mesmo se não tiver opção

        # Extrai mensagem
        msg = data.get("message", {})
        text = (
            msg.get("conversation") or 
            msg.get("extendedTextMessage", {}).get("text") or
            msg.get("imageMessage", {}).get("caption")
        )

        if not text: return jsonify({"status": "no_text"}), 200

        print(f"📩 Mensagem de {phone}: {text}")

        # === IA ===
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://katana.app",
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
        reply = resp.json()['choices'][0]['message']['content'] if resp.ok else "Buguei."

        # Envia
        send_via_evolution(phone, reply)
        
        return jsonify({"status": "sent"}), 200

    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({"error": str(e)}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
