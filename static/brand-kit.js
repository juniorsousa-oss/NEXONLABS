/* Materiais de identidade do ATRIA — padrão oficial por organização.
   O cliente pode manter o template padrão ou instalar uma matriz personalizada compatível. */
'use strict';
window.NexonBrandUI=(()=>{
  const html=v=>esc(v??'');
  const site='https://atria.nexonlabs.com.br';
  let busy=false,referenceReady=false,referenceChecked=false,referenceLoading=false;
  let selectedReference='',referenceFits=false;
  async function checkReference(){
    if(referenceLoading)return;
    referenceLoading=true;
    try{
      const response=await api('/brand-reference/status');
      referenceReady=Boolean(response.installed);referenceChecked=true;
    }catch(e){referenceReady=false;referenceChecked=true;}
    finally{referenceLoading=false;if(typeof route!=='undefined'&&route==='equipe'&&typeof render==='function')render();}
  }
  function avatar(member){return html(initials(member.name))}
  function page(){
    if(!referenceChecked&&!referenceLoading)checkReference();
    return heading('Equipe','Colaboradores, dados profissionais e materiais de '+html(state.organization?.name||'ATRIA')+'.',
      '<button type="button" class="primary" data-brand-action="new">'+icon('plus')+' Adicionar colaborador</button>')+
      (!referenceChecked?'<section class="panel"><p class="muted">Preparando materiais de identidade...</p></section>':
       '<section class="panel brand-template-warning brand-standard-ready"><div class="panel-head"><h2>Cartão de visita e assinatura</h2><span class="brand-standard-badge">'+
        (referenceReady?'Modelo personalizado ativo':'Modelo padrão ATRIA')+'</span></div>'+
        '<p>'+(referenceReady?'A organização está usando um modelo personalizado aprovado.':
          'O ATRIA já disponibiliza um layout padrão para cartão e assinatura. Você pode usá-lo imediatamente ou criar uma arte personalizada compatível com o aplicativo.')+'</p>'+
        '<div class="brand-standard-actions"><button type="button" class="secondary" data-brand-action="instructions">'+icon('download')+' Baixar instruções para IA</button>'+
        (state.user_role==='admin'?'<button type="button" class="primary" data-brand-action="install">'+
          (referenceReady?'Substituir modelo personalizado':'Instalar modelo personalizado')+'</button>':'')+
        (state.user_role==='admin'&&referenceReady?'<button type="button" class="secondary" data-brand-action="restore-template">Usar modelo padrão ATRIA</button>':'')+
        '</div><small class="member-brand-hint">O modelo padrão usa a logo, as cores e os dados da organização. Um template personalizado é opcional e pode ser restaurado a qualquer momento.</small></section>')+
      '<section class="panel"><div class="panel-head"><h2>Colaboradores</h2>'+
      '<span class="muted">'+state.members.length+' cadastrados</span></div>'+
      '<div class="list-stack member-brand-list">'+
      (state.members.length?state.members.map(m=>
        '<div class="member-brand-item"><div class="member-brand-identity">'+
        '<span class="mini-avatar">'+avatar(m)+'</span><div class="member-brand-copy"><h3>'+html(m.name)+'</h3>'+
        '<p>'+html(m.role||'Colaborador')+(m.email?' · '+html(m.email):'')+'</p>'+
        '<small>'+html(m.whatsapp||'WhatsApp não informado')+' · '+html(m.city||'Cidade não informada')+'</small></div></div>'+
        '<div class="member-brand-actions">'+
        '<button type="button" class="secondary" data-brand-action="edit" data-id="'+m.id+'" aria-label="Editar cadastro de '+html(m.name)+'">'+icon('edit')+' Editar cadastro</button>'+
        '<button type="button" class="primary" data-brand-action="preview" data-id="'+m.id+'">'+icon('file')+' Cartão e assinatura</button>'+
        '<button type="button" class="danger" data-action="delete-member" data-id="'+m.id+'">Remover</button>'+
        '</div></div>').join(''):
        empty('Equipe ainda não cadastrada','Adicione os colaboradores para gerar materiais personalizados.','new-member'))+
      '</div></section>';
  }
  function installDialog(){
    selectedReference='';referenceFits=false;
    modal('Instalar modelo personalizado',
      '<form id="brand-template-form" class="brand-template-install">'+
      '<p>Selecione a <strong>prancha completa do modelo personalizado</strong> em PNG ou JPEG. O arquivo precisa seguir exatamente a estrutura aceita pelo ATRIA; use o botão “Baixar instruções para IA” antes de criar uma nova arte.</p>'+
      '<label for="brand-template-file">Imagem aprovada *<input type="file" id="brand-template-file" name="reference" accept=".png,.jpg,.jpeg,image/png,image/jpeg" required></label>'+
      '<p id="brand-template-feedback" class="member-brand-hint brand-template-feedback" role="status" aria-live="polite">Nenhum arquivo selecionado.</p>'+
      '<img id="brand-template-preview" class="brand-template-preview" alt="Prévia da prancha completa selecionada" hidden>'+
      '<label class="brand-template-confirm"><input id="brand-template-confirmed" type="checkbox" disabled> Confirmei que a arte respeita as áreas e dimensões aceitas pelo ATRIA.</label>'+
      '<p class="member-brand-hint">Imagem completa: 1536 × 1024 pixels, até 6 MB. Não envie uma captura apenas do cartão, nem uma imagem recortada.</p>'+
      '<div class="form-actions"><button type="button" class="secondary" data-action="close-modal">Cancelar</button>'+
      '<button id="brand-install-button" type="submit" class="primary" disabled>Instalar imagem aprovada</button></div></form>');
  }
  function fileFeedback(message,isError=false){
    const text=document.querySelector('#brand-template-feedback');
    if(text){text.textContent=message;text.classList.toggle('brand-template-error',isError);}
  }
  function updateInstallButton(){
    const button=document.querySelector('#brand-install-button');
    const checkbox=document.querySelector('#brand-template-confirmed');
    if(button)button.disabled=!(selectedReference&&referenceFits&&checkbox?.checked);
  }
  function memberForm(m){
    const item=m||{};
    modal(m?'Editar colaborador':'Adicionar colaborador',
      '<form id="member-form" '+(m?'data-id="'+m.id+'"':'')+'><div class="fields">'+
      field('Nome completo *','name',item.name||'','text','required minlength="2" maxlength="120"')+
      field('Cargo / função','role',item.role||'Equipe','text','maxlength="120"')+
      field('WhatsApp','whatsapp',item.whatsapp||'','tel','maxlength="40" placeholder="(34) 99999-9999"')+
      field('E-mail (opcional)','email',item.email||'','email','maxlength="200"')+
      field('Cidade / UF','city',item.city??'Patos de Minas - MG','text','maxlength="120"')+
      field('Site','site',item.site??site,'url','maxlength="250" placeholder="https://..."')+
      '</div><p class="member-brand-hint">O cartão e a assinatura utilizam estes dados. Não é preciso cadastrar uma conta de login para gerar os materiais.</p>'+
      '<div class="form-actions"><span></span><div class="right"><button type="button" class="secondary" data-action="close-modal">Cancelar</button>'+
      '<button type="submit" class="primary">'+(m?'Salvar colaborador':'Cadastrar colaborador')+'</button></div></div></form>');
  }
  function artUrl(id,kind,format='png'){
    return '/api/members/'+encodeURIComponent(String(id))+'/brand/'+encodeURIComponent(kind)+'?format='+encodeURIComponent(format);
  }
  function previewImage(id,kind,alt){
    const url=artUrl(id,kind);
    return '<div class="brand-preview-media" data-brand-media="'+kind+'">'+
      '<p class="brand-image-progress" role="status">Carregando prévia...</p>'+
      '<img loading="eager" decoding="async" data-brand-image="'+kind+'" src="'+url+'" alt="'+html(alt)+'">'+
      '<div class="brand-image-error" hidden><p>Não foi possível carregar esta imagem. Tente novamente sem sair da tela.</p>'+
      '<button type="button" class="secondary" data-brand-action="retry-image">Tentar novamente</button></div></div>';
  }
  function retryImage(image){
    const media=image?.closest('[data-brand-media]');
    if(!media)return;
    const progress=media.querySelector('.brand-image-progress');
    const error=media.querySelector('.brand-image-error');
    if(progress){progress.hidden=false;progress.textContent='Recarregando prévia...';}
    if(error)error.hidden=true;
    image.classList.remove('brand-image-loaded');
    image.dataset.retryCount=String(Number(image.dataset.retryCount||0)+1);
    // Apenas falhas usam URL única; tentativas normais continuam usando o cache.
    const url=new URL(image.getAttribute('src'),location.href);
    url.searchParams.set('retry',String(Date.now()));
    image.src=url.pathname+url.search;
  }
  function preview(id){
    const member=state.members.find(m=>m.id===id);
    if(!member)return;
    modal('Materiais de identidade — '+member.name,
      '<div class="brand-kit-preview"><p class="member-brand-hint">'+
      (referenceReady?'Modelo personalizado ativo para '+html(state.organization?.name||'esta organização')+'.':
        'Modelo padrão ATRIA usando automaticamente a logo, as cores e os dados desta organização.')+
      '<div class="brand-kit-block"><h3>Assinatura de e-mail</h3>'+
      previewImage(id,'signature','Prévia da assinatura de '+member.name)+
      '<div class="brand-kit-downloads"><button class="secondary" type="button" data-brand-action="download" data-id="'+id+'" data-kind="signature" data-format="png">Baixar PNG</button>'+
      '<button class="secondary" type="button" data-brand-action="download" data-id="'+id+'" data-kind="signature" data-format="html">Baixar HTML</button></div></div>'+
      '<div class="brand-kit-block"><h3>Cartão de visita · frente</h3>'+
      previewImage(id,'front','Prévia da frente do cartão de '+member.name)+
      '</div><div class="brand-kit-block"><h3>Cartão de visita · verso</h3>'+
      previewImage(id,'back','Prévia do verso do cartão de '+member.name)+
      '</div><div class="brand-kit-downloads">'+
      '<button class="primary" type="button" data-brand-action="download" data-id="'+id+'" data-kind="card" data-format="pdf">'+icon('download')+' Cartão PDF para gráfica</button>'+
      '<button class="secondary" type="button" data-brand-action="download" data-id="'+id+'" data-kind="front" data-format="png">Frente PNG</button>'+
      '<button class="secondary" type="button" data-brand-action="download" data-id="'+id+'" data-kind="back" data-format="png">Verso PNG</button></div>'+
      '<p class="member-brand-hint">O PDF contém frente e verso (90 × 50 mm + 3 mm de sangria em cada borda). Confira uma prova da gráfica antes de imprimir.</p>'+
      '<p class="member-brand-hint">O material padrão exibe somente a identidade e as informações profissionais cadastradas. Templates externos devem seguir as instruções de compatibilidade do ATRIA.</p>'+
      '</div>');
  }
  // load e error de <img> não borbulham; o terceiro argumento captura ambos.
  document.addEventListener('load',event=>{
    const image=event.target;
    if(image?.dataset?.brandImage===undefined)return;
    const media=image.closest('[data-brand-media]');
    if(!media)return;
    image.classList.add('brand-image-loaded');
    const progress=media.querySelector('.brand-image-progress');
    const error=media.querySelector('.brand-image-error');
    if(progress)progress.hidden=true;
    if(error)error.hidden=true;
  },true);
  document.addEventListener('error',event=>{
    const image=event.target;
    if(image?.dataset?.brandImage===undefined)return;
    const media=image.closest('[data-brand-media]');
    if(!media)return;
    // Uma falha transitória do Render ou da rede recebe uma tentativa automática.
    if(Number(image.dataset.retryCount||0)<1){retryImage(image);return;}
    const progress=media.querySelector('.brand-image-progress');
    const error=media.querySelector('.brand-image-error');
    if(progress)progress.hidden=true;
    if(error)error.hidden=false;
  },true);
  async function download(button){
    if(busy)return;
    busy=true;button.disabled=true;
    const id=button.dataset.id,kind=button.dataset.kind,format=button.dataset.format;
    try{
      const response=await fetch(artUrl(id,kind,format),{credentials:'same-origin',cache:'no-store'});
      if(response.status===401){location.href='/';return;}
      if(!response.ok){let detail='Não foi possível gerar o material.';try{detail=(await response.json()).detail||detail;}catch{}throw Error(detail);}
      const blob=await response.blob();
      const url=URL.createObjectURL(blob);
      const name=(state.members.find(m=>m.id===Number(id))?.name||'colaborador').normalize('NFD')
        .replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
      const prefix=(state.organization?.slug||'atria').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'atria';
      const file=document.createElement('a');
      file.href=url;file.download=prefix+'_'+name+'_'+kind+'.'+format;
      document.body.append(file);file.click();file.remove();
      setTimeout(()=>URL.revokeObjectURL(url),60000);
      notice('Material gerado e baixado.');
    }catch(e){notice(e.message);}
    finally{busy=false;button.disabled=false;}
  }
  function downloadInstructions(){
    const content=[
      'ATRIA — INSTRUÇÕES PARA CRIAÇÃO DE MODELO PERSONALIZADO',
      '',
      'Objetivo: criar uma prancha de identidade para cartão de visita e assinatura compatível com o ATRIA.',
      '',
      'ARQUIVO FINAL',
      '- Formato: PNG ou JPEG',
      '- Dimensão exata: 1536 x 1024 pixels',
      '- Tamanho máximo: 6 MB',
      '- Enviar a prancha completa, sem recortes.',
      '',
      'ÁREAS UTILIZADAS PELO APLICATIVO',
      '- Assinatura: x=786 a 1519, y=106 a 398',
      '- Frente do cartão: x=797 a 1508, y=436 a 696',
      '- Verso do cartão: x=792 a 1510, y=724 a 993',
      '',
      'INSTRUÇÃO PARA A IA',
      'Crie uma prancha de identidade visual profissional em 1536 x 1024 px. Preserve exatamente as três áreas de recorte descritas acima. A assinatura e o cartão devem usar apenas a logo da organização e as informações profissionais variáveis: nome, cargo, empresa, e-mail, site, telefone/WhatsApp e cidade quando existirem. Não inclua slogans, chamadas promocionais ou informações fixas fora dessa estrutura. O cartão deve ter leitura clara em 90 x 50 mm, prever 3 mm de sangria e manter contraste alto. A assinatura deve funcionar em fundo claro. Evite textos pequenos, efeitos excessivos e elementos essenciais nas bordas.',
      '',
      'IMPORTANTE',
      'A imagem enviada será usada como matriz. O ATRIA aplica os dados variáveis do colaborador sobre as áreas previstas. Antes de instalar, valide a prévia.',
      '',
      'Produto: ATRIA'
    ].join('\n');
    const blob=new Blob([content],{type:'text/plain;charset=utf-8'});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;a.download='ATRIA_instrucoes_modelo_personalizado.txt';
    document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),5000);
    notice('Instruções para criação do modelo baixadas.');
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-brand-action]');
    if(!button)return;
    const action=button.dataset.brandAction;
    if(action==='instructions'){downloadInstructions();return;}
    if(action==='retry-image'){
      const image=button.closest('[data-brand-media]')?.querySelector('[data-brand-image]');
      if(image)retryImage(image);
      return;
    }
    if(action==='install')installDialog();
    if(action==='restore-template'){
      if(!referenceReady)return;
      (async()=>{
        if(!await confirmAction('Voltar ao layout padrão do ATRIA para cartão e assinatura? O template personalizado será removido.','Restaurar modelo padrão','Restaurar'))return;
        try{
          await api('/brand-reference',{method:'DELETE'});
          referenceReady=false;referenceChecked=true;
          notice('Modelo padrão ATRIA restaurado.');
          render();
        }catch(error){notice(error.message)}
      })();
      return;
    }
    if(action==='new')memberForm();
    if(action==='edit')memberForm(state.members.find(m=>m.id===Number(button.dataset.id)));
    if(action==='preview')preview(Number(button.dataset.id));
    if(action==='download')download(button);
  });
  document.addEventListener('change',async event=>{
    if(event.target.id==='brand-template-confirmed'){
      updateInstallButton();return;
    }
    if(event.target.id!=='brand-template-file')return;
    const file=event.target.files?.[0];
    const preview=document.querySelector('#brand-template-preview');
    const confirmed=document.querySelector('#brand-template-confirmed');
    selectedReference='';referenceFits=false;
    if(preview){preview.hidden=true;preview.removeAttribute('src');}
    if(confirmed){confirmed.disabled=true;confirmed.checked=false;}
    updateInstallButton();
    if(!file){fileFeedback('Nenhum arquivo selecionado.');return;}
    const mime=file.type==='image/png'||/\.png$/i.test(file.name)?'image/png':
      file.type==='image/jpeg'||/\.jpe?g$/i.test(file.name)?'image/jpeg':'';
    if(!mime){fileFeedback('Escolha a imagem completa em PNG (.png) ou JPEG (.jpg/.jpeg).',true);return;}
    if(file.size>6_000_000){fileFeedback('A imagem ultrapassa 6 MB. Selecione o arquivo completo até 6 MB.',true);return;}
    fileFeedback('Lendo '+file.name+'... aguarde a prévia.');
    try{
      const result=await new Promise((resolve,reject)=>{
        const reader=new FileReader();
        reader.onload=()=>resolve(String(reader.result||''));
        reader.onerror=()=>reject(Error('Não foi possível ler a imagem.'));
        reader.readAsDataURL(file);
      });
      const encoded=result.split(',')[1];
      if(!encoded)throw Error('Não foi possível ler os dados da imagem.');
      const value='data:'+mime+';base64,'+encoded;
      const image=new Image();
      await new Promise((resolve,reject)=>{
        image.onload=resolve;
        image.onerror=()=>reject(Error('O arquivo não abriu como imagem válida.'));
        image.src=value;
      });
      if(preview){preview.src=value;preview.hidden=false;}
      if(image.naturalWidth!==1536||image.naturalHeight!==1024){
        fileFeedback('Imagem selecionada: '+file.name+' ('+image.naturalWidth+' × '+image.naturalHeight+' pixels). É necessária a imagem completa de 1536 × 1024 pixels, sem recortes.',true);
        return;
      }
      selectedReference=value;referenceFits=true;
      if(confirmed)confirmed.disabled=false;
      fileFeedback('Arquivo selecionado: '+file.name+' ('+Math.round(file.size/1024)+' KB). Confira a prancha completa, marque a confirmação e toque em “Instalar imagem aprovada”.');
      updateInstallButton();
    }catch(error){
      fileFeedback('Não foi possível visualizar: '+(error.message||'arquivo inválido'),true);
    }
  });
  document.addEventListener('submit',async event=>{
    if(event.target.id!=='brand-template-form')return;
    event.preventDefault();
    const form=event.target,button=form.querySelector('#brand-install-button');
    const confirmed=form.querySelector('#brand-template-confirmed')?.checked;
    if(!selectedReference||!referenceFits||!confirmed){
      fileFeedback('Selecione a imagem completa, confira a prévia e marque a confirmação antes de instalar.',true);
      return;
    }
    if(button){button.disabled=true;button.textContent='Instalando...';}
    fileFeedback('Enviando imagem e validando a referência...');
    try{
      await api('/brand-reference',{method:'PUT',
        body:JSON.stringify({image_data:selectedReference,confirmed:true})});
      referenceReady=true;referenceChecked=true;selectedReference='';referenceFits=false;
      closeModal();notice('Imagem instalada. Confira as prévias personalizadas antes de imprimir.');
      render();
    }catch(error){
      fileFeedback('Não foi possível instalar: '+(error?.message||'erro desconhecido')+'. Sua imagem não foi substituída.',true);
      if(button){button.disabled=false;button.textContent='Tentar instalar novamente';}
    }
  });
  return {page,memberForm};
})();
