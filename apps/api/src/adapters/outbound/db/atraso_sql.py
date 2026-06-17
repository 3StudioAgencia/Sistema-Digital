"""Fragmentos SQL de "Atrasada" (W4-C16) — fonte unica para o Dashboard E o C07.

"Atrasada" (RN-008): prova ATIVA (nao terminal) cujo ULTIMO evento (ultima
movimentacao, ou ``created_at`` se nunca movimentou) e mais antigo que o
instante-limite — ``private.instante_limite_atraso(now(), delay)`` recuando o
delay configurado (C09) em horas uteis (DP-4). Tudo numa UNICA consulta
RLS-escopada (minimo de idas ao banco — RNF-020/022): o delay e lido inline do
``system_settings`` (leitura ``authenticated`` — C09/DP-2) e o limite e computado
pela funcao da migration 0020.

O Dashboard (``dashboard_repository``) e o filtro ``atrasada`` da listagem
(``provas_repository``) importam ESTES fragmentos — assim a regra de atraso e
IDENTICA nos dois lugares (um clique em "Atrasadas" leva a mesma contagem). Os
fragmentos referenciam a tabela ``provas`` SEM alias (as duas consultas a usam
crua). A lista de terminais deriva de ``ESTADOS_TERMINAIS`` (sem drift do enum).
"""

from src.domain.state_machine.rules import ESTADOS_TERMINAIS

# Estados terminais como lista SQL — derivada do dominio (sem drift): uma prova
# terminal (recebida_clicheria/cancelada) NUNCA atrasa (RN-008 fala de prova parada
# no fluxo). Aspas simples seguras: valores de enum, nunca entrada do usuario.
_TERMINAIS_SQL = ", ".join(f"'{estado.value}'" for estado in ESTADOS_TERMINAIS)

# Delay EFETIVO: sobrescrita do C09 ou o padrao 48 (mesma fonte da leitura do C09).
SQL_DELAY = (
    "COALESCE((SELECT (value #>> '{}')::int FROM system_settings "
    "WHERE key = 'delay_horas_uteis'), 48)"
)

# Instante-limite (horas uteis) — UMA chamada por query (a funcao e pura/STABLE).
SQL_LIMITE_ATRASO = f"private.instante_limite_atraso(now(), {SQL_DELAY})"

# Ultimo evento da prova: ultima movimentacao (RLS espelha provas) ou created_at.
SQL_ULTIMO_EVENTO = (
    "COALESCE((SELECT max(m.created_at) FROM movimentacoes m "
    "WHERE m.prova_id = provas.id), provas.created_at)"
)

# Predicado completo "Atrasada": ativa E parada alem do limite. Usado tanto no
# WHERE do filtro do C07 quanto na CTE de breakdown do Dashboard.
SQL_PREDICADO_ATRASADA = (
    f"provas.status NOT IN ({_TERMINAIS_SQL}) AND {SQL_ULTIMO_EVENTO} <= {SQL_LIMITE_ATRASO}"
)


__all__ = [
    "SQL_DELAY",
    "SQL_LIMITE_ATRASO",
    "SQL_PREDICADO_ATRASADA",
    "SQL_ULTIMO_EVENTO",
]
