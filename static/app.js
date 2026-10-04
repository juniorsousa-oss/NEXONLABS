/* DESIGN LOCK v1 — interações devem preservar a identidade visual aprovada. */
'use strict';
const paths={ticket:'<path d="M2 9a2 2 0 0 0 0 4v5a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-5a2 2 0 0 0 0-4V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v3z"/><path d="M13 5v2M13 10v4M13 17v2"/>',home:'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/><path d="M9 21v-8h6v8"/>',folder:'<path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v10H3z"/>', 'check-circle':'<circle cx="12" cy="12" r="10"/><path d="m7 12 3 3 7-7"/>',users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',chart:'<path d="M5 21v-8m7 8V7m7 14V3"/>',settings:'<path d="m9.7 2 .55 2.12a8 8 0 0 1 3.5 0L14.3 2l3 1.7-.6 2.1a8 8 0 0 1 1.75 3l2.13.55v3.5l-2.13.55a8 8 0 0 1-1.75 3l.6 2.1-3 1.7-.55-2.12a8 8 0 0 1-3.5 0L9.7 20.2l-3-1.7.6-2.1a8 8 0 0 1-1.75-3l-2.13-.55v-3.5l2.13-.55a8 8 0 0 1 1.75-3l-.6-2.1z"/><circle cx="12" cy="11.1" r="2.5"/>',search:'<circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/>',bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>','chevron-down':'<path d="m6 9 6 6 6-6"/>',menu:'<path d="M4 7h16M4 12h16M4 17h16"/>',plus:'<path d="M12 5v14M5 12h14"/>',clock:'<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',layers:'<path d="m12 3 9 5-9 5-9-5 9-5zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',truck:'<path d="M3 5h12v12H3zM15 9h4l3 4v4h-7z"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',wallet:'<rect x="3" y="5" width="18" height="15" rx="2"/><path d="M3 9h18M16 15h2"/>',file:'<path d="M5 3h10l5 5v13H5zM15 3v6h5M8 14h8M8 18h6"/>','chevron-right':'<path d="m9 6 6 6-6 6"/>','chevron-left':'<path d="m15 6-6 6 6 6"/>',download:'<path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>',trash:'<path d="M4 7h16M10 3h4M6 7l1 14h10l1-14M10 11v6M14 11v6"/>',edit:'<path d="m4 17 1 3 3-1L20 7l-4-4z"/>',logout:'<path d="M9 4H4v16h5M14 8l4 4-4 4M8 12h10"/>'};
const icon=(name)=>`<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name]||paths.file}</svg>`;
document.querySelectorAll('[data-icon]').forEach(n=>n.innerHTML=icon(n.dataset.icon));
const $=s=>document.querySelector(s), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state={projects:[],tasks:[],members:[],activities:[],meetings:[],user:'Equipe ATRIA',auth_enabled:false};
let route='inicio', filter='todos',query='',page=1,perPage=5,modalProject=null,toastTimer, menuPop=null,profileMenuPop=null,confirmResolver=null;
const statusText={planejamento:'Planejamento',em_andamento:'Em andamento',concluido:'Concluído',atrasado:'Atrasado'};
const initials=s=>String(s||'NL').trim().split(/\s+/).map(n=>n[0]).slice(0,2).join('').toUpperCase();
const shortDate=s=>s?new Date(s+'T12:00:00').toLocaleDateString('pt-BR'):'—';
const dayMonth=s=>s?new Date(s+'T12:00:00').toLocaleDateString('pt-BR',{day:'2-digit',month:'short'}).replace('.','').toUpperCase():'—';
const isLate=s=>{const d=new Date();const local=[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');return Boolean(s&&s<local)};
function notice(message){const t=$('#toast');t.textContent=message;t.classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove('visible'),3500)}
async function api(path,options={}){const r=await fetch('/api'+path,{credentials:'same-origin',headers:{'Content-Type':'application/json'},...options});if(r.status===401){location.href='/';throw Error('Sessão encerrada.')}if(!r.ok){let p={};try{p=await r.json()}catch{}const detail=Array.isArray(p.detail)?p.detail.map(x=>x.msg).join('; '):p.detail;throw Error(detail||`Erro ${r.status}`)}return r.headers.get('content-type')?.includes('application/json')?r.json():r}
const ATRIA_BRAND={primary:'#0B2D4A',secondary:'#14B8A6'};
function brandAssetUrl(kind){return state.organization?.asset_urls?.[kind]||''}
function productBrandAssetUrl(kind){return state.product_brand?.asset_urls?.[kind]||''}
function contrastText(hex){
  const value=String(hex||'').replace('#','');
  if(!/^[0-9A-Fa-f]{6}$/.test(value))return '#FFFFFF';
  const rgb=[0,2,4].map(i=>parseInt(value.slice(i,i+2),16)/255)
    .map(v=>v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4));
  const luminance=.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];
  return luminance>.46?'#102943':'#FFFFFF';
}
function applyOrganizationBrand(){
  const org=state.organization||{};
  const custom=Boolean(org.use_custom_brand&&!org.is_demo);
  const basePrimary=state.product_brand?.primary_color||ATRIA_BRAND.primary;
  const baseSecondary=state.product_brand?.secondary_color||ATRIA_BRAND.secondary;
  const primary=custom?(org.primary_color||basePrimary):basePrimary;
  const secondary=custom?(org.secondary_color||baseSecondary):baseSecondary;
  document.documentElement.style.setProperty('--navy',primary);
  document.documentElement.style.setProperty('--teal',secondary);
  document.documentElement.style.setProperty('--brand-primary',primary);
  document.documentElement.style.setProperty('--brand-secondary',secondary);
  document.documentElement.style.setProperty('--brand-on-primary',contrastText(primary));
  const defaultBrand=$('#default-brand-lockup');
  const customLogo=$('#organization-brand-image');
  const officialLogo=productBrandAssetUrl('logo_dark')||productBrandAssetUrl('logo');
  const logo=custom?brandAssetUrl('logo_dark'):officialLogo;
  if(defaultBrand&&customLogo){
    defaultBrand.hidden=true;
    customLogo.hidden=true;
    document.querySelector('.sidebar .brand')?.classList.toggle('custom-brand-active',Boolean(logo));
    if(logo){
      customLogo.onload=()=>{defaultBrand.hidden=true;customLogo.hidden=false};
      customLogo.onerror=()=>{customLogo.hidden=true;defaultBrand.hidden=false};
      customLogo.src=logo;
    }else{
      defaultBrand.hidden=false;
    }
  }
  const orgLabel=$('#profile-organization');
  if(orgLabel)orgLabel.textContent=custom?(org.name||'Organização'):'ATRIA';
  const signature=$('#brand-signature');
  if(signature){
    signature.hidden=false;
    signature.innerHTML=custom?'POWERED BY ATRIA<br>BY NEXON LABS':'GESTÃO INTEGRADA';
  }
  const favicon=document.querySelector('link[rel="icon"]');
  const faviconUrl=custom&&brandAssetUrl('favicon')?brandAssetUrl('favicon'):productBrandAssetUrl('favicon');
  if(favicon){
    if(faviconUrl)favicon.href=faviconUrl;
    else favicon.removeAttribute('href');
  }
}
function fileAsDataUrl(file){
  return new Promise((resolve,reject)=>{
    const reader=new FileReader();
    reader.onload=()=>resolve(String(reader.result||''));
    reader.onerror=()=>reject(new Error('Não foi possível ler o arquivo.'));
    reader.readAsDataURL(file);
  });
}
async function refresh(){try{Object.assign(state,await api('/state'));$('#display-name').textContent=state.user;const platformContext=Boolean(state.organization?.is_platform);const platformNav=$('#atria-platform-nav');if(platformNav)platformNav.hidden=!state.platform_admin;document.querySelectorAll('.nav-link[data-route]').forEach(link=>{if(link.id==='atria-platform-nav')return;link.hidden=platformContext&&!['configuracoes'].includes(link.dataset.route)});document.querySelectorAll('.nav-section').forEach(section=>section.hidden=platformContext);if(route==='administracao-atria'&&!state.platform_admin){route='inicio';history.replaceState(null,'','#inicio')}if(platformContext&&!['administracao-atria','configuracoes'].includes(route)){route='administracao-atria';history.replaceState(null,'','#administracao-atria')}applyOrganizationBrand();const avatar=$('#avatar');avatar.textContent=initials(state.user);if(state.has_photo){const image=document.createElement('img');image.alt='';image.className='profile-avatar-image';image.onerror=()=>image.remove();image.src='/api/profile/avatar?updated='+Date.now();avatar.appendChild(image);}const alertCount=state.projects.filter(p=>p.status==='atrasado').length+state.tasks.filter(t=>!t.completed&&isLate(t.due_at)).length;$('#bell-dot').hidden=!alertCount;render()}catch(e){notice(e.message)}}
function heading(title,description,button=''){return `<div class="simple-head"><div><h1>${esc(title)}</h1><p>${esc(description)}</p></div>${button}</div>`}
const newProjectButton=()=>`<button class="primary" data-action="new-project">${icon('plus')} Novo projeto</button>`;
function metric(name,value,type='folder',hint='Dados atuais'){return `<div class="metric"><div class="metric-heading"><div class="micon ${type==='check-circle'?'teal':''}">${icon(type)}</div><div><div class="num">${esc(value)}</div><div class="mlabel">${esc(name)}</div></div></div><div class="metric-foot"><span class="up">${icon('check-circle').replace('<svg','<svg style="width:13px;height:13px;vertical-align:-2px"')} Dados em tempo real</span>${esc(hint)}</div></div>`}
function banner(){return '<div class="slogan-card"><div><h2>Da informação<br>à ação.</h2><p>Soluções sob medida<br>para o seu negócio.</p></div><div class="molecule-art"><img src="/static/brand-network.svg?v=2" alt="" aria-hidden="true"></div><button type="button" class="round-next" data-route="projetos" aria-label="Ver projetos">'+icon('chevron-right')+'</button></div>'}
function projectStatus(p){return `<span class="pill ${esc(p.status)}">${esc(statusText[p.status]||p.status)}</span>`}
function filteredProjects(){let items=state.projects.filter(p=>filter==='todos'||p.status===filter);if(query){const q=query.toLocaleLowerCase('pt-BR');items=items.filter(p=>[p.name,p.description,p.client,p.client_site,p.owner,statusText[p.status]].some(v=>String(v||'').toLocaleLowerCase('pt-BR').includes(q)))}return items}
function projectRows(items){return items.map(p=>`<tr><td><div class="project-cell"><span class="project-symbol">${icon('layers')}</span><button class="click-project" data-action="edit-project" data-id="${p.id}"><strong title="${esc(p.name)}">${esc(p.name)}</strong><small title="${esc(p.description)}">${esc(p.description||'Aplicativo e soluções digitais')}</small></button></div></td><td><div class="project-client-cell"><span title="${esc(p.client)}">${esc(p.client||'—')}</span>${p.client_site?`<a class="project-site-link" href="${esc(p.client_site)}" target="_blank" rel="noopener noreferrer" title="Abrir site de ${esc(p.client||p.name)}">Abrir site ↗</a>`:''}</div></td><td><div class="mini-person"><span class="mini-avatar">${esc(initials(p.owner))}</span><span title="${esc(p.owner)}">${esc(p.owner||'Não definido')}</span></div></td><td>${shortDate(p.due_at)}</td><td><div class="progress"><div class="progress-track"><div class="progress-fill" style="width:${p.progress}%"></div></div>${p.progress}%</div></td><td>${projectStatus(p)}</td><td><button class="dots" type="button" data-action="project-menu" data-id="${p.id}" aria-label="Opções do projeto ${esc(p.name)}">⋮</button></td></tr>`).join('')}
function projectMobileCards(items){return `<div class="project-mobile-list">${items.map(p=>`<article class="project-mobile-card"><div class="project-mobile-head"><div class="project-cell"><span class="project-symbol">${icon('layers')}</span><button class="click-project" data-action="edit-project" data-id="${p.id}"><strong title="${esc(p.name)}">${esc(p.name)}</strong><small title="${esc(p.description)}">${esc(p.description||'Aplicativo e soluções digitais')}</small></button></div><button class="dots" type="button" data-action="project-menu" data-id="${p.id}" aria-label="Opções do projeto ${esc(p.name)}">⋮</button></div><div class="project-mobile-meta"><div><small>Cliente</small><div class="project-client-cell"><span title="${esc(p.client)}">${esc(p.client||'—')}</span>${p.client_site?`<a class="project-site-link" href="${esc(p.client_site)}" target="_blank" rel="noopener noreferrer">Abrir site ↗</a>`:''}</div></div><div><small>Responsável</small><div class="mini-person"><span class="mini-avatar">${esc(initials(p.owner))}</span><span title="${esc(p.owner)}">${esc(p.owner||'Não definido')}</span></div></div><div><small>Prazo</small><strong>${shortDate(p.due_at)}</strong></div><div><small>Status</small>${projectStatus(p)}</div></div><div class="project-mobile-progress"><div class="project-mobile-progress-head"><span>Progresso</span><strong>${Number(p.progress||0)}%</strong></div><div class="progress-track"><div class="progress-fill" style="width:${Number(p.progress||0)}%"></div></div></div></article>`).join('')}</div>`}
function projectPanel(){const items=filteredProjects(),shown=items.slice((page-1)*perPage,page*perPage),pages=Math.max(1,Math.ceil(items.length/perPage));if(page>pages){page=pages;return projectPanel()}return `<section class="panel project-panel"><div class="panel-head"><h2>Projetos em andamento</h2>${newProjectButton()}</div><div class="tabs">${[['todos','Todos'],['em_andamento','Em andamento'],['planejamento','Planejamento'],['concluido','Concluídos'],['atrasado','Atrasados']].map(([key,label])=>`<button class="tab ${filter===key?'active':''}" type="button" data-filter="${key}">${label} (${key==='todos'?state.projects.length:state.projects.filter(p=>p.status===key).length})</button>`).join('')}</div><div class="table-scroll"><table class="project-table"><colgroup><col style="width:27%"><col style="width:14%"><col style="width:17%"><col style="width:11%"><col style="width:17%"><col style="width:12%"><col style="width:2%"></colgroup><thead><tr><th>PROJETO</th><th>CLIENTE</th><th>RESPONSÁVEL</th><th>PRAZO</th><th>PROGRESSO</th><th>STATUS</th><th></th></tr></thead><tbody>${projectRows(shown)}</tbody></table></div>${projectMobileCards(shown)}${!items.length?empty('Nenhum projeto encontrado','Cadastre seu primeiro projeto ou altere os filtros.','new-project'):''}<div class="panel-bottom"><span>${items.length?'Mostrando '+((page-1)*perPage+1)+'–'+Math.min(page*perPage,items.length)+' de '+items.length+' projetos':'Nenhum projeto cadastrado'}</span><div class="pager"><button class="page-btn" data-page="${page-1}" ${page===1?'disabled':''} aria-label="Página anterior">${icon('chevron-left')}</button>${Array.from({length:Math.min(pages,5)},(_,i)=>{let n=i+1;return `<button class="page-btn ${page===n?'active':''}" data-page="${n}">${n}</button>`}).join('')}<button class="page-btn" data-page="${page+1}" ${page===pages?'disabled':''} aria-label="Próxima página">${icon('chevron-right')}</button></div></div></section>`}
function empty(title,description,action){return `<div class="empty">${icon('folder')}<h3>${esc(title)}</h3><p>${esc(description)}</p>${action?`<button class="secondary" data-action="${action}">${icon('plus')} Adicionar</button>`:''}</div>`}
function rightPanels(){const upcoming=state.projects.filter(p=>p.due_at&&p.status!=='concluido').sort((a,b)=>a.due_at.localeCompare(b.due_at)).slice(0,4);return `<aside class="right-stack"><section class="panel"><div class="panel-head"><h2>Próximas entregas</h2><button class="small-link" data-route="cronograma">Ver todas</button></div><div class="delivery-list">${upcoming.length?upcoming.map(p=>`<div class="delivery home-delivery-compact"><div class="date-box"><b>${dayMonth(p.due_at).split(' ')[0]}</b><small>${dayMonth(p.due_at).split(' ').slice(1).join(' ')}</small></div><div class="delivery-body"><strong>${esc(p.name)}</strong></div><span class="dot ${p.status==='atrasado'?'red':'teal'}"></span></div>`).join(''):empty('Sem entregas previstas','')}</div></section><section class="panel"><div class="panel-head"><h2>Atividades recentes</h2><button class="small-link" data-route="relatorios">Ver todas</button></div><div class="activity-list">${state.activities.length?state.activities.slice(0,4).map(a=>`<div class="activity home-activity-compact"><span class="mini-avatar">NL</span><div class="activity-body"><strong>${esc(a.message)}</strong></div><span class="dot teal"></span></div>`).join(''):empty('Nenhuma atividade ainda','')}</div></section></aside>`}
function relative(value){if(!value)return '';const min=Math.max(0,Math.floor((Date.now()-new Date(value).getTime())/60000));if(min<2)return 'Agora';if(min<60)return `Há ${min} min`;if(min<1440)return `Há ${Math.floor(min/60)} h`;return new Date(value).toLocaleDateString('pt-BR')}

