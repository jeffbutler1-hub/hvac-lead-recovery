from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import PlainTextResponse

from openai import OpenAI
from supabase import create_client
from twilio.rest import Client as TwilioClient

import os
import json
import base64
import subprocess
import threading
import logging

from datetime import datetime

# ---------------------------------------------------
# Logging Configuration
# ---------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------
# FastAPI App
# ---------------------------------------------------
app = FastAPI()

logger.info("🚀 HVAC LEAD RECOVERY APP LOADED")

# ---------------------------------------------------
# OpenAI Client
# ---------------------------------------------------
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# ---------------------------------------------------
# Twilio SMS Client
# ---------------------------------------------------
twilio_client = TwilioClient(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

TWILIO_SMS_NUMBER = os.getenv(
    "TWILIO_SMS_NUMBER"
)

# ---------------------------------------------------
# Supabase Client
# ---------------------------------------------------
SUPABASE_URL = os.getenv(
    "SUPABASE_URL"
)

SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY"
)

supabase = None

if SUPABASE_URL and SUPABASE_KEY:

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

    logger.info("✅ SUPABASE CONNECTED")

else:

    logger.warning("⚠️ SUPABASE NOT CONFIGURED")

# ---------------------------------------------------
# Active Calls
# Prevents concurrent call collisions
# ---------------------------------------------------
active_calls = {}

# ---------------------------------------------------
# Startup Event
# ---------------------------------------------------
@app.on_event("startup")
async def startup_event():

    logger.info("🚀 APPLICATION STARTUP COMPLETE")

# ---------------------------------------------------
# Health Check
# ---------------------------------------------------
@app.get("/")
async def root():

    return {
        "status": "running"
    }

# ---------------------------------------------------
# Incoming Call Webhook
# ---------------------------------------------------
@app.post("/incoming-call")
async def incoming_call(request: Request):

    logger.info("📞 INCOMING CALL RECEIVED")

    form = await request.form()

    from_number = form.get("From")
    to_number = form.get("To")
    call_sid = form.get("CallSid")

    logger.info(f"Caller: {from_number}")
    logger.info(f"Business Line: {to_number}")
    logger.info(f"CallSid: {call_sid}")

    twiml = f"""
<Response>
    <Connect>
        <Stream url="wss://hvac-lead-recovery-1.onrender.com/ws">
            <Parameter name="from" value="{from_number}" />
            <Parameter name="to" value="{to_number}" />
            <Parameter name="call_sid" value="{call_sid}" />
        </Stream>
    </Connect>
</Response>
"""

    return PlainTextResponse(
        content=twiml,
        media_type="application/xml"
    )

