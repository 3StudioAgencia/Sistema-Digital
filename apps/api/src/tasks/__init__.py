"""Drivers inbound de tarefas agendadas/CLI (fora do ciclo HTTP).

Cada módulo aqui é um *entry point* executável por ``python -m src.tasks.<nome>``,
acionado por um scheduler EXTERNO (ex.: GitHub Actions — ADR-015). A lógica de
domínio/infra que essas tarefas usam vive nas camadas de sempre; o módulo de
tarefa é só o gatilho fino (config + logging + exit code).
"""
