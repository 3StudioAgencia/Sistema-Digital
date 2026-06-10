"""Núcleo de domínio — entidades, value objects e regras de negócio puras.

REGRA DE DEPENDÊNCIA (CLAUDE.md §5.2): este pacote NÃO importa nada de fora do
próprio ``domain`` — nem FastAPI, nem SQLAlchemy, nem Pydantic-settings, nem
qualquer adapter. Violações são bloqueadas em code review.

Conteúdo previsto (waves futuras — não implementar antes da hora):
- Wave 2 (C06+): entidades de Prova e value objects (código PRV-AAAA-MM-NNNNNN).
- Wave 3 (C11): ``state_machine/`` com rules.py, machine.py e enums.py
  (14 estados, 4 rotas — Requisitos v1.0 §6; cobertura ≥ 95%).
"""
