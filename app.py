from flask import Flask, request, Response
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

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
MY_PERSONAL_NUMBER = os.getenv("MY_PERSONAL_NUMBER")

GSHEET_WEBHOOK = os.getenv("GSHEET_WEBHOOK")

# --------------------------
# Health check
# --------------------------
@app.route("/", methods=["GET"])
def home():
    return "App is running!"

# --------------------------
# Incoming call
# --------------------------
@app.route("/incoming-call", methods=["POST"])
def incoming_call():
    print("\n--- INCOMING CALL ---")

    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Please leave your name, number, and what you need help with after the beep.</Say>
    <Record maxLength="120" action="/handle-recording" recordingStatusCallback="/handle-recording" recordingStatusCallbackMethod="POST"/>
</Response>"""

    return Response(response, mimetype="text/xml")

# --------------------------
# Handle recording
# --------------------------
@app.route("/handle-recording", methods=["POST"])
def handle_recording():
    print("\n--- RECORDING RECEIVED ---")

    try:
        recording_url = request.form.get("RecordingUrl")

        if not recording_url:
            print("❌ No recording URL")
            return "OK", 200

        recording_url += ".wav"
        print("🎧 Recording URL:", recording_url)

        file_path = download_audio(recording_url)

        transcript = transcribe_audio(file_path)
        print("📝 Transcript:", transcript)

        structured_text = extract_with_openai(transcript)
        structured = parse_json(structured_text)

        print("\n🚨 NEW LEAD 🚨")
        print(structured)

        # Send SMS
        send_sms_alert(structured)

        # Send to Google Sheets
        send_to_sheets(structured)

        return "OK", 200

    except Exception as e:
        print("❌ ERROR in handle_recording:", str(e))
        return "OK", 200

# --------------------------
# Download audio
# --------------------------
def download_audio(url):
    print("⬇️ Downloading audio...")
    response = requests.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))

    file_path = "temp.wav"
    with open(file_path, "wb") as f:
        f.write(response.content)

    return file_path

# --------------------------
# Transcribe
# --------------------------
def transcribe_audio(file_path):
    print("🧠 Transcribing audio...")
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
    print("🧩 Extracting structured data...")

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
    except Exception as e:
        print("❌ JSON parse failed:", str(e))
        return {
            "name": "unknown",
            "phone": "unknown",
            "service": "unknown",
            "urgency": "unknown"
        }

# --------------------------
# Send SMS
# --------------------------
def send_sms_alert(data):
    try:
        print("📲 Attempting to send SMS...")

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        body = f"""🚨 New Lead 🚨
Name: {data['name']}
Phone: {data['phone']}
Service: {data['service']}
Urgency: {data['urgency']}"""

        message = client.messages.create(
            body=body,
            from_=TWILIO_PHONE_NUMBER,
            to=MY_PERSONAL_NUMBER
        )

        print("✅ SMS sent:", message.sid)

    except Exception as e:
        print("❌ SMS FAILED:", str(e))

# --------------------------
# Send to Google Sheets
# --------------------------
def send_to_sheets(data):
    if GSHEET_WEBHOOK:
        try:
            print("📊 Sending to Google Sheets...")
            requests.post(GSHEET_WEBHOOK, json=data)
            print("✅ Sent to Google Sheets")
        except Exception as e:
            print("❌ Sheets error:", str(e))

# --------------------------
# Run app
# --------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)