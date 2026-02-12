---
type: Guide
domain: Data-Engineering
tags:
  - kb/ontology
  - type/Guide
  - domain/Data-Engineering
status: living
related_moc: '[[Data Engineering]]'
updated: '2026-02-12'
---

# 4 Design Principles for Robust Data Pipelines

## Metadata

* Author: *Mike Aidane*
* Full Title: 4 Design Principles for Robust Data Pipelines
* Category: #Type/Highlight/Article
* URL: https://medium.com/p/5bbd40de4a43

## Highlights

* This architecture is key to effective backfills, that is adding or modifying existing records due to a change in desired output/format or an error that had occurred.
* Incremental Thinking
* The first logical step is to design your stack in an incremental fashion. That way, when a certain step fails, you will go back to the previous one, avoiding recomputing the entire process. When handling large data loads, you will quickly realize that building an incremental stack cannot be an afterthought.
* Data Porosity
* A way to solve this in Data Engineering is to guarantee data porosity between environments. That way, data will be able to flow from production to staging and further to dev but never the reverse. In essence, staging and dev should both have read access to data from production but not be allowed to write.

## Knowledge Graph Links

- [[Data Engineering]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
