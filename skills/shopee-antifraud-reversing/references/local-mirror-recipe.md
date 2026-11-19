# Local SPA Mirror — Full Build Recipe

Local mirror of shopee.co.id that boots the real React SPA and signs live API calls.
Useful for static analysis, DOM inspection, and cheap-endpoint harvesting. **Does not defeat
`90309999`** — see the root-cause section in SKILL.md.

## Four bugs that eat hours

1. **Basename collisions.** `modules-federation/live/0/react/19.2.1.js` and
   `.../react-dom/19.2.1.js` both save as `19.2.1.js` with a naive `url.split('/')[-1]`
   downloader. React silently overwrites ReactDOM -> `Cannot read properties of null
   (reading 'useMemo')`. Save as `mf/react-19.2.1.js` / `mf/react-dom-19.2.1.js`.
2. **Script order.** The webpack runtime reads `window.__ASSETS__.SAP` at module-load time.
   If any bundle runs before the inline config block, every bundle dies with
   `Cannot read properties of undefined (reading 'SAP')`. Inline the `<script data-webfe="config">`
   block first, then `webpack-runtime` -> `entry-modules` -> `react` -> `react-dom` ->
   other remotes -> app bundles.
3. **Bare-JSON `<script>` block.** Homepage ships a 125 KB manifest as `{"pcmall-...":"https://..."}`
   inside a *plain* `<script>` tag. That is a SyntaxError and it kills every script after it.
   Re-emit it as `<script type="application/json">`.
4. **Patchright blocks inline scripts.** Verified with a 3-line HTML probe:
   `patchright -> window.MARK_A === undefined`, `plain playwright -> "number"`.
   **Always use plain `playwright` for mirror work.**

## Trapdoors in the HTML

- `<script nomodule>location.replace("/unsupported.html")</script>` — modern Chromium still
  executes the fallback on our setup, so the page navigates away before anything renders.
  Strip it.
- `df.infra.test.shopee.sg` (shpsec beacon) is NXDOMAIN. The live host is
  `df.infra.shopee.sg` (HTTP 200, valid cert). Rewrite at the network layer.

## Proxy must spoof origin

A mirror that forwards `Referer: http://<upstream-host>:<port>/` gets the 157 KB SPA shell back for
**every** `/devapi` and `/api` call. Force `Referer: https://shopee.co.id/` and
`Origin: https://shopee.co.id`, pass through `af-ac-enc-dat`, `af-ac-enc-sz-token`,
`x-sap-ri`, `x-sap-sec`, `x-sz-sdk-version`, `x-csrftoken`, `Cookie`.

## Scripts

- `scripts/boot_build.py` — regenerate `serve/boot.html` with correct ordering + JSON block fix
- `scripts/mirror_proxy.py` — HTTP mirror with `/api` + `/devapi` passthrough and origin spoof
- `scripts/https_mirror.py` — same on HTTPS :443 for hostname-identical testing

## Verified outcome

Renders the Shopee language modal, forms 17 real cookies (`SPC_F`, `SPC_T_ID/IV`,
`SPC_SEC_SI`, `_sapid`, `shopee_webUnique_ccd`), signs every call with a fresh 2,412-char
`x-sap-sec`, and gets **200 on 9 cheap endpoints** including
`pages/get_category_tree` (26 top-level / 388 total categories).
`search_items`, `pdp/get_pc`, `get_ratings`, `get_shop_info`, `recommend/*` stay at 90309999.
