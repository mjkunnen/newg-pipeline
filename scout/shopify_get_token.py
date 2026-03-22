"""Quick OAuth flow to get a Shopify Admin API access token."""
import http.server
import urllib.parse
import urllib.request
import json
import webbrowser
import ssl

SHOP = "2fgppd-7k.myshopify.com"
CLIENT_ID = "04e5c3005fb72b8e8c8c2b643e8f4439"
CLIENT_SECRET = "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"
REDIRECT_URI = "http://localhost:9999/callback"
SCOPES = "read_products,write_products,read_orders,write_orders,read_inventory,write_inventory,read_themes,write_themes,read_content,write_content,read_files,write_files,read_customers,write_customers,read_fulfillments,write_fulfillments,read_locations,read_discounts,write_discounts"

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            code = params["code"][0]
            print(f"\nGot authorization code: {code}")

            # Exchange code for permanent access token
            token_url = f"https://{SHOP}/admin/oauth/access_token"
            data = json.dumps({
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
            }).encode()

            req = urllib.request.Request(
                token_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            ctx = ssl.create_default_context()

            try:
                resp = urllib.request.urlopen(req, context=ctx)
                result = json.loads(resp.read())
                access_token = result.get("access_token", "")
                print(f"\n{'='*50}")
                print(f"ACCESS TOKEN: {access_token}")
                print(f"{'='*50}")
                print(f"\nSave this token! It won't be shown again.")

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Success!</h1><p>Token: {access_token}</p>".encode())
            except urllib.error.HTTPError as e:
                error_body = e.read().decode()
                print(f"\nERROR {e.code}: {error_body}")

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Error {e.code}</h1><pre>{error_body}</pre>".encode())

            # Stop server
            import threading
            threading.Thread(target=self.server.shutdown).start()
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No code received")

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = http.server.HTTPServer(("localhost", 9999), CallbackHandler)

    auth_url = (
        f"https://{SHOP}/admin/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        f"&scope={SCOPES}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    )

    print("Opening browser for Shopify authorization...")
    print(f"If browser doesn't open, go to:\n{auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for callback...")
    server.serve_forever()
