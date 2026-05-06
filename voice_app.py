from fastapi import FastAPI, WebSocket
from fastapi.responses import PlainTextResponse

app = FastAPI()

print("🚀 CLEAN APP LOADED")

@app.get("/")
async def root():
    return {"status": "running"}

@app.post("/incoming-call")
async def incoming_call():

    print("📞 INCOMING CALL HIT")

    twiml = """
<Response>
    <Connect>
        <Stream url="wss://hvac-lead-recovery-1.onrender.com/ws"/>
    </Connect>
</Response>
"""

    return PlainTextResponse(
        content=twiml,
        media_type="application/xml"
    )

@app.websocket("/ws")
async def ws(websocket: WebSocket):

    print("⚡ WEBSOCKET FUNCTION ENTERED")

    await websocket.accept()

    print("🔌 WEBSOCKET ACCEPTED")

    try:

        while True:

            msg = await websocket.receive()

            # Handle disconnect FIRST
            if msg["type"] == "websocket.disconnect":

                print("❌ WEBSOCKET DISCONNECTED")

                break

            print("📦 MESSAGE RECEIVED")

            print(msg)

    except Exception as e:

        print("❌ WEBSOCKET ERROR")

        print(type(e))

        print(str(e))