# bot.py - Katana ELITE7 com Evolution API (Versão Final com Fix de LID)
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
    # Remove sufixos para garantir limpeza, mas mantém o número base
    s = str(raw).replace("@s.whatsapp.net", "").replace("@c.us", "").replace("@lid", "")
    digits = re.sub(r"\D", "", s)
    return digits

def send_via_evolution(phone, message):
    # Garante URL correta sem barra dupla
    base_url = EVOLUTION_API_URL.rstrip('/')
    url = f"{base_url}/message/sendText/{EVOLUTION_INSTANCE}"
    
    # Limpa o número para envio (O Evolution v2 gosta apenas dos números)
    # Se o phone já vier limpo (sem @...), essa função só garante que é digito.
    clean_number = normalize_phone(phone)
    
    # Formato correto para Evolution API v1.7.4+
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
        print(f"🚀 Enviando para REAL: {clean_number}")
        # print(f"📤 Payload: {payload}") # Descomente se quiser debug total
        
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        
        print(f"📊 Status Envio: {r.status_code}")
        
        if r.status_code != 200 and r.status_code != 201:
            print(f"⚠️ Erro Evolution: {r.text[:200]}")
            
        return r.ok, r.text
    except Exception as e:
        print(f"❌ Erro no envio Evolution: {e}")
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
@app.route("/webhook/messages-upsert", methods=["POST"]) # Garante compatibilidade
def webhook():
    if request.method == "GET":
        return jsonify({"message": "Webhook ativo. Use POST."}), 200
    
    incoming = request.get_json(force=True, silent=True)
    
    if not incoming:
        return jsonify({"status": "ignored", "reason": "empty payload"}), 200

    print("=" * 60)
    print("📥 WEBHOOK RECEBIDO")

    phone = None
    message = None
    
    try:
        # ===== LÓGICA DE LEITURA (PARSING) =====
        data = incoming.get("data", {})
        
        # 1. Tenta pegar o Remetente Real (SENDER) que vem na raiz do JSON
        # Isso é CRUCIAL para consertar o bug do LID
        real_sender = incoming.get("sender")
        
        # 2. Pega os dados da chave
        key = data.get("key", {})
        remote_jid = key.get("remoteJid") or data.get("remoteJid")
        from_me = key.get("fromMe", False)
        
        if from_me:
            return jsonify({"status": "ignored", "reason": "own message"}), 200

        # === CORREÇÃO DO NÚMERO (LID FIX) ===
        if remote_jid and "@lid" in remote_jid:
            print(f"⚠️ Detectado ID de dispositivo (LID): {remote_jid}")
            if real_sender:
                print(f"🔄 Trocando LID pelo SENDER REAL: {real_sender}")
                phone = real_sender
            else:
                # Se não tiver sender, tenta pegar o owner (outra chance)
                phone = data.get("owner", remote_jid)
        else:
            # Se for grupo ou número normal, segue o jogo
            phone = remote_jid

        # 3. Pega a mensagem
        msg_obj = data.get("message", {})
        message = (
            msg_obj.get("conversation") or
            msg_obj.get("extendedTextMessage", {}).get("text") or
            msg_obj.get("imageMessage", {}).get("caption") or
            msg_obj.get("videoMessage", {}).get("caption")
        )
                
    except Exception as e:
        print(f"❌ Erro ao parsear webhook: {e}")
        return jsonify({"error": "parse error"}), 200

    # Normaliza phone (remove @s.whatsapp.net etc) para ficar limpo
    if phone:
        phone = normalize_phone(phone)
    
    print(f"📱 Phone Final para Envio: {phone}")
    print(f"💬 Mensagem: {message}")

    # Validação
    if not message or not phone:
        print("⚠️ Faltando phone ou message - ignorando")
        return jsonify({"status": "ignored"}), 200

    if not message.strip():
        return jsonify({"status": "ignored", "reason": "empty"}), 200

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
        
        if or_resp.ok:
            or_json = or_resp.json()
            if "choices" in or_json and len(or_json["choices"]) > 0:
                reply = or_json["choices"][0]["message"]["content"]
            else:
                reply = "Buguei aqui."
        else:
            print(f"❌ Erro OpenRouter Status: {or_resp.status_code}")
            reply = "To sem sinal no cérebro."
            
    except Exception as e:
        print(f"❌ Erro OpenRouter Exception: {e}")
        reply = "Erro fatal na IA."

    # ===== ENVIA RESPOSTA VIA EVOLUTION =====
    if reply:
        ok, info = send_via_evolution(phone, reply.strip())
        print(f"✅ Ciclo concluído. Enviado: {ok}")
    
    return jsonify({"status": "sent"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
