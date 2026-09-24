/* Central de chamados internos Nexon Labs. Atendimento e histórico sem portal externo. */
'use strict';
window.NexonTickets = (() => {
  let tickets=[], loaded=false, loading=false, error='', filter='ativos', editing=null, detail=null, showEditor=false, transition=null, submitting=false;
  const statusLabels={aberto:'Aberto',em_atendimento:'Em atendimento',aguardando_cliente:'Aguardando cliente',resolvido:'Resolvido',fechado:'Fechado'};
  const typeLabels={suporte:'Suporte',erro:'Erro / incidente',melhoria:'Melhoria',solicitacao:'Solicitação'};
  const priorityLabels={baixa:'Baixa',normal:'Normal',alta:'Alta',critica:'Crítica'};
  const escape=v=>esc(v??'');
  const localDate=d=>d?new Date(d.slice(0,10)+'T12:00:00').toLocaleDateString('pt-BR'):'—';
  const when=d=>d?new Date(d).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'}):'—';
  const select=(name,values,current)=>'<select name="'+name+'">'+Object.entries(values).map(([k,label])=>'<option value="'+k+'" '+(current===k?'selected':'')+'>'+escape(label)+'</option>').join('')+'</select>';
  const labelField=(label,name,value='',type='text',extra='')=>
    '<label>'+label+'<input name="'+name+'" type="'+type+'" value="'+escape(value)+'" '+extra+'></label>';
  async function load(){
    if(loading)return;
    loading=true;
    try{tickets=await api('/tickets');error='';}
    catch(err){error=err.message;}
    finally{loaded=true;loading=false;if(route==='chamados')render();}
  }
  async function reload(){loaded=false;await load();}
  function counters(){
    return '<div class="tickets-kpis">'+[
      ['Abertos',tickets.filter(t=>t.status==='aberto').length],
      ['Em atendimento',tickets.filter(t=>t.status==='em_atendimento').length],
      ['Aguardando cliente',tickets.filter(t=>t.status==='aguardando_cliente').length],
      ['Resolvidos',tickets.filter(t=>t.status==='resolvido').length]
    ].map(([title,count])=>'<div class="tickets-kpi"><strong>'+count+'</strong><span>'+title+'</span></div>').join('')+'</div>';
  }
  function actionsBar(){
    return '<div class="tickets-filters" role="group" aria-label="Filtrar chamados">'+
      [['ativos','Ativos'],['todos','Todos'],['aberto','Abertos'],['em_atendimento','Em atendimento'],['aguardando_cliente','Aguardando cliente'],['resolvido','Resolvidos'],['fechado','Fechados']]
        .map(([value,label])=>'<button type="button" class="tab '+(filter===value?'active':'')+'" data-ticket-action="filter" data-value="'+value+'">'+label+'</button>').join('')+
      '</div>';
  }
  function ticketRow(t){
    const project=state.projects.find(p=>p.id===t.project_id);
    return '<div class="ticket-row-wrap"><button type="button" class="ticket-row" data-ticket-action="open" data-id="'+t.id+'">'+
      '<div class="ticket-row-main"><strong>'+escape(t.title)+'</strong><small>'+escape(t.number)+' · '+escape(t.client)+(project?' · '+escape(project.name):'')+'</small>'+
      '<span class="ticket-row-descr">'+escape(t.description)+'</span></div>'+
      '<div class="ticket-row-meta"><span class="ticket-status status-'+t.status+'">'+escape(statusLabels[t.status])+'</span>'+
      '<span class="ticket-priority priority-'+t.priority+'">'+escape(priorityLabels[t.priority])+'</span>'+
      '<small>Responsável: '+escape(t.assignee||'Não atribuído')+'</small>'+
      '<small>Prazo: '+localDate(t.due_at)+'</small></div></button>'+
      '<div class="ticket-row-actions">'+
      (t.status==='fechado'?'<button type="button" class="secondary" data-ticket-action="transition" data-id="'+t.id+'" data-status="aberto">Reabrir</button>':
       t.status==='resolvido'?'<button type="button" class="secondary" data-ticket-action="transition" data-id="'+t.id+'" data-status="fechado">Fechar chamado</button>':
       '<button type="button" class="secondary" data-ticket-action="transition" data-id="'+t.id+'" data-status="fechado">Concluir e fechar</button>')+
      '</div></div>';
  }
  function listing(){
    let visible=tickets.slice();
    if(filter==='ativos')visible=visible.filter(t=>!['resolvido','fechado'].includes(t.status));
    else if(filter!=='todos')visible=visible.filter(t=>t.status===filter);
    return counters()+actionsBar()+'<section class="panel ticket-list"><div class="panel-head"><h2>Solicitações registradas</h2><span class="muted">'+visible.length+' chamado(s)</span></div>'+
      '<div class="ticket-rows">'+(visible.length?visible.map(ticketRow).join(''):empty('Nenhum chamado nesse filtro','Registre um chamado ou escolha outro filtro.'))+'</div></section>';
  }
  function editor(){
    const t=editing||{},options=[['','Sem vínculo com projeto'],...state.projects.map(p=>[String(p.id),p.name])];
    return '<section class="panel ticket-editor"><div class="panel-head"><h2>'+(t.id?'Editar '+escape(t.number):'Novo chamado')+'</h2>'+
      '<button type="button" class="secondary" data-ticket-action="back">Voltar</button></div>'+
      '<form id="ticket-form"><div class="ticket-fields">'+
      labelField('Assunto *','title',t.title||'','text','required minlength="3" maxlength="180"')+
      labelField('Cliente / empresa *','client',t.client||'','text','required minlength="2" maxlength="160"')+
      labelField('Solicitante','requester',t.requester||'','text','maxlength="140"')+
      labelField('Contato','contact',t.contact||'','text','maxlength="180"')+
      '<label>Categoria'+select('type',typeLabels,t.type||'suporte')+'</label>'+
      '<label>Prioridade'+select('priority',priorityLabels,t.priority||'normal')+'</label>'+
      '<label>Situação'+select('status',statusLabels,t.status||'aberto')+'</label>'+
      labelField('Responsável','assignee',t.assignee||'','text','list="ticket-owners" maxlength="140"')+
      '<datalist id="ticket-owners">'+state.members.map(m=>'<option value="'+escape(m.name)+'"></option>').join('')+'</datalist>'+
      labelField('Prazo para atendimento','due_at',t.due_at||'','date','')+
      '<label>Projeto vinculado<select name="project_id">'+options.map(([id,name])=>
        '<option value="'+escape(id)+'" '+(String(t.project_id||'')===id?'selected':'')+'>'+escape(name)+'</option>').join('')+
      '</select></label>'+
      '<label class="ticket-full">Descrição da solicitação *<textarea name="description" required minlength="5" maxlength="6000">'+escape(t.description||'')+'</textarea></label>'+
      '</div><div class="ticket-form-actions"><button class="secondary" type="button" data-ticket-action="back">Cancelar</button>'+
      '<button type="submit" class="primary">Salvar chamado</button></div></form></section>';
  }
  function detailPage(t){
    const project=state.projects.find(p=>p.id===t.project_id);
    const events=t.events||[];
    return '<section class="panel ticket-detail"><div class="ticket-detail-top"><div><span class="muted">'+escape(t.number)+' · '+escape(typeLabels[t.type])+'</span>'+
      '<h2>'+escape(t.title)+'</h2></div><div class="ticket-detail-actions"><button type="button" class="secondary" data-ticket-action="back">Voltar</button>'+
      '<button type="button" class="secondary" data-ticket-action="edit" data-id="'+t.id+'">'+icon('edit')+' Editar</button>'+
      (t.status==='fechado'?'<button type="button" class="primary" data-ticket-action="transition" data-id="'+t.id+'" data-status="aberto">Reabrir chamado</button>':
       t.status==='resolvido'?'<button type="button" class="primary" data-ticket-action="transition" data-id="'+t.id+'" data-status="fechado">Fechar chamado</button>'+
          '<button type="button" class="secondary" data-ticket-action="transition" data-id="'+t.id+'" data-status="aberto">Reabrir</button>':
       '<button type="button" class="primary" data-ticket-action="transition" data-id="'+t.id+'" data-status="fechado">Concluir e fechar</button>')+'</div></div>'+
      '<div class="ticket-detail-tags"><span class="ticket-status status-'+t.status+'">'+escape(statusLabels[t.status])+'</span>'+
      '<span class="ticket-priority priority-'+t.priority+'">'+escape(priorityLabels[t.priority])+'</span></div>'+
      '<div class="ticket-details-grid"><div><small>Cliente</small><strong>'+escape(t.client)+'</strong></div>'+
      '<div><small>Solicitante</small><strong>'+escape(t.requester||'—')+'</strong></div>'+
      '<div><small>Contato</small><strong>'+escape(t.contact||'—')+'</strong></div>'+
      '<div><small>Responsável</small><strong>'+escape(t.assignee||'Não atribuído')+'</strong></div>'+
      '<div><small>Projeto</small><strong>'+escape(project?.name||'Não vinculado')+'</strong></div>'+
      '<div><small>Prazo</small><strong>'+localDate(t.due_at)+'</strong></div></div>'+
      '<div class="ticket-description"><h3>Descrição</h3><p>'+escape(t.description)+'</p></div>'+
      '<div class="ticket-history"><h3>Histórico de atendimento</h3>'+
      '<div class="ticket-events">'+(events.length?events.map(e=>'<div class="ticket-event"><span class="ticket-event-dot"></span>'+
        '<div><small>'+when(e.created_at)+' · '+(e.kind==='comentario'?'Registro':e.kind==='alteracao'?'Atualização':'Abertura')+'</small>'+
        '<p>'+escape(e.message)+'</p></div></div>').join(''):'<p class="muted">Nenhum registro.</p>')+'</div>'+
      '<form id="ticket-comment-form" data-ticket-id="'+t.id+'"><label>Novo registro / andamento<textarea name="message" required minlength="2" maxlength="4000" placeholder="Registre o contato com o cliente, a análise ou a solução aplicada..."></textarea></label>'+
      '<div class="ticket-form-actions"><button class="primary" type="submit">Adicionar registro</button></div></form></div></section>';
  }
  function page(){
    if(!loaded&&!loading)load();
    let content=error?'<section class="panel"><p>'+escape(error)+'</p><button class="secondary" type="button" data-ticket-action="retry">Tentar novamente</button></section>':
      !loaded?'<section class="panel"><p class="muted">Carregando chamados...</p></section>':
      showEditor?editor():detail?detailPage(tickets.find(t=>t.id===detail)||tickets[0]):listing();
    return heading('Chamados','Registre solicitações de clientes, acompanhe responsáveis, prazos e o histórico do atendimento.',
      '<button type="button" class="primary" data-ticket-action="new">'+icon('plus')+' Novo chamado</button>')+content;
  }
  document.addEventListener('click',async event=>{
    const button=event.target.closest('[data-ticket-action]');
    if(!button)return;
    const action=button.dataset.ticketAction,id=Number(button.dataset.id);
    if(action==='new'){editing=null;detail=null;showEditor=true;render();return;}
    if(action==='filter'){filter=button.dataset.value;detail=null;showEditor=false;render();return;}
    if(action==='retry'){loaded=false;error='';render();return;}
    if(action==='open'){detail=id;showEditor=false;render();return;}
    if(action==='edit'){editing=tickets.find(t=>t.id===id);showEditor=true;render();return;}
    if(action==='back'){showEditor=false;editing=null;detail=null;render();return;}
  });
  document.addEventListener('submit',async event=>{
    const form=event.target;
    if(form.id!=='ticket-form'&&form.id!=='ticket-comment-form')return;
    event.preventDefault();
    if(form.id==='ticket-form'){
      const values=Object.fromEntries(new FormData(form).entries());
      values.project_id=values.project_id?Number(values.project_id):null;
      values.due_at=values.due_at||null;
      try{
        const id=editing?.id;
        const saved=await api('/tickets'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify(values)});
        detail=saved.id;editing=null;showEditor=false;notice(id?'Chamado atualizado.':'Chamado aberto.');
        await reload();
      }catch(err){notice(err.message);}
      return;
    }
    try{
      const saved=await api('/tickets/'+Number(form.dataset.ticketId)+'/comments',{
        method:'POST',body:JSON.stringify({message:form.elements.message.value})
      });
      detail=saved.id;notice('Registro adicionado ao chamado.');await reload();
    }catch(err){notice(err.message);}
  });
  return {page,load};
})();
