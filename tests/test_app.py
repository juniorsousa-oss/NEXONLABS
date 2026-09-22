import os
import tempfile
os.environ['DATABASE_URL'] = 'sqlite:///' + tempfile.mkstemp(prefix='nexon_test_', suffix='.db')[1]
os.environ['APP_PASSWORD'] = 'test-password'
os.environ['SESSION_SECRET'] = 'test-key-with-sufficient-length'
from fastapi.testclient import TestClient
from app import app

def test_health_and_protected_routes():
    c=TestClient(app)
    assert c.get('/health').json()=={'status':'ok'}
    assert c.get('/api/state').status_code==401
    assert c.post('/api/login',json={'password':'wrong'}).status_code==401
    assert c.post('/api/login',json={'password':'test-password'}).status_code==200
    assert c.get('/api/state').status_code==200

def test_project_task_member_lifecycle():
    with TestClient(app) as c:
        c.post('/api/login',json={'password':'test-password'})
        p=c.post('/api/projects',json={'name':'App gestão','client':'Cliente 1','owner':'Júnior','status':'planejamento','progress':30,'due_at':'2027-12-31'})
        assert p.status_code==201,p.text
        p=p.json(); pid=p['id']
        assert c.get('/api/state').json()['projects'][0]['name']=='App gestão'
        t=c.post('/api/tasks',json={'project_id':pid,'title':'Criar tela','hours':2.5})
        assert t.status_code==201,t.text
        tid=t.json()['id']
        assert c.put(f'/api/tasks/{tid}',json={'project_id':pid,'title':'Criar tela','hours':3,'completed':True}).json()['completed']
        assert c.post('/api/members',json={'name':'Júnior'}).status_code==201
        assert 'App gestão' in c.get('/api/export/projects.csv').text
        assert c.delete(f'/api/projects/{pid}').status_code==200
        assert c.get('/api/state').json()['tasks']==[]

def test_validation_and_markup():
    with TestClient(app) as c:
        c.post('/api/login',json={'password':'test-password'})
        assert c.post('/api/projects',json={'name':'x','progress':101}).status_code==422
        assert c.post('/api/projects',json={'name':'Teste','started_at':'2027-10-02','due_at':'2027-10-01'}).status_code==422
        assert 'NEXON' in c.get('/').text
        assert 'DESIGN LOCK v1' in c.get('/static/style.css').text

def test_meetings_calendar_and_client_agenda():
    with TestClient(app) as c:
        assert c.post('/api/meetings', json={
            'title':'Reunião não autenticada','meeting_date':'2026-10-01',
            'start_time':'09:00','end_time':'10:00'
        }).status_code == 401
        assert c.post('/api/login',json={'password':'test-password'}).status_code == 200
        project = c.post('/api/projects',json={'name':'Cliente piloto'}).json()
        data = {
            'title':'Diagnóstico com cliente','client':'Indústria Alfa',
            'project_id':project['id'],'meeting_date':'2026-10-01',
            'start_time':'09:00','end_time':'10:00',
            'location':'Online','meeting_url':'https://meet.example.com/teste',
            'notes':'Levantamento inicial das necessidades'
        }
        created = c.post('/api/meetings',json=data)
        assert created.status_code == 201, created.text
        mid=created.json()['id']
        meetings=c.get('/api/state').json()['meetings']
        assert any(m['id']==mid and m['client']=='Indústria Alfa' for m in meetings)
        invalid=c.post('/api/meetings',json={**data,'start_time':'11:00','end_time':'10:00'})
        assert invalid.status_code == 422
        bad_link=c.post('/api/meetings',json={**data,'meeting_url':'javascript:alert(1)'})
        assert bad_link.status_code == 422
        edited=c.put(f'/api/meetings/{mid}',json={**data,'title':'Reunião de alinhamento','meeting_date':'2026-10-02'})
        assert edited.status_code == 200, edited.text
        assert edited.json()['meeting_date']=='2026-10-02'
        assert c.delete(f'/api/meetings/{mid}').status_code==200
        assert not any(m['id']==mid for m in c.get('/api/state').json()['meetings'])
        assert c.delete(f'/api/projects/{project["id"]}').status_code==200


