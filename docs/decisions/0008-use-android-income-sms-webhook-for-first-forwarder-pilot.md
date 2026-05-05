# Decision 0008: Use Android Incoming SMS Webhook for First Forwarder Pilot

## Decision

Sprint 3 will use `bogkonstantin/android_income_sms_gateway_webhook` as the first Android SMS forwarding pilot.

The backend will expose a selected-forwarder endpoint:

```text
POST /api/forwarders/android-income-sms-webhook
X-Inbound-SMS-Secret: <INBOUND_SMS_SECRET>
```

The endpoint maps the app's documented payload into the internal Sprint 2 inbound SMS contract.

## Reason

The pilot app matches the smallest V1 need: receive SMS on Android and POST a JSON payload directly to the backend without requiring a cloud account in the forwarding path.

It also documents sender filtering, retry behavior, a test request button, and the relevant payload fields:

```json
{
  "from": "FAKEBANK",
  "text": "Fake SMS body",
  "sentStamp": "1777890599000",
  "receivedStamp": "1777890600000",
  "sim": "SIM1"
}
```

## Alternatives Considered

- SMSGate. Also a strong candidate because it is open source and supports incoming SMS webhooks, local/private/cloud modes, and structured message fields. It is broader than the minimal pilot need, so it remains the fallback.
- httpSMS. Has a clear webhook model, signed webhook JWTs, retries, and event schema. It introduces a hosted service/dashboard path by default, which is more external dependency than the first private finance SMS pilot needs.
- textbee. Polished hosted gateway with webhooks and signature verification, but it adds account/service dependency and free-tier limits.
- SMSsync. Longstanding Android SMS-to-HTTP gateway, but appears more dated than the selected pilot and fallback options.

## Consequences

- Sprint 3 can validate a concrete external payload shape instead of keeping forwarding abstract.
- The selected app must be tested on the user's Android device before real SMS ingestion.
- The selected app's ability to send the shared secret as a header must be verified. If unavailable, a narrowly scoped tokenized endpoint or another auth-compatible forwarder will be needed.
- Android background execution and battery optimization settings remain operational risks.
- SMSGate remains the fallback if the selected app fails setup, auth, or reliability testing.

## Date

2026-05-05
