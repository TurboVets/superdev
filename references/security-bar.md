# SuperDev security bar (load on Path 5.5 / Path 7 when the diff touches

# auth, outbound URLs, uploads, webhooks, HTML rendering, tokens, or PII)

Mined 2026-08-12 from Tan Kucukoglu's shipped hardening series in the offline
PR corpus. **Provenance note:** these rules come from the PR bodies of fixes he
authored, not from review comments — they are the shapes he ships and therefore
the shapes the house has accepted, not preferences he argued for. Every quote
below is machine-verified against the corpus.

Two-fifths of his authored PRs are `fix(auth)` / `fix(security)` / `chore(deps)`.
His hardening PRs carry an explicit **Residual risk** section: state what the
fix does _not_ cover, then file it. That habit is what produced the follow-up
PRs cited under F3 in `review-bar.md`.

---

## S-1 — Outbound URL handling (SSRF)

Any user- or admin-supplied URL that the server fetches is an SSRF surface.
Validate at every entry point, not just the obvious one: allow only
`http`/`https`, resolve the host, and reject private, loopback, link-local and
cloud-metadata targets (#8897; residual sweep in #9187). Connector `baseUrl`
and `tokenUrl` are two separate surfaces — hardening one leaves the other.

## S-2 — No enumeration oracles

Login, invite, password-reset and lookup endpoints must not vary in response
shape, error text, or **timing** by whether the account exists. Compare against
a dummy hash when the user is absent so the work is constant, and keep the
failure message identical (#9068).

## S-3 — Lockout that survives distribution

Per-account lockout must be enforced server-side and independently of per-IP
throttling, so a distributed attacker cannot rotate IPs out of the limit
(#7630). UI-side cooldown is not an abuse control.

## S-4 — Object keys are opaque, and replaced objects are deleted

Public asset keys must not be guessable or derived from user identifiers; on
replace, delete the old object rather than orphaning it (#8993). Anything
reachable by URL is public regardless of the UI that produced it.

## S-5 — Sanitize before render; never bypass

Server-provided HTML gets sanitized before it reaches the template.
`bypassSecurityTrustHtml` is not an escape hatch for "our own" content
(#9082). Formly `new Function` template expressions are untrusted input.

## S-6 — Webhook HMAC verifies the raw body

Signature verification must run against the raw request bytes, before any JSON
parse or body-transform middleware — a re-serialized body will not match
(#8226).

## S-7 — Mass-assignment on trust-bearing fields

Update mutations must never accept verification, entitlement, role, or status
fields from the client. Block them at the DTO, not in the service (#7628).

## S-8 — Privacy flags are honored in every query path

An opt-out like `allowLookup` has to be applied in each search and lookup
resolver, including admin-adjacent ones (#8227). One unfiltered query defeats
the flag everywhere.

## S-9 — Fail closed on unknown actor kinds

An authorization `where` builder must deny by default. If a new actor kind
(Admin, service, POA) falls through the branch chain with no ownership filter,
the query returns everything (#9079). Enumerate every actor kind the builder
can receive and assert the deny in a test.

## S-10 — Dependency alerts cover nested manifests

Scanning the root `package-lock.json` is not coverage: nested manifests and
GitHub Actions workflow pins are separate dependency trees and need their own
resolution pass (#8690).

## S-11 — Token revocation is strict, and residual risk is stated

Session invalidation must be enforced on the server (denylist / strict
revocation), and the PR must state honestly what remains exposed — e.g. a
stolen valid cookie window before revocation lands (#9030). "Residual risk:
none" on a security PR is a claim that needs the same proof as any other.

---

## How to use this in a review

1. Classify the diff: does it accept a URL, render HTML, take an upload, verify
   a webhook, mint or check a token, or read PII? If yes, this file applies.
2. Walk S-1…S-11 against the changed entry points, **including siblings the
   diff did not touch** — the dominant defect is a partial sweep.
3. Require the fix PR to name its residual risk and file the follow-up, rather
   than implying complete coverage.
