---
Date: <% tp.date.now() %>
Author: Jimmy Briggs <jimmy.briggs@jimbrig.com>
Tags:
  - '#Type/Project'
  - '#Topic/Work/PwC'
Alias: <% tp.file.cursor() %>
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

# <% tp.file.title %>

- 🔗 - < add link to Todoist project here >
- 📁 - < add URI/path to project directory here >

## Contents

```dataview
list from "<% tp.file.folder(true) %>" AND !#Type/Readme AND -"Changelog"
```

***

*Backlinks*

```dataview
list from [[<% tp.file.title %>]] AND -"Changelog"
```

## Knowledge Graph Links

- [[Software Development]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
