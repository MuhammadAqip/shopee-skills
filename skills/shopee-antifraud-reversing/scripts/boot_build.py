"""Module-federation remotes must load in STRICT dependency order:
react -> react-dom -> everything else. Bundles that consume them last."""
import re, pathlib, os

src = pathlib.Path("home.html").read_text(errors="replace")

shell = re.sub(r'<script[^>]*\bsrc="[^"]*"[^>]*>\s*</script>', '', src)
inline = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', src, re.S)
shell = re.sub(r'<script(?![^>]*\bsrc=)[^>]*>.*?</script>', '', shell, flags=re.S)

def mfp(name):
    p = "bundles/mf/" + name
    return p if os.path.exists(p) else None

def asset(name):
    p = "bundles/" + name
    return p if os.path.exists(p) else None

# strict order
order = []
for n in ["webpack-runtime.583dce620212857d.2023.js",
          "entry-modules.02ca39241aac2cf3.2023.js"]:
    if asset(n): order.append(asset(n))

# federation core FIRST
for n in ["react-19.2.1.js", "react-dom-19.2.1.js"]:
    if mfp(n): order.append(mfp(n))

# then remaining remotes
for f in sorted(os.listdir("bundles/mf")):
    p = "bundles/mf/" + f
    if p not in order and f not in ("react-19.2.1.js","react-dom-19.2.1.js"):
        order.append(p)

# then app bundles (js in /assets/)
for f in sorted(os.listdir("bundles")):
    if f.endswith(".js") and os.path.isfile("bundles/" + f):
        p = "bundles/" + f
        if p not in order and not any(x.endswith(f) for x in order):
            order.append(p)

fixed = []
for b in inline:
    t = b.strip()
    if t.startswith("{") and t.endswith("}"):
        fixed.append(f'<script type="application/json">{b}</script>')
    else:
        fixed.append(f"<script>{b}</script>")

tags = "\n".join(f'<script src="/{p}"></script>' for p in order)
shell = shell.replace("</head>", "\n".join(fixed) + "\n</head>", 1)
shell = shell.replace("</body>", tags + "\n</body>", 1)
shell = shell.replace('<script nomodule>location.replace("/unsupported.html")</script>', '')
shell = shell.replace('<script>location.replace("/unsupported.html")</script>', '')

pathlib.Path("serve/boot.html").write_text(shell)
print(f"boot.html {len(shell)}B | {len(order)} scripts")
for i,p in enumerate(order[:10]): print(f"  {i}: {p.split('/')[-1]}")
