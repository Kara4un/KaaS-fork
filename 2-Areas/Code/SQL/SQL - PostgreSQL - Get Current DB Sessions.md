---
type: Pattern
domain: Databases
tags:
  - kb/ontology
  - type/Pattern
  - domain/Databases
status: living
related_moc: '[[Databases]]'
updated: '2026-02-12'
---

# SQL - PostgreSQL - Get Current DB Sessions

*Source: https://www.postgresql.org/docs/current/monitoring-stats.html*

````SQL
-- Ref: https://www.postgresql.org/docs/current/monitoring-stats.html
-- Get current DB Sessions
SELECT count(*) as stat_count, state 
FROM pg_stat_activity 
WHERE "query"::text not ilike '%pg_stat_activity%' 
GROUP BY "state"
````

---

## Appendix: Links

* *Code*
* [SQL](SQL.md)
* [Databases](../../MOCs/Databases.md)
* [PostgreSQL](../../../3-Resources/Tools/Developer%20Tools/Data%20Stack/Databases/PostgreSQL.md)
* [Development](../../MOCs/Development.md)

*Backlinks:*

````dataview
list from [[SQL - PostgreSQL - Get Current DB Sessions]] AND -"Changelog"
````

## Knowledge Graph Links

- [[Databases]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
