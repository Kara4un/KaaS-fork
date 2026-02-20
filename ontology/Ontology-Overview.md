---
type: Ontology
title: Ontology Overview
status: living
updated: 2026-02-12T00:00:00.000Z
domain: Software-Development
tags:
  - kb/ontology
  - type/Guide
  - domain/Software-Development
related_moc: '[[Software Development]]'
---

# Ontology Overview

This ontology defines the canonical structure for the company knowledge base built on top of this vault.

It has four primary goals:

1. Standardize how knowledge is captured and linked.
2. Improve discoverability through consistent metadata and [[Document-Types]].
3. Reduce ambiguity with a shared [[Glossary-Key-Terms]].
4. Organize knowledge by business and engineering context in [[Core-Domains]].

## Structural Model

Our knowledge model is intentionally simple:

- **Document Type**: what kind of artifact a note is (e.g., runbook, ADR, standard).
- **Domain**: which area of the organization owns or uses the knowledge.
- **Term**: controlled vocabulary that defines concepts and reduces semantic drift.

Together, these three dimensions help answer:

- What is this document?
- Where does it belong?
- Which concepts does it define or depend on?

## Usage Guidance

Every new company-facing note should:

- map to at least one entry from [[Document-Types]];
- belong to at least one domain in [[Core-Domains]];
- reuse terms from [[Glossary-Key-Terms]] where applicable.

## Governance

This ontology is a living asset.

- Updates should be reviewed by engineering leadership and operations stakeholders.
- Breaking naming changes should be explicitly documented and backward-linked.
- New terms should include concise definitions and practical usage context.

## Related

- [[Document-Types]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
