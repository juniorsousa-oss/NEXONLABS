"""Assinatura institucional presente no acesso e inicio sem afetar o login."""
from pathlib import Path
from fastapi.testclient import TestClient
from app import app

ROOT=Path(__file__).resolve().parents[1]/"static"


def test_login_has_accessible_monochrome_brand_signature():
    with TestClient(app) as client:
        response=client.get("/")
        assert response.status_code==200
        assert "nexon-monochrome-dark.svg" in response.text
        assert "login-form" in response.text
        assert "nexon-signature.css" in response.text


def test_home_footer_uses_brand_and_preserves_client_structure():
    html=(ROOT/"index.html").read_text(encoding="utf-8")
    js=(ROOT/"app.js").read_text(encoding="utf-8")
    assert "nexon-signature.css" in html
    assert "nexon-monochrome-dark.svg" in js
    assert "route==='inicio'" in js
    assert "aria-label=\"Desenvolvido pela Nexon Labs\"" in js
    assert (ROOT/"nexon-monochrome-light.svg").exists()
    assert (ROOT/"nexon-monochrome-dark.svg").exists()
