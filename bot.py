# bot.py - Katana ELITE7 (Versão "Blindada" - Tenta todos os formatos)
import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIGURAÇÃO ====================
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v3.2")
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE") # CERTIFIQUE-SE QUE AS MAIÚSCULAS BATEM!

SYSTEM_PROMPT = """
Você é a Katana ELITE7.
PERSONALIDADE:
- Debochada, zoeira, usa gírias.
- Respostas curtas e diretas.
"""

def limpar_numero(remote_jid):
    if not remote_jid: return ""
    return str(remote_jid).split('@')[0]

def enviar_mensagem_evolution(remote_jid, texto):
    if not EVOLUTION_API_URL or not EVOLUTION_INSTANCE:
        print("❌ ERRO: Faltam variáveis de ambiente (URL ou INSTANCE).")
        return False

    # URL QUE SABEMOS QUE EXISTE (A que deu erro 400 antes, não a 404)
    base_url = EVOLUTION_API_URL.rstrip('/')
    url = f"{base_url}/message/sendText/{EVOLUTION_INSTANCE}"
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    numero_limpo = limpar_numero(remote_jid)
    print(f"🚀 Tentando enviar para {numero_limpo} na instância {EVOLUTION_INSTANCE}...")

    # --- ESTRATÉGIA BLINDADA: TENTATIVA 1 (FORMATO NOVO V2) ---
    payload_v2 = {
        "number": numero_limpo,
        "options": {"delay": 1200, "presence": "composing", "linkPreview": False},
        "textMessage": {"text": texto}
    }

    try:
        r = requests.post(url, json=payload_v2, headers=headers, timeout=15)
        
        if r.status_code == 200 or r.status_code == 201:
            print("✅ Sucesso com Payload V2!")
            return True
            
        print(f"⚠️ Falha V2 ({r.status_code}): {r.text}. Tentando V1...")
        
        # --- ESTRATÉGIA BLINDADA: TENTATIVA 2 (FORMATO ANTIGO V1) ---
        # Se o V2 falhou, pode ser que sua versão queira o simples
        payload_v1 = {
            "number": numero_limpo,
            "text": texto,
            "delay": 1200,
            "linkPreview": False
        }
        
        r2 = requests.post(url, json=payload_v1, headers=headers, timeout=15)
        
        if r2.status_code == 200 or r2.status_code == 201:
            print("✅ Sucesso com Payload V1!")
            return True
            
        print(f"❌ ERRO FINAL ({r2.status_code}): {r2.text}")
        return False

    except Exception as e:
        print(f"❌ Erro de Conexão: {e}")
        return False

def consultar_cerebro_katana(mensagem):
    if not OPENROUTER_KEY: return "Sem chave da IA configurada."
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
    # Pega o JSON mesmo se vier bagunçado
    body = request.get_json(force=True, silent=True)
    if not body: return jsonify({"status": "ignored"}), 200

    try:
        data = body.get("data", {})
        if not data or 'key' not in data: return jsonify({"status": "ignored"}), 200
        
        # Ignora minhas próprias mensagens
        if data['key'].get('fromMe', False): return jsonify({"status": "ignored_self"}), 200

        remote_jid = data['key'].get('remoteJid')
        msg = data.get('message', {})
        
        # Extrai texto de qualquer lugar possível
        texto = ""
        if 'conversation' in msg: texto = msg['conversation']
        elif 'extendedTextMessage' in msg: texto = msg['extendedTextMessage'].get('text')
        
        if not texto: return jsonify({"status": "no_text"}), 200

        print(f"📩 Recebido: {texto}")
        
        resposta = consultar_cerebro_katana(texto)
        enviar_mensagem_evolution(remote_jid, resposta)
        
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"❌ Erro: {e}")
        return jsonify({"error": str(e)}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