/* A visão executiva mostra prioridades; a listagem completa continua em Projetos. */
function homePriorityPanel(){
  const priority=state.projects.filter(p=>p.status!=='concluido')
    .slice().sort((a,b)=>(a.status==='atrasado'?-1:0)-(b.status==='atrasado'?-1:0)
      ||(a.due_at||'9999-12-31').localeCompare(b.due_at||'9999-12-31')).slice(0,3);
  const cards=priority.map(p=>'<button type="button" class="home-project-card" data-action="edit-project" data-id="'+p.id+
    '" aria-label="Abrir o projeto '+esc(p.name)+'"><span class="home-project-name">'+esc(p.name)+'</span>'+
    '<span class="home-client">'+esc(p.client||'Cliente não informado')+'</span>'+projectStatus(p)+
    '<span class="home-project-meta"><span>Progresso '+Number(p.progress||0)+'%</span><span>Prazo '+shortDate(p.due_at)+'</span></span>'+
    '<span class="progress-track"><span class="progress-fill" style="display:block;width:'+Number(p.progress||0)+'%"></span></span></button>').join('');
  return '<section class="panel home-priority-panel"><div class="panel-head home-section-head">'+
    '<h2>Projetos prioritários</h2><button type="button" class="small-link" data-route="projetos">Ver todos os projetos</button></div>'+
    (priority.length?'<div class="home-priority-cards">'+cards+'</div>':
      '<div class="home-empty"><strong>Nenhum projeto em andamento</strong>'+
      '<p>Cadastre um novo projeto ou consulte os projetos concluídos.</p>'+
      '<button type="button" class="secondary" data-action="new-project">'+icon('plus')+' Novo projeto</button></div>')+
    '</section>';
}
function homeUpcomingMeetings(){
  const now=new Date(),today=[now.getFullYear(),String(now.getMonth()+1).padStart(2,'0'),String(now.getDate()).padStart(2,'0')].join('-');
  const upcoming=(state.meetings||[]).filter(m=>m.meeting_date>=today&&m.status==='agendada')
    .slice().sort((a,b)=>(a.meeting_date+a.start_time).localeCompare(b.meeting_date+b.start_time)).slice(0,3);
  return '<section class="panel home-meetings-panel"><div class="panel-head"><h2>Próximas reuniões</h2>'+
    '<button type="button" class="small-link" data-route="reunioes">Ver agenda</button></div>'+
    '<div class="home-mini-agenda">'+(upcoming.length?upcoming.map(m=>'<div class="delivery home-meeting-compact">'+
      '<div class="date-box"><b>'+dayMonth(m.meeting_date).split(' ')[0]+'</b><small>'+dayMonth(m.meeting_date).split(' ').slice(1).join(' ')+'</small></div>'+
      '<div class="delivery-body"><strong>'+esc(m.title)+'</strong><small>'+esc(m.start_time)+'</small></div>'+
      '<span class="dot teal"></span></div>').join(''):
      '<div class="home-empty home-empty-compact"><strong>Agenda livre</strong>'+
      '<button type="button" class="secondary" data-route="reunioes">'+icon('calendar')+' Abrir agenda</button></div>')+
    '</div></section>';
}
function homeSidebar(){
  return rightPanels().replace('</aside>',homeUpcomingMeetings()+'</aside>');
}
function dashboard(){
  const active=state.projects.filter(p=>p.status!=='concluido').length;
  const pending=state.tasks.filter(t=>!t.completed).length;
  const nonDone=state.projects.filter(p=>p.status!=='concluido'&&p.due_at);
  const onTime=nonDone.length?Math.round(nonDone.filter(p=>p.status!=='atrasado').length/nonDone.length*100):null;
  const hours=state.tasks.reduce((a,t)=>a+Number(t.hours||0),0);
  const metrics='<div class="metric-grid home-metrics">'+
    metric('Projetos ativos',active,'folder','Em planejamento ou execução')+
    metric('Tarefas em andamento',pending,'check-circle','Atividades pendentes')+
    metric('Projetos no prazo',onTime===null?'—':onTime+'%','chart',nonDone.length?'Entre projetos com prazo':'Sem projetos com prazo')+
    metric('Horas registradas',hours.toLocaleString('pt-BR')+'h','clock','Horas lançadas nas tarefas')+
    '</div>';
  const quick='<div class="home-quick-links">'+
    '<button type="button" data-route="orcamentos">'+icon('file')+
    '<span><strong>Orçamentos</strong><small>Precificação e propostas comerciais</small></span></button>'+
    '<button type="button" data-route="reunioes">'+icon('calendar')+
    '<span><strong>Reuniões</strong><small>Agendamentos com clientes</small></span></button></div>';
  return '<div class="hero"><div class="hero-text"><h1>Olá, '+esc((state.user||'').split(' ')[0]||'bem-vindo')+'!</h1>'+
    '<p>Acompanhe seus projetos e transforme planos em resultados.</p></div>'+banner()+'</div>'+
    metrics+'<div class="home-grid"><div class="home-main">'+homePriorityPanel()+quick+
    '</div>'+homeSidebar()+'</div>';
}
function projectsPage(){const underway=state.projects.filter(p=>p.status==='em_andamento').length,planned=state.projects.filter(p=>p.status==='planejamento').length,done=state.projects.filter(p=>p.status==='concluido').length;return heading('Projetos','Cadastre, acompanhe e atualize cada projeto no ATRIA.')+'<div class="projects-view"><div class="projects-summary"><span><strong>'+state.projects.length+'</strong> cadastrados</span><span><strong>'+underway+'</strong> em andamento</span><span><strong>'+planned+'</strong> em planejamento</span><span><strong>'+done+'</strong> concluídos</span></div>'+projectPanel()+'</div>'}
function tasksPage(){const list=state.tasks.filter(t=>!query||[t.title,t.assignee,state.projects.find(p=>p.id===t.project_id)?.name].some(x=>String(x||'').toLowerCase().includes(query.toLowerCase())));return `${heading('Tarefas','Acompanhe atividades e registre o tempo dedicado a cada projeto.',`<button class="primary" data-action="new-task">${icon('plus')} Nova tarefa</button>`)}<section class="panel"><div class="panel-head"><h2>Atividades dos projetos</h2><span class="muted">${state.tasks.filter(t=>!t.completed).length} pendentes</span></div><div class="list-stack" style="margin-top:17px">${list.length?list.map(t=>`<div class="line-item"><aside><input type="checkbox" data-action="toggle-task" data-id="${t.id}" ${t.completed?'checked':''} aria-label="Marcar ${esc(t.title)} como concluída"><div><h3 style="${t.completed?'text-decoration:line-through;color:#8191a4':''}">${esc(t.title)}</h3><p>${esc(state.projects.find(p=>p.id===t.project_id)?.name||'Projeto excluído')} · ${esc(t.assignee||'Sem responsável')} · ${t.hours}h · Prazo ${shortDate(t.due_at)}</p></div></aside><button class="secondary" data-action="edit-task" data-id="${t.id}">${icon('edit')} Editar</button></div>`).join(''):empty('Nenhuma tarefa cadastrada','As tarefas cadastradas nos projetos aparecerão aqui.','new-task')}</div></section>`}
function teamPage(){return window.NexonBrandUI.page()}
function schedulePage(){const due=state.projects.filter(p=>p.due_at).sort((a,b)=>a.due_at.localeCompare(b.due_at));const taskDue=state.tasks.filter(t=>t.due_at&&!t.completed).map(t=>({...t,project:state.projects.find(p=>p.id===t.project_id)}));const events=[...due.map(p=>({id:p.id,date:p.due_at,title:p.name,subtitle:'Prazo do projeto',status:p.status,action:'edit-project'})),...taskDue.map(t=>({id:t.id,date:t.due_at,title:t.title,subtitle:'Tarefa · '+(t.project?.name||''),status:isLate(t.due_at)?'atrasado':'planejamento',action:'edit-task'}))].sort((a,b)=>a.date.localeCompare(b.date));return `${heading('Cronograma','Entregas e tarefas organizadas por prazo.',newProjectButton())}<section class="panel"><div class="panel-head"><h2>Próximos compromissos</h2><span class="muted">${events.length} registros</span></div><div class="list-stack" style="margin-top:17px">${events.length?events.map(e=>`<div class="line-item"><aside><div class="date-box"><b>${dayMonth(e.date).split(' ')[0]}</b><small>${dayMonth(e.date).split(' ').slice(1).join(' ')}</small></div><div><h3>${esc(e.title)}</h3><p>${esc(e.subtitle)} · ${shortDate(e.date)}</p></div></aside><button class="secondary" data-action="${e.action}" data-id="${e.id}">${icon('chevron-right')} Abrir</button></div>`).join(''):empty('Sem prazos definidos','Defina datas para acompanhar seu cronograma.')}</div></section>`}
function reportsPage(){const done=state.projects.filter(p=>p.status==='concluido').length;return `${heading('Relatórios','Indicadores calculados a partir dos projetos e tarefas cadastrados.',`<button class="primary" data-action="export">${icon('download')} Exportar projetos CSV</button>`)}<div class="report-tiles">${metric('Projetos cadastrados',state.projects.length,'folder')}${metric('Projetos concluídos',done,'check-circle')}${metric('Tarefas concluídas',state.tasks.filter(t=>t.completed).length,'chart')}</div><section class="panel"><div class="panel-head"><h2>Distribuição por status</h2></div><div class="list-stack" style="margin-top:16px">${Object.entries(statusText).map(([key,label])=>`<div class="line-item"><h3>${label}</h3><strong>${state.projects.filter(p=>p.status===key).length}</strong></div>`).join('')}</div><div class="subsection"><h3>Últimas movimentações</h3>${state.activities.length?state.activities.slice(0,20).map(a=>`<div class="task-inside"><span>${esc(a.message)}</span><small class="muted">${relative(a.created_at)}</small></div>`).join(''):'<p class="muted">Nenhuma movimentação registrada.</p>'}</div></section>`}
function brandAssetCard(kind,label,hint){
  const org=state.organization||{},has=Boolean(org.assets?.[kind]),src=brandAssetUrl(kind);
  const editable=state.user_role==='admin'&&!org.is_demo;
  return '<article class="brand-asset-card"><div class="brand-asset-preview '+(kind==='watermark'?'watermark-preview':'')+'">'+
    (has?'<img src="'+esc(src)+'" alt="'+esc(label)+'">':'<div class="brand-asset-empty">'+icon(kind==='favicon'?'layers':'file')+'<span>Usando padrão ATRIA</span></div>')+
    '</div><div class="brand-asset-copy"><strong>'+esc(label)+'</strong><small>'+esc(hint)+'</small></div>'+
    (editable?'<div class="brand-asset-actions"><label class="secondary brand-upload-button">'+icon('plus')+' '+(has?'Substituir':'Enviar')+
      '<input type="file" hidden data-brand-file="'+kind+'" accept="image/png,image/jpeg,image/webp"></label>'+
      (has?'<button type="button" class="brand-remove-link" data-action="remove-brand-asset" data-kind="'+kind+'">Remover</button>':'')+
      '</div>':'')+'</article>';
}
function productBrandAssetCard(kind,label,hint){
  const brand=state.product_brand||{},has=Boolean(brand.assets?.[kind]),src=productBrandAssetUrl(kind);
  return '<article class="brand-asset-card"><div class="brand-asset-preview '+(kind==='watermark'?'watermark-preview':'')+'">'+
    (has?'<img src="'+esc(src)+'" alt="'+esc(label)+'">':'<div class="brand-asset-empty">'+icon(kind==='favicon'?'layers':'file')+'<span>Arquivo oficial pendente</span></div>')+
    '</div><div class="brand-asset-copy"><strong>'+esc(label)+'</strong><small>'+esc(hint)+'</small></div>'+
    (state.platform_admin?'<div class="brand-asset-actions"><label class="secondary brand-upload-button">'+icon('plus')+' '+(has?'Substituir':'Enviar')+
      '<input type="file" hidden data-product-brand-file="'+kind+'" accept="image/png,image/jpeg,image/webp"></label>'+
      (has?'<button type="button" class="brand-remove-link" data-action="remove-product-brand-asset" data-kind="'+kind+'">Remover</button>':'')+
    '</div>':'')+'</article>';
}

