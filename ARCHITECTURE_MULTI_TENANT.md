# ATRIA — Arquitetura Multiempresa e Branding

## Objetivo

Transformar o ATRIA em um produto SaaS multiempresa, no qual cada organização tenha seus próprios usuários, dados, arquivos e identidade visual, mantendo a assinatura obrigatória da Nexon Labs em todos os ambientes e materiais gerados.

## Estrutura de marca

A hierarquia oficial é:

1. Marca do cliente
2. ATRIA como produto
3. Nexon Labs como criadora e assinatura permanente

Regras:

- O ATRIA possui identidade padrão própria.
- Cada organização pode aplicar sua própria identidade visual.
- A identificação da Nexon Labs não pode ser removida pelo cliente.
- Quando houver marca do cliente, a aplicação deve usar uma assinatura discreta como:
  - "Powered by ATRIA · Nexon Labs"
  - ou "ATRIA · by Nexon Labs"
- PDFs, relatórios, propostas, documentos e demais exportações devem manter identificação Nexon Labs e/ou marca d'água conforme o template do produto.

## Organizações iniciais

### atria-demo

Ambiente de demonstração e validação comercial.

- Logo padrão ATRIA
- Dados fictícios
- Usuários próprios
- Arquivos próprios
- Não pode acessar dados reais da Nexon Labs

### nexon-labs

Ambiente operacional real da Nexon Labs.

- Identidade visual Nexon Labs
- Dados atualmente existentes no banco devem ser migrados para esta organização
- Usuários reais da Nexon Labs
- Projetos, tarefas, reuniões, chamados e orçamentos reais

## Modelo de dados

Tabela base planejada:

```text
organizations
-------------
id
name
slug
logo_url
logo_dark_url
favicon_url
primary_color
secondary_color
use_custom_brand
active
created_at
```

Todas as entidades funcionais deverão pertencer a uma organização por meio de `organization_id`.

Entidades prioritárias:

- app_accounts
- members
- projects
- tasks
- activities
- meetings
- meeting_closures
- meeting_attendees
- project_client_sites
- chamados
- orçamentos
- anexos e arquivos
- demais tabelas futuras

## Isolamento

Toda leitura, criação, alteração e exclusão deve ser filtrada por `organization_id`.

Regra:

```text
sessão do usuário
    ↓
organization_id
    ↓
consulta restrita à organização
```

Nenhum endpoint deve confiar em um `organization_id` enviado livremente pelo navegador para decidir acesso.

## Usuários

Cada conta pertence a uma única organização na primeira versão.

A sessão deve carregar:

- account_id
- organization_id
- role
- session_version

O administrador de uma organização só pode gerenciar usuários da própria organização.

## Armazenamento

Arquivos não devem ficar dentro do container Docker.

Estrutura lógica:

```text
organizations/
  atria-demo/
  nexon-labs/
  cliente-x/
```

O banco deve armazenar apenas metadados e URLs/chaves dos objetos.

## Branding configurável

Tela prevista:

Configurações > Empresa > Identidade visual

Campos:

- Nome da empresa
- Logo para fundo claro
- Logo para fundo escuro
- Favicon
- Cor principal
- Cor secundária
- Logo em relatórios
- Assinatura em documentos

O produto deve oferecer restauração para a identidade padrão ATRIA.

## Branding obrigatório Nexon Labs

A assinatura Nexon Labs é uma regra de plataforma e não uma preferência por cliente.

Aplicações mínimas:

- rodapé ou área institucional do app
- tela de login quando apropriado
- PDFs
- relatórios
- propostas
- exportações
- documentos gerados
- marcas d'água

O cliente pode personalizar sua marca, mas não remover a autoria Nexon Labs.

## Estratégia de migração

1. ✅ Criar tabela `organizations`.
2. ✅ Criar organizações `atria-demo` e `nexon-labs`.
3. ✅ Vincular todos os dados existentes à organização `nexon-labs`.
4. ✅ Vincular contas atuais à organização `nexon-labs`.
5. ✅ Adicionar filtros de organização aos endpoints existentes.
6. ⏳ Criar ambiente de demonstração com usuário e dados próprios.
7. ⏳ Adicionar branding por organização.
8. ⏳ Adicionar storage por organização.
9. ✅ Criar testes de isolamento.
10. ⏳ Habilitar onboarding de novos clientes após validação das etapas anteriores.

### Status técnico — Fase 2

O isolamento bidirecional entre `nexon-labs` e `atria-demo` já está ativo na branch
`feature/multi-tenant-foundation`.

As consultas, criações, alterações e exclusões de projetos, tarefas, equipe, reuniões,
atividades, contas, chamados e orçamentos usam a organização da sessão. Tentativas de
acessar diretamente um ID de outra organização retornam recurso não encontrado.

A matriz visual interna da Nexon Labs também foi restringida à organização Nexon Labs.

Validação automatizada atual: **19 testes aprovados**.

## Regra de segurança para migração

A migração deve ser aditiva e reversível.

- Não apagar dados existentes.
- Não renomear tabelas antigas durante a primeira etapa.
- Criar colunas inicialmente compatíveis com os registros atuais.
- Popular `organization_id` antes de torná-lo obrigatório.
- Validar leitura e escrita da Nexon Labs antes de criar o ambiente Demo.
- Manter backup antes de executar migração de produção.
