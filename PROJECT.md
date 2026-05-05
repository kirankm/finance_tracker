# Product Spec: Automated SMS-Based Expense Tracker

## 1. Product Goal

Build an automated personal expense tracker that reads transaction SMS messages, converts them into structured transactions, tags and categorizes them, detects mismatches, and provides review, analysis, and insights.

The core goal:

> Make SMS-based expense tracking trustworthy with minimum manual work.

---

## 2. V1 Scope

V1 should focus on reliable automated tracking from SMS.

### V1 Includes

- SMS ingestion via external SMS forwarding service / inbound SMS pipeline
- Transaction parsing
- Account mapping
- Merchant normalization
- Transaction type / purpose / category tagging
- Duplicate detection
- Ledger sanity checks
- Review queue
- Manual add/edit/delete
- Cash account tracking
- Structured search and filters
- Analysis screen
- Insights screen
- Import/export and backup
- Audit trail / correction history

### V1 Excludes

- Bank integrations
- LLM chat over expenses
- Split transactions
- Recurring pattern detection
- Budgeting
- Investment holdings tracking
- Advanced net worth dashboard
- Native Android SMS-reading app

---

## 3. Core Transaction Model

Every SMS should be converted into a structured transaction.

```yaml
transaction:
  id: txn_001
  date: 2026-05-04
  amount: 480
  transaction_type: debit
  purpose: expense
  category: food_delivery
  merchant_raw: "UPI/SWIGGY/ORDER123"
  merchant_canonical: "Swiggy"
  account: hdfc_savings
  source: sms
  confidence:
    parsing: high
    merchant_mapping: high
    category: medium
  review_status: needs_review
  duplicate_status: unique
  ledger_status: included
```

---

## 4. Transaction Type

Each transaction must have a `transaction_type`.

Suggested values:

- debit
- credit
- transfer
- refund
- reversal
- fee
- cash_adjustment
- unknown

---

## 5. Purpose

Each transaction must also have a `purpose`.

Suggested values:

- expense
- income
- transfer
- investment
- savings
- refund
- reversal
- cash_update
- unknown

This is important because investments and transfers should not appear as normal expenses.

Example:

```yaml
transaction_type: debit
purpose: investment
category: mutual_fund
```

---

## 6. Categories

Categories are user-editable.

Initial categories:

- food_delivery
- groceries
- travel
- shopping
- rent
- utilities
- medical
- family
- household
- subscriptions
- salary
- investment
- cash_spend
- fees
- unknown

The system should allow new categories to be created manually.

---

## 7. Soft Intent Type

Each category can optionally have an `intent_type`.

Suggested values:

- committed
- controllable
- lifestyle
- support
- emergency
- wealth_building
- unknown

This is not budgeting yet. It is just a soft classification for better future insights.

---

## 8. Accounts

The app must support multiple accounts.

Suggested account types:

- cash
- bank_account
- credit_card
- upi_wallet
- investment
- loan
- asset
- liability

Example:

```yaml
account:
  id: hdfc_savings
  name: HDFC Savings
  type: bank_account
  balance_tracking: true
```

Cash must be treated as its own account.

```yaml
account:
  id: cash_wallet
  name: Cash Wallet
  type: cash
  current_balance: 4200
  last_manual_update: 2026-05-04
```

---

## 9. SMS Ingestion

V1 should not build a native Android SMS-reading app.

V1 should ingest SMS through an external SMS forwarding app/service or equivalent inbound SMS pipeline that sends new SMS messages to the backend.

The backend should receive inbound SMS payloads, validate them, store the raw SMS safely, and then parse/classify the message into transaction candidates.

Flow:

```text
New SMS arrives on phone
→ external SMS forwarding service sends payload to backend
→ backend validates inbound payload
→ backend stores raw SMS safely
→ app checks whether it looks like a financial transaction
→ parser extracts structured data
→ account is mapped
→ merchant is normalized
→ category/type/purpose are assigned
→ duplicate checks run
→ ledger sanity checks run
→ item enters review queue if needed
```

Native Android SMS reading can remain a later option if the forwarding-service approach becomes unreliable or limiting.

---

## 10. Parsing

The parser should extract:

- amount
- date/time
- transaction direction
- merchant/payee
- bank/account clue
- available balance, if present
- transaction reference, if present
- raw SMS source

If parsing fails, the transaction should go to `unmapped`.

---

## 11. Merchant Normalization

The app should maintain canonical merchants.

Example:

```yaml
raw_merchant: "UPI/SWIGGY/ORDER123"
canonical_merchant: "Swiggy"
merchant_group: "Food Delivery Apps"
```

LLM can suggest merchant normalization rules.

```yaml
suggested_rule:
  condition:
    raw_merchant_contains_any:
      - "SWIGGY"
      - "RAZORPAY SWIGGY"
  canonical_merchant: "Swiggy"
  default_category: food_delivery
```

These can be soft-applied automatically, but should remain editable.

---

## 12. Rules and LLM Suggestions

The system should separate:

- user-approved rules
- user corrections
- existing deterministic rules
- LLM soft suggestions
- unknown/unmapped

Priority order:

```text
User-approved rule
> User correction
> Existing rule
> LLM soft suggestion
> Unknown
```

If the user edits an LLM-suggested category or merchant, the system may create or update a future rule.

Example:

```text
User changes Swiggy Instamart from food_delivery to groceries.

System suggests:
“Apply Groceries to future Swiggy Instamart transactions?”
```

---

## 13. Review Queue

The review screen should show transactions that need attention.

Statuses:

- auto_approved
- needs_review
- unmapped
- suspicious
- possible_duplicate
- ledger_mismatch
- possible_transfer
- possible_refund

The aim:

> User should only review uncertain or important items.

---

## 14. Duplicate Detection

V1 must include duplicate detection.

Duplicate signals:

- same amount
- nearby timestamp
- same/similar merchant
- same account clue
- same transaction reference
- similar SMS content

Statuses:

- unique
- possible_duplicate
- confirmed_duplicate
- ignored_duplicate

Duplicates should not affect analysis or ledger calculations unless confirmed as unique.

---

## 15. Ledger Sanity Checks

The app should perform account-level daily sanity checks.

Formula:

```text
opening balance
- debits
+ credits
= expected closing balance
```

Compare expected closing balance with observed closing balance from SMS, if available.

Example:

```yaml
daily_ledger_check:
  date: 2026-05-04
  account: hdfc_savings
  opening_balance: 52000
  total_debits: 3250
  total_credits: 10000
  expected_closing: 58750
  observed_closing: 57950
  mismatch: 800
  status: needs_review
```

The app should highlight likely problem days causing the mismatch.

---

## 16. Cash Tracking

Cash is an account.

User can manually update current cash balance at any time.

Example:

```text
Expected cash: ₹5,000
User reported cash: ₹4,200
Difference: ₹800
Action: mark as uncategorized cash spend?
```

Cash transactions can be manually added.

---

## 17. Manual Transaction Management

Manual entries are first-class transactions.

User can:

- add expense
- add income
- add cash spend
- edit transaction
- ignore transaction
- mark duplicate
- delete transaction
- restore transaction
- change account
- change category
- change merchant
- change purpose/type

Use soft delete, not hard delete.

```yaml
status: active | ignored | duplicate | deleted
```

---

## 18. Audit Trail

Every automated and manual change should be recorded.

Example:

```yaml
history:
  - system_parsed_sms
  - llm_suggested_category: food_delivery
  - user_changed_category: groceries
  - rule_created_from_user_correction
```

This is required for trust and debugging.

---

## 19. Search and Filters

V1 should include structured search, not LLM chat.

Filters:

- date range
- account
- transaction type
- purpose
- category
- merchant
- amount range
- review status
- duplicate status
- ledger status
- source

---

## 20. Screens

### Screen 1: Tag Review

Purpose: review transactions and fix uncertain mappings.

Shows:

- merchant
- amount
- date
- account
- suggested category
- suggested purpose
- matched rule
- confidence
- review actions

Actions:

- accept
- edit category
- edit merchant
- change account
- mark duplicate
- ignore
- create rule

---

### Screen 2: Analysis

Purpose: show where money went.

Examples:

- monthly spend by category
- spend by account
- income vs expense
- investments/savings separately
- cash balance changes
- unmapped transactions count

This should be mostly deterministic, not LLM-generated.

---

### Screen 3: Insights

Purpose: highlight things worth noticing.

Examples:

- Food delivery increased this month.
- There are 5 unmapped transactions.
- May 4 has an ₹800 ledger mismatch.
- Cash balance is lower than expected by ₹1,200.
- Possible duplicate transactions found.

LLM can help write insight explanations, but calculations should come from structured data.

---

## 21. Import / Export / Backup

Must support:

- export to CSV
- export to JSON
- local backup
- restore from backup

---

## 22. V2 Ideas

- Bank integration
- LLM chat interface: “Ask my money”
- Split transactions
- Recurring commitments
- Budgeting
- Investment holdings
- Net worth dashboard
- Natural-language rule creation
- Advanced anomaly detection

---

## 23. Engineering Principle

The product should not assume the LLM is always correct.

Core principle:

> LLM proposes, rules apply, user corrections improve the system.

Final V1 goal:

> Automated enough to reduce manual work, transparent enough to trust, editable enough to recover from mistakes.