function platformAdminPage(){
  if(!state.platform_admin)return heading('Administração ATRIA','Área restrita da plataforma.')+
    '<section class="panel"><p class="muted">Você não possui acesso à administração global do produto.</p></section>';
  const brand=state.product_brand||{};
  const primary=brand.primary_color||ATRIA_BRAND.primary;
  const secondary=brand.secondary_color||ATRIA_BRAND.secondary;
  const readiness=brand.brand_ready
    ?'<div class="brand-locked-note"><strong>Padrão base completo</strong><span>Login, sidebar e favicon possuem os ativos oficiais necessários.</span></div>'
    :'<div class="brand-locked-note"><strong>Padrão base incompleto</strong><span>Cadastre pelo menos a Logo ATRIA para fundo escuro e o Favicon oficial. Enquanto faltarem, o ATRIA usa apenas um fallback tipográfico e não reutiliza a marca antiga.</span></div>';
  return heading('Administração ATRIA','Defina o padrão global do produto. Organizações sem personalização herdam estas configurações automaticamente.')+
    '<section class="panel organization-brand-panel product-brand-panel"><div class="panel-head"><div><h2>Padrão oficial do produto</h2>'+
    '<p class="muted">O ATRIA Demo usa este padrão integralmente. Novos clientes recebem o mesmo layout e identidade-base, podendo sobrescrever apenas os itens liberados para a organização.</p></div>'+
    '<span class="brand-mode-badge">Global</span></div>'+
    readiness+
    '<form id="product-brand-form" class="organization-brand-form">'+
      '<div class="brand-color-grid"><label>Cor principal padrão<div><input type="color" name="primary_color" value="'+esc(primary)+'"><code>'+esc(primary)+'</code></div></label>'+
      '<label>Cor de destaque padrão<div><input type="color" name="secondary_color" value="'+esc(secondary)+'"><code>'+esc(secondary)+'</code></div></label></div>'+
      '<div class="brand-settings-actions"><span class="muted">Layout-base: '+esc(brand.layout_version||'atria-v1')+'</span><button type="submit" class="primary">Salvar padrão global</button></div>'+
    '</form>'+
    '<div class="brand-assets-grid">'+
      productBrandAssetCard('logo','Logo principal ATRIA','Uso padrão em fundos claros, documentos, assinatura e cartão.')+
      productBrandAssetCard('logo_dark','Logo ATRIA para fundo escuro','Uso padrão no login e na barra lateral.')+
      productBrandAssetCard('favicon','Favicon oficial ATRIA','Símbolo padrão do navegador e atalhos.')+
      productBrandAssetCard('watermark','Marca d’água ATRIA','Padrão disponível para PDFs, relatórios e documentos.')+
    '</div>'+
    '<div class="brand-product-signature"><span>Herança do produto</span><strong>ATRIA Demo = padrão global · Clientes = padrão global + personalizações próprias</strong></div>'+
    '</section>'+
    '<section class="panel" style="margin-top:16px"><div class="panel-head"><div><h2>Regra de replicação</h2><p class="muted">Alterações no layout-base e nos ativos oficiais passam a valer automaticamente para todas as organizações que não tenham sobrescrito aquele item.</p></div></div>'+
    '<div class="list-stack"><div class="line-item"><div><h3>ATRIA Demo</h3><p>Referência oficial de como um ambiente novo sai de fábrica.</p></div><strong>Padrão integral</strong></div>'+
    '<div class="line-item"><div><h3>Organizações clientes</h3><p>Recebem o mesmo produto-base e personalizam logo, favicon, cores, marca d’água e materiais conforme permitido.</p></div><strong>Herança + override</strong></div></div></section>';
}
function settingsPage(){
  const org=state.organization||{};
  const admin=state.user_role==='admin',locked=Boolean(org.is_demo||org.is_platform);
  const basePrimary=state.product_brand?.primary_color||ATRIA_BRAND.primary;
  const baseSecondary=state.product_brand?.secondary_color||ATRIA_BRAND.secondary;
  const primary=org.use_custom_brand?(org.primary_color||basePrimary):basePrimary;
  const secondary=org.use_custom_brand?(org.secondary_color||baseSecondary):baseSecondary;
  const identity='<section class="panel organization-brand-panel"><div class="panel-head"><div><h2>Identidade visual</h2>'+
    '<p class="muted">Marca da organização aplicada sem remover a assinatura do ATRIA e da Nexon Labs.</p></div>'+
    '<span class="brand-mode-badge">'+(locked?'Padrão ATRIA':org.use_custom_brand?'Personalizada':'Padrão ATRIA')+'</span></div>'+
    (locked?'<div class="brand-locked-note"><strong>'+(org.is_platform?'Administração da plataforma':'Ambiente de demonstração')+'</strong><span>'+(org.is_platform?'Este perfil usa diretamente a identidade oficial do ATRIA e não possui personalização de cliente.':'O ATRIA Demo permanece com a identidade oficial do produto.')+'</span></div>':
    '<form id="organization-brand-form" class="organization-brand-form">'+
      '<label class="brand-enable"><input type="checkbox" name="use_custom_brand" '+(org.use_custom_brand?'checked':'')+' '+(!admin?'disabled':'')+'>'+
      '<span><strong>Usar identidade personalizada</strong><small>Ativa logo, favicon e cores próprias desta organização.</small></span></label>'+
      '<div class="brand-color-grid"><label>Cor principal<div><input type="color" name="primary_color" value="'+esc(primary)+'" '+(!admin?'disabled':'')+'><code>'+esc(primary)+'</code></div></label>'+
      '<label>Cor de destaque<div><input type="color" name="secondary_color" value="'+esc(secondary)+'" '+(!admin?'disabled':'')+'><code>'+esc(secondary)+'</code></div></label></div>'+
      (admin?'<div class="brand-settings-actions"><button type="button" class="secondary" data-action="restore-brand-default">Restaurar padrão ATRIA</button>'+
      '<button type="submit" class="primary">Salvar identidade</button></div>':'<p class="muted">Somente administradores podem alterar a identidade visual.</p>')+
    '</form>')+
    '<div class="brand-assets-grid">'+
      brandAssetCard('logo','Logo principal','Uso em fundos claros e documentos.')+
      brandAssetCard('logo_dark','Logo para fundo escuro','Usada na barra lateral. Se não houver, o ATRIA mantém sua marca oficial para preservar o contraste.')+
      brandAssetCard('favicon','Favicon','Ícone quadrado do navegador e atalhos.')+
      brandAssetCard('watermark','Marca d’água','Reservada para PDFs, relatórios e documentos.')+
    '</div>'+
    '<div class="brand-product-signature"><span>Assinatura do produto</span><strong>'+(org.use_custom_brand&&!org.is_demo?'Powered by ATRIA · by Nexon Labs':'A marca ATRIA já inclui BY NEXON LABS')+'</strong></div>'+
    '</section>';
  return heading('Configurações','Personalize somente esta organização, seus dados e seus acessos ao sistema.')+
    identity+window.NexonUsers.panel()+
  '<section class="panel" style="margin-top:16px"><div class="panel-head"><h2>Segurança e sessão</h2></div>'+
  '<p class="muted">Acesso individual: '+esc(state.user||'Usuário')+
  ' · '+(state.user_role==='admin'?'Administrador':'Usuário')+'.</p>'+
  '<p class="muted">Cada organização mantém usuários e dados isolados no ATRIA.</p>'+
  '<button type="button" class="secondary" data-action="logout">'+icon('logout')+' Sair da conta</button></section>';
}
function render(){document.querySelectorAll('.nav-link[data-route]').forEach(e=>{const active=e.dataset.route===route;e.classList.toggle('active',active);if(active)e.setAttribute('aria-current','page');else e.removeAttribute('aria-current');});const views={inicio:dashboard,projetos:projectsPage,tarefas:tasksPage,equipe:teamPage,cronograma:schedulePage,reunioes:window.NexonMeetings.page,orcamentos:window.NexonQuotes.page,chamados:window.NexonTickets.page,relatorios:reportsPage,configuracoes:settingsPage};if(state.platform_admin)views['administracao-atria']=platformAdminPage;$('#main').innerHTML=(views[route]||dashboard)();}
function go(target){if(target==='administracao-atria'&&!state.platform_admin){notice('Área restrita à administração da plataforma ATRIA.');target='inicio'}route=target;filter='todos';page=1;window.location.hash=route;$('#sidebar').classList.remove('open');$('.mobile-overlay')?.remove();render();window.scrollTo({top:0,behavior:'instant'})}
function field(label,name,value='',type='text',extra=''){return `<label>${esc(label)}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`}
function selectField(label,name,values,current){return `<label>${esc(label)}<select name="${name}">${values.map(([v,s])=>`<option value="${esc(v)}" ${v===current?'selected':''}>${esc(s)}</option>`).join('')}</select></label>`}
function modal(title,body,actions=''){closeMenu();$('#modal-root').innerHTML=`<div class="modal-cover" id="modal-cover"><section class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="modal-top"><h2>${esc(title)}</h2><button type="button" class="close-btn" data-action="close-modal" aria-label="Fechar">×</button></div>${body}${actions}</section></div>`;$('#modal-cover').addEventListener('click',e=>{if(e.target.id==='modal-cover')closeModal()});$('#modal-root').querySelector('input:not([type=hidden]),select')?.focus()}
function finishConfirm(value){
  if(!confirmResolver)return;
  const resolve=confirmResolver;confirmResolver=null;
  $('#modal-root').innerHTML='';modalProject=null;
  resolve(Boolean(value));
}
function confirmAction(message,title='Confirmar ação',confirmLabel='Confirmar'){
  if(confirmResolver)finishConfirm(false);
  return new Promise(resolve=>{
    confirmResolver=resolve;
    $('#modal-root').innerHTML='<div class="modal-cover confirmation-cover" id="confirmation-cover">'+
      '<section class="modal confirmation-modal" role="alertdialog" aria-modal="true" aria-labelledby="confirmation-title">'+
      '<div class="confirmation-icon">!</div><h2 id="confirmation-title">'+esc(title)+'</h2>'+
      '<p>'+esc(message)+'</p><div class="confirmation-actions">'+
      '<button type="button" class="secondary" data-confirm-choice="no">Cancelar</button>'+
      '<button type="button" class="danger confirmation-danger" data-confirm-choice="yes">'+esc(confirmLabel)+'</button>'+
      '</div></section></div>';
    $('#confirmation-cover').addEventListener('click',e=>{if(e.target.id==='confirmation-cover')finishConfirm(false)});
    $('#modal-root').querySelector('[data-confirm-choice="no"]')?.focus();
  });
}
function closeModal(){
  if(confirmResolver){finishConfirm(false);return;}
  $('#modal-root').innerHTML='';modalProject=null
}
function projectForm(p){modalProject=p?.id??null;modal(p?'Editar projeto':'Novo projeto',`<form id="project-form"><div class="fields">${field('Nome do projeto *','name',p?.name||'','text','required minlength="2" maxlength="160"')}${field('Cliente','client',p?.client||'')}${field('Site do cliente','client_site',p?.client_site||'','url','placeholder="https://www.cliente.com.br" maxlength="500"')}${p?.client_site?`<div class="project-site-current full"><span>Site cadastrado</span><a href="${esc(p.client_site)}" target="_blank" rel="noopener noreferrer">Abrir site do cliente ↗</a></div>`:''}${field('Responsável','owner',p?.owner||'','text','list="owner-list"')}<datalist id="owner-list">${state.members.map(m=>`<option value="${esc(m.name)}"></option>`).join('')}</datalist>${selectField('Status','status',[['planejamento','Planejamento'],['em_andamento','Em andamento'],['concluido','Concluído']],p?.saved_status||'planejamento')}${field('Início','started_at',p?.started_at||'','date')}${field('Prazo','due_at',p?.due_at||'','date')}${field('Progresso (%)','progress',p?.progress??0,'number','min="0" max="100"') }<label class="full">Descrição<textarea name="description" maxlength="2000">${esc(p?.description||'')}</textarea></label></div><div class="form-actions">${p?`<button type="button" class="danger" data-action="delete-project" data-id="${p.id}">${icon('trash')} Excluir projeto</button>`:'<span class="hint">* Campo obrigatório</span>'}<div class="right"><button type="button" class="secondary" data-action="close-modal">Cancelar</button><button type="submit" class="primary">${p?'Salvar alterações':'Cadastrar projeto'}</button></div></div></form>${p?`<div class="subsection"><h3>Tarefas do projeto</h3>${state.tasks.filter(t=>t.project_id===p.id).map(t=>`<div class="task-inside"><span>${t.completed?'✓':'○'} ${esc(t.title)}</span><button data-action="edit-task" data-id="${t.id}">Editar</button></div>`).join('')||'<p class="muted">Nenhuma tarefa cadastrada.</p>'}<button class="secondary" data-action="new-task" data-project-id="${p.id}" style="margin-top:12px">${icon('plus')} Nova tarefa</button></div>`:''}`)}
function taskForm(t,projectId){if(!state.projects.length){notice('Cadastre um projeto antes de adicionar tarefas.');return}const id=t?.project_id||Number(projectId)||state.projects[0].id;modal(t?'Editar tarefa':'Nova tarefa',`<form id="task-form"><div class="fields">${selectField('Projeto *','project_id',state.projects.map(p=>[String(p.id),p.name]),String(id))}${field('Título da tarefa *','title',t?.title||'','text','required minlength="2"')}${field('Responsável','assignee',t?.assignee||'','text','list="member-list"')}<datalist id="member-list">${state.members.map(m=>`<option value="${esc(m.name)}"></option>`).join('')}</datalist>${field('Prazo','due_at',t?.due_at||'','date')}${field('Horas registradas','hours',t?.hours??0,'number','min="0" max="100000" step="0.25"')}<label>Concluída<select name="completed"><option value="false" ${!t?.completed?'selected':''}>Não</option><option value="true" ${t?.completed?'selected':''}>Sim</option></select></label></div><div class="form-actions">${t?`<button type="button" class="danger" data-action="delete-task" data-id="${t.id}">Excluir</button>`:'<span></span>'}<div class="right"><button type="button" class="secondary" data-action="close-modal">Cancelar</button><button class="primary" type="submit">Salvar tarefa</button></div></div></form>`);$('#task-form').dataset.id=t?.id||''}
function memberForm(m){return window.NexonBrandUI.memberForm(m)}
function formValues(form){return Object.fromEntries(new FormData(form).entries())}
function closeMenu(){menuPop?.remove();menuPop=null}
function closeProfileMenu(){profileMenuPop?.remove();profileMenuPop=null}
function profileMenuFor(target){
  closeProfileMenu();
  const rect=target.getBoundingClientRect();
  profileMenuPop=document.createElement('div');
  profileMenuPop.className='profile-menu';
  profileMenuPop.style.top=Math.min(rect.bottom+8,innerHeight-130)+'px';
  profileMenuPop.style.right=Math.max(12,innerWidth-rect.right)+'px';
  profileMenuPop.innerHTML='<div class="profile-menu-head"><strong>'+esc(state.user||'Usuário')+'</strong>'+
    '<small>'+esc(state.organization?.name||'ATRIA')+'</small></div>'+
    '<button type="button" data-action="profile-settings">'+icon('settings')+' Configurações</button>'+
    '<button type="button" class="profile-menu-logout" data-action="logout">'+icon('logout')+' Sair</button>';
  document.body.append(profileMenuPop);
}
function menuFor(target,p){closeMenu();const rect=target.getBoundingClientRect();menuPop=document.createElement('div');menuPop.className='tooltip-menu';menuPop.style.left=Math.max(8,Math.min(rect.left-142,innerWidth-185))+'px';menuPop.style.top=Math.min(rect.bottom+4,innerHeight-105)+'px';menuPop.innerHTML=`<button data-action="edit-project" data-id="${p.id}">Editar projeto</button>${p.client_site?'<a class="project-menu-site" href="'+esc(p.client_site)+'" target="_blank" rel="noopener noreferrer">Abrir site do cliente ↗</a>':''}${p.status==='concluido'?'<button data-action="reopen-project" data-id="'+p.id+'">Reabrir projeto</button>':'<button data-action="complete-project" data-id="'+p.id+'">Concluir projeto</button>'}<button data-action="delete-project" data-id="${p.id}">Excluir projeto</button>`;document.body.append(menuPop)}
async function safeWrite(callback){try{await callback();closeModal();await refresh()}catch(e){notice(e.message)}}
document.addEventListener('click',async e=>{const confirmEl=e.target.closest('[data-confirm-choice]');if(confirmEl){finishConfirm(confirmEl.dataset.confirmChoice==='yes');return}const filterEl=e.target.closest('[data-filter]');if(filterEl){filter=filterEl.dataset.filter;page=1;render();return}const pageEl=e.target.closest('[data-page]');if(pageEl){page=Number(pageEl.dataset.page);render();return}const button=e.target.closest('[data-action],[data-route]');if(!button){if(menuPop&&!e.target.closest('.tooltip-menu'))closeMenu();if(profileMenuPop&&!e.target.closest('.profile-menu')&&!e.target.closest('#profile'))closeProfileMenu();return}if(button.dataset.route){go(button.dataset.route);return}const action=button.dataset.action,id=Number(button.dataset.id);if(!button.closest('.tooltip-menu')&&action!=='project-menu')closeMenu();switch(action){case 'close-modal':closeModal();break;case 'profile-settings':closeProfileMenu();go('configuracoes');break;case 'new-project':projectForm(null);break;case 'edit-project':projectForm(state.projects.find(p=>p.id===id));break;case 'project-menu':menuFor(button,state.projects.find(p=>p.id===id));break;case 'new-task':taskForm(null,button.dataset.projectId);break;case 'edit-task':taskForm(state.tasks.find(t=>t.id===id));break;case 'new-member':memberForm();break;case 'complete-project':{const p=state.projects.find(p=>p.id===id);if(!p)break;const pending=state.tasks.filter(t=>t.project_id===id&&!t.completed);if(pending.length){notice('Conclua antes as '+pending.length+' tarefa(s) pendente(s) do projeto.');break;}if(await confirmAction('Concluir o projeto '+p.name+'? Ele sairá dos projetos ativos.','Concluir projeto','Concluir'))await safeWrite(async()=>{await api('/projects/'+id,{method:'PUT',body:JSON.stringify({...p,status:'concluido',progress:100})});notice('Projeto concluído.');});break;}
case 'reopen-project':{const p=state.projects.find(p=>p.id===id);if(!p)break;if(await confirmAction('Reabrir o projeto '+p.name+'?','Reabrir projeto','Reabrir'))await safeWrite(async()=>{await api('/projects/'+id,{method:'PUT',body:JSON.stringify({...p,status:'em_andamento',progress:Math.min(99,Number(p.progress||0))})});notice('Projeto reaberto.');});break;}
case 'remove-product-brand-asset':{const kind=button.dataset.kind;if(await confirmAction('Remover este arquivo da identidade oficial do ATRIA?','Remover arquivo oficial','Remover')){try{await api('/product-brand/assets/'+kind,{method:'DELETE'});notice('Arquivo oficial removido.');await refresh()}catch(error){notice(error.message)}}break;}case 'restore-brand-default':if(await confirmAction('Restaurar a identidade visual padrão do ATRIA nesta organização?','Restaurar identidade','Restaurar')){try{for(const kind of ['logo','logo_dark','favicon','watermark'])if(state.organization?.assets?.[kind])await api('/organization/brand/assets/'+kind,{method:'DELETE'});const basePrimary=state.product_brand?.primary_color||ATRIA_BRAND.primary,baseSecondary=state.product_brand?.secondary_color||ATRIA_BRAND.secondary;await api('/organization/brand',{method:'PUT',body:JSON.stringify({primary_color:basePrimary,secondary_color:baseSecondary,use_custom_brand:false})});notice('Identidade padrão do ATRIA restaurada.');await refresh()}catch(error){notice(error.message)}}break;case 'remove-brand-asset':{const kind=button.dataset.kind;if(await confirmAction('Remover este arquivo da identidade visual?','Remover identidade','Remover')){try{await api('/organization/brand/assets/'+kind,{method:'DELETE'});notice('Arquivo removido.');await refresh()}catch(error){notice(error.message)}}break;}case 'delete-project':if(await confirmAction('Excluir o projeto e todas as tarefas dele? Esta ação não pode ser desfeita.','Excluir projeto','Excluir'))await safeWrite(async()=>{await api('/projects/'+id,{method:'DELETE'});notice('Projeto excluído.')});break;case 'delete-task':if(await confirmAction('Excluir esta tarefa?','Excluir tarefa','Excluir'))await safeWrite(async()=>{await api('/tasks/'+id,{method:'DELETE'});notice('Tarefa excluída.')});break;case 'delete-member':if(await confirmAction('Remover integrante da equipe?','Remover integrante','Remover'))await safeWrite(async()=>{await api('/members/'+id,{method:'DELETE'});notice('Integrante removido.')});break;case 'toggle-task':{const t=state.tasks.find(t=>t.id===id);await safeWrite(async()=>{await api('/tasks/'+id,{method:'PUT',body:JSON.stringify({...t,completed:button.checked})});notice('Tarefa atualizada.')});break}case 'export':window.location.assign('/api/export/projects.csv');break;case 'logout':closeProfileMenu();await api('/logout',{method:'POST'});location.assign('/');break;}}
);
document.addEventListener('submit',async e=>{if(!['project-form','task-form','member-form','organization-brand-form','product-brand-form'].includes(e.target.id))return;e.preventDefault();const f=e.target,values=formValues(f);if(f.id==='product-brand-form'){try{const payload={primary_color:String(values.primary_color||ATRIA_BRAND.primary),secondary_color:String(values.secondary_color||ATRIA_BRAND.secondary)};state.product_brand=await api('/product-brand',{method:'PUT',body:JSON.stringify(payload)});notice('Padrão global do ATRIA atualizado.');applyOrganizationBrand();render()}catch(error){notice(error.message)}return;}if(f.id==='organization-brand-form'){try{const payload={primary_color:String(values.primary_color||ATRIA_BRAND.primary),secondary_color:String(values.secondary_color||ATRIA_BRAND.secondary),use_custom_brand:Boolean(f.elements.use_custom_brand?.checked)};await api('/organization/brand',{method:'PUT',body:JSON.stringify(payload)});notice('Identidade visual atualizada.');await refresh()}catch(error){notice(error.message)}return;}if(f.id==='project-form'){values.progress=Number(values.progress);values.started_at=values.started_at||null;values.due_at=values.due_at||null;values.client_site=(values.client_site||'').trim();const id=modalProject;await safeWrite(async()=>{await api(id?'/projects/'+id:'/projects',{method:id?'PUT':'POST',body:JSON.stringify(values)});notice(id?'Projeto atualizado.':'Projeto cadastrado.')})}if(f.id==='task-form'){values.project_id=Number(values.project_id);values.hours=Number(values.hours);values.due_at=values.due_at||null;values.completed=values.completed==='true';const id=Number(f.dataset.id);await safeWrite(async()=>{await api(id?'/tasks/'+id:'/tasks',{method:id?'PUT':'POST',body:JSON.stringify(values)});notice('Tarefa salva.')})}if(f.id==='member-form'){const id=Number(f.dataset.id)||null;await safeWrite(async()=>{await api(id?'/members/'+id:'/members',{method:id?'PUT':'POST',body:JSON.stringify(values)});notice(id?'Colaborador atualizado.':'Colaborador cadastrado.')})}});
document.addEventListener('change',async e=>{
  const productInput=e.target.closest('[data-product-brand-file]');
  const input=productInput||e.target.closest('[data-brand-file]');
  if(!input||!input.files?.length)return;
  const file=input.files[0],kind=productInput?productInput.dataset.productBrandFile:input.dataset.brandFile;
  const limit=kind==='favicon'?1_000_000:2_500_000;
  if(file.size>limit){notice('Arquivo maior que o limite permitido.');input.value='';return;}
  try{
    const image_data=await fileAsDataUrl(file);
    const endpoint=productInput?'/product-brand/assets/':'/organization/brand/assets/';
    await api(endpoint+kind,{method:'PUT',body:JSON.stringify({image_data})});
    notice(productInput?'Identidade oficial do ATRIA atualizada.':'Arquivo de identidade visual atualizado.');
    await refresh();
  }catch(error){notice(error.message)}
  finally{input.value=''}
});
document.addEventListener('input',e=>{
  const color=e.target.closest('#organization-brand-form input[type="color"],#product-brand-form input[type="color"]');
  if(!color)return;
  const code=color.parentElement?.querySelector('code');
  if(code)code.textContent=color.value.toUpperCase();
});
$('#global-search').addEventListener('input',e=>{query=e.target.value.trim();page=1;if(!['projetos','inicio','tarefas'].includes(route))go('projetos');else render()});
$('#bell').addEventListener('click',()=>{const count=state.projects.filter(p=>p.status==='atrasado').length+state.tasks.filter(t=>!t.completed&&isLate(t.due_at)).length;notice(count?`${count} prazo(s) exigem atenção. Confira o cronograma.`:'Nenhuma pendência de prazo identificada.');if(count)go('cronograma')});
$('#profile').addEventListener('click',e=>{e.stopPropagation();if(profileMenuPop){closeProfileMenu();return}profileMenuFor($('#profile'));});
$('#menu-toggle').addEventListener('click',()=>{const side=$('#sidebar');side.classList.toggle('open');if(side.classList.contains('open')){let overlay=document.createElement('div');overlay.className='mobile-overlay show';overlay.onclick=()=>{side.classList.remove('open');overlay.remove()};document.body.append(overlay)}else $('.mobile-overlay')?.remove()});
window.addEventListener('hashchange',()=>{const target=location.hash.slice(1);if(['inicio','projetos','tarefas','equipe','cronograma','reunioes','orcamentos','chamados','relatorios','configuracoes','administracao-atria'].includes(target)&&target!==route)go(target)});
window.addEventListener('keydown',e=>{if(e.key==='Escape'){closeModal();closeMenu();closeProfileMenu()}});
if(['inicio','projetos','tarefas','equipe','cronograma','reunioes','orcamentos','chamados','relatorios','configuracoes','administracao-atria'].includes(location.hash.slice(1)))route=location.hash.slice(1);
refresh();
