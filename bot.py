# bot.py - Katana ELITE7 (Correção do Erro 400 - textMessage)
import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIGURAÇÃO ====================
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v3.2")
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE")

SYSTEM_PROMPT = """
Você é a Katana ELITE7.
PERSONALIDADE:
- Debochada, zoeira, usa gírias (tankar, cringe, mds).
- Se o usuário falar besteira, zoa ele.
- Respostas curtas.
"""

def limpar_numero(remote_jid):
    if not remote_jid:
        return ""
    return str(remote_jid).split('@')[0]

def enviar_mensagem_evolution(remote_jid, texto):
    if not EVOLUTION_API_URL or not EVOLUTION_INSTANCE:
        print("❌ Configurações do Evolution faltando.")
        return False

    # === MUDANÇA IMPORTANTE: Usando o endpoint genérico /send ===
    base_url = EVOLUTION_API_URL.rstrip('/')
    url = f"{base_url}/message/send/{EVOLUTION_INSTANCE}"

    numero_limpo = limpar_numero(remote_jid)

    # === O PAYLOAD QUE O EVOLUTION V2 EXIGE ===
    payload = {
        "number": numero_limpo,
        "options": {
            "delay": 1200,
            "presence": "composing",
            "linkPreview": False
        },
        "textMessage": {
            "text": texto
        }
    }

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }

    try:
        print(f"🚀 Enviando (Endpoint /send) para: {numero_limpo}...")
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code != 200 and response.status_code != 201:
            print(f"⚠️ ERRO EVOLUTION ({response.status_code}): {response.text}")
        else:
            print(f"✅ Mensagem enviada!")
            
        return response.ok
    except Exception as e:
        print(f"❌ Erro Conexão: {e}")
        return False

def consultar_cerebro_katana(mensagem_usuario):
    if not OPENROUTER_KEY: return "Sem chave da IA."
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://katana.app",
        "X-Title": "Katana"
    }
    
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": mensagem_usuario}
                ]
            },
            timeout=20
        )
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content']
        return "Buguei aqui."
    except:
        return "Erro na IA."

@app.route("/webhook/messages-upsert", methods=["POST"])
def webhook():
    body = request.get_json(force=True, silent=True)
    if not body: return jsonify({"status": "ignored"}), 200

    try:
        data = body.get("data", {})
        if not data or 'key' not in data: return jsonify({"status": "ignored"}), 200
        if data['key'].get('fromMe', False): return jsonify({"status": "ignored_self"}), 200

        remote_jid = data['key'].get('remoteJid')
        msg = data.get('message', {})
        
        texto = ""
        if 'conversation' in msg: texto = msg['conversation']
        elif 'extendedTextMessage' in msg: texto = msg['extendedTextMessage'].get('text')
        
        if not texto: return jsonify({"status": "no_text"}), 200

        print(f"📩 Recebido: {texto}")
        resposta = consultar_cerebro_katana(texto)
        enviar_mensagem_evolution(remote_jid, resposta)
        
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({"error": str(e)}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
