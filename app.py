import os
print("ENV TEST →", os.getenv("GEMINI_API_KEY"))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google import genai
import json
import re

app = Flask(__name__)
CORS(app)

# ✅ Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def empty_response(topic=""):
    return {
        "topic": topic,
        "story": "",
        "questions": []
    }


def safe_json_parse(text, topic=""):
    if not text:
        return empty_response(topic)

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    match = re.search(r"\{[\s\S]*?\}", cleaned)
    if not match:
        print("JSON PARSE FAIL → RAW:", text)
        return empty_response(topic)

    try:
        data = json.loads(match.group())

        data["topic"] = data.get("topic", topic)
        data["story"] = data.get("story", "")
        data["questions"] = data.get("questions", [])

        if not isinstance(data["questions"], list):
            data["questions"] = []

        return data

    except Exception as e:
        print("JSON LOAD ERROR:", e)
        print("RAW TEXT:", text)
        return empty_response(topic)


def generate_content_from_query(user_query):
    prompt = f"""
Sen KPSS Tarih uzmanı bir eğitmendsin.

Konu: {user_query}

Görevlerin:
1. Konuyu KPSS dilinde, en fazla 250 kelimeyle hikâyeleştirerek anlat.
2. Ardından AYNI KONUDAN **5 adet KPSS formatında soru** üret.
3. Her soru 4 şıklı (A, B, C, D) olsun.
4. Her soru için doğru cevabı ve kısa bir açıklama yaz.

ÇIKTIYI SADECE aşağıdaki JSON formatında ver.
Başka hiçbir metin yazma.

{{
  "topic": "{user_query}",
  "story": "",
  "questions": [
    {{
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
  ]
}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return safe_json_parse(response.text, user_query)


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True)
    query = data.get("query") if data else None

    if not query:
        return jsonify(empty_response()), 200

    try:
        result = generate_content_from_query(query)

        # ✅ DEBUG DOĞRU YERDE
        print("RAW RESULT →", result)

        if not result or not isinstance(result.get("questions"), list):
            result = empty_response(query)

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
