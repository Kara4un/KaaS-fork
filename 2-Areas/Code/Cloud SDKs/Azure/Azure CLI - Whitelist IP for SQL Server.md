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

# Azure CLI - Whitelist IP for SQL Server

\*Source: *

````bash
az sql server firewall-rule [update/add/create]
````

## Example

````powershell
$myip = (Get-NetIPAddress -AddressFamily IPV4 -InterfaceAlias Wi-Fi).IPAddress
$myip2 = (Invoke-WebRequest -uri "https://api.ipify.org/").Content

$name = "Jimmy"

az sql server firewall-rule update --end-ip-address $myip --start-ip-address $myip -g AS-RESERVE -s reserving-modernization -n $name
az sql server firewall-rule update --end-ip-address $myip2 --start-ip-address $myip -g AS-RESERVE -s reserving-modernization -n "Jimmy2"

az sql server firewall-rule update --end-ip-address $myip --start-ip-address $myip -g AS-RESERVE -s reserving-modernization -n $name
az sql server firewall-rule add --end-ip-address $myip --start-ip-address $myip -g AS-RESERVE -s reserving-modernization -n $name
az sql server firewall-rule --help
az sql server firewall-rule create --end-ip-address $myip --start-ip-address $myip -g AS-RESERVE -s reserving-modernization -n $name
````

---

## Appendix: Links

* [Code](../../Code.md)
* [Development](../../../MOCs/Development.md)

*Backlinks:*

````dataview
list from [[Azure CLI - Whitelist IP for SQL Server]] AND -"Changelog"
````

## Knowledge Graph Links

- [[Databases]]
- [[Ontology-Overview]]
- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
