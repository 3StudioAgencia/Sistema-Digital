# Prompt de Execução — W2-C06 · Cadastro de Prova com Seleção de Rota + Etiqueta com Código Textual

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz do repositório, as **Waves 0 e 1 concluídas** (C01–C05 mergeados) e as **duas imagens anexadas** (tela "Nova prova Digital" e o "Template etiqueta"). Este é o **primeiro componente da Wave 2** (núcleo do domínio) e a **primeira tabela de domínio de provas**. Trabalhe a sessão inteira neste único componente.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize:
- **§2 / §2.1** — fontes da verdade e divergências. *Atenção: a etiqueta do design diverge dos Requisitos (RF-003) — ver DP-1.*
- **§3** — pilares: **robustez, escalabilidade, mínimo de requisições, observabilidade** e **animações leves e suaves**.
- **§4 / §5** — stack e Ports & Adapters; gestão de schema (DAT **§2**: domínio via Alembic, enums via `CREATE TYPE`, RLS versionada).
- A **Matriz de Acesso §7** e a RBAC do C05: a página **Criar Prova é exclusiva do 3Studio**; a tabela `provas` recebe **RLS por perfil** nesta sessão (ver DP-6).

**Estado atual do repositório (Waves 0 + 1 entregues):**
- C01: **porta de storage + adapter R2** (reusar para o upload da arte), Settings, logging estruturado, DB async, Alembic.
- C04: **app shell** (sidebar + shell branco) — a tela de criação pluga aqui; tabela **`usuarios`** (a coluna `vendedor_id` de `provas` referencia um usuário de setor Vendedor).
- C05: **`access-matrix.ts`** + **middleware** (gateia "Criar Prova" para 3Studio), **Custom Access Token Hook** (claims `setor`/`user_id`), **helpers SQL de RLS** (`is_3studio()`, `current_app_user_id()`, leitura de `setor`), **propagação de claims (ADR-008)** e o **harness de equivalência**. **Reuse tudo isso — não recrie.**

**Insumos confirmados:** etiqueta **retangular 5,5 × 9,5 cm** (ver DP-2 para orientação/specs). Designs da tela de criação e da etiqueta no Figma, anexados. **Layout exatamente igual ao design** (com a reconciliação obrigatória da DP-1).

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — etiqueta, formato do código, enum, imutabilidade, RLS, geração — você **para, expõe o ponto com 2–3 opções e a sua recomendação, e aguarda a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, confirme o estado das Waves 0 + 1 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas. **DP-1 (etiqueta) é bloqueante.**
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte.
4. **Nunca invente** formato de código, identificadores de enum, nomes de rotas/variáveis, libs ou valores de design. Em dúvida, **pergunte**.

---

## 0.2 Fidelidade ao design

**Tela "Nova prova Digital"** (dentro do shell do C04): título "Nova prova Digital"; botão **"Criar Prova"** (amarelo, topo-direita); formulário em shell-branco-interno com **Nome** e **Requerimento** (linha 1), **Cliente** e **Vendedor** (linha 2), **Rota** (segmented control com 4 opções — no design a ordem é **Matriz · Filial · Lam. Matriz · Lam. Filial**, com Matriz selecionado em preto) e uma **dropzone** de upload ("Solte ou clique · JPG • PNG").

**Template da etiqueta** (Image 2): wordmark **3STUDIO** + logo (ver DP-2), "Aponte a câmera para o QR CODE", barra divisória, bloco **Nome / Requerimento / Cliente / Vendedor**, **QR Code** (à direita), "2026", "Etiqueta de rastreio". **A etiqueta precisa ser reconciliada com a DP-1** (falta o código alfanumérico em destaque e a rota).

Tokens precisos (cores, tipografia, raios, espaçamentos), ícones e o logo da etiqueta devem ser confirmados — **não chute** (DP-2, DP-7, e a confirmação de tokens; se houver link do Figma, extraia via Dev Mode/MCP).

---

## 1. Objetivo do componente

