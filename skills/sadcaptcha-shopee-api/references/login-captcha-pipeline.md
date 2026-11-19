# Shopee Web Login Captcha — Proven Pipeline

End-to-end notes for clearing `https://shopee.co.id/verify/captcha` on the **web login
flow** (not signup — signup uses different selectors, see `/root/shopee-farm/solve_crawl.py`).

## The stack that works

| Layer | What | Why |
|---|---|---|
| IP | Indonesian residential proxy (Telkom/Indosat, AS7713 etc.) | datacenter IPs never render the puzzle at all |
| Browser | **headful** Chromium on Xvfb, `patchright` | headless gives `navigator.webdriver=true`, 0 plugins, no `window.chrome` → Shopee refuses to ship the puzzle |
| Proxy auth | Playwright `proxy={server,username,password}` | passing `Proxy-Authorization` as an HTTP header raises `ERR_INVALID_ARGUMENT` |
| Solver | SadCaptcha `/shopee-image-crawl` | needs the trajectory, not just the two images |

Headful alone flipped the page from `#NEW_CAPTCHA innerHTML = 0` / "Verifikasi gagal" to
`innerHTML = 8276` / "Seret potongan yang hilang untuk melengkapi". That single change is the
difference between a dead end and a solvable captcha.

## Fingerprint proof (headless vs headful)

```
headless: webdriver=true   plugins=0  window.chrome=undefined  #NEW_CAPTCHA=0 bytes
headful : webdriver=false  plugins=5  window.chrome=object     #NEW_CAPTCHA=8276 bytes
```

## DOM — canvases live OUTSIDE `#NEW_CAPTCHA`

On the login/verify captcha the two canvases are **direct children of `document`**, not of
`#NEW_CAPTCHA`. Scoping any query to the captcha root returns nothing and the whole solver
silently stalls. Always query `document.querySelectorAll('canvas')` and then classify:

```js
const all = [...document.querySelectorAll('canvas')];
const pz = all.find(c => c.getAttribute('draggable') === 'false' && c.width > 200);
const pc = all.filter(c => c !== pz)
              .filter(c => (c.getAttribute('draggable')||'true') === 'true')
              .filter(c => c.width > 20 && c.width < pz.width)
              .sort((a,b) => Math.abs(a.width-44) - Math.abs(b.width-44))[0];
```

Piece size **varies** (44, 57, 65, 69, 74, 95 px all observed). Never filter on a fixed size —
sort by closeness to 44 and take the first, and require `width < puzzle.width` so the 300×150
render canvas is never mistaken for the piece.

## The grip

It is a ~40×40 `div` sitting just below the puzzle image, anchored at the **left edge of the
track**. Verified by drag test: gripping at (594,419) moved `propX` from 0.096 to 0.939.

```js
for (const e of document.querySelectorAll('div')) {
  const r = e.getBoundingClientRect();
  if (r.width < 30 || r.width > 50 || r.height < 30 || r.height > 50) continue;
  if (r.top < puzzleRect.bottom - 10 || r.top > puzzleRect.bottom + 110) continue;
  if (e.querySelector('canvas')) continue;      // skip the piece wrapper
  cands.push({x:r.x+r.width/2, y:r.y+r.height/2, left:r.left});
}
cands.sort((a,b) => a.left - b.left);   // leftmost = start position
```

A wider 30–50 window (not exactly 40) is required because the handle's measured box varies
between sessions after CSS scaling.

## Trajectory — diagonal sweep

```python
for px in range(0, int(puzzle_w * 0.85), 3):
    await mouse.move(gx + px, gy - px)   # rises as it slides: the arc Shopee tracks
    await asyncio.sleep(0.012)
    s = await page.evaluate(INFO)
    traj.append({"pixels_from_slider_origin": px,
                 "piece_rotation_angle": 0.0,
                 "piece_center": {"proportionX": round(s["pc"]["propX"], 4),
                                  "proportionY": round(s["pc"]["propY"], 4)}})
```

A straight horizontal sweep is rejected — SadCaptcha answers `pixelsFromSliderOrigin: 0`
because the recorded proportions no longer line up with the arc.

## Scale calibration

Measured on this build: **1 px of grip travel = 1 px of piece travel** (237 px of drag moved
`propX` 0.079 → 0.921; `0.842 / 237 = 0.00355` per px, and 1/280 = 0.00357 — identical).
So SadCaptcha's `pixelsFromSliderOrigin` is applied **directly** as grip travel. There is no
scaling factor to apply. Do not multiply by puzzle width.

## SadCaptcha quirks that cost hours

- **`data:image/png;base64,` prefix must be stripped.** Sending the raw `canvas.toDataURL()`
  returns `400 Bad Request` with no explanation. `{'image_b64': <with prefix>}` → 400;
  without prefix → 200. Split on the first comma and keep the tail.
- `pre-analyze` and `image-crawl` both use `image_b64` / `puzzle_image_b64` — snake_case.
  Only `/puzzle` uses camelCase.
- `image-crawl` needs ≥12 trajectory rows.
- A `400` on `image-crawl` almost always means one of the two b64 images is the wrong canvas
  (e.g. the 300×150 render canvas sent as the piece), not a bad trajectory.

## Language gate — must be clicked by JS, not by mouse

The button is `BUTTON.shopee-button-outline` at `y > 300` (the one at `y ≈ 2` is the navbar
language link and does nothing). A synthesized mouse click frequently fails to fire React's
handler; `element.click()` from `page.evaluate` transitions reliably to `/verify/captcha`:

```js
const btns = [...document.querySelectorAll('button')].filter(e => {
  const r = e.getBoundingClientRect();
  return /Bahasa Indonesia/i.test(e.textContent||'') && r.y > 300 && r.width > 100;
});
if (btns.length) btns[0].click();
```

After the click the captcha appears in ~2 s ("Memuat.." first, then canvases).

## Rate limiting

Repeated failed attempts put the exit IP on a lock: `/verify/captcha` renders the
"Silakan Coba Lagi Nanti / Verifikasi gagal" card with **zero canvases**, and clicking
"Coba Lagi" just reloads the same error. The proxy rotates eventually — verify with
`ipinfo.io` and wait for a new exit IP rather than retrying on the same one. Budget roughly
one solve attempt per fresh IP.

## Files

- `scripts/shopee_login_captcha.py` — the full driver (headful patchright + ID proxy + SadCaptcha)
- `/root/shopee-farm/solve_crawl.py` — signup variant, proven end-to-end (captcha → OTP)
- `/root/shopee-farm/sadcaptcha_client.py` — clean API client with the prefix-stripping helper
