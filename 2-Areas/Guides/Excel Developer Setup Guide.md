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

# Excel Developer Setup Guide

## Overview

To setup a proper development environment for [Excel](../Code/Excel/Excel.md) the following steps should be taken:

1. Download and Install [Microsoft Office](../../3-Resources/Tools/Microsoft%20Office/Microsoft%20Office.md) 

### Flowchart

````mermaid
flowchart LR
	subgraph install[Installation]
		
		download[Download Office]
		insiders[Join Inisider Program]
		update[Update Office]
		
		download --> insiders --> update
	end
	
	subgraph config[Configure]
	
		enableDev[Enable Developer Tab]
		customizeRibbon[Customize Ribbon]
		personalWB[Create PERSONAL.xlsb]
		addRefs[Add External References]
		addMacros[Add Custom Macros and Modules]
		assignHotKeys[Assign Keyboard Shortcuts]
		document[Document Personal Macros]
		
		enableDev --> customizeRibbon --> personalWB --> addRefs --> addMacros --> assignHotKeys --> document
		
	end
	
	subgraph extras[Install AddIns and Tools]
	
		installAddIns[Install Excel Addins]
		installTools[Install External Tools]
	
		installAddIns --> installTools
		
	end
	
	subgraph backup[Backup with Version Control]
		
		exportVBA[Export VBA Code]
		git[Backup with Git]
		
		exportVBA --> git
		
	end
	
	install --> config --> extras --> backup
	
	
	
````

---

## Appendix: Links and References

* [2022-09-04](../Daily-Notes/2022/2022-09/2022-09-04.md)
* *Excel*
* *VBA*

---

Jimmy Briggs <jimmy.briggs@jimbrig.com> | 2022

## Knowledge Graph Links

- [[Software Development]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
