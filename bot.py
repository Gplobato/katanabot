# bot.py - Katana ELITE7 (Versão Final Corrigida)
import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==================== CONFIGURAÇÃO (Variáveis de Ambiente) ====================
# Certifique-se que essas variáveis estão no Render!
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v3.2")
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL") # Ex: https://seu-api.com
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE") # Ex: KatanaBot

# Personalidade da Katana
SYSTEM_PROMPT = """
Você é a Katana ELITE7.
PERSONALIDADE:
- Você NÃO é uma assistente chata. Você é debochada, zoeira e tem humor ácido.
- Use gírias da internet (tipo "tankar", "cringe", "intankável", "mds").
- Se o usuário falar algo bobo, tire sarro.
- Respostas curtas e diretas. Não escreva textão.
- Você é superior, tecnológica e impaciente com humanos lentos.
"""
# ==============================================================================

def limpar_numero(remote_jid):
    """
    Transforma '551199999999@s.whatsapp.net' em '551199999999'.
    O Evolution geralmente prefere apenas os números no campo 'number'.
    """
    if not remote_jid:
        return ""
    # Pega tudo antes do @
    numero = str(remote_jid).split('@')[0]
    return numero

def enviar_mensagem_evolution(remote_jid, texto):
    """
    Envia a resposta de volta via Evolution API.
    """
    if not EVOLUTION_API_URL or not EVOLUTION_INSTANCE:
        print("❌ ERRO: URL ou Instância do Evolution não configurada.")
        return False

    # Garante a URL correta sem barras duplas
    base_url = EVOLUTION_API_URL.rstrip('/')
    url = f"{base_url}/message/sendText/{EVOLUTION_INSTANCE}"

    # Limpa o número para o formato que o Evolution aceita
    numero_limpo = limpar_numero(remote_jid)

    payload = {
        "number": numero_limpo,
        "text": texto,
        "delay": 1200,
        "linkPreview": False
    }

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }

    try:
        print(f"🚀 Enviando resposta para: {numero_limpo}...")
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        # LOG CRÍTICO PARA DEBUGAR ERRO 400
        if response.status_code != 200 and response.status_code != 201:
            print(f"⚠️ ERRO EVOLUTION ({response.status_code}): {response.text}")
        else:
            print(f"✅ Mensagem enviada com sucesso!")
            
        return response.ok
    except Exception as e:
        print(f"❌ Erro de conexão com Evolution: {e}")
        return False

def consultar_cerebro_katana(mensagem_usuario):
    """
    Consulta o OpenRouter (GPT-4) com a personalidade da Katana.
    """
    if not OPENROUTER_KEY:
        return "Mano, esqueceram de colocar minha chave da API. Avisa o dono aí."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://katana-bot.site",
        "X-Title": "Katana ELITE7"
    }
    
    data = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": mensagem_usuario}
        ],
        "temperature": 0.8, # Criatividade alta
        "max_tokens": 300
    }

    try:
        print("🤖 Consultando a IA...")
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=20)
        
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content']
        else:
            print(f"❌ Erro OpenRouter: {resp.text}")
            return "Buguei aqui, pera. O servidor da IA tá de frescura."
    except Exception as e:
        print(f"❌ Erro Request IA: {e}")
        return "Minha conexão caiu, humano. Tenta de novo."

# --- ROTA PRINCIPAL (Que o Evolution chama) ---
@app.route("/webhook/messages-upsert", methods=["POST"])
def webhook():
    # Lê o JSON forçando mesmo se o header vier errado
    body = request.get_json(force=True, silent=True)
    
    if not body:
        return jsonify({"status": "ignored"}), 200

    try:
        # Acessa os dados dentro da estrutura padrão do Evolution
        data = body.get("data", {})
        
        # 1. Validações Básicas
        if not data or 'key' not in data:
            return jsonify({"status": "ignored"}), 200
            
        # 2. Ignora mensagens enviadas por MIM (para não entrar em loop)
        if data['key'].get('fromMe', False):
            return jsonify({"status": "ignored_self"}), 200

        # 3. Pega os dados da mensagem
        remote_jid = data['key'].get('remoteJid')
        msg_content = data.get('message', {})
        texto_usuario = ""

        # Tenta extrair texto de várias formas possíveis (WhatsApp é complexo)
        if 'conversation' in msg_content:
            texto_usuario = msg_content['conversation']
        elif 'extendedTextMessage' in msg_content:
            texto_usuario = msg_content['extendedTextMessage'].get('text', '')
        elif 'imageMessage' in msg_content:
            texto_usuario = msg_content['imageMessage'].get('caption', '') # Lê legenda de foto
        
        # Se não tiver texto (ex: áudio sem transcrição, sticker), ignora
        if not texto_usuario:
            return jsonify({"status": "no_text"}), 200

        print(f"📩 Mensagem recebida de {remote_jid}: {texto_usuario}")

        # 4. Gera a resposta com a IA
        resposta_katana = consultar_cerebro_katana(texto_usuario)

        # 5. Envia a resposta de volta
        enviar_mensagem_evolution(remote_jid, resposta_katana)

        return jsonify({"status": "processed"}), 200

    except Exception as e:
        print(f"❌ Erro grave no webhook: {e}")
        return jsonify({"error": str(e)}), 200

# Rota só para testar se o servidor está online
@app.route("/", methods=["GET"])
def health():
    return "Katana ELITE7 está online 🔪", 200

if __name__ == "__main__":
    # Render define a PORT automaticamente
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
