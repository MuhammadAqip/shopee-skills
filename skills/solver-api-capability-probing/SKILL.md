---
name: solver-api-capability-probing
description: Probe a captcha-solver API's live methods before wiring it.
version: 1.0.0
author: curator
license: MIT
metadata:
  hermes:
    tags: [captcha, solver, api, recaptcha, turnstile, playwright, probe]
    related_skills: [captcha-solver-api-integration, browser-signup-farming, proxy-pool-operations]
---

# Solver-API Capability Probing & Solve-Loop Hardening

Before wiring any captcha-solver API to a target, and before claiming a target
"cannot be solved", PROBE the live API. Vendor docs advertise methods the backend does
not implement; and a browser solve loop that half-works hides real bugs behind apparent
"proxy flakiness". This skill is the empirical layer above `captcha-solver-api-integration`
(which documents specific vendors and payload shapes).

## When to Use

- You are handed a solver API key + docs URL and asked to solve a target's captcha.
- A solve returns a "method not supported"-class error and you must decide whether the
  provider is incapable or you are calling it wrong.
- A batch farm shows per-account failures and you need to separate proxy variance from a
  real solve-loop bug.

## 1. Probe the live method registry (docs are marketing, not a contract)

For 2captcha-shaped APIs (`POST /in.php`, `GET /res.php`), the **error code is the tell**:

```
ERROR_NO_SUCH_METHOD          -> the slug is NOT registered (do not wire this target type)
ERROR_BAD_PARAMETERS          -> REGISTERED; body incomplete (a REAL method returns this)
ERROR_EMPTY_IMAGE / URL_EMPTY -> REGISTERED; needs the image/url field
ERROR_KEY_DOES_NOT_EXIST      -> wrong transport / wrong field name (see below)
```

- Sweep candidate slugs (`userrecaptcha`, `recapv2`, `recapv3`, `hcaptcha`, `turnstile`, …)
  and trust `BAD_PARAMETERS` over `NO_SUCH_METHOD`.
- **Probing is free** on these APIs — charge happens ONLY on a successful solve; unsolved /
  expired tasks refund. So the sweep costs nothing (confirm the balance is unchanged after).
- **Always run a known-good control method on the SAME key** in the SAME call shape in the
  same probe. If the control returns `BAD_PARAMETERS` and your target slug returns
  `NO_SUCH_METHOD`, the absence is real, not a request-shape artifact.
- **The category the docs push hardest can be the one that is absent.** A provider may ship
  full example payloads for a captcha family (sitekey/version/domain) while that family's
  slug returns `NO_SUCH_METHOD` and dozens of others return `BAD_PARAMETERS`. Placeholder
  example values (`6LdABC123...`) are the tell that the doc page was written ahead of the
  backend and never tested end-to-end.
- **Two-transport tell:** a wrong field name returns `ERROR_KEY_DOES_NOT_EXIST` on
  form-encoded POST but `NO_SUCH_METHOD` on JSON. JSON is the correct transport; the field
  is `methods` (plural), not `method`.

## 2. Distinguish "provider incapable" from "origin flaky" (both cost days)

- **521 from Cloudflare on `api.`/`docs.`/apex simultaneously, from multiple egress IPs,
  is the ORIGIN being down** — not an IP block on your side. Re-poll a few times; if it
  flips 521→200 opportunistically, the vendor is flaky and is not a production
  foundation regardless of method support. Report this as a separate axis from capability.
- Conclusion shape for the operator: "API can do <registered list>; it cannot do <absent
  family>; and it is <stable|flaky> — so for target X use <free/other solver>." Never
  report capability without also checking stability when the target gates a batch job.

## 3. Harden the browser solve loop (separate the real bug from proxy flakiness)

A datacenter IP makes reCAPTCHA escalate; a residential proxy fixes that but is SLOW, and
slow introduces its own failure modes that look like "the solver broke". Fix these before
blaming the proxy or the solver:

- **Self-heal a reset challenge.** A reCAPTCHA audio/image challenge RESETS after a
  failed/delayed attempt and drops back to the checkbox/anchor state, so `#audio-source`
  stops resolving forever. Re-click at TWO sites: once at the top of the outer attempt,
  AND inside the inner poll loop (guard with `if button.count(): click` else
  `re-click the anchor`). Log the recovery branch — its presence proves the self-heal
  fired; without it the account burns every attempt. After N consecutive no-audio polls,
  BAIL the attempt entirely (fresh page + fresh challenge) rather than polling a dead
  widget.
