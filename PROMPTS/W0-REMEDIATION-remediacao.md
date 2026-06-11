# Prompt de Execução — W0-REMEDIATION · Remediação da Wave 0 (genérico)

> **Como usar:** cole este prompt no Claude Code **após a sessão de auditoria**, com o relatório **`docs/audits/wave-0-audit.md`** presente e os arquivos de contexto na raiz. Esta sessão **corrige** os achados da auditoria (modifica código) e termina com um **gate de re-verificação**. É genérica: resolve **o que estiver no relatório**, por severidade — não depende de achados específicos.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior executando a **remediação** da Wave 0 do projeto **Rastreio de Provas Digitais** (3Studio). Ao contrário da auditoria (somente-leitura), **esta sessão altera o código** — mas com disciplina cirúrgica: corrige exatamente os achados, verifica cada correção e não introduz regressão nem escopo novo.

**Leia antes de começar:** o relatório **`docs/audits/wave-0-audit.md`** (lista de achados `W0-A-NNN`, severidades, evidências e correções recomendadas), `CLAUDE.md` (inteiro — as correções **devem respeitar** §2, §3, §5, §8, §11), `DECISIONS.md` (ADRs) e as entradas **W0** no `SESSION_LOG.md`.

> **Pré-requisitos:**
> - Se **`docs/audits/wave-0-audit.md` não existir**, **pare** e instrua a rodar a sessão de auditoria antes.
> - Se o relatório indicar **zero achados**, **não fabrique trabalho**: rode o gate de re-verificação (§5), confirme que está tudo verde, registre no `SESSION_LOG.md` e libere a Wave 1. Encerre.

---

## 1. Objetivo

Levar a Wave 0 a **conformidade verificada** com o Backlog (C01/C02), o DAT, o `CLAUDE.md`, a DoD e os ADRs — resolvendo os achados da auditoria por ordem de severidade/dependência, **sem regressões** e **sem ampliar escopo**, deixando rastreabilidade `achado → correção → evidência`.

---

## 2. Insumo e princípios invioláveis

- **Fonte do trabalho:** os achados do relatório. Trate-os como a lista de tarefas; **corrija por ID**.
- **Correção mínima e correta:** implemente a correção alinhada às regras do `CLAUDE.md`. Siga a "correção recomendada" do achado **a menos que** exista uma solução mais aderente às regras do projeto — nesse caso, faça a melhor e **registre o porquê** no log de remediação. Nunca resolva um achado **violando outra regra** (ex.: não conserte cobertura desligando checagem; não exponha segredo para "facilitar" deploy).
- **Sem escopo novo:** remediação ≠ novas features/componentes. Não antecipe Wave 1+. Corrigir a Wave 0 para ficar conforme — nada além.
- **Achados emergentes:** se uma correção revelar um problema **novo** não listado, **não o ignore**: registre-o no log (continuando a numeração, ex.: `W0-A-101+`), corrija-o **se for Blocker/High**, caso contrário registre como dívida e siga.
- **Decisões que você não pode tomar com segurança** (ex.: escolha de plataforma de deploy — ADR-009 *Revisável*): aplique o **default documentado** no `DECISIONS.md` e **anote claramente**; se **não houver** default seguro, marque o achado como **`DECISÃO NECESSÁRIA`** no log e **não chute** — deixe o restante resolvido.
- **Greenfield:** como não há dados de produção, **migrations podem ser revisadas** (corrigir a baseline é aceitável), desde que a cadeia permaneça válida e `upgrade`/`downgrade` sejam testados em banco limpo.
- **Rastreabilidade:** cada correção vira commit semântico referenciando o ID (`fix(w0-a-003): ...`, `test(w0-a-007): ...`, `ci(w0-a-012): ...`, `docs(w0-a-015): ...`).

---

## 3. Política por severidade (o que fazer com cada nível)

- **Blocker** → **corrigir e verificar obrigatoriamente** nesta sessão. A Wave 0 não é liberada com Blocker em aberto.
- **High** → **corrigir e verificar** nesta sessão.
- **Medium** → **corrigir nesta sessão** por padrão; só **adie com justificativa registrada** se for de alto risco/grande esforço que comprometa a estabilidade agora.
- **Low / Nit** → **corrigir em lote se for barato**; caso contrário, **adiar como dívida registrada** (sem virar escopo). Evite que cosméticos atrasem os críticos.
- **Todo adiamento** é registrado no log com **motivo** e **severidade** (vira backlog de dívida técnica).

---

## 4. Procedimento de remediação (loop por achado, em ordem de prioridade)

Ordene por **severidade × dependência** (corrija pré-requisitos primeiro). Para **cada** achado:

1. **Entenda** — releia evidência, `Esperado × Atual`, referência (RF/RNF/ADR/DoD/Backlog) e correção recomendada.
2. **Implemente** a correção mínima e correta, aderente ao `CLAUDE.md`.
3. **Cubra com teste** — adicione/ajuste teste que falharia antes e passa depois (prevenção de regressão). Para achados de config/CI/docs, ajuste a verificação correspondente.
4. **Verifique localmente (alvo)** — rode a checagem específica daquela área e confirme que o sintoma do achado sumiu.
5. **Commite** com mensagem referenciando o ID.
6. **Registre status** no log de remediação (`Resolvido` / `Adiado + motivo` / `Decisão necessária`).

> Trabalhe em incrementos pequenos e verificáveis. **Não** re-audite do zero — confie nos achados como lista de trabalho, mas **verifique suas próprias correções**.

---

## 5. Gate de re-verificação (OBRIGATÓRIO antes de encerrar)

Reexecute **toda** a suíte de verificação da Wave 0 (a mesma da auditoria) e confirme verde:

```bash
# Domínio sem dependências de framework (deve ser vazio):
grep -rEn "import (fastapi|sqlalchemy|boto3)" apps/api/src/domain || echo "OK: domain limpo"
# Segredos versionados (inspecionar resultados):
git grep -nE "(SECRET|PASSWORD|ACCESS_KEY|service_role|eyJ[A-Za-z0-9_-]{10,})" -- . ':!*.example' ':!*.md' || echo "Sem matches óbvios"

docker compose up -d db
cd apps/api && uv sync && uv run ruff check . && uv run mypy src \
  && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head \
  && uv run pytest --cov
uv run python -m src.tasks.keep_alive            # sucesso contra DB local

cd ../web && pnpm install && pnpm lint && pnpm build
git ls-files | grep -E "uv.lock|pnpm-lock.yaml"  # lockfiles versionados
```

**Critérios do gate:**
- ✅ **Zero Blocker e zero High** em aberto.
- ✅ Os itens da **matriz de conformidade** que estavam `FAIL`/`PARTIAL` para os achados tratados agora estão `PASS`.
- ✅ Todas as checagens acima **verdes** (lint, types, migrations up/down, testes, build, lockfiles, sem segredos).
- ✅ **Nenhuma regressão** introduzida (nada que estava `PASS` virou `FAIL`).

Se qualquer checagem falhar, **corrija e reexecute** até passar (exceto adiamentos Low/Nit explicitamente justificados, que **nunca** podem ser Blocker/High).

---

## 6. Entregáveis e atualização de documentos

1. **Log de remediação — `docs/audits/wave-0-remediation.md`:**
   - Cabeçalho (data, commit/branch, relatório de origem).
   - **Tabela achado → status:** `W0-A-NNN` · severidade · `Resolvido | Adiado(motivo) | Decisão necessária` · commit/ref · evidência da correção (saída de teste/comando).
   - **Resumo:** quantos resolvidos/adiados por severidade; resultado do gate (§5); itens `DECISÃO NECESSÁRIA` destacados para o responsável.
2. **Anotar o relatório de auditoria** (`docs/audits/wave-0-audit.md`): adicione, por achado, uma linha **"Status pós-remediação"** e atualize a **matriz de conformidade** para o estado pós-correção (ou aponte para o log de remediação).
3. **Protocolo de Encerramento (`CLAUDE.md §10`):**
   - **`CHANGELOG.md`** — em `[Unreleased] → Fixed/Changed`, descreva as correções referenciando os IDs.
   - **`DECISIONS.md`** — **confirme/ajuste** ADRs tocados pela remediação (ex.: se um achado era "ADR-007/010/012 não confirmado", mova de *Proposta* para *Aceita*); registre qualquer decisão nova.
   - **`SESSION_LOG.md`** — nova entrada: objetivo, achados resolvidos/adiados, resultado do gate, `DECISÃO NECESSÁRIA` pendentes e **próximo passo** (= **retomar a Wave 1 · W1-C03**).
   - **`CLAUDE.md §9` / `README.md`** — atualize comandos/roadmap **se** algo estrutural mudou.
4. **Commits semânticos** por achado/grupo lógico, **árvore limpa, sem segredos versionados, lockfiles atualizados.**

---

## 7. Encerramento

Ao final, **apresente um resumo**:
- Achados **resolvidos × adiados**, por severidade.
- **Resultado do gate (§5):** verde? o que (se algo) permanece e por quê.
- Itens **`DECISÃO NECESSÁRIA`** que dependem de você (ex.: plataforma de deploy).
- Caminhos do **log de remediação** e do relatório atualizado.
- **Comando exato** para iniciar a próxima sessão (retomar a Wave 1, W1-C03).

---

### Lembrete final
Conserte com o mesmo rigor com que se constrói: **correção mínima, testada e aderente às regras**, sem regressão e sem escopo novo. **O gate de re-verificação é sagrado** — a Wave 0 só está liberada quando estiver verde e sem Blocker/High em aberto. Diagnóstico foi a etapa anterior; aqui é a **cirurgia limpa**.
