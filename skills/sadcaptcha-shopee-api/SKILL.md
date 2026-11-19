---
name: sadcaptcha-shopee-api
description: "Use for SadCaptcha Shopee captcha solver API calls."
version: 1.0.0
---

# SadCaptcha Shopee Captcha Solver — API Reference

Base URL: `https://www.sadcaptcha.com/api/v1`

**Auth:** `licenseKey` is a **QUERY PARAMETER** on every endpoint (not a header).
Example: `https://www.sadcaptcha.com/api/v1/shopee-image-crawl?licenseKey=YOUR_KEY`

**Headers:** `Content-Type: application/json`

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/license/credits` | Check credits: `{"credits": N}` |
| POST | `/shopee-image-crawl-pre-analyze` | Analyze puzzle image BEFORE solving |
| POST | `/shopee-image-crawl` | Solve arced-slide challenge (needs trajectory) |
| POST | `/puzzle` | Simple slide-puzzle (2-image) |
| POST | `/shopee-image-drag` | Drag missing piece then click Verify |
| POST | `/semantic-shapes` | Text-challenge shapes |

## ✅ /puzzle + SLIDER HANDLE — captcha Desktop login CLEARED (verified live 2026-11-13)

`/shopee-image-drag` and `/shopee-image-crawl` never produced a pass. This does:

1. **`POST /puzzle`** with `{puzzleImageB64, pieceImageB64}` (camelCase, NO trajectory)
   → `{"slideXProportion": float}`.
2. **Drag the SLIDER HANDLE — not the piece canvas.** Dragging the piece canvas is a
   dead end on shopee.co.id: it is hit-testable (`pointer-events:auto`) but the widget
   ignores drags on it. Every wrapper ancestor ignores it too (tested canvas + 3 wrappers,
   all `delta=0`).
3. **Verify is auto-fired on drop.** `found verify=False` is correct, not a failure.

### Handle selector (class hashes rotate per build)

```js
// puzzle = canvas[draggable=false] && width > 200        (280x150)
// piece  = smallest other canvas, 20 < w < puzzle.w
// handle = 40x40 div, has child <svg>, NO child <canvas>,
//          top between puzzleBottom-40 and puzzleBottom+160
// SORT BY DEPTH DESC (outermost first), then left asc
```

Sorting by `left` first grabs a 12 px-inset decoration div (x=586) instead of the real
handle (x=594) → drag silently does nothing. `(594,419)` = rest position @ 1420×900.

### Grip→piece gain ≈2.2x, non-linear — use a closed loop

Measured: handle +97 px ⇒ piece propX 0.780 (target 0.346). Handle +62 px ⇒ piece 0.112
(target 0.118). Never use a fixed conversion:

```python
cur, moved = pc_propX, 0.0
while moved < pz_w * 0.92:
    if abs(target - cur) < 0.010: break
    moved += 2.0
    page.mouse.move(gx + moved + jitter, gy - 6*min(1, moved/(pz_w*0.9)) + jitter)
    sleep(randint(9,20)/1000)
    cur = (await probe())['piece']['propX']
page.mouse.up()
```

Verified landing error 0.002–0.006. Saturates near propX 0.83 (rail ≈168–170 px).

### Readiness gate — 5 silent failures came from skipping it

`canvas` exists but paints blank for 8–100 s. Require ALL:

```python
len(pz_b64) > 20000 and len(piece_b64) > 900
and 20 < piece.w < pz.w - 5          # a 300x150 "piece" is the puzzle canvas
and (piece.x != pz.x or piece.y != pz.y)   # blank piece sits at puzzle origin
```

`toDataURL()` before paint returns a **1,458-byte black PNG** → API 400. Paint gate is
the fix, not a retry.

### Canvas scope is `document`, NOT `#NEW_CAPTCHA`

On the desktop login captcha the canvases are not inside `#NEW_CAPTCHA` /
`aside[aria-modal=true]`. Scoped queries return `{"canvases": []}` and stall forever.

### Proof of pass

