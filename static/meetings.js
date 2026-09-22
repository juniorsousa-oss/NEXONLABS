/* Calendário de reuniões Nexon Labs — módulo funcional, independente do cronograma. */
'use strict';
window.NexonMeetings = (() => {
  let month = new Date(), selected = null;
  month = new Date(month.getFullYear(), month.getMonth(), 1);
  const text = value => esc(value ?? '');
  const pad = n => String(n).padStart(2,'0');
  const iso = d => [d.getFullYear(),pad(d.getMonth()+1),pad(d.getDate())].join('-');
  const display = d => new Date(d+'T12:00:00').toLocaleDateString('pt-BR');
  const label = d => d.toLocaleDateString('pt-BR',{month:'long',year:'numeric'});
  const all = () => state.meetings || [];
  const row = m => '<div class="meeting-entry"><div class="date-box"><b>'+display(m.meeting_date).slice(0,2)+'</b><small>'+new Date(m.meeting_date+'T12:00:00').toLocaleDateString('pt-BR',{month:'short'}).replace('.','').toUpperCase()+'</small></div><div class="meeting-copy"><strong>'+text(m.title)+'</strong><small>'+text(m.start_time+'–'+m.end_time)+' · '+text(m.client||'Cliente não informado')+(m.location?' · '+text(m.location):'')+'</small></div><button class="secondary" type="button" data-meeting-action="edit" data-id="'+m.id+'">Editar</button></div>';
  function page(){
    const yyyy=month.getFullYear(),mm=month.getMonth(),first=new Date(yyyy,mm,1),offset=(first.getDay()+6)%7,length=new Date(yyyy,mm+1,0).getDate(),today=iso(new Date());
    const meetings=all().slice().sort((a,b)=>(a.meeting_date+a.start_time).localeCompare(b.meeting_date+b.start_time));
    let calendar='<div class="meeting-weekdays">'+['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'].map(d=>'<span>'+d+'</span>').join('')+'</div><div class="meeting-calendar">';
    for(let i=0;i<offset;i++) calendar+='<span class="meeting-blank" aria-hidden="true"></span>';
    for(let day=1;day<=length;day++){
      const d=yyyy+'-'+pad(mm+1)+'-'+pad(day),items=meetings.filter(m=>m.meeting_date===d);
      calendar+='<button type="button" class="meeting-day'+(d===today?' today':'')+'" data-meeting-action="new" data-date="'+d+'" aria-label="Agendar reunião para '+display(d)+'"><span class="meeting-number">'+day+'</span>'+items.slice(0,2).map(m=>'<span class="meeting-dot" title="'+text(m.title)+'">'+text(m.start_time+' '+m.title)+'</span>').join('')+(items.length>2?'<span class="meeting-more">+'+(items.length-2)+' reuniões</span>':'')+'</button>';
    }
    calendar+='</div>';
    const upcoming=meetings.filter(m=>m.meeting_date>=today).slice(0,8);
    return heading('Reuniões','Agenda de encontros com clientes, separada do cronograma de projetos.','<button class="primary" data-meeting-action="new">'+icon('plus')+' Nova reunião</button>')+
      '<div class="meeting-layout"><section class="panel"><div class="meeting-toolbar"><div><h2>Calendário de reuniões</h2><p class="muted">Selecione um dia para agendar um compromisso.</p></div><div class="meeting-month"><button type="button" class="secondary" data-meeting-action="prev" aria-label="Mês anterior">'+icon('chevron-left')+'</button><strong>'+text(label(month))+'</strong><button type="button" class="secondary" data-meeting-action="next" aria-label="Próximo mês">'+icon('chevron-right')+'</button></div></div>'+calendar+'</section><section class="panel"><div class="panel-head"><h2>Próximas reuniões</h2><span class="muted">'+upcoming.length+' agendadas</span></div><div class="meeting-agenda">'+(upcoming.length?upcoming.map(row).join(''):empty('Nenhuma reunião agendada','Clique em Nova reunião ou selecione uma data no calendário.'))+'</div></section></div>'+
      '<section class="panel meeting-all"><div class="panel-head"><h2>Todas as reuniões</h2><span class="muted">'+meetings.length+' registros</span></div><div class="meeting-agenda">'+(meetings.length?meetings.map(row).join(''):empty('Agenda vazia','Cadastre reuniões com clientes para visualizá-las aqui.'))+'</div></section>';
  }
  function form(existing,date){
    selected=existing?.id||null;
    const d=date||existing?.meeting_date||iso(new Date()), options=[['','Sem projeto vinculado']].concat(state.projects.map(p=>[String(p.id),p.name]));
    modal(existing?'Editar reunião':'Agendar reunião','<form id="meeting-form"><div class="fields">'+
      field('Título da reunião *','title',existing?.title||'','text','required minlength="2" maxlength="180"')+
      field('Cliente / empresa','client',existing?.client||'','text','maxlength="160"')+
      selectField('Projeto relacionado','project_id',options,existing?.project_id?String(existing.project_id):'')+
      field('Data *','meeting_date',d,'date','required')+
      field('Início *','start_time',existing?.start_time||'09:00','time','required')+
      field('Término *','end_time',existing?.end_time||'10:00','time','required')+
      field('Local / modalidade','location',existing?.location||'','text','placeholder="Online, presencial, endereço..." maxlength="250"')+
      field('Link da reunião','meeting_url',existing?.meeting_url||'','url','placeholder="https://..." maxlength="500"')+
      '<label class="full">Pauta e observações<textarea name="notes" maxlength="4000">'+text(existing?.notes||'')+'</textarea></label></div>'+
      '<div class="form-actions">'+(existing?'<button class="danger" type="button" data-meeting-action="delete" data-id="'+existing.id+'">'+icon('trash')+' Excluir</button>':'<span class="hint">* Campo obrigatório</span>')+
      '<div class="right"><button class="secondary" type="button" data-action="close-modal">Cancelar</button><button class="primary" type="submit">Salvar reunião</button></div></div></form>');
  }
  document.addEventListener('click',async e=>{
    const control=e.target.closest('[data-meeting-action]');
    if(!control)return;
    const action=control.dataset.meetingAction;
    if(action==='prev'||action==='next'){month=new Date(month.getFullYear(),month.getMonth()+(action==='next'?1:-1),1);render();return;}
    if(action==='new'){form(null,control.dataset.date);return;}
    if(action==='edit'){form(all().find(m=>m.id===Number(control.dataset.id)));return;}
    if(action==='delete' && confirm('Excluir este agendamento de reunião?')) {
      try {await api('/meetings/'+Number(control.dataset.id),{method:'DELETE'});closeModal();await refresh();notice('Reunião excluída.');}
      catch(error){notice(error.message);}
    }
  });
  document.addEventListener('submit',async e=>{
    if(e.target.id!=='meeting-form')return;
    e.preventDefault();
    const values=Object.fromEntries(new FormData(e.target).entries()),id=selected;
    values.project_id=values.project_id?Number(values.project_id):null;
    if(values.end_time<=values.start_time){notice('O horário de término deve ser posterior ao de início.');return;}
    try {
      await api('/meetings'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify(values)});
      closeModal();await refresh();notice(id?'Reunião atualizada.':'Reunião agendada.');
    }catch(error){notice(error.message);}
  });
  return {page};
})();
