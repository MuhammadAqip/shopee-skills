# Shopee Anti-Crawler — Full Reverse Map (2026-11-13)

Reverse dari `pcmall-anticrawler.30b0dea29eac8eb432e5.js` (41,561 bytes, modern build).
Source: `USER_STATIC_TOGGLE` di `window.__ASSETS__` → `pcmall-anticrawler` asset JSON.

## Toggle aktif (live, ID locale)

```json
"af_sap_sdk": true,
"af_sap_legacy": false,
"use_anti_crawler_api_protection_sdk": true,
"standalone_security_sdk": true,
"standalone_fetch_utils": true,
"fetch_account_v4": true
```

Artinya: signer aktif = **`af_sap_sdk`** (bukan legacy). Anti-crawler gate aktif.

## Endpoint verifikasi (SATU-SATUNYA)

```
POST /api/v4/anti_fraud/anti_crawler/verify_signature
body: {
  app_key:            string,   // dari ?app_key= atau storage
  captcha_signature:  string,   // hasil solve captcha
  mfr_captcha_token:  string,   // token dari mfr decode
  scene:              string | number,
  tracking_id:        string    // ?anti_bot_tracking_id=
}
resp: { error, error_msg, x, o }
```

`x` / `o` = hasil callback `s(g)` dan `i(v)` — dipakai untuk lanjut redirect.

## Storage keys (sessionStorage)

```
@shopee-ac/app_key
@shopee-ac/scene
@shopee-ac/client_id
@shopee-ac/should_replace_history
@shopee-ac/redirect_url
@shopee-ac/redirect_type
@shopee-ac/tracking_id
```

## mfr token decoder — `z(e)`

Format: `mfr<base64url(JSON)><suffix>`  
Suffix: `.PC` | `.RW` | `.APP`

```js
function z(e){
  if (e.startsWith("mfr")) {
    const suf = (e.match(/\.PC$|\.RW$|\.APP$/) || [""])[0];
    const b64 = e.replace(suf,"").slice(3).replace(/-/g,"+").replace(/_/g,"/");
    const json = JSON.parse(atob(b64));
    return { appKey: json.business + suf, mfr: json.mfr, mfrCaptcha: json.mfr_captcha };
  }
  return { appKey: e };
}
```

**Ini yang bisa lo replikasi tanpa signer.** `business`, `mfr`, `mfr_captcha` semuanya plaintext di dalam base64 — cuma dibungkus, bukan dienkripsi.

## Config flow

```js
const {appKey, scene, trackingId} = {
  appKey:     sessionStorage.getItem("@shopee-ac/app_key"),
  scene:      sessionStorage.getItem("@shopee-ac/scene"),
  trackingId: sessionStorage.getItem("@shopee-ac/tracking_id"),
};
// fallback: parse dari location.search
//   ?app_key= → z(app_key) → appKey (+ mfr decode)
//   ?scene=
//   ?anti_bot_tracking_id=  → trackingId
```

## Whitelist domain (bypass zone)

Anti-crawler **tidak jalan** di:
```
localhost, *.localhost, 0.0.0.0, 127.0.0.1
```
Regex: `/^(localhost|.*\.localhost|0\.0\.0\.0|127\.0\.0\.1)$/`

→ **Ini jalur bypass paling murah**: serve/mirror halaman di localhost, gate-nya skip.

Domain yang di-cover (harus gate): `shopee.co.id|th`, `shopee.com.{my,br,mx,co,ar,mm,la}`, `shopee.{sg,vn,tw,ph,cl,pl,es}`, `shopeekh.com`.

## Response codes

```
SERVER_ERROR   = 10005
REQUEST_TIMEOUT = -99
apiProgress: INIT(0) → REQ(1) → OK(2) / ERR(3)
```

Non-2xx → `{error:10005}`, 408 → `{error:-99}`.

## Implikasi untuk RE

1. `USER_STATIC_TOGGLE` di HTML **bocorin konfigurasi anti-bot server** tanpa auth. Ambil dari `home.html` → `window.__ASSETS__.USER_STATIC_TOGGLE`.
2. Asset manifest tiap micro-app dapat di-fetch dari `deo.shopeemobile.com/shopee/stm-sg-live/<id>/asset-ID-live.<hash>.json` — **nggak kena gate**.
3. `mfr` token = base64 JSON, bukan kripto. Decode langsung.
4. Verifikasi butuh `captcha_signature` — di sinilah SadCaptcha dipakai (solve puzzle → signature).
5. `tracking_id` di URL `/verify/captcha?anti_bot_tracking_id=<gqRjZGVr...>` = protobuf-ish base64 — di-generate server per-sesi.

## Modul anti-fraud lain (manifest)

```
pcmall-anticrawler      stm-sg-live/50819
pcmall-antifraudivs     stm-sg-live/55230
pcmall-antifrauderror   stm-sg-live/47170
pcmall-antifraudsetupsecurityemail  78718
pcmall-antifraudverifyemaillink     55084
pcmall-antifraudverifyemaillinkreceiver 56011
pcmall-antifraudverifylink          54844
pcmall-antifraudverifylinkreceiver  55429
pcmall-antifraudverifyqr            54899
pcmall-antifraudverifyquestion      77556
```
