/* Materiais de identidade — template Opção B aprovado, integrado em Equipe > Colaboradores.
   Nenhuma alteração na identidade principal ou na página de Usuários. */
'use strict';
window.NexonBrandUI=(()=>{
  const html=v=>esc(v??'');
  const site='https://nexonlabs.onrender.com';
  let busy=false,referenceReady=false,referenceChecked=false,referenceLoading=false;
  async function checkReference(){
    if(referenceLoading)return;
    referenceLoading=true;
    try{
      const response=await api('/brand-reference/status');
      referenceReady=Boolean(response.installed);referenceChecked=true;
    }catch(e){referenceChecked=true;notice(e.message);}
    finally{referenceLoading=false;if(typeof route!=='undefined'&&route==='equipe'&&typeof render==='function')render();}
  }
  function avatar(member){return html(initials(member.name))}
  function page(){
    if(!referenceChecked&&!referenceLoading)checkReference();
    return heading('Equipe','Colaboradores, dados profissionais e materiais da Nexon Labs.',
      '<button type="button" class="primary" data-brand-action="new">'+icon('plus')+' Adicionar colaborador</button>')+
      (!referenceChecked?'<section class="panel"><p class="muted">Verificando o modelo visual aprovado...</p></section>':
       !referenceReady?'<section class="panel brand-template-warning"><h2>Matriz visual Opção B pendente</h2>'+
        '<p>Para preservar a arte original, a geração é liberada apenas após a instalação da imagem aprovada.</p>'+
        (state.user_role==='admin'?'<button type="button" class="primary" data-brand-action="install">Instalar matriz visual aprovada</button>':
         '<p>Peça ao administrador para instalar a referência aprovada.</p>')+'</section>':'')+
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
        '<button type="button" class="primary" data-brand-action="preview" data-id="'+m.id+'" '+(!referenceReady?'disabled title="Aguarde a instalação da matriz aprovada"':'')+'>'+icon('file')+' Cartão e assinatura</button>'+
        '<button type="button" class="danger" data-action="delete-member" data-id="'+m.id+'">Remover</button>'+
        '</div></div>').join(''):
        empty('Equipe ainda não cadastrada','Adicione os colaboradores para gerar materiais personalizados.','new-member'))+
      '</div></section>';
  }
  function installDialog(){
    modal('Instalar matriz visual Opção B',
      '<div class="brand-template-install"><p>A imagem original aprovada será verificada antes de ativar as prévias.</p>'+
      '<label>Imagem original com as duas opções (JPEG)<input type="file" id="brand-template-file" accept="image/jpeg" required></label>'+
      '<p class="member-brand-hint">Use a imagem completa como foi aprovada, sem recortar, alterar ou comprimir o arquivo.</p>'+
      '<div class="form-actions"><button type="button" class="secondary" data-action="close-modal">Cancelar</button></div></div>');
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
  function preview(id){
    const member=state.members.find(m=>m.id===id);
    if(!member)return;
    if(!referenceReady){notice('Instale o modelo original aprovado para liberar a geração.');return;}
    modal('Materiais de identidade — '+member.name,
      '<div class="brand-kit-preview"><p class="member-brand-hint">'+
      'Modelo Opção B aprovado: assinatura com bloco azul-marinho e diagonal turquesa; cartão escuro na frente, cartão claro no verso com QR Code e serviços à direita.</p>'+
      '<div class="brand-kit-block"><h3>Assinatura de e-mail</h3>'+
      '<img loading="lazy" src="'+artUrl(id,'signature')+'" alt="Prévia da assinatura de '+html(member.name)+'">'+
      '<div class="brand-kit-downloads"><button class="secondary" type="button" data-brand-action="download" data-id="'+id+'" data-kind="signature" data-format="png">Baixar PNG</button>'+
      '<button class="secondary" type="button" data-brand-action="download" data-id="'+id+'" data-kind="signature" data-format="html">Baixar HTML</button></div></div>'+
      '<div class="brand-kit-block"><h3>Cartão de visita · frente</h3>'+
      '<img loading="lazy" src="'+artUrl(id,'front')+'" alt="Prévia da frente do cartão">'+
      '</div><div class="brand-kit-block"><h3>Cartão de visita · verso</h3>'+
      '<img loading="lazy" src="'+artUrl(id,'back')+'" alt="Prévia do verso personalizado do cartão">'+
      '</div><div class="brand-kit-downloads">'+
      '<button class="primary" type="button" data-brand-action="download" data-id="'+id+'" data-kind="card" data-format="pdf">'+icon('download')+' Cartão PDF para gráfica</button>'+
      '<button class="secondary" type="button" data-brand-action="download" data-id="'+id+'" data-kind="front" data-format="png">Frente PNG</button>'+
      '<button class="secondary" type="button" data-brand-action="download" data-id="'+id+'" data-kind="back" data-format="png">Verso PNG</button></div>'+
      '<p class="member-brand-hint">O PDF contém frente e verso (90 × 50 mm + 3 mm de sangria em cada borda). Confira uma prova da gráfica antes de imprimir.</p>'+
      '<p class="member-brand-hint">O QR Code aponta para o site cadastrado. Se o endereço for o do app Nexon Labs, visitantes verão a tela de login, não uma página pública de apresentação.</p>'+
      '</div>');
  }
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
      const file=document.createElement('a');
      file.href=url;file.download='nexonlabs_'+name+'_'+kind+'.'+format;
      document.body.append(file);file.click();file.remove();
      setTimeout(()=>URL.revokeObjectURL(url),60000);
      notice('Material gerado e baixado.');
    }catch(e){notice(e.message);}
    finally{busy=false;button.disabled=false;}
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-brand-action]');
    if(!button)return;
    const action=button.dataset.brandAction;
    if(action==='install')installDialog();
    if(action==='new')memberForm();
    if(action==='edit')memberForm(state.members.find(m=>m.id===Number(button.dataset.id)));
    if(action==='preview')preview(Number(button.dataset.id));
    if(action==='download')download(button);
  });
  document.addEventListener('change',async event=>{
    if(event.target.id!=='brand-template-file')return;
    const input=event.target,file=input.files?.[0];
    if(!file)return;
    if(file.type!=='image/jpeg'||file.size>1_200_000){
      notice('Use a imagem JPEG original aprovada com até 1,2 MB.');input.value='';return;
    }
    input.disabled=true;
    try{
      const image_data=await new Promise((resolve,reject)=>{
        const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));
        reader.onerror=()=>reject(Error('Não foi possível ler o arquivo.'));reader.readAsDataURL(file);
      });
      await api('/brand-reference',{method:'PUT',body:JSON.stringify({image_data})});
      referenceReady=true;referenceChecked=true;
      closeModal();notice('Matriz original validada e instalada. As prévias usam a arte aprovada.');render();
    }catch(error){notice(error.message);input.value='';input.disabled=false;}
  });
  return {page,memberForm};
})();
