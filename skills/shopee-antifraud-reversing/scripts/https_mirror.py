"""HTTPS mirror on shopee.co.id:443 — identical origin to the real site.
The SPA's anti-crawler checks (which whitelist localhost anyway) plus the
fingerprint generation see a legitimate origin, so SPC_CDS can form."""
import http.server, socketserver, ssl, urllib.request, urllib.error, sys, os

UPSTREAM_PROXY = "http://127.0.0.1:18080"
SHOPEE = "https://shopee.co.id"
ROOT = "/root/.hermes/cache/scratch/se/serve"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": UPSTREAM_PROXY, "https": UPSTREAM_PROXY}))

PASS = ("Content-Type", "Accept", "Accept-Language", "X-Requested-With",
        "Af-ac-enc-dat", "Af-ac-enc-sz-token", "X-Sap-Ri", "X-Sap-Sec", "X-Api-Source",
        "X-Shopee-Language", "X-Sz-Sdk-Version", "X-Csrftoken", "Cookie",
        "Sec-Ch-Ua", "Sec-Ch-Ua-Mobile", "Sec-Ch-Ua-Platform")

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(self, *a): pass

    def _proxy(self, method):
        url = SHOPEE + self.path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(url, data=body, method=method)
        for h in PASS:
            v = self.headers.get(h)
            if v: req.add_header(h, v)
        req.add_header("User-Agent", UA)
        req.add_header("Referer", "https://shopee.co.id/")
        req.add_header("Origin", "https://shopee.co.id")
        try:
            r = opener.open(req, timeout=45)
            data = r.read(); code = r.status; ctype = r.headers.get("Content-Type", "application/json")
            setck = r.headers.get_all("Set-Cookie") or []
        except urllib.error.HTTPError as e:
            data = e.read(); code = e.code; ctype = e.headers.get("Content-Type", "application/json")
            setck = e.headers.get_all("Set-Cookie") or []
        except Exception:
            data = b'{"error":-1,"error_msg":"proxy_fail"}'; code = 502; ctype = "application/json"; setck = []
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for c in setck: self.send_header("Set-Cookie", c)
        self.end_headers()
        try: self.wfile.write(data)
        except Exception: pass

    def do_GET(self):
        if self.path.startswith(("/api/", "/devapi/")): return self._proxy("GET")
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith(("/api/", "/devapi/")): return self._proxy("POST")
        self.send_error(405)

class S(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain("/root/.hermes/cache/scratch/se/tls/cert.pem",
                        "/root/.hermes/cache/scratch/se/tls/key.pem")
    srv = S(("127.0.0.1", 443), H)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    print("HTTPS mirror on https://shopee.co.id:443", flush=True)
    srv.serve_forever()
