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
# ENTRY: Incoming call
# --------------------------
@app.route("/incoming-call", methods=["POST"])
def incoming_call():
    print("\n--- INCOMING CALL ---")

    response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Press 1 to speak with our AI assistant, or stay on the line to leave a voicemail.</Say>
    <Gather numDigits="1" action="/route-call" timeout="5"/>
    <Say>No input received. Please leave a message after the beep.</Say>
    <Record maxLength="120"
        action="/handle-recording"
        recordingStatusCallback="/handle-recording"
        recordingStatusCallbackMethod="POST"/>
</Response>"""

    return Response(response, mimetype="text/xml")

# --------------------------
# Route call (AI vs voicemail)
# --------------------------
@app.route("/route-call", methods=["POST"])
def route_call():
    digit = request.form.get("Digits")

    if digit == "1":
        print("Routing to AI assistant")

        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Hi, what’s going on with your HVAC system?</Say>
    <Record maxLength="8" action="/ai-step-1"/>
</Response>""", mimetype="text/xml")

    else:
        print("Routing to voicemail")

        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Please leave a message after the beep.</Say>
    <Record maxLength="120"
        action="/handle-recording"
        recordingStatusCallback="/handle-recording"
        recordingStatusCallbackMethod="POST"/>
</Response>""", mimetype="text/xml")

# --------------------------
# AI STEP 1
# --------------------------
@app.route("/ai-step-1", methods=["POST"])
def ai_step_1():
    print("\n--- AI STEP 1 ---")

    recording_url = request.form.get("RecordingUrl")

    if not recording_url:
        return "OK", 200

    recording_url += ".wav"

    transcript = transcribe_from_url(recording_url)
    print("AI Step 1 transcript:", transcript)

    reply = ai_followup(transcript)

    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>{reply}</Say>
    <Record maxLength="8" action="/ai-step-2"/>
</Response>"""

    return Response(response, mimetype="text/xml")

# --------------------------
# AI STEP 2 (FINALIZE)
# --------------------------
@app.route("/ai-step-2", methods=["POST"])
def ai_step_2():
    print("\n--- AI STEP 2 ---")

    recording_url = request.form.get("RecordingUrl")

    if not recording_url:
        return "OK", 200

    recording_url += ".wav"

    transcript = transcribe_from_url(recording_url)
    print("AI Step 2 transcript:", transcript)

    structured = extract_with_openai(transcript)
    structured = parse_json(structured)

    print("\n🚨 AI LEAD 🚨")
    print(structured)

    send_to_sheets(structured)
    send_sms_alert(structured)

    return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Thanks, we’ve got your request and will follow up shortly.</Say>
</Response>""", mimetype="text/xml")

# --------------------------
# VOICEMAIL FLOW (UNCHANGED CORE LOGIC)
# --------------------------
@app.route("/handle-recording", methods=["POST"])
def handle_recording():
    print("\n--- RECORDING CALLBACK ---")

    recording_status = request.form.get("RecordingStatus")

    # Prevent duplicates
    if recording_status != "completed":
        print("Skipping - recording not complete yet")
        return "OK", 200

    try:
        recording_url = request.form.get("RecordingUrl")

        if not recording_url:
            print("No recording URL")
            return "OK", 200

        recording_url += ".wav"
        print("Recording URL:", recording_url)

        transcript = transcribe_from_url(recording_url)
        print("Transcript:", transcript)

        structured = extract_with_openai(transcript)
        structured = parse_json(structured)

        print("\n🚨 VOICEMAIL LEAD 🚨")
        print(structured)

        send_to_sheets(structured)
        send_sms_alert(structured)

        return "OK", 200

    except Exception as e:
        print("ERROR:", e)
        return "OK", 200

# --------------------------
# Helpers
# --------------------------
def transcribe_from_url(url):
    print("⬇️ Downloading audio...")
    response = requests.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))

    file_path = "temp.wav"
    with open(file_path, "wb") as f:
        f.write(response.content)

    print("🧠 Transcribing...")
    with open(file_path, "rb") as audio:
        transcript = openai_client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio
        )

    return transcript.text

def ai_followup(text):
    prompt = f"""
You are an HVAC receptionist.

User said:
"{text}"

Ask a short follow-up question to collect:
- name
- phone number

Keep it conversational and brief.
"""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def extract_with_openai(text):
    print("🧩 Extracting structured data...")

    prompt = f"""
Extract:
- name
- phone
- service
- urgency

Return ONLY valid JSON.

Transcript:
{text}
"""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def parse_json(output):
    try:
        return json.loads(output)
    except Exception as e:
        print("JSON parse failed:", str(e))
        return {
            "name": "unknown",
            "phone": "unknown",
            "service": "unknown",
            "urgency": "unknown"
        }

def send_sms_alert(data):
    try:
        print("📲 Attempting SMS...")
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        message = client.messages.create(
            body=f"New lead: {data}",
            from_=TWILIO_PHONE_NUMBER,
            to=MY_PERSONAL_NUMBER
        )

        print("SMS sent:", message.sid)

    except Exception as e:
        print("SMS failed:", str(e))

def send_to_sheets(data):
    if GSHEET_WEBHOOK:
        try:
            print("📊 Sending to Google Sheets...")
            requests.post(GSHEET_WEBHOOK, json=data)
            print("✅ Sent to Google Sheets")
        except Exception as e:
            print("Sheets error:", str(e))

# --------------------------
# Run app
# --------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)