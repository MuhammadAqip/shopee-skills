---
name: shopee-account-phone-change
description: Change or set a Shopee account phone via OTP ops 23/18.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [shopee, otp, change-phone, anti-abuse, telegram-bot]
    related_skills: [shopee-sms-otp-bypass, shopee-token-war-stack, shopee-antifraud-reversing, shopee-ivs-flow]
---

# Shopee Account Phone Change (ganti / set nomor)

## When to Use

Load when the task is changing or setting a Shopee account phone number: "ganti
nomor Shopee", "change number", "set phone", op 23 / op 18, a bot feature that asks
for a cookie then a new number, or when `get_settings_v2` keeps answering
`23500158` / `23500101` / `23500000`. Also load when a phone-change flow "does
nothing" in a Telegram bot and you must decide whether the account is burnt or the
handler is wrong.

Changing an account phone number is one HTTP flow, not a browser flow. Only the
final commit needs a warm webpack runtime. Budget: `check_account` ~0.06 s,
`check_number` ~0.21 s, `send_vcode` ~0.20 s, commit ~1 s warm.

## Decision order — before touching any number

1. Validate the cookie: `GET /api/v4/account/basic/get_account_info`.
   `error 19` = residue, not a session. Stop.
2. Triage the ACCOUNT before blaming a number (see below).
3. `change_phone_init_v2` — alone tells you whether the account can do this at all
   (`ivs_required`, `ongoing_request_phone`, token size).
4. `get_settings_v2` with operation **23**; fall back to 18 only if 23 answers
   `23500158`. Never sweep both ops across several numbers "to be sure" — each
   call burns the per-account counter.

## Operation enum

| op | scene | `need_captcha` | verdict |
|---|---|---|---|
| **23** `AccountChangePhone` | `phone_otp_account_change_phone` | **false** | try late; the real flow uses **0** |
| **0** `General` | `others` | **false** | **the operation the working change-phone client sends** — see below |
| **18** `AccountSetPhone` | `phone_otp_account_set_phone` | **true** | fallback; `send_vcode` -> `23500101` |
| 7 / 8 | login / signup | true | never |
| 0 | `others` | false | full channel list `[3,2,1]` on a healthy session — **default op** |

**`operation: 0` is the value the working client sends, despite 23 being named
`AccountChangePhone`.** Verified live: a hand-rolled client sending `23` was
answered `23500158` on several accounts while the same cookie answered
`op 0 -> error:0, ch:[3,2,1], cap:false`. The enum name is not evidence — copy the
operation from the bundle call site, and keep an `OP_CHAIN = (0, 23, 18)` so a
gated op falls through instead of aborting the flow.

`get_settings_v2` returns **`need_login`** as well as `need_captcha`. True
`need_login` alone does not block `send_vcode`; true `need_captcha` does.

## Pipeline

```
1. init:     POST /api/v4/account/management/change_phone_init_v2 {phone, seq_no:null}
             -> data.change_phone_token (~236 B; ~804 B when ivs_required)
2. settings: POST /api/v4/otp/get_settings_v2 {phone, operation:23}
             -> seed, available_channels, preferred_channel, need_captcha, need_login
3. send:     POST /api/v4/otp/send_vcode {phone, channel, operation:23, seed}
             -> otp_tracking_id (== seed)
4. verify:   POST /api/v4/otp/verify_vcode {phone, vcode:<code>, operation:23,
                                           m_token:<change_phone_token>}
             -> data.vcode_token (~236 B)
5. commit:   warm webpack runtime -> req("66199").K.changePhoneCommitV2(
               {phone, changePhoneToken, vcodeToken})
             -> {error:0, data:{is_delayed:false}}
```

Pitfalls with mechanism:

- **Field is `vcode`, not `code`** for account-management ops (op 0 signup keeps
  `code`). Wrong field answers `23500000`, indistinguishable from a bad OTP.
- **`operation` must be identical at settings / send / verify.** A valid code
  rejects when send used 18 and verify used 23.
- **Commit cannot run over plain HTTP** — `/change_phone_commit_v2` answers
  `10002` because the calling service module exists only in a lazy chunk. Load
  `req.e(8167)` (ChangePhoneNumberV2), `req.e(5358)` (V3), `req.e(896)`
  (AddPhoneNumberV2), then `req("66199").K`. Do **not** route through
  `req(7231)` — circular dep `Cannot access 'N' before initialization`.
- `vcode_token` also travels as a query param on the post-verify navigation
  (`?vcode_token=..&seed=..`).
- Channels: `3` WhatsApp, `2` voice, `1` SMS. Offer only what
  `available_channels` lists — a number can be voice-only.

## Error taxonomy

