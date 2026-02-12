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

# Retrieve Windows Credential Manager Saved Secrets

\*Source: *

Utilize the `cmdkey.exe` executable to retrieve secrets from `wincred`:

````powershell
cmdkey.exe /list
````

---

## Appendix: Links

* *Code*
* [Development](../../MOCs/Development.md)
* *Windows*
* *Windows CMD*
* *Command Line*
* [PowerShell](../PowerShell/PowerShell.md)

*Backlinks:*

````dataview
list from [[Retrieve Windows Credential Manager Saved Secrets]] AND -"Changelog"
````

## Knowledge Graph Links

- [[Development]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
