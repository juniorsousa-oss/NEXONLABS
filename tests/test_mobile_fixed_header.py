"""ATRIA mobile: cabeçalho visível, rolagem independente e drawer acessível."""

from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def test_mobile_scroll_keeps_topbar_outside_scroll_region():
    html = (BASE / "static/index.html").read_text(encoding="utf-8")
    css = (BASE / "static/mobile-fixed-header.css").read_text(encoding="utf-8")
    js = (BASE / "static/app.js").read_text(encoding="utf-8")
    assert html.index('class="topbar"') < html.index('class="main" id="main"')
    assert html.index("mobile-fixed-header.css") > html.index("atria-axora-exterior.css")
    assert "@media (max-width:850px)" in css
    assert "body:not(.login-page)" in css
    assert "height:100%!important" in css
    assert "flex-direction:column!important" in css
    assert "overflow:hidden!important" in css
    assert "body:not(.login-page) .shell .topbar" in css
    assert "body:not(.login-page) .shell .main" in css
    assert "overflow-y:auto!important" in css
    assert "overscroll-behavior-y:contain" in css
    assert "body:not(.login-page) .shell>.sidebar" in css
    assert "z-index:71!important" in css
    assert "body:not(.login-page) .shell>.mobile-overlay" in css
    assert "'#main').scrollTop=0" in js
    assert css.count("{") == css.count("}")


def test_mobile_header_does_not_modify_login_or_desktop():
    css = (BASE / "static/mobile-fixed-header.css").read_text(encoding="utf-8")
    assert "@media (min-width:851px)" not in css
    assert "body.login-page" not in css
    assert "fetch(" not in css
