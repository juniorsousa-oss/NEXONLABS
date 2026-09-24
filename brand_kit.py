"""Opção B aprovada — peças de identidade por colaborador.
Frente escura: marca à esquerda, teclado/diagonal e "DA IDEIA À OPERAÇÃO" à direita.
Verso claro: colaborador à esquerda, QR central e serviços no painel lateral escuro.
Assinatura: bloco escuro da marca à esquerda e dados personalizados à direita.
As artes de colaboradores são documentos internos autenticados.
"""
from __future__ import annotations

import io
import html
import math
import re
from functools import lru_cache
from urllib.parse import quote

from fastapi import Depends, HTTPException
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
SITE='https://nexonlabs.onrender.com'
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

def wordmark(draw,x,y,large=42,dark=False):
    col=INK if dark else WHITE
    draw.text((x,y),'NEXON',font=font(large,True),fill=col)
    off=int(draw.textlength('NEXON',font=font(large,True)))
    draw.text((x+off+8,y),'LABS',font=font(large),fill=col)
    draw.text((x+2,y+large+8),'S O L U Ç Õ E S   D I G I T A I S',
              font=font(max(11,int(large*.27)),True),fill=TEAL if dark else WHITE)

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
    draw.text((x,y+77),'Nexon Labs',font=font(20,True),fill=TEAL)

def front(member,w=1134,h=661):
    im=gradient(w,h,True);d=ImageDraw.Draw(im)
    # Faixa direita de teclado e borda diagonal ciano, como a Opção B aprovada.
    art=keyboard_art(int(w*.36),h)
    im.paste(art,(w-art.width,0))
    d=ImageDraw.Draw(im)
    d.polygon([(int(w*.68),0),(int(w*.75),0),(int(w*.62),h),(int(w*.55),h)],
              fill=(10,46,73))
    d.line((int(w*.71),0,int(w*.61),h),fill=CYAN,width=4)
    for k in range(3):
        x=int(w*(.78+k*.08))
        d.line((x,-30,x-int(w*.13),h+30),fill=(10,77,102),width=12)
    d.rounded_rectangle((0,0,w-1,h-1),radius=17,outline=(39,113,139),width=2)
    brand_mark(im,(116,180),135)
    d=ImageDraw.Draw(im)
    wordmark(d,206,139,49)
    d.line((100,390,169,390),fill=CYAN,width=5)
    lines(d,[SLOGAN],100,415,WHITE,20,maxwidth=int(w*.51))
    # A frase no mesmo lado/posição do layout aprovado, sem inventar outra chamada.
    lines(d,['DA','IDEIA','À','OPERAÇÃO.'],w-180,170,WHITE,29,leading=1.35,bold=True,maxwidth=159)
    return im

def back(member,w=1134,h=661):
    im=Image.new('RGB',(w,h),WHITE);d=ImageDraw.Draw(im)
    d.polygon([(int(w*.80),0),(w,0),(w,h),(int(w*.70),h)],fill=NAVY)
    d.polygon([(int(w*.79),0),(int(w*.84),0),(int(w*.73),h),(int(w*.68),h)],fill=TEAL)
    role_line(d,member,59,77,int(w*.49),size=29,dark=True)
    contact(d,member,60,256,int(w*.49),size=24,spacing=67,dark=True)
    d.line((int(w*.54),70,int(w*.54),h-65),fill=LINE,width=3)
    if member.get('site'):
        qr=make_qr(member['site'],169)
        im.paste(qr,(int(w*.585),115))
        d=ImageDraw.Draw(im)
        lines(d,['ACESSE NOSSO SITE'],int(w*.57),307,INK,17,leading=1.4,bold=True)
        lines(d,['E CONHEÇA NOSSAS','SOLUÇÕES'],int(w*.57),341,MUTED,13,leading=1.45)
    else:
        d.text((int(w*.57),205),'SITE NÃO INFORMADO',fill=INK,font=font(14,True))
    for i,(title,subtitle) in enumerate(zip(LABELS,SUBLABELS)):
        yy=88+i*135
        d.ellipse((w-179,yy,w-145,yy+34),outline=CYAN,width=3)
        lines(d,[title,subtitle],w-130,yy,WHITE,16,leading=1.4,bold=True,maxwidth=120)
    return im

