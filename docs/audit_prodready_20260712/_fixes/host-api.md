# Fixes — group: host-api — 2026-07-12

Owner files: host/server.py, host/multi_asset.py, host/exec_cards.py, admin/server.py,
lib/api_auth.py (NEW), db/seed_api_token.sql (NEW, not applied).

All owned files re-read in full at ~08:11 before editing (host/server.py, multi_asset.py, exec_cards.py were
touched by another session at 07:58–08:00; edits below are surgical on the CURRENT tree).

---

## 1. host/multi_asset.py — `kind:"dashboard"` on the multi-asset envelope [followups OBS-1 / host-api OBS-1]
- Grep first: no `kind` key anywhere in build_response_multi (confirmed on the 07:59 version).
- Added `"kind": "dashboard"` to the return dict, directly after `"ok"` — exact parity with the single-asset
  stamp in host/server.py build_response. host/web/src/types.ts declares the discriminant REQUIRED; the multi
  envelope was the one wire shape that lacked it.
- Test: tests/test_multi_asset.py — 10 passed.

## 2. host/server.py — handled 500s now visible to run_traced [host-api OBS-2]
- Status derivation read (obs/middleware.py:81-84): `status="error"` iff trace errors non-empty OR
  `resp.get("errors")` (PLURAL) truthy. The handled-500 envelopes used only `error` (singular), so a 500 landed
  in obs_traces/Inspector as status="ok".
- Fix: both catch-all handlers (handle_frame, handle_run) now return
  `{"ok": False, "error": …, "errors": {"http_500": …}}` — `error` singular stays byte-identical for the FE
  contract (api.ts reads it / httpError throws before body parse on !res.ok); `errors` plural is additive and is
  the exact key the middleware already checks, so no middleware edit needed (obs/middleware.py not mine).
- Success envelopes and 400 client-fault envelopes untouched (verified: handle_frame({}) → 400 without `errors`).
- Test: smoke — handle_frame with a bad render_card_id ("abc" → int() ValueError) returns
  (500, keys=[error, errors, ok]); middleware derivation over that envelope yields "error".

## 3. host/server.py — trace_id stamped BEFORE the disk dump [host-api OBS-4]
- Previously obs/middleware setdefault'ed trace_id onto the resp AFTER handle_run had already written
  outputs/logs/response_<run_id>.json → the recovery/payload_diff artifact couldn't join obs traces (run_ids are
  prompt-hashed and collide, H14).
- Added `_stamp_trace_id(resp)` helper (fail-open, reads obs.trace.current()) and called it immediately before
  BOTH `_dump_response(resp)` sites (knowledge terminal + dashboard leg). Middleware's `setdefault` explicitly
  yields to a handler-set value, so the wire copy is unchanged.
- Test: smoke — with an active trace, `_stamp_trace_id` writes the exact current trace_id; with no trace, no-op.

## 4. host/exec_cards.py — budget-race harvest [host-api OBS-5]
- The post-timeout `finally` sweep marked EVERY cid not in status_by_id as "executor budget exceeded" — including
  a future that COMPLETED between as_completed's TimeoutError and the sweep (real payload discarded).
- Fix: in the sweep, a `fut.done() and not fut.cancelled()` future has `fut.result()` harvested (returns
  immediately on a done future) → completed_by_id + ok status + exec stage record; a raised task takes the
  existing exception failure path; only genuinely-unfinished futures are cancelled + budget-blanked.
- Tests: (a) deterministic harvest-branch repro — as_completed patched to raise TimeoutError after the futures
  complete: both cards harvested ok (pre-fix this scenario budget-blanked both). (b) honest path preserved —
  0.3 s budget + 0.6 s card: still "executor budget exceeded", payload absent. (c) tests/test_render_guarantee_50.py
  offline: 1 passed, 2 skipped.

## 5. lib/api_auth.py (NEW) + host/server.py + admin/server.py + db/seed_api_token.sql (NEW) — R6 partial, default-OFF
- lib/api_auth.py: `require_token(headers) -> bool`; reads `cfg("api.token", "")` LAZILY per request (no restart
  to enable/rotate), empty/missing knob → True (auth disabled = today's behavior, byte-identical), non-empty →
  constant-time compare (hmac.compare_digest) against the `X-V48-Token` header; fail-OPEN on any error (a config
  outage can never lock out the API).
- host/server.py: gate at the top of do_GET + do_POST → 401 `{"ok":false,"error":"unauthorized"}` on mismatch.
  do_OPTIONS deliberately NOT gated (CORS preflight cannot carry custom headers).
- admin/server.py: same gate at do_GET + do_POST entry (:8790 serves full prompts/AI outputs — same exposure class
  as /api/inspector, OBS-3).
- db/seed_api_token.sql: declares the knob ('api.token', '', 'text', 'api', …) with ON CONFLICT (key) DO NOTHING
  (never clobbers an operator-set token). **NOT applied to the DB** (owner-gated per followups OBS-9).
- NOTE for enable-time (deliberately not done now — healthy-path byte-identical rule): when the owner sets the
  knob for BROWSER clients, `X-V48-Token` must be added to the `Access-Control-Allow-Headers` header in both
  `_send` methods, or CORS preflight will block the FE. curl/sweep clients are unaffected.
- Tests: smoke — knob unset → True; knob set (cfg monkeypatched) → False without header, False on wrong token,
  True on match (case-insensitive header lookup), False on headers=None.

## 6. host/server.py — obs file-retention wired at boot [OBS-6 / H15]
- `main()` now calls `obs.retention.ensure_started()` (idempotent daemon prune thread, built by the concurrent
  obs session; its docstring says "the host owner wires ensure_started() at boot" — this is that wire) inside
  try/except → boot stays safe whether or not the module exists.
- Verified: obs/retention.py exists NOW, import is side-effect-free (not self-starting), ensure_started callable.
  NOT invoked in tests (a real call would prune outputs/logs — forbidden side effect); the wiring takes effect on
  the next :8770 restart (restart itself is out of scope per the brief).

---

## Gates
- `python3 -m py_compile host/server.py host/multi_asset.py host/exec_cards.py admin/server.py lib/api_auth.py` — clean.
- `python3 -c "import host.server, host.multi_asset, host.exec_cards, admin.server"` — imports ok (no server start).
- Offline pytest (`ls tests | grep -iE "exec_cards|server|multi"` + the two files importing build_response):
  tests/test_multi_asset.py tests/test_fe_data_note_serve.py tests/property/test_prop_host_knowledge_terminal.py
  tests/test_render_guarantee_50.py → **26 passed, 2 skipped, 4 deselected** (skips/deselects = live-marked, pre-existing).
- No service restarts, no DB writes, no git operations.
