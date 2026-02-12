---
type: Guide
domain: Databases
tags:
  - kb/ontology
  - type/Guide
  - domain/Databases
status: living
related_moc: '[[Databases]]'
updated: '2026-02-12'
---

# Unattended Install of the Latest SQL Server Management Studio Using PowerShell

## Metadata

* Author: *Guillermo Musumeci*
* Full Title: Unattended Install of the Latest SQL Server Management Studio Using PowerShell
* Category: #Type/Highlight/Article
* URL: https://medium.com/p/e8003e583265

## Highlights

* $InstallerSQL = $env:TEMP + “\SSMS-Setup-ENU.exe”; 
  Invoke-WebRequest “https://aka.ms/ssmsfullsetup" -OutFile $InstallerSQL; 
  start $InstallerSQL /Quiet
  Remove-Item $InstallerSQL;

## Knowledge Graph Links

- [[Databases]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