def signature(member,w=1180,h=455):
    im=Image.new('RGB',(w,h),WHITE)
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((3,3,w-4,h-4),radius=20,fill=WHITE,outline=LINE,width=2)
    # Bloco naval com corte diagonal e filete teal, mesma composição B.
    d.polygon([(3,3),(465,3),(527,h-3),(3,h-3)],fill=NAVY)
    d.polygon([(433,3),(456,3),(520,h-3),(499,h-3)],fill=TEAL)
    brand_mark(im,(164,143),131)
    d=ImageDraw.Draw(im)
    wordmark(d,54,226,39)
    d.line((54,337,112,337),fill=CYAN,width=4)
    lines(d,['Tecnologia que','simplifica necessidades.'],54,351,WHITE,17,leading=1.45,maxwidth=400)
    role_line(d,member,547,69,580,size=31,dark=True)
    contact(d,member,551,199,570,size=21,spacing=46,dark=True)
    d.line((550,h-58,w-34,h-58),fill=LINE,width=2)
    d.text((551,h-48),'APLICATIVOS   |   AUTOMAÇÃO   |   INTEGRAÇÃO   |   RESULTADOS',
           font=textfit(d,'APLICATIVOS   |   AUTOMAÇÃO   |   INTEGRAÇÃO   |   RESULTADOS',585,13,minsize=9),fill=MUTED)
    return im

def render(member,kind):
    if kind=='front':return front(member)
    if kind=='back':return back(member)
    if kind=='signature':return signature(member)
    raise HTTPException(404,'Material não encontrado.')

def image_png(image):
    output=io.BytesIO();image.save(output,format='PNG',optimize=True)
    return output.getvalue()

def card_pdf(member):
    from reportlab.lib.units import mm
    buffer=io.BytesIO()
    c=canvas.Canvas(buffer,pagesize=(96*mm,56*mm),pageCompression=1)
    c.setTitle('Nexon Labs — cartão de visita · Opção B')
    # Página inteira 96×56 mm: formato de corte 90×50 mm + sangria de 3 mm por lado.
    for art in (front(member),back(member)):
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
    if site:extra+='<a href="'+site+'">Site da Nexon Labs</a>'
    return ('<!doctype html><html lang="pt-BR"><meta charset="utf-8">'
            '<title>Assinatura de e-mail - '+html.escape(member['name'])+'</title>'
            '<body style="margin:0;padding:0;font-family:Arial,sans-serif">'
            '<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr><td>'
            '<img src="'+image+'" width="590" height="228" alt="Assinatura de '
            +html.escape(member['name'],quote=True)+' - Nexon Labs" style="max-width:100%;height:auto;display:block">'
            '</td></tr><tr><td style="padding:7px 4px;font-size:12px;color:#0b2d4a">'+extra+
            '</td></tr></table></body></html>')

def install_brand_kit(app,Base,DB,engine,authorized,log,Member,member_dict):
    class MemberBrand(Base):
        __tablename__='member_brand_profiles'
        member_id: Mapped[int]=mapped_column(ForeignKey('members.id',ondelete='CASCADE'),primary_key=True)
        whatsapp: Mapped[str]=mapped_column(String(40),default='',nullable=False)
        city: Mapped[str]=mapped_column(String(120),default=CITY,nullable=False)
        site: Mapped[str]=mapped_column(String(250),default=SITE,nullable=False)
    Base.metadata.create_all(engine,tables=[MemberBrand.__table__])

    def session():
        with DB() as db:yield db

    def extra(db,member):
        profile=db.get(MemberBrand,member.id)
        return dict(whatsapp=profile.whatsapp,city=profile.city,site=profile.site) if profile else dict(whatsapp='',city=CITY,site=SITE)

    def member_data(db,member):
        return dict(name=member.name,role=member.role,email=member.email,**extra(db,member))

    def sync(db,member,data):
        saved=db.get(MemberBrand,member.id)
        if saved is None:
            saved=MemberBrand(member_id=member.id);db.add(saved)
        saved.whatsapp=data.whatsapp
        saved.city=data.city
        saved.site=data.site

    def member_or_404(db,member_id):
        member=db.get(Member,member_id)
        if not member:raise HTTPException(404,'Colaborador não encontrado.')
        return member

    @app.get('/api/members/{member_id}/brand/{kind}',dependencies=[Depends(authorized)])
    def export(member_id:int,kind:str,format:str='png',db:Session=Depends(session)):
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
        if kind=='card':
            content=card_pdf(data);media='application/pdf';filename='cartao'
        else:
            art=render(data,kind);png=image_png(art)
            if format=='html':
                content=signature_html(data,png).encode('utf-8')
                media='text/html; charset=utf-8';filename='assinatura'
            else:
                content=png;media='image/png';filename=kind
        safe=re.sub(r'[^a-z0-9]+','-',member.name.lower()).strip('-') or 'colaborador'
        ext='pdf' if format=='pdf' else 'html' if format=='html' else 'png'
        return Response(content=content,media_type=media,headers={
            'Content-Disposition':f'attachment; filename="nexonlabs_{safe}_{filename}.{ext}"',
            'Cache-Control':'private, no-store',
            'X-Content-Type-Options':'nosniff'
        })

    return MemberBrand,extra,sync
