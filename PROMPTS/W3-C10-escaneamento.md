# Prompt de Execução — W3-C10 · Escaneamento por Câmera + Fallback de Digitação Manual (Mobile-First)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, as **Waves 0–2 concluídas e auditadas (GO)** e o **C06 mergeado**, e as **duas imagens do design anexadas** (Escanear prova — modos Câmera e Manual). Este é o **primeiro componente da Wave 3** e o **componente mais mobile-first do sistema**. Trabalhe a sessão inteira nele.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (**robustez/degradação graciosa, escalabilidade, mínimo de requisições, observabilidade**, animações leves), arquitetura §5 (Ports & Adapters), §9 (comandos), §11 (o que NÃO fazer).

**Estado atual do repositório (Waves 0–2 entregues):**
- C04: **app shell** (sidebar + shell branco); **toasts**; **fundação de motion**.
- C05: `access-matrix.ts` + middleware + `useAuthorization` + **helpers de RLS** + propagação de claims (ADR-008).
- C06: tabela **`provas`** com o **código alfanumérico** (formato **`PRV-AAAA-MM-...`**) e o **QR** que **codifica esse identificador** (RF-002); RLS de provas por perfil.
- C07/C08/C09: listagem, detalhe (com **anti-vazamento de existência** — reuse o padrão), configurações. **Reuse tudo isso — não recrie.**

**Insumo confirmado:** as duas telas no Figma (Câmera / Manual). **Atenção a uma divergência crítica (DP-1):** o design mostra o código manual como **"3S- XXXX-XXXX" / "8 dígitos"**, mas o **backlog (C10) e o C06 definem `PRV-AAAA-MM-NNNNNN`** — o C10 tem que ler **exatamente** o que o C06 gera.

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — formato do código, fronteira entre componentes, segurança do endpoint, lib de câmera, adaptação mobile — **pare, exponha 2–3 opções e a sua recomendação, e aguarde a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, confirme o estado das Waves 0–2 + C06 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas. **DP-1 (formato do código) é bloqueante.**
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte.
4. **Nunca invente** o formato/máscara do código, o contrato do endpoint, a lib de câmera ou valores de design. Em dúvida, **pergunte**.

---

## 0.2 Fidelidade ao design

**Tela "Escanear prova"** (dentro do shell do C04), em **dois modos** via toggle **Câmera / Manual** (ambos sempre acessíveis): título "Escanear prova" + subtítulo "Leia o QR Code da etiqueta com a câmera ou insira o código manualmente para confirmar a próxima movimentação."
- **Câmera:** visor com **área de leitura demarcada** ("Centralize o QR Code no quadro") + painel "Pronto para escanear" + botão **"Abrir câmera"**. Rodapé "Última leitura há X min" + "Ver histórico →".
- **Manual:** "Inserir código manualmente" + instrução + **input com máscara** + botão **"Buscar prova →"** (desabilitado até válido). *(A máscara do design — "3S- XXXX-XXXX" — é a divergência da DP-1; use a máscara real do formato do C06.)*

**Mobile-first:** o design mostrado é desktop, mas **este componente é primariamente mobile** (motoristas/vendedores/clicheria usam celular). **Não há mockup mobile** — siga RF-029/US-020 (ver DP-4). Tokens/cores/tipografia seguem o já estabelecido; **não chute** — se houver link do Figma, extraia via Dev Mode/MCP; senão, confirme.

---

## 1. Objetivo do componente

Entregar o **mecanismo de identidade** que conecta a prova **física** (etiqueta impressa) ao registro **digital**: **leitura por câmera** (in-app, sem app externo) + **fallback de digitação manual**, com um **endpoint único e idempotente de identificação** que resolve a prova — tudo **mobile-first**, robusto a falhas (câmera negada → manual) e seguro (anti-enumeração + rate limiting).

