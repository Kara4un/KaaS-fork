---
type: Guide
domain: Software-Development
tags:
  - kb/ontology
  - type/Guide
  - domain/Software-Development
status: living
related_moc: '[[Software Development]]'
updated: '2026-02-12'
---

# KaaS - Knowledge as a Service

Это персональный Obsidian-vault с заметками и картами контента.

## Структура

- `0-Slipbox` — атомарные заметки
- `1-Projects` — проектные заметки
- `2-Areas` — области ответственности и MOC
- `3-Resources` — справочники, шаблоны, материалы

## Локальная публикация через Quartz v4

В репозитории настроена **локальная** сборка сайта через Quartz v4.

### Требования

- Node.js `22+`
- npm `10+`

### Установка

```bash
npm install
```

### Локальный предпросмотр

```bash
npm run quartz:serve
```

Сайт будет доступен по адресу `http://localhost:8080`.

### Одноразовая сборка

```bash
npm run quartz:build
```

Результат сборки появляется в `public/`.

## Что удалено

- MkDocs-конфигурация и зависимости (`mkdocs.yml`, `requirements.txt`)
- GitHub Pages мета (`CNAME`)
- Workflow публикации MkDocs (`.github/workflows/mkdocs.yml`)

## Примечание

Quartz читает контент из папки `content/`, где подключены основные разделы vault.

## Knowledge Graph Links

- [[Software Development]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
