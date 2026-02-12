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

# Windows CMD - Extended Disk Cleanup

\*Source: *

An alternative version of `cleanmgr` with deeper cleaning capabilities, administrative privileges, and runs in the background:

````cmd
cmd.exe /c Cleanmgr /sageset:65535 & Cleanmgr /sagerun:65535
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
list from [[Windows CMD - Extended Disk Cleanup]] AND -"Changelog"
````

## Knowledge Graph Links

- [[Development]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
