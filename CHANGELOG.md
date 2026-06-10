# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

> **Convenção:** registre as mudanças em `[Unreleased]`, agrupadas por categoria (*Added, Changed, Deprecated, Removed, Fixed, Security*), referenciando o componente (ex.: `W0-C01`). Ao concluir uma wave ou liberar uma versão, mova o bloco para uma seção versionada com data.

---

## [Unreleased]

### Added
- Inicialização do projeto: documentos de contexto na raiz (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`).
- Baseline de decisões de arquitetura (ADR-001 a ADR-011) em `DECISIONS.md`.

<!--
Modelo de entrada por componente:

### Added
- **W0-C01:** estrutura do monorepo (Ports & Adapters), app factory FastAPI, health check, adapter R2 (boto3), Alembic configurado, logging estruturado, CI inicial.

### Changed
- ...

### Fixed
- ...
-->

---

## Histórico de versões do produto (contexto)

> Esta seção registra a linha do tempo das **especificações** anteriores ao código. A baseline de implementação é a **v1.0**.

- **Produto v1.0 (Jun/2026)** — linha de base única e definitiva: 14 estados, 4 rotas, seleção manual e imutável da rota, laminação na clicheria com travessias do motorista, RBAC em duas camadas, identificação por câmera + digitação manual, assinatura no fluxo, responsividade mobile, animações leves e pilares de robustez/escalabilidade/mínimo de requisições/observabilidade.
- **DAT v3.0 (Abr/2026)** — documento de arquitetura técnica (stack e padrões). Usado como referência de stack; ressalvas em `CLAUDE.md §2.1`.
