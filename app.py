"""
LIA — Backend de voz (ElevenLabs proxy)
-------------------------------------------
Este servidor guarda a chave do ElevenLabs em uma variável de ambiente
(NUNCA no código) e faz a ponte entre o front-end da Lia e a API de voz.
O navegador nunca vê a chave.

COMO RODAR (local):
    1. pip install -r requirements.txt
    2. Defina a chave como variável de ambiente:
         Linux/Mac:  export ELEVENLABS_API_KEY="sk_sua_chave_nova_aqui"
         Windows:    set ELEVENLABS_API_KEY=sk_sua_chave_nova_aqui
    3. python app.py
    4. Abra http://localhost:5000 no navegador

A Lia (index.html) é servida por este mesmo servidor, então tudo
funciona junto sem configuração extra de CORS.
"""

import os
from pathlib import Path
import requests
from flask import Flask, request, jsonify, Response, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="")

# ----- Configuração -----
# Chaves vêm do AMBIENTE, nunca escritas aqui.
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

ELEVEN_BASE = "https://api.elevenlabs.io/v1"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")
# Modelo multilíngue (suporta português). Flash é mais rápido/barato.
DEFAULT_MODEL = "eleven_multilingual_v2"

ABOUT_ME_PATH = Path(__file__).parent / "about_me.md"


def load_about_me() -> str:
    try:
        return ABOUT_ME_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/health")
def health():
    """Confere se a chave está configurada (sem revelá-la)."""
    return jsonify({
        "ok": True,
        "key_configured": bool(ELEVENLABS_API_KEY),
    })


@app.route("/api/voices")
def voices():
    """Lista as vozes disponíveis na conta — usado pelo seletor da Lia.

    Por padrão retorna apenas vozes com accent brasileiro / idioma português.
    Use ?all=1 para retornar todas as vozes da conta.
    """
    if not ELEVENLABS_API_KEY:
        return jsonify({"error": "API key não configurada no servidor."}), 500
    show_all = request.args.get("all") in ("1", "true", "yes")
    try:
        r = requests.get(
            f"{ELEVEN_BASE}/voices",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        all_voices = data.get("voices", [])

        def is_user_added(v):
            """Vozes adicionadas pelo usuário ao 'My Voices' (não as padrão premade)."""
            return (v.get("category") or "").lower() != "premade"

        filtered = all_voices if show_all else [v for v in all_voices if is_user_added(v)]

        slim = [
            {
                "voice_id": v.get("voice_id"),
                "name": v.get("name"),
                "labels": v.get("labels", {}),
                "preview_url": v.get("preview_url"),
            }
            for v in filtered
        ]
        return jsonify({"voices": slim, "total": len(all_voices), "filtered": len(slim)})
    except requests.HTTPError as e:
        return jsonify({"error": f"ElevenLabs: {e.response.status_code}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tts", methods=["POST"])
def tts():
    """
    Recebe { text, voice_id } do front, chama o ElevenLabs e
    devolve o áudio (audio/mpeg) em streaming.
    """
    if not ELEVENLABS_API_KEY:
        return jsonify({"error": "API key não configurada no servidor."}), 500

    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    voice_id = (body.get("voice_id") or "").strip()

    if not text:
        return jsonify({"error": "Texto vazio."}), 400
    if not voice_id:
        return jsonify({"error": "voice_id ausente."}), 400

    # Limite defensivo pra evitar gastar créditos à toa
    if len(text) > 2000:
        text = text[:2000]

    try:
        upstream = requests.post(
            f"{ELEVEN_BASE}/text-to-speech/{voice_id}/stream",
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": DEFAULT_MODEL,
                "voice_settings": {
                    "stability": 0.45,        # mais baixo = mais expressivo
                    "similarity_boost": 0.8,
                    "style": 0.35,            # leve estilo/calor
                    "use_speaker_boost": True,
                },
            },
            stream=True,
            timeout=60,
        )
        if upstream.status_code != 200:
            detail = upstream.text[:300]
            return jsonify({"error": f"ElevenLabs {upstream.status_code}: {detail}"}), 502

        def generate():
            for chunk in upstream.iter_content(chunk_size=4096):
                if chunk:
                    yield chunk

        return Response(generate(), mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Recebe { messages: [{role, content}], system?: string } e responde com
    a saída do GPT. O backend injeta o conteúdo de about_me.md no system
    prompt, então a Lia sempre tem o contexto pessoal do usuário.
    """
    if not OPENAI_API_KEY:
        return jsonify({"error": "OPENAI_API_KEY não configurada no servidor."}), 500

    body = request.get_json(silent=True) or {}
    messages = body.get("messages") or []
    base_system = (body.get("system") or "").strip()

    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "messages vazio ou inválido."}), 400

    about = load_about_me()
    system_parts = [p for p in [base_system, "## Contexto pessoal sobre o usuário\n" + about if about else ""] if p]
    system_prompt = "\n\n".join(system_parts)

    full_messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + messages

    try:
        r = requests.post(
            OPENAI_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "messages": full_messages,
            },
            timeout=60,
        )
        if r.status_code != 200:
            return jsonify({"error": f"OpenAI {r.status_code}: {r.text[:300]}"}), 502
        data = r.json()
        text = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        return jsonify({"reply": text, "model": data.get("model")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    if not ELEVENLABS_API_KEY:
        print("\n⚠️  ELEVENLABS_API_KEY não definida!")
        print("   Defina antes de rodar. Veja instruções no topo de app.py.\n")
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
