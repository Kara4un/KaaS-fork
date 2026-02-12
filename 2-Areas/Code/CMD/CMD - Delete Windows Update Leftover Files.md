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

# Delete Windows Update Leftover Files

\*Source: *

````powershell
del /s /q /f "%SYSTEMROOT%\Logs\WindowsUpdate\*"
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
list from [[Delete Windows Update Leftover Files]] AND -"Changelog"
````

## Knowledge Graph Links

- [[Development]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