| code | meaning | action |
|---|---|---|
| `23500158` | account-level anti-abuse block on the OTP settings path | stop; triage the account |
| `23500152` | per-number rate limit | later / another number |
| `23500101` | captcha demanded at **send** though settings said false (typical of op 18) | switch op or surface captcha |
| `23500000` | code mismatch — check the field name first | |
| `23500002` | code superseded by a later `send_vcode` | re-send, newest code |
| `31500000` | OTP session expired | restart from send |
| `90309999` | TRIGGER_ANTI_CRAWLER, **scoped** — on `get_settings_v2` it means blocked; on `order_list`/`cart` it is the normal web-PC answer | judge only by `get_settings_v2` |
| `19` | cookie is residue, not a session | new cookie |

## Triage: account flagged vs number blocked

Every number failing — including one never used — means the number is not the
problem. **`get_settings_v2` is the only valid health signal.** `get_order_list`
and `cart/get` answer `90309999` for essentially every web-PC request, on healthy
accounts too — they are not indicators and must stay out of any health check:

```
GET  /api/v4/account/basic/get_account_info                   -> 0     (auth OK)
POST /api/v4/account/management/change_phone_init_v2          -> ivs_required?
POST /api/v4/otp/get_settings_v2 {operation:23}               -> the verdict
POST /api/v4/otp/get_settings_v2 {operation:0}                -> 23500158 when flagged
```

Reading `order_list`/`cart` as "flagged" produces a false `AKUN KENA FLAG
ANTI-CRAWLER` warning on every account, including ones whose `op 23` returns 0 —
and probing them on each cookie paste adds to the anti-abuse counter. Probe with a
single dummy phone (`628000000000`) against `get_settings_v2` op 23, then 18, and
map the codes: `0` → ok, `23500101` → ok (probe number needs captcha, account
fine), `23500158`/`23500152`/`90309999` → limited, `init_v2.ivs_required` → ivs,
`get_account_info` non-zero → dead.

Elimination matrix — each line rules a cause out:

| Variable changed | Result | Rules out |
|---|---|---|
| fresh never-used number | still 23500158 | the number |
| different residential IP | still 23500158 | the IP |
| forged / absent `af-ac-enc-dat`, `x-sap-ri` | still 23500158 | the SAP headers |
| different account cookie | `op 23 -> error 0` | confirms the first account is flagged |
| 5 min after a success, code unchanged | ok -> 23500158 | per-account request counter |

The counter climbs within a few dozen requests. Budget **one** probe per
debugging cycle; 3 ops × 3 numbers spends nine and deepens the block. Recovery is
a fresh account cookie or roughly a day.

### Before any of that: is the request itself real?

`23500158` / `90309999` on **every** account and **every** number at once is the
signature of a malformed request, not a block. Diff what you send against a call
known to have succeeded on the same endpoint before spending a single probe:

Two gates run in order, and both must pass before any probe counts:

**Gate A — the request shape.** A client can be wrong in three independent ways
(headers, body, egress) and each one alone produces `90309999` / `23500158` on
healthy accounts. Fix shape first; only then does a probe mean anything. This
session's own history is the cautionary case: a fabricated header set, a proxy
that was never wired into `Api.__init__`, and a health helper that probed
`order_list` were three separate causes of the *same* false "account flagged"
verdict, discovered one at a time across hours. Reproduce the known-good request
shape and check egress IP in one pass instead of eliminating causes serially.

- **Never fabricate a signature header.** Random values in `af-ac-enc-dat`,
  `x-sap-ri`, `af-ac-enc-sz-token`, `x-sz-sdk-version` are unverifiable
  ciphertext — the gate answers `90309999` for the whole session and it reads
  exactly like a burnt account. Absent headers are accepted; invented ones are
  not. Verified: removing those four turned `90309999` into `op 23 -> error:0` on
  the same cookie, first try. Keep only the ordinary set: `User-Agent`, `Accept`,
  `Accept-Language`, `Content-Type`, `Origin`, `Referer`, `x-api-source`,
  `x-requested-with`, `x-csrftoken`, `x-shopee-language`, plus `Cookie`.
- **Send the full body.** `get_settings_v2` wants
  `{operation, phone, supported_channels: [1,2,3], support_session: false}`;
  `send_vcode` wants `{phone, channel, operation, force_channel: false,
  supported_channels: [1,2,3], seed}`. A trimmed body answers `10002`
  (params short), which reads like a missing auth step.
- **Keep a known-good script in the repo** — the flow that worked end to end once
  — and re-run it against the exact cookie the bot is failing on. Success there
  plus failure in the bot isolates the bug to the bot's request shape, and no
  account or number is consumed reaching that conclusion.

Other per-account states, all visible in `init_v2`:

- `ivs_required: true` + 804 B token — identity verification pending; change-phone
  is impossible until IVS completes in the app. Report, never retry.
- `ongoing_request_phone` non-empty — earlier change still pending.
- `verified: false` / `phone: null` — no number yet; that is op **18** territory.

### Health check must not call the endpoint it is measuring

A health helper that POSTs `get_settings_v2` to decide whether `get_settings_v2`
is blocked moves the counter it reports on. Check the account with endpoints that
carry no OTP cost, and treat `get_settings_v2` as a deliberate, budgeted probe
rather than a startup check:

```
cookie paste -> get_account_info          error:0  -> alive
             -> change_phone_init_v2      ivs_required:true -> IVS branch, stop
                                          error:0           -> ready, proceed
```

This classifies `dead` / `ivs` / `ready` with zero OTP requests, so pasting the same
cookie repeatedly is harmless. Only the actual number submission spends the
counter. When a user reports "all my accounts are blocked" after pasting several
cookies in a row, suspect the health helper before suspecting the accounts.

**Never probe `get_settings_v2` inside the health path at all.** Even a single
budgeted probe per cookie paste multiplies across a multi-account test session:
three pastes = six calls and three accounts that later report `23500158`. Health is
`get_account_info` + `change_phone_init_v2` only; the OTP counters are spent the
first time a real number is submitted and nowhere else.

## Verify the relay before blaming Shopee

A SOCKS relay started without its credentials env forwards from the VPS IP, which
looks exactly like an anti-abuse block:

```
curl -s -x http://IP:PORT https://api.ipify.org   # expect the residential IP
```

Empty / 502 = relay not authenticating. A unit with bare `ExecStart` and no
`EnvironmentFile=` has empty `UP_USER`/`UP_PASS`, rejects every CONNECT, yet
`systemctl is-active` still says `active`.

### The client must actually USE the proxy — verify, never assume

Setting `SHOPEE_MITM` in the shell and seeing requests succeed proves nothing: if
`Api.__init__` never assigns `self.s.proxies`, every request leaves from the VPS
IP and the result you measured came from the datacenter IP. Corollary rule for any
HTTP client here: read the proxy from env **in the constructor** and fall back to
the working endpoint, never to `None`:

```python
PROXY_CHAIN = ("SHOPEE_MITM", "SHOPEE_PROXY", "HTTPS_PROXY", "https_proxy")
PROXY_DEFAULT = "http://IP:PORT"   # SOCKS relay — NOT the mitmproxy port

def proxy_url():
    for k in PROXY_CHAIN:
        if v := (os.environ.get(k) or "").strip():
            return v
    return PROXY_DEFAULT

class Api:
    def __init__(self, cookie, timeout=25, proxy=None):
        self.s = requests.Session()
        self.s.proxies = ({"http": proxy, "https": proxy} if proxy
                          else proxies_dict())
```

Hard-won specifics:

- **Point at the SOCKS relay port, not the mitmproxy port.** mitmproxy terminates
  TLS with its own CA; `requests` answers
  `SSL: CERTIFICATE_VERIFY_FAILED ... unable to get local issuer certificate`,
  the call raises, and a careless client silently falls back to DIRECT — the exact
  path that burns accounts. The relay port forwards the tunnel untouched.
- **Distinguish proxy failure from network failure** in the return value
  (`error: -997` for proxy, `-999` for network) and surface it. A generic
  `network: ...` hides a dead relay behind a plausible-looking error.
- **Verify end-to-end from the service's own environment**, not from an interactive
  shell: `systemctl show <unit> -p MainPID` → read `/proc/<pid>/environ` → build
  `Api` and print `proxy_info()["ip"]`. Only that proves production egress.
- `systemctl is-active` and a listening port prove nothing about auth or TLS; only
  an actual egress-IP check does.

## Presenting it in a Telegram bot

- After the cookie arrives, send a **new** message with username + old phone, then
  ask for the new number; every later status transition edits that same message.
  Delete-and-send makes the buttons vanish and throws the user down the chat.
- Always surface the raw code + `error_msg` + a hint. "Blocked" without the code
  sends the operator hunting the wrong layer.
- Route the flow's text handler **before** any generic phone-number capturer: an
  `auto_detect_phone` handler registered earlier swallows the cookie paste and the
  bot looks mute with no log lines.
- A burnt account is indistinguishable from a code bug in the UI. Keep the triage
  probe reachable so "account or code?" is answered in one call.
- Health states need distinct UI branches, not one shared warning: `ok` → proceed
  with `🟢 siap ganti nomor`, `ivs` → stop and tell the operator to finish IVS in
  the app, `limited` → stop and say wait / use another account, `dead` → new
  cookie. A single "flagged" branch fires on healthy accounts and destroys trust in
  every subsequent report.
