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


## Módulo comercial — orçamentos e precificação

No menu **Orçamentos**, cadastre cliente, escopo, etapas, quantidades e horas estimadas. Os valores internos de custo/hora, reserva, despesas específicas, margem e taxas são usados exclusivamente no cálculo; não aparecem no PDF da proposta.

- Fórmula de desenvolvimento: \`(horas × custo/hora × (1 + reserva) + despesas) / (1 - margem - taxas)\`. A reserva é aplicada apenas ao custo da mão de obra; não repita despesas já incorporadas ao custo/hora.
- Mensalidade: quando aplicável, \`custo mensal / (1 - margem - taxas)\`, apresentada separadamente do valor único.
- Percentuais de margem e tributos/taxas são premissas fornecidas pelo usuário; o sistema não determina alíquotas nem substitui análise contábil.
- Os preços das etapas no PDF são rateados por horas entre os itens; os ajustes de centavos são alocados à última etapa.
- Dados comerciais (nome, contato, CNPJ e logo PNG/JPEG até 300 KB) são configurados somente para a apresentação no PDF; a identidade visual do aplicativo permanece inalterada. PDFs reemitidos após mudança de marca usam os dados comerciais atuais. Guarde o arquivo enviado ao cliente para preservar a versão apresentada.
- O orçamento tem histórico, número sequencial por banco, status manual de negociação e exportação de PDF. Após aprovação, pode ser convertido em projeto. O sistema **não** envia e-mail, cobra clientes ou registra assinatura eletrônica.
- Os dados internos de custo exigem autenticação, mas a aplicação ainda usa senha compartilhada; antes de oferecer acesso a clientes externos, implemente perfis individuais e permissões por cliente.
- O PDF é uma proposta comercial, não é nota fiscal nem contrato assinado; formalize os termos e a eventual aceitação em instrumento apropriado.

## Testes

```bash
pip install pytest httpx
pytest -q
```
