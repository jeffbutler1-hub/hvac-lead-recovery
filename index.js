require('dotenv').config();
const express = require('express');
const twilio = require('twilio');

const app = express();
app.use(express.urlencoded({ extended: false }));
app.use(express.json());

const client = twilio(
  process.env.TWILIO_ACCOUNT_SID,
  process.env.TWILIO_AUTH_TOKEN
);

app.get('/', (req, res) => {
  res.send('HVAC lead recovery is running');
});

app.post('/missed-call', async (req, res) => {
  const callerNumber = req.body.From;
  console.log('Missed call from:', callerNumber);

  const toNumber = '+19183780537';

  await client.messages.create({
    body: "Hi! Sorry we missed your call. We'd love to help — can I grab your name and what's going on with your system?",
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

app.post('/incoming-sms', (req, res) => {
  const from = req.body.From;
  const body = req.body.Body;
  console.log(`Reply from ${from}: ${body}`);

  res.type('text/xml');
  res.send(`
    <Response>
      <Message>Got it! We'll have someone reach out to you shortly.</Message>
    </Response>
  `);
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));