Referências: Backlog **C10** · Requisitos **RF-004, RF-005, RF-029, RN-014, RNF-002, RNF-013, RNF-014** · §7 (Escanear = universal) · C06 (código/QR) · C08 (anti-vazamento) · **Fronteira com C11/C12** (ver §1.1/DP-2).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **Formato do código (canônico):** o backlog (C10) e o C06 definem **`PRV-AAAA-MM-NNNNNN`**. O QR **carrega esse identificador** (RF-002). O input manual deve **bater exatamente** com o que o C06 gera (DP-1). *(A máscara "3S-/8 dígitos" do design diverge — ver DP-1.)*
2. **C10 só IDENTIFICA — não transiciona nem assina.** O fluxo completo (RF-006/RF-028, US-002/018/019) é: **identificar → validar a próxima transição (perfil+estado) → assinatura digital → confirmar → transição**. Mas **validar transição = C11 (máquina de estados)** e **assinatura = C12** — e o C10 **depende só do 06**. O C10 entrega a **identificação** (`POST /api/provas/identificar` / `resolver_prova()`); o resto pluga depois (DP-2).
3. **Endpoint idempotente quanto ao mecanismo:** token do QR **e** código manual passam pelo **mesmo** caminho lógico (`resolver_prova()`) e resolvem o **mesmo** registro.
4. **Anti-enumeração (RN-014):** **código inválido E código fora do escopo retornam a MESMA mensagem genérica** (não revelar existência). **Rate limiting:** **30 tentativas/usuário autenticado/minuto**.
5. **Acesso (Matriz §7):** "Escanear QR" é **universal** (todos os perfis); a resolução respeita a **RLS** (fora do escopo → mensagem genérica).
6. **Degradação graciosa (RNF-014):** **câmera indisponível/negada não bloqueia a tela** — o campo manual permanece disponível.
7. **Performance (RNF-002):** identifica o QR em **≤ 2 s** após o foco.

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **Tela "Escanear prova"** (dentro do shell do C04), dois modos (Câmera/Manual sempre acessíveis), fiel ao design + DP-1, **mobile-first** (DP-4): visor de câmera com área demarcada + "Abrir câmera"; input manual com **máscara do formato do C06** + validação em tempo real + "Buscar prova".
- **Câmera (RF-004):** leitura in-app via `getUserMedia` + lib de decodificação (DP-4), **sem app externo**; **permissão negada → manual disponível** (degradação graciosa); identificação em **≤ 2 s** (RNF-002); **animação leve de feedback** ao identificar com sucesso (sobre os tokens; `prefers-reduced-motion`).
- **Backend — `POST /api/provas/identificar`** (`resolver_prova()`): aceita **token do QR ou código manual** (mesmo caminho), **idempotente**, **respeita a RLS** (claims propagados), **anti-enumeração** (inválido == fora-de-escopo → mesma mensagem genérica), **rate limiting 30/min** (DP-3). Logs estruturados (sem vazar dados sensíveis).
- **Pós-identificação:** ao resolver, navegar para o **detalhe (C08)** ou um **placeholder** do fluxo de confirmação (DP-2) — o C10 **não** transiciona nem assina.
- **Documentação** (`docs/escaneamento.md`): o endpoint e `resolver_prova()`, o formato do código (DP-1), anti-enumeração + rate limiting, a fronteira com C11/C12, e as diretrizes mobile-first. **Testes** (§7) e **Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Máquina de estados / validação da próxima transição / registro de movimentação** (Componente **11**). O C10 **resolve** a prova; **não** decide nem executa transição.
- ❌ **Tela de assinatura digital** (Componente **12**) — o C10 **não** assina; após identificar, encaminha ao fluxo (placeholder até C11/C12).
- ❌ **Aprovar/Reprovar do vendedor** (RF-008 — parte do fluxo de transição, C11/C12).
- ❌ **Timeline/histórico de movimentações** (C11/C13) — "Ver histórico" conforme DP-5.
- ❌ Dashboard, relatórios (Waves 4–5).

> Vontade de adiantar transição, assinatura ou aprovar/reprovar: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Código bate com o C06:** a máscara e a validação do input manual seguem **exatamente** o formato gerado pelo C06 (DP-1); o parser do QR lê o payload **conforme o C06 codificou**.
2. **Endpoint idempotente e seguro:** QR e manual pelo **mesmo `resolver_prova()`**; **RLS** respeitada (claims propagados — ADR-008); **anti-enumeração** (inválido == fora-de-escopo → mesma mensagem genérica — RN-014); **rate limiting 30/usuário/min**.
3. **Câmera sem app externo** (RF-004); **HTTPS** (getUserMedia — Vercel ok); **permissão negada → manual permanece** (RNF-014); identificação **≤ 2 s** (RNF-002).
4. **Mobile-first (RF-029, RNF-013, US-020):** responsivo de **360 px**; touch targets **≥ 44×44 px / 48 dp**; **portrait e landscape**; **safe areas via `env()`** (notch); **botões principais no terço inferior** (alcance com uma mão); **contraste AA** (uso ao ar livre).
5. **Estilização:** **CSS Modules mobile-first**; fidelidade ao design + DP-1. Animações `transform`/`opacity`; **`prefers-reduced-motion`** obrigatório.
6. **Robustez:** **error boundary** na rota; perda de câmera/conexão não derruba a tela (RNF-014/016).
7. **Stateless** (RNF-018); **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada. **DP-1 é bloqueante.**

### Bloco A — O contrato do código

