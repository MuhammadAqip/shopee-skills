# SDK deobfuscation + captcha keys

Two things worth having before touching the SDK: how to get plaintext out of
`sfu-stable.<hash>.2023.js`, and the AES materials for `anti_fraud/captcha`.
Both were derived and verified live; neither requires the VM emulator.

## String-table deobfuscation (10 minutes, no emulator)

The SDK wraps every literal in a **custom-base64 alphabet**. The alphabet is
visible in the bootstrap as the only 65-char string near the top:

```
evdqphkgrfmiotbyjlxczanswuTMBGWXRCAEPIZNHFLUDSVKOQJY4912758063+/=
```

Translate that to standard base64, decode, and rewrite the file. Reproducible
in ~40 lines:

```python
ALPHA = "evdqphkgrfmiotbyjlxczanswuTMBGWXRCAEPIZNHFLUDSVKOQJY4912758063+/="
STD   = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
TBL   = str.maketrans(ALPHA, STD)
pat   = re.compile(r'"([A-Za-z0-9+/=]{16,})"')

def repl(m):
    body = m.group(1)
    txt  = base64.b64decode(body.translate(TBL) + "=" * (-len(body) % 4)).decode("utf-8")
    return '"' + txt.replace("\\", "\\\\").replace('"', '\\"') + '"'

open("sfu_deob.js", "w").write(pat.sub(repl, src))
```

Only accept the substitution when the decoded text is printable and ≥3 chars;
that filters the actual crypto blobs (2,400-char base64 payloads) that survive
the same regex. Yields ~370 strings from a 572 KB file.

**Watch for a second alphabet.** The same SDK family ships the tables
`ofksgblrxcamqiunzpthjwydevYDSVHBOZKWEGFXCMINTJARQLPU1357249806+/=` and
`evdqphkgrfmiotbyjlxczanswu…` in different bundles. If a table decoded with one
alphabet produces garbage, try the other before concluding the file is
VM-only.

After decoding, `grep` for the strings you actually need. In one pass this
surfaced `app_key`, `device_sz_fingerprint`, `af-ac-enc-dat`, and the whole
policy list — none of which are greppable in the source.

## What the deobfuscated file gives you

### Per-environment app keys

```js
test:    "90a081b48a9c87345189bda87a989d23"
uat:     "5a733eaa4e1df48aa36fd9316f093107"
staging: "d9dd212362d63e8ddb085bb5bce5259f"
stable:  "dc6fe70845cb784460ead6c7fd76bb91"
live:    "f9ffc83459897a13dd14c537e84b1753"
```

### `af-ac-enc-dat` is just a nonce

```js
function B(){
  var e, t = function(e){
    for (var t="", f=0; f<e.length; f++){
      var n = e[f].toString(16);
      t += n.padStart ? n.padStart(2,"0") : (1===n.length ? "0"+n : n);
    }
    return t;
  }(function(){ for (var e=new Uint8Array(8), t=0; t<8; t++) e[t]=Math.floor(256*Math.random()); return e; }());
  return (e={})["af-ac-enc-dat"] = t, e;
}
```

8 random bytes, hex-encoded. No device state, no signature. Anyone claiming
this header is the anti-bot key is wrong — it is a per-request nonce and can be
regenerated with `secrets.token_hex(8)`.

### The two fetch-option flags decide everything

```js
if (e.useSecurityAntibot) {          // x-sap-ri / x-sap-sec / sz-token
  await a({});                       // wait for SDK init
  e.headers = {...e.headers, ...i.u()};
  e.headers[D] = await F();          // af-ac-enc-sz-token
  e.headers[g] = o();                // x-sz-sdk-version
}
if (e.useSecurityDfp) {              // device fingerprint
  await a({});                       // MUST wait for DFP init
  const u = await i.R({});           // generate device_sz_fingerprint
  const p = e.useSecurityDfp.dataFormatter ? e.useSecurityDfp.dataFormatter(u[b]) : u;
  e.data = {...e.data, ...p};        // body, NOT header
}
```

Two consequences that cost hours if missed:

- `device_sz_fingerprint` goes into the **request body**, formatted as
  `{"security_device_fingerprint": "<base64>"}`, not into a header.
- The fingerprint only exists after `await a({})` resolves. Firing a
  `useSecurityDfp` request before SDK init completes sends an empty string and
  the server treats it as absent.

The fingerprint cannot be generated outside the page — it is built from live
browser surface. Do not try to forge it; drive the call from a page instead.

## `anti_fraud/captcha` — AES keys and wire format

Found in the captcha caller inside the IVS bundle:

```js
_ = function(e){
  return e ? "dRgUkXp2r5u8x/A?D(G+KbPeShVmYq3t"
           : "5v8y/B?E(H+MbPeShVmYq3t6w9z$C&F)";
}
```

32 bytes each, `isLiveEnv` selects. Format is
`CryptoJS.AES.encrypt(JSON.stringify(payload), key).toString()` — the OpenSSL
`Salted__` container, AES-256-CBC, key derived by **EVP_BytesToKey with MD5**.

Getting the KDF right is the whole trick. The naive one-shot derivation
(`md5(key+salt)` then `md5(d1+key+salt)`) yields a 32-byte digest that cannot
supply both a 32-byte key and a 16-byte IV, and `AES.new` raises
`Incorrect IV length`. The correct loop feeds the previous digest back in:

```python
def evp_encrypt(obj, key):
    pt   = json.dumps(obj, separators=(",", ":")).encode()
    salt = secrets.token_bytes(8)
    d, prev = b"", b""
    while len(d) < 48:
        prev = hashlib.md5(prev + key + salt).digest()
        d += prev
    ct = AES.new(d[:32], AES.MODE_CBC, d[32:48]).encrypt(pad(pt, 16))
    return base64.b64encode(b"Salted__" + salt + ct).decode()
```

Decrypt is the mirror. Proof the crypto is right: the server answers HTTP 200
with a well-formed `encrypted_data` that decrypts cleanly — a wrong key
produces unparseable bytes, not a JSON error.

Correct crypto is not sufficient, though. With valid ciphertext the generate
endpoint still answers `31500000` (`is_non_retryable`) for **every** scene and
`captcha_type` tested — `login`, `login_otp`, `login_pw`, `ivs`, `change_phone`,
`account`, `register` × types 0-3. The call needs a `captcha_id` /
`image_version` pair minted by a page that actually rendered a captcha. Do not
burn time permuting scenes; if there is no live captcha on screen there is
nothing to generate, and no scene string changes that.

## Capturing headers: what works

| Method | Result |
|---|---|
| Playwright `page.on("request")` + `req.all_headers()` | **works** — full `x-sap-sec` body, every request |
| CDP `Network.requestWillBeSent` | empty |
| JS `window.fetch` monkey-patch | empty — SDK installs above it |
| `XMLHttpRequest.setRequestHeader` patch | no `x-sap-*` seen |

The SDK layers its own fetch wrapper over the page's, so userland hooks miss it.
Playwright's network layer sits below the page entirely and sees everything.
