require("dotenv").config();
const express = require("express");
const twilio = require("twilio");
const Anthropic = require("@anthropic-ai/sdk");

const app = express();
app.use(express.urlencoded({ extended: false }));
app.use(express.json());

const MessagingResponse = twilio.twiml.MessagingResponse;

const twilioClient = twilio(
  process.env.TWILIO_ACCOUNT_SID,
  process.env.TWILIO_AUTH_TOKEN
);

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY
});

const conversations = {};
const activatedUsers = {};

const OWNER_NUMBER = process.env.OWNER_PHONE_NUMBER;

const SYSTEM_PROMPT = `
You are a friendly HVAC intake assistant via SMS.

Collect these 5 items one at a time:

1. Full name
2. Service address
3. HVAC issue
4. Urgency (emergency / 24 hours / week / planning)
5. Preferred callback time

Rules:
- Ask ONE short question at a time
- Be warm and concise
- SMS tone
- Once complete, output ONLY valid JSON:

{
"name":"John Smith",
"address":"123 Main St Austin TX",
"issue":"AC not cooling",
"urgency":"emergency",
"callback":"today after 5",
"complete": true
}
`;

async function chat(phoneNumber, userMessage) {
  if (!conversations[phoneNumber]) {
    conversations[phoneNumber] = [];
  }

  conversations[phoneNumber].push({
    role: "user",
    content: userMessage
  });

  const response = await anthropic.messages.create({
    model: "claude-sonnet-4-5",
    max_tokens: 500,
    system: SYSTEM_PROMPT,
    messages: conversations[phoneNumber]
  });

  const text = response.content[0].text;

  conversations[phoneNumber].push({
    role: "assistant",
    content: text
  });

  return text;
}

app.get("/", (req, res) => {
  res.send("Lead recovery app is running");
});

app.post("/missed-call", async (req, res) => {
  const callerNumber = req.body.From;

  console.log("Missed call from:", callerNumber);

  try {
    await twilioClient.messages.create({
      from: process.env.TWILIO_PHONE_NUMBER,
      to: callerNumber,
      body:
        "Hi! Sorry we missed your call. Reply YES to connect with our assistant and we’ll get your info to the team quickly. Reply STOP to opt out."
    });
  } catch (err) {
    console.error(err);
  }

  res.type("text/xml");
  res.send(`
<Response>
<Say>Please leave a message after the tone.</Say>
<Record maxLength="60"/>
</Response>
`);
});

app.post("/incoming-sms", async (req, res) => {
  const from = req.body.From;
  const body = req.body.Body.trim();

  const twiml = new MessagingResponse();

  try {
    // Require YES first
    if (!activatedUsers[from]) {
      if (body.toUpperCase() === "YES") {
        activatedUsers[from] = true;
        twiml.message(
          "Thanks! What is your full name?"
        );
      } else {
        twiml.message(
          "Reply YES if you'd like help with your missed call request. Reply STOP to opt out."
        );
      }

      return res.type("text/xml").send(twiml.toString());
    }

    const aiReply = await chat(from, body);

    if (aiReply.includes('"complete": true')) {
      const lead = JSON.parse(aiReply);

      console.log("Lead captured:", lead);

      // notify owner
      await twilioClient.messages.create({
        from: process.env.TWILIO_PHONE_NUMBER,
        to: OWNER_NUMBER,
        body:
          `NEW LEAD\n` +
          `${lead.name}\n` +
          `${lead.address}\n` +
          `${lead.issue}\n` +
          `${lead.urgency}\n` +
          `${lead.callback}`
      });

      twiml.message(
        `Thanks ${lead.name}! We’ve got your info and someone will contact you soon.`
      );

      delete conversations[from];
      delete activatedUsers[from];

    } else {
      twiml.message(aiReply);
    }

  } catch (err) {
    console.error(err);
    twiml.message(
      "Sorry, something went wrong. Please call us back shortly."
    );
  }

  res.type("text/xml");
  res.send(twiml.toString());
});

const PORT = process.env.PORT || 3000;

app.listen(PORT, () =>
  console.log(`Server running on port ${PORT}`)
);