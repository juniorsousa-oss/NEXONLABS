# Nexon Labs — Gestão de Projetos

Aplicativo web para acompanhar projetos de desenvolvimento da Nexon Labs. Interface responsiva baseada no **layout aprovado em 21/09/2026**: menu lateral azul-marinho, logo de núcleo e conexões, quatro indicadores, tabela de projetos, próximas entregas e atividades recentes.

## Funcionalidades da primeira versão

- Cadastro, edição, pesquisa, status, prazo, progresso e exclusão de projetos.
- Tarefas vinculadas a projetos: responsável, horas, prazo, conclusão e edição.
- Cadastro de equipe, cronograma de entregas, relatórios e exportação de projetos CSV.
- Indicadores calculados a partir dos registros reais, atividades recentes e alertas de prazo.
- Acesso individual com somente o campo de senha; cada senha cadastrada identifica um usuário e seu nome é mostrado após o login.

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

Em produção, use **PostgreSQL persistente** em `DATABASE_URL` (`postgresql://...`, convertido internamente para `postgresql+psycopg://...`). O SQLite `nexonlabs.db` padrão é adequado apenas a uso local ou ambiente com disco persistente. Não use filesystem efêmero na hospedagem: os dados seriam perdidos ao reiniciar. Faça backup periódico do banco. As contas são individuais, mas os dados de projetos, orçamentos e chamados ainda são compartilhados entre os usuários autorizados; não disponibilize acesso direto aos clientes antes de implementar permissões por cliente.

## Acesso individual e reconhecimento por senha

- Ao abrir `/` sem sessão válida, o aplicativo apresenta somente o campo **Senha de acesso**. Após o login, mostra o nome da pessoa no topo e na saudação da tela Início.
- A senha já configurada em `APP_PASSWORD` no Render é utilizada **uma única vez** para criar a primeira conta administrativa quando a tabela de usuários está vazia. Depois disso, `APP_PASSWORD` **não funciona como senha mestra**: as contas usam hashes individuais armazenados no banco.
- No primeiro acesso, abra **Configurações → Meu acesso** e altere o nome inicial do administrador para seu nome. Para criar mais pessoas, use **Configurações → Usuários e permissões → Novo usuário** e informe um nome e uma senha individual de pelo menos oito caracteres.
- O administrador pode redefinir senhas e desativar contas. Alterações de senha ou desativação invalidam sessões anteriores. As senhas não aparecem na lista de usuários nem são armazenadas em texto puro no banco.
- A aba **Equipe** cadastra colaboradores envolvidos nos projetos; ela não cria automaticamente contas de acesso. Contas são criadas apenas pelo administrador em **Configurações**.
- Não compartilhe senhas entre pessoas. Se você perder o único acesso administrativo, a recuperação exigirá uma ação administrativa controlada no banco ou no ambiente; alterar apenas a variável `APP_PASSWORD` não sobrescreve as senhas existentes.
- Os dados cadastrados no sistema continuam visíveis aos usuários autorizados desta versão. A diferenciação administrador/usuário restringe a **gestão de acessos**, não o acesso a projetos e orçamentos.

## Materiais de identidade dos colaboradores — modelo B aprovado

No menu **Equipe → Colaboradores**, escolha **Editar** para completar nome, cargo, WhatsApp, e-mail opcional, cidade e site. Os campos novos são guardados em uma tabela própria para não excluir os registros anteriores. Colaboradores não são necessariamente contas de login.

Em **Cartão e assinatura** há prévias com os dados salvos e as exportações: assinatura em PNG e HTML; frente e verso do cartão em PNG; cartão completo com duas páginas em PDF 96 × 56 mm (90 × 50 mm de corte e 3 mm de sangria por borda). O QR Code é codificado com a URL do site registrada no perfil; se ela for o domínio do app privado, o visitante verá o login. Não coloque contato de e-mail ou WhatsApp inventado: os campos em branco são omitidos.

**Referência visual:** composição **Opção B — Tecnológica e Moderna** aprovada: assinatura escuro/branco com separação diagonal turquesa, frente azul-marinho com elemento de teclado no lado direito e chamada "DA IDEIA À OPERAÇÃO"; verso branco com QR central e faixa escura de quatro serviços. As formas, letras e efeitos são recriados digitalmente, portanto não representam uma cópia de pixels da montagem em imagem; conferir as prévias e uma prova da gráfica antes da impressão definitiva. A imagem da assinatura HTML é incorporada como data URI, que pode ser bloqueada por alguns clientes de e-mail; nesses casos, use o PNG ou hospede a imagem em HTTPS.

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
- Os dados internos de custo exigem autenticação individual, mas **não há segregação dos projetos ou orçamentos entre funcionários cadastrados**. Antes de oferecer acesso a clientes externos, implemente permissões por cliente e por módulo.
- O PDF é uma proposta comercial, não é nota fiscal nem contrato assinado; formalize os termos e a eventual aceitação em instrumento apropriado.

## Testes

```bash
pip install pytest httpx
pytest -q
```
