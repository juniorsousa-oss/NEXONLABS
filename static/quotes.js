/* Orçamentos: módulo comercial isolado da identidade visual aprovada. */
'use strict';
window.NexonQuotes = (() => {
  let quotes = [], company = null, loaded = false, loading = false;
  let editing = null, showEditor = false, showCompany = false;
  const curr = value => Number(value || 0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
  const integer = value => String(value ?? '');
  const fmtDate = date => date ? new Date(date+'T12:00:00').toLocaleDateString('pt-BR') : '—';
  const clean = value => esc(value ?? '');
  const attr = (name, value) => ' name="'+name+'" value="'+clean(value)+'"';
  const fieldQ = (name, title, value, type, extra) =>
    '<label>'+title+'<input'+attr(name,value)+' type="'+(type||'text')+'" '+(extra||'')+'></label>';
  const areaQ = (name,title,value,extra) => '<label class="quote-full">'+title+'<textarea name="'+name+'" '+(extra||'')+'>'+clean(value)+'</textarea></label>';
  const statusText = {rascunho:'Em elaboração',enviado:'Enviado',aprovado:'Aprovado',recusado:'Recusado',vencido:'Vencido'};
  const statusOptions = key => '<select name="status">'+Object.keys(statusText).filter(s=>s!=='vencido').map(s=>
    '<option value="'+s+'" '+(key===s?'selected':'')+'>'+statusText[s]+'</option>').join('')+'</select>';
  function estimate(values){
    const qty = Math.max(0,Number(values.quantity)||0), hours = Math.max(0,Number(values.hours_per_unit)||0);
    const cost = Math.max(0,Number(values.hourly_cost)||0), reserve = Math.max(0,Number(values.reserve_pct)||0);
    const expenses = Math.max(0,Number(values.project_expenses)||0),margin=Number(values.margin_pct)||0,fees=Number(values.fees_pct)||0;
    const monthly=Math.max(0,Number(values.monthly_cost)||0),rate=1-(margin+fees)/100;
    return {hours:qty*hours, cost:qty*hours*cost*(1+reserve/100)+expenses,
      setup:rate>0?(qty*hours*cost*(1+reserve/100)+expenses)/rate:NaN,
      month:rate>0?monthly/rate:NaN};
  }
  function totals(){
    const form=document.getElementById('quote-form'),box=document.getElementById('quote-pricing-result');
    if(!form||!box)return;
    const v=Object.fromEntries(new FormData(form).entries()),items=[...form.querySelectorAll('[data-quote-line]')];
    const quantity=items.reduce((s,line)=>s+Math.max(0,Number(line.querySelector('[name="quantity"]').value)||0)*Math.max(0,Number(line.querySelector('[name="hours_per_unit"]').value)||0),0);
    const cost=quantity*Math.max(0,Number(v.hourly_cost)||0)*(1+(Number(v.reserve_pct)||0)/100)+Math.max(0,Number(v.project_expenses)||0);
    const rate=1-((Number(v.margin_pct)||0)+(Number(v.fees_pct)||0))/100;
    box.innerHTML=rate<=0?'<strong class="quote-error">Margem + tributos/taxas devem ser inferiores a 100%.</strong>':
      '<div><span>Horas estimadas</span><strong>'+quantity.toLocaleString('pt-BR')+' h</strong></div>'+
      '<div><span>Custo interno estimado</span><strong>'+curr(cost)+'</strong></div>'+
      '<div class="quote-highlight"><span>Preço de desenvolvimento</span><strong>'+curr(cost/rate)+'</strong></div>'+
      '<div><span>Mensalidade, se contratada</span><strong>'+curr((Number(v.monthly_cost)||0)/rate)+'</strong></div>'+
      '<p class="muted">Margem projetada e tributos/taxas são premissas. Os custos internos não constam no PDF.</p>';
  }
  function rowQ(item,index){
    const it=item||{title:'',quantity:1,hours_per_unit:0};
    return '<div class="quote-line" data-quote-line><span class="quote-step">Etapa '+(index+1)+'</span>'+
      fieldQ('title','Descrição *',it.title,'text','required minlength="2" maxlength="180"')+
      fieldQ('quantity','Quantidade *',it.quantity,'number','min="1" max="1000" step="1" required')+
      fieldQ('hours_per_unit','Horas por unidade *',it.hours_per_unit,'number','min="0" max="100000" step="0.25" required')+
      '<button type="button" class="secondary quote-remove" data-quote-action="remove-line" aria-label="Remover etapa">'+icon('trash')+'</button></div>';
  }
  function editor(){
    const q=editing||{},items=q.items?.length?q.items:[{title:'Desenvolvimento do aplicativo',quantity:1,hours_per_unit:20}];
    return '<section class="panel quote-editor"><div class="panel-head"><h2>'+(q.id?'Editar '+clean(q.number):'Novo orçamento')+'</h2><button type="button" class="secondary" data-quote-action="close-editor">Fechar</button></div>'+
      '<form id="quote-form" class="quote-form"><div class="quote-section"><h3>Cliente e proposta</h3><div class="quote-grid">'+
      fieldQ('client_name','Cliente / empresa *',q.client_name||'','text','required minlength="2" maxlength="180"')+
      fieldQ('client_contact','Contato',q.client_contact||'','text','maxlength="140"')+
      fieldQ('client_email','E-mail do cliente',q.client_email||'','email','maxlength="180"')+
      fieldQ('project_name','Nome do projeto *',q.project_name||'','text','required minlength="2" maxlength="180"')+
      areaQ('scope','Descrição do escopo *',q.scope||'','required minlength="5" maxlength="5000"')+
      fieldQ('delivery_days','Prazo de entrega (dias) *',q.delivery_days??30,'number','min="1" max="3650" required')+
      fieldQ('validity_days','Validade da proposta (dias) *',q.validity_days??15,'number','min="1" max="365" required')+
      areaQ('payment_terms','Condições de pagamento',q.payment_terms??'A combinar','maxlength="1500"')+
      areaQ('assumptions','Premissas, exclusões e limite de ajustes',q.assumptions||'','maxlength="3000"')+
      '<label>Situação comercial'+statusOptions(q.status||'rascunho')+'</label></div></div>'+
      '<div class="quote-section"><div class="quote-row"><h3>Etapas e horas previstas</h3><button type="button" class="secondary" data-quote-action="add-line">'+icon('plus')+' Adicionar etapa</button></div>'+
      '<div id="quote-lines">'+items.map(rowQ).join('')+'</div></div>'+
      '<div class="quote-section quote-internal"><h3>Precificação interna — não aparece no PDF</h3><p class="muted">A hora interna deve incluir remuneração e despesas fixas alocadas. Não inclua novamente os mesmos custos nas despesas do projeto.</p>'+
      '<div class="quote-grid">'+fieldQ('hourly_cost','Custo interno por hora (R$) *',q.hourly_cost??60,'number','min="0.01" max="100000" step="0.01" required')+
      fieldQ('reserve_pct','Reserva adicional (%)',q.reserve_pct??15,'number','min="0" max="100" step="0.01" required')+
      fieldQ('project_expenses','Despesas específicas (R$)',q.project_expenses??0,'number','min="0" max="10000000" step="0.01" required')+
      fieldQ('margin_pct','Margem desejada (%)',q.margin_pct??25,'number','min="0" max="95" step="0.01" required')+
      fieldQ('fees_pct','Tributos e taxas estimados (%)',q.fees_pct??8,'number','min="0" max="95" step="0.01" required')+
      fieldQ('monthly_cost','Custo mensal (R$; zero = não cobrar mensalidade)',q.monthly_cost??0,'number','min="0" max="10000000" step="0.01" required')+
      fieldQ('monthly_description','Serviço mensal',q.monthly_description??'Hospedagem, suporte e manutenção','text','maxlength="500"')+
      '</div><div id="quote-pricing-result" class="quote-result" aria-live="polite"></div></div>'+
      '<div class="quote-actions"><button type="button" class="secondary" data-quote-action="close-editor">Cancelar</button><button class="primary" type="submit">'+icon('file')+' Salvar orçamento</button></div></form></section>';
  }
  function list(){
    if(!loaded)return '<section class="panel"><p class="muted">Carregando orçamentos...</p></section>';
    if(!quotes.length)return '<section class="panel">'+empty('Nenhum orçamento cadastrado','Crie o primeiro orçamento para calcular seu preço e gerar o PDF comercial.')+'</section>';
    return '<section class="panel"><div class="panel-head"><h2>Propostas comerciais</h2><span class="muted">'+quotes.length+' registro(s)</span></div>'+
      '<div class="quote-table-wrap"><table class="quote-table"><thead><tr><th>Orçamento</th><th>Cliente / projeto</th><th>Situação</th><th>Desenvolvimento</th><th>Mensalidade</th><th>Ações</th></tr></thead><tbody>'+
      quotes.map(q=>'<tr><td><strong>'+clean(q.number)+'</strong><small>'+fmtDate(q.created_at.slice(0,10))+'</small></td>'+
      '<td><strong>'+clean(q.project_name)+'</strong><small>'+clean(q.client_name)+'</small></td>'+
      '<td><span class="quote-pill quote-'+clean(q.effective_status)+'">'+clean(statusText[q.effective_status]||q.effective_status)+'</span></td>'+
      '<td>'+curr(q.pricing.setup_price)+'</td><td>'+curr(q.pricing.monthly_price)+'</td>'+
      '<td class="quote-controls"><button class="secondary" type="button" data-quote-action="edit" data-id="'+q.id+'">Editar</button>'+
      (!q.project_id&&q.status!=='aprovado'&&q.status!=='recusado'?'<button class="secondary" type="button" data-quote-action="decision" data-status="aprovado" data-id="'+q.id+'">Aprovar</button>'+
      '<button class="secondary" type="button" data-quote-action="decision" data-status="recusado" data-id="'+q.id+'">Recusar</button>':'')+
      (!q.project_id&&q.status==='recusado'?'<button class="secondary" type="button" data-quote-action="decision" data-status="rascunho" data-id="'+q.id+'">Retomar negociação</button>':'')+
      '<a class="secondary quote-pdf" href="/api/quotes/'+q.id+'/pdf" download="orcamento-'+clean(q.number)+'.pdf">'+icon('download')+' PDF</a>'+
      (q.status==='aprovado'&&!q.project_id?'<button class="secondary" type="button" data-quote-action="convert" data-id="'+q.id+'">Criar projeto</button>':'')+
      (q.project_id?'<button class="secondary" type="button" data-route="projetos">Ver projeto</button>':'')+
      (q.status!=='aprovado'&&!q.project_id?'<button class="secondary quote-delete" type="button" data-quote-action="delete" data-id="'+q.id+'" aria-label="Excluir orçamento">'+icon('trash')+'</button>':'')+
      '</td></tr>').join('')+'</tbody></table></div></section>';
  }
  function companyForm(){
    const p=company||{},f=(name,title,type,extra)=>fieldQ(name,title,p[name]||'',type,extra);
    return '<section class="panel quote-company"><div class="panel-head"><h2>Dados da empresa para o PDF</h2><button class="secondary" type="button" data-quote-action="company-toggle">Fechar</button></div>'+
      '<p class="muted">Personalize apenas o documento comercial. A identidade visual do aplicativo permanece inalterada enquanto o nome da empresa é definido.</p>'+
      '<form id="quote-company-form"><div class="quote-grid">'+
      f('name','Nome exibido na proposta *','text','required maxlength="160" minlength="2"')+
      f('subtitle','Subtítulo','text','maxlength="180"')+
      f('document','CNPJ / documento (opcional)','text','maxlength="40"')+
      f('email','E-mail comercial','email','maxlength="180"')+
      f('phone','Telefone','text','maxlength="80"')+
      f('website','Site','text','maxlength="180"')+
      f('address','Endereço','text','maxlength="240"')+
      '<label>Logo do PDF (PNG/JPEG, até 300 KB)<input type="file" name="logo_upload" accept="image/png,image/jpeg"></label>'+
      '</div><div class="quote-actions"><button type="button" class="secondary" data-quote-action="remove-logo">Remover logo do PDF</button><button type="submit" class="primary">Salvar dados comerciais</button></div></form></section>';
  }
  function page(){
    if(!loaded&&!loading)load();
    return heading('Orçamentos','Calcule o preço internamente e gere uma proposta comercial em PDF.','<button class="primary" data-quote-action="new">'+icon('plus')+' Novo orçamento</button>')+
      '<div class="quote-toolbar"><span>Desenvolvimento, implantação e mensalidade apresentados separadamente.</span><button class="secondary" data-quote-action="company-toggle">'+icon('settings')+' Dados da empresa no PDF</button></div>'+
      (showCompany?companyForm():'')+(showEditor?editor():'')+list();
  }
  async function load(){
    if(loading)return;
    loading=true;
    try {
      const [q,c]=await Promise.all([api('/quotes'),api('/quotes/settings/company')]);
      quotes=q;company=c;loaded=true;
    }catch(err){notice(err.message);}
    finally{loading=false;if(route==='orcamentos'){render();if(showEditor)totals();}}
  }
  function formPayload(form){
    const payload=Object.fromEntries(new FormData(form).entries());
    payload.items=[...form.querySelectorAll('[data-quote-line]')].map(line=>({
      title:line.querySelector('[name="title"]').value.trim(),
      quantity:Number(line.querySelector('[name="quantity"]').value),
      hours_per_unit:Number(line.querySelector('[name="hours_per_unit"]').value)
    }));
    ['delivery_days','validity_days'].forEach(k=>payload[k]=Number(payload[k]));
    ['hourly_cost','reserve_pct','project_expenses','margin_pct','fees_pct','monthly_cost'].forEach(k=>payload[k]=Number(payload[k]));
    return payload;
  }
  document.addEventListener('click',async event=>{
    const button=event.target.closest('[data-quote-action]');
    if(!button)return;
    const action=button.dataset.quoteAction,id=Number(button.dataset.id);
    if(action==='new'){editing=null;showEditor=true;showCompany=false;render();totals();return;}
    if(action==='edit'){
      editing=quotes.find(q=>q.id===id);
      if(editing?.project_id){notice('A proposta já foi convertida em projeto. Crie um novo orçamento para alterá-la.');return;}
      showEditor=true;showCompany=false;render();totals();return;
    }
    if(action==='close-editor'){showEditor=false;editing=null;render();return;}
    if(action==='company-toggle'){showCompany=!showCompany;showEditor=false;render();return;}
    if(action==='add-line'){
      const host=document.getElementById('quote-lines');
      if(host.children.length>=40){notice('Limite de 40 etapas por orçamento.');return;}
      host.insertAdjacentHTML('beforeend',rowQ(null,host.children.length));totals();return;
    }
    if(action==='remove-line'){
      const host=document.getElementById('quote-lines');
      if(host.children.length<=1){notice('Mantenha pelo menos uma etapa.');return;}
      button.closest('[data-quote-line]').remove();
      [...host.children].forEach((line,i)=>line.querySelector('.quote-step').textContent='Etapa '+(i+1));
      totals();return;
    }
    if(action==='delete' && confirm('Excluir este orçamento em elaboração?')){
      try{await api('/quotes/'+id,{method:'DELETE'});notice('Orçamento excluído.');await load();}catch(err){notice(err.message);}
      return;
    }
    if(action==='decision'){
      const quote=quotes.find(q=>q.id===id);
      const status=button.dataset.status;
      if(!quote||!['aprovado','recusado','rascunho'].includes(status))return;
      if(quote.project_id){notice('Orçamento já convertido em projeto.');return;}
      const label={aprovado:'Aprovar',recusado:'Recusar',rascunho:'Retomar negociação'}[status];
      if(!confirm(label+' a proposta '+quote.number+'?'))return;
      button.disabled=true;
      try{
        const updated=await api('/quotes/'+id,{
          method:'PUT',body:JSON.stringify({...quote,status})
        });
        await load();
        notice(updated.status==='aprovado'?'Proposta aprovada. Você já pode criar o projeto.':
          updated.status==='recusado'?'Proposta recusada e mantida no histórico.':'Negociação retomada.');
      }catch(err){notice(err.message);}
      finally{button.disabled=false;}
      return;
    }
    if(action==='convert' && confirm('Criar um projeto a partir deste orçamento aprovado?')){
      try{await api('/quotes/'+id+'/project',{method:'POST'});notice('Projeto criado.');await refresh();await load();}catch(err){notice(err.message);}
      return;
    }
    if(action==='remove-logo'){
      if(!company)company={};
      company.logo_data='';
      notice('Logo removida da prévia. Salve os dados comerciais para confirmar.');return;
    }
  });
  document.addEventListener('input',event=>{
    if(event.target.closest('#quote-form'))totals();
  });
  document.addEventListener('submit',async event=>{
    const form=event.target;
    if(form.id!=='quote-form'&&form.id!=='quote-company-form')return;
    event.preventDefault();
    if(form.id==='quote-form'){
      const values=formPayload(form),rate=values.margin_pct+values.fees_pct;
      if(rate>=100){notice('Margem mais tributos/taxas deve ser inferior a 100%.');return;}
      if(!values.items.some(x=>x.hours_per_unit>0)){notice('Informe horas previstas em pelo menos uma etapa.');return;}
      if(editing?.project_id){notice('O orçamento já foi convertido em projeto.');return;}
      try{
        const id=editing?.id;
        await api('/quotes'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify(values)});
        showEditor=false;editing=null;
        notice(id?'Orçamento atualizado.':'Orçamento salvo; o PDF já pode ser gerado.');
        await load();
      }catch(err){notice(err.message);}
      return;
    }
    try{
      const values=Object.fromEntries(new FormData(form).entries());
      delete values.logo_upload;
      values.logo_data=company?.logo_data||'';
      const file=form.querySelector('[name="logo_upload"]').files[0];
      if(file){
        if(!['image/png','image/jpeg'].includes(file.type)||file.size>300000)throw Error('Envie PNG ou JPEG de até 300 KB.');
        values.logo_data=await new Promise((resolve,reject)=>{
          const reader=new FileReader();
          reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(Error('Falha ao ler a imagem.'));
          reader.readAsDataURL(file);
        });
      }
      company=await api('/quotes/settings/company',{method:'PUT',body:JSON.stringify(values)});
      showCompany=false;render();notice('Dados comerciais para o PDF salvos.');
    }catch(err){notice(err.message);}
  });
  return {page,load};
})();
