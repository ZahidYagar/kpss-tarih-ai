import os
print("ENV TEST →", os.getenv("GEMINI_API_KEY"))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google import genai
import json
import re

app = Flask(__name__)
CORS(app)

# Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def empty_response(topic=""):
    return {
        "topic": topic,
        "story": "",
        "questions": []
    }


def safe_json_parse(text, topic=""):
    if not text:
        return None

    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        print("JSON BLOCK NOT FOUND")
        return None

    raw_json = match.group()

    # LLM kaynaklı yaygın JSON hatalarını onar
    raw_json = re.sub(r'"\s*\n\s*"', '",\n"', raw_json)
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
        print("JSON STILL BROKEN:", e)
        print("RAW JSON:", raw_json)
        return None


def generate_content_from_query(user_query):
    prompt = f"""
SADECE JSON ÜRET.
AÇIKLAMA YAZMA.
KOD BLOĞU KULLANMA.

SEN KPSS TARİH ALANINDA UZMAN, SORU YAZARI BİR EĞİTMENSİN.

KONU: {user_query}

AMAÇ:
- KPSS’de çıkan YORUM ve ANALİZ ağırlıklı sorular üret.
- Ezberle çözülemeyen, en az iki bilgiyi ilişkilendiren sorular yaz.
- Şıklar birbirine bilerek yakın ve çeldirici olsun.
- "Hangisi söylenemez?", "Bu durumun sonucu nedir?" tarzı sorular tercih et.

ZORUNLU KURALLAR:
- story: sebep–sonuç ilişkisi kuran kısa anlatım (BOŞ OLAMAZ)
- questions: TAM 5 ADET OLMAK ZORUNDA
- Her soru:
  - yorum gerektirsin
  - KPSS dili kullansın
  - şıklar mantıklı ve yakın olsun
- explanation:
  - neden doğru
  - neden diğerleri yanlış (kısa)

ŞEMA DIŞINA ASLA ÇIKMA:

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

    # 🔁 RETRY MEKANİZMASI
    for attempt in range(3):
        print(f"LLM ATTEMPT {attempt + 1}")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        parsed = safe_json_parse(response.text, user_query)

        if parsed and parsed.get("questions"):
            return parsed

        print("RETRY NEEDED")

    return empty_response(user_query)


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True)
    query = data.get("query") if data else None

    if not query:
        return jsonify(empty_response()), 200

    try:
        result = generate_content_from_query(query)
        print("FINAL RESULT →", result)
        return jsonify(result), 200

    except Exception as e:
        print("BACKEND ERROR:", str(e))
        return jsonify(empty_response(query)), 200


@app.route("/ping")
def ping():
    return "pong"


@app.route("/")
def index():
    return send_from_directory(".", "index.html")
