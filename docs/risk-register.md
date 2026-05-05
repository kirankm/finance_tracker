# Risk Register

| Risk | Impact | Mitigation | Status |
|---|---|---|---|
| SMS formats vary across banks and payment systems | Parser may miss or misread transactions | Build golden dataset and add fixtures per pattern | Open |
| LLM misclassifies transactions | Wrong spending analysis | LLM suggestions are soft; rules/user corrections override | Open |
| Duplicate detection false positives | Real transactions may be excluded | Possible duplicates require review | Open |
| Raw SMS leakage in logs | Privacy issue | Logging rules, fake fixtures, review sensitive logs | Open |
| Ledger mismatch logic is wrong | User loses trust in balances | TDD with ledger fixtures and explainability metadata | Open |
| External SMS forwarding service changes payload format | Ingestion may break | Validate payloads and add contract tests | Open |
| Linode production deployment exposes inbound SMS endpoint before HTTPS/auth hardening | Financial SMS data could be intercepted or submitted by unauthorized clients | Caddy HTTPS is verified, the app port is not public, and a strong secret is configured; still add authenticated ingestion contract tests before real ingestion | Partially mitigated |
| SQLite database on a VPS is not backed up | User could lose transaction history if the server disk fails | Backup/restore commands are documented and smoke-tested with fake data; choose off-server backup storage before relying on real data | Partially mitigated |