```
ready 14s | pz 280x150 | piece 72 propX=0.000 | grip (594,419)
api: 200 {"slideXProportion":0.11785714}
handle released at +62px, piece propX=0.112 (target 0.118)
url: https://shopee.co.id/      <-- was /verify/captcha
```

Working script: `/root/.hermes/cache/scratch/se/solve_slider.py`.

---

## /shopee-image-crawl — THE RULE THAT FIXES 400

`400 Bad Request` = body incomplete. You MUST send `slide_piece_trajectory`.

Request body (`ImageCrawlCaptchaRequest`):
```json
{
  "puzzle_image_b64": "<base64 PNG>",
  "piece_image_b64": "<base64>",
  "slide_piece_trajectory": [
    {
      "pixels_from_slider_origin": 0,
      "piece_rotation_angle": 0.0,
      "piece_center": {"proportionX": 0.1234, "proportionY": 0.5}
    }
  ]
}
```
- `pixels_from_slider_origin` (int): slider-button distance dragged from origin, per sample.
- `piece_rotation_angle` (float): piece CSS rotate() angle in degrees.
- `piece_center` (proportional point): piece center x/y divided by puzzle container width/height (0..1).
- MIN 12 rows (`MIN_TRAJECTORY_ROWS`).

Response:
```json
{"pixelsFromSliderOrigin": 137}
```

Status codes: `400` = bad request / no answer found - `401` = bad key or out of credits.

## /shopee-image-crawl-pre-analyze — ALWAYS CALL FIRST

Request: `{"image_b64": "<puzzle image b64>"}`
Response:
```json
{"version": "v1", "slideXProportion": 0.4714, "skipRecommended": false}
```
- `skipRecommended: true` -> abandon & refresh this captcha (retry up to 3).
- `slideXProportion >= 0.99` -> captcha malformed, refresh (retry up to 3).
- `slideXProportion` = piece-center-X proportion where motion should STOP during recording.

## DOM SELECTORS (Shopee)

```
PUZZLE_IMAGE: "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false], div:not(#puzzleContainer) > img"
PIECE_IMAGE:  "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true], #puzzleContainer > #puzzleImgComponent"
SLIDER_BTN:   "div:has(> svg + svg)"
RESET_BTN:    "#NEW_CAPTCHA svg[viewBox='0 0 16 16'], aside svg[viewBox='0 0 16 16']"
```

## TRAJECTORY RECORDING ALGORITHM

The piece moves on an ARC, not linear. To record:
1. `mouseDown` on slider button center.
2. Sweep x from 0 -> `0.85 * puzzleWidth`, step 3px.
3. SCATTER each 30px block: shuffled pixel order (Fisher-Yates) - random order defeats bot detection; do NOT sweep monotonically.
4. After each move sample: `pixels_from_slider_origin` (button x - origin), `piece_rotation_angle` (parse `rotate(Xdeg)` from piece inline style), `piece_center` (piece rect center as proportion of puzzle box).
5. STOP when `piece_center.proportionX >= slideXProportion` AND overshoot >= 15px; OR piece not moved for 10 samples.
6. Sort by `pixels_from_slider_origin` before sending.

## HUMAN-LIKE RELEASE (post-solution)

```
maxPx = puzzleWidth * 0.85
toU(px) = px/maxPx*4 - 2
toPx(u) = (u+2)/4*maxPx
aimU = toU(solution)
# 4 oscillation passes (decreasing amplitude 1.5), step 13px; final leg step 15px to solution
# pause random 900-2100ms before nudge, 750-1450ms before release
```
Gesture constants: `GESTURE_AMP_U=1.5`, `GESTURE_PASSES=4`, `GESTURE_PACE_MS=2`,
`PAUSE_BEFORE_NUDGE_MS=[900,2100]`, `PAUSE_BEFORE_RELEASE_MS=[750,1450]`,
`OVERSHOOT_PX=15`, `SWING_SAFE_PX=12`, `SCATTER_BLOCK_PX=30`, `SKIP_CAP=3`.

