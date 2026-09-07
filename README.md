# MiniDLNA Manager

Aplicativo desktop (GTK4 + libadwaita) para gerenciar o serviço MiniDLNA no Linux via Polkit, sem exigir que a UI rode como root.

Spec completa: [`docs/spec-minidlna-manager.md`](docs/spec-minidlna-manager.md).

## Status

Projeto em desenvolvimento por sprints (ver seção 6 da spec). Sprint atual: **Sprint 0 — Fundação do projeto**.

## Desenvolvimento

```bash
make install   # instala dependências (modo editável + dev)
make test      # roda a suíte de testes
make lint      # roda o linter (ruff)
```