# ---------------------------------------------------
# WebSocket Endpoint
# ---------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    logger.info("🔥 WEBSOCKET CONNECTED")

    await websocket.accept()

    current_call_sid = None

    try:

        while True:

            msg = await websocket.receive()

            # ---------------------------------------------------
            # Disconnect Handling
            # ---------------------------------------------------
            if msg["type"] == "websocket.disconnect":

                logger.warning("❌ WEBSOCKET DISCONNECTED")

                break

            # ---------------------------------------------------
            # Ignore Empty Frames
            # ---------------------------------------------------
            if "text" not in msg:
                continue

            text_data = msg["text"]

            if not text_data:
                continue

            data = json.loads(text_data)

            event = data.get("event")

            # ---------------------------------------------------
            # STREAM START
            # ---------------------------------------------------
            if event == "start":

                start_data = data.get("start", {})

                stream_sid = start_data.get(
                    "streamSid"
                )

                custom_params = start_data.get(
                    "customParameters",
                    {}
                )

                call_sid = custom_params.get(
                    "call_sid"
                )

                current_call_sid = call_sid

                logger.info("▶️ STREAM STARTED")
                logger.info(f"CallSid: {call_sid}")
                logger.info(f"StreamSid: {stream_sid}")

                active_calls[call_sid] = {

                    "audio_chunks": [],

                    "chunk_count": 0,

                    "metadata": {

                        "call_sid": call_sid,

                        "stream_sid": stream_sid,

                        "from_number": custom_params.get(
                            "from"
                        ),

                        "to_number": custom_params.get(
                            "to"
                        ),

                        "started_at": datetime.utcnow().isoformat()
                    }
                }

            # ---------------------------------------------------
            # MEDIA EVENT
            # ---------------------------------------------------
            elif event == "media":

                if not current_call_sid:
                    continue

                payload = data["media"]["payload"]

                chunk = base64.b64decode(
                    payload
                )

                active_calls[current_call_sid][
                    "audio_chunks"
                ].append(chunk)

                active_calls[current_call_sid][
                    "chunk_count"
                ] += 1

                chunk_count = active_calls[
                    current_call_sid
                ]["chunk_count"]

                if chunk_count % 100 == 0:

                    logger.info(
                        f"🎤 {chunk_count} chunks "
                        f"received for {current_call_sid}"
                    )

            # ---------------------------------------------------
            # STOP EVENT
            # ---------------------------------------------------
            elif event == "stop":

                logger.info("⏹ STREAM STOPPED")

                if not current_call_sid:
                    break

                call_data = active_calls.get(
                    current_call_sid
                )

                if not call_data:
                    break

                audio_copy = call_data[
                    "audio_chunks"
                ].copy()

                metadata_copy = call_data[
                    "metadata"
                ].copy()

                # ---------------------------------------------------
                # Process in Background Thread
                # ---------------------------------------------------
                threading.Thread(
                    target=process_call_audio,
                    args=(
                        audio_copy,
                        metadata_copy
                    ),
                    daemon=True
                ).start()

                # ---------------------------------------------------
                # Cleanup
                # ---------------------------------------------------
                del active_calls[current_call_sid]

                break

    except RuntimeError:

        logger.warning("⚠️ NORMAL WEBSOCKET CLOSE")

    except Exception as e:

        logger.exception("❌ WEBSOCKET ERROR")

# ---------------------------------------------------
# Main Audio Pipeline
# ---------------------------------------------------
def process_call_audio(audio_data, metadata):

    try:

        call_sid = metadata["call_sid"]

        logger.info(f"🧠 PROCESSING CALL: {call_sid}")

        # ---------------------------------------------------
        # Filenames
        # ---------------------------------------------------
        raw_filename = f"{call_sid}.ulaw"

        wav_filename = f"{call_sid}.wav"

        # ---------------------------------------------------
        # Save μ-law Audio
        # ---------------------------------------------------
        logger.info(
            f"💾 Saving μ-law audio "
            f"({len(audio_data)} chunks)"
        )

        with open(raw_filename, "wb") as f:

            f.write(b"".join(audio_data))

        logger.info("✅ RAW AUDIO SAVED")

        # ---------------------------------------------------
        # Convert μ-law -> WAV
        # ---------------------------------------------------
        command = [

            "ffmpeg",

            "-f", "mulaw",

            "-ar", "8000",

            "-ac", "1",

            "-i", raw_filename,

            wav_filename,

            "-y"
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True
        )

        logger.info("🎵 FFMPEG CONVERSION COMPLETE")

        if result.stderr:

            logger.info(result.stderr)

        # ---------------------------------------------------
        # Transcription
        # ---------------------------------------------------
        logger.info("🧠 STARTING TRANSCRIPTION")

        with open(wav_filename, "rb") as audio_file:

            transcript = client.audio.transcriptions.create(

                model="gpt-4o-mini-transcribe",

                file=audio_file
            )

        transcript_text = transcript.text

        logger.info("📄 TRANSCRIPT:")
        logger.info(transcript_text)

        # ---------------------------------------------------
        # Structured Extraction
        # ---------------------------------------------------
        lead_data = extract_lead_info(
            transcript_text
        )

        # ---------------------------------------------------
        # Lookup Contractor
        # ---------------------------------------------------
        contractor = get_contractor_by_twilio_number(
            metadata.get("to_number")
        )

        contractor_id = None

        if contractor:

            contractor_id = contractor["id"]

            logger.info(
                f"🏢 CONTRACTOR: "
                f"{contractor['business_name']}"
            )

        else:

            logger.warning(
                "⚠️ NO CONTRACTOR FOUND"
            )

        # ---------------------------------------------------
        # Save Call Record
        # ---------------------------------------------------
        save_call_record(

            contractor_id=contractor_id,

            metadata=metadata,

            transcript=transcript_text,

            lead_data=lead_data
        )

        # ---------------------------------------------------
        # Send SMS Notification
        # ---------------------------------------------------
        if contractor:

            send_sms_notification(

                contractor_number=contractor[
                    "notification_phone"
                ],

                contractor_name=contractor[
                    "business_name"
                ],

                metadata=metadata,

                lead_data=lead_data
            )

        else:

            logger.warning(
                "⚠️ SKIPPING SMS - "
                "NO CONTRACTOR FOUND"
            )

        logger.info("✅ CALL PIPELINE COMPLETE")

    except Exception:

        logger.exception("❌ PROCESSING ERROR")

