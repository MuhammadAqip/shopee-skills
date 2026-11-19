"""Local reverse proxy: serves mirrored shopee static + proxies /api/* to shopee.co.id
through the authenticated upstream relay. Runs on <host>:<port>."""
import http.server, socketserver, urllib.request, urllib.error, os, sys

UPSTREAM_PROXY = "http://127.0.0.1:18080"   # our auth relay
SHOPEE = "https://shopee.co.id"
ROOT = "/root/.hermes/cache/scratch/se/serve"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# build opener that uses the upstream proxy
opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": UPSTREAM_PROXY, "https": UPSTREAM_PROXY}))

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**k): super().__init__(*a, directory=ROOT, **k)

    def log_message(self,*a): pass

    def _proxy(self, method):
        path = self.path
        url = SHOPEE + path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(url, data=body, method=method)
        for h in ("Content-Type","Accept","Accept-Language","X-Requested-With",
                  "Af-ac-enc-dat","Af-ac-enc-sz-token","X-Sap-Ri","X-Sap-Sec","X-Api-Source",
                  "X-Shopee-Language","X-Sz-Sdk-Version","X-Csrftoken","Cookie",
                  "Sec-Ch-Ua","Sec-Ch-Ua-Mobile","Sec-Ch-Ua-Platform"):
            v = self.headers.get(h)
            if v: req.add_header(h, v)
        req.add_header("User-Agent", UA)
        # CRITICAL: present as the real origin, never the local mirror
        req.add_header("Referer", "https://shopee.co.id/")
        req.add_header("Origin", "https://shopee.co.id")
        try:
            r = opener.open(req, timeout=40)
            data = r.read(); code = r.status; ctype = r.headers.get("Content-Type","application/json")
        except urllib.error.HTTPError as e:
            data = e.read(); code = e.code; ctype = e.headers.get("Content-Type","application/json")
        except Exception as e:
            data = ('{"error":-1,"error_msg":"proxy_fail"}').encode(); code = 502; ctype="application/json"
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try: self.wfile.write(data)
        except Exception: pass

    def do_GET(self):
        if self.path.startswith(("/api/", "/devapi/")): return self._proxy("GET")
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith(("/api/", "/devapi/")): return self._proxy("POST")
        self.send_error(405)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Headers","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
        self.end_headers()

class S(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv)>1 else 8124
    print(f"mirror+proxy on http://127.0.0.1:{port}", flush=True)
    S(("127.0.0.1", port), H).serve_forever()
