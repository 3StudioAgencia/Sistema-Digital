"""Máquina de estados do fluxo de provas (W3-C11) — o coração do domínio.

Módulo arquitetural da Requisitos v1.0 §6 (DAT §4 / CLAUDE.md §5.3):

- ``enums.py`` — ``Acao`` (ações de transição) e ``Autorizacao`` (quem pode
  acionar cada transição: setor operacional OU flag admin — ADR-023).
- ``rules.py`` — ``TRANSITION_RULES``: a §6 inteira como estrutura IMUTÁVEL,
  indexada por ``(rota, estado_atual)``. Vive em código versionado, NUNCA no
  banco. Sem wildcard/fallback: transição não listada é rejeitada (422).
- ``machine.py`` — ``avaliar_transicao``: função PURA que valida
  ``(rota, estado, ação, perfil)`` contra ``rules.py`` (422/403) e o motivo
  obrigatório, devolvendo a transição ou levantando erro de domínio.

A PERSISTÊNCIA da transição (tabela ``movimentacoes``, atomicidade, idempotência)
é do caso de uso (``application/transicoes.py``); aqui é só a regra pura.
"""
