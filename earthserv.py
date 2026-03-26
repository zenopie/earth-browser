#!/usr/bin/env python3
"""earthserv — Reticulum HTTP Server

A minimal HTTP server that runs as a Reticulum destination.
Serves static files over Reticulum links using HTTP/1.1 semantics.
"""

import os
import sys
import time
import argparse
import threading
import RNS

APP_NAME = "earthserv"
ASPECTS = ["http"]

class EarthServ:
    def __init__(self, document_root, identity_path=None, config_path=None):
        self.document_root = os.path.abspath(document_root)
        if not os.path.isdir(self.document_root):
            raise FileNotFoundError(f"Document root not found: {self.document_root}")

        # Initialize Reticulum
        self.reticulum = RNS.Reticulum(configdir=config_path)

        # Load or create identity
        if identity_path and os.path.exists(identity_path):
            self.identity = RNS.Identity.from_file(identity_path)
            RNS.log(f"Loaded identity from {identity_path}")
        else:
            self.identity = RNS.Identity()
            if identity_path:
                identity_dir = os.path.dirname(identity_path)
                if identity_dir:
                    os.makedirs(identity_dir, exist_ok=True)
                self.identity.to_file(identity_path)
                RNS.log(f"Created new identity, saved to {identity_path}")

        # Create destination
        self.destination = RNS.Destination(
            self.identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            APP_NAME,
            *ASPECTS
        )

        # Register HTTP request handler
        self.destination.register_request_handler(
            "/http",
            self.handle_request,
            allow=RNS.Destination.ALLOW_ALL
        )

        # Set link established callback for logging
        self.destination.set_link_established_callback(self.on_link_established)

        # Announce on the network
        self.destination.announce()

        RNS.log(f"earthserv running")
        RNS.log(f"Destination hash: {self.destination.hexhash}")
        RNS.log(f"Full address:     {self.destination.hexhash}.ret")
        RNS.log(f"Document root:    {self.document_root}")

    def on_link_established(self, link):
        RNS.log(f"Link established from {link}")

    def handle_request(self, path, data, request_id, link_id, remote_identity, requested_at):
        """Handle an incoming HTTP request. Returns raw HTTP response bytes."""
        try:
            request_text = data.decode("utf-8", errors="replace")
            lines = request_text.split("\r\n")
            if not lines:
                return self.error_response(400, "Bad Request")

            # Parse request line: METHOD /path HTTP/1.x
            parts = lines[0].split(" ", 2)
            if len(parts) < 2:
                return self.error_response(400, "Bad Request")

            method = parts[0]
            req_path = parts[1]

            RNS.log(f"[{method}] {req_path}")

            if method not in ("GET", "HEAD", "POST"):
                return self.error_response(405, "Method Not Allowed")

            # Parse headers and body
            header_section = request_text.split("\r\n\r\n", 1)[0]
            body = request_text.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in request_text else ""
            headers = {}
            for line in header_section.split("\r\n")[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            # Parse query string
            query_string = ""
            if "?" in req_path:
                req_path, query_string = req_path.split("?", 1)

            # Handle POST to CGI scripts
            if method == "POST":
                return self.handle_post(req_path, headers, body, query_string)

            # Default to index.html
            if req_path == "/" or req_path == "":
                req_path = "/index.html"

            # Resolve file path
            file_path = os.path.join(self.document_root, req_path.lstrip("/"))
            file_path = os.path.realpath(file_path)

            # Path traversal protection
            if not file_path.startswith(self.document_root):
                return self.error_response(403, "Forbidden")

            # Serve directory index
            if os.path.isdir(file_path):
                file_path = os.path.join(file_path, "index.html")

            if not os.path.isfile(file_path):
                return self.error_response(404, "Not Found")

            # Read and serve file
            with open(file_path, "rb") as f:
                body = f.read()

            content_type = self.guess_content_type(file_path)

            if method == "HEAD":
                return self.build_response(200, "OK", b"", content_type,
                                           extra_headers={"Content-Length": str(len(body))})
            else:
                return self.build_response(200, "OK", body, content_type)

        except Exception as e:
            RNS.log(f"Error handling request: {e}", RNS.LOG_ERROR)
            return self.error_response(500, "Internal Server Error")

    def handle_post(self, req_path, headers, body, query_string):
        """Handle POST requests — route to CGI scripts or return form echo."""
        if req_path == "/" or req_path == "":
            req_path = "/index.html"

        # Check for CGI script
        cgi_path = os.path.join(self.document_root, req_path.lstrip("/"))
        cgi_path = os.path.realpath(cgi_path)

        if not cgi_path.startswith(self.document_root):
            return self.error_response(403, "Forbidden")

        # If it's a .py file in cgi-bin, execute it
        if cgi_path.endswith(".py") and os.path.isfile(cgi_path) and os.access(cgi_path, os.X_OK):
            return self.run_cgi(cgi_path, "POST", headers, body, query_string)

        # Parse form data for non-CGI POST
        from urllib.parse import parse_qs
        content_type = headers.get("content-type", "")
        form_data = {}
        if "application/x-www-form-urlencoded" in content_type:
            form_data = parse_qs(body)

        # Default: echo the form data back as HTML
        rows = ""
        for k, vals in form_data.items():
            for v in vals:
                rows += f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>"

        html = (
            f"<html><head><title>Form Received</title>"
            f'<link rel="stylesheet" href="/style.css"></head>'
            f'<body><div class="container">'
            f"<h1>Form Data Received</h1>"
            f'<div class="info"><table>{rows}</table></div>'
            f'<p><a href="/">Back to home</a></p>'
            f"</div></body></html>"
        ).encode("utf-8")
        return self.build_response(200, "OK", html)

    def run_cgi(self, script_path, method, headers, body, query_string):
        """Execute a CGI script and return its output as an HTTP response."""
        import subprocess
        env = os.environ.copy()
        env["REQUEST_METHOD"] = method
        env["QUERY_STRING"] = query_string
        env["CONTENT_TYPE"] = headers.get("content-type", "")
        env["CONTENT_LENGTH"] = str(len(body))
        env["DOCUMENT_ROOT"] = self.document_root

        try:
            result = subprocess.run(
                ["python3", script_path],
                input=body.encode("utf-8") if isinstance(body, str) else body,
                capture_output=True,
                timeout=30,
                env=env,
            )
            output = result.stdout.decode("utf-8", errors="replace")

            # CGI output: headers\n\nbody
            if "\n\n" in output:
                cgi_headers, cgi_body = output.split("\n\n", 1)
            elif "\r\n\r\n" in output:
                cgi_headers, cgi_body = output.split("\r\n\r\n", 1)
            else:
                cgi_body = output
                cgi_headers = "Content-Type: text/html"

            response_headers = "HTTP/1.1 200 OK\r\n"
            for line in cgi_headers.strip().split("\n"):
                response_headers += line.strip() + "\r\n"
            body_bytes = cgi_body.encode("utf-8")
            response_headers += f"Content-Length: {len(body_bytes)}\r\n"
            response_headers += "Connection: close\r\n\r\n"
            return response_headers.encode("utf-8") + body_bytes
        except Exception as e:
            RNS.log(f"CGI error: {e}", RNS.LOG_ERROR)
            return self.error_response(500, "CGI Error")

    def build_response(self, status_code, status_text, body, content_type="text/html",
                       extra_headers=None):
        """Build a raw HTTP/1.1 response."""
        headers = f"HTTP/1.1 {status_code} {status_text}\r\n"
        headers += f"Content-Type: {content_type}\r\n"
        headers += f"Content-Length: {len(body)}\r\n"
        headers += "Connection: close\r\n"
        if extra_headers:
            for k, v in extra_headers.items():
                headers += f"{k}: {v}\r\n"
        headers += "\r\n"
        return headers.encode("utf-8") + body

    def error_response(self, code, message):
        body = (
            f"<html><head><title>{code} {message}</title></head>"
            f"<body><h1>{code} {message}</h1></body></html>"
        ).encode("utf-8")
        return self.build_response(code, message, body)

    def guess_content_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css":  "text/css; charset=utf-8",
            ".js":   "application/javascript",
            ".json": "application/json",
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif":  "image/gif",
            ".svg":  "image/svg+xml",
            ".ico":  "image/x-icon",
            ".txt":  "text/plain; charset=utf-8",
            ".xml":  "application/xml",
            ".pdf":  "application/pdf",
            ".woff": "font/woff",
            ".woff2":"font/woff2",
        }
        return content_types.get(ext, "application/octet-stream")


def main():
    parser = argparse.ArgumentParser(
        description="earthserv — Reticulum HTTP Server"
    )
    parser.add_argument(
        "document_root",
        help="Path to the document root directory"
    )
    parser.add_argument(
        "-i", "--identity",
        help="Path to identity file (creates persistent address)",
        default=None
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to Reticulum config directory",
        default=None
    )
    args = parser.parse_args()

    server = EarthServ(args.document_root, args.identity, args.config)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nearthserv shutting down")
        sys.exit(0)


if __name__ == "__main__":
    main()
