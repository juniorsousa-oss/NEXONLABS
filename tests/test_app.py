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