- **Retry the submit click independently of the solve.** A slow residential proxy throws
  `TimeoutError` on the REGISTER/SUBMIT click AFTER the captcha already solved — the
  correct solve is wasted. Wrap it:
  `click("button[type=submit]", timeout=15000, no_wait_after=True)` in a 3x retry loop,
  with a JS fallback `eval_on_selector("button[type=submit]", "el=>el.click()")`, then
  poll `page.url` yourself to confirm the advance. `no_wait_after=True` stops Playwright
  binding the click to a navigation the proxy is too slow to complete. Symptom this fixes:
  a child log that shows a solved token twice then dies on the submit button.
- **Never conclude "the solver is broken" from a child-log failure without the cause.**
  Read the specific log: an audio-loop failure, a submit timeout, and a hard "Try again
  later" block are three DIFFERENT problems with three different fixes.

## 4. Scaling shape for a browser+solve farm

- A browser+solve account is ~1.5-2 GB (browser tree) plus a transcription/vision spike;
  compute the honest worker cap from `free -h` + `nproc` BEFORE proposing a parallel
  runner. On a 2-core / 7-8 GB box the cap is ~2 concurrent workers, not 20 — more thrashes
  swap during the overlap of render + transcript.
- A per-account retry budget (2-3 attempts, fresh proxy exit each) absorbs the ~1-in-N
  residential flakiness; the batch status is net-ok, not first-attempt-ok.

## 5. Subscribing an account farm to the same budget (credit harvest)

When the same solver is what your other farms consume, farming solver accounts on the
cheap and pooling their keys beats buying credits. The chain, and the one step per link
that is easy to get wrong:

```
random email on a CATCH-ALL domain -> GET register (csrf + session)
  -> solve captcha -> POST register
  -> poll inbox for activation link -> activate -> login -> scrape API key
  -> verify key against the credits endpoint -> store
```

- **Read the register outcome from the `Location` header, not the status code.** Success is a
  302 to `/login`; failure is a 302 to `/register`. Both are 302 — a status-code check cannot
tell them apart, and a body check is worse (the form looks identical either way).
- **Verify every scraped key against the vendor's credits endpoint before trusting it.** A
  regex like `[a-f0-9]{32}` against a dashboard page grabs the first 32-hex blob on the page,
  which after any UI change is a build hash or CSRF token. The credits call is the only
  authoritative check: returns a number = real key, returns an error = regex lied, re-scrape.
- **A catch-all domain removes the mailbox-per-account step entirely** — any local part
  arrives in the same inbox. Poll `api/mailbox/<address>`, extract the activation URL by
  regex, and require a minimum link length (~60 chars) so a truncated HTML-wrapped URL does
  not get clicked.
- **Retry with a NEW email, not the same one.** A register that half-succeeded leaves the
  address registered; the retry then fails with "already exists", which reads as the chain
  being broken when it is working.
- **Check solver balance against the batch cost before starting** (`count × cost_per_solve`,
  plus a 1.5x buffer for retries). A batch that dies on account 3 because the balance was 3
  tokens burns more time than the check costs.
- **Keep the account archive and the active key pool as separate files.** The archive
  (email + password + key) only grows; the pool (key -> credits) changes on every solve.
  Refreshing credit counts must never touch the archive — a bug in refresh should not be able
  to delete account records you cannot reconstruct.

## Pitfalls

- **Trusting a docs page over a live probe** — the advertised family may be unimplemented (Rule 1).- **Concluding "unsupported" from ONE failed call** — confirm against a known-good control
  method on the same key before declaring a method absent (Rule 1).
- **Reading a transient 521 as "my IP is blocked"** — check from multiple egress IPs; if all
  see 521 it is the origin (Rule 2).
- **Blaming the proxy/solver for a reset challenge or a slow submit** — both are loop bugs
  with specific fixes (Rule 3).
- **Checking the register status code instead of its `Location` header** — success and
  failure are both 302 (Rule 5).
- **Trusting a scraped key without a credits-endpoint check** — a 32-hex regex matches build
  hashes too (Rule 5).
- **Proposing a 20-worker scale on a 2-core box** — compute the real cap from RAM/CPU first (Rule 4).
