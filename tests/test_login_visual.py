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
    assert 'atria-login-axora-scale.css?v=login-scale-r5-mobile-flex-center' in html
    assert '@media (min-width:901px)' in css
    assert 'width:min(960px,calc(100vw - 56px))' in css
    assert 'height:min(680px,calc(100dvh - 64px))' in css
    assert 'grid-template-columns:minmax(0,1fr) minmax(0,1fr)' in css
    assert 'margin:clamp(63px,8vh,84px) 0 0' in css
    assert 'body.login-page .login-card' in css
    assert 'body.login-page .login-note.atria-nexon-note' in css
    assert '@media (min-width:761px) and (max-width:900px)' in css
    assert '@media (max-width:760px)' in css
    assert '@media (max-width:520px)' in css
    assert css.count('{')==css.count('}')
    assert 'fetch(\'/api/login\'' in html

def test_login_axora_vertical_hierarchy_is_present():
    css=(ROOT/'static/atria-login-axora-scale.css').read_text(encoding='utf-8')
    html=LOGIN.read_text(encoding='utf-8')
    assert 'class="login-overline"' in html
    assert 'class="login-brand-foot"' in html
    assert 'Da informação à ação.' in html
    assert 'flex-direction:column' in css
    assert 'margin:auto 0 0' in css
    assert 'body.login-page .login-note.atria-nexon-note' in css
    assert 'align-items:center' in css
    assert '@media (min-width:901px) and (max-height:760px)' in css
    assert '@media (min-width:901px) and (max-height:630px)' in css
    assert 'height:min(510px,calc(100dvh - 20px))' in css
    assert '@media (min-width:901px) and (max-height:530px)' in css
    assert '@media(max-width:900px)' in css


def test_smartphone_login_centers_without_clipping_short_viewports():
    """Flex + margens automaticas: centro em telas altas, inicio + scroll nas baixas."""
    css=(ROOT/'static/atria-login-axora-scale.css').read_text(encoding='utf-8')
    html=LOGIN.read_text(encoding='utf-8')
    mobile=css.split('/* Smartphone:',1)[1].split('@media (max-width:520px)',1)[0]
    assert 'body.login-page{' in mobile
    assert 'display:flex' in mobile
    assert 'flex-direction:column' in mobile
    assert 'justify-content:flex-start' in mobile
    assert 'margin-block:auto' in mobile
    assert 'flex:0 0 auto' in mobile
    assert 'min-height:100svh' in mobile
    assert 'height:auto' in mobile
    assert 'login-scale-r5-mobile-flex-center' in html
    assert css.count('{') == css.count('}')
