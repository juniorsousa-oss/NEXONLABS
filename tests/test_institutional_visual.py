"""Verifica que a marca institucional global não modifica logos dos clientes.

Valida logo no login, sidebar e home, upload exclusivo na Administração
ATRIA, fallback estável e tamanhos do menu em desktop e smartphone.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'static/index.html').read_text(encoding='utf-8')
login=(ROOT/'static/login.html').read_text(encoding='utf-8')
app=(ROOT/'static/app.js').read_text(encoding='utf-8')
css=(ROOT/'static/atria-institutional-brand.css').read_text(encoding='utf-8')
api=(ROOT/'app.py').read_text(encoding='utf-8')


def test_institutional_identity_is_global_not_an_organization_override():
    assert "PRODUCT_BRAND_ASSET_KINDS = {'logo', 'logo_dark', 'favicon', 'watermark', 'institutional_logo'}" in api
    assert "BRAND_ASSET_KINDS = {'logo', 'logo_dark', 'favicon', 'watermark'}" in api
    assert "required = {'logo_dark', 'favicon'}" in api
    assert "productBrandAssetUrl('institutional_logo')" in app
    assert "productBrandAssetCard('institutional_logo','Logo institucional Nexon Labs'" in app
    assert "state.platform_admin" in app
    assert "product_brand_admin" in api
    assert "normalize_brand_logo(kind, raw, mime_type)" in api


def test_login_and_app_use_one_global_image_with_fallback():
    assert 'id="login-institutional-logo"' in login
    assert "brand.asset_urls?.institutional_logo" in login
    assert "/static/nexon-monochrome-dark.svg" in login
    assert 'id="sidebar-institutional-logo"' in html
    assert 'id="sidebar-footer-decoration"' in html
    assert "const institutionalUrl=productBrandAssetUrl('institutional_logo')" in app
    assert "institutionDecoration.hidden=true" in app
    assert "productBrandAssetUrl('institutional_logo')||'/static/nexon-monochrome-dark.svg'" in app
    assert "organization-brand-image" in html
    assert "const logo=custom?brandAssetUrl('logo_dark'):officialLogo" in app
    assert "brandAssetUrl('institutional_logo')" not in app
    assert 'id="app-favicon"' in html


def test_menu_click_targets_larger_and_mobile_remains_scrollable():
    assert 'atria-institutional-brand.css?v=institutional-r1' in html
    assert 'atria-institutional-brand.css?v=institutional-r1' in login
    assert 'min-height:50px!important' in css
    assert 'min-height:49px!important' in css
    assert 'overflow-y:auto!important' in css
    assert '.sidebar-institutional-logo[hidden]' in css
    assert '.footer-molecule[hidden]' in css
    assert 'max-height:45px' in css
