# Prompt de Remediação — Auditoria da Wave 1

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, a **Wave 1 mergeada** (C03 · C04 · C05) e o **relatório de auditoria já gerado** em `docs/audits/AUDITORIA-WAVE-1.md`. Esta sessão **corrige os achados** da auditoria para que a Wave 1 fique pronta (veredito **GO**) antes da Wave 2. Trabalhe a sessão inteira nisto.

---

## 0. Papel e contexto

Você é um engenheiro de software sênior fazendo a **remediação** de uma auditoria já realizada. O insumo desta sessão é o **relatório de auditoria** — você não recomeça a análise; você **resolve os achados** que ela registrou, com evidência de que cada um foi de fato fechado e de que **nada regrediu**.

**Leia, antes de qualquer alteração:** `docs/audits/AUDITORIA-WAVE-1.md` (a fonte de trabalho), `CLAUDE.md` (pilares §3, arquitetura §5, DoD §8, regras §11), `DECISIONS.md` (ADRs do C03/C04/C05) e `SESSION_LOG.md` (pendências declaradas). Tenha à mão os Requisitos §5/§7, o Backlog (critérios de aceitação + DoD global §2) e o DAT §2/§7.

**Objetivo:** resolver os achados (prioritariamente **Críticos** e **Altos**), re-verificar a Wave 1 inteira e **atualizar o veredito** do relatório para **GO** — ou, se algo não puder ser resolvido sem o dono, deixar claro o que falta.

---

## 0.1 Regras da remediação (INVIOLÁVEIS)

1. **DIRIGIDA PELO RELATÓRIO.** A lista de trabalho são **os achados do relatório** — nada além disso. Não “aproveite para” refatorar, renomear ou “melhorar” o que não é achado. Qualquer problema novo que você notar e que **não** esteja no relatório: **registre como observação e pergunte**, não corrija por conta própria.
2. **ORDEM DE SEVERIDADE.** Resolva **Críticos** primeiro, depois **Altos**, depois os **Médios/Baixos** que o dono autorizar. **Observações** e melhorias só se o dono pedir.
3. **PLANO ANTES DE CÓDIGO.** Antes de tocar **qualquer** arquivo, produza o **Plano de Remediação** (§2) e **aguarde aprovação**. Não comece a corrigir sem isso.
4. **UMA CORREÇÃO POR VEZ, RE-VERIFICANDO.** Para cada achado: faça a **correção mínima** → adicione/ajuste o **teste que prova** que o achado foi fechado → rode os checks relevantes → confirme que o achado **realmente** se resolveu **e que nada quebrou** → **commit semântico** referenciando o ID do achado. Não faça correções em lote “no escuro”.
5. **NÃO QUEBRAR ACESSO LEGÍTIMO.** Correções de RLS/RBAC devem rodar testes **positivos e negativos**: o perfil autorizado **continua** vendo seus dados, e o não autorizado recebe **0 registros**. Uma “correção” que **super-restringe** é um novo defeito.
6. **FALSO-POSITIVO É VÁLIDO.** Se um achado, na sua análise, for **intencional/correto** (falso-positivo do auditor), **não force uma correção**: marque como **Não-corrigido (falso-positivo)** com **justificativa**, e **confirme com o dono** antes de fechá-lo assim.
7. **AÇÕES EXTERNAS EXIGEM CONFIRMAÇÃO.** Qualquer passo fora do código — **rotacionar um segredo** no dashboard do Supabase, **reescrever histórico do git**, alterar configuração de ambiente — só após **confirmação explícita** do dono (têm implicação operacional).
8. **PRESERVE A TRILHA.** Ao final, **atualize o relatório** marcando cada achado como **Resolvido / Adiado (dívida rastreada) / Não-corrigido (falso-positivo)** com evidência, e atualize os documentos de contexto (a remediação **muda** o código).
9. **PARE E PERGUNTE.** Diante de qualquer ambiguidade na abordagem de correção, de um trade-off, ou de um achado que pareça intencional, **pare e pergunte** antes de alterar.

---

## 1. Entrada — leitura e classificação dos achados

1. Leia `docs/audits/AUDITORIA-WAVE-1.md` e **enumere todos os achados** por **ID** e **severidade**.
2. Separe em dois grupos:
   - **Obrigatório antes da Wave 2:** todos os **Críticos** e **Altos**.
   - **Decisão do dono:** **Médios / Baixos / Observações** (corrigir agora vs. seguir como **dívida rastreada**).
3. Caso o relatório **já seja GO sem Críticos/Altos**: confirme com o dono se deve abordar algum **Médio/Baixo** agora ou **seguir direto** para a Wave 2 (e então esta sessão fica curta: só os itens que ele escolher + a re-verificação).

---

## 2. Plano de Remediação — apresente e aguarde aprovação (ANTES de codificar)

Para **cada achado** (na ordem de severidade), apresente em bloco:
- **ID e severidade** + resumo do achado (do relatório).
- **Abordagem da correção** proposta (o que muda, quais arquivos).
- **Teste** que vai provar o fechamento (novo ou ajustado).
- **Risco/efeito colateral** e como vai garantir que nada regrida.
- **Classificação:** **Correção confirmada** (fix óbvio, conforme o relatório) · **Precisa de decisão** (trade-off/ambiguidade) · **Suspeita de falso-positivo** (com justificativa) · **Requer ação externa** (rotação/scrub/config — precisa de confirmação).

