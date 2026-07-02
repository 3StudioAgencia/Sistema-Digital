"""Eventos de domínio do realtime do dashboard (etapa 3 da migração Supabase->local).

O realtime (SSE) é um SINAL genérico: quando uma prova muda (criação C06 /
transição C11 / cancelamento C14 / reinício C15), o backend emite um ``NOTIFY``
neste canal com um payload GENÉRICO ("mudou"). O navegador, ao receber, rebusca
``GET /dashboard`` — que já vem escopado pela RLS por perfil (Matriz §7).

NADA sensível trafega pelo canal: ``NOTIFY``/``LISTEN`` NÃO sofrem RLS, então um
payload com dado de domínio (código, cliente, vendedor) vazaria entre perfis. O
escopo por perfil é garantido no refetch (a RLS de ``provas``), não no canal
(ADR-114). Por isso o payload é uma constante — e deve permanecer assim.

Fonte ÚNICA do nome do canal e do payload — compartilhada pelo publisher
(``adapters/outbound/db/event_bus_pg.py``) e pelo listener
(``infrastructure/realtime.py``).
"""

# Canal Postgres LISTEN/NOTIFY. É uma string combinada entre publisher e listener
# (não é objeto de catálogo: sem migration, sem GRANT, sem RLS).
CANAL_EVENTOS_PROVAS = "eventos_provas"

# Payload genérico do sinal "uma prova mudou" (sem dado por perfil — ver acima).
EVENTO_PROVA_MUDOU = "mudou"

__all__ = ["CANAL_EVENTOS_PROVAS", "EVENTO_PROVA_MUDOU"]
