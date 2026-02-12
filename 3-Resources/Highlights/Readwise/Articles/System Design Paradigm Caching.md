---
type: Guide
domain: System-Design
tags:
  - kb/ontology
  - type/Guide
  - domain/System-Design
status: living
related_moc: '[[Development]]'
updated: '2026-02-12'
---

# [[System Design]] Paradigm: [[Caching]]

## Metadata

* Author: *Abracadabra*
* Full Title: [[System Design]] Paradigm: [[Caching]]
* Category: #Type/Highlight/Article
* URL: https://medium.com/p/e57a25ab2f0a

## Highlights

* The solution is a lease. The first cache miss will grant the app server a lease token. Only the app server having the token for a key can query DB and fill the cache. After a token is issued, all subsequent requests to the cache will be asked to retry after a period. The lease expires after a while to avoid deadlock

## Knowledge Graph Links

- [[Development]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
