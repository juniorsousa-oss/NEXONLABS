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


def test_tickets_lifecycle_audit_and_permissions():
    with TestClient(app) as c:
        payload = {
            "title":"Ajustar relatório de estoque",
            "client":"Cliente Alfa",
            "requester":"Marina",
            "contact":"marina@example.com",
            "description":"O relatório apresenta divergência entre saldos e movimentos.",
            "type":"erro",
            "priority":"alta",
            "status":"aberto",
            "assignee":"Suporte",
            "project_id":None,
            "due_at":"2026-10-15",
        }
        assert c.get("/api/tickets").status_code == 401
        assert c.post("/api/tickets", json=payload).status_code == 401
        assert c.post("/api/login", json={"password":"test-password"}).status_code == 200
        missing=c.post("/api/tickets",json={**payload,"project_id":99999999})
        assert missing.status_code==422
        invalid=c.post("/api/tickets",json={**payload,"description":"x"})
        assert invalid.status_code==422
        project=c.post("/api/projects",json={"name":"Aplicativo do cliente"}).json()
        payload["project_id"]=project["id"]
        created=c.post("/api/tickets",json=payload)
        assert created.status_code==201,created.text
        ticket=created.json()
        tid=ticket["id"]
        assert ticket["number"].startswith("CH-")
        assert ticket["status"]=="aberto"
        assert len(ticket["events"])==1
        assert ticket["events"][0]["kind"]=="abertura"
        assert any(t["id"]==tid for t in c.get("/api/tickets").json())
        comment=c.post(f"/api/tickets/{tid}/comments",json={"message":"  Solicitado print ao cliente.  "})
        assert comment.status_code==201,comment.text
        assert comment.json()["events"][-1]["message"]=="Solicitado print ao cliente."
        changed=c.put(f"/api/tickets/{tid}",json={
            **payload,"status":"em_atendimento","assignee":"Júnior","priority":"critica"
        })
        assert changed.status_code==200,changed.text
        assert changed.json()["status"]=="em_atendimento"
        assert any("Situação" in e["message"] for e in changed.json()["events"])
        assert any(e["kind"]=="comentario" for e in changed.json()["events"])
        # Fechamento e reabertura exigem um motivo registrado.
        assert c.put(f"/api/tickets/{tid}",json={**payload,"status":"fechado"}).status_code==422
        assert c.post(f"/api/tickets/{tid}/transition",json={"status":"fechado","message":" "}).status_code==422
        closed=c.post(f"/api/tickets/{tid}/transition",json={
            "status":"fechado","message":"Corrigida divergência dos saldos e validado com o cliente."
        })
        assert closed.status_code==200,closed.text
        assert closed.json()["closed_at"]
        assert closed.json()["status"]=="fechado"
        assert len(closed.json()["events"])==4
        assert closed.json()["events"][-1]["kind"]=="situacao"
        assert "Corrigida divergência" in closed.json()["events"][-1]["message"]
        assert c.post(f"/api/tickets/{tid}/transition",json={"status":"fechado","message":"Mesmo chamado"}).status_code==409
        assert c.put(f"/api/tickets/{tid}",json={**payload,"status":"aberto"}).status_code==422
        assert c.post(f"/api/tickets/{tid}/transition",json={"status":"aguardando_cliente","message":"Tentar editar fechado"}).status_code==409
        reopened=c.post(f"/api/tickets/{tid}/transition",json={
            "status":"aberto","message":"Cliente relatou recorrência do erro; investigar novamente."
        })
        assert reopened.status_code==200,reopened.text
        assert reopened.json()["status"]=="aberto"
        assert reopened.json()["closed_at"] is None
        assert reopened.json()["events"][-1]["kind"]=="situacao"
        assert len(reopened.json()["events"])==5
        solved=c.post(f"/api/tickets/{tid}/transition",json={
            "status":"resolvido","message":"Nova validação feita, divergência eliminada."
        })
        assert solved.status_code==200,solved.text
        assert solved.json()["closed_at"] is None
        assert solved.json()["status"]=="resolvido"
        finalized=c.post(f"/api/tickets/{tid}/transition",json={
            "status":"fechado","message":"Cliente confirmou recebimento e atendimento encerrado."
        })
        assert finalized.status_code==200,finalized.text
        assert finalized.json()["closed_at"] is not None
        assert c.post(f"/api/tickets/{tid}/comments",json={"message":" "}).status_code==422
        assert c.post("/api/tickets/99999999/comments",json={"message":"Teste"}).status_code==404
        assert c.delete(f"/api/projects/{project['id']}").status_code==200
        after=c.get("/api/tickets").json()
        assert next(t for t in after if t["id"]==tid)["project_id"] is None