## SIMPLE PYTHON CLIENT

```python
import requests
BASE = "https://www.sadcaptcha.com/api/v1"

def credits(key):
    return requests.get(f"{BASE}/license/credits", params={"licenseKey": key}).json()["credits"]

def pre_analyze(key, image_b64):
    r = requests.post(f"{BASE}/shopee-image-crawl-pre-analyze",
                      params={"licenseKey": key}, json={"image_b64": image_b64})
    return r.json()   # {version, slideXProportion, skipRecommended}

def solve_image_crawl(key, puzzle_b64, piece_b64, trajectory):
    r = requests.post(f"{BASE}/shopee-image-crawl", params={"licenseKey": key}, json={
        "puzzle_image_b64": puzzle_b64,
        "piece_image_b64": piece_b64,
        "slide_piece_trajectory": trajectory,
    })
    if r.status_code == 400: raise RuntimeError("bad request / no answer")
    if r.status_code == 401: raise RuntimeError("bad key or out of credits")
    return r.json()["pixelsFromSliderOrigin"]

def solve_puzzle(key, puzzle_b64, piece_b64):
    r = requests.post(f"{BASE}/puzzle", params={"licenseKey": key},
                      json={"puzzleImageB64": puzzle_b64, "pieceImageB64": piece_b64})
    return r.json()["slideXProportion"]   # camelCase here
```

Field-name gotcha: camelCase everywhere else (`puzzleImageB64`, `pixelsFromSliderOrigin`, `slideXProportion`, `proportionX`) EXCEPT the image-crawl request body which uses snake_case.

## REPOS
- `github.com/gbiz123/shopee-captcha-solver` (PyPI `shopee-captcha-solver`) - Selenium/Playwright/Nodriver clients
- `github.com/gbiz123/shopee-captcha-solver-chrome-extension` - MV3 extension, `script.ts` = reference solver
- `github.com/gbiz123/sadcaptcha-code-examples` - puzzle/rotate/shapes examples
- Swagger: https://www.sadcaptcha.com/api/v1/swagger-ui/index.html - OpenAPI JSON: https://www.sadcaptcha.com/api/v1/v3/api-docs

## PATTERN: CACHE-FIRST + API FALLBACK

Resolve captcha cache-first (match exact puzzle bytes in local SQLite; store solved `pixelsFromSliderOrigin`/proportion). Call the API only on MISS. Prewarm when credits available; serve from cache in production to save credits.
- Cache lookup MUST use content match (b64 bytes), not a stored hash.
- Use SQLite WAL mode to avoid 'database is locked' with a concurrent prewarm writer.

## PITFALLS
- **`data:` prefix kills the request.** `canvas.toDataURL()` returns `data:image/png;base64,AAAA…`.
  Sending that string verbatim gives `400 Bad Request` with no detail. Strip everything up to the
  first comma. This applies to `image_b64` AND `puzzle_image_b64`.
- **The b64 must be the right canvas.** A 300×150 canvas that is not the puzzle and not the piece
  produces `400` on `/shopee-image-crawl` — the error looks identical to a bad trajectory, so check
  which node you serialized before blaming the trajectory.
- `400` almost always = missing/too-short `slide_piece_trajectory` (>=12 rows) OR wrong field casing.
- `401` = bad key OR out of credits - check `/license/credits` first.
- The Shopee arced-slide has TWO plausible landing spots; the API disambiguates using the trajectory - do NOT solve with a single gap-detection/OpenCV template match; accuracy is low.
- `slideXProportion` is a PROPORTION (0..1) of container width, not pixels.
- Record the trajectory from a **diagonal** sweep (grip rises as it slides). A horizontal sweep
  returns `pixelsFromSliderOrigin: 0`. Full working recipe: `references/login-captcha-pipeline.md`.
- `pixelsFromSliderOrigin` is applied 1:1 as grip travel on shopee.co.id login (measured
  0.00355 propX/px ≈ 1/280). Do not rescale by puzzle width.
