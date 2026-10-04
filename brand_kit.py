"""Materiais de identidade do ATRIA por colaborador.
O padrão oficial usa somente logo e informações da organização/pessoa.
Cada organização herda a marca ATRIA ou aplica sua identidade personalizada.
Um template externo compatível pode substituir o padrão quando instalado pelo administrador.
"""
from __future__ import annotations

import io
import os
import html
import math
import re
import hashlib
import json
import threading
from collections import OrderedDict
from functools import lru_cache
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

NAVY=(11,35,61); NAVY2=(14,49,78); TEAL=(18,174,174)
CYAN=(24,192,207); INK=(15,40,65); MUTED=(81,104,125)
WHITE=(255,255,255); LINE=(222,232,242)
SITE='https://atria.nexonlabs.com.br'
CITY='Patos de Minas - MG'
SLOGAN='Tecnologia que simplifica necessidades.'
LABELS=('APLICATIVOS', 'INTEGRAÇÃO', 'AUTOMAÇÃO', 'RESULTADOS')
SUBLABELS=('SOB MEDIDA', 'DE DADOS', 'DE PROCESSOS', 'OPERACIONAIS')

class BrandData(BaseModel):
    whatsapp: str = Field(default='', max_length=40)
    city: str = Field(default=CITY, max_length=120)
    site: str = Field(default=SITE, max_length=250)

    @field_validator('whatsapp','city','site')
    @classmethod
    def trim(cls,value):
        return value.strip()

    @field_validator('site')
    @classmethod
    def site_url(cls,value):
        if value and not value.startswith(('https://','http://')):
            raise ValueError('O site deve começar por https:// ou http://.')
        return value

