# Contratos de dominio

## Vocabulario canónico

Los únicos roles son:

- `ADMINISTRADOR`
- `OPERADOR`
- `CLIENTE`

Los aliases heredados se aceptan únicamente al interpretar eventos antiguos; no se
persisten ni se muestran como valores válidos. `EJECUTIVO` no existe.

## Autenticación e identidad

- Cognito User Pool es la fuente de identidad.
- `sub` es el `userId` estable.
- Cognito Identity Pool entrega una identidad federada y credenciales temporales.
- `cognito:preferred_role` se deriva de un grupo administrado.
- Una identidad sin grupo inequívoco no recibe credenciales.
- El auto-registro nunca acepta `role`; post-confirmation persiste `CLIENTE`.
- Un cambio privilegiado elimina grupos oficiales anteriores, agrega uno y actualiza
  DynamoDB. El comando es exclusivo de `ADMINISTRADOR` y genera auditoría.

## Permisos

| Capacidad | ADMINISTRADOR | OPERADOR | CLIENTE |
|---|:---:|:---:|:---:|
| Consultar/editar/desactivar usuarios | Sí | No | Solo perfil propio |
| Asignar roles | Sí | No | No |
| Crear/editar/desactivar tiendas | Sí | No | No |
| Consultar tiendas/productos | Sí | Sí | Sí |
| CRUD de productos | Sí | No | No |
| Actualizar inventario | Sí | Sí | No |
| Gestionar estados de pedidos | No | Sí | No |
| Comprar/carrito | No | No | Sí |
| Consultar pedidos | Todos | Todos | Solo propios |
| Cancelar pedido | No | Sí | Solo propio y permitido |
| Dashboard/reportes | Sí | No | No |

IAM limita el método/ruta. La Lambda aplica rol, permiso y propiedad. La decisión de no
dar gestión de pedidos a Administrador sigue literalmente SEC-04/SEC-05; el
Administrador observa agregados, mientras el Operador gestiona el workflow.

## Errores HTTP

| Status | Código | Uso |
|---:|---|---|
| 400 | `INVALID_INPUT`, `INVALID_JSON` | Schema o regla básica inválida |
| 401 | `UNAUTHENTICATED` | Excepción técnica pública o token inválido |
| 403 | `FORBIDDEN` | Identidad válida sin rol/permiso/propiedad |
| 404 | `*_NOT_FOUND` | Recurso inexistente o no visible |
| 409 | `CONFLICT`, `INVALID_TRANSITION`, `INSUFFICIENT_STOCK`, `IDEMPOTENCY_CONFLICT` | Conflicto de dominio |
| 429 | `RATE_LIMITED` | Throttling |
| 500 | `INTERNAL_ERROR` | Falla no esperada sin detalles sensibles |
| 503 | `DEPENDENCY_UNAVAILABLE` | Dependencia temporal |

Formato:

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "No tiene permisos para realizar esta acción",
    "correlationId": "8cb69bd7-..."
  }
}
```

Cada respuesta incluye `X-Correlation-Id`. Se acepta el header entrante si es UUID; de
lo contrario se genera uno.

## Producto

Campos obligatorios:

- `productId`: UUID generado.
- `code`: texto 1..64.
- `name`: texto 1..160.
- `description`: texto 1..2000.
- `category`: texto 1..100.
- `price`: decimal > 0, hasta dos decimales.
- `inventory`: entero 0..1,000,000.
- `storeId`: tienda activa.
- `status`: `ACTIVE` o `DELETED`.
- `createdAt`, `updatedAt`: UTC ISO-8601.

Las escrituras usan condición de versión (`updatedAt`) y auditoría transaccional.

## Tienda

- `storeId`: UUID.
- `name`: texto 1..160.
- `description`: texto 1..1000.
- `status`: `ACTIVE` o `INACTIVE`.
- `createdAt`, `updatedAt`.

No se crean productos para tiendas inactivas. Desactivar no elimina productos; los
productos permanecen trazables y se excluyen de nuevos checkouts.

## Carrito

Un carrito pertenece a una identidad `CLIENTE`. Cada item contiene snapshot mínimo
(`productId`, `quantity`) y se vuelve a validar contra producto/precio/stock al hacer
checkout. Cantidad válida: 1..99. Operaciones repetidas usan condición y no autorizan
acceso a otro propietario.

## Pedido

Estados:

```text
PENDIENTE -> CONFIRMADO -> EN_PREPARACION -> ENVIADO -> ENTREGADO
     |            |
     +----------> CANCELADO
```

Reglas:

- El checkout crea `PENDIENTE`.
- `OPERADOR` puede avanzar una sola arista.
- `CLIENTE` puede cancelar su pedido en `PENDIENTE` o `CONFIRMADO`.
- `OPERADOR` puede cancelar en `PENDIENTE` o `CONFIRMADO`.
- `CANCELADO` y `ENTREGADO` son terminales.
- Una transición repetida con la misma idempotency key devuelve el resultado previo.
- Cancelar repone inventario exactamente una vez dentro de una transacción.

Cada pedido guarda:

- `orderId`, `customerId`, `status`;
- items con `productId`, `storeId`, `name`, `unitPrice`, `quantity`, `subtotal`;
- `total`, `createdAt`, `updatedAt`;
- `correlationId`, `idempotencyKey`;
- `inventoryRestored` para compensación.

## Checkout, consistencia y eventos

1. La Lambda valida máximo 20 items, tiendas/productos activos y totales server-side.
2. `TransactWriteItems` realiza por item un `Update` condicional
   `inventory >= quantity`, crea el pedido, registra auditoría y crea un outbox. La
   idempotency key impide otro pedido lógico.
3. DynamoDB Streams invoca el relay. `PutEvents` publica `OrderCreated` a EventBridge;
   el relay marca el outbox como publicado. Si falla antes de marcar, puede publicar un
   duplicado.
4. Consumidores usan `eventId`/`orderId` en una tabla de idempotencia. EventBridge
   reintenta y envía fallos agotados a SQS DLQ.
5. Auditoría e inventario ya son parte de la transacción; correo no es una barrera ni
   condiciona la existencia del pedido.
6. SES consumer guarda estado y `messageId`. Un fallo posterior a `SendEmail` y previo
   al guardado puede producir un correo duplicado; se documenta semántica al-menos-una-
   vez y el subject incluye el número de pedido.

Eventos:

```json
{
  "version": 1,
  "eventId": "uuid",
  "eventType": "OrderCreated",
  "occurredAt": "2026-07-23T18:00:00Z",
  "correlationId": "uuid",
  "actorId": "cognito-sub",
  "customerUserId": "cognito-sub-propietario",
  "orderId": "uuid",
  "customerId": "cognito-identity-id",
  "total": "125.50"
}
```

`customerUserId` identifica al propietario que recibe la notificación; `actorId`
identifica a quien ejecutó la acción. El consumidor v1 acepta `actorId` como fallback
para eventos anteriores que no incluyan el campo nuevo.

No se publican tokens, email ni dirección en EventBridge/logs.

## Auditoría

Schema común:

- `auditId`
- `actorId`
- `action`
- `resourceType`
- `resourceId`
- `occurredAt`
- `result`: `EXITOSO` o `FALLIDO`
- `correlationId`
- `details`: metadatos no sensibles y acotados

Acciones mínimas: `CREATE_USER`, `CHANGE_USER_ROLE`, `DEACTIVATE_USER`,
`DELETE_PRODUCT`, `CREATE_ORDER`, `CANCEL_ORDER`, `UPDATE_INVENTORY`.
