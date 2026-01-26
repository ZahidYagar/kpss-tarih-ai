from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google import genai
import os
import json
import re

app = Flask(__name__)
CORS(app)

# API KEY ortam değişkeninden okunur
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def safe_json_parse(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"error": "JSON üretilemedi", "raw": text}
    return json.loads(match.group())

def generate_content_from_query(user_query):
    prompt = f"""
Sen KPSS Tarih uzmanı bir eğitmendsin.

Konu: {user_query}

- KPSS dilinde
- En fazla 120 kelime
- Hikâyeleştirilmiş anlatım
- Ardından 1 KPSS tarzı soru, 4 şık, doğru cevap ve kısa açıklama üret.

Çıktıyı SADECE JSON olarak ver.

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
        return jsonify({"error": "query boş"}), 400

    result = generate_content_from_query(query)
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

@app.route("/")
def index():
    return send_from_directory(".", "index.html")
