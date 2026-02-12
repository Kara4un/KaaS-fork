---
type: Ontology
title: Document Types
status: living
updated: 2026-02-12T00:00:00.000Z
domain: Software-Development
tags:
  - kb/ontology
  - type/Guide
  - domain/Software-Development
related_moc: '[[Software Development]]'
---

# Document Types

This page defines canonical document categories for the engineering knowledge base.

## Architecture & Design

- **Architecture Decision Record (ADR)**: captures a significant technical decision, alternatives considered, and consequences.
- **[[System Design]]**: describes architecture, boundaries, integrations, and scalability characteristics.
- **Technical Standard**: mandatory engineering rule or policy (security, coding, compliance).
- **Reference Architecture**: reusable design pattern for common solution classes.

## Delivery & Execution

- **Implementation Plan**: step-by-step plan to deliver a feature or initiative.
- **Release Plan**: deployment strategy, cutover method, rollback path, and communication plan.
- **Project Brief**: concise statement of scope, objectives, stakeholders, and timeline.
- **Postmortem / Incident Review**: analysis of failure, contributing factors, and corrective actions.

## Operations & Reliability

- **Runbook**: operational procedure for standard or emergency tasks.
- **Troubleshooting Guide**: symptom-to-diagnosis-to-fix workflow.
- **Service Catalog Entry**: ownership, SLOs, dependencies, and support model for a service.
- **Operational Checklist**: pre-flight or recurring validation checklist.

## Data & Analytics

- **Data Contract**: producer-consumer schema and quality guarantees.
- **Data Dictionary**: field-level semantics, type definitions, constraints.
- **Metric Definition**: business metric meaning, formula, and data source.
- **Pipeline Spec**: ingestion/transformation rules, dependencies, schedules.

## Product & Process

- **Requirements Spec**: functional and non-functional requirements with acceptance criteria.
- **Process Definition**: repeatable workflow with roles, gates, and artifacts.
- **Policy / Guideline**: expected behavior for teams and systems.
- **Knowledge Note**: focused explanatory note for reusable understanding.

## Classification Rules

- Prefer one primary type per note.
- Add secondary intent in the body instead of over-tagging types.
- If uncertain between operational and design content, split into separate notes and cross-link.

## Related

- [[Ontology-Overview]]
- [[Core-Domains]]
- [[Glossary-Key-Terms]]
