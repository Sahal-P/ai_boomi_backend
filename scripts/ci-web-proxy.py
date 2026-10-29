"""Start a loopback-only CI nginx with production-equivalent API routing."""

import os
import subprocess
import tempfile
from pathlib import Path

folder = Path(tempfile.mkdtemp(prefix="finboy-ci-nginx-"))
snippet = (Path(__file__).resolve().parents[1] / "deploy/finboy-proxy.conf").read_text()
snippet = snippet.replace("127.0.0.1:8020", "127.0.0.1:8031")
config = f"""
pid {folder}/nginx.pid;
error_log /dev/null crit;
events {{ worker_connections 256; }}
http {{
  access_log off;
  client_body_temp_path {folder}/body;
  proxy_temp_path {folder}/proxy;
  limit_req_zone $binary_remote_addr zone=finboy_login:1m rate=10r/m;
  server {{
    listen 127.0.0.1:3031;
    client_max_body_size 103m;
    location = /api/v1/auth/login {{
      limit_req zone=finboy_login burst=5 nodelay;
      limit_req_status 429;
      client_max_body_size 4k;
      add_header Cache-Control no-store always;
      {snippet}
    }}
    location /api/v1/ {{ add_header Cache-Control no-store always; {snippet} }}
    location / {{
      proxy_pass http://127.0.0.1:3032;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_set_header X-Forwarded-For $remote_addr;
      proxy_buffering off;
    }}
  }}
}}
"""
(folder / "nginx.conf").write_text(config)
binary = "/usr/sbin/nginx" if Path("/usr/sbin/nginx").exists() else "nginx"
subprocess.run([binary, "-t", "-p", str(folder), "-c", str(folder / "nginx.conf")], check=True)
os.execv(binary, [binary, "-p", str(folder), "-c", str(folder / "nginx.conf"), "-g", "daemon off;"])
