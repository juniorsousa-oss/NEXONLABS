/* Cadastro e identificação por senha. Nenhuma senha aparece em listas ou em logs. */
'use strict';
window.NexonUsers = (() => {
  let accounts=[], loaded=false, loading=false, error='';
  const clean=v=>esc(v??'');
  function profile(){
    return '<section class="panel account-panel"><div class="panel-head"><h2>Meu acesso</h2></div>'+
      '<p class="muted">A senha identifica automaticamente quem acessa o sistema. Cada pessoa deve ter uma senha exclusiva.</p>'+
      '<form id="profile-form" class="account-form"><div class="account-fields">'+
      '<label>Nome exibido após o login<input name="name" required minlength="2" maxlength="120" autocomplete="name" value="'+clean(state.user||'')+'"></label>'+
      '<label>Senha atual (apenas para alterar a senha)<input name="current_password" type="password" minlength="1" maxlength="256" autocomplete="current-password" placeholder="Senha atual"></label>'+
      '<label>Nova senha (opcional)<input name="new_password" type="password" minlength="8" maxlength="256" autocomplete="new-password" placeholder="Mínimo de 8 caracteres"></label>'+
      '</div><div class="account-form-actions"><button type="submit" class="primary">Salvar meus dados</button></div></form>'+
      '<p class="account-note">Se alterar sua senha, as sessões anteriores serão encerradas. A nova senha passa a identificar somente você.</p>'+
      '</section>';
  }
  async function load(){
    if(loading||state.user_role!=='admin')return;
    loading=true;
    try{accounts=await api('/accounts');error='';loaded=true;}
    catch(err){error=err.message;}
    finally{loading=false;if(route==='configuracoes')render();}
  }
  function rows(){
    if(error)return '<p class="muted">'+clean(error)+'</p><button class="secondary" type="button" data-account-action="reload">Tentar novamente</button>';
    if(!loaded)return '<p class="muted">Carregando acessos...</p>';
    return '<div class="account-list">'+accounts.map(a=>
      '<div class="account-row"><div><strong>'+clean(a.name)+'</strong><small>'+clean(a.role==='admin'?'Administrador':'Usuário')+
      ' · '+(a.active?'Ativo':'Desativado')+(a.id===state.user_id?' · Você':'')+'</small></div>'+
      '<button type="button" class="secondary" data-account-action="edit" data-id="'+a.id+'">Gerenciar</button></div>').join('')+'</div>';
  }
  function admin(){
    if(!loaded&&!loading)load();
    return '<section class="panel account-panel"><div class="panel-head"><h2>Usuários e permissões</h2>'+
      '<button type="button" class="primary" data-account-action="new">'+icon('plus')+' Novo usuário</button></div>'+
      '<p class="muted">Cadastre uma senha diferente para cada pessoa. O nome aparece automaticamente quando ela entra. Somente administradores gerenciam acessos.</p>'+
      rows()+'</section>';
  }
  function panel(){return '<div class="accounts-layout">'+profile()+(state.user_role==='admin'?admin():'')+'</div>';}
  function createForm(){
    modal('Cadastrar usuário','<form id="account-create-form" class="account-form"><div class="fields">'+
      field('Nome *','name','','text','required minlength="2" maxlength="120" autocomplete="off"')+
      field('Senha exclusiva *','password','','password','required minlength="8" maxlength="256" autocomplete="new-password"')+
      selectField('Permissão','role',[['usuario','Usuário'],['admin','Administrador']],'usuario')+
      '</div><p class="account-note">Informe a senha por um canal privado. Não compartilhe a senha do administrador.</p>'+
      '<div class="form-actions"><button class="secondary" type="button" data-action="close-modal">Cancelar</button>'+
      '<button class="primary" type="submit">Criar acesso</button></div></form>');
  }
  function editForm(a){
    modal('Gerenciar acesso','<form id="account-edit-form" data-account-id="'+a.id+'" class="account-form"><div class="fields">'+
      field('Nome *','name',a.name,'text','required minlength="2" maxlength="120"')+
      selectField('Permissão','role',[['usuario','Usuário'],['admin','Administrador']],a.role)+
      selectField('Situação','active',[['true','Ativo'],['false','Desativado']],String(a.active))+
      field('Redefinir senha (opcional)','new_password','','password','minlength="8" maxlength="256" autocomplete="new-password" placeholder="Deixe em branco para manter a atual"')+
      '</div><p class="account-note">Desativar a conta ou alterar a senha encerra as sessões antigas. A conta não poderá entrar enquanto estiver desativada.</p>'+
      '<div class="form-actions"><button class="secondary" type="button" data-action="close-modal">Cancelar</button>'+
      '<button class="primary" type="submit">Salvar acesso</button></div></form>');
  }
  document.addEventListener('click',async e=>{
    const button=e.target.closest('[data-account-action]');
    if(!button)return;
    if(button.dataset.accountAction==='new'){createForm();return;}
    if(button.dataset.accountAction==='edit'){const item=accounts.find(a=>a.id===Number(button.dataset.id));if(item)editForm(item);return;}
    if(button.dataset.accountAction==='reload'){loaded=false;error='';await load();}
  });
  document.addEventListener('submit',async e=>{
    const form=e.target;
    if(!['profile-form','account-create-form','account-edit-form'].includes(form.id))return;
    e.preventDefault();
    const values=Object.fromEntries(new FormData(form).entries());
    try{
      if(form.id==='profile-form'){
        values.current_password=values.current_password||null;
        values.new_password=values.new_password||null;
        const me=await api('/profile',{method:'PUT',body:JSON.stringify(values)});
        state.user=me.name;
        await refresh();
        notice('Seus dados de acesso foram atualizados.');
      }else if(form.id==='account-create-form'){
        await api('/accounts',{method:'POST',body:JSON.stringify(values)});
        closeModal();notice('Usuário cadastrado. A senha identifica essa pessoa no próximo acesso.');
        await load();
      }else{
        const id=Number(form.dataset.accountId);
        values.active=values.active==='true';
        values.new_password=values.new_password||null;
        const result=await api('/accounts/'+id,{method:'PUT',body:JSON.stringify(values)});
        closeModal();
        if(id===state.user_id)await refresh();
        notice(result.active?'Acesso atualizado.':'Acesso desativado.');
        await load();
      }
    }catch(err){notice(err.message);}
  });
  return {panel,load};
})();