def test_quote_pricing_pdf_company_and_conversion():
    from io import BytesIO
    from pypdf import PdfReader
    with TestClient(app) as client:
        payload = {
            "client_name":"Cliente Exemplo","client_contact":"Ana","client_email":"ana@example.com",
            "project_name":"Aplicativo de estoque","scope":"Desenvolver controle de estoque com relatórios.",
            "delivery_days":30,"validity_days":15,"payment_terms":"50% de entrada; 50% na entrega",
            "assumptions":"Até duas rodadas de ajustes no escopo.",
            "items":[{"title":"Desenvolvimento do aplicativo","quantity":1,"hours_per_unit":"72.00"}],
            "hourly_cost":"60.00","reserve_pct":"15.00","project_expenses":"300.00",
            "margin_pct":"25.00","fees_pct":"8.00",
            "monthly_cost":"200.00","monthly_description":"Hospedagem e suporte mensal",
            "status":"rascunho"
        }
        assert client.get("/api/quotes").status_code == 401
        assert client.get("/api/quotes/1/pdf").status_code == 401
        assert client.put("/api/quotes/settings/company",json={"name":"Teste"}).status_code == 401
        client.post("/api/login",json={"password":"test-password"})
        company = client.put("/api/quotes/settings/company",json={
            "name":"Marca provisória", "subtitle":"Soluções digitais",
            "email":"contato@example.com","logo_data":""
        })
        assert company.status_code == 200,company.text
        bad_logo=client.put("/api/quotes/settings/company",json={"name":"Marca provisória","logo_data":"data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="})
        assert bad_logo.status_code == 422
        invalid=client.post("/api/quotes",json={**payload,"margin_pct":"95.00","fees_pct":"8.00"})
        assert invalid.status_code == 422
        no_hours=client.post("/api/quotes",json={**payload,"items":[{"title":"Etapa sem horas","quantity":1,"hours_per_unit":0}]})
        assert no_hours.status_code == 422
        quote=client.post("/api/quotes",json=payload)
        assert quote.status_code == 201,quote.text
        q=quote.json()
        assert round(q["pricing"]["total_hours"],2)==72
        assert round(q["pricing"]["total_cost"],2)==5268
        assert round(q["pricing"]["setup_price"],2)==7862.69
        assert round(q["pricing"]["monthly_price"],2)==298.51
        assert q["number"].startswith("ORC-")
        assert q["id"] in [x["id"] for x in client.get("/api/quotes").json()]
        pdf=client.get(f"/api/quotes/{q['id']}/pdf")
        assert pdf.status_code == 200,pdf.text
        assert pdf.content.startswith(b"%PDF")
        assert "attachment;" in pdf.headers["content-disposition"]
        doc=PdfReader(BytesIO(pdf.content))
        text_pdf="\n".join((page.extract_text() or "") for page in doc.pages)
        for visible in ("Marca provisória", "Cliente Exemplo", "Aplicativo de estoque",
                        "7.862,69", "298,51", "Hospedagem e suporte mensal", q["number"]):
            assert visible in text_pdf,visible
        for private in ("Custo interno", "Margem desejada", "Reserva adicional", "72.00"):
            assert private not in text_pdf
        edited=client.put(f"/api/quotes/{q['id']}",json={**payload,"status":"aprovado"})
        assert edited.status_code == 200,edited.text
        project=client.post(f"/api/quotes/{q['id']}/project")
        assert project.status_code == 201,project.text
        assert project.json()["name"] == "Aplicativo de estoque"
        assert client.post(f"/api/quotes/{q['id']}/project").status_code == 409
        assert client.put(f"/api/quotes/{q['id']}",json=payload).status_code == 409
        assert client.delete(f"/api/quotes/{q['id']}").status_code == 409
        assert any(p["id"] == project.json()["id"] for p in client.get("/api/state").json()["projects"])
