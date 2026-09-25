/* Teste de ligação dos botões/ações sem dependências de navegador externo. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function context(file,extras={}){
  const handlers={};
  const doc={
    addEventListener(name,fn){handlers[name]=fn;},
    querySelector(){return {focus(){}};}
  };
  const source=fs.readFileSync(file,'utf8');
  const obj={
    window:{},document:doc,
    esc:v=>String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;'),
    initials:name=>name.slice(0,2).toUpperCase(),
    state:{members:[],projects:[]},
    heading:()=>'',icon:()=>'',empty:()=>'',field:(label,name,value)=>'<span>'+name+':'+value+'</span>',
    modal:()=>{},notice:()=>{},render:()=>{},
    ...extras
  };
  vm.createContext(obj);vm.runInContext(source,obj,{filename:file});
  return {obj,handlers};
}

(async()=>{
  let captured=null;
  const member={id:42,name:'Júnior Andrade',role:'CEO | Diretor de Criação e Branding',
    whatsapp:'(34) 99662-1546',email:'',city:'Patos de Minas - MG',
    site:'https://nexonlabs.onrender.com'};
  const members=context('static/brand-kit.js',{
    state:{members:[member],projects:[],user_role:'admin'},route:'equipe',
    api:async()=>({installed:false}),
    modal:(title,body)=>{captured={title,body};}
  });
  const list=members.obj.window.NexonBrandUI.page();
  members.handlers.click({target:{closest:()=>({dataset:{brandAction:'install'}})}});
  assert.equal(captured.title,'Instalar modelo aprovado — Opção B');
  assert.match(captured.body,/id="brand-template-form"/);
  assert.match(captured.body,/id="brand-install-button"/);
  assert.match(captured.body,/id="brand-template-feedback"/);
  assert.match(captured.body,/\.png/);
  assert.match(captured.body,/id="brand-template-preview"/);
  assert.match(captured.body,/id="brand-template-confirmed"/);
  assert.match(list,/Editar cadastro/);
  assert.match(list,/data-brand-action="edit" data-id="42"/);
  members.handlers.click({target:{closest:()=>({dataset:{brandAction:'edit',id:'42'}})}});
  assert.equal(captured.title,'Editar colaborador');
  assert.match(captured.body,/data-id="42"/);
  assert.match(captured.body,/whatsapp:\(34\) 99662-1546/);
  assert.match(captured.body,/city:Patos de Minas - MG/);
  assert.match(captured.body,/role:CEO \| Diretor de Criação e Branding/);

  // Uma pessoa ainda não aberta não pode depender de rolar até a imagem ou
  // de atualizar a página caso o primeiro carregamento falhe.
  let previewMarkup='';
  const readyMembers=context('static/brand-kit.js',{
    state:{members:[member],projects:[],user_role:'admin'},route:'equipe',
    api:async()=>({installed:true}),
    modal:(title,body)=>{previewMarkup=body;}
  });
  readyMembers.obj.window.NexonBrandUI.page();
  // A consulta de disponibilidade da matriz conclui antes de abrir a prévia.
  await new Promise(resolve=>setImmediate(resolve));
  readyMembers.handlers.click({target:{closest:()=>({
    dataset:{brandAction:'preview',id:'42'}
  })}});
  assert.equal((previewMarkup.match(/loading="eager"/g)||[]).length,3);
  assert.match(previewMarkup,/Carregando prévia/);
  assert.match(previewMarkup,/data-brand-action="retry-image"/);
  assert.match(previewMarkup,/data-brand-image="signature"/);
  assert.match(previewMarkup,/data-brand-image="front"/);
  assert.match(previewMarkup,/data-brand-image="back"/);

  // Reunião: um toque em salvar deve gerar uma única requisição e fechar o modal
  // assim que a gravação for confirmada, sem depender do refresh da tela.
  let meetingCalls=0,meetingClosed=0,meetingRefreshes=0,releaseMeeting;
  const pendingMeeting=new Promise(resolve=>{releaseMeeting=resolve;});
  const submitButton={disabled:false,textContent:'Salvar reunião'};
  class MeetingFormData{
    entries(){return Object.entries({
      title:'Reunião com cliente',client:'Cliente A',project_id:'',
      meeting_date:'2026-10-10',start_time:'09:00',end_time:'10:00',
      location:'Online',meeting_url:'',notes:'Pauta',attendee_ids:'42'
    });}
    getAll(name){return name==='attendee_ids'?['42']:[];}
  }
  const meetings=context('static/meetings.js',{
    state:{projects:[],meetings:[],members:[member]},route:'reunioes',
    FormData:MeetingFormData,
    api:async (url,opt)=>{
      assert.equal(url,'/meetings');
      assert.equal(opt.method,'POST');
      meetingCalls++;
      await pendingMeeting;
      const body=JSON.parse(opt.body);
      assert.deepEqual(body.attendee_ids,[42]);
      return {id:91,has_conflict:false,conflicts:[],attendee_ids:[42],attendee_names:['Júnior Andrade']};
    },
    closeModal:()=>{meetingClosed++;},
    refresh:async()=>{meetingRefreshes++;},
    notice:()=>{}
  });
  let meetingPrevented=0;
  const meetingForm={
    id:'meeting-form',
    querySelector:selector=>selector==='button[type="submit"]'?submitButton:null,
    querySelectorAll:()=>[],
    elements:{
      meeting_date:{value:'2026-10-10'},start_time:{value:'09:00'},end_time:{value:'10:00'}
    }
  };
  const meetingEvent={target:meetingForm,preventDefault(){meetingPrevented++;}};
  const saveOne=meetings.handlers.submit(meetingEvent);
  const saveTwo=meetings.handlers.submit(meetingEvent);
  assert.equal(meetingCalls,1);
  assert.equal(submitButton.disabled,true);
  assert.equal(submitButton.textContent,'Salvando...');
  releaseMeeting();
  await saveOne;await saveTwo;
  assert.equal(meetingPrevented,2);
  assert.equal(meetingClosed,1);
  assert.equal(meetingRefreshes,1);
  assert.equal(meetingCalls,1);

  let ticket={id:8,number:'CH-2026-00008',title:'Erro no sistema',
    client:'Cliente A',description:'Relatório com divergência',status:'aberto',priority:'normal',
    events:[],project_id:null,assignee:'',due_at:null,requester:'',contact:'',type:'erro'};
  let displayed='',transitionCalls=0;
  const tickets=context('static/tickets.js',{
    state:{projects:[],members:[]},route:'chamados',heading:()=>'',icon:()=>'',empty:()=>'', 
    api:async (url,opt)=>{
      if(url==='/tickets')return [ticket];
      if(url==='/tickets/8/transition'){
        transitionCalls++;
        assert.equal(opt.method,'POST');
        const body=JSON.parse(opt.body);
        assert.equal(body.status,'fechado');
        assert.equal(body.message,'Corrigido e validado com o cliente.');
        ticket={...ticket,status:'fechado',closed_at:'2026-09-24T12:00:00Z'};
        return ticket;
      }
      throw Error('API inesperada '+url);
    }
  });
  tickets.obj.render=()=>{displayed=tickets.obj.window.NexonTickets.page();};
  await tickets.obj.window.NexonTickets.load();
  displayed=tickets.obj.window.NexonTickets.page();
  assert.match(displayed,/Concluir e fechar/);
  assert.match(displayed,/Marcar como resolvido/);
  await tickets.handlers.click({target:{closest:()=>({dataset:{ticketAction:'open',id:'8'}})}});
  assert.match(displayed,/Atualizar situação do chamado/);
  assert.match(displayed,/Em atendimento/);
  assert.match(displayed,/Aguardando cliente/);
  assert.match(displayed,/Marcar como resolvido/);
  assert.match(displayed,/Concluir e fechar/);
  await tickets.handlers.click({target:{closest:()=>({dataset:{ticketAction:'transition',id:'8',status:'fechado'}})}});
  assert.match(displayed,/ticket-transition-form/);
  assert.match(displayed,/Relato do atendimento/);
  let prevented=false;
  await tickets.handlers.submit({
    target:{
      id:'ticket-transition-form',dataset:{id:'8'},
      elements:{message:{value:'Corrigido e validado com o cliente.'}},
      querySelector:()=>({disabled:false})
    },
    preventDefault(){prevented=true;}
  });
  assert.equal(prevented,true);
  assert.equal(transitionCalls,1);
  assert.match(displayed,/Reabrir chamado/);
  process.stdout.write('UI OK: colaborador, reunião com participante/conflito e chamado com ciclo completo.\n');
})().catch(error=>{console.error(error);process.exitCode=1;});
