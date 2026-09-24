"""Matriz visual aprovada Opção B.
Não redesenha a arte: recorta os próprios pixels da referência entregue pelo cliente.
Uma única imagem de referência é armazenada no banco, não no disco efêmero do Render.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import re

from fastapi import Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, Session, mapped_column
from PIL import Image, ImageDraw, ImageFont
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

APPROVED_SHA256='d01bae604b83e5df8925041f812ad3ad9b7c479a57882d6093dfc6e713412155'
BOXES={'signature':(786,106,1519,398),'front':(797,436,1508,696),'back':(792,724,1510,993)}
NAVY='#0b2341'
INK='#112c4b'
TEAL='#119f9d'

class ReferenceUpload(BaseModel):
    image_data: str = Field(min_length=500,max_length=9_000_000)
    # A confirmação explícita permite PNG e JPEG salvos pelo celular sem afirmar
    # que seus bytes são idênticos ao JPEG histórico. A validação visual é do admin.
    confirmed: bool = False

MAX_IMAGE_BYTES=6_000_000
EXPECTED_SIZE=(1536,1024)
FORMATS={'image/png':'PNG','image/jpeg':'JPEG'}

def raw_image(value: str,confirmed: bool=False):
    try:
        header,encoded=value.split(',',1)
    except ValueError:
        raise HTTPException(422,'Selecione a imagem em PNG ou JPEG.') from None
    if not header.startswith('data:') or ';base64' not in header:
        raise HTTPException(422,'Selecione um arquivo PNG ou JPEG válido.')
    declared=header[5:].split(';',1)[0].lower()
    if declared not in FORMATS:
        raise HTTPException(422,'Formato não aceito: selecione PNG ou JPEG.')
    if len(encoded)>8_000_000:
        raise HTTPException(413,'Imagem maior que 6 MB.')
    try:
        raw=base64.b64decode(encoded,validate=True)
    except (ValueError,binascii.Error) as exc:
        raise HTTPException(422,'Não foi possível ler a imagem.') from exc
    if len(raw)>MAX_IMAGE_BYTES:
        raise HTTPException(413,'A imagem deve ter no máximo 6 MB.')
    is_original=hashlib.sha256(raw).hexdigest()==APPROVED_SHA256
    if not is_original and not confirmed:
        raise HTTPException(422,'Confira a prévia e marque a confirmação da Opção B antes de instalar.')
    try:
        with Image.open(io.BytesIO(raw)) as picture:
            if picture.size!=EXPECTED_SIZE:
                raise HTTPException(422,
                    f'A imagem possui {picture.width} × {picture.height} pixels; a referência completa deve ter 1536 × 1024 pixels. Envie a arte completa, sem recortar.')
            if picture.format!=FORMATS[declared]:
                raise HTTPException(422,'A extensão e o conteúdo da imagem não correspondem. Escolha PNG ou JPEG original.')
            picture.verify()
    except (OSError,ValueError,Image.DecompressionBombError) as exc:
        raise HTTPException(422,'Imagem inválida. Selecione a arte completa em PNG ou JPEG.') from exc
    return raw

def install_reference(app,Base,DB,engine,authorized,admin_only):
    class ApprovedArtwork(Base):
        __tablename__='approved_brand_artwork'
        id:Mapped[int]=mapped_column(Integer,primary_key=True)
        image:Mapped[bytes]=mapped_column(nullable=False)
    Base.metadata.create_all(engine,tables=[ApprovedArtwork.__table__])
    def session():
        with DB() as db:yield db

    @app.get('/api/brand-reference/status',dependencies=[Depends(authorized)])
    def reference_status(db:Session=Depends(session)):
        return {'installed':db.get(ApprovedArtwork,1) is not None}

    @app.put('/api/brand-reference',dependencies=[Depends(admin_only)])
    def save_reference(data:ReferenceUpload,db:Session=Depends(session)):
        # PNG/JPEG podem ter codificações diferentes: a prévia e a confirmação
        # explícita evitam confundir igualdade de arquivos com igualdade visual.
        original=raw_image(data.image_data,data.confirmed)
        row=db.get(ApprovedArtwork,1)
        if row:row.image=original
        else:db.add(ApprovedArtwork(id=1,image=original))
        db.commit()
        return {'ok':True,'installed':True,'sha256':hashlib.sha256(original).hexdigest(),
                'exact_original_file':hashlib.sha256(original).hexdigest()==APPROVED_SHA256}

    @app.get('/api/brand-reference/{kind}',dependencies=[Depends(authorized)])
    def reference_preview(kind:str,db:Session=Depends(session)):
        row=db.get(ApprovedArtwork,1)
        if row is None:raise HTTPException(409,'A matriz visual aprovada ainda não foi instalada.')
        if kind not in BOXES:raise HTTPException(404,'Prévia não encontrada.')
        with Image.open(io.BytesIO(row.image)) as picture:
            return Response(content=encode(picture.crop(BOXES[kind])),media_type='image/png',
                            headers={'Cache-Control':'private, no-store'})
    return ApprovedArtwork

def encode(image):
    out=io.BytesIO();image.save(out,format='PNG',optimize=True)
    return out.getvalue()

def faces(image):
    return {name:image.crop(bounds).convert('RGB') for name,bounds in BOXES.items()}

def font(size,bold=False):
    import reportlab
    from pathlib import Path
    fp=Path(reportlab.__file__).resolve().parent/'fonts'/('VeraBd.ttf' if bold else 'Vera.ttf')
    try:return ImageFont.truetype(str(fp),size)
    except OSError:return ImageFont.load_default()

def writefit(draw,text,xy,maxwidth,size,bold=False,color=INK):
    if not text:return
    value=str(text)
    while size>9 and draw.textlength(value,font=font(size,bold))>maxwidth:size-=1
    draw.text(xy,value,font=font(size,bold),fill=color)

def contact_lines(data):
    result=[]
    for k,prefix in (('whatsapp','W'),('site','@'),('city','•'),('email','E')):
        value=str(data.get(k) or '').strip()
        if k=='site':value=re.sub(r'^https?://','',value).rstrip('/')
        if value:result.append((prefix,value))
    return result

def draw_contacts(draw,data,x,y,spacing,text_size,max_width):
    for ix,(icon,value) in enumerate(contact_lines(data)):
        yy=y+spacing*ix
        # Pictogramas à esquerda, sem deslocar o ícone QR ou os componentes da imagem original.
        draw.ellipse((x,yy+2,x+19,yy+21),fill=TEAL if icon=='W' else INK)
        writefit(draw,icon,(x+5,yy+4),15,12,True,color='white')
        writefit(draw,value,(x+34,yy),max_width,text_size,color=INK)

def draw_personalized(original,data,kind):
    art=original.copy().convert('RGB')
    if kind=='front':return art  # Frente institucional: exatamente os pixels aprovados.
    d=ImageDraw.Draw(art)
    name=str(data.get('name') or '').upper()
    role=str(data.get('role') or 'Colaborador')
    if kind=='signature':
        # Somente o retângulo branco de DADOS VARIÁVEIS é limpo. A marca, faixa
        # diagonal, slogan, ícones/rodapé, dimensões e proporções são preservados.
        d.rectangle((345,20,718,218),fill='white')
        writefit(d,name,(347,24),353,23,True)
        writefit(d,role,(347,58),355,18)
        writefit(d,'Nexon Labs',(347,83),350,17,True,color=TEAL)
        draw_contacts(d,data,347,121,25,17,325)
        return art
    if kind=='back':
        d.rectangle((45,35,325,228),fill='white')
        writefit(d,name,(47,40),265,21,True)
        writefit(d,role,(47,70),273,15)
        writefit(d,'Nexon Labs',(47,95),260,16,True,color=TEAL)
        draw_contacts(d,data,48,132,25,15,242)
        # O QR da composição original é ilustrativo; substituir APENAS o miolo
        # quadrado pelo código funcional do endereço cadastrado.
        if data.get('site'):
            qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                             box_size=8,border=1)
            qr.add_data(data['site']);qr.make(fit=True)
            pict=qr.make_image(fill_color=INK,back_color='white').convert('RGB')
            art.paste(pict.resize((90,90),Image.Resampling.NEAREST),(374,64))
        else:
            d.rectangle((373,63,465,154),fill='white')
        return art
    raise ValueError('Arte inválida')

def signature_html(data,png):
    import html
    uri='data:image/png;base64,'+base64.b64encode(png).decode('ascii')
    name=html.escape(data.get('name') or '',quote=True)
    site=html.escape(data.get('site') or '',quote=True)
    phone=re.sub(r'\D','',data.get('whatsapp') or '')
    if len(phone)==11:phone='55'+phone
    links=('<a href="https://wa.me/'+phone+'">WhatsApp</a> &nbsp; ' if phone else '')
    links+=('<a href="'+site+'">Site</a>' if site else '')
    return ('<!doctype html><html lang="pt-BR"><meta charset="utf-8">'
            '<body style="margin:0;font-family:Arial,sans-serif"><table role="presentation" cellspacing="0" cellpadding="0">'
            '<tr><td><img width="733" height="292" alt="Assinatura de '+name+
            '" style="max-width:100%;height:auto" src="'+uri+'"></td></tr><tr><td style="font-size:12px;padding:6px">'
            +links+'</td></tr></table></body></html>')

def card_pdf(face,back):
    # A matriz de referência é uma montagem horizontal (~2,7:1), não um cartão
    # gráfico convencional (~1,8:1). Não esticar: ajustar proporcionalmente e
    # completar a área sem alterar letras, logo ou a composição aprovada.
    out=io.BytesIO()
    c=canvas.Canvas(out,pagesize=(96*mm,56*mm),pageCompression=1)
    c.setTitle('Nexon Labs — modelo B aprovado, referência visual')
    for art,color in ((face,NAVY),(back,'white')):
        c.setFillColor(color);c.rect(0,0,96*mm,56*mm,stroke=0,fill=1)
        iw,ih=art.size
        width=96*mm
        height=width*ih/iw
        c.drawImage(ImageReader(art),0,(56*mm-height)/2,width=width,height=height,mask='auto')
        c.showPage()
    c.save()
    return out.getvalue()
