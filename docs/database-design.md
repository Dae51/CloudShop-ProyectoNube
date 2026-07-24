# Diseño de base de datos

Todas las tablas usan `PAY_PER_REQUEST`, cifrado administrado, Point-in-Time Recovery
en entornos desplegables y deletion protection opcional en producción. Los nombres
incluyen `cloudshop-{environment}`.

| Tabla | PK | SK/GSI | Patrones de acceso |
|---|---|---|---|
| Users | `userId` | GSI `EmailIndex(email)` | perfil por sub, email único lógico, lista admin |
| Stores | `storeId` | — | CRUD y activos |
| Products | `productId` | GSI `StoreIdCreatedAtIndex(storeId, createdAt)` | detalle, catálogo y por tienda |
| Carts | `customerId` | — | carrito propio completo |
| Orders | `orderId` | GSI `CustomerCreatedAtIndex(customerId, createdAt)`; GSI `StatusCreatedAtIndex(status, createdAt)` | detalle, propios, cola operador |
| Audit | `auditId` | GSI `ResourceOccurredAtIndex(resourceKey, occurredAt)`; GSI `CorrelationIndex(correlationId, occurredAt)` | traza por recurso/correlación |
| Outbox | `eventId` | GSI `StatusOccurredAtIndex(status, occurredAt)` + Streams | relay y recuperación |
| Idempotency | `idempotencyKey` | TTL `expiresAt` | checkout, cancelación y consumidores |
| ProductAudit | `auditId` | — | compatibilidad de auditoría heredada de productos |

## Operaciones condicionales

- Producto/tienda: `updatedAt = :expected` evita lost updates.
- Crear/actualizar producto hace `GetItem` consistente y exige tienda `ACTIVE`.
- Carrito: `customerId` proviene de identidad firmada; `version` permite optimistic
  locking.
- Checkout: una transacción contiene `ConditionCheck`/`Update` por producto,
  `Put Orders`, `Put Audit`, `Put Outbox` y `Put Idempotency`.
- Stock: `SET inventory = inventory - :quantity` con
  `status = ACTIVE AND inventory >= :quantity`.
- Cancelación: condición de estado y `inventoryRestored <> true`; repone todos los
  items, cambia estado y registra auditoría/outbox en una transacción.
- Outbox relay: `status` pasa `PENDING -> PUBLISHED` con condición. Publicación y marca
  no son atómicas; consumidores toleran duplicados.
- Consumidor: `Put Idempotency` condicional por `consumer#eventId`.

El máximo de 20 items mantiene la transacción por debajo del límite de 100 acciones:
20 updates de stock + pedido + auditoría + outbox + idempotencia.

## Paginación

Listas aceptan `limit` 1..100 y `nextToken` opaco base64url. Nunca se expone
`LastEvaluatedKey` sin codificar. Reportes académicos pueden usar Scan paginado para un
dataset pequeño; el documento técnico registra que producción real requeriría
agregados materializados por eventos.

## Retención y datos sensibles

- Audit: retención definida por política académica; sin TTL por defecto.
- Idempotency: TTL 24 horas para comandos y 30 días para eventos.
- Outbox publicado: TTL 30 días.
- No se almacenan contraseñas, tokens ni credenciales.
- Email vive en Users y no se incluye en eventos/logs.
- Borrado de usuarios es lógico para preservar auditoría y pedidos.