**DP-1 — Formato do código (design diverge dos requisitos) — BLOQUEANTE.**
O **backlog (C10) e o C06 definem `PRV-AAAA-MM-NNNNNN`**; o **design mostra "3S- XXXX-XXXX" / "8 dígitos"**. **[Recomendado]** manter o formato canônico **`PRV-AAAA-MM-...`** (backlog + C06, Wave 2 **auditada**) e tratar a máscara do design como **desatualizada** — o input manual usa a máscara/validação que **bate exatamente** com o que o C06 gera (confirme **comprimento e charset do sufixo** lendo a implementação/ADR do C06). *(Se você preferir mesmo o formato curto "3S-", isso **retroage ao C06** — gerador + etiqueta + migração de códigos — em Wave 2 já auditada; só vale se nada foi para produção.)* Confirmar.

### Bloco B — Mecanismo, fronteiras e segurança

**DP-2 — Fronteira C10↔C11↔C12 e destino pós-identificação.**
**[Recomendado]** o C10 entrega **só a identificação** (scan + manual + `POST /api/provas/identificar` / `resolver_prova()`); **validar a próxima transição = C11**, **assinatura = C12**. Após resolver, navegar para o **detalhe (C08)** ou um **placeholder** do fluxo de confirmação (C11/C12 plugam depois). Confirmar a fronteira e o destino pós-identificação.

**DP-3 — Endpoint de identificação: segurança.**
**[Recomendado]** `POST /api/provas/identificar` idempotente (QR e manual pelo mesmo `resolver_prova()`), **RLS** respeitada; **código inválido E fora do escopo → MESMA mensagem genérica** (RN-014); **rate limiting 30/usuário/min**. Confirmar o **contrato do endpoint** (entrada: token/código; saída em sucesso/erro) e a **implementação do rate limiting** (onde/como, dado que o backend é stateless — ex.: contador no Postgres/Redis? confirmar a abordagem disponível).

**DP-4 — Câmera (lib, permissões) e mobile-first (sem mockup mobile).**
**[Recomendado]** lib de decodificação no browser (ex.: `html5-qrcode`/`zxing-js` — ou a critério do `CLAUDE.md §4`); `getUserMedia` (HTTPS); **permissão negada → manual disponível** (RNF-014); **mobile-first** conforme RF-029/US-020 (360px+, touch ≥44/48, portrait+landscape, **safe areas `env()`**, **botões no terço inferior**, contraste AA). Confirmar a **lib** e a **adaptação mobile** (o design é desktop; não há mockup mobile).

**DP-5 — "Ver histórico" / "Última leitura".**
**[Recomendado]** "Última leitura há X min" como indicador local/sessão; "Ver histórico" → **placeholder** ou o histórico da prova (C13, não construído). Confirmar o destino e se há **registro de leituras** no C10 (ou se é só UI).

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Frontend — `apps/web/`
- **`app/(app)/escanear/page.tsx`** (ou rota conforme a sidebar) — tela com toggle **Câmera/Manual** (ambos acessíveis), **mobile-first** (DP-4): visor de câmera (área demarcada, "Abrir câmera", degradação graciosa); input manual (**máscara do formato do C06** — DP-1, validação em tempo real, "Buscar prova"); **animação leve de feedback** ao identificar. Rodapé (DP-5).
- Parser do QR consistente com o C06; chamada ao `identificar`; pós-identificação (DP-2).
- Animações sobre os tokens (GPU-only, `prefers-reduced-motion`).

### 5.2 Backend — `apps/api/`
- **`POST /api/provas/identificar`** (Ports & Adapters): `resolver_prova()` (QR/manual pelo mesmo caminho), **RLS** (claims propagados), **anti-enumeração** (mesma mensagem genérica), **rate limiting 30/min** (DP-3). Validação Pydantic; logs estruturados (sem vazar dados).

### 5.3 Documentação — `docs/`
- `docs/escaneamento.md`: o endpoint + `resolver_prova()`, o formato do código (DP-1), anti-enumeração + rate limiting, a **fronteira com C11/C12** (só identifica), e as **diretrizes mobile-first**. Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Identifica QR Codes em ≤ 2 s** após o foco (RNF-002); **leitura in-app sem app externo** (RF-004).
2. ✅ **Fluxo manual sempre acessível**, mesmo com a câmera ativa; **permissão de câmera negada não bloqueia** — o manual continua disponível (RNF-014).
3. ✅ **Código inválido e código fora do escopo retornam a MESMA mensagem genérica** (anti-enumeração, RN-014); **rate limiting 30/usuário/min** ativo.
4. ✅ **QR e código manual** resolvem o **mesmo registro** pelo **mesmo caminho** (`resolver_prova()`, idempotente); a resolução **respeita a RLS**.
5. ✅ O **input manual usa o formato que o C06 gera** (DP-1); o parser do QR lê o payload do C06 corretamente.
6. ✅ **Mobile-first**: renderiza de **360 px a 768 px**, portrait e landscape; touch ≥ 44/48; **safe areas** respeitadas (notch); **botões principais no terço inferior**; contraste AA.
7. ✅ Após identificar, navega ao destino definido (DP-2); o C10 **não** transiciona nem assina; **animação de feedback** com `prefers-reduced-motion`.
8. ✅ **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**.