Entregar a **criação de provas digitais** com **seleção manual e obrigatória de rota** (entre as quatro), gerando o **identificador alfanumérico único**, o **QR Code** e a **etiqueta PDF imprimível**, e estabelecendo a **primeira tabela de domínio de provas** com a **rota imutável** e a **RLS por perfil** (que fecha a pendência do C05).

Referências: Backlog **C06** · Requisitos **RF-001, RF-002, RF-003, RF-010, RN-007, RN-011, US-001, RNF-017, RNF-019** · §6 (estado inicial "Criada") · §7 (Matriz) · DAT **§2, §7** · **ADR-007, ADR-008**.

---

## 1.1 Fatos do domínio (grounded nos Requisitos — não use suposições)

1. **Campos obrigatórios (RF-001, US-001):** nome, número do requerimento, cliente, **vendedor responsável**, **rota**, e **arte (JPG/PNG, máx 10 MB)**. O `vendedor` é um **usuário de setor Vendedor** (FK para `usuarios`) — necessário para a RLS (`vendedor_id`).
2. **Rota (RN-007, RF-010):** quatro opções (Matriz, Lam. Matriz, Filial, Lam. Filial), **escolha manual e livre**, independente da localização do vendedor; **imutável após a criação** (mudar rota ⇒ cancelar e recriar).
3. **QR e código (RF-002):** QR Code **único e não reutilizável**; **carrega um identificador alfanumérico único da prova**. Ou seja: o QR e o código manual são **o mesmo identificador** (ex.: `PRV-2026-06-K3T9XB`). É o identificador que o **fallback manual do C10** digita.
4. **Etiqueta (RF-003):** PDF imprimível padronizado contendo **nome, requerimento, vendedor, rota, QR Code e o código alfanumérico em texto legível, em destaque**, para fixação na pasta física; disponível para impressão/download. Template **configurável** (RN-011) — a *configuração* é do C09; **o C06 entrega o template padrão**, parametrizável.
5. **Estado inicial (§6):** ao criar, a prova nasce com status **"Criada"** e na rota selecionada (US-001). A máquina de estados (14 estados, transições) é do **C11**.
6. **DIVERGÊNCIA DA ETIQUETA (DP-1):** o design **não exibe** o **código alfanumérico em destaque** nem a **rota** — ambos **obrigatórios** por RF-003. O código é essencial para o fallback do C10. Reconciliar antes de implementar a etiqueta.

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **Tela de Criação de Prova** (dentro do shell do C04), fiel ao design + DP-1: formulário com validação em tempo real; **select de Vendedor** (usuários de setor Vendedor, carregados via backend com claims propagados); segmented control de **Rota**; **dropzone** de upload (JPG/PNG, máx 10 MB, validação client+server); botão "Criar Prova". Página **gateada para 3Studio** (middleware do C05).
- **Backend — domínio `provas`:** primeira migration de domínio de provas com **`rota_enum`** (`'matriz','lam_matriz','filial','lam_filial'`, **NOT NULL**), a coluna **`status`** (ver DP-4), `codigo` (único), `vendedor_id` (FK `usuarios`), demais campos, índices (RNF-019); **imutabilidade da rota** (DP-5).
- **Identificador + QR + Etiqueta:** geração do **código alfanumérico único** (DP-3), do **QR** (codificando o identificador) e da **etiqueta PDF** padrão (DP-2/DP-7) contendo os campos do RF-003 reconciliados (DP-1); endpoint de download/impressão.
- **Upload da arte no R2:** reusar a porta/adapter de storage do C01; validação de tipo/tamanho; chave/URL persistida na prova.
- **RLS de `provas` (fecha a pendência do C05):** políticas por perfil usando os **helpers do C05** (3Studio/Clicheria todas; Vendedor as próprias; Motorista as "Em Trânsito"), versionadas em `/migrations/rls/`; **estender o harness de equivalência** às células de `provas` (via fixtures que inserem provas em diversos status).
- **Endpoint de criação** (FastAPI, Ports & Adapters) com validação Pydantic de RF-001/RN-007, transação atômica (RNF-017) e logging estruturado.
- **Animações** (continuidade do C03/C04, sobre os tokens; GPU-only; `prefers-reduced-motion`): entrada do formulário, microinterações do segmented control e da dropzone, feedback de criação/sucesso (toast do C04).
- **Documentação** (`docs/provas.md`): modelo de `provas`, formato do código, geração de QR/etiqueta, RLS de provas, imutabilidade da rota.
- **Testes** (§7) e **Protocolo de Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Máquina de estados / transições / movimentações / tabela de audit log** (Componente **11**). O C06 só cria a prova no estado **"Criada"**; logging de criação via log estruturado (o audit log imutável é do C11).
- ❌ **Listagem/pesquisa/filtros de provas** (Componente **07**) e **detalhe/timeline** (Componente **08**). Após criar, navegue para um **placeholder** (DP-7).
- ❌ **Escaneamento / endpoint de identificação** (`POST /api/provas/identificar`) — Componente **10**. O C06 só **gera** o código/QR; o C10 os consome.
- ❌ **Configuração do template de etiqueta** (RN-011/RF-022) — Componente **09**. O C06 entrega o **template padrão parametrizável**.
- ❌ Edição de rota (proibida por RN-007) e qualquer item de Waves 3+.

