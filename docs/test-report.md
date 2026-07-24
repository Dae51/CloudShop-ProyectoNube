# Reporte de pruebas

Fecha de corte: 2026-07-24.

## Resultado

Las validaciones locales pasan. Las pruebas obligatorias contra AWS están PARTIAL o
BLOCKED porque no hubo despliegue.

| Suite | Comando | Resultado |
|---|---|---|
| Backend global | `python -m unittest discover -s tests -v` | PASS, 44/44 antes del residual final |
| Backend residual | common + post-confirmation + eventos | PASS, 16/16 tras el residual |
| Productos heredado | `python -m unittest discover -s Modulos/Productos/tests -v` | PASS, 12/12 |
| Frontend | `npm test` en `Modulos/Frontend/app` | PASS, 8/8 |
| Build frontend | `npm run build` | PASS, 670 módulos |
| Dependencias frontend | `npm install` | PASS, 0 vulnerabilidades |
| Terraform formato | `terraform fmt -check -recursive` | PASS |
| Terraform root | `terraform validate -no-color` | PASS |
| Terraform bootstrap | `terraform -chdir=bootstrap validate -no-color` | PASS |
| Plan bootstrap | `terraform -chdir=bootstrap plan` | PASS estático: 5 add, 0 change, 0 destroy |
| Plan root real | `terraform plan` con backend S3 | BLOCKED: backend no existe |
| Plan root aislado | copia `/tmp`, backend local | PARTIAL histórico: 367/0/0; regenerar tras fixer |

El plan aislado sirve para detectar errores de configuración y acciones destructivas,
pero no demuestra drift, ownership ni despliegue.

## Cobertura de riesgo

- Registro siempre CLIENTE y retry post-confirmation.
- Roles oficiales y fallo cerrado ante token IAM ambiguo/no terminal.
- 403 por rol en usuarios, productos, tiendas, carrito, pedido y reportes.
- Ownership de perfil, carrito y pedido.
- Producto exige tienda activa.
- Stock insuficiente y forma atómica del checkout.
- Idempotencia de checkout, transiciones, cancelación, relay y notificación.
- Replay de cancelación no filtra pedidos entre clientes.
- Checkout rechaza tienda inactiva sin efectos y un conflicto reproduce al ganador.
- Lease concurrente y liberación de claim ante fallo temporal SES.
- Cancelación repone inventario exactamente una vez.
- Máquina de estados rechaza saltos/terminales.
- Outbox tolera publicación repetida.
- SES sin configuración no se marca como enviado.
- Roles aliases fallan cerrados y Productos valida límites/campos extra de OpenAPI.
- Seis métricas del dashboard y exclusividad ADMINISTRADOR.
- OpenAPI usa solo roles oficiales y 34 operaciones.
- Cliente frontend firma SigV4, conserva errores y no usa fallback demo.

## Casos obligatorios

| ID | Estado | Evidencia | Falta |
|---|---|---|---|
| TST-01 403 | PARTIAL | varios unit tests 403, incluido DELETE producto | llamada SigV4 real y métrica API |
| TST-02 pedido completo | PARTIAL | tests de transacción/outbox/SES mockeado | DynamoDB/EventBridge/SES reales y MessageId |
| TST-03 métricas | PARTIAL | dashboard/filtros/alarmas en Terraform válido | series visibles en CloudWatch |
| TST-04 Terraform | BLOCKED | bootstrap/plan estático | backend/apply real, 0 destroy |

## Casos que deben ejecutarse tras deploy

1. Registrar y confirmar CLIENTE; comprobar grupo y role ARN STS.
2. `GET /productos` 200 y `DELETE /productos/{id}` 403 con el mismo usuario.
3. Dos clientes intentan comprar el último stock; solo un checkout confirma.
4. Repetir Idempotency-Key y evento; no duplicar pedido/inventario/claim.
5. Confirmar auditoría y correlation ID desde API hasta correo.
6. Forzar fallo temporal y comprobar retry/DLQ.
7. Transicionar los seis estados y rechazar saltos.
8. Abrir dashboard CloudWatch y observar Count, 4XX, 5XX, Latency y WAF.

## Warnings y omisiones

No hay tests omitidos convertidos en PASS. Los logs JSON impresos durante tests son
evidencia de ramas negativas, no errores de suite. `pytest` no forma parte de las
dependencias; el runner reproducible es `unittest`.
