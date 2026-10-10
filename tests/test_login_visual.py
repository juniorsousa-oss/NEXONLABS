"""Regressão visual do login ATRIA: identidade Nexon Labs, sem mexer na autenticação."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGIN = ROOT / "static" / "login.html"
STYLES = ROOT / "static" / "atria-premium.css"
NETWORK = ROOT / "static" / "atria-login-network.svg"


def test_login_approved_identity_uses_dynamic_official_logo():
    html = LOGIN.read_text(encoding="utf-8")
    assert "atria-premium.css?v=mobile-frame-v2" in html
    assert 'id="login-product-logo"' in html
    assert "fetch('/api/product-brand'" in html
    assert "login-brand-accent" in html
    assert "transformar planos" in html
    assert 'class="login-lock-icon"' in html
    assert 'class="login-button-arrow"' in html


def test_login_keeps_password_and_session_security_flow():
    html = LOGIN.read_text(encoding="utf-8")
    assert 'id="login-form"' in html
    assert 'id="password" type="password"' in html
    assert 'id="reveal-password"' in html
    assert "fetch('/api/login'" in html
    assert "fetch('/api/state'" in html
    assert "credentials:'same-origin'" in html
    assert "passwordInput.type=e.target.checked?'text':'password'" in html


def test_network_motif_and_mobile_styles_are_scoped_to_login():
    css = STYLES.read_text(encoding="utf-8")
    assert "ATRIA Login — Nexon connected identity v1" in css
    assert "body.login-page::before" in css
    assert "/static/atria-login-network.svg" in css
    assert ".login-page .login-brand-copy .login-brand-accent" in css
    assert ".login-page .login-input-wrap" in css
    assert "font-size:16px" in css
    assert "@media(max-width:760px)" in css
    assert "@media(max-width:520px)" in css
    assert "@media(max-width:360px)" in css
    assert css.count("{") == css.count("}")


def test_network_asset_is_valid_embedded_reference():
    import xml.etree.ElementTree as ET
    graphic = ET.parse(NETWORK).getroot()
    assert graphic.tag.endswith("svg")
    assert graphic.attrib["viewBox"] == "0 0 1400 900"


def test_login_uses_axora_reference_size_without_touching_authentication():
    css=(ROOT/'static/atria-login-axora-scale.css').read_text(encoding='utf-8')
    html=LOGIN.read_text(encoding='utf-8')
    assert 'atria-login-axora-scale.css?v=login-scale-r1' in html
    assert '@media (min-width:901px)' in css
    assert 'width:min(960px,calc(100vw - 56px))' in css
    assert 'height:min(550px,calc(100dvh - 64px))' in css
    assert 'grid-template-columns:minmax(0,1fr) minmax(0,1fr)' in css
    assert 'margin-top:clamp(51px,7vh,72px)' in css
    assert 'body.login-page .login-card' in css
    assert 'body.login-page .login-note.atria-nexon-note' in css
    assert '@media (min-width:761px) and (max-width:900px)' in css
    assert '@media (max-width:760px)' in css
    assert '@media (max-width:520px)' in css
    assert css.count('{')==css.count('}')
    assert 'fetch(\'/api/login\'' in html
