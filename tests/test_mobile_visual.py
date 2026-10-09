"""Verificações estáticas do acabamento responsivo ATRIA / Nexon Labs.

Os testes não exigem banco de dados ou credenciais e garantem que
as correções de moldura permaneçam confinadas à versão mobile.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "atria-premium.css").read_text(encoding="utf-8")
APP_HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
LOGIN_HTML = (ROOT / "static" / "login.html").read_text(encoding="utf-8")


def test_mobile_frame_matches_premium_rounded_shell():
    assert "ATRIA — Mobile premium frame v2" in CSS
    mobile_css = CSS.split("ATRIA — Mobile premium frame v2", 1)[1]
    assert "@media (max-width:850px)" in mobile_css
    assert "body:not(.login-page) .shell" in mobile_css
    assert "width:calc(100% - 20px)" in mobile_css
    assert "border-radius:24px" in mobile_css
    assert "box-shadow:0 18px 47px" in mobile_css
    assert "body:not(.login-page) .shell .topbar" in mobile_css
    assert "body:not(.login-page) .shell>.sidebar" in mobile_css
    assert "position:fixed" in mobile_css


def test_mobile_cards_get_soft_rounded_finish_without_losing_existing_modules():
    mobile_css = CSS.split("ATRIA — Mobile premium frame v2", 1)[1]
    assert "body:not(.login-page) .home-metrics .metric" in mobile_css
    assert "body:not(.login-page) .panel" in mobile_css
    assert "body:not(.login-page) .home-project-card" in mobile_css
    assert "body:not(.login-page) .hero .slogan-card" in mobile_css
    assert "body:not(.login-page) .home-metrics .metric::after" in mobile_css
    assert "atria-login-network.svg" in mobile_css


def test_login_network_repeats_on_mobile_and_login_behavior_is_intact():
    mobile_css = CSS.split("ATRIA Login — conexão Nexon", 1)[1]
    assert "@media (max-width:760px)" in mobile_css
    assert "background-repeat:repeat" in mobile_css
    assert "background-size:620px auto" in mobile_css
    assert "background-size:565px auto" in mobile_css
    assert 'id="login-form"' in LOGIN_HTML
    assert 'id="password" type="password"' in LOGIN_HTML
    assert "fetch('/api/login'" in LOGIN_HTML
    assert "fetch('/api/state'" in LOGIN_HTML


def test_versioned_stylesheets_and_balanced_css():
    assert "atria-premium.css?v=mobile-drawer-v3" in APP_HTML
    assert "atria-premium.css?v=mobile-frame-v2" in LOGIN_HTML
    assert CSS.count("{") == CSS.count("}")


def test_sidebar_drawer_backdrop_layering_and_accessibility():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="mobile-overlay" hidden' in APP_HTML
    assert 'aria-controls="sidebar"' in APP_HTML
    assert 'aria-expanded="false"' in APP_HTML
    assert "app.js?v=mobile-drawer-v3" in APP_HTML

    assert "ATRIA mobile drawer touch fix v3" in CSS
    drawer = CSS.split("ATRIA mobile drawer touch fix v3", 1)[1]
    assert "body:not(.login-page) .shell>.mobile-overlay" in drawer
    assert "z-index:70" in drawer
    assert "body:not(.login-page) .shell>.sidebar" in drawer
    assert "z-index:71" in drawer
    assert "pointer-events:auto" in drawer
    assert "overscroll-behavior-y:contain" in drawer

    assert "function setMobileMenuState" in js
    assert "function closeMobileMenu" in js
    assert "mobileSidebar.inert=" in js
    assert "mobileOverlay.hidden=!expanded" in js
    assert "mobileSidebar.classList.toggle('open',expanded)" in js
    assert "mobileMenuButton.setAttribute('aria-expanded'" in js
    assert "mobileOverlay?.addEventListener('click'" in js
    assert "closeMobileMenu(true);closeModal()" in js
    assert "document.body.append(overlay)" not in js