> Vontade de adiantar transições, listagem ou identificação: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Rota imutável de verdade:** Pydantic sem caminho de update para `rota`; **PATCH em `rota` → 422**; e **imutabilidade no banco via trigger** `BEFORE UPDATE` que rejeita `NEW.rota <> OLD.rota` (uma `CHECK` não compara OLD/NEW — então é trigger, não "constraint" literal). Enum `rota_enum` **NOT NULL desde a primeira migration**.
2. **Código único e não reutilizável:** formato `PRV-AAAA-MM-XXXXXX` (DP-3); **constraint UNIQUE** em `codigo`; geração com **retry em colisão**; charset **não ambíguo** para digitação manual (DP-3). O QR codifica o identificador (DP-3).
3. **Upload seguro:** validar **tipo (JPG/PNG)** e **tamanho (≤ 10 MB)** no client **e** no server; armazenar no **R2** (porta/adapter do C01); nunca confiar só na extensão (checar content-type/magic bytes).
4. **RLS de `provas`:** versionada em `/migrations/rls/` **antes** de aplicar; reaplicável após recriação de tabela; usar os **helpers do C05**; o acesso a `provas` via backend roda com **claims propagados** (ADR-008) para a RLS valer.
5. **Atomicidade (RNF-017):** criar prova + persistir arte + gerar código é uma operação **consistente**; falha em qualquer etapa não deixa prova/arte órfã.
6. **Escalabilidade/mínimo de requisições:** índices nas colunas de filtro/ordenação (RNF-019, antecipando o C07); sem N+1 (ex.: carregar vendedores em uma consulta).
7. **Geração de etiqueta no tamanho físico exato** (DP-2): o PDF sai em **95 × 55 mm** (confirmar orientação), QR com resolução adequada para leitura, código legível.
8. **Estilização:** **CSS Modules**; fidelidade ao design + DP-1. Animações `transform`/`opacity`, `prefers-reduced-motion` obrigatório.
9. **Stateless** (RNF-018); **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada. **DP-1 é bloqueante.**

### Bloco A — Etiqueta

**DP-1 — Reconciliação da etiqueta (BLOQUEANTE).**
O design **omite** o **código alfanumérico em destaque** e a **rota**, ambos exigidos por RF-003 (e o código é o que o fallback do C10 digita). **[Recomendado]** incluir, mantendo o estilo do design: o **código alfanumérico em fonte grande** (posicionado de forma destacada, ex.: logo abaixo do QR) e a **rota selecionada** (badge/linha). Confirmar o layout reconciliado — **ou** fornecer a etiqueta atualizada no Figma. *(A etiqueta não pode sair sem o código.)*

