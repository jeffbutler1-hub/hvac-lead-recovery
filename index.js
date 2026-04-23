require("dotenv").config();
const express = require("express");
const twilio = require("twilio");
const Anthropic = require("@anthropic-ai/sdk");
const Airtable = require("airtable");

const app = express();

app.use(express.urlencoded({ extended: false }));
app.use(express.json());

/* -----------------------------
   Clients
----------------------------- */

const twilioClient = twilio(
  process.env.TWILIO_ACCOUNT_SID,
  process.env.TWILIO_AUTH_TOKEN
);

const MessagingResponse = twilio.twiml.MessagingResponse;

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY
});

const base = new Airtable({
  apiKey: process.env.AIRTABLE_TOKEN
}).base(process.env.AIRTABLE_BASE_ID);

/* -----------------------------
   In-memory state (MVP only)
----------------------------- */

const conversations = {};
const activatedUsers = {};

const OWNER_NUMBER = process.env.OWNER_PHONE_NUMBER;

/* -----------------------------
   AI Prompt
----------------------------- */

const SYSTEM_PROMPT = `
You are a friendly intake assistant for an HVAC service company.

A customer called the business, the call was missed, and they are now texting.

Collect these 5 items ONE QUESTION AT A TIME:

1. Full name
2. Service address
3. Description of HVAC issue
4. Urgency:
   - emergency
   - within 24 hours
   - within a week
   - planning ahead
5. Preferred callback time

Rules:
- Keep replies short and friendly for SMS
- Ask only ONE question at a time
- Do not ask for multiple things in one message
- Be warm and professional

When ALL info is collected, respond ONLY with valid JSON:

{
  "name": "John Smith",
  "address": "123 Main St, Austin TX",
  "issue": "AC not cooling",
  "urgency": "emergency",
  "callback": "today after 5pm",
  "complete": true
}

Do not include any extra text once complete.
`;

/* -----------------------------
   Helpers
----------------------------- */

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

  const assistantText = response.content[0].text;

  conversations[phoneNumber].push({
    role: "assistant",
    content: assistantText
  });

  return assistantText;
}

async function saveLeadToAirtable(lead, phone) {
  await base(process.env.AIRTABLE_TABLE_NAME).create([
    {
      fields: {
        Name: lead.name || "",
        Phone: phone || "",
        Address: lead.address || "",
        Issue: lead.issue || "",
        Urgency: lead.urgency || "",
        Callback: lead.callback || "",
        Status: "New"
      }
    }
  ]);
}

async function notifyOwner(lead, phone) {
  if (!OWNER_NUMBER) return;

  const msg =
    `NEW LEAD\n\n` +
    `Name: ${lead.name}\n` +
    `Phone: ${phone}\n` +
    `Address: ${lead.address}\n` +
    `Issue: ${lead.issue}\n` +
    `Urgency: ${lead.urgency}\n` +
    `Callback: ${lead.callback}`;

  await twilioClient.messages.create({
    from: process.env.TWILIO_PHONE_NUMBER,
    to: OWNER_NUMBER,
    body: msg
  });
}

/* -----------------------------
   Routes
----------------------------- */

app.get("/", (req, res) => {
  res.send("Lead recovery app is running");
});

/*
Configure Twilio Voice webhook to:
POST https://yourdomain.com/missed-call
*/

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
    console.error("Error sending missed-call SMS:", err);
  }

  res.type("text/xml");
  res.send(`
<Response>
  <Say>Please leave a message after the tone.</Say>
  <Record maxLength="60" />
</Response>
`);
});

/*
Configure Twilio Messaging webhook to:
POST https://yourdomain.com/incoming-sms
*/

app.post("/incoming-sms", async (req, res) => {
  const from = req.body.From;
  const body = (req.body.Body || "").trim();

  console.log(`Incoming SMS from ${from}: ${body}`);

  const twiml = new MessagingResponse();

  try {
    // Step 1: Require YES opt-in first
    if (!activatedUsers[from]) {
      if (body.toUpperCase() === "YES") {
        activatedUsers[from] = true;

        twiml.message(
          "Thanks! What is your full name?"
        );
      } else {
        twiml.message(
          "Reply YES if you'd like help with your request. Reply STOP to opt out."
        );
      }

      res.type("text/xml");
      return res.send(twiml.toString());
    }

    // Step 2: AI intake flow
    const aiReply = await chat(from, body);

    // Step 3: Completion check
    if (aiReply.includes('"complete": true')) {
      const lead = JSON.parse(aiReply);

      console.log("Lead completed:", lead);

      // Save to Airtable
      await saveLeadToAirtable(lead, from);

      // Notify owner
      await notifyOwner(lead, from);

      twiml.message(
        `Thanks ${lead.name}! We’ve got your info and someone will contact you soon.`
      );

      // Reset state
      delete conversations[from];
      delete activatedUsers[from];

    } else {
      // Continue intake
      twiml.message(aiReply);
    }

  } catch (err) {
    console.error("SMS route error:", err);

    twiml.message(
      "Sorry, something went wrong. Please call us again shortly."
    );
  }

  res.type("text/xml");
  res.send(twiml.toString());
});

/* -----------------------------
   Start Server
----------------------------- */

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});