import os
import json
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google import genai

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

    # JSON'u güvenli şekilde yakala
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None

    raw = match.group()

    # Yaygın JSON hatalarını düzelt
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)

    try:
        data = json.loads(raw)

        story = data.get("story", "")
        questions = data.get("questions", [])

        # 🔐 Guard'lar
        if not isinstance(story, str) or len(story.split()) < 180:
            return None

        if not isinstance(questions, list) or len(questions) < 5:
            return None

        return {
            "topic": data.get("topic", topic),
            "story": story,
            "questions": questions
        }

    except Exception as e:
        print("JSON PARSE ERROR:", e)
        return None


# ======================
# LLM CALL
# ======================
def generate_content_from_query(user_query):
    prompt = f"""
SADECE JSON ÜRET.
KESİNLİKLE YARIM BIRAKMA.
JSON TAMAMLAMADAN DURMA.

SEN KPSS TARİH ALANINDA KİTAP YAZARI VE SORU YAZARI BİR EĞİTMENSİN.

KONU: {user_query}

STORY:
- 250–350 kelime
- KPSS kitap dili
- Sebep–sonuç
- Kronolojik akış
- Giriş → gelişme → sonuç

SORULAR:
- TAM 5 ADET
- Yorum ve analiz ağırlıklı
- Ezberle çözülemez
- Şıklar birbirine yakın
- “Hangisi söylenemez?”, “Bu durumun sonucu nedir?” tarzı

FORMAT DIŞINA ASLA ÇIKMA:

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

    # 🔁 RETRY MEKANİZMASI (3 deneme)
    for attempt in range(3):
        print(f"LLM ATTEMPT → {attempt + 1}")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"max_output_tokens": 1400}
        )

        parsed = safe_json_parse(response.text, user_query)

        if parsed:
            return parsed

        print("RETRY...")

    return empty_response(user_query)


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
# LOCAL / PROD RUN
# ======================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
