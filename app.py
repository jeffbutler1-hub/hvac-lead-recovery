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

# Store conversation memory (simple in-memory)
conversation_memory = {}

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
    <Say voice="Polly.Joanna">Press 1 to speak with our assistant, or stay on the line to leave a message.</Say>
    <Gather numDigits="1" action="/route-call" timeout="5"/>
    <Say voice="Polly.Joanna">No input received. Please leave a message after the beep.</Say>
    <Record maxLength="120"
        action="/handle-recording"
        recordingStatusCallback="/handle-recording"
        recordingStatusCallbackMethod="POST"/>
</Response>"""

    return Response(response, mimetype="text/xml")

# --------------------------
# Route call
# --------------------------
@app.route("/route-call", methods=["POST"])
def route_call():
    digit = request.form.get("Digits")

    if digit == "1":
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Hi, what’s going on with your HVAC system?</Say>
    <Record maxLength="4" timeout="2" action="/ai-step-1"/>
</Response>""", mimetype="text/xml")

    else:
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Please leave a message after the beep.</Say>
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
    call_sid = request.form.get("CallSid")

    if not recording_url:
        return "OK", 200

    recording_url += ".wav"
    transcript = transcribe_from_url(recording_url)

    print("Step 1 transcript:", transcript)

    # Store first turn
    conversation_memory[call_sid] = transcript

    reply = ai_followup(transcript)

    return Response(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{reply}</Say>
    <Record maxLength="4" timeout="2" action="/ai-step-2"/>
</Response>""", mimetype="text/xml")

# --------------------------
# AI STEP 2
# --------------------------
@app.route("/ai-step-2", methods=["POST"])
def ai_step_2():
    print("\n--- AI STEP 2 ---")

    recording_url = request.form.get("RecordingUrl")
    call_sid = request.form.get("CallSid")

    if not recording_url:
        return "OK", 200

    recording_url += ".wav"
    transcript = transcribe_from_url(recording_url)

    print("Step 2 transcript:", transcript)

    # Combine both turns
    first_turn = conversation_memory.get(call_sid, "")
    combined_text = first_turn + " " + transcript

    print("Combined:", combined_text)

    structured = extract_with_openai(combined_text)
    structured = parse_json(structured)

    print("\n🚨 AI LEAD 🚨")
    print(structured)

    send_to_sheets(structured)
    send_sms_alert(structured)

    # cleanup memory
    if call_sid in conversation_memory:
        del conversation_memory[call_sid]

    return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Got it. We’ll have someone follow up shortly.</Say>
</Response>""", mimetype="text/xml")

# --------------------------
# VOICEMAIL FLOW (UNCHANGED)
# --------------------------
@app.route("/handle-recording", methods=["POST"])
def handle_recording():
    print("\n--- RECORDING CALLBACK ---")

    recording_status = request.form.get("RecordingStatus")

    if recording_status != "completed":
        print("Skipping - not complete")
        return "OK", 200

    try:
        recording_url = request.form.get("RecordingUrl")

        if not recording_url:
            return "OK", 200

        recording_url += ".wav"
        transcript = transcribe_from_url(recording_url)

        print("Voicemail transcript:", transcript)

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
    response = requests.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))

    with open("temp.wav", "wb") as f:
        f.write(response.content)

    with open("temp.wav", "rb") as audio:
        t = openai_client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio
        )

    return t.text

def ai_followup(text):
    prompt = f"""
You are a friendly HVAC receptionist speaking on the phone.

The caller said:
"{text}"

Respond naturally in ONE short sentence.

Tone:
- conversational
- human
- not robotic

Goal:
acknowledge their issue and ask for name + phone

Example:
"Got it—that sounds frustrating. Can I grab your name and number so we can get someone out to you?"

Now respond:
"""
    res = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content.strip()

def extract_with_openai(text):
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
    res = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content

def parse_json(output):
    try:
        return json.loads(output)
    except:
        return {
            "name": "unknown",
            "phone": "unknown",
            "service": "unknown",
            "urgency": "unknown"
        }

def send_sms_alert(data):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=f"New lead: {data}",
            from_=TWILIO_PHONE_NUMBER,
            to=MY_PERSONAL_NUMBER
        )
    except:
        pass

def send_to_sheets(data):
    if GSHEET_WEBHOOK:
        requests.post(GSHEET_WEBHOOK, json=data)

# --------------------------
# Run
# --------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)