# ---------------------------------------------------
# GPT Structured Extraction
# ---------------------------------------------------
def extract_lead_info(transcript_text):

    try:

        response = client.chat.completions.create(

            model="gpt-4.1-mini",

            response_format={
                "type": "json_object"
            },

            messages=[

                {
                    "role": "system",

                    "content": """
You extract HVAC lead information.

Return ONLY valid JSON.

Fields:
- customer_name
- phone_number
- issue
- intent
- urgency
- summary
"""
                },

                {
                    "role": "user",

                    "content": transcript_text
                }
            ]
        )

        result = response.choices[
            0
        ].message.content

        parsed = json.loads(result)

        logger.info("📋 EXTRACTED LEAD INFO:")

        logger.info(
            json.dumps(
                parsed,
                indent=2
            )
        )

        return parsed

    except Exception:

        logger.exception("❌ EXTRACTION ERROR")

        return {}

# ---------------------------------------------------
# Contractor Lookup
# ---------------------------------------------------
def get_contractor_by_twilio_number(
    twilio_number
):

    try:

        response = supabase.table(
            "contractors"
        ).select("*").eq(
            "twilio_number",
            twilio_number
        ).execute()

        data = response.data

        if not data:

            return None

        contractor = data[0]

        logger.info("🏢 CONTRACTOR FOUND")

        logger.info(contractor)

        return contractor

    except Exception:

        logger.exception("❌ CONTRACTOR LOOKUP ERROR")

        return None

# ---------------------------------------------------
# Save Call Record
# ---------------------------------------------------
def save_call_record(

    contractor_id,
    metadata,
    transcript,
    lead_data
):

    try:

        record = {

            "contractor_id": contractor_id,

            "call_sid": metadata.get(
                "call_sid"
            ),

            "stream_sid": metadata.get(
                "stream_sid"
            ),

            "from_number": metadata.get(
                "from_number"
            ),

            "to_number": metadata.get(
                "to_number"
            ),

            "started_at": metadata.get(
                "started_at"
            ),

            "transcript": transcript,

            "lead_data": lead_data
        }

        logger.info("💾 SAVING CALL RECORD")

        logger.info(
            json.dumps(
                record,
                indent=2
            )
        )

        # ---------------------------------------------------
        # Save to Supabase
        # ---------------------------------------------------
        if supabase:

            response = supabase.table(
                "calls"
            ).insert(record).execute()

            logger.info("✅ SAVED TO SUPABASE")

            logger.info(response)

        else:

            logger.warning(
                "⚠️ NO DATABASE CONNECTED"
            )

    except Exception:

        logger.exception("❌ DATABASE SAVE ERROR")

# ---------------------------------------------------
# SMS Notification
# ---------------------------------------------------
def send_sms_notification(

    contractor_number,
    contractor_name,
    metadata,
    lead_data
):

    try:

        sms_body = f"""
🔥 New Lead for {contractor_name}

Customer:
{lead_data.get('customer_name', 'Unknown')}

Phone:
{lead_data.get('phone_number', metadata.get('from_number'))}

Issue:
{lead_data.get('issue', 'Unknown')}

Urgency:
{lead_data.get('urgency', 'Unknown')}

Summary:
{lead_data.get('summary', 'No summary')}
"""

        logger.info("📲 SENDING SMS")

        logger.info(sms_body)

        message = twilio_client.messages.create(

            body=sms_body,

            from_=TWILIO_SMS_NUMBER,

            to=contractor_number
        )

        logger.info("✅ SMS SENT")

        logger.info(message.sid)

    except Exception:

        logger.exception("❌ SMS ERROR")