**DP-2 — Dimensões, orientação e assets da etiqueta.**
Confirmar **95 mm (largura) × 55 mm (altura), landscape** (o design é landscape; "5,5 × 9,5" → 5,5 alt × 9,5 larg). Confirmar **margens/bleed**, **resolução do QR**, e que o **PDF sai no tamanho físico exato** para impressão/fixação. Confirmar o **logo ao lado do 3STUDIO** ("studio &ART!"): é **fixo** (identidade) ou é o **logo do cliente** (variável por prova)?

### Bloco B — Identificador e QR

**DP-3 — Formato do código, charset e payload do QR.**
**[Recomendado]** `PRV-AAAA-MM-XXXXXX` com sufixo de **6 caracteres** em **charset não ambíguo** (sem `0/O`, `1/I/L`) para reduzir erro de digitação no fallback; **UNIQUE + retry** em colisão; o **QR codifica o código** (alternativa: URL/deep-link contendo o código, se quiser abertura por câmera nativa). Confirmar formato, charset e o payload do QR — **alinhado com a máscara de digitação do C10**.

### Bloco C — Domínio e fronteiras

**DP-4 — Enum de status (`status_prova_enum`).**
**[Recomendado]** o C06 cria o **`status_prova_enum` completo (os 14 estados da Requisitos §6)** + default **'criada'**, para a coluna nascer corretamente tipada e evitar `ALTER TYPE` depois; o **C11** detém transições/movimentações. Confirmar (vs. enum mínimo agora) e a **convenção de nomes** dos identificadores (derivada de §6, usada por C06 e C11).

**DP-5 — Imutabilidade da rota.**
**[Recomendado]** trigger `BEFORE UPDATE` rejeitando alteração de `rota` + Pydantic sem update de rota + PATCH `rota` → 422. Confirmar.

**DP-6 — RLS de `provas` (fecha a pendência do C05).**
**[Recomendado]** autorar e aplicar a RLS por perfil de `provas` com os **helpers do C05**: 3Studio/Clicheria veem todas; **Vendedor** `vendedor_id = current_app_user_id()`; **Motorista** `status ∈` estados "Com Motorista (*)"; e **estender o harness de equivalência** às células de `provas` (testar via fixtures inserindo provas em vários status, inclusive os "Em Trânsito", sem depender do C11). Confirmar. Confirmar também que **`vendedor` é FK para `usuarios`** (setor Vendedor).

**DP-7 — Geração, libs e fluxo pós-criação.**
**[Recomendado]** QR e PDF gerados **sob demanda** no backend (`GET /api/provas/{id}/etiqueta.pdf`), stateless (sem armazenar a etiqueta); arte no **R2**; após "Criar Prova" → **toast de sucesso + download/impressão da etiqueta** + navegação a um **placeholder** (até C07/C08 existirem). Confirmar: as **libs** (ex.: `segno` p/ QR, `reportlab`/`fpdf2` p/ PDF — ou a critério do `CLAUDE.md §4`), geração sob demanda vs. armazenada, e o destino pós-criação.

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Backend / Banco — `apps/api/`
- **Migration de domínio** (`versions/00xx_provas.py`): `rota_enum` (NOT NULL), `status_prova_enum` (DP-4), tabela `provas` (`id`, `codigo` UNIQUE, `nome`, `requerimento`, `cliente`, `vendedor_id` FK→`usuarios`, `rota`, `status` default 'criada', `arte_key`/url, `created_at`/`updated_at`, e o que o domínio exigir), **índices** (RNF-019); `downgrade`.
- **Imutabilidade da rota** (DP-5): trigger versionado.
- **RLS de `provas`** (`migrations/rls/provas_*.sql`): políticas por perfil com helpers do C05 (DP-6).
- **Domínio/aplicação/adapters:** modelo `Prova`, schemas Pydantic (validação RF-001/RN-007), **serviço de geração de código** (formato/charset/retry — DP-3), **gerador de QR**, **gerador de etiqueta PDF** (template padrão parametrizável — DP-1/DP-2), porta de storage (R2, C01) para a arte.
- **Endpoints HTTP:** `POST /api/provas` (criação atômica), `GET /api/provas/{id}/etiqueta.pdf` (download/impressão), e o endpoint que **lista vendedores** para o select (ou reusar o do C04). Erros padronizados; logs estruturados.