- A handler test that imports the bot module fresh does NOT share the running
  process's in-memory state dict — use it to check registration order and syntax,
  never to assert live state.

## Telegram bot delivery layer (applies to any cookie-driven feature here)

`409 Conflict: terminated by other getUpdates request` is never a code bug — two
processes hold the same bot token and Telegram allows one long-poll. Hunt them
across every host that ever ran the project, not just the current VPS:

```
ps aux | grep -F shopee_bot                 # stray manual runs survive `systemctl stop`
for p in $(pgrep -f shopee_bot); do
  tr '\0' '\n' < /proc/$p/environ | grep -F 'BOT_TOKEN' | cut -c1-24
done
systemctl list-units --all | grep -iE 'shopee|webhook'   # Restart=always respawns
```

`kill -9` alone is not enough when the unit has `Restart=always`; also
`stop` + `disable` + `mask` every unit on the old host — a second service name
(e.g. a `*-webhook.service`) frequently carries the same token from an earlier
webhook experiment. Cheap proof of a clean window — poll `getUpdates` in a loop and
count: all `ok`, zero `conflict` for 60 s, then restart the bot.

## Dead inline buttons — audit before claiming done

A button that renders but does nothing is a **handler that exists without a branch
for that action**, not a missing handler. Adding `InlineKeyboardButton(cb="adm_cred")`
while `on_admin` only branches on `home/status/restart/net/pool/set/gpm/back`
leaves `act == "cred"` unmatched: the callback fires, the function returns having
done nothing, the UI looks broken with no error anywhere.

Three gates, cheapest first — run all before telling the user it works:

1. **Registration** — every `callback_data` literal in the source is matched by a
   `startswith`/`==` handler predicate. Catches typos and forgotten decorators.
2. **Branch coverage** — every callback reaching a dispatcher has a matching
   `if act == ...` inside it. Parsers must understand each routing style in the
   file, or they lie: literal `if act == "x"`, `d.startswith("x")`,
   `chg_cb(c, uid, d)` delegation (the branches live in the callee),
   `val = c.data[7:]` slicing, and `int(c.data.split("_")[1])` numeric lookup
   against a package/pricing dict. Static audit scripts that only match
   `if act ==` report healthy handlers as dead — verify every reported dead button
   by reading its handler before "fixing" it.
3. **Live invocation** — call the handler with a stub CallbackQuery and a stubbed
   bot object, then assert the call list is non-empty:

```python
class BotStub:
    def __init__(self): self.calls = []
    def answer_callback_query(self, *a, **k): self.calls.append("answer")
    def edit_message_text(self, *a, **k): self.calls.append("edit")
    def send_message(self, *a, **k): self.calls.append("send")

bot = BotStub()
handler(CallbackQuery(data="adm_cred", from_user=User(id=ADMIN), message=Msg()))
assert {"edit", "send"} & set(bot.calls), "handler produced no UI change"
```

Static analysis proves a string is reachable; only invocation proves the branch
executes. Both, every time. Copy-ready scripts for all three gates:
`references/telegram-inline-audit.md`.

## IVS branch inside the change-phone bot

`init_v2` answering `ivs_required: true` is a **branch, not a dead end**. Fetch the
method list and render it — do not tell the user to "finish IVS in the app" before
showing what the account actually offers:

```
POST /api/v4/anti_fraud/ivs/methods {event: 2, u_token: <ivs_utoken>}
  -> [{"type": 8, "v_token": "..."}]        e.g. EMAIL_LINK only
```

One inline button per returned entry, `callback_data="ivsm:<type>"`, `v_token` kept
in per-user state. `type 2` → ask password, `3`/`10` → ask PIN, anything else →
`method/select` then ask for the emailed code. Delete the message containing the
password/PIN right after reading it.

The user supplying a password is **not** evidence the account has one. Most
OTP-login accounts never set a Shopee password, so `ivs/methods` returns
`EMAIL_LINK` alone and every password attempt answers `10003`/`10002`. Check the
method list first; if `type:2` is absent, say so plainly and name the fix (set a
Shopee password in the app) instead of running attempts. Full IVS chain, signature
harvest and `211` semantics: `shopee-ivs-flow`.

## Admin credit panel (multi-user cookie bots)

When the bot charges per action and an admin must top users up: keep admin on the
same `saldo` field and the same charge path — do not special-case admins as free.
Adding balance is `db["users"][uid]["saldo"] += n` under the existing DB lock, plus
one append into a capped `credit_log` (`uid, by, delta, before, after, ts`) so
misclicks are auditable. Clamp at 0 rather than allowing negative balance. Custom
amount input arrives as plain text — route its `step` through the same pre-generic
text handler the change-number flow uses, otherwise the generic number capturer
eats it.