@lru_cache(maxsize=32)
def font(size, bold=False, italic=False):
    names=(
        ['/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
        if bold and italic else
        ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf'] if italic else
        ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'] if bold else
        ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    )
    # ReportLab inclui fontes Vera, úteis em hospedagens com fontes de SO reduzidas.
    import reportlab
    from pathlib import Path
    font_dir=Path(reportlab.__file__).resolve().parent/'fonts'
    names+= [str(font_dir/('VeraBI.ttf' if bold and italic else 'VeraBd.ttf' if bold else 'VeraIt.ttf' if italic else 'Vera.ttf'))]
    for path in names:
        try:return ImageFont.truetype(path,int(size))
        except OSError:pass
    return ImageFont.load_default()

def textfit(draw,text,maxwidth,size,bold=False,minsize=11):
    while size>minsize and draw.textlength(text,font=font(size,bold))>maxwidth:size-=1
    return font(size,bold)

def lines(draw,parts,x,y,color=INK,size=25,leading=1.48,bold=False,maxwidth=None):
    for part in parts:
        if not part:continue
        f=textfit(draw,part,maxwidth or 9999,size,bold)
        draw.text((x,y),part,font=f,fill=color,stroke_width=0)
        y+=int(size*leading)
    return y

def brand_mark(image,center,size,navy_core=False):
    """Símbolo oficial do app: núcleo radial com seis conexões, sem trocar a marca."""
    draw=ImageDraw.Draw(image)
    cx,cy=center
    scale=size/100
    pts=((50,12),(18,26),(83,28),(14,72),(83,76),(50,88))
    for index,(xx,yy) in enumerate(pts):
        px=cx+int((xx-50)*scale);py=cy+int((yy-50)*scale)
        clr=TEAL if index in (1,4) else WHITE
        draw.line((cx,cy,px,py),fill=clr,width=max(2,int(5*scale)))
        r=max(2,int(9*scale))
        draw.ellipse((px-r,py-r,px+r,py+r),fill=clr)
    r=max(3,int(16*scale))
    draw.ellipse((cx-r,cy-r,cx+r,cy+r),fill=NAVY if navy_core else WHITE)

def wordmark(draw,x,y,large=42,dark=False,brand_name='Nexon Labs'):
    col=INK if dark else WHITE
    name=str(brand_name or 'ATRIA').strip()
    if name.lower()=='nexon labs':
        draw.text((x,y),'NEXON',font=font(large,True),fill=col)
        off=int(draw.textlength('NEXON',font=font(large,True)))
        draw.text((x+off+8,y),'LABS',font=font(large),fill=col)
        subtitle='S O L U Ç Õ E S   D I G I T A I S'
    else:
        upper=name.upper()
        fitted=textfit(draw,upper,420,large,True,minsize=20)
        draw.text((x,y),upper,font=fitted,fill=col)
        subtitle='P O W E R E D   B Y   A T R I A'
    draw.text((x+2,y+large+8),subtitle,
              font=font(max(11,int(large*.27)),True),fill=TEAL if dark else WHITE)

def hex_color(value,default):
    text=str(value or '').strip().lstrip('#')
    if len(text)==6:
        try:return tuple(int(text[i:i+2],16) for i in (0,2,4))
        except ValueError:pass
    return default

def open_logo(raw):
    if not raw:return None
    try:
        image=Image.open(io.BytesIO(raw)).convert('RGBA')
        alpha=image.getchannel('A')
        bbox=alpha.point(lambda value:255 if value>=20 else 0).getbbox() or alpha.getbbox()
        return image.crop(bbox) if bbox else image
    except Exception:
        return None

def paste_logo(canvas,raw,box,brand_name='ATRIA',dark=False):
    x1,y1,x2,y2=box
    logo=open_logo(raw)
    if logo is not None:
        max_w,max_h=max(1,x2-x1),max(1,y2-y1)
        logo.thumbnail((max_w,max_h),Image.Resampling.LANCZOS)
        x=x1+(max_w-logo.width)//2
        y=y1+(max_h-logo.height)//2
        canvas.paste(logo,(x,y),logo)
        return
    d=ImageDraw.Draw(canvas)
    center=(x1+int((x2-x1)*.28),y1+(y2-y1)//2)
    brand_mark(canvas,center,min(120,y2-y1-20),navy_core=not dark)
    wordmark(d,x1+int((x2-x1)*.46),center[1]-38,38,dark=not dark,brand_name=brand_name)

def network_pattern(image,accent=(18,174,174),opacity=35):
    overlay=Image.new('RGBA',image.size,(255,255,255,0))
    d=ImageDraw.Draw(overlay)
    w,h=image.size
    points=[(int(w*.06),int(h*.20),26),(int(w*.14),int(h*.08),15),(int(w*.18),int(h*.34),19),
            (int(w*.82),int(h*.16),22),(int(w*.91),int(h*.28),31),(int(w*.78),int(h*.72),17),
            (int(w*.92),int(h*.80),24),(int(w*.68),int(h*.88),13)]
    links=[(0,1),(0,2),(3,4),(3,5),(5,6),(5,7)]
    for a,b in links:
        x1,y1,_=points[a];x2,y2,_=points[b]
        d.line((x1,y1,x2,y2),fill=(*accent,max(14,opacity//2)),width=2)
    for x,y,r in points:
        d.ellipse((x-r,y-r,x+r,y+r),fill=(*accent,opacity))
    base=image.convert('RGBA')
    base.alpha_composite(overlay)
    return base.convert('RGB')

def gradient(w,h,dark=True):
    im=Image.new('RGB',(w,h))
    d=ImageDraw.Draw(im)
    a=NAVY if dark else WHITE
    b=(13,65,89) if dark else (248,251,255)
    for y in range(h):
        t=y/max(1,h-1)
        color=tuple(round(a[i]*(1-t)+b[i]*t) for i in range(3))
        d.line((0,y,w,y),fill=color)
    return im

def keyboard_art(width,height):
    """Representação abstrata local de teclado, sem fotografia externa nem texto fixo."""
    bg=Image.new('RGB',(width,height),(3,18,29))
    d=ImageDraw.Draw(bg)
    d.polygon([(0,height//2),(width,0),(width,height)],fill=(7,34,51))
    for row in range(5):
        for col in range(7):
            x=30+col*int(width*.15)-row*13
            y=int(height*.33)+row*int(height*.135)+col*4
            color=(15+row*3,67+col*3,83+col*4)
            d.rounded_rectangle((x,y,x+int(width*.115),y+int(height*.07)),
                                radius=5,fill=color,outline=(19,133,152),width=1)
    bg=bg.filter(ImageFilter.GaussianBlur(2))
    d=ImageDraw.Draw(bg)
    d.line((0,int(height*.12),width,int(height*.8)),fill=(12,146,169),width=7)
    return bg

def make_qr(site,size=196):
    qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                     box_size=8,border=2)
    qr.add_data(site);qr.make(fit=True)
    return qr.make_image(fill_color='#122c48',back_color='white').convert('RGB').resize((size,size),Image.Resampling.NEAREST)

def whatsapp_url(phone):
    digits=''.join(ch for ch in phone if ch.isdigit())
    if not digits:return ''
    if len(digits)==11:digits='55'+digits
    return 'https://wa.me/'+digits

def contact_lines(member):
    output=[]
    if member.get('whatsapp'):output.append(('WA',member['whatsapp']))
    if member.get('site'):output.append(('WEB',re.sub(r'^https?://','',member['site']).rstrip('/')))
    if member.get('city'):output.append(('LOC',member['city']))
    if member.get('email'):output.append(('MAIL',member['email']))
    return output

def contact(draw,member,x,y,maxwidth,size=21,spacing=52,dark=False):
    for index,(kind,value) in enumerate(contact_lines(member)):
        yy=y+index*spacing
        draw.rounded_rectangle((x,yy,x+30,yy+30),radius=15,
                               fill=TEAL if kind=='WA' else INK)
        glyph={'WA':'W','WEB':'@','LOC':'•','MAIL':'✉'}[kind]
        draw.text((x+8,yy+3),glyph,font=font(19,True),fill=WHITE)
        f=textfit(draw,value,maxwidth-53,size,minsize=10)
        draw.text((x+46,yy+2),value,font=f,fill=INK if dark else WHITE)

def role_line(draw,member,x,y,maxwidth,size=24,dark=False):
    draw.text((x,y),member['name'].upper(),
              font=textfit(draw,member['name'].upper(),maxwidth,size,True,minsize=13),
              fill=INK if dark else WHITE)
    draw.text((x,y+44),member.get('role') or 'Colaborador',
              font=textfit(draw,member.get('role') or 'Colaborador',maxwidth,18,minsize=11),
              fill=INK if dark else WHITE)
    draw.text((x,y+77),str(member.get('_brand_name') or 'ATRIA'),font=font(20,True),fill=TEAL)

def _brand_palette(member):
    return (
        hex_color(member.get('_primary_color'),NAVY),
        hex_color(member.get('_secondary_color'),TEAL),
    )

def _contact_rows(member):
    rows=[]
    if member.get('email'):rows.append(('✉',member['email']))
    if member.get('site'):rows.append(('◎',re.sub(r'^https?://','',member['site']).rstrip('/')))
    if member.get('whatsapp'):rows.append(('W',member['whatsapp']))
    if member.get('city'):rows.append(('●',member['city']))
    return rows

def _person_block(draw,member,x,y,maxwidth,accent):
    name=str(member.get('name') or '').upper()
    role=str(member.get('role') or 'Colaborador')
    organization=str(member.get('_brand_name') or 'ATRIA')
    draw.text((x,y),name,font=textfit(draw,name,maxwidth,38,True,minsize=19),fill=INK)
    draw.text((x,y+51),role,font=textfit(draw,role,maxwidth,25,minsize=14),fill=MUTED)
    draw.text((x,y+88),organization,font=textfit(draw,organization,maxwidth,25,True,minsize=14),fill=accent)
    yy=y+145
    for icon_text,value in _contact_rows(member)[:4]:
        draw.rounded_rectangle((x,yy,x+39,yy+39),radius=10,fill=(239,247,251))
        draw.text((x+10,yy+5),icon_text,font=font(21,True),fill=INK)
        draw.text((x+56,yy+4),value,font=textfit(draw,value,maxwidth-56,23,minsize=13),fill=INK)
        yy+=58

def front(member,branding=None,w=1200,h=667):
    branding=branding or {}
    primary,accent=_brand_palette(member)
    im=Image.new('RGB',(w,h),WHITE)
    im=network_pattern(im,accent,opacity=22)
    d=ImageDraw.Draw(im)
    left=int(w*.43)
    d.rounded_rectangle((1,1,w-2,h-2),radius=28,outline=LINE,width=2)
    d.rounded_rectangle((1,1,left+24,h-2),radius=28,fill=primary)
    d.rectangle((left-10,1,left+24,h-2),fill=primary)
    d.line((left+45,70,left+45,h-70),fill=accent,width=4)
    logo=branding.get('logo_dark') or branding.get('logo')
    paste_logo(im,logo,(38,95,left-25,h-95),member.get('_brand_name') or 'ATRIA',dark=True)
    d=ImageDraw.Draw(im)
    _person_block(d,member,left+100,122,w-left-145,accent)
    return im

def back(member,branding=None,w=1200,h=667):
    branding=branding or {}
    primary,accent=_brand_palette(member)
    im=Image.new('RGB',(w,h),primary)
    im=network_pattern(im,accent,opacity=28)
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((1,1,w-2,h-2),radius=28,outline=tuple(min(255,x+35) for x in primary),width=2)
    logo=branding.get('logo_dark') or branding.get('logo')
    paste_logo(im,logo,(170,155,w-170,h-155),member.get('_brand_name') or 'ATRIA',dark=True)
    return im

def signature(member,branding=None,w=1600,h=430):
    branding=branding or {}
    primary,accent=_brand_palette(member)
    im=Image.new('RGB',(w,h),WHITE)
    im=network_pattern(im,accent,opacity=18)
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((2,2,w-3,h-3),radius=24,outline=LINE,width=2)
    divider=615
    d.line((divider,58,divider,h-58),fill=accent,width=4)
    logo=branding.get('logo') or branding.get('logo_dark')
    paste_logo(im,logo,(55,70,divider-60,h-70),member.get('_brand_name') or 'ATRIA',dark=False)
    d=ImageDraw.Draw(im)
    _person_block(d,member,divider+68,54,w-divider-115,accent)
    return im

def render(member,kind,branding=None):
    if kind=='front':return front(member,branding)
    if kind=='back':return back(member,branding)
    if kind=='signature':return signature(member,branding)
    raise HTTPException(404,'Material não encontrado.')

def image_png(image):
    output=io.BytesIO();image.save(output,format='PNG',optimize=True)
    return output.getvalue()

def card_pdf(member,branding=None):
    from reportlab.lib.units import mm
    buffer=io.BytesIO()
    c=canvas.Canvas(buffer,pagesize=(96*mm,56*mm),pageCompression=1)
    c.setTitle(f"{member.get('_brand_name') or 'ATRIA'} — cartão de visita")
    # Página inteira 96×56 mm: formato de corte 90×50 mm + sangria de 3 mm por lado.
    for art in (front(member,branding),back(member,branding)):
        c.drawImage(ImageReader(art),0,0,width=96*mm,height=56*mm,mask='auto')
        c.showPage()
    c.save();return buffer.getvalue()

def signature_html(member,png):
    """Versão HTML editável com dados clicáveis e marca visual inline.
    Alguns provedores de e-mail bloqueiam imagens incorporadas: PNG é alternativa.
    """
    image='data:image/png;base64,'+__import__('base64').b64encode(png).decode('ascii')
    site=html.escape(member.get('site') or '',quote=True)
    phone=html.escape(whatsapp_url(member.get('whatsapp') or ''),quote=True)
    extra=''
    if phone:extra+='<a href="'+phone+'">WhatsApp</a> &nbsp; '
    if site:extra+='<a href="'+site+'">Site</a>'
    return ('<!doctype html><html lang="pt-BR"><meta charset="utf-8">'
            '<title>Assinatura de e-mail - '+html.escape(member['name'])+'</title>'
            '<body style="margin:0;padding:0;font-family:Arial,sans-serif">'
            '<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr><td>'
            '<img src="'+image+'" width="590" height="228" alt="Assinatura de '
            +html.escape(member['name'],quote=True)+' - Nexon Labs" style="max-width:100%;height:auto;display:block">'
            '</td></tr><tr><td style="padding:7px 4px;font-size:12px;color:#0b2d4a">'+extra+
            '</td></tr></table></body></html>')

# Pequeno cache de renderização em cada processo: a chave depende da imagem
# aprovada e dos dados usados na arte. Não há gravação de imagens em disco.
# O servidor pode reiniciar; isso não invalida a matriz persistida no PostgreSQL.
_BRAND_CACHE = OrderedDict()
_BRAND_CACHE_BYTES = 0
_BRAND_CACHE_MAX_BYTES = 18_000_000
_BRAND_CACHE_LOCK = threading.RLock()

def cached_artifact(key, make):
    global _BRAND_CACHE_BYTES
    with _BRAND_CACHE_LOCK:
        result=_BRAND_CACHE.get(key)
        if result is not None:
            _BRAND_CACHE.move_to_end(key)
            return result
    content,media,filename=make()
    etag='"'+hashlib.sha256(content).hexdigest()+'"'
    value=(content,media,filename,etag)
    if len(content)<=_BRAND_CACHE_MAX_BYTES:
        with _BRAND_CACHE_LOCK:
            existing=_BRAND_CACHE.get(key)
            if existing is not None:
                _BRAND_CACHE.move_to_end(key)
                return existing
            _BRAND_CACHE[key]=value
            _BRAND_CACHE_BYTES+=len(content)
            while _BRAND_CACHE_BYTES>_BRAND_CACHE_MAX_BYTES:
                _,old=_BRAND_CACHE.popitem(last=False)
                _BRAND_CACHE_BYTES-=len(old[0])
    return value

def artifact_key(data,reference,kind,fmt):
    # A edição de qualquer dado ou a troca da imagem-matriz altera a chave.
    value=hashlib.sha256()
    value.update(b'nexon-brand-b-cache-v1\\0')
    value.update(hashlib.sha256(reference or b'').digest())
    value.update(json.dumps(data,sort_keys=True,ensure_ascii=False).encode('utf-8'))
    value.update(kind.encode('ascii'))
    value.update(fmt.encode('ascii'))
    return value.digest()

def install_brand_kit(app,Base,DB,engine,authorized,log,Member,member_dict,Organization=None):
    class MemberBrand(Base):
        __tablename__='member_brand_profiles'
        member_id: Mapped[int]=mapped_column(ForeignKey('members.id',ondelete='CASCADE'),primary_key=True)
        whatsapp: Mapped[str]=mapped_column(String(40),default='',nullable=False)
        city: Mapped[str]=mapped_column(String(120),default=CITY,nullable=False)
        site: Mapped[str]=mapped_column(String(250),default=SITE,nullable=False)
    Base.metadata.create_all(engine,tables=[MemberBrand.__table__])

    def session(request: Request):
        current=authorized(request)
        with DB() as db:
            db.info['organization_id']=current['organization_id']
            yield db

    def org_id(db: Session):
        return int(db.info['organization_id'])

    def extra(db,member):
        profile=db.get(MemberBrand,member.id)
        return dict(whatsapp=profile.whatsapp,city=profile.city,site=profile.site) if profile else dict(whatsapp='',city=CITY,site=SITE)

    def member_data(db,member):
        brand_name='ATRIA'
        brand_slug='atria'
        primary='#0B2D4A'
        secondary='#14B8A6'
        use_custom=False
        if Organization is not None:
            organization=db.get(Organization,org_id(db))
            if organization is not None:
                brand_name=organization.name
                brand_slug=organization.slug
                primary=organization.primary_color or primary
                secondary=organization.secondary_color or secondary
                use_custom=bool(organization.use_custom_brand)
        return dict(name=member.name,role=member.role,email=member.email,
                    _brand_name=brand_name,_brand_slug=brand_slug,
                    _primary_color=primary,_secondary_color=secondary,
                    _use_custom_brand=use_custom,**extra(db,member))

    def branding_data(db,data):
        from app import OrganizationBrandAsset, ProductBrandAsset
        custom=bool(data.get('_use_custom_brand'))
        organization_id=org_id(db)
        def organization_asset(kind):
            if not custom:return None
            row=db.scalar(select(OrganizationBrandAsset).where(
                OrganizationBrandAsset.organization_id==organization_id,
                OrganizationBrandAsset.kind==kind
            ).limit(1))
            return row.image if row is not None else None
        def product_asset(kind):
            row=db.get(ProductBrandAsset,kind)
            return row.image if row is not None else None
        return {
            'logo':organization_asset('logo') or product_asset('logo'),
            'logo_dark':organization_asset('logo_dark') or organization_asset('logo') or product_asset('logo_dark') or product_asset('logo'),
        }

    def sync(db,member,data):
        saved=db.get(MemberBrand,member.id)
        if saved is None:
            saved=MemberBrand(member_id=member.id);db.add(saved)
        saved.whatsapp=data.whatsapp
        saved.city=data.city
        saved.site=data.site

    def member_or_404(db,member_id):
        member=db.scalar(select(Member).where(
            Member.id==member_id,
            Member.organization_id==org_id(db)
        ).limit(1))
        if not member:raise HTTPException(404,'Colaborador não encontrado.')
        return member

    @app.get('/api/members/{member_id}/brand/{kind}',dependencies=[Depends(authorized)])
    def export(member_id:int,kind:str,request:Request,format:str='png',db:Session=Depends(session)):
        if kind not in ('front','back','card','signature'):
            raise HTTPException(404,'Material não encontrado.')
        if (kind=='card' and format!='pdf') or format not in ('png','pdf','html'):
            raise HTTPException(422,'Formato de arquivo inválido.')
        if kind in ('front','back') and format!='png':
            raise HTTPException(422,'Para o cartão em PDF, selecione cartão completo.')
        if kind=='signature' and format=='pdf':
            raise HTTPException(422,'A assinatura está disponível em PNG ou HTML.')
        member=member_or_404(db,member_id)
        data=member_data(db,member)
        from approved_template import cached_faces as approved_faces, draw_personalized, encode as approved_png
        from approved_template import signature_html as approved_html, card_pdf as approved_pdf
        from app import ApprovedArtwork
        source=db.get(ApprovedArtwork,org_id(db))
        branding=branding_data(db,data)
        def generate():
            if source is not None:
                parts=approved_faces(source.image)
                if kind=='card':
                    front=draw_personalized(parts['front'],data,'front')
                    back=draw_personalized(parts['back'],data,'back')
                    return approved_pdf(front,back),'application/pdf','cartao'
                art=draw_personalized(parts[kind],data,kind)
                png=approved_png(art)
                if format=='html':
                    return approved_html(data,png).encode('utf-8'),'text/html; charset=utf-8','assinatura'
                return png,'image/png',kind
            if kind=='card':
                return card_pdf(data,branding),'application/pdf','cartao'
            art=render(data,kind,branding)
            png=image_png(art)
            if format=='html':
                return signature_html(data,png).encode('utf-8'),'text/html; charset=utf-8','assinatura'
            return png,'image/png',kind

        # Cachear imagens por conteúdo da matriz + informações do colaborador.
        # Uma alteração nesses dados provoca geração nova sem exibir versão antiga.
        # A frente não contém dados pessoais: a mesma arte aprovada é
        # compartilhada entre os colaboradores no cache do servidor.
        cache_data={} if kind=='front' and source is not None else data
        brand_bytes=(branding.get('logo') or b'')+(branding.get('logo_dark') or b'')
        reference=(source.image if source is not None else b'')+hashlib.sha256(brand_bytes).digest()
        key=artifact_key(cache_data,reference,kind,format)
        content,media,filename,etag=cached_artifact(key,generate)
        common={'ETag':etag,'Vary':'Cookie',
                'Cache-Control':'private, no-cache, must-revalidate',
                'X-Content-Type-Options':'nosniff'}
        # Na reabertura da página, o navegador reaproveita os bytes locais se
        # o arquivo não foi alterado; a rota segue exigindo sessão autenticada.
        if request is not None and request.headers.get('if-none-match')==etag:
            return Response(status_code=304,headers=common)
        safe=re.sub(r'[^a-z0-9]+','-',member.name.lower()).strip('-') or 'colaborador'
        ext='pdf' if format=='pdf' else 'html' if format=='html' else 'png'
        prefix=re.sub(r'[^a-z0-9]+','-',str(data.get('_brand_slug') or 'atria').lower()).strip('-') or 'atria'
        return Response(content=content,media_type=media,headers={
            **common,
            'Content-Disposition':f'attachment; filename="{prefix}_{safe}_{filename}.{ext}"'
        })

    return MemberBrand,extra,sync