### 5.2 Frontend — `apps/web/`
- **`app/(app)/nova-prova/page.tsx`** (ou rota conforme a sidebar) — formulário fiel ao design + DP-1; select de Vendedor; segmented control de Rota; dropzone (validação client); estados de loading/erro/sucesso; **gateada a 3Studio** (middleware C05).
- Fluxo pós-criação (DP-7): toast + download/impressão da etiqueta + navegação a placeholder.
- Animações sobre os tokens (GPU-only, `prefers-reduced-motion`).

### 5.3 Documentação — `docs/`
- `docs/provas.md`: modelo `provas`, formato do código, geração de QR/etiqueta (tamanho físico, template), RLS de provas, imutabilidade da rota. Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Criar prova sem rota selecionada retorna erro de validação claro**; campos obrigatórios validados (RF-001).
2. ✅ Após a criação, **PATCH na coluna `rota` é rejeitado (422)** e o banco rejeita a alteração (trigger). Enum `rota_enum` NOT NULL.
3. ✅ **Código alfanumérico único** gerado (formato/charset da DP-3), **UNIQUE**, com retry em colisão; o **QR codifica esse identificador**.
4. ✅ **Etiqueta PDF** exibe **nome, requerimento, vendedor, rota, QR Code e o código alfanumérico em destaque** (RF-003, reconciliado na DP-1), no **tamanho físico exato** (DP-2), disponível para impressão/download.
5. ✅ **Arte** validada (JPG/PNG, ≤ 10 MB, client+server) e persistida no **R2**; criação **atômica** (sem prova/arte órfã).
6. ✅ **RLS de `provas`** ativa: 3Studio/Clicheria veem todas; **Vendedor só as suas**; **Motorista só as "Em Trânsito"**; **query SQL direta fora do escopo retorna 0 registros**; o **harness de equivalência** cobre as células de `provas`.
7. ✅ A prova nasce com status **"Criada"** e na rota selecionada (US-001).
8. ✅ **Tela de criação** fiel ao design (+ DP-1), **gateada a 3Studio**, responsiva; **animações** com `prefers-reduced-motion`.
9. ✅ Índices de filtro/ordenação presentes (RNF-019); **stateless**; **sem segredos versionados**; **R$ 0**.
10. ✅ `ruff`, `mypy (strict)`, `pytest`, `pnpm lint`/`build` **verdes**; migrations `upgrade`/`downgrade` em ambiente limpo; RLS reaplicável de `/migrations/rls/`.

---

## 7. Testes desta camada

**Backend / Banco**
- Validação RF-001 (campos obrigatórios; rota obrigatória); arte rejeitada se tipo/tamanho inválidos.
- Imutabilidade da rota: PATCH `rota` → 422; UPDATE direto no banco → rejeitado pelo trigger.
- Código: unicidade (constraint), retry em colisão simulada, charset não ambíguo; QR codifica o identificador correto.
- Etiqueta: PDF contém os campos do RF-003 (DP-1) e o tamanho físico correto.
- Criação atômica: falha no upload/geração não deixa prova órfã.
- **RLS de `provas`** (fecha o C05): para cada perfil, query direta retorna o escopo correto (Vendedor só as suas via `vendedor_id`; Motorista só "Em Trânsito" — testar inserindo provas com status "Com Motorista (*)" via fixture; 3Studio/Clicheria todas; perfil sem acesso → 0 registros). **Equivalência** middleware↔RLS para as células de provas.
- Roda **offline** (Postgres local; R2 mockado; JWTs de teste com claims por perfil).

