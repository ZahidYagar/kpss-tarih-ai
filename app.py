from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google import genai
import os
import json
import re

# Flask app
app = Flask(__name__)
CORS(app)

# Gemini client (API key ortam değişkeninden okunur)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def safe_json_parse(text):
    """
    Gemini bazen JSON öncesi/sonrası metin ekleyebilir.
    Bu fonksiyon sadece ilk JSON bloğunu yakalar.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return empty_response()

    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return empty_response()


def empty_response():
    return {
        "topic": "",
        "story": "",
        "question": "",
        "choices": {
            "A": "",
            "B": "",
            "C": "",
            "D": ""
        },
        "answer": "",
        "explanation": ""
    }


def generate_content_from_query(user_query):
    prompt = f"""
Sen KPSS Tarih uzmanı bir eğitmendsin.

Konu: {user_query}

Görevlerin:
1. Konuyu KPSS dilinde, en fazla 250 kelimeyle hikâyeleştirerek anlat.
2. Ardından KPSS formatında **4 şıklı (A, B, C, D)** bir soru üret.
3. **Şıklar mutlaka anlamlı ve birbirinden farklı olsun.**
4. Doğru cevabı belirt ve kısa bir açıklama yaz.

ÇIKTIYI SADECE aşağıdaki JSON formatında ver.
Başka hiçbir metin yazma.

{{
  "topic": "{user_query}",
  "story": "",
  "question": "",
  "choices": {{
    "A": "",
    "B": "",
    "C": "",
    "D": ""
  }},
  "answer": "",
  "explanation": ""
}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return safe_json_parse(response.text)


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    query = data.get("query")

    if not query:
        return jsonify({
            "error": "bad_request",
            "message": "query boş"
        }), 400

    try:
        result = generate_content_from_query(query)
        return jsonify(result)

    except Exception as e:
        error_msg = str(e)

        # Gemini quota dolduysa
        if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
            return jsonify({
                "error": "quota",
                "message": "Günlük ücretsiz kullanım limiti doldu. Lütfen biraz sonra tekrar deneyin."
            }), 429

        # Diğer hatalar
        return jsonify({
            "error": "server",
            "message": "Sunucu hatası oluştu."
        }), 500


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
