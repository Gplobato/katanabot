# bot.py - Katana ELITE7 com Evolution API - VERSÃO FINAL CORRIGIDA
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
    
    # Mantém o formato original se tiver @
    if "@" in str(raw):
        return str(raw)
    
    # Remove tudo que não é número
    digits = re.sub(r"\D", "", str(raw))
    
    print(f"🔢 Raw: {raw} → Normalizado: {digits}")
    return digits

def send_via_evolution(remote_jid, message):
    """
    remote_jid pode ser:
    - 5511999999999@s.whatsapp.net (individual)
    - 123456789@g.us (grupo)
    - 72439623090228@lid (canal - vamos tentar enviar mesmo assim)
    """
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    
    # Remove @ e pega só o número
    clean_number = remote_jid.split('@')[0] if '@' in remote_jid else remote_jid
    
    # Formato 1: Tenta com textMessage
    payload1 = {
        "number": clean_number,
        "textMessage": {
            "text": message
        }
    }
    
    # Formato 2: Tenta formato alternativo
    payload2 = {
        "number": clean_number,
        "text": message
    }
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    try:
        print(f"🚀 Enviando mensagem...")
        print(f"📤 Remote JID original: {remote_jid}")
        print(f"📤 Número limpo: {clean_number}")
        print(f"📤 URL: {url}")
        
        # Tenta formato 1
        print(f"📤 Tentativa 1 - Payload: {payload1}")
        r1 = requests.post(url, headers=headers, json=payload1, timeout=15)
        print(f"📊 Status formato 1: {r1.status_code}")
        print(f"📋 Resposta formato 1: {r1.text}")
        
        if r1.ok:
            return True, r1.text
        
        # Se falhou, tenta formato 2
        print(f"⚠️ Formato 1 falhou, tentando formato 2...")
        print(f"📤 Tentativa 2 - Payload: {payload2}")
        r2 = requests.post(url, headers=headers, json=payload2, timeout=15)
        print(f"📊 Status formato 2: {r2.status_code}")
        print(f"📋 Resposta formato 2: {r2.text}")
        
        if r2.ok:
            return True, r2.text
        
        # Se ambos falharam, retorna o erro do último
        return False, r2.text
        
    except Exception as e:
        print(f"❌ Erro no envio: {e}")
        return False, str(e)

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "bot": "Katana ELITE7",
        "endpoints": ["/webhook"],
        "evolution_configured": bool(EVOLUTION_API_URL and EVOLUTION_API_KEY)
    }), 200

@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        return jsonify({"message": "Webhook ativo. Use POST para enviar mensagens."}), 200
    
    incoming = request.get_json(force=True, silent=True)
    
    print("=" * 60)
    print("📥 WEBHOOK RECEBIDO")
    print("=" * 60)
    print(f"Payload completo: {incoming}")
    print("=" * 60)

    if not incoming:
        print("⚠️ Payload vazio - ignorando")
        return jsonify({"status": "ignored", "reason": "empty payload"}), 200

    remote_jid = None
    message = None
    
    try:
        # Pega o evento
        event = incoming.get("event", "")
        print(f"🔔 Evento: {event}")
        
        # Só processa se for mensagem
        if "data" in incoming and isinstance(incoming["data"], dict):
            data = incoming["data"]
            
            # Pega o remote JID (mantém o formato completo)
            remote_jid = data.get("key", {}).get("remoteJid")
            
            print(f"📱 Remote JID detectado: {remote_jid}")
            
            # Ignora se for mensagem própria
            if data.get("key", {}).get("fromMe"):
                print("⚠️ Mensagem própria - ignorando")
                return jsonify({"status": "ignored", "reason": "own message"}), 200
            
            # Pega a mensagem
            if "message" in data and isinstance(data["message"], dict):
                msg_obj = data["message"]
                message = (
                    msg_obj.get("conversation") or
                    msg_obj.get("extendedTextMessage", {}).get("text") or
                    msg_obj.get("imageMessage", {}).get("caption") or
                    msg_obj.get("videoMessage", {}).get("caption")
                )
                
    except Exception as e:
        print(f"❌ Erro ao parsear webhook: {e}")

    print(f"📱 Remote JID final: {remote_jid}")
    print(f"💬 Mensagem extraída: {message}")
    print("=" * 60)

    # Validação
    if not message or not remote_jid:
        print("⚠️ Faltando remote_jid ou message - ignorando")
        return jsonify({"status": "ignored", "reason": "no jid or no message"}), 200

    # Ignora mensagens vazias
    if not message.strip():
        print("⚠️ Mensagem vazia - ignorando")
        return jsonify({"status": "ignored", "reason": "empty message"}), 200

    # ===== CHAMA OPENROUTER =====
    reply = ""
    try:
        print("🤖 Chamando OpenRouter...")
        or_resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://katana-elite7.app",
                "X-Title": "Katana ELITE7"
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": BOT_PERSONALITY},
                    {"role": "user", "content": message}
                ],
                "temperature": 0.8,
                "max_tokens": 500
            },
            timeout=25
        )
        
        print(f"📊 OpenRouter status: {or_resp.status_code}")
        
        if or_resp.ok:
            or_json = or_resp.json()
            if "choices" in or_json and len(or_json["choices"]) > 0:
                reply = or_json["choices"][0]["message"]["content"]
            else:
                reply = "Desculpa, deu algum erro na minha cabeça 🤯"
        else:
            reply = "Opa, tô com um problema técnico aqui 😅"
            
    except Exception as e:
        print(f"❌ Erro OpenRouter: {e}")
        reply = "Caralho, bugou tudo aqui 😂 Tenta de novo!"

    if not reply or not reply.strip():
        reply = "Fiquei sem palavras agora kkkk"

    # ===== ENVIA RESPOSTA =====
    ok, info = send_via_evolution(remote_jid, reply.strip())
    
    print(f"{'✅' if ok else '❌'} Resposta enviada: {ok}")
    print("=" * 60)

    return jsonify({
        "status": "sent" if ok else "error",
        "remote_jid": remote_jid,
        "reply": reply[:100],
        "detail": str(info)[:200]
    }), 200

@app.route("/webhook/messages-upsert", methods=["POST"])
def webhook_messages():
    return webhook()

@app.route("/webhook/message-create", methods=["POST"])
def webhook_message_create():
    return webhook()

@app.route("/webhook/qrcode-updated", methods=["POST"])
def webhook_qrcode():
    return jsonify({"status": "ignored"}), 200

if __name__ == "__main__":
    print("=" * 60)
    print("🔍 VERIFICAÇÃO DE CONFIGURAÇÃO")
    print("=" * 60)
    print(f"OPENROUTER_KEY: {'✅ OK' if OPENROUTER_KEY else '❌ FALTANDO'}")
    print(f"EVOLUTION_API_URL: {'✅ OK' if EVOLUTION_API_URL else '❌ FALTANDO'}")
    print(f"EVOLUTION_API_KEY: {'✅ OK' if EVOLUTION_API_KEY else '❌ FALTANDO'}")
    print(f"EVOLUTION_INSTANCE: {EVOLUTION_INSTANCE}")
    print(f"MODEL: {OPENROUTER_MODEL}")
    print("=" * 60)
    
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor rodando na porta {port}")
    app.run(host="0.0.0.0", port=port)