**Frontend**
- Render fiel + DP-1; validação em tempo real; dropzone aceita só JPG/PNG ≤ 10 MB; estados de loading/erro/sucesso; fluxo pós-criação (download da etiqueta).
- Página **negada a perfil não-3Studio** (gating do C05).
- `prefers-reduced-motion` (animações instantâneas).
- **E2E (Playwright):** criar prova (caminho feliz) + baixar etiqueta; validações; tentativa de acesso por perfil não autorizado.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`, confirme Waves 0 + 1 (R2, usuarios, helpers de RLS, middleware, access-matrix) no repositório.
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas (DP-1 é bloqueante).**
3. Migration de domínio `provas` (enums, índices, trigger de imutabilidade); `alembic upgrade head`/`downgrade`.
4. RLS de `provas` com os helpers do C05; testes de RLS + extensão do harness de equivalência.
5. Serviços de backend: geração de código (DP-3), QR, etiqueta PDF (DP-1/DP-2), upload no R2; endpoint `POST /api/provas` (atômico) + `GET .../etiqueta.pdf`; testes verdes.
6. Tela de criação (formulário, select de Vendedor, segmented control, dropzone), gateada a 3Studio; fluxo pós-criação (DP-7).
7. Animações sobre os tokens; responsividade; `prefers-reduced-motion`.
8. `docs/provas.md`.
9. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
10. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: criação de provas; primeira tabela de domínio `provas` + `rota_enum`/`status_prova_enum`; geração de código/QR/etiqueta PDF; upload de arte no R2; RLS de `provas`; tela de criação.
2. **`DECISIONS.md`** — novos ADRs: (a) **modelo de `provas`** + `rota_enum` + imutabilidade via trigger; (b) **formato/charset do código** + payload do QR (alinhado ao C10); (c) **`status_prova_enum` completo** e a fronteira C06↔C11 (transições no C11); (d) **geração de etiqueta** (template padrão, tamanho físico) e a reconciliação da etiqueta (DP-1); (e) **RLS de `provas`** (fecha a pendência do C05, usando os helpers). Status *Aceita* onde aplicável; **atualize `CLAUDE.md §2.1`** com a reconciliação da etiqueta.
3. **`SESSION_LOG.md`** — nova entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão + etiqueta reconciliada)**, testes/cobertura (citar a cobertura da RLS de provas e a extensão do harness), **pendências** e **próximo passo** = **W2-C07 · Listagem, Pesquisa e Filtros de Provas**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** (gerar etiqueta localmente; rodar a criação de prova); registre o **modelo de `provas`**, o **formato do código** e que a **RLS de provas** agora existe (helpers do C05 em uso). Enxuto e verdadeiro.
5. **`README.md`** — atualize setup (libs de QR/PDF; bucket/arte no R2) e o roadmap (C06 concluído; início da Wave 2).
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **imutabilidade da rota**, **RLS por perfil** e **equivalência**), **migration versionada e documentada**, **RLS de `provas` versionada** em `/migrations/rls/`, sem erro de console/log crítico, docs do módulo, idempotência/atomicidade da criação, error handling, animações com `prefers-reduced-motion`, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w2-c06): ...`, `chore(w2-c06): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. a etiqueta PDF gerada com o código em destaque e a prova de que a RLS bloqueia query direta fora do escopo), decisões registradas, pendências e o **comando exato** para iniciar a próxima sessão (**W2-C07**).

---

### Lembrete final
Esta é a **porta de entrada do domínio**: a prova nasce aqui, e o **código alfanumérico** que você imprime na etiqueta é o que sustenta todo o rastreamento — inclusive o **fallback manual do C10**. Por isso a DP-1 é inegociável: **etiqueta sem o código em destaque quebra o sistema na prática.** A **rota imutável** e a **RLS por perfil** precisam estar sólidas, porque a Wave 3 inteira (escaneamento, máquina de estados, assinatura) se apoia nesta tabela. **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