---

## 7. Testes desta camada

**Backend**
- `resolver_prova()`: **QR e manual** levam ao **mesmo registro**; idempotente.
- **Anti-enumeração:** código **inválido** e código **fora do escopo** (RLS) retornam a **mesma mensagem genérica** (sem diferença observável); dentro do escopo → resolve.
- **Rate limiting:** acima de 30/min → bloqueado.
- **RLS:** por perfil, a resolução respeita o escopo (claims propagados).
- Roda **offline** (Postgres local; JWTs de teste por perfil; provas via fixture).

**Frontend**
- Toggle Câmera/Manual (ambos acessíveis); **permissão de câmera negada → manual disponível** (mock de getUserMedia); input manual valida o formato do C06; "Buscar prova" só habilita com código válido.
- **Mobile-first:** layout de 360 px, portrait/landscape, touch targets, safe areas, botões no terço inferior; `prefers-reduced-motion` (feedback instantâneo).
- **E2E (Playwright):** identificar por código manual (caminho feliz) → navega ao destino (DP-2); código inválido → mensagem genérica; (mock de câmera) leitura de QR → mesmo destino.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`, confirme Waves 0–2 + C06 (formato do código, payload do QR, RLS, padrão anti-vazamento do C08).
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas (DP-1 é bloqueante).**
3. Backend: `POST /api/provas/identificar` (`resolver_prova()`, RLS, anti-enumeração, rate limiting); testes (mesmo registro por QR/manual, anti-enumeração, rate limit, escopo).
4. Frontend: tela de escaneamento mobile-first (toggle, câmera com degradação graciosa, input manual com a máscara do C06), animação de feedback; pós-identificação (DP-2).
5. Responsividade mobile (360px+, safe areas, terço inferior); `prefers-reduced-motion`.
6. `docs/escaneamento.md`.
7. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
8. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: tela de escaneamento (câmera + manual, mobile-first); endpoint `POST /api/provas/identificar` (`resolver_prova()`, anti-enumeração, rate limiting).
2. **`DECISIONS.md`** — ADRs conforme as decisões: (a) **formato do código** (resolução da DP-1 — confirmar `PRV-AAAA-MM-...` e o charset/comprimento, alinhado ao C06); (b) **fronteira C10↔C11↔C12** (C10 só identifica); (c) **anti-enumeração + rate limiting** do endpoint; (d) **lib de câmera** e diretrizes mobile-first. Status *Aceita* onde aplicável; **atualize `CLAUDE.md §2.1`** com a resolução da divergência do código.
3. **`SESSION_LOG.md`** — entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão)**, testes/cobertura (citar anti-enumeração e idempotência QR/manual), **pendências** e **próximo passo** = **W3-C11 · Máquina de Estados (14 Estados, 4 Rotas)**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** se necessário; registre o **contrato de `/api/provas/identificar`**, o **formato do código** (confirmado) e as **diretrizes mobile-first**. Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap (C10 concluído; início da Wave 3).
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **anti-enumeração** e **idempotência QR/manual**), sem erro de console/log crítico, docs do módulo, **error boundary** + degradação graciosa (câmera negada → manual), animações com `prefers-reduced-motion`, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w3-c10): ...`, `chore(w3-c10): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. a mesma mensagem genérica para inválido/fora-de-escopo, a degradação graciosa da câmera, e QR/manual resolvendo o mesmo registro), decisões registradas, pendências e o **comando exato** para iniciar a próxima sessão (**W3-C11**).

---

### Lembrete final
O C10 é a **porta de entrada física→digital** e o componente que os operadores usam **no celular, em pé, sob luz forte** — por isso o **mobile-first** (safe areas, botões no terço inferior, contraste AA) não é enfeite. Dois cuidados de segurança são inegociáveis: **anti-enumeração** (inválido e fora-de-escopo dão a **mesma** mensagem genérica) e **rate limiting**. E mantenha o **escopo enxuto**: o C10 **identifica** — quem **valida a transição** é o C11 e quem **assina** é o C12. O código manual tem que casar **exatamente** com o que o C06 imprime na etiqueta — confirme o formato antes de tudo. **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
