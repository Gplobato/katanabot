# bot.py - Katana ELITE7 (Correção para LIDs e IDs estranhos)
import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIGURAÇÃO ====================
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4-turbo-preview")
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE") # Ex: KatanaBot

SYSTEM_PROMPT = """
Você é a Katana ELITE7.
PERSONALIDADE:
- Debochada, zoeira, usa gírias.
- Respostas curtas e diretas.
"""

def enviar_mensagem_evolution(remote_jid, texto):
    if not EVOLUTION_API_URL or not EVOLUTION_INSTANCE:
        print("❌ ERRO: Variáveis de ambiente faltando.")
        return False

    base_url = EVOLUTION_API_URL.rstrip('/')
    url = f"{base_url}/message/sendText/{EVOLUTION_INSTANCE}"
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    # --- MUDANÇA CRUCIAL: NÃO limpamos mais o número ---
    # Enviamos o remote_jid COMPLETO (ex: 1054...@lid ou 5521...@s.whatsapp.net)
    print(f"🚀 Respondendo para o ID original: {remote_jid}")

    # Tenta payload V2 (padrão novo)
    payload_v2 = {
        "number": remote_jid, # Envia o ID sujo mesmo, o Evolution resolve
        "options": {"delay": 1200, "presence": "composing", "linkPreview": False},
        "textMessage": {"text": texto}
    }

    try:
        r = requests.post(url, json=payload_v2, headers=headers, timeout=15)
        
        if r.status_code == 200 or r.status_code == 201:
            print("✅ Sucesso!")
            return True
            
        print(f"⚠️ Falha V2 ({r.status_code}): {r.text}. Tentando modo simples...")
        
        # Fallback (Payload Simples)
        payload_v1 = {
            "number": remote_jid,
            "text": texto,
            "delay": 1200
        }
        r2 = requests.post(url, json=payload_v1, headers=headers, timeout=15)
        return r2.ok

    except Exception as e:
        print(f"❌ Erro de Conexão: {e}")
        return False

def consultar_cerebro_katana(mensagem):
    if not OPENROUTER_KEY: return "Sem chave da IA."
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://katana.app",
            "X-Title": "Katana"
        }
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": mensagem}
                ]
            },
            timeout=20
        )
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content']
        return "Erro na IA."
    except:
        return "IA indisponível."

@app.route("/webhook/messages-upsert", methods=["POST"])
def webhook():
    body = request.get_json(force=True, silent=True)
    if not body: return jsonify({"status": "ignored"}), 200

    try:
        data = body.get("data", {})
        if not data or 'key' not in data: return jsonify({"status": "ignored"}), 200
        
        # Ignora mensagens próprias
        if data['key'].get('fromMe', False): return jsonify({"status": "ignored_self"}), 200

        # --- AQUI ESTÁ O SEGREDO ---
        # Pegamos o remoteJid exato que o WhatsApp mandou.
        # Se for LID (1054...@lid) ou Número (5521...@s.whatsapp.net), tanto faz.
        remote_jid = data['key'].get('remoteJid')
        
        msg = data.get('message', {})
        texto = ""
        if 'conversation' in msg: texto = msg['conversation']
        elif 'extendedTextMessage' in msg: texto = msg['extendedTextMessage'].get('text')
        
        if not texto: return jsonify({"status": "no_text"}), 200

        print(f"📩 Recebido de {remote_jid}: {texto}")
        
        resposta = consultar_cerebro_katana(texto)
        enviar_mensagem_evolution(remote_jid, resposta)
        
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"❌ Erro: {e}")
        return jsonify({"error": str(e)}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