def test_password_identifies_each_person_and_enforces_permissions():
    from accounts_module import verify_password
    from app import Account, DB
    with TestClient(app) as anonymous:
        assert 'Senha de acesso' in anonymous.get('/').text
        assert anonymous.get('/api/state').status_code == 401
        assert anonymous.get('/api/accounts').status_code == 401
        assert anonymous.post('/api/accounts',json={
            'name':'Usuário indevido','password':'indevia123'
        }).status_code == 401
        assert anonymous.post('/api/login',json={'password':'wrong'}).status_code == 401

    with TestClient(app) as admin:
        response=admin.post('/api/login',json={'password':'test-password'})
        assert response.status_code==200,response.text
        assert response.json()['user']['role']=='admin'
        assert admin.get('/').status_code==200
        initial=admin.get('/api/state').json()
        assert initial['user_id']==response.json()['user']['id']
        assert initial['user_role']=='admin'
        assert initial['user']==response.json()['user']['name']
        users_before=admin.get('/api/accounts')
        assert users_before.status_code==200
        assert users_before.json()
        assert all('password' not in u for u in users_before.json())
        same=admin.post('/api/accounts',json={'name':'Senha duplicada','password':'test-password'})
        assert same.status_code==409
        created=admin.post('/api/accounts',json={
            'name':'Bianca','password':'senha-distinta-987','role':'usuario'
        })
        assert created.status_code==201,created.text
        new_user=created.json()
        assert new_user['name']=='Bianca'
        assert new_user['role']=='usuario'
        assert 'password' not in new_user
        with DB() as db:
            user=db.get(Account,new_user['id'])
            assert user.password_hash!='senha-distinta-987'
            assert verify_password('senha-distinta-987',user.password_hash)

        with TestClient(app) as employee:
            assert employee.get('/api/state').status_code==401
            logged=employee.post('/api/login',json={'password':'senha-distinta-987'})
            assert logged.status_code==200,logged.text
            assert logged.json()['user']['name']=='Bianca'
            profile=employee.get('/api/state').json()
            assert profile['user']=='Bianca'
            assert profile['user_role']=='usuario'
            assert profile['user_id']==new_user['id']
            assert employee.get('/api/accounts').status_code==403
            assert employee.post('/api/accounts',json={
                'name':'Invasor','password':'outra-senha-valida'
            }).status_code==403
            renamed=employee.put('/api/profile',json={'name':'Bianca Beatriz'})
            assert renamed.status_code==200,renamed.text
            assert employee.get('/api/state').json()['user']=='Bianca Beatriz'
            assert employee.put('/api/profile',json={
                'name':'Bianca Beatriz','current_password':'errada',
                'new_password':'senha-alterada-123'
            }).status_code==403
            pwd=employee.put('/api/profile',json={
                'name':'Bianca Beatriz','current_password':'senha-distinta-987',
                'new_password':'senha-alterada-123'
            })
            assert pwd.status_code==200,pwd.text
            assert employee.get('/api/state').status_code==200
            assert employee.post('/api/logout').status_code==200
            assert employee.get('/').text.find('Senha de acesso')>=0
            assert employee.post('/api/login',json={'password':'senha-distinta-987'}).status_code==401
            assert employee.post('/api/login',json={'password':'senha-alterada-123'}).status_code==200
            assert employee.get('/api/state').json()['user']=='Bianca Beatriz'

            assert admin.put(f"/api/accounts/{new_user['id']}",json={
                'name':'Bianca Beatriz','role':'usuario','active':False
            }).status_code==200
            assert employee.get('/api/state').status_code==401
            assert employee.get('/').text.find('Senha de acesso')>=0
            assert employee.post('/api/login',json={'password':'senha-alterada-123'}).status_code==401
            assert admin.put(f"/api/accounts/{new_user['id']}",json={
                'name':'Bianca Beatriz','role':'usuario','active':True,
                'new_password':'nova-senha-pessoal-321'
            }).status_code==200
            assert employee.post('/api/login',json={'password':'nova-senha-pessoal-321'}).status_code==200
            assert employee.get('/api/state').json()['user']=='Bianca Beatriz'
        assert admin.put(f"/api/accounts/{response.json()['user']['id']}",json={
            'name':'Administrador','role':'usuario','active':False
        }).status_code==409
        assert admin.get('/api/state').json()['user_role']=='admin'


