# Padrão visual de login — Nexon Labs

**Versão 1.1 · 08/10/2026 · Referência estrutural aprovada: ATRIA**

Este documento define a linguagem visual a ser seguida por ATRIA, Opera Hub e futuros produtos. **Padronizar não significa substituir identidades visuais nem mudar fluxos de autenticação já aprovados.**

## Diretrizes de composição

1. **Card centralizado na página:** fundo institucional escuro; um card branco com cantos arredondados, profundidade discreta e margens externas visíveis no smartphone.
2. **Layout de duas regiões:** painel institucional superior (logo, slogan e imagem/arte) e painel inferior claro (identificação do ambiente, instruções e formulário).
3. **Altura ajustada ao conteúdo:** evitar (min-height: 100vh) no **card** em dispositivos móveis; usar altura automática. O plano de fundo pode ocupar toda a viewport. Não esticar a área superior ou inferior apenas para preencher a tela.
4. **Proporção mobile:** ATRIA é a referência de densidade e escala. Os produtos podem ter altura um pouco diferente quando o formulário tiver mais campos, mensagens de erro ou opções úteis (como voltar à página inicial). Não remover campos para forçar uma altura idêntica.
5. **Espaçamento:** reduzir vazios redundantes antes de reduzir textos ou controles. Priorizar compactação de altura de painel, padding vertical, margens de título, distância entre campos e rodapé.
6. **Elementos arredondados:** cantos do card próximos de 24–28 px e controles internos com arredondamento consistente. Respeitar sistema próprio da marca.
7. **Legibilidade e acessibilidade:** campos móveis devem preservar fonte de ao menos 16 px para evitar zoom do Safari; áreas de toque com altura em torno de 44–48 px ou maior quando necessário; manter rótulos, foco visível, erros de autenticação e suporte a teclado.
8. **Responsividade:** centralizar o card em telas altas; permitir rolagem natural em telas baixas, em paisagem, com zoom do sistema ou teclado aberto. Considerar safe areas do iPhone sem ocultar ações.
9. **Identidade independente:** ATRIA mantém suas cores, símbolo, mensagem e experiência de acesso por senha. Opera Hub mantém amarelo institucional, imagem operacional, identificação DEMO/CLIENTE, usuário + senha e botão de voltar.
10. **Integridade da aplicação:** alterações de padrão visual não alteram banco de dados, permissões, rotas, credenciais, sessões, configurações multiempresa ou páginas internas.

## Referências de código existentes

- **ATRIA (layout aprovado, não modificar para padronizar):** repositório `juniorsousa-oss/NEXONLABS`, arquivos `static/login.html` e `static/atria-premium.css`.
- **Opera Hub:** repositório `juniorsousa-oss/OPERAHUB---NOVA-VERS-O`, arquivos `templates/login.html`, `templates/index.html`, `static/premium.css` e `static/nexon-connections.svg`. Em 08/10/2026, o login mobile foi compactado, e posteriormente a versão desktop teve largura-alvo de 960 px e altura mínima de 535 px, próximas das proporções do ATRIA; o fundo externo ganhou a paleta navy/dourado. A tela inicial usa indicadores coesos e a assinatura discreta **by Nexon Labs**.

## Identidade e assinatura de portfólio

- A identidade de cada produto é prioritária: **ATRIA** permanece em navy/azul e turquesa; **Opera Hub** segue navy com amarelo/dourado. Não copiar a cor do ATRIA para o Opera.
- A assinatura textual de origem é discreta: `by Nexon Labs`, preferencialmente no rodapé do login e da área principal, sem competir com a marca de cada produto.
- Textura de conexões da Nexon Labs pode surgir em baixa opacidade e sem interferir em legibilidade ou acesso; no Opera Hub é uma variante dourada em SVG.
- Indicadores do Opera Hub usam a mesma base de superfícies claras, navy, dourado e neutros quentes; cores funcionais de atenção são subordinadas à paleta.
- A altura dos cards não deve ser forçada a ficar idêntica: preservar campos extras e mensagens de autenticação em vez de reduzir a acessibilidade.
- O documento estabelece regras para futuras aplicações. Nenhuma alteração de aparência no ATRIA deve acontecer apenas para adaptar a identidade do Opera Hub.

## Checklist de validação por entrega

- [ ] Smartphone: margens externas, cabeçalho, campos, botão e rodapé visíveis ou acessíveis por rolagem.
- [ ] iPhone Safari: sem zoom involuntário ao focar campo de entrada; teclado não bloqueia o envio.
- [ ] Smartphone compacto e viewport baixa: não há sobreposição, corte, altura mínima excessiva ou rolagem horizontal.
- [ ] Tablet e desktop: duas regiões ou empilhamento conforme breakpoint, sem regressão.
- [ ] Marcas, slogans, logos, ícones, cores e mensagens específicos continuam intactos.
- [ ] Login, exibição de senha, avisos, URLs e isolamento de organizações funcionam como antes.
- [ ] CSS atualizado é carregado sem cache antigo.
- [ ] Publicação confirmada no serviço de hospedagem; commit no GitHub, isoladamente, não comprova deploy.

## Governança

O padrão do ATRIA é a referência visual, não uma biblioteca obrigatória. Toda nova tela de login deve aderir às diretrizes; mudanças no ATRIA ou no Opera Hub devem ser feitas apenas quando necessárias e validadas sem regressão.
