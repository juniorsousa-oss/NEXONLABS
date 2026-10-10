"""Verifica se a versão visual do ATRIA chegou à hospedagem, sem login.

Saída:
  PUBLICADO — os arquivos da moldura AXORA estão acessíveis na produção.
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
    "/static/atria-axora-exterior.css?v=axora-network-desktop-mobile-r1":
        b"ATRIA | Moldura externa inspirada no AXORA",
    "/static/nexon-app-atmosphere.svg":
        b"Atmosfera de conex",
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
print("ATRIA_PRODUCAO_ARTE_EXTERNA_CONFIRMADA")
