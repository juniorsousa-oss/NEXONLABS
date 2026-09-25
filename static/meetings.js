/* Calendário de reuniões Nexon Labs — módulo funcional, independente do cronograma. */
'use strict';
window.NexonMeetings = (() => {
  let month = new Date(), selected = null, saving = false;
  month = new Date(month.getFullYear(), month.getMonth(), 1);
  const text = value => esc(value ?? '');
  const pad = n => String(n).padStart(2,'0');
  const iso = d => [d.getFullYear(),pad(d.getMonth()+1),pad(d.getDate())].join('-');
  const display = d => new Date(d+'T12:00:00').toLocaleDateString('pt-BR');
  const label = d => d.toLocaleDateString('pt-BR',{month:'long',year:'numeric'});
  const all = () => state.meetings || [];
  const statusLabels={agendada:'Agendada',realizada:'Realizada',cancelada:'Cancelada'};
  const conflictText=m=>{
    if(!m?.has_conflict)return '';
    const people=[...new Set((m.conflicts||[]).flatMap(c=>c.attendee_names||[]))];
    const details=(m.conflicts||[]).map(c=>(c.attendee_names||[]).join(', ')+' · '+c.start_time+'–'+c.end_time+' · '+c.title);
    return 'Conflito de agenda'+(people.length?' com '+people.join(', '):'')+(details.length?': '+details.join('; '):'.');
  };
  function localConflicts(date,start,end,attendeeIds,excludeId=null){
    if(!date||!start||!end||!attendeeIds.length||end<=start)return [];
    const chosen=new Set(attendeeIds.map(Number));
    return all().filter(m=>
      m.id!==excludeId&&m.status!=='cancelada'&&m.meeting_date===date&&
      m.start_time<end&&m.end_time>start&&
      (m.attendee_ids||[]).some(id=>chosen.has(Number(id)))
    ).map(m=>{
      const shared=(m.attendee_ids||[]).filter(id=>chosen.has(Number(id)));
      const names=state.members.filter(member=>shared.includes(member.id)).map(member=>member.name);
      return {meeting_id:m.id,title:m.title,start_time:m.start_time,end_time:m.end_time,attendee_names:names};
    });
  }
  function durationMinutes(form){
    const raw=form?.elements?.duration?.value||'60';
    return Math.max(15,Number(raw)||60);
  }
  function addMinutes(time,minutes){
    const [h,m]=String(time||'00:00').split(':').map(Number);
    const total=h*60+m+minutes;
    if(total>=24*60)return null;
    return pad(Math.floor(total/60))+':'+pad(total%60);
  }
  function syncMeetingEnd(form){
    if(!form)return '';
    const end=addMinutes(form.elements.start_time?.value||'',durationMinutes(form));
    const hidden=form.elements.end_time;
    if(hidden)hidden.value=end||'';
    const preview=form.querySelector('#meeting-end-preview');
    if(preview)preview.textContent=end?'Término previsto: '+end:'A duração ultrapassa o fim do dia.';
    return end||'';
  }
  function syncMeetingMode(form){
    if(!form)return;
    const mode=form.elements.meeting_mode?.value||'presencial';
    const local=form.querySelector('[data-meeting-local]');
    const link=form.querySelector('[data-meeting-link]');
    if(local)local.hidden=mode!=='presencial';
    if(link)link.hidden=mode!=='online';
  }
  function renderConflictPreview(form){
    const box=form?.querySelector?.('#meeting-conflict-preview');
    if(!box)return;
    const ids=[...form.querySelectorAll('input[name="attendee_ids"]:checked')].map(input=>Number(input.value));
    const date=form.elements.meeting_date?.value||'',start=form.elements.start_time?.value||'',end=syncMeetingEnd(form);
    const conflicts=localConflicts(date,start,end,ids,selected);
    if(!ids.length){
      box.className='meeting-conflict-preview is-required';
      box.textContent='Selecione pelo menos um colaborador da Nexon Labs para participar.';
      return;
    }
    if(!conflicts.length){
      box.className='meeting-conflict-preview is-clear';
      box.textContent='✓ Horário disponível para todos os participantes.';
      return;
    }
    box.className='meeting-conflict-preview has-conflict';
    box.innerHTML='<strong>Conflito de agenda identificado.</strong><span>'+
      conflicts.map(c=>text((c.attendee_names||[]).join(', ')+' · '+c.start_time+'–'+c.end_time+' · '+c.title)).join('</span><span>')+
      '</span><small>O agendamento pode ser salvo, mas o conflito precisa ser tratado.</small>';
  }
  const row = m => '<div class="meeting-entry'+(m.has_conflict?' has-conflict':'')+'"><div class="date-box"><b>'+display(m.meeting_date).slice(0,2)+
    '</b><small>'+new Date(m.meeting_date+'T12:00:00').toLocaleDateString('pt-BR',{month:'short'}).replace('.','').toUpperCase()+
    '</small></div><div class="meeting-copy"><div class="meeting-title-line"><strong>'+text(m.title)+'</strong>'+
    (m.has_conflict?'<span class="meeting-conflict-badge">CONFLITO</span>':'')+'</div><small>'+text(m.start_time+'–'+m.end_time)+
    ' · '+text(m.client||'Cliente não informado')+(m.location?' · '+text(m.location):'')+'</small>'+
    '<small><b>Participantes:</b> '+text((m.attendee_names||[]).join(', ')||'Não informado')+'</small>'+
    (m.has_conflict?'<small class="meeting-conflict-copy">'+text(conflictText(m))+'</small>':'')+
    '<small class="meeting-status meeting-status-'+m.status+'">'+text(statusLabels[m.status]||'Agendada')+
    (m.closure_note?' · '+text(m.closure_note):'')+'</small></div>'+
    '<div class="meeting-actions"><button class="secondary" type="button" data-meeting-action="edit" data-id="'+m.id+'">Editar</button>'+
    (m.status==='agendada'?'<button class="primary" type="button" data-meeting-action="outcome" data-status="realizada" data-id="'+m.id+'">Concluir</button>'+
      '<button class="secondary" type="button" data-meeting-action="outcome" data-status="cancelada" data-id="'+m.id+'">Cancelar</button>':
      '<button class="secondary" type="button" data-meeting-action="outcome" data-status="agendada" data-id="'+m.id+'">Reabrir</button>')+
    '</div></div>';
  function page(){
    const yyyy=month.getFullYear(),mm=month.getMonth(),first=new Date(yyyy,mm,1),offset=(first.getDay()+6)%7,length=new Date(yyyy,mm+1,0).getDate(),today=iso(new Date());
    const meetings=all().slice().sort((a,b)=>(a.meeting_date+a.start_time).localeCompare(b.meeting_date+b.start_time));
    let calendar='<div class="meeting-weekdays">'+['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'].map(d=>'<span>'+d+'</span>').join('')+'</div><div class="meeting-calendar">';
    for(let i=0;i<offset;i++) calendar+='<span class="meeting-blank" aria-hidden="true"></span>';
    for(let day=1;day<=length;day++){
      const d=yyyy+'-'+pad(mm+1)+'-'+pad(day),items=meetings.filter(m=>m.meeting_date===d),dayConflict=items.some(m=>m.has_conflict&&m.status!=='cancelada');
      calendar+='<button type="button" class="meeting-day'+(d===today?' today':'')+(dayConflict?' has-conflict':'')+'" data-meeting-action="new" data-date="'+d+'" aria-label="Agendar reunião para '+display(d)+(dayConflict?' — há conflito de agenda':'')+'"><span class="meeting-number">'+day+'</span>'+
        (dayConflict?'<span class="meeting-day-alert">CONFLITO</span>':'')+
        items.slice(0,2).map(m=>'<span class="meeting-dot'+(m.has_conflict?' has-conflict':'')+'" title="'+text(m.has_conflict?conflictText(m):m.title)+'">'+text(m.start_time+' '+m.title)+'</span>').join('')+
        (items.length>2?'<span class="meeting-more">+'+(items.length-2)+' reuniões</span>':'')+'</button>';
    }
    calendar+='</div>';
    const upcoming=meetings.filter(m=>m.meeting_date>=today&&m.status==='agendada').slice(0,8);
    return heading('Reuniões','Agenda de encontros com clientes, separada do cronograma de projetos.','<button class="primary" data-meeting-action="new">'+icon('plus')+' Nova reunião</button>')+
      '<div class="meeting-layout"><section class="panel"><div class="meeting-toolbar"><div><h2>Calendário de reuniões</h2><p class="muted">Selecione um dia para agendar um compromisso.</p></div><div class="meeting-month"><button type="button" class="secondary" data-meeting-action="prev" aria-label="Mês anterior">'+icon('chevron-left')+'</button><strong>'+text(label(month))+'</strong><button type="button" class="secondary" data-meeting-action="next" aria-label="Próximo mês">'+icon('chevron-right')+'</button></div></div>'+calendar+'</section><section class="panel"><div class="panel-head"><h2>Próximas reuniões</h2><span class="muted">'+upcoming.length+' agendadas</span></div><div class="meeting-agenda">'+(upcoming.length?upcoming.map(row).join(''):empty('Nenhuma reunião agendada','Clique em Nova reunião ou selecione uma data no calendário.'))+'</div></section></div>'+
      '<section class="panel meeting-all"><div class="panel-head"><h2>Todas as reuniões</h2><span class="muted">'+meetings.length+' registros</span></div><div class="meeting-agenda">'+(meetings.length?meetings.map(row).join(''):empty('Agenda vazia','Cadastre reuniões com clientes para visualizá-las aqui.'))+'</div></section>';
  }
  function form(existing,date){
    saving=false;
    selected=existing?.id||null;
    const d=date||existing?.meeting_date||iso(new Date());
    const options=[['','Sem projeto vinculado']].concat(state.projects.map(p=>[String(p.id),p.name]));
    const selectedIds=new Set((existing?.attendee_ids||[]).map(Number));
    const start=existing?.start_time||'09:00';
    const toMinutes=t=>{const [h,m]=String(t||'').split(':').map(Number);return h*60+m;};
    const existingDuration=existing?.end_time&&existing?.start_time?Math.max(15,toMinutes(existing.end_time)-toMinutes(existing.start_time)):60;
    const durationOptions=[15,30,45,60,90,120];
    const durationValue=durationOptions.includes(existingDuration)?existingDuration:60;
    const inferredOnline=!!existing?.meeting_url || String(existing?.location||'').toLowerCase()==='online';
    const mode=inferredOnline?'online':'presencial';
    const attendees=state.members.length?
      '<fieldset class="meeting-attendees full"><legend>Colaboradores participantes *</legend><div class="meeting-attendee-grid">'+
      state.members.map(member=>'<label class="meeting-attendee-option"><input type="checkbox" name="attendee_ids" value="'+member.id+'" '+(selectedIds.has(member.id)?'checked':'')+'><span class="meeting-check" aria-hidden="true">✓</span><span class="meeting-person"><b>'+text(member.name)+'</b><small>'+text(member.role||'Colaborador')+'</small></span></label>').join('')+
      '</div></fieldset>':
      '<div class="meeting-attendees-empty full">Cadastre pelo menos um colaborador em Equipe antes de agendar reuniões.</div>';
    modal(existing?'Editar reunião':'Agendar reunião','<form id="meeting-form"><div class="fields meeting-form-grid">'+
      '<div class="full">'+field('Título da reunião *','title',existing?.title||'','text','required minlength="2" maxlength="180"')+'</div>'+
      '<div>'+field('Cliente / empresa','client',existing?.client||'','text','maxlength="160"')+'</div>'+
      '<div>'+selectField('Projeto relacionado','project_id',options,existing?.project_id?String(existing.project_id):'')+'</div>'+
      '<div class="meeting-schedule full">'+
        '<label>Data *<input name="meeting_date" type="date" required value="'+text(d)+'"></label>'+
        '<label>Início *<input name="start_time" type="time" required value="'+text(start)+'"></label>'+
        '<label>Duração<select name="duration">'+durationOptions.map(min=>'<option value="'+min+'" '+(durationValue===min?'selected':'')+'>'+(min<60?min+' min':min===60?'1 hora':min===90?'1h30':'2 horas')+'</option>').join('')+'</select></label>'+
        '<input type="hidden" name="end_time" value="'+text(existing?.end_time||'')+'">'+
        '<small id="meeting-end-preview" class="meeting-end-preview"></small>'+
      '</div>'+
      '<div class="meeting-mode full"><span class="meeting-field-title">Modalidade</span><div class="meeting-mode-options">'+
        '<label><input type="radio" name="meeting_mode" value="presencial" '+(mode==='presencial'?'checked':'')+'><span>Presencial</span></label>'+
        '<label><input type="radio" name="meeting_mode" value="online" '+(mode==='online'?'checked':'')+'><span>Online</span></label>'+
      '</div></div>'+
      '<label class="full" data-meeting-local>Local / endereço<input name="location" type="text" value="'+text(mode==='presencial'?(existing?.location||''):'')+'" placeholder="Informe o local da reunião" maxlength="250"></label>'+
      '<label class="full" data-meeting-link>Link da reunião<input name="meeting_url" type="url" value="'+text(existing?.meeting_url||'')+'" placeholder="https://..." maxlength="500"></label>'+
      attendees+
      '<div id="meeting-conflict-preview" class="meeting-conflict-preview full" role="status" aria-live="polite"></div>'+
      '<label class="full">Pauta e observações<textarea name="notes" maxlength="4000" rows="3">'+text(existing?.notes||'')+'</textarea></label></div>'+
      '<div class="form-actions">'+(existing?'<button class="danger" type="button" data-meeting-action="delete" data-id="'+existing.id+'">'+icon('trash')+' Excluir</button>':'<span class="hint">* Campo obrigatório</span>')+
      '<div class="right"><button class="secondary" type="button" data-action="close-modal">Cancelar</button><button class="primary" type="submit" '+(!state.members.length?'disabled':'')+'>Salvar reunião</button></div></div></form>');
    const current=document.querySelector('#meeting-form');
    if(current){syncMeetingMode(current);syncMeetingEnd(current);renderConflictPreview(current);}
  }
  document.addEventListener('click',async e=>{
    const control=e.target.closest('[data-meeting-action]');
    if(!control)return;
    const action=control.dataset.meetingAction;
    if(action==='prev'||action==='next'){month=new Date(month.getFullYear(),month.getMonth()+(action==='next'?1:-1),1);render();return;}
    if(action==='outcome'){
      const m=all().find(item=>item.id===Number(control.dataset.id));
      if(!m){notice('Reunião não encontrada. Atualize a página.');return;}
      const target=control.dataset.status,labels={agendada:'Reabrir reunião',realizada:'Concluir reunião',cancelada:'Cancelar reunião'};
      modal(labels[target],
        '<form id="meeting-outcome-form" data-id="'+m.id+'" data-status="'+target+'">'+
        '<p class="muted">Registre o resultado ou o motivo. A reunião continuará no histórico.</p>'+
        '<label>Resultado / justificativa *<textarea name="note" required minlength="5" maxlength="2000" placeholder="Descreva o resultado ou o motivo da alteração..."></textarea></label>'+
        '<div class="form-actions"><span></span><div class="right"><button class="secondary" type="button" data-action="close-modal">Voltar</button>'+
        '<button class="primary" type="submit">'+labels[target]+'</button></div></div></form>');
      return;
    }
    if(action==='new'){form(null,control.dataset.date);return;}
    if(action==='edit'){form(all().find(m=>m.id===Number(control.dataset.id)));return;}
    if(action==='delete' && confirm('Excluir este agendamento de reunião?')) {
      try {await api('/meetings/'+Number(control.dataset.id),{method:'DELETE'});closeModal();await refresh();notice('Reunião excluída.');}
      catch(error){notice(error.message);}
    }
  });
  document.addEventListener('change',e=>{
    const form=e.target.closest?.('#meeting-form');
    if(!form)return;
    if(e.target.name==='meeting_mode'){syncMeetingMode(form);return;}
    if(['attendee_ids','meeting_date','start_time','duration'].includes(e.target.name)){syncMeetingEnd(form);renderConflictPreview(form);}
  });
  document.addEventListener('input',e=>{
    const form=e.target.closest?.('#meeting-form');
    if(form&&['meeting_date','start_time'].includes(e.target.name)){syncMeetingEnd(form);renderConflictPreview(form);}
  });
  document.addEventListener('submit',async e=>{
    if(e.target.id==='meeting-outcome-form'){
      e.preventDefault();
      if(saving)return;
      const form=e.target,button=form.querySelector('button[type="submit"]');
      const originalLabel=button?.textContent||'Salvar';
      saving=true;
      if(button){button.disabled=true;button.textContent='Salvando...';}
      try{
        await api('/meetings/'+Number(form.dataset.id)+'/outcome',{
          method:'POST',body:JSON.stringify({status:form.dataset.status,note:form.elements.note.value})
        });
        closeModal();
        saving=false;
        notice(form.dataset.status==='realizada'?'Reunião concluída.':
          form.dataset.status==='cancelada'?'Reunião cancelada e mantida no histórico.':'Reunião reaberta.');
        await refresh();
      }catch(error){
        saving=false;
        notice(error.message);
        if(button){button.disabled=false;button.textContent=originalLabel;}
      }
      return;
    }
    if(e.target.id!=='meeting-form')return;
    e.preventDefault();
    if(saving)return;
    const form=e.target,button=form.querySelector('button[type="submit"]');
    const formData=new FormData(form),values=Object.fromEntries(formData.entries()),id=selected;
    values.project_id=values.project_id?Number(values.project_id):null;
    values.attendee_ids=formData.getAll('attendee_ids').map(Number);
    values.end_time=syncMeetingEnd(form);
    const meetingMode=values.meeting_mode||'presencial';
    delete values.duration;
    delete values.meeting_mode;
    if(meetingMode==='online'){values.location='Online';}
    else {values.meeting_url='';}
    if(!values.attendee_ids.length){notice('Selecione pelo menos um colaborador da Nexon Labs para a reunião.');renderConflictPreview(form);return;}
    if(values.end_time<=values.start_time){notice('O horário de término deve ser posterior ao de início.');return;}
    const originalLabel=button?.textContent||'Salvar reunião';
    saving=true;
    if(button){button.disabled=true;button.textContent='Salvando...';}
    try {
      const saved=await api('/meetings'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify(values)});
      selected=null;
      closeModal();
      saving=false;
      await refresh();
      notice(saved.has_conflict?('Reunião salva com conflito. '+conflictText(saved)):(id?'Reunião atualizada.':'Reunião agendada.'));
    }catch(error){
      saving=false;
      notice(error.message);
      if(button){button.disabled=false;button.textContent=originalLabel;}
    }
  });
  return {page};
})();
