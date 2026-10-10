"""Verifica se a versão visual do ATRIA chegou à hospedagem, sem login.

Saída:
  PUBLICADO — a moldura, o login proporcional e a preparação do favicon estão na produção.
  DESATUALIZADO — a versão ativa não contém os arquivos novos.
  INACESSÍVEL — a hospedagem não respondeu; não comprova versão.
"""
from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import os
import sys

BASE = os.getenv("ATRIA_PUBLIC_URL", "https://atria.nexonlabs.com.br").rstrip("/")
FILES = {
    "/static/atria-axora-exterior.css?v=axora-frame-uniform-r2":
        "contorno contínuo, referência visual AXORA".encode("utf-8"),
    "/static/nexon-app-atmosphere.svg":
        b"Atmosfera de conex",
    # A query string isolada não indica a versão: verificar a própria regra,
    # e a referência nova no HTML de login para detectar deploy incompleto.
    "/static/atria-login-axora-scale.css?v=login-scale-r3":
        b"height:min(510px,calc(100dvh - 20px))",
    "/":
        b"atria-login-axora-scale.css?v=login-scale-r3",
    "/static/app.js?v=compact-favicon-r3":
        b"let left=sample.width,top=sample.height,right=-1,bottom=-1;",
}
failures = []
for path, expected in FILES.items():
    url = BASE + path
    req = Request(url, headers={"User-Agent": "ATRIA-deployment-check/1.0", "Cache-Control":"no-cache"})
    try:
        with urlopen(req, timeout=15) as response:
            body = response.read(1_200_000)
            status = response.status
        if status == 200 and expected in body:
            print(f"PUBLICADO: {path} (HTTP {status}; {len(body)} bytes)")
        else:
            failures.append("DESATUALIZADO: " + path + f" (HTTP {status}; {len(body)} bytes)")
    except HTTPError as exc:
        failures.append(f"DESATUALIZADO: {path} (HTTP {exc.code})")
    except (URLError, TimeoutError, OSError) as exc:
        failures.append(f"INACESSÍVEL: {path} ({type(exc).__name__}: {exc})")

for msg in failures:
    print(msg, file=sys.stderr)
if failures:
    print("AÇÃO NECESSÁRIA: publicar/recriar o contêiner ATRIA na Hostinger.", file=sys.stderr)
    sys.exit(1)
print("ATRIA_PRODUCAO_VISUAL_E_FAVICON_CONFIRMADOS")
