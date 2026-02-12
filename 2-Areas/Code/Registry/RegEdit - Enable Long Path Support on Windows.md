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

# Enable Long Path Support on Windows

\*Source: *

````powershell
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name 'LongPathsEnabled' -Value 1
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
list from [[Enable Long Path Support on Windows]] AND -"Changelog"
````

## Knowledge Graph Links

- [[Development]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
