from flask import Flask, request, Response
from flask_cors import CORS
import requests
import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from twilio.rest import Client

# --------------------------
# Setup
# --------------------------
load_dotenv()

app = Flask(__name__)
CORS(app)  # ← prevents 403 issues

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")

MY_PERSONAL_NUMBER = os.getenv("MY_PERSONAL_NUMBER")
GSHEET_WEBHOOK = os.getenv("GSHEET_WEBHOOK")

# --------------------------
# HEALTH CHECK (important for debugging)
# --------------------------
@app.route("/", methods=["GET"])
def home():
    return "App is running!"

# --------------------------
# Incoming call
# --------------------------
@app.route("/incoming-call", methods=["POST"])
def incoming_call():
    print("\n--- INCOMING CALL HIT ---")
    print("Headers:", request.headers)
    print("Form:", request.form)

    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Please leave your name, number, and what you need help with after the beep.</Say>
    <Record maxLength="120" action="/handle-recording"/>
</Response>"""

    return Response(response, mimetype="text/xml")

# --------------------------
# Handle recording
# --------------------------
@app.route("/handle-recording", methods=["POST"])
def handle_recording():
    print("\n--- HANDLE RECORDING HIT ---")

    try:
        recording_url = request.form.get("RecordingUrl")

        if not recording_url:
            print("❌ No recording URL found")
            return "No recording", 200

        recording_url += ".wav"
        print("Recording URL:", recording_url)

        file_path = download_audio(recording_url)

        transcript = transcribe_audio(file_path)
        print("Transcript:", transcript)

        structured_text = extract_with_openai(transcript)
        structured = parse_json(structured_text)

        print("\n🚨 NEW LEAD 🚨")
        print(structured)

        # send_sms_alert(structured)
        send_to_sheets(structured)

        return "OK", 200

    except Exception as e:
        print("❌ ERROR:", e)
        return "Error", 200  # return 200 so Twilio doesn’t retry endlessly

# --------------------------
# Download audio
# --------------------------
def download_audio(url):
    response = requests.get(url, auth=(TWILIO_SID, TWILIO_AUTH))

    file_path = "temp.wav"
    with open(file_path, "wb") as f:
        f.write(response.content)

    return file_path

# --------------------------
# Transcribe
# --------------------------
def transcribe_audio(file_path):
    with open(file_path, "rb") as audio:
        transcript = openai_client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio
        )
    return transcript.text

# --------------------------
# Extract structured data
# --------------------------
def extract_with_openai(text):
    prompt = f"""
Extract the following fields from the transcript.

Return ONLY valid JSON in this format:

{{
  "name": "",
  "phone": "",
  "service": "",
  "urgency": "low | medium | high"
}}

Transcript:
{text}
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

# --------------------------
# Parse JSON safely
# --------------------------
def parse_json(output):
    try:
        return json.loads(output)
    except:
        print("⚠️ JSON parse failed")
        return {
            "name": "unknown",
            "phone": "unknown",
            "service": "unknown",
            "urgency": "unknown"
        }

# --------------------------
# Send SMS (demo-safe)
# --------------------------
def send_sms_alert(data):
    try:
        client = Client(TWILIO_SID, TWILIO_AUTH)

        body = f"""🚨 New Lead 🚨
Name: {data['name']}
Phone: {data['phone']}
Service: {data['service']}
Urgency: {data['urgency']}"""

        print("Sending SMS:", body)

        message = client.messages.create(
            body=body,
            from_=MY_PERSONAL_NUMBER,
            to=MY_PERSONAL_NUMBER
        )

        print("SMS sent:", message.sid)

    except Exception as e:
        print("❌ SMS error:", e)

# --------------------------
# Send to Google Sheets
# --------------------------
def send_to_sheets(data):
    if GSHEET_WEBHOOK:
        try:
            requests.post(GSHEET_WEBHOOK, json=data)
            print("Sent to Google Sheets")
        except Exception as e:
            print("❌ Sheets error:", e)

# --------------------------
# Run app
# --------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)