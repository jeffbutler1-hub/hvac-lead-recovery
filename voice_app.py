from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import PlainTextResponse
from openai import OpenAI

import os
import json
import base64
import subprocess
import threading
from datetime import datetime

# ---------------------------------------------------
# OPTIONAL DATABASE SUPPORT (SUPABASE)
# ---------------------------------------------------
# pip install supabase
#
# Add these environment variables:
# SUPABASE_URL=
# SUPABASE_KEY=
# ---------------------------------------------------

from supabase import create_client

# ---------------------------------------------------
# FastAPI app
# ---------------------------------------------------
app = FastAPI()

print("🚀 HVAC LEAD RECOVERY APP LOADED")

# ---------------------------------------------------
# OpenAI client
# ---------------------------------------------------
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# ---------------------------------------------------
# Supabase client
# ---------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = None

if SUPABASE_URL and SUPABASE_KEY:

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

    print("✅ SUPABASE CONNECTED")

else:

    print("⚠️ SUPABASE NOT CONFIGURED")

# ---------------------------------------------------
# ACTIVE CALL STORAGE
# Prevents cross-call contamination
# ---------------------------------------------------
active_calls = {}

# ---------------------------------------------------
# Health check
# ---------------------------------------------------
@app.get("/")
async def root():

    return {
        "status": "running"
    }

# ---------------------------------------------------
# Incoming Twilio webhook
# ---------------------------------------------------
@app.post("/incoming-call")
async def incoming_call(request: Request):

    print("📞 INCOMING CALL RECEIVED")

    form = await request.form()

    from_number = form.get("From")
    to_number = form.get("To")
    call_sid = form.get("CallSid")

    print(f"Caller: {from_number}")
    print(f"Business Line: {to_number}")
    print(f"CallSid: {call_sid}")

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
# WebSocket endpoint
# ---------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    print("🔥 WEBSOCKET CONNECTED")

    await websocket.accept()

    current_call_sid = None

    try:

        while True:

            msg = await websocket.receive()

            # ---------------------------------------------------
            # Handle disconnect
            # ---------------------------------------------------
            if msg["type"] == "websocket.disconnect":

                print("❌ WEBSOCKET DISCONNECTED")

                break

            # ---------------------------------------------------
            # Ignore empty frames
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

                stream_sid = start_data.get("streamSid")

                custom_params = start_data.get(
                    "customParameters",
                    {}
                )

                call_sid = custom_params.get("call_sid")

                current_call_sid = call_sid

                print("▶️ STREAM STARTED")
                print(f"CallSid: {call_sid}")
                print(f"StreamSid: {stream_sid}")

                active_calls[call_sid] = {
                    "audio_chunks": [],
                    "chunk_count": 0,
                    "metadata": {
                        "call_sid": call_sid,
                        "stream_sid": stream_sid,
                        "from_number": custom_params.get("from"),
                        "to_number": custom_params.get("to"),
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

                chunk = base64.b64decode(payload)

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

                    print(
                        f"🎤 {chunk_count} chunks "
                        f"received for {current_call_sid}"
                    )

            # ---------------------------------------------------
            # STOP EVENT
            # ---------------------------------------------------
            elif event == "stop":

                print("⏹ STREAM STOPPED")

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
                # Process asynchronously
                # ---------------------------------------------------
                threading.Thread(
                    target=process_call_audio,
                    args=(
                        audio_copy,
                        metadata_copy
                    )
                ).start()

                # ---------------------------------------------------
                # Cleanup memory
                # ---------------------------------------------------
                del active_calls[current_call_sid]

                break

    except RuntimeError:

        print("⚠️ NORMAL WEBSOCKET CLOSE")

    except Exception as e:

        print("❌ WEBSOCKET ERROR")
        print(type(e))
        print(str(e))

# ---------------------------------------------------
# Main audio processing pipeline
# ---------------------------------------------------
def process_call_audio(audio_data, metadata):

    try:

        call_sid = metadata["call_sid"]

        print(f"🧠 PROCESSING CALL: {call_sid}")

        # ---------------------------------------------------
        # Create filenames
        # ---------------------------------------------------
        raw_filename = f"{call_sid}.ulaw"
        wav_filename = f"{call_sid}.wav"

        # ---------------------------------------------------
        # Save μ-law audio
        # ---------------------------------------------------
        print(
            f"💾 Saving μ-law audio "
            f"({len(audio_data)} chunks)"
        )

        with open(raw_filename, "wb") as f:

            f.write(b"".join(audio_data))

        print("✅ RAW AUDIO SAVED")

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

        print("🎵 FFMPEG CONVERSION COMPLETE")

        if result.stderr:
            print(result.stderr)

        # ---------------------------------------------------
        # Transcription
        # ---------------------------------------------------
        print("🧠 STARTING TRANSCRIPTION")

        with open(wav_filename, "rb") as audio_file:

            transcript = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio_file
            )

        transcript_text = transcript.text

        print("📄 TRANSCRIPT:")
        print(transcript_text)

        # ---------------------------------------------------
        # Structured extraction
        # ---------------------------------------------------
        lead_data = extract_lead_info(
            transcript_text
        )

        # ---------------------------------------------------
        # Save to database
        # ---------------------------------------------------
        save_call_record(
            metadata=metadata,
            transcript=transcript_text,
            lead_data=lead_data
        )

        print("✅ CALL PIPELINE COMPLETE")

    except Exception as e:

        print("❌ PROCESSING ERROR")
        print(type(e))
        print(str(e))

# ---------------------------------------------------
# GPT structured extraction
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

        print("📋 EXTRACTED LEAD INFO:")
        print(json.dumps(parsed, indent=2))

        return parsed

    except Exception as e:

        print("❌ EXTRACTION ERROR")
        print(type(e))
        print(str(e))

        return {}

# ---------------------------------------------------
# Persist call data
# ---------------------------------------------------
def save_call_record(
    metadata,
    transcript,
    lead_data
):

    try:

        record = {
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

        print("💾 SAVING CALL RECORD")

        print(json.dumps(
            record,
            indent=2
        ))

        # ---------------------------------------------------
        # Save to Supabase
        # ---------------------------------------------------
        if supabase:

            response = supabase.table(
                "calls"
            ).insert(record).execute()

            print("✅ SAVED TO SUPABASE")

            print(response)

        else:

            print(
                "⚠️ NO DATABASE CONNECTED"
            )

    except Exception as e:

        print("❌ DATABASE SAVE ERROR")
        print(type(e))
        print(str(e))