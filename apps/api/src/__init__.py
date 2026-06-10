"""Backend FastAPI do Sistema de Rastreio de Provas Digitais (3Studio).

Arquitetura Hexagonal (Ports & Adapters) — CLAUDE.md §5:

- ``domain``         núcleo puro; não importa nada de fora (nem framework, nem ORM).
- ``application``    casos de uso + portas (interfaces abstratas).
- ``adapters``       implementações das portas (inbound HTTP, outbound DB/storage/auth).
- ``infrastructure`` config, logging, database, app factory — wiring técnico.
- ``main``           composition root: o único lugar onde concreto encontra abstrato.

Dependências apontam sempre para dentro.
"""
