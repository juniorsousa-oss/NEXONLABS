"""Regressão da moldura ATRIA inspirada no AXORA (desktop + celular).
Valida a cascata, a arte, o drawer e o carregamento de CSS sem exigir login.
"""
from pathlib import Path
import re
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/"static/index.html").read_text(encoding="utf-8")
login=(ROOT/"static/login.html").read_text(encoding="utf-8")
css=(ROOT/"static/atria-axora-exterior.css").read_text(encoding="utf-8")
premium=(ROOT/"static/atria-premium.css").read_text(encoding="utf-8")
js=(ROOT/"static/app.js").read_text(encoding="utf-8")
asset=ROOT/"static/nexon-app-atmosphere.svg"

def test_external_atmosphere_comes_from_axora_reference():
    assert asset.exists()
    root=ET.parse(asset).getroot()
    assert root.tag.endswith("svg")
    assert root.attrib["viewBox"]=="0 0 1672 941"
    graphic=asset.read_text(encoding="utf-8")
    assert 'id="base"' in graphic
    assert "Fundo abstrato AXORA" not in graphic
    assert "nexon-app-atmosphere.svg" in css

def test_approved_app_css_is_final_and_login_is_not_affected():
    stylesheet='/static/atria-axora-exterior.css?v=axora-frame-uniform-r2'
    assert stylesheet in html
    assert html.index(stylesheet)>html.index('/static/nexon-signature.css')
    assert stylesheet not in login
    assert css.count("{")==css.count("}")
    assert "body:not(.login-page)" in css
    assert ".shell>.workspace" in css
    assert ".shell>.sidebar" in css
    assert "background-image:var(--atria-shell-background)" in css
    assert "background-image:none!important" in css
    assert "background:var(--atria-inner-surface)" in css
    assert "background-attachment:fixed" in css
    assert "background-attachment:scroll" in css
    assert 'zoom:.9' not in css and 'transform:scale(.9)' not in css

def test_mobile_same_wallpaper_and_drawer_above_overlay():
    media=css.split("@media (max-width:850px)",1)[1]
    assert "background-attachment:scroll!important" in media
    assert "background-size:cover" in media
    assert "body:not(.login-page) .shell>.sidebar.open" in media
    assert "z-index:71" in media
    assert "z-index:70" in media
    assert "left:-265px" in media
    assert "left:0" in media
    assert "width:265px" in media
    assert "overflow-y:auto" in media
    assert "pointer-events:auto" in media
    assert "border-radius:0 24px 24px 0" in media
    assert 'id="mobile-overlay" hidden' in html
    assert "function setMobileMenuState" in js
    assert "mobileSidebar.classList.toggle('open',expanded)" in js
    assert "mobileOverlay.hidden=!expanded" in js
    assert "mobileSidebar.inert=" in js
    assert "ATRIA mobile drawer touch fix v3" in premium

def test_sidebar_and_card_language_remains_atria_brand():
    assert ".nav-link.active" in css
    assert "background:linear-gradient(100deg" in css
    assert "nav-section" in css
    assert 'id="organization-brand-image"' in html
    assert 'id="default-brand-lockup"' in html
    assert "body:not(.login-page) .shell .main" in css
    assert "rgba(255,255,255,.97)" in css
    assert re.search(r"@media\s*\(min-width:851px\)",css)
    assert "@media(max-width:520px)" in css
    assert "@media(max-width:370px)" in css

def test_desktop_must_not_scroll_the_entire_frame():
    assert "height:calc(100dvh - 2 * var(--atria-shell-gutter))!important" in css
    assert "body:not(.login-page):has(.shell)" in css
    assert "overflow:hidden!important" in css
    assert "overflow-y:auto!important" in css
    assert "flex-direction:column!important" in css
    assert "height:0!important" in css
    assert "max-height:100dvh!important" in css

def test_menu_has_one_homogeneous_background():
    assert "background:#0B2D4A!important" in css
    assert "background-image:none!important" in css
    assert "background-size:cover,auto 100%" not in css
    assert ".shell>.sidebar" in css