Em **uma rodada**, peça a decisão do dono sobre: (a) os achados **“Precisa de decisão”**; (b) quais **Médios/Baixos** corrigir vs. adiar; (c) os **suspeitos de falso-positivo**; (d) autorização para as **ações externas**. **Aguarde a resposta.** Os “Correção confirmada” podem ser executados sem ida e volta adicional, mas só **após** esta aprovação geral.

---

## 3. Execução (após aprovação)

Para cada achado aprovado, em **ordem de severidade**:

- **Correção mínima e cirúrgica**, conforme o plano. Sem escopo extra.
- **Tratamento especial de achados de SEGURANÇA:**
  - **Segredo vazado:** remover do código **não basta**. É preciso (i) **rotacionar** o segredo (dashboard/provedor — ação externa, confirmada), (ii) **remover do histórico do git** se foi commitado (reescrita de histórico — ação externa, confirmada), (iii) **invalidar** a chave antiga, e (iv) **re-`grep`** do bundle/env para confirmar que sumiu. Só feche o achado quando os quatro estiverem feitos.
  - **RLS contornável (role owner/`BYPASSRLS`, RLS desabilitada, `FORCE` ausente):** corrigir o role/política e **provar** com query direta (perfil não autorizado → 0 registros) **e** o teste positivo (autorizado vê seus dados).
  - **Verificação de JWT frouxa / claim na posição errada / hook mal configurado:** corrigir e provar com tokens de teste (válido/expirado/`aud` errada → comportamento correto).
- **Disciplina de migration/RLS (DAT §2):** se a correção exigir migration/RLS nova, ela é **aditiva**, **versionada** (`.sql` em `/migrations/rls/` antes de aplicar), **reaplicável** após recriação de tabela, e **`upgrade`/`downgrade` limpos** em banco de teste.
- **Verificação imediata:** rode o teste que prova o achado fechado **e** os checks da área afetada; confirme que **nada quebrou**.
- **Commit semântico** por achado (ou grupo lógico): `fix(w1-audit): <ID> <resumo>` (use `chore`/`test`/`docs` conforme a natureza). Mantenha os commits **rastreáveis ao ID**.

---

## 4. Re-verificação final (depois de todas as correções)

Rode a **suíte completa de verificação da Wave 1** e registre a saída real:
- `ruff`, `mypy --strict`, lint e **build** do front — verdes.
- `pytest` com **cobertura** (≥ 80% domínio/serviço); todos verdes.
- **Testes negativos e positivos** de RLS/Matriz por perfil; **harness de equivalência** middleware↔RLS.
- **`prefers-reduced-motion`** (degradação instantânea); **idempotência** de escrita (RNF-015).
- **Migrations `upgrade`/`downgrade`** em banco limpo + **reaplicação das RLS** a partir de `/migrations/rls/`.
- **Sem erros no console** do browser nem log de erro crítico.

Confirme que **cada item que antes falhava agora passa** e que **nenhum item que passava regrediu**.

---

## 5. Atualização do relatório e dos documentos

1. **`docs/audits/AUDITORIA-WAVE-1.md`** — para cada achado, marque o desfecho: **Resolvido** (com a evidência: teste que agora passa / commit) · **Adiado** (dívida rastreada, com justificativa e prioridade) · **Não-corrigido (falso-positivo)** (com justificativa aprovada). Atualize o **VEREDITO** (GO/NO-GO) com base no estado pós-remediação. *(Acrescente como apêndice/seção de remediação; não apague o conteúdo original da auditoria.)*
2. **`CHANGELOG.md`** — em `[Unreleased] → Fixed`, liste as correções (referenciando os IDs).
3. **`DECISIONS.md`** — se alguma correção **mudou uma decisão** ou exigiu um novo ADR (ex.: troca de role de conexão, mudança na posição dos claims), registre/atualize.
4. **`SESSION_LOG.md`** — entrada de remediação: o que foi corrigido, o que ficou como dívida, o **veredito atualizado**, e o **próximo passo** = **W2-C07 · Listagem, Pesquisa e Filtros** (se GO).
5. **`CLAUDE.md` / `README.md`** — só se comandos, setup ou comportamento mudaram.

---

## 6. Encerramento

**Apresente no chat:**
- **Resumo dos achados:** quantos **Resolvidos / Adiados / Não-corrigidos (falso-positivo)**, por severidade.
- **Resultado da re-verificação** (saída resumida de lint/types/build/testes/cobertura + testes de RLS/equivalência).
- **VEREDITO atualizado:** **GO** ou **NO-GO** para a Wave 2, justificado.
- **Dívida remanescente** rastreada (Médios/Baixos adiados), se houver.
- Se **GO**: o **comando exato** para iniciar a próxima sessão (**W2-C07**).
- Se ainda **NO-GO**: exatamente **o que falta** e por quê (ex.: um Crítico que depende de ação/decisão do dono).

Não commite nada além das correções aprovadas, dos testes e das atualizações de documento. Em qualquer dúvida nova, **pare e pergunte**.

---

### Lembrete final
Remediar não é “fazer o teste passar” — é **fechar a causa raiz** do achado **sem abrir outro buraco**. Os erros mais perigosos aqui são os silenciosos: uma RLS “corrigida” que passa a **super-restringir** e quebra o acesso legítimo; um segredo removido do arquivo mas **ainda válido e ainda no histórico**; um claim ajustado que faz a política retornar tudo. Por isso cada correção é provada com testes **positivos e negativos**, uma de cada vez, e o segredo vazado só fecha após **rotação + scrub + reverificação**. **Na dúvida, pare e pergunte.** Um **GO** só vale quando a re-verificação inteira sustenta.
