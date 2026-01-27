import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google import genai
import json
import re

# ======================
# APP CONFIG
# ======================
app = Flask(__name__)
CORS(app)

print("ENV TEST →", bool(os.getenv("GEMINI_API_KEY")))

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

# ======================
# HELPERS
# ======================
def empty_response(topic=""):
    return {
        "topic": topic,
        "story": "",
        "questions": []
    }


def safe_json_parse(text, topic=""):
    if not text:
        return None

    cleaned = (
        text.replace("```json", "")
            .replace("```", "")
            .strip()
    )

    # 🔑 Non-greedy JSON yakalama (RAM dostu)
    match = re.search(r"\{[\s\S]*?\}", cleaned)
    if not match:
        return None

    raw_json = match.group()

    # Yaygın LLM JSON hatalarını onar
    raw_json = re.sub(r',\s*}', '}', raw_json)
    raw_json = re.sub(r',\s*]', ']', raw_json)

    try:
        data = json.loads(raw_json)

        data["topic"] = data.get("topic", topic)
        data["story"] = data.get("story", "")
        data["questions"] = data.get("questions", [])

        if not isinstance(data["questions"], list):
            data["questions"] = []

        return data

    except Exception as e:
        print("JSON PARSE ERROR:", e)
        return None


# ======================
# LLM CALL
# ======================
def generate_content_from_query(user_query):
    prompt = f"""
SADECE JSON ÜRET.
AÇIKLAMA, BAŞLIK, MADDE, KOD BLOĞU KULLANMA.

SEN KPSS TARİH ALANINDA UZMAN, SORU YAZARI BİR EĞİTMENSİN.

KONU: {user_query}

AMAÇ:
- KPSS’de çıkan YORUM ve ANALİZ ağırlıklı sorular üret
- Ezberle çözülemeyen sorular yaz
- En az iki bilgiyi ilişkilendir
- Şıklar bilerek birbirine yakın (çeldirici)

STORY KURALLARI:
- 250–320 kelime
- KPSS kitap dili
- Sebep–sonuç ilişkisi
- Kronolojik akış
- Gereksiz uzatma YAPMA

SORULAR:
- TAM 5 ADET
- KPSS dili
- “Hangisi söylenemez?”, “Bu durumun sonucu nedir?” tarzı
- explanation:
  - neden doğru
  - neden diğerleri yanlış (kısa)

FORMAT DIŞINA ÇIKMA:

{{
  "topic": "{user_query}",
  "story": "string",
  "questions": [
    {{
      "question": "string",
      "choices": {{
        "A": "string",
        "B": "string",
        "C": "string",
        "D": "string"
      }},
      "answer": "A|B|C|D",
      "explanation": "string"
    }}
  ]
}}
"""

    # 🔥 TEK DENEME – RAM SAFE
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "max_output_tokens": 1200
        }
    )

    parsed = safe_json_parse(response.text, user_query)
    return parsed if parsed else empty_response(user_query)


# ======================
# ROUTES
# ======================
@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True)
    query = data.get("query") if data else None

    if not query:
        return jsonify(empty_response()), 200

    try:
        result = generate_content_from_query(query)
        return jsonify(result), 200

    except Exception as e:
        print("BACKEND ERROR:", e)
        return jsonify(empty_response(query)), 200


@app.route("/ping")
def ping():
    return "pong"


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# ======================
# LOCAL RUN
# ======================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
