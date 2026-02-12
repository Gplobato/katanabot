from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime

app = Flask(__name__)

# ====== CONFIGURAÇÕES ======
EVOLUTION_URL = os.getenv('EVOLUTION_URL')  # Ex: https://seu-evolution.com
EVOLUTION_API_KEY = os.getenv('EVOLUTION_API_KEY')
EVOLUTION_INSTANCE = os.getenv('EVOLUTION_INSTANCE')  # Ex: katana
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

# Configuração da IA
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODEL = "deepseek/deepseek-v3.2"  # DeepSeek 3.2

# Personalidade do bot
SYSTEM_PROMPT = """Você é a Katana, uma assistente virtual descontraída e amigável. 
Seja natural, use emojis ocasionalmente e mantenha conversas agradáveis.
Seja prestativa mas sem exageros."""

# Armazenamento simples de conversas (em produção use Redis/Database)
conversations = {}

# ====== FUNÇÕES AUXILIARES ======

def log(message):
    """Log com timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def get_conversation_history(phone):
    """Obtém histórico da conversa"""
    if phone not in conversations:
        conversations[phone] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    return conversations[phone]

def add_to_history(phone, role, content):
    """Adiciona mensagem ao histórico"""
    history = get_conversation_history(phone)
    history.append({"role": role, "content": content})
    
    # Limita histórico a 20 mensagens (10 trocas)
    if len(history) > 21:  # 1 system + 20 mensagens
        history = [history[0]] + history[-20:]
        conversations[phone] = history

def chat_with_ai(phone, user_message):
    """Envia mensagem para OpenRouter e retorna resposta"""
    try:
        # Adiciona mensagem do usuário ao histórico
        add_to_history(phone, "user", user_message)
        
        # Prepara requisição
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://katanabot.onrender.com",
            "X-Title": "KatanaBot"
        }
        
        payload = {
            "model": AI_MODEL,
            "messages": get_conversation_history(phone),
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        log(f"🤖 Enviando para OpenRouter...")
        response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            ai_response = response.json()['choices'][0]['message']['content']
            
            # Adiciona resposta da IA ao histórico
            add_to_history(phone, "assistant", ai_response)
            
            log(f"✅ IA respondeu: {ai_response[:100]}...")
            return ai_response
        else:
            log(f"❌ Erro OpenRouter: {response.status_code} - {response.text}")
            return "Desculpe, estou com problemas técnicos no momento. Tente novamente em instantes."
            
    except Exception as e:
        log(f"❌ Erro ao chamar IA: {str(e)}")
        return "Ops, algo deu errado. Por favor, tente novamente."

def send_whatsapp_message(phone, message):
    """Envia mensagem pelo Evolution API"""
    try:
        # Remove @s.whatsapp.net se existir
        clean_phone = phone.replace('@s.whatsapp.net', '').replace('@g.us', '')
        
        url = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"
        
        headers = {
            "Content-Type": "application/json",
            "apikey": EVOLUTION_API_KEY
        }
        
        payload = {
            "number": clean_phone,
            "text": message,
            "delay": 1200
        }
        
        log(f"🚀 Enviando para {clean_phone}...")
        log(f"📍 URL: {url}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        log(f"📊 Status Envio: {response.status_code}")
        
        if response.status_code in [200, 201]:
            log(f"✅ Mensagem enviada com sucesso!")
            return True
        else:
            log(f"❌ Erro ao enviar: {response.text}")
            return False
            
    except Exception as e:
        log(f"❌ Erro no envio: {str(e)}")
        return False

# ====== ROTAS DA API ======

@app.route('/', methods=['GET'])
def home():
    """Endpoint de verificação"""
    return jsonify({
        "status": "online",
        "bot": "KatanaBot",
        "version": "2.0",
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check para Render"""
    return jsonify({"status": "healthy"}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook principal - recebe eventos do Evolution API"""
    try:
        data = request.json
        log(f"\n{'='*60}")
        log(f"📨 Webhook recebido: {data.get('event', 'unknown')}")
        
        # Verifica se é mensagem nova
        event = data.get('event')
        
        if event == 'messages.upsert':
            return handle_message(data)
        
        return jsonify({"status": "event_ignored"}), 200
        
    except Exception as e:
        log(f"❌ Erro no webhook: {str(e)}")
        return jsonify({"error": str(e)}), 500

def handle_message(data):
    """Processa mensagem recebida"""
    try:
        # Extrai dados da mensagem
        message_data = data.get('data', {})
        
        # Suporta diferentes estruturas do Evolution
        if 'message' in message_data:
            msg = message_data['message']
            key = message_data.get('key', {})
        else:
            msg = message_data
            key = message_data.get('key', {})
        
        # Pega informações do remetente
        remote_jid = key.get('remoteJid', '')
        from_me = key.get('fromMe', False)
        
        # Ignora mensagens enviadas pelo bot
        if from_me:
            log("⏭️  Ignorando mensagem própria")
            return jsonify({"status": "ignored_own_message"}), 200
        
        # Ignora grupos (opcional - remova se quiser responder em grupos)
        if '@g.us' in remote_jid:
            log("⏭️  Ignorando mensagem de grupo")
            return jsonify({"status": "ignored_group"}), 200
        
        # Extrai texto da mensagem
        text_message = None
        
        if 'conversation' in msg:
            text_message = msg['conversation']
        elif 'extendedTextMessage' in msg:
            text_message = msg['extendedTextMessage'].get('text', '')
        elif 'text' in msg:
            text_message = msg['text']
        
        if not text_message or text_message.strip() == '':
            log("⏭️  Mensagem sem texto")
            return jsonify({"status": "no_text"}), 200
        
        # Extrai número do telefone
        phone = remote_jid.split('@')[0]
        
        log(f"\n📞 Mensagem de: {phone}")
        log(f"📩 Usuário disse: {text_message}")
        
        # Processa com IA
        ai_response = chat_with_ai(phone, text_message)
        
        log(f"🤖 Katana respondeu: {ai_response}")
        
        # Envia resposta
        send_whatsapp_message(remote_jid, ai_response)
        
        return jsonify({"status": "processed"}), 200
        
    except Exception as e:
        log(f"❌ Erro ao processar mensagem: {str(e)}")
        import traceback
        log(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/clear/<phone>', methods=['POST'])
def clear_history(phone):
    """Limpa histórico de conversa (útil para testes)"""
    if phone in conversations:
        del conversations[phone]
        log(f"🗑️  Histórico limpo para {phone}")
        return jsonify({"status": "cleared", "phone": phone}), 200
    return jsonify({"status": "not_found"}), 404

# ====== INICIALIZAÇÃO ======

if __name__ == '__main__':
    log("\n" + "="*60)
    log("🚀 KATANABOT INICIANDO...")
    log("="*60)
    log(f"📍 Evolution URL: {EVOLUTION_URL}")
    log(f"📱 Instância: {EVOLUTION_INSTANCE}")
    log(f"🤖 Modelo IA: {AI_MODEL}")
    log("="*60 + "\n")
    
    # Valida variáveis de ambiente
    required_vars = ['EVOLUTION_URL', 'EVOLUTION_API_KEY', 'EVOLUTION_INSTANCE', 'OPENROUTER_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        log(f"❌ ERRO: Variáveis faltando: {', '.join(missing_vars)}")
        log("⚠️  Configure todas as variáveis de ambiente no Render!")
    else:
        log("✅ Todas as variáveis configuradas!")
    
    # Porta do Render
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)