def test_user_avatar_upload_is_private_normalized_and_removable():
    import base64
    import io
    from PIL import Image
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/profile/avatar').status_code == 401
        assert anonymous.put('/api/profile/avatar',json={'photo_data':'not-an-image'}).status_code == 401
        assert anonymous.delete('/api/profile/avatar').status_code == 401
    with TestClient(app) as admin:
        assert admin.post('/api/login',json={'password':'test-password'}).status_code == 200
        assert admin.get('/api/state').json()['has_photo'] is False
        assert admin.get('/api/profile/avatar').status_code == 404
        bad = admin.put('/api/profile/avatar',json={
            'photo_data':'data:image/png;base64,' + base64.b64encode(b'not a png').decode()
        })
        assert bad.status_code == 422, bad.text
        invalid_type = admin.put('/api/profile/avatar',json={
            'photo_data':'data:image/svg+xml;base64,' + base64.b64encode(b'<svg/>').decode()
        })
        assert invalid_type.status_code == 422
        image=Image.new('RGB',(800,600),color=(30,90,150))
        output=io.BytesIO()
        image.save(output,format='PNG')
        photo_data='data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()
        saved=admin.put('/api/profile/avatar',json={'photo_data':photo_data})
        assert saved.status_code == 200, saved.text
        assert saved.json()['has_photo'] is True
        avatar=admin.get('/api/profile/avatar')
        assert avatar.status_code == 200
        assert avatar.headers['content-type'].startswith('image/jpeg')
        assert avatar.headers['cache-control']=='private, no-store'
        assert avatar.content.startswith(b'\xff\xd8')
        actual=Image.open(io.BytesIO(avatar.content))
        assert max(actual.size)<=320
        assert admin.get('/api/state').json()['has_photo'] is True
        other=admin.post('/api/accounts',json={
            'name':'Perfil sem foto','password':'foto-individual-123','role':'usuario'
        })
        assert other.status_code == 201,other.text
        with TestClient(app) as employee:
            assert employee.post('/api/login',json={'password':'foto-individual-123'}).status_code == 200
            assert employee.get('/api/state').json()['has_photo'] is False
            assert employee.get('/api/profile/avatar').status_code == 404
            assert employee.put('/api/profile/avatar',json={'photo_data':photo_data}).status_code == 200
            assert employee.get('/api/state').json()['has_photo'] is True
            assert employee.delete('/api/profile/avatar').status_code == 200
            assert employee.get('/api/profile/avatar').status_code == 404
            assert employee.get('/api/state').json()['has_photo'] is False
        # A foto do administrador não é alterada pelo segundo usuário.
        assert admin.get('/api/profile/avatar').content == avatar.content
        assert admin.delete('/api/profile/avatar').status_code == 200
        assert admin.get('/api/state').json()['has_photo'] is False
        assert admin.get('/api/profile/avatar').status_code == 404


def test_same_password_on_independent_devices_and_session_cookie():
    """Simula computadores, celulares e navegador novo na mesma instalação."""
    with TestClient(app) as admin:
        login = admin.post('/api/login', json={'password':'test-password'})
        assert login.status_code == 200, login.text
        user = admin.post('/api/accounts', json={
            'name':'Acesso multiplataforma','password':'Acesso-Portatil-736',
            'role':'usuario'
        })
        assert user.status_code == 201, user.text
        uid = user.json()['id']
        # Cada cliente tem cookies próprios e user-agent diferente.
        with TestClient(app, headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0) Chrome/126'}) as desktop, \
             TestClient(app, headers={'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile Safari'}) as phone, \
             TestClient(app, headers={'User-Agent':'Mozilla/5.0 (Linux; Android 15) Chrome/126 Mobile'}) as other:
            for browser in (desktop, phone, other):
                assert 'Senha de acesso' in browser.get('/').text
                response=browser.post('/api/login',json={'password':'Acesso-Portatil-736'})
                assert response.status_code==200, response.text
                assert response.json()['user']['id']==uid
                state=browser.get('/api/state')
                assert state.status_code==200, state.text
                assert state.json()['user_id']==uid
                assert state.json()['user']=='Acesso multiplataforma'
                assert '<main class="main" id="main"' in browser.get('/').text
            # Alterar a senha encerra as sessões anteriores de todos os dispositivos.
            updated=admin.put(f'/api/accounts/{uid}',json={
                'name':'Acesso multiplataforma','role':'usuario','active':True,
                'new_password':'Senha-Nova-736'
            })
            assert updated.status_code==200, updated.text
            for browser in (desktop,phone,other):
                assert browser.get('/api/state').status_code==401
                assert browser.post('/api/login',json={'password':'Acesso-Portatil-736'}).status_code==401
                assert browser.post('/api/login',json={'password':'Senha-Nova-736'}).status_code==200
                assert browser.get('/api/state').json()['user_id']==uid


def test_login_error_page_distinguishes_password_and_server_failures():
    with TestClient(app) as client:
        page=client.get('/')
        assert page.status_code==200
        source=page.text
        assert 'response.status===401' in source
        assert 'response.status===429' in source
        assert 'response.status>=500' in source
        assert "fetch('/api/state'" in source
        assert 'este navegador não manteve a sessão' in source


def test_colaborador_brand_kit_aprovado():
    """Pessoa com cadastro existente recebe novos campos sem quebra de dados,
    e PDFs/PNGs/HTML só são fornecidos em sessão autenticada."""
    from io import BytesIO
    from PIL import Image
    from pypdf import PdfReader
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/members/1/brand/card?format=pdf').status_code==401
        assert anonymous.get('/api/members/1/brand/signature?format=png').status_code==401
    with TestClient(app) as client:
        assert client.post('/api/login',json={'password':'test-password'}).status_code==200
        existing=client.post('/api/members',json={'name':'Colaborador pré-existente','role':'Operações'})
        assert existing.status_code==201,existing.text
        existing_id=existing.json()['id']
        previous=next(x for x in client.get('/api/state').json()['members'] if x['id']==existing_id)
        assert previous['whatsapp']==''
        assert previous['name']=='Colaborador pré-existente'
        assert previous['city']=='Patos de Minas - MG'
        assert previous['site']=='https://nexonlabs.onrender.com'

        invalid=client.post('/api/members',json={
            'name':'Pessoa com link inválido','site':'javascript:alert(1)'
        })
        assert invalid.status_code==422
        payload={
            'name':'Júnior Andrade','role':'CEO | Diretor de Criação e Branding',
            'email':'','whatsapp':'(34) 99662-1546',
            'city':'Patos de Minas - MG','site':'https://nexonlabs.onrender.com'
        }
        user=client.post('/api/members',json=payload)
        assert user.status_code==201,user.text
        mid=user.json()['id']
        assert user.json()['whatsapp']==payload['whatsapp']
        assert user.json()['role']==payload['role']
        assert user.json()['email']==''
        root=f'/api/members/{mid}/brand/'
        for kind,size in (('front',(1134,661)),('back',(1134,661)),('signature',(1180,455))):
            response=client.get(root+kind+'?format=png')
            assert response.status_code==200,(kind,response.text[:150])
            assert response.headers['content-type']=='image/png'
            assert response.headers['cache-control']=='private, no-cache, must-revalidate'
            etag=response.headers['etag']
            cached=client.get(root+kind+'?format=png',headers={'If-None-Match':etag})
            assert cached.status_code==304
            assert cached.content==b''
            assert cached.headers['etag']==etag
            img=Image.open(BytesIO(response.content))
            assert img.size==size
        rendered=client.get(root+'card?format=pdf')
        assert rendered.status_code==200,rendered.text[:150]
        assert rendered.content.startswith(b'%PDF')
        pages=PdfReader(BytesIO(rendered.content)).pages
        assert len(pages)==2
        from reportlab.lib.units import mm
        assert abs(float(pages[0].mediabox.width)-96*mm)<0.1
        assert abs(float(pages[0].mediabox.height)-56*mm)<0.1
        html=client.get(root+'signature?format=html')
        assert html.status_code==200
        assert 'Júnior Andrade' in html.text
        assert 'https://wa.me/5534996621546' in html.text
        assert 'https://nexonlabs.onrender.com' in html.text
        assert 'data:image/png;base64,' in html.text
        assert client.get(root+'card?format=png').status_code==422
        assert client.get(root+'signature?format=pdf').status_code==422
        assert client.get('/api/members/999999/brand/card?format=pdf').status_code==404
        previous_etag=client.get(root+'signature?format=png').headers['etag']
        updated=client.put(f'/api/members/{mid}',json={
            **payload,'name':'Júnior Atualizado','whatsapp':'','city':'Uberlândia - MG',
            'site':'https://exemplo.com','email':'junior@example.com'
        })
        assert updated.status_code==200,updated.text
        assert updated.json()['whatsapp']==''
        assert updated.json()['site']=='https://exemplo.com'
        assert updated.json()['city']=='Uberlândia - MG'
        saved=next(x for x in client.get('/api/state').json()['members'] if x['id']==mid)
        assert saved['name']=='Júnior Atualizado'
        assert saved['email']=='junior@example.com'
        changed_image=client.get(root+'signature?format=png')
        assert changed_image.status_code==200
        # ETag antigo não pode devolver imagem com dados anteriores à edição.
        old_image_etag=client.get(root+'signature?format=png').headers['etag']
        assert changed_image.headers['etag']==old_image_etag
        assert changed_image.headers['etag']!=previous_etag
        stale=client.get(root+'signature?format=png',headers={'If-None-Match':previous_etag})
        assert stale.status_code==200
        assert stale.headers['etag']==changed_image.headers['etag']
        generated=client.get(root+'signature?format=html').text
        assert 'https://exemplo.com' in generated
        assert 'wa.me/' not in generated
        assert client.delete(f'/api/members/{mid}').status_code==200
        assert client.get(root+'card?format=pdf').status_code==404


def test_ticket_closure_requires_auth_and_valid_lifecycle():
    with TestClient(app) as anonymous:
        assert anonymous.post('/api/tickets/1/transition',json={
            'status':'fechado','message':'Resolvido por suporte.'
        }).status_code==401
    with TestClient(app) as client:
        assert client.post('/api/login',json={'password':'test-password'}).status_code==200
        assert client.post('/api/tickets',json={
            'title':'Cadastro iniciado fechado','client':'Cliente XYZ',
            'description':'Teste para validar que precisa ser registrado e fechado depois.',
            'status':'fechado'
        }).status_code==422
        assert client.post('/api/tickets/999999/transition',json={
            'status':'fechado','message':'Este chamado não existe.'
        }).status_code==404


def test_meeting_completion_and_reopening():
    with TestClient(app) as anonymous:
        assert anonymous.post('/api/meetings/1/outcome',json={
            'status':'realizada','note':'Cliente aprovou o encaminhamento.'
        }).status_code==401
    with TestClient(app) as client:
        assert client.post('/api/login',json={'password':'test-password'}).status_code==200
        m=client.post('/api/meetings',json={
            'title':'Reunião de validação','client':'Cliente teste','meeting_date':'2027-01-01',
            'start_time':'09:00','end_time':'10:00'
        })
        assert m.status_code==201,m.text
        mid=m.json()['id']
        assert m.json()['status']=='agendada'
        assert client.post(f'/api/meetings/{mid}/outcome',json={
            'status':'realizada','note':' '
        }).status_code==422
        done=client.post(f'/api/meetings/{mid}/outcome',json={
            'status':'realizada','note':'Encontro concluído, escopo validado pelo cliente.'
        })
        assert done.status_code==200,done.text
        assert done.json()['status']=='realizada'
        assert done.json()['closure_note'].startswith('Encontro concluído')
        assert done.json()['closure_by']
        assert done.json()['closure_at']
        assert client.post(f'/api/meetings/{mid}/outcome',json={
            'status':'realizada','note':'Tentar repetir estado'
        }).status_code==409
        saved=next(m for m in client.get('/api/state').json()['meetings'] if m['id']==mid)
        assert saved['status']=='realizada'
        reopened=client.post(f'/api/meetings/{mid}/outcome',json={
            'status':'agendada','note':'Cliente solicitou nova data para alinhar ajustes.'
        })
        assert reopened.status_code==200,reopened.text
        assert reopened.json()['status']=='agendada'
        canceled=client.post(f'/api/meetings/{mid}/outcome',json={
            'status':'cancelada','note':'Reunião cancelada após orientação do cliente.'
        })
        assert canceled.status_code==200,canceled.text
        assert canceled.json()['status']=='cancelada'
        assert canceled.json()['closure_note'].startswith('Reunião cancelada')
        assert client.delete(f'/api/meetings/{mid}').status_code==200
        assert not any(item['id']==mid for item in client.get('/api/state').json()['meetings'])


def test_quote_approve_reject_actions():
    with TestClient(app) as client:
        assert client.post('/api/login',json={'password':'test-password'}).status_code==200
        payload={
            'client_name':'Empresa Beta','project_name':'Sistema de controle',
            'scope':'Desenvolvimento de uma aplicação de controle interno.',
            'items':[{'title':'Etapa de desenvolvimento','quantity':1,'hours_per_unit':10}],
            'hourly_cost':'65.00','status':'rascunho'
        }
        created=client.post('/api/quotes',json=payload)
        assert created.status_code==201,created.text
        quote=created.json()
        # Mesmo corpo que a tabela de orçamentos envia ao clicar em Recusar.
        declined=client.put(f"/api/quotes/{quote['id']}",json={**quote,'status':'recusado'})
        assert declined.status_code==200,declined.text
        assert declined.json()['status']=='recusado'
        resumed=client.put(f"/api/quotes/{quote['id']}",json={**declined.json(),'status':'rascunho'})
        assert resumed.status_code==200,resumed.text
        approved=client.put(f"/api/quotes/{quote['id']}",json={**resumed.json(),'status':'aprovado'})
        assert approved.status_code==200,approved.text
        assert approved.json()['status']=='aprovado'
        assert client.put(f"/api/quotes/{quote['id']}",json={**approved.json(),'status':'recusado'}).status_code==409


