---
name: ai-native-workflow
description: Run the master JCode AI-Native SDLC workflow (DoR check, semantic graph, architecture guard, swarm TDD, slop scan, runtime verification, telemetry, audit attestation). Use when user wants to run the full AI-Native workflow.
---

# JCode AI-Native SDLC Workflow Skill

When invoked, this skill executes the complete JCode AI-Native SDLC workflow pipeline:

1. **DoR Quality Gate**: Validates task intent against 7-point rubric.
2. **Semantic Graph & Architecture Guard**: Checks upstream/downstream symbol impact and layer violations.
3. **Autonomous Swarm & Strict TDD**: Executes Red-Green-Refactor state machine and swarm cycle.
4. **Red-Team & Scope Guard**: Runs adversarial debate, slop scan, and DORA small-batch diff check.
5. **Runtime Verification & Audit Ledger**: Collects telemetry and records cryptographic chained hash log.
6. **Self-Evolution & Case Study**: Evolves adaptive rules and generates structured case study markdown.

**Command execution**:
```bash
python tools/scripts/jcode_cross_platform_runner.py workflow-ai-native
```
