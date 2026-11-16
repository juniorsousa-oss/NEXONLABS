# NEXON LABS — Padrão PWA v1.0

## Objetivo
Permitir instalação dos aplicativos via navegador em Android, iOS e computadores com suporte a PWA, sem publicação obrigatória nas lojas.

## Itens obrigatórios em todos os aplicativos
1. Manifesto JSON próprio, com `name`, `short_name`, `id`, `start_url`, `scope`, `display: standalone`, `theme_color`, `background_color` e `lang: pt-BR`.
2. Ícones PNG reais de **192 × 192** e **512 × 512** derivando da identidade oficial; nunca ampliar um ícone sem revisar a nitidez.
3. Ícone de tela inicial da Apple e opção nativa de instalação no Android/desktop.
4. Registro de service worker servido na raiz (`/service-worker.js`) em HTTPS e com escopo `/`.
5. O service worker básico **não possui fetch handler ou CacheStorage**: não armazenar senhas, tokens, dados financeiros, dados de saúde, projetos, cadernos, respostas acadêmicas nem informações dos clientes offline.
6. O aplicativo deve continuar funcionando como web quando instalação/service worker não forem compatíveis.
7. Layout responsivo, identidade institucional aprovada, cada produto com seu nome, ícone e tema.

## Padrão aplicado em 16/11/2026
- ATRIA: `juniorsousa-oss/NEXONLABS`, branch `feature/pwa-installable-20261116`; fonte `static/logo.svg`.
- AXORA: `juniorsousa-oss/GESTAO-FINANCEIRA`, branch `develop`; fonte `axora_v2/static/axora-mark.svg`.
- RITMOX: `juniorsousa-oss/RITMOX`, branch `feature/pwa-installable-20261116`; fonte `static/ritmox-mark.svg`.
- OPERA HUB: `juniorsousa-oss/OPERAHUB---NOVA-VERS-O`, branch `feature/pwa-installable-20261116`; fonte `static/favicon.svg`.
- AULVIA: `juniorsousa-oss/AULVIA`, branch `develop`; fonte `public/brand/aulvia-app-icon.svg`.

## Checklist de homologação
- [ ] Executar testes de construção de ícones e validação de manifestos/scripts.
- [ ] Validar resposta HTTP 200 e MIME correto do manifesto, ícones e SW.
- [ ] Verificar instalação no Android (Chrome/Samsung), iOS (Adicionar à Tela de Início) e desktop (Chrome/Edge).
- [ ] Confirmar tela inicial, nome, marca, modo `standalone` e ausência de barras de navegação após instalação.
- [ ] Reabrir o aplicativo instalado e verificar autenticação; **não salvar senha**.
- [ ] Confirmar que sair/logout e troca de usuário não deixam conteúdo privado acessível offline.
- [ ] Confirmar nova versão do servidor sem exigir desinstalação.
- [ ] Validar desktop/mobile e fallback em navegador sem service worker.
- [ ] Aprovar os ambientes BETA/DEMO antes de integrar a `main` ou publicar em domínio de produção.

## Observações
- A instalação depende de compatibilidade do sistema operacional e navegador, e de servir por HTTPS.
- A primeira fase é **online-first**. Não prometer trabalho offline ou notificações push até existir projeto e testes próprios.
- O padrão é técnico e não altera marca, autorização ou arquitetura multi-tenant.
