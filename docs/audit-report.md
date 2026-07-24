# Auditoría independiente y cierre del fixer

Fecha: 2026-07-24. Dictamen vigente: **NOT READY FOR SUBMISSION**.

El auditor read-only refutó el estado del commit `5e0903b` y reportó un bloqueo
CRITICAL, siete HIGH, ocho MEDIUM y un LOW. El builder confirmó los hallazgos
reproducibles; no clasificó ninguno como falso positivo.

## Hallazgos corregidos localmente

| ID | Severidad | Cierre implementado | Evidencia local |
|---|---|---|---|
| AUDIT-001 | HIGH | ownership antes del replay de cancelación | test con dos clientes: 403 |
| AUDIT-002 | HIGH | tienda ACTIVE y `ConditionCheck` transaccional | checkout inactivo sin efectos |
| AUDIT-003 | HIGH | DLQ exclusiva en Streams y log JSON del relay | Terraform validate |
| AUDIT-004 | HIGH | catches 500 en API, triggers y SES; Responses 401/403 | tests/validate/source |
| AUDIT-005 | HIGH | IAM separado por tabla, acción e índice, incluido Auth | Terraform validate/source |
| AUDIT-006 | HIGH | bootstrap valida Cognito/Groups/Users, compensa y audita | script compila/runbook |
| AUDIT-007 | HIGH | condición idempotente sin token de payload variable | conflicto reproduce ganador |
| AUDIT-009 | MEDIUM | 403 pre-Lambda con CORS y correlation ID | Terraform validate |
| AUDIT-010 | MEDIUM | roles exactos y multigrupo falla cerrado | tests de aliases/grupos |
| AUDIT-011 | MEDIUM | tipos, límites, precisión y campos alineados con OpenAPI | tests frontera |
| AUDIT-012 | MEDIUM | refresh Cognito antes de renovar STS | build/test frontend |
| AUDIT-014 | MEDIUM | propietario explícito y fallback v1; SES ausente durable | tests consumer |
| AUDIT-016 | MEDIUM | policies Productos incluyen `name_prefix` | Terraform validate |
| AUDIT-017 | LOW | eliminado zip obsoleto de Usuarios | Git diff |

Estos cierres siguen **PARTIAL** frente a la rúbrica hasta probarlos en AWS. La DLQ
evita pérdida, pero su redrive real debe demostrarse post-deploy.

## Hallazgos abiertos o bloqueados

| ID | Estado | Criterio pendiente |
|---|---|---|
| AUDIT-008/018 | BLOCKED CRITICAL | backend remoto, apply, URL y E2E |
| AUDIT-013 | PARTIAL MEDIUM | algunas operaciones no tienen vista dedicada completa |
| AUDIT-015 | PARTIAL MEDIUM | TST-01..03 solo locales; TST-04 bloqueado |
| AUDIT-019 | BLOCKED HIGH | SES tiene cero identidades verificadas |

También faltan confirmar cuenta/región docente y presupuesto WAF. Ningún bloqueo fue
convertido en PASS.

## Reauditoría

El mismo auditor reexaminó el fixer en modo read-only. No encontró CRITICAL/HIGH
nuevo; cerró 001, 002, 003, 007, 009, 012, 014, 016 y 017, y dejó 004, 005, 006,
010 y 011 PARTIAL por residuos concretos. El builder aplicó después una corrección
acotada para esos residuos: logs 500 en triggers/SES, policy Auth separada, bootstrap
consistente, rechazo multigrupo y tipos OpenAPI exactos. Las pruebas dirigidas y
`terraform validate` pasan. No se abre una tercera auditoría para respetar el máximo
de rondas; el dictamen permanece NOT READY por los bloqueos AWS.
