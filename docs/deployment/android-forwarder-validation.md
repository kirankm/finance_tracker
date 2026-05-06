# Android Forwarder Fake-Device Validation

Date: 2026-05-06

Use this before accepting real SMS payloads.

## Selected Forwarder

The selected V1 forwarder remains `bogkonstantin/android_income_sms_gateway_webhook`.

Production backend endpoint:

```text
POST /api/forwarders/android-income-sms-webhook
X-Inbound-SMS-Secret: <INBOUND_SMS_SECRET>
```

## Validation Steps

1. Install/configure the forwarder on the Android device.
2. Configure the production HTTPS endpoint.
3. Configure `X-Inbound-SMS-Secret` as a request header.
4. Send a fake SMS payload only. Do not use real bank SMS for validation.
5. Confirm the backend returns `201` for the first fake payload.
6. Send the same fake payload again and confirm the backend returns `200` with the same `raw_sms_id`.
7. Send a malformed fake payload and confirm the backend rejects it without persistence.
8. Confirm no full raw SMS body appears in container logs.
9. Confirm the fake message appears in the review queue and can be reviewed/promoted.

## No-Go Conditions

- The forwarder cannot send `X-Inbound-SMS-Secret` as a header.
- The device delays or drops fake forwarded SMS under normal battery settings.
- Production logs contain full raw SMS bodies.
- The endpoint is reachable over plain HTTP instead of HTTPS.

If header support fails, do not send real SMS. Switch to another forwarder that
supports headers, or explicitly implement and review a narrowly scoped fallback
in a later sprint. Query-string tokens are intentionally not accepted in Sprint
20 because they are easier to leak through logs and browser/history tooling.
