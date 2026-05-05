# Risk Register

| Risk | Impact | Mitigation | Status |
|---|---|---|---|
| SMS formats vary across banks and payment systems | Parser may miss or misread transactions | Build golden dataset and add fixtures per pattern | Open |
| LLM misclassifies transactions | Wrong spending analysis | LLM suggestions are soft; rules/user corrections override | Open |
| Duplicate detection false positives | Real transactions may be excluded | Possible duplicates require review | Open |
| Duplicate SMS messages can still be promoted as separate ledger transactions before Sprint 7 | Ledger totals may be overstated if banks or forwarders send distinct duplicate messages | Sprint 6 only enforces idempotency for the same raw SMS; Sprint 7 will add cross-message duplicate detection before analysis is trusted | Open |
| Raw SMS leakage in logs | Privacy issue | Logging rules, fake fixtures, review sensitive logs | Open |
| Review detail endpoints expose raw SMS body | Privacy issue if endpoint access is not controlled | Review queue endpoints require the same shared secret as inbound SMS; list responses omit raw SMS bodies | Partially mitigated |
| Ledger mismatch logic is wrong | User loses trust in balances | TDD with ledger fixtures and explainability metadata | Open |
| Deterministic categorization rules are wrong or too broad | Transactions may be assigned to the wrong category or merchant | Keep Sprint 4 rules narrow, fake-fixture based, explainable, and reviewable; add golden fixtures for each new rule | Open |
| External SMS forwarding service changes payload format | Ingestion may break | Validate payloads and add contract tests | Open |
| Selected Android forwarder cannot send the shared secret as a header | Real SMS forwarding cannot be authenticated with the current endpoint contract | Verify header support during fake-device setup; if unavailable, add a narrowly scoped tokenized endpoint or switch to SMSGate | Open |
| Android background restrictions stop SMS forwarding | Transactions may be delayed or missed | Document required permissions, battery optimization settings, and fake end-to-end test steps before real ingestion | Open |
| Linode production deployment exposes inbound SMS endpoint before HTTPS/auth hardening | Financial SMS data could be intercepted or submitted by unauthorized clients | Caddy HTTPS is verified, the app port is not public, and a strong secret is configured; still add authenticated ingestion contract tests before real ingestion | Partially mitigated |
| SQLite database on a VPS is not backed up | User could lose transaction history if the server disk fails | Backup/restore commands are documented and smoke-tested with fake data; choose off-server backup storage before relying on real data | Partially mitigated |
