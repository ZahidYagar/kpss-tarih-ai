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
    """
    🔒 GARANTİLİ PARSE
    - JSON düzgünse: full içerik
    - JSON bozuksa: story KURTARILIR
    - Her durumda frontend boş kalmaz
    """
    if not text:
        return empty_response(topic)

    cleaned = (
        text.replace("```json", "")
            .replace("```", "")
            .strip()
    )

    # JSON bloğunu yakala (non-greedy)
    match = re.search(r"\{[\s\S]*?\}", cleaned)
    if not match:
        print("JSON BLOCK NOT FOUND")
        return {
            "topic": topic,
            "story": cleaned[:2000],  # 🔥 ham metinden özet kurtarma
            "questions": []
        }

    raw = match.group()

    # Yaygın LLM JSON hatalarını temizle
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)

    try:
        data = json.loads(raw)

        return {
            "topic": data.get("topic", topic),
            "story": data.get("story", ""),
            "questions": data.get("questions", []) if isinstance(data.get("questions"), list) else []
        }

    except Exception as e:
        print("JSON BROKEN → STORY RECOVERY MODE:", e)

        # 🔥 STORY'Yİ ZORLA KURTAR
        story_match = re.search(
            r'"story"\s*:\s*"([\s\S]*?)"\s*,\s*"questions"',
            raw
        )

        story = story_match.group(1) if story_match else cleaned[:2000]

        return {
            "topic": topic,
            "story": story,
            "questions": []
        }


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

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "max_output_tokens": 1200
        }
    )

    return safe_json_parse(response.text, user_query)


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
