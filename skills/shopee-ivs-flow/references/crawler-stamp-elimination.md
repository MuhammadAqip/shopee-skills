# Diagnosing the `crawler_item` stamp — variable elimination

Run these probes in order. Stop at the first one that clears
`cart/mini`'s `90309999`; otherwise the list tells you where the gate is
*not*, which is what saves the next session from re-testing it.

## 1. Is the session even alive?

```python
api("/api/v4/account/basic/get_account_info", None, "GET")
```

`error: 0` with a correct `userid` proves auth is fine. `19` means the cookie
is dead — replace it before going any further.

## 2. Is the gate up?

```python
api("/api/v4/cart/mini", {"version_list": [3145728, 65]}).get("error")
```

`90309999` = stamped. Everything downstream (`precheck` → `10002`,
`otp/*` → `error_not_found`) follows from here and is not a separate bug.

## 3. Which variable owns the stamp?

| variable | how to change it | verdict |
|---|---|---|
| outbound IP | direct VPS, rotating proxy, sticky residential relay | **not the cause** — stamp survives all three |
| TLS fingerprint | `curl_cffi` `impersonate` in `chrome`, `chrome136`, `chrome131`, `safari`, `firefox` | **not the cause** — all return `403` + `90309999` |
| account | three live sessions, distinct userids | **not the cause** — identical `anti_bot_tracking_id` on every one |
| device cookies | drop `_sapid`/`SPC_F`/`SPC_SI`/`SPC_SEC_SI`/`sense_sa_r`/`_ga*`/`_fbp`/`fr` | **not the cause** — Shopee mints new ones, stamp persists |
| `@shopee-ac/scene` | set to `profile_page` | **not the cause** — SDK writes `crawler_item` back |
| localStorage / IndexedDB | hook fetch + XHR + `Storage.setItem` and scan | **empty** — nothing ever stored there |
| captcha | load `/verify/captcha` | **never renders** on a stamped session (`canvas:0`, `#captchaMask:0`, `img:1`) — SadCaptcha gets `no img`, credits untouched |
| `order_list` / `cart/get` as a health oracle | send a real Shopee Android UA; compare an account whose `op 23` returns `0` against one whose `op 23` returns `23500158` | **not an indicator** — both answer `90309999` identically. These endpoints reply that to essentially every web-PC request. Using them as the "stamped" tell fires a false flag on healthy accounts and, because the probe itself is traffic, walks the anti-abuse counter higher. Judge only by `otp/get_settings_v2`. |
| `SPC_ST` login token | re-login through `/buyer/login` in a clean profile | **the flag owner** — with no cookie at all `cart/mini` returns `200` and no gate fires; with any of four stored cookie sets it returns `90309999` on every egress tried (datacenter and Indonesian residential alike). A fresh token from a clean first-party origin is the fix. |
| **fabricated** anti-fraud headers | build `af-ac-enc-dat` / `x-sap-ri` / `af-ac-enc-sz-token` as random hex + mac and send them from a plain `requests` client | **this is a cause, and the loudest one** — every account and every number answered `90309999` on `get_settings_v2`; with the same four headers removed, the same cookie returned `op 23 -> error:0` on the first try. Absent headers pass, invented ones fail. Never synthesise them. |
| SDK request headers | `fetch()` from inside the page so the SDK signs it (`x-sap-sec` ~3,968 B, fresh `x-sap-ri`, fresh `af-ac-enc-dat`) | **not the cause** — same call still `403` + `90309999`. Building a signer is a dead end; stop asking for `x-sap-sec`/`x-sap-ri` generation when the gate is what is failing. |
| header reuse across endpoints | compare `x-sap-sec` length per URL from one page-context session | **reveals a hard rule** — same SDK, same session: `cart/mini` → 2,916 B, `account/management/change_phone_init` → 3,576 B, `change_phone_init_v2` → 3,596 B. The payload embeds per-endpoint context, so a header captured off one route is inert on another. Always drive the call from the page that owns it; a length mismatch is the tell that you are replaying the wrong one. |
| ingress path | reverse-proxy the shop (rewrite `home_url`, strip CSP, `<base href="/">`) and load it from the user's own handset on cellular | **this is the lever** — that path minted a *different* tracking id (`314aabcb818-e952-…`, UUID-shaped) instead of the shared `gqRjZGVr…` blob, proving the id is minted per ingress and that a clean first-party origin changes it. |

## 4. Where the stamp actually comes from

The traffic gate answers in the body of the very first API call, and the SDK
replays that id afterwards:

```
POST /api/v4/cart/mini {"version_list":[3145728,65]}
-> 403 {"3":90309999, "error":90309999,
        "6":{"1":"<challenge token>", "0":"<anti_bot_tracking_id>"}}
```

The id is present on the **first homepage request**, before any page JS runs,
with a freshly minted `_sapid`. That rules out every client-side store and
points at the login token or a server-side account classification.

## 5. What to reach for when the web path is closed

Ranked by whether it was actually observed to work:

1. **On-device origin** — Shopee Android app on a handset with a local SIM,
driven over `adb` + `uiautomator2`. The app signs natively; no browser
fingerprint is ever computed, so no stamp is applied. See the parent
SKILL.md's on-device section for the tunnelling setup.
2. **Human-driven login in a fresh profile over VNC** — same browser the
agent will use afterwards, so the session is never "moved". Use the VNC
recipe in the parent SKILL.md; it costs one captcha solve and produces a
natively-created `SPC_ST`.

Residential proxies are not on this list. See parent SKILL.md for the
mechanism (the handshake originates at the vendor's server, so the ASN still
reads as infrastructure).

## 6. Letting the user log in through a reverse proxy (last resort)

When the browser has to be the user's own (their IP, their device) but you must
control the session, run a small HTTP reverse proxy to `shopee.co.id` on the VPS
and have them open `http://<vps>:<port>/buyer/login` in their phone browser. It works —
the SPA renders, `POST /api/v4/account/login_by_password` fires and returns 200 — but
four things break it silently:

- **Duplicate `Set-Cookie` collapse.** `dict(resp.headers.items())` keeps only the last
  `Set-Cookie`; login succeeds server-side while the next request reports
  `is_logged_in=false`. Use `resp.getheaders()`, collect every `set-cookie`, and emit one
  `send_header("Set-Cookie", …)` per entry. Verify:
  `curl -D - -o /dev/null http://127.0.0.1:<port>/buyer/login | grep -ci set-cookie`.
- **`Set-Cookie` attributes must be stripped.** Remove `Domain=`, `Secure`, `SameSite=` or
  the browser refuses to store the cookie for the proxy origin.
- **`home_url` leaks the proxy IP.** The gate redirect echoes
  `home_url=http%3A%2F%2F<vps>%3A<port>`, which by itself re-triggers
  `/verify/traffic/error`. Rewrite every absolute `https://shopee.co.id` in HTML/JS/JSON
  bodies to a relative path, inject `<base href="/">`, and drop `Content-Security-Policy`.
- **Blank body with all assets at 200.** The login SPA needs time and reruns; poll for
  `input[name="loginKey"]` for ~45 s with a reload rather than waiting on
  `domcontentloaded`, and submit with `press("Enter")` because the `LOG IN` button text
  match is fragile (the button may not be a `<button>`).

Gate the effort: if the proxy still shows `/verify/traffic/error` after the rewrite, the
origin is flagged and no amount of proxy polish fixes it — go on-device.