def test_ticket_explicit_close_reopen_with_reason():
    from fastapi.testclient import TestClient
    payload = {
        'title':'Falha em tela de cliente','client':'Cliente Teste',
        'description':'Ao salvar pedido aparece erro de comunicação.',
        'status':'aberto','priority':'normal','type':'suporte',
        'assignee':'Atendimento'
    }
    with TestClient(app) as c:
        assert c.post('/api/tickets/99999/transition',json={
            'status':'fechado','message':'Chamado investigado e resolvido.'
        }).status_code==401
        assert c.post('/api/login',json={'password':'test-password'}).status_code==200
        created=c.post('/api/tickets',json=payload)
        assert created.status_code==201,created.text
        ticket=created.json()
        tid=ticket['id']
        endpoint=f'/api/tickets/{tid}/transition'
        # Não permitir fechar por um PUT genérico sem explicar a conclusão.
        illegal=c.put(f'/api/tickets/{tid}',json={**payload,'status':'fechado'})
        assert illegal.status_code==422
        assert c.post(endpoint,json={'status':'fechado','message':' '}).status_code==422
        assert c.post(endpoint,json={'status':'fechado','message':'nada'}).status_code==422
        closed=c.post(endpoint,json={'status':'fechado',
            'message':'Correção aplicada, conferida e comunicada ao cliente.'})
        assert closed.status_code==200,closed.text
        assert closed.json()['status']=='fechado'
        assert closed.json()['closed_at']
        history=closed.json()['events']
        assert len(history)==2
        assert history[-1]['kind']=='situacao'
        assert 'Correção aplicada' in history[-1]['message']
        assert c.post(endpoint,json={'status':'fechado','message':'Já fechado.'}).status_code==409
        assert c.put(f'/api/tickets/{tid}',json={**payload,'status':'aberto'}).status_code==422
        assert c.post(endpoint,json={'status':'aguardando_cliente',
            'message':'Aguardar mais detalhes.'}).status_code==409
        reopened=c.post(endpoint,json={'status':'aberto',
            'message':'Cliente informou recorrência do erro e solicitou nova análise.'})
        assert reopened.status_code==200,reopened.text
        assert reopened.json()['status']=='aberto'
        assert reopened.json()['closed_at'] is None
        assert len(reopened.json()['events'])==3
        assert any('reabert' in e['message'].lower() or 'Aberto' in e['message']
            for e in reopened.json()['events'])
        assert c.post('/api/tickets/999999/transition',json={
            'status':'fechado','message':'Tentativa sem registro válido.'
        }).status_code==404
        c.post(endpoint,json={'status':'resolvido','message':'Ajuste novamente testado.'})
        resolved=c.get('/api/tickets').json()
        assert next(x for x in resolved if x['id']==tid)['status']=='resolvido'
        finally_closed=c.post(endpoint,json={'status':'fechado','message':'Cliente confirmou normalização.'})
        assert finally_closed.status_code==200,finally_closed.text
        assert finally_closed.json()['status']=='fechado'


def test_reference_original_pixel_fidelity(monkeypatch):
    """Reprodução da arte B usa pixels da matriz, sem reinterpretar a frente.
    A identidade exata da referência real está fixada por SHA256 em produção.
    """
    import base64
    import hashlib
    import io
    from PIL import Image
    from pypdf import PdfReader
    import approved_template
    master=Image.new("RGB",(1536,1024),(241,245,249))
    # Três regiões visivelmente distintas: o pixel deve atravessar o gerador intacto.
    from PIL import ImageDraw
    draw=ImageDraw.Draw(master)
    draw.rectangle((800,445,1500,690),fill=(11,35,61))
    draw.rectangle((792,110,1510,394),fill=(255,255,255))
    draw.rectangle((799,730,1503,986),fill=(255,255,255))
    raw=io.BytesIO()
    master.save(raw,format="JPEG",quality=92)
    original=raw.getvalue()
    value='data:image/jpeg;base64,'+base64.b64encode(original).decode()
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/brand-reference/status').status_code==401
        assert anonymous.put('/api/brand-reference',json={'image_data':value}).status_code==401
    with TestClient(app) as admin:
        assert admin.post('/api/login',json={'password':'test-password'}).status_code==200
        status=admin.get('/api/brand-reference/status')
        assert status.status_code==200
        assert status.json()['installed'] is False
        assert admin.put('/api/brand-reference',json={'image_data':value}).status_code==422
        monkeypatch.setattr(approved_template,'APPROVED_SHA256',hashlib.sha256(original).hexdigest())
        saved=admin.put('/api/brand-reference',json={'image_data':value})
        assert saved.status_code==200,saved.text
        assert admin.get('/api/brand-reference/status').json()['installed'] is True
        view=admin.get('/api/brand-reference/front')
        assert view.status_code==200
        assert Image.open(io.BytesIO(view.content)).size==(711,260)
        member=admin.post('/api/members',json={
            'name':'Equipe matriz B','role':'Desenvolvedor',
            'whatsapp':'(34) 99662-1546','city':'Patos de Minas - MG',
            'site':'https://nexonlabs.onrender.com'
        })
        assert member.status_code==201,member.text
        mid=member.json()['id']
        front=admin.get(f'/api/members/{mid}/brand/front?format=png')
        assert front.status_code==200,front.text[:100]
        # Frente institucional exportada sem nenhum redesenho, cor ou proporção diferentes.
        assert front.content==view.content
        signature=admin.get(f'/api/members/{mid}/brand/signature?format=png')
        assert signature.status_code==200
        assert Image.open(io.BytesIO(signature.content)).size==(733,292)
        back=admin.get(f'/api/members/{mid}/brand/back?format=png')
        assert back.status_code==200
        assert Image.open(io.BytesIO(back.content)).size==(718,269)
        pdf=admin.get(f'/api/members/{mid}/brand/card?format=pdf')
        assert pdf.status_code==200,pdf.text[:120]
        assert len(PdfReader(io.BytesIO(pdf.content)).pages)==2
        assert admin.delete(f'/api/members/{mid}').status_code==200


