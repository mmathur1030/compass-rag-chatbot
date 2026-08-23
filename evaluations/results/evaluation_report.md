# Compass RAG Evaluation Report

## Summary

| Metric | Result | Target |
|---|---:|---:|
| Router accuracy | 100.0% | 90% |
| Correct-source hit rate | 100.0% | 90% |
| Answer keyword coverage | 89.7% | — |
| Refusal accuracy | 100.0% | 100% |
| Citation validity | 100.0% | 100% |
| Faithfulness | 100.0% | 95% |
| Average latency | 5.97s | — |
| p95 latency | 13.58s | 8.00s |

## Dense versus hybrid retrieval

- Dense correct-source hit rate: **100.0%**
- Hybrid correct-source hit rate: **100.0%**

## Question-level results

| ID | Type | Route | Source | Refusal | Citations | Faithfulness | Latency | Failure |
|---|---|---:|---:|---:|---:|---:|---:|---|
| hr-annual-leave | direct | ✓ | ✓ | ✓ | ✓ | 100% | 1.64s | — |
| hr-cross-border-remote | direct | ✓ | ✓ | ✓ | ✓ | 100% | 1.11s | — |
| hr-parental-leave | direct | ✓ | ✓ | ✓ | ✓ | 100% | 1.25s | — |
| tech-rate-limit | exact-term | ✓ | ✓ | ✓ | ✓ | 100% | 1.48s | — |
| tech-webhook-signature | exact-term | ✓ | ✓ | ✓ | ✓ | 100% | 2.48s | — |
| tech-production-deploy | direct | ✓ | ✓ | ✓ | ✓ | 100% | 2.47s | — |
| compliance-data-request | direct | ✓ | ✓ | ✓ | ✓ | 100% | 9.48s | — |
| compliance-critical-finding | direct | ✓ | ✓ | ✓ | ✓ | 100% | 11.10s | — |
| cross-p1-response | cross-document | ✓ | ✓ | ✓ | ✓ | 100% | 12.98s | — |
| cross-credential-security | cross-document | ✓ | ✓ | ✓ | ✓ | 100% | 8.93s | — |
| ambiguous-retention | ambiguous | ✓ | ✓ | ✓ | ✓ | 100% | 12.68s | — |
| ambiguous-work-home | ambiguous | ✓ | ✓ | ✓ | ✓ | 100% | 13.58s | — |
| unknown-cafeteria | unanswerable | ✓ | ✓ | ✓ | ✓ | — | 4.77s | — |
| unknown-travel | unanswerable | ✓ | ✓ | ✓ | ✓ | — | 3.05s | — |
| compliance-access-revocation | direct | ✓ | ✓ | ✓ | ✓ | 100% | 2.57s | — |

## Failure analysis

No failures under the current rubric.
