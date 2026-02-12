---
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

# RMarkdown Template for Developing a Package with Best Practices

For every function, create a [RMarkdown Tabset](../../../0-Slipbox/INBOX/RMarkdown%20Tabset.md) with:

1. Source code of the function:

````R
R> styler::style(<package>::<function>)
````

2. Tests for the function:

````R
R> styler::style(readLines("tests/testthat/<function>_tests.R"))
````

3. Function’s Documentation:

````R
R> HTML(readLines("man/<function>.rd"))
````

4. [Changelog](../../../Changelog.md) for the Function:

*need a way to parse [Git](../../../3-Resources/Tools/Developer%20Tools/Version%20Control/Git.md) Commit history for a specific file using [R](../../Code/R/R.md).*

````R
# need a way to parse Git Commit history for a specific file using R.
````

---

## Appendix: Links

* 

*Backlinks:*

````dataview
list from [[RMarkdown Template for Developing a Package with Best Practices]] AND -"Changelog"
````

---

* Date: [2022-09-18](../../Daily-Notes/2022-09-18.md)

## Knowledge Graph Links

- [[Software Development]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
