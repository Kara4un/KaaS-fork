---
type: Pattern
domain: DevOps
tags:
  - kb/ontology
  - type/Pattern
  - domain/DevOps
status: living
related_moc: '[[Development]]'
updated: '2026-02-12'
---

# Retrieve Local Public IPv4 IP Address

\*Source: *

Retrieve Local Public IPv4 IP Address via <https://ipify.org>'s API:

````powershell
(Invoke-WebRequest -uri "https://api.ipify.org/").Content
````

---

## Appendix: Links

* *Code*
* [Development](../../MOCs/Development.md)
* [2-Areas/MOCs/PowerShell](../../MOCs/PowerShell.md)

*Backlinks:*

````dataview
list from [[Retrieve Local Public IPv4 IP Address]] AND -"Changelog"
````

## Knowledge Graph Links

- [[Development]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
