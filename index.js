require('dotenv').config();
const express = require('express');
const twilio = require('twilio');
const Anthropic = require('@anthropic-ai/sdk');

const app = express();
app.use(express.urlencoded({ extended: false }));
app.use(express.json());

const twilioClient = twilio(
  process.env.TWILIO_ACCOUNT_SID,
  process.env.TWILIO_AUTH_TOKEN
);

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY
});

// Stores conversation history per phone number
const conversations = {};

const SYSTEM_PROMPT = `You are a friendly intake assistant for an HVAC service company. 
A customer just missed a call with the business. Your job is to collect the following 
information one question at a time in a conversational, friendly way appropriate for SMS:

1. Their first and last name
2. Their service address
3. A description of their HVAC issue
4. The urgency (emergency, within 24 hours, within a week, just planning ahead)
5. Their preferred callback time

Important rules:
- Ask only ONE question at a time
- Keep messages short and friendly — this is SMS
- Once you have ALL 5 pieces of information, respond ONLY with a JSON object like this:
{"name": "John Smith", "address": "123 Main St, Austin TX", "issue": "AC not cooling", "urgency": "emergency", "callback": "tomorrow morning", "complete": true}
- Do not include any text outside the JSON when you are done`;

async function chat(phoneNumber, userMessage) {
  // Initialize conversation if first message
  if (!conversations[phoneNumber]) {
    conversations[phoneNumber] = [];
  }

  // Add user message to history
  conversations[phoneNumber].push({
    role: 'user',
    content: userMessage
  });

  // Call Claude
  const response = await anthropic.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 1024,
    system: SYSTEM_PROMPT,
    messages: conversations[phoneNumber]
  });

  const assistantMessage = response.content[0].text;

  // Add Claude's response to history
  conversations[phoneNumber].push({
    role: 'assistant',
    content: assistantMessage
  });

  return assistantMessage;
}

app.get('/', (req, res) => {
  res.send('HVAC lead recovery is running');
});

app.post('/missed-call', async (req, res) => {
  const callerNumber = req.body.From;
  console.log('Missed call from:', callerNumber);

  const toNumber = '+19183780537';

  await twilioClient.messages.create({
    body: "Hi! Sorry we missed your call. Reply YES to connect with our virtual assistant and we'll get your info to the right person fast. Reply STOP at any time to opt out.",
    from: process.env.TWILIO_PHONE_NUMBER,
    to: toNumber
  });

  res.type('text/xml');
  res.send(`
    <Response>
      <Say>Please leave a message after the tone.</Say>
      <Record maxLength="60" />
    </Response>
  `);
});

app.post('/incoming-sms', async (req, res) => {
  const from = req.body.From;
  const body = req.body.Body.trim();
  console.log(`Reply from ${from}: ${body}`);

  let replyText;

  try {
    const claudeResponse = await chat(from, body);
    console.log('Claude response:', claudeResponse);

    // Check if Claude is done and returned JSON
    if (claudeResponse.includes('"complete": true')) {
      const lead = JSON.parse(claudeResponse);
      console.log('Lead captured:', lead);
      // Airtable and owner notification coming next
      replyText = `Thanks ${lead.name}! We've got your info and someone will call you back at your preferred time. Reply STOP at any time to opt out.`;
      delete conversations[from];
    } else {
      replyText = claudeResponse;
    }
  } catch (err) {
    console.error('Error:', err);
    replyText = "Sorry, something went wrong. Please call us back directly.";
  }

  res.type('text/xml');
  res.send(`
    <Response>
      <Message>${replyText}</Message>
    </Response>
  `);
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));