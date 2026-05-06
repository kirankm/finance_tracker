# Sprint 10: Minimal Review UI

## Goal

Provide a usable local web workflow to inspect fake SMS candidates, correct fields, mark items reviewed, promote reviewed items, and verify promotion status without using raw API calls.

## Scope

- Replace the placeholder home page with a dense operational review queue screen.
- Require the existing `X-Inbound-SMS-Secret` value before loading review data or sending review actions.
- List pending review candidates without showing raw SMS bodies in the broad list.
- Show a selected review item detail view with raw SMS body only after explicit item selection.
- Display parsed candidate fields, confidence, parser metadata, rule metadata, correction metadata, duplicate status, ledger status, and ledger sanity status where present.
- Support candidate correction actions for the Sprint 9 correction fields through the existing backend API.
- Support marking a candidate reviewed through the existing review API.
- Support promoting reviewed candidates through the existing promotion API.
- Show action results and errors clearly without logging or displaying secrets.
- Keep the UI minimal, local, authenticated, and operational rather than analytical or decorative.
- Add HTTP-level and template/UI smoke tests appropriate for the current FastAPI/Jinja stack.

## Out of Scope

- Analysis dashboard.
- Insights screen.
- Mobile app.
- Polished account/category management.
- Dedicated frontend build system unless the existing server-rendered approach proves insufficient.
- Multi-user authentication.
- Broad raw SMS browsing outside explicit detail views.
- Duplicate resolution UI beyond showing the existing duplicate metadata.
- Ledger sanity recalculation or mismatch resolution UI.
- Real SMS examples, real merchant names, real account identifiers, or secrets.

## Expected Changes

- `app/templates/index.html` replacement with the minimal review UI.
- `app/main.py` route/template context changes if needed.
- Optional small static CSS/JS files only if keeping all UI code in the template becomes unwieldy.
- Tests for authenticated review UI behavior in `tests/test_review_ui.py` or equivalent.
- Existing review queue, correction, and promotion tests only if response shapes need small compatibility updates.
- `README.md` update for local UI usage.
- `project-status.md`.

## Tests to Write First

- Home page renders the minimal review UI shell without exposing the inbound SMS secret.
- Review queue list fetch behavior requires a user-provided secret and does not include raw SMS body in broad list rows.
- Selected item detail can display raw SMS body only for the selected item detail path.
- UI correction action sends only supported correction fields and surfaces validation errors.
- UI review action can mark a fake candidate reviewed.
- UI promotion action can promote a reviewed fake candidate and surface `ledger_transaction_id`, `duplicate_status`, `ledger_status`, and `ledger_sanity_status`.
- Existing authenticated API behavior for review queue, corrections, and promotion continues to pass.
- No real SMS, real merchant names, real account identifiers, or secrets appear in fixtures or rendered test snapshots.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_review_ui.py tests/test_review_queue.py tests/test_corrections.py tests/test_ledger_promotion.py
```

## Acceptance Criteria

- A fake SMS can be ingested through the existing API, then reviewed, corrected if needed, promoted, and verified from the web UI.
- Raw SMS bodies are omitted from broad list views and shown only in selected detail context.
- The UI does not hard-code or leak the shared secret.
- The UI is usable on desktop and mobile widths without overlapping text or controls.
- Existing backend review, correction, promotion, duplicate, and ledger sanity behavior remains intact.
- Relevant tests, lint, and typecheck pass through Docker.
- CI passes before merge.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Build the Docker app image after code/test edits.
- [ ] Start the app locally and open `http://localhost:8000`.
- [ ] Enter the development shared secret and verify pending fake SMS candidates load.
- [x] Verify the queue list does not show raw SMS body.
- [x] Select one fake SMS and verify raw SMS body appears only in detail.
- [x] Correct merchant/category from the UI and verify correction metadata remains visible.
- [x] Mark the candidate reviewed from the UI.
- [x] Promote the reviewed candidate from the UI and verify promotion status fields are shown.
- [x] Try an invalid correction and verify the UI surfaces the error without mutating data.
- [ ] Verify desktop and mobile viewport layouts do not overlap text or controls.
- [x] Verify production code paths do not log full raw SMS content or sensitive payloads.

## Risks / Open Questions

- The existing shared-secret auth is service-level, not a browser session model; Sprint 10 should keep this local and explicit rather than pretending it is production user auth.
- Raw SMS detail exposure must stay constrained because the browser UI makes inspection easier than API calls.
- Server-rendered HTML with inline JavaScript may be enough for Sprint 10, but later account/category management could justify a fuller frontend structure.
- UI tests may need to stay at HTTP/template level unless a browser test dependency is added deliberately.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued without a separate plan review at user request.

- Replaced the placeholder home page with a server-rendered minimal review queue UI.
- The UI prompts for the existing shared secret and uses it only in request headers.
- The pending list omits raw SMS bodies; selected detail fetches and displays the raw body explicitly.
- Added candidate correction, mark-reviewed, and promote actions against existing APIs.
- Added HTTP/template-level tests in `tests/test_review_ui.py`.
- Focused Sprint 10 tests passed with `docker compose run --rm app python -m pytest tests/test_review_ui.py tests/test_review_queue.py tests/test_corrections.py tests/test_ledger_promotion.py`.
