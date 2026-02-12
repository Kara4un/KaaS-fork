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

# DISM Commands

\*Source: *

* `DISM` Scan Health:

````powershell
Dism /Online /Cleanup-Image /ScanHealth
````

* `DISM` component cleanup:

````powershell
Dism.exe /online /Cleanup-Image /StartComponentCleanup
````

* DISM online repair image

````powershell
Dism /Online /Cleanup-Image /RestoreHealth
````

* DISM online repair image with [PowerShell](../PowerShell/PowerShell.md) cmdlet:

````powershell
Repair-WindowsImage -Online -RestoreHealth
````

* DISM online repair image

````powershell
Repair-WindowsImage -Online -RestoreHealth
````

* DISM online repair image

````powershell

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
list from [[DISM Commands]] AND -"Changelog"
````

## Knowledge Graph Links

- [[Development]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
