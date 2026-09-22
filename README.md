# Nexon Labs — Gestão de Projetos

Aplicativo web para acompanhar projetos de desenvolvimento da Nexon Labs. Interface responsiva baseada no **layout aprovado em 21/09/2026**: menu lateral azul-marinho, logo de núcleo e conexões, quatro indicadores, tabela de projetos, próximas entregas e atividades recentes.

## Funcionalidades da primeira versão

- Cadastro, edição, pesquisa, status, prazo, progresso e exclusão de projetos.
- Tarefas vinculadas a projetos: responsável, horas, prazo, conclusão e edição.
- Cadastro de equipe, cronograma de entregas, relatórios e exportação de projetos CSV.
- Indicadores calculados a partir dos registros reais, atividades recentes e alertas de prazo.
- Acesso protegido por senha compartilhada quando `APP_PASSWORD` estiver configurada.

**Importante:** não existem projetos fictícios pré-cadastrados; os números da imagem aprovada são exemplos visuais, enquanto o aplicativo mostra apenas dados reais. O nome/ícone/paleta/estrutura estão separados em `static/` e marcados com `DESIGN LOCK v1`. Não alterar a aparência sem aprovação do responsável.

## Executar localmente

Requer Python 3.11+.

```bash
pip install -r requirements.txt
export APP_PASSWORD='sua-senha-forte'
export SESSION_SECRET='uma-chave-longa-e-aleatoria'
uvicorn app:app --reload
```

Abra <http://localhost:8000>. No Windows PowerShell, use `$env:APP_PASSWORD='...'` e `$env:SESSION_SECRET='...'`.

## Publicar e manter dados

O repositório inclui `render.yaml` para publicação como web service Python na Render. Conecte este repositório à plataforma e configure `APP_PASSWORD`, `DATABASE_URL` e `SESSION_SECRET` (o blueprint gera uma chave), mantendo `COOKIE_SECURE=1` em HTTPS. A URL de hospedagem será gerada pela plataforma **depois da publicação**, não apenas por enviar os arquivos ao GitHub. O GitHub sozinho não executa a API Python.

Em produção, use **PostgreSQL persistente** em `DATABASE_URL` (`postgresql://...`, convertido internamente para `postgresql+psycopg://...`). O SQLite `nexonlabs.db` padrão é adequado apenas a uso local ou ambiente com disco persistente. Não use filesystem efêmero na hospedagem: os dados seriam perdidos ao reiniciar. Faça backup periódico do banco. Para a primeira versão, a senha dá acesso a todas as informações; perfis individuais e autorização por cliente não estão implementados. Não disponibilize acesso direto a clientes externos antes dessa etapa.

## Identidade visual

- `static/style.css`: layout e paleta com **DESIGN LOCK v1**;
- `static/logo.svg`: símbolo da marca em formato vetorial;
- `static/index.html`: estrutura da tela aprovada;
- `static/app.js`: dados, renderização e ações sem alterar a linguagem visual.

## Testes

```bash
pip install pytest httpx
pytest -q
```