def test_reference_png_can_be_uploaded_after_visual_confirmation():
    import base64
    import io
    from PIL import Image
    from pypdf import PdfReader
    with TestClient(app) as c:
        assert c.post('/api/login',json={'password':'test-password'}).status_code==200
        reference=Image.new('RGB',(1536,1024),(247,249,252))
        from PIL import ImageDraw
        draw=ImageDraw.Draw(reference)
        draw.rectangle((795,430,1510,700),fill=(12,42,65))
        draw.rectangle((790,105,1520,400),fill=(255,255,255))
        draw.rectangle((790,720,1515,994),fill=(255,255,255))
        buf=io.BytesIO();reference.save(buf,format='PNG')
        raw=buf.getvalue()
        value='data:image/png;base64,'+base64.b64encode(raw).decode()
        assert c.put('/api/brand-reference',json={'image_data':value}).status_code==422
        wrong=Image.new('RGB',(900,700),(247,249,252))
        buf_wrong=io.BytesIO();wrong.save(buf_wrong,format='PNG')
        wrong_value='data:image/png;base64,'+base64.b64encode(buf_wrong.getvalue()).decode()
        resized=c.put('/api/brand-reference',json={'image_data':wrong_value,'confirmed':True})
        assert resized.status_code==422
        assert '1536' in resized.json()['detail']
        saved=c.put('/api/brand-reference',json={'image_data':value,'confirmed':True})
        assert saved.status_code==200,saved.text
        assert saved.json()['installed'] is True
        assert saved.json()['exact_original_file'] is False
        assert c.get('/api/brand-reference/status').json()['installed'] is True
        for kind,sz in (('signature',(733,292)),('front',(711,260)),('back',(718,269))):
            response=c.get('/api/brand-reference/'+kind)
            assert response.status_code==200
            assert Image.open(io.BytesIO(response.content)).size==sz
        member=c.post('/api/members',json={'name':'Colaborador PNG','role':'Técnico'})
        assert member.status_code==201,member.text
        mid=member.json()['id']
        front=c.get(f'/api/members/{mid}/brand/front?format=png')
        assert front.status_code==200,front.text[:120]
        assert Image.open(io.BytesIO(front.content)).size==(711,260)
        pdf=c.get(f'/api/members/{mid}/brand/card?format=pdf')
        assert pdf.status_code==200
        assert len(PdfReader(io.BytesIO(pdf.content)).pages)==2
        assert c.delete(f'/api/members/{mid}').status_code==200
