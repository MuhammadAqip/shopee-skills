"""v5 — exact port of the proven /root/shopee-farm pipeline onto this captcha.

Differences from my earlier attempts, all taken from code that actually cleared
Shopee's captcha (BREAKTHROUGH_RESULTS.md):

  * piece = canvas[draggable=true], puzzle = canvas[draggable=false]  (attribute,
    not size — the piece is often 95px and my >100 filter mis-split them)
  * grip = div:has(> svg + svg)  with a geometric fallback
  * sweep is HORIZONTAL x then VERTICAL y shaped by mouse.move(sx+px, sy-px)
    but the RECORDED proportion comes from the piece element itself each step
  * after solving: mouse.move back to origin, then drag forward to target
"""
import asyncio
import json
import os
import base64
import random
import re
import requests
from playwright.async_api import async_playwright

EXE = "/root/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
PROXY = {"server": "http://aliyun.dennak.com:443", "username": "res-id",
         "password": "pgw-97015dada5d05d9da5ed4f54a1bab9376736a25f2c0b0c52"}
KEY = "6ac9ab5de2edf8436e2870ec381ed9ac"
BASE = "https://www.sadcaptcha.com/api/v1"
OUT = os.path.dirname(os.path.abspath(__file__))

SEL = {
    "pz": "#NEW_CAPTCHA canvas[draggable=false], aside canvas[draggable=false]",
    "pc": "#NEW_CAPTCHA canvas[draggable=true], aside canvas[draggable=true]",
}

FIND_GRIP = """() => {
  const all = [...document.querySelectorAll('canvas')];
  const pz = all.find(c => c.getAttribute('draggable') === 'false' && c.width > 200);
  if (!pz) return null;
  const pr = pz.getBoundingClientRect();
  const cands = [];
  for (const e of document.querySelectorAll('div')) {
    const r = e.getBoundingClientRect();
    if (r.width < 30 || r.width > 50 || r.height < 30 || r.height > 50) continue;
    if (r.top < pr.bottom - 10 || r.top > pr.bottom + 110) continue;
    if (e.querySelector('canvas')) continue;
    cands.push({x:r.x+r.width/2, y:r.y+r.height/2, w:r.width, left:r.left});
  }
  if (!cands.length) return null;
  cands.sort((a,b) => a.left - b.left);
  const g = cands[0];
  return {x:g.x, y:g.y, src:'left-edge-of-track'};
}"""

INFO = """() => {
  const all = [...document.querySelectorAll('canvas')];
  const pz = all.find(c => c.getAttribute('draggable') === 'false' && c.width > 200);
  // piece: draggable, smaller than the puzzle, and NOT the same node
  const pc = all.filter(c => c !== pz)
                .filter(c => (c.getAttribute('draggable')||'true') === 'true')
                .filter(c => c.width > 20 && c.width < (pz ? pz.width : 1000))
                .sort((a,b) => Math.abs(a.width-44) - Math.abs(b.width-44))[0];
  if (!pz || !pc) return null;
  const pr = pz.getBoundingClientRect();
  const ir = pc.getBoundingClientRect();
  return {
    pz: {x:pr.x, y:pr.y, w:pr.width, h:pr.height, nw:pz.width, nh:pz.height},
    pc: {x:ir.x, y:ir.y, w:ir.width, h:ir.height, nw:pc.width, nh:pc.height,
         cx: ir.x + ir.width/2, cy: ir.y + ir.height/2,
         style: pc.getAttribute('style') || '',
         propX: (ir.x + ir.width/2 - pr.x) / pr.width,
         propY: (ir.y + ir.height/2 - pr.y) / pr.height},
    b64pz: pz.toDataURL('image/png'),
    b64pc: pc.toDataURL('image/png'),
    txt: (document.body.innerText||'').replace(/\\s+/g,' ').slice(0,120)
  };
}"""


def credits():
    return requests.get(f"{BASE}/license/credits", params={"licenseKey": KEY}, timeout=30).json()["credits"]


