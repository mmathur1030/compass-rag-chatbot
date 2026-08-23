# Compass RAG Evaluation Report

## Summary

| Metric | Result | Target |
|---|---:|---:|
| Router accuracy | 100.0% | 90% |
| Correct-source hit rate | 100.0% | 90% |
| Answer keyword coverage | 87.2% | — |
| Refusal accuracy | 100.0% | 100% |
| Citation validity | 100.0% | 100% |
| Faithfulness | 100.0% | 95% |
| Average latency | 5.04s | — |
| p95 latency | 12.78s | 8.00s |

## Dense versus hybrid retrieval

- Dense correct-source hit rate: **100.0%**
- Hybrid correct-source hit rate: **100.0%**

## Question-level results

| ID | Type | Route | Source | Refusal | Citations | Faithfulness | Latency | Failure |
|---|---|---:|---:|---:|---:|---:|---:|---|
| hr-annual-leave | direct | ✓ | ✓ | ✓ | ✓ | 100% | 1.62s | — |
| hr-cross-border-remote | direct | ✓ | ✓ | ✓ | ✓ | 100% | 1.44s | — |
| hr-parental-leave | direct | ✓ | ✓ | ✓ | ✓ | 100% | 1.13s | — |
| tech-rate-limit | exact-term | ✓ | ✓ | ✓ | ✓ | 100% | 1.42s | — |
| tech-webhook-signature | exact-term | ✓ | ✓ | ✓ | ✓ | 100% | 1.42s | — |
| tech-production-deploy | direct | ✓ | ✓ | ✓ | ✓ | 100% | 1.11s | — |
| compliance-data-request | direct | ✓ | ✓ | ✓ | ✓ | 100% | 6.36s | — |
| compliance-access-revocation | direct | ✓ | ✓ | ✓ | ✓ | 100% | 7.58s | — |
| compliance-critical-finding | direct | ✓ | ✓ | ✓ | ✓ | 100% | 11.53s | — |
| cross-p1-response | cross-document | ✓ | ✓ | ✓ | ✓ | 100% | 6.90s | — |
| ambiguous-retention | ambiguous | ✓ | ✓ | ✓ | ✓ | 100% | 12.78s | — |
| ambiguous-work-home | ambiguous | ✓ | ✓ | ✓ | ✓ | 100% | 12.77s | — |
| unknown-cafeteria | unanswerable | ✓ | ✓ | ✓ | ✓ | — | 1.90s | — |
| unknown-travel | unanswerable | ✓ | ✓ | ✓ | ✓ | — | 3.86s | — |
| cross-credential-security | cross-document | ✓ | ✓ | ✓ | ✓ | 100% | 3.71s | — |

## Failure analysis

No failures under the current rubric.
