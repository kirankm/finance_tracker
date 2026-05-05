# Golden SMS Fixture Dataset

This folder contains fake or anonymized SMS examples and expected structured outputs.

Rules:
- Do not store real personal SMS here.
- Every SMS example must have an expected output.
- Every new SMS pattern requires a fixture and test.
- Changes to expected output must be explained in the sprint document.

Suggested structure:

```text
golden/
  debit-upi.sms.txt
  debit-upi.expected.json
  credit-salary.sms.txt
  credit-salary.expected.json
  refund.sms.txt
  refund.expected.json
```