def api(path, body):
    r = requests.post(f"{BASE}/{path}", params={"licenseKey": KEY}, json=body, timeout=90)
    if r.status_code == 400:
        raise RuntimeError(f"400 {r.text[:130]}")
    if r.status_code == 401:
        raise RuntimeError("401")
    r.raise_for_status()
    return r.json()


async def main():
    print("credits:", credits())
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False, executable_path=EXE,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled", "--start-maximized"])
        ctx = await b.new_context(viewport={"width": 1420, "height": 900}, locale="id-ID",
            timezone_id="Asia/Jakarta", user_agent=UA, proxy=PROXY)
        await ctx.add_cookies([{"name": "shopee_webLanguage", "value": "id",
                                "domain": ".shopee.co.id", "path": "/"}])
        pg = await ctx.new_page()

        for a in range(3):
            try:
                await pg.goto("https://shopee.co.id/", wait_until="commit", timeout=90000)
                break
            except Exception:
                await pg.wait_for_timeout(3000)
        await pg.wait_for_timeout(9000)

        # language gate: the real button is BUTTON.shopee-button-outline, y > 400
        for _ in range(15):
            txt = await pg.evaluate("() => (document.body.innerText||'').slice(0,400)")
            if "Pilih bahasa Anda" not in txt:
                break
            btn = await pg.evaluate("""() => {
              let best = null;
              for (const e of document.querySelectorAll('button')) {
                const t = (e.textContent||'').trim();
                if (!/^Bahasa Indonesia$/i.test(t)) continue;
                const r = e.getBoundingClientRect();
                if (r.width < 100 || r.y < 300) continue;   // skip the navbar link
                best = {x:r.x+r.width/2, y:r.y+r.height/2, w:r.width, h:r.height};
              }
              return best;
            }""")
            if btn:
                await pg.evaluate("""() => {
                  const btns = [...document.querySelectorAll('button')].filter(e => {
                    const r = e.getBoundingClientRect();
                    return /Bahasa Indonesia/i.test(e.textContent||'') && r.y > 300 && r.width > 100;
                  });
                  if (btns.length) btns[0].click();
                }""")
                print("    lang clicked via JS")
            else:
                print("    no inline lang button")
            await pg.wait_for_timeout(2500)

        info = None
        for i in range(70):
            info = await pg.evaluate(INFO)
            g = await pg.evaluate(FIND_GRIP)
            body = await pg.evaluate("() => (document.body.innerText||'').replace(/\\s+/g,' ').slice(0,200)")
            if i % 4 == 0:
                print(f"      [{i}] info={bool(info)} grip={bool(g)} body={body[:60]}")
            if info and g and "Verifikasi untuk melanjutkan" in (info.get("txt") or ""):
                print(f"    captcha up after {i*1.2:.0f}s | grip={g}")
                break
            if "Verifikasi gagal" in body or "Coba Lagi" in body:
                print("    rate-limited page — clicking Coba Lagi")
                await pg.evaluate("""() => {
                  const b = [...document.querySelectorAll('button,div,a')]
                    .find(e => /Coba Lagi/i.test((e.textContent||'').trim()));
                  if (b) b.click();
                }""")
                await pg.wait_for_timeout(20000)
                continue
            if "Pilih bahasa Anda" in body:
                await pg.evaluate("""() => {
                  const btns = [...document.querySelectorAll('button')].filter(e => {
                    const r = e.getBoundingClientRect();
                    return /Bahasa Indonesia/i.test(e.textContent||'') && r.y > 300 && r.width > 100;
                  });
                  if (btns.length) btns[0].click();
                }""")
            await pg.wait_for_timeout(1200)

        if not info:
            print("[!] captcha not up")
            await pg.screenshot(path=os.path.join(OUT, "v5_no.png"))
            await b.close()
            return

        grip = await pg.evaluate(FIND_GRIP)
        print(f"[1] grip {grip} | pz {info['pz']['w']:.0f}x{info['pz']['h']:.0f} | "
              f"pc {info['pc']['w']:.0f}x{info['pc']['h']:.0f} | propX={info['pc']['propX']:.4f}")

        pz = info["b64pz"].split(",", 1)[-1]
        pc = info["b64pc"].split(",", 1)[-1]
        open(os.path.join(OUT, "v5_puzzle.png"), "wb").write(base64.b64decode(pz))
        open(os.path.join(OUT, "v5_piece.png"), "wb").write(base64.b64decode(pc))

        sx, sy = grip["x"], grip["y"]
        pz_rect = info["pz"]

        # ---------------- sweep ----------------
        print("[2] sweep diagonal")
        await pg.mouse.move(sx, sy)
        await pg.wait_for_timeout(100)
        await pg.mouse.down()
        await pg.wait_for_timeout(160)

        traj = []
        limit = int(pz_rect["w"] * 0.85)
        for px in range(0, limit, 3):
            await pg.mouse.move(sx + px, sy - px)
            await asyncio.sleep(0.015)
            cur = await pg.evaluate(INFO)
            if not cur:
                continue
            a = 0.0
            m = re.search(r"rotate\(([-0-9.]+)deg", cur["pc"]["style"] or "")
            if m:
                a = float(m.group(1))
            traj.append({
                "pixels_from_slider_origin": px,
                "piece_rotation_angle": a,
                "piece_center": {"proportionX": round(cur["pc"]["propX"], 4),
                                 "proportionY": round(cur["pc"]["propY"], 4)},
            })

        traj.sort(key=lambda r: r["pixels_from_slider_origin"])
        print(f"    traj={len(traj)} propX {traj[0]['piece_center']['proportionX']:.3f} -> "
              f"{traj[-1]['piece_center']['proportionX']:.3f}")

        # ---------------- solve ----------------
        try:
            sol = api("shopee-image-crawl", {"puzzle_image_b64": pz, "piece_image_b64": pc,
                                             "slide_piece_trajectory": traj})
            target = sol["pixelsFromSliderOrigin"]
            print("[3] answer:", sol)
        except Exception as e:
            print("[!]", str(e)[:140])
            await pg.mouse.up()
            await b.close()
            return

        # ---------------- rewind & drag ----------------
        print(f"[4] rewind to origin then drag {target}")
        await pg.mouse.move(sx, sy, steps=25)
        await asyncio.sleep(0.15)
        if target and target > 0:
            await pg.mouse.move(sx + 1, sy, steps=1)
            for i in range(0, int(target), 4):
                await pg.mouse.move(sx + i, sy)
                await asyncio.sleep(0.010)
            ov = random.choice([1, 2, 3])
            await pg.mouse.move(sx + target + ov, sy + ov, steps=10)
            await pg.mouse.move(sx + target, sy, steps=8)
        await asyncio.sleep(0.3)
        await pg.mouse.up()
        await pg.wait_for_timeout(5000)

        info2 = await pg.evaluate(INFO)
        print("[5] after:", (f"propX={info2['pc']['propX']:.4f} txt={info2['txt'][:70]}"
                             if info2 else "captcha gone"))
        await pg.screenshot(path=os.path.join(OUT, "v5_after.png"))

        await pg.wait_for_timeout(4000)
        print("[6] url:", pg.url[:100])
        await pg.screenshot(path=os.path.join(OUT, "v5_final.png"))

        out = await pg.evaluate("""async () => {
          const U = {tree:'/api/v4/pages/get_category_tree',
            flash:'/api/v4/flash_sale/flash_sale_get_items?limit=6&offset=0',
            search:'/api/v4/search/search_items?by=relevancy&keyword=sepatu&limit=10&newest=0&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2'};
          const o={};
          for (const k in U) {
            try { const r=await fetch(U[k],{credentials:'include',
                    headers:{'x-api-source':'pc','Accept':'application/json'}});
                  const j=await r.json(); let n=null;
                  if (j.items) n=j.items.length;
                  else if (j.data) for (const f of ['items','category_list'])
                    if (j.data[f]) { n=Array.isArray(j.data[f])?j.data[f].length:1; break; }
                  o[k]={s:r.status,err:j.error,n}; }
            catch(e){o[k]={e:String(e).slice(0,40)};}
          }
          return o;
        }""")
        print("APIs:", json.dumps(out, indent=1))
        print("credits:", credits())
        await b.close()

asyncio.run(main())
