# Modelo de Datos DynamoDB

CloudShop Enterprise usa Amazon DynamoDB como persistencia principal. Las tablas estan definidas en Terraform dentro del modulo que administra cada dominio.

## DynamoDB Tables

| Tabla | Modulo | Proposito |
| --- | --- | --- |
| `Users` | Usuarios | Usuarios de la plataforma |
| `UserAudit` | Usuarios | Auditoria de cambios de usuarios |
| `Products` | Productos | Catalogo e inventario |
| `ProductAudit` | Productos | Auditoria de cambios de productos |
| `Stores` | Tiendas | Tiendas registradas |
| `CartItems` | Compras | Items de carrito por usuario |
| `Orders` | Pedidos | Pedidos transaccionales |
| `OrderEventsAudit` | Pedidos | Eventos completos publicados por pedidos |

## Users

Clave primaria:

- Partition key: `userId` (`S`)

GSI:

- `StatusCreatedAtIndex`
  - Partition key: `status`
  - Sort key: `createdAt`

Atributos esperados:

- `userId`
- `name`
- `email`
- `role`: `ADMINISTRADOR`, `OPERADOR` o `CLIENTE`
- `phone`
- `status`: `ACTIVE` o `DISABLED`
- `createdAt`
- `updatedAt`
- `disabledAt`

Patrones de acceso:

- `PutItem` para registrar usuarios.
- `Query` por `status` usando `StatusCreatedAtIndex`.
- `GetItem` por `userId`.
- `PutItem` condicionado para actualizar usuarios.
- `UpdateItem` para desactivar usuarios.

## UserAudit

Clave primaria:

- Partition key: `auditId` (`S`)

Indices: no tiene GSI implementado.

Atributos:

- `auditId`
- `usuario`
- `accion`
- `resourceType`
- `resourceId`
- `fecha`
- `resultado`

Patrones de acceso:

- `PutItem` desde `usuarios-lambda` para acciones `CREATE_USER`, `UPDATE_USER` y `DISABLE_USER`.

## Products

Clave primaria:

- Partition key: `productId` (`S`)

GSI:

- `StoreIdCreatedAtIndex`
  - Partition key: `storeId`
  - Sort key: `createdAt`

Atributos:

- `productId`
- `code`
- `name`
- `description`
- `category`
- `price`
- `inventory`
- `storeId`
- `status`: `ACTIVE` o `DELETED`
- `createdAt`
- `updatedAt`

Patrones de acceso:

- `GetItem` por `productId`.
- `Scan` filtrado por `status = ACTIVE` para listar productos.
- `Query` por `storeId` usando `StoreIdCreatedAtIndex`.
- `PutItem` para crear y actualizar.
- `UpdateItem` para inventario.
- Lectura por reportes para productos sin stock.
- Transaccion de inventario desde el consumidor de pedidos.

## ProductAudit

Clave primaria:

- Partition key: `auditId` (`S`)

Indices: no tiene GSI implementado.

Atributos:

- `auditId`
- `accion`
- `resourceType`
- `resourceId`
- `fecha`
- `resultado`

Patrones de acceso:

- `PutItem` desde `productos-lambda` para registrar cambios relevantes.

## Stores

Clave primaria:

- Partition key: `storeId` (`S`)

GSI:

- `StatusCreatedAtIndex`
  - Partition key: `status`
  - Sort key: `createdAt`

Atributos:

- `storeId`
- `name`
- `ownerId`
- `contactEmail`
- `description`
- `phone`
- `address`
- `status`: `ACTIVE` o `DISABLED`
- `createdAt`
- `updatedAt`
- `disabledAt`

Patrones de acceso:

- `GetItem` por `storeId`.
- `Query` por `status` usando `StatusCreatedAtIndex`.
- `PutItem` para crear y actualizar.
- `UpdateItem` para deshabilitar.

## CartItems

Clave primaria compuesta:

- Partition key: `userId` (`S`)
- Sort key: `productId` (`S`)

GSI:

- `ProductIdUserIdIndex`
  - Partition key: `productId`
  - Sort key: `userId`

Atributos:

- `userId`
- `productId`
- `quantity`
- `unitPrice`
- `productName`
- `storeId`
- `createdAt`
- `updatedAt`

Patrones de acceso:

- `Query` por `userId` para obtener carrito completo.
- `GetItem` por `userId` + `productId`.
- `PutItem` para agregar item.
- `UpdateItem` para cambiar cantidad.
- `DeleteItem` para eliminar item o vaciar carrito.

## Orders

Clave primaria:

- Partition key: `orderId` (`S`)

GSI:

- `UserIdCreatedAtIndex`
  - Partition key: `userId`
  - Sort key: `createdAt`
- `StatusCreatedAtIndex`
  - Partition key: `status`
  - Sort key: `createdAt`

Atributos:

- `orderId`
- `userId`
- `status`
- `items`
- `total`
- `currency`
- `createdAt`
- `updatedAt`
- `inventoryStatus`
- `inventoryProcessedAt`
- `eventPublicationStatus`
- `customerEmail`
- `shippingAddress`

Estados de flujo documentados por la implementacion:

- Estado inicial: `PENDIENTE`.
- Estados aceptados: `PENDIENTE`, `CONFIRMADO`, `EN_PREPARACION`, `PAGADO`, `ENVIADO`, `ENTREGADO`, `CANCELADO`.
- Estados finales: `ENTREGADO`, `CANCELADO`.
- Inventario inicial: `PENDIENTE`.
- Publicacion de evento: `PENDIENTE`, `PUBLICADO` o `FALLIDO`.

Patrones de acceso:

- `PutItem` para crear pedido.
- `GetItem` por `orderId`.
- `Query` por `userId` usando `UserIdCreatedAtIndex`.
- `Query` por `status` usando `StatusCreatedAtIndex` para reportes.
- `UpdateItem` para cambio de estado.
- `UpdateItem` por consumidor de inventario para marcar resultado.

## OrderEventsAudit

Clave primaria:

- Partition key: `eventId` (`S`)

GSI:

- `OrderIdEventTimeIndex`
  - Partition key: `orderId`
  - Sort key: `eventTime`

Atributos:

- `eventId`
- `orderId`
- `eventTime`
- `source`
- `detailType`
- `eventPayload`

Patrones de acceso:

- `PutItem` desde `pedidos-auditoria-consumer-lambda`.
- Consulta por `orderId` para evidenciar el flujo completo de pedidos.

## Relationships

DynamoDB no aplica llaves foraneas. Las relaciones se modelan por atributos:

- `Products.storeId` relaciona productos con tiendas.
- `CartItems.userId` relaciona carritos con usuarios.
- `CartItems.productId` relaciona items con productos.
- `Orders.userId` relaciona pedidos con usuarios.
- `Orders.items[].productId` relaciona pedidos con productos.
- `Orders.items[].storeId` permite reportes por tienda.
- `OrderEventsAudit.orderId` vincula eventos auditados con pedidos.

## Access Patterns

| Caso | Tabla | Acceso |
| --- | --- | --- |
| Registrar usuario | `Users` | `PutItem(userId)` |
| Listar usuarios activos | `Users` | `Query(StatusCreatedAtIndex)` |
| Desactivar usuario | `Users` | `UpdateItem(userId)` |
| Obtener producto | `Products` | `GetItem(productId)` |
| Listar productos activos | `Products` | `Scan` con filtro de estado |
| Productos por tienda | `Products` | `Query(StoreIdCreatedAtIndex)` |
| Listar tiendas activas | `Stores` | `Query(StatusCreatedAtIndex)` |
| Obtener carrito | `CartItems` | `Query(userId)` |
| Obtener item de carrito | `CartItems` | `GetItem(userId, productId)` |
| Crear pedido | `Orders` | `PutItem(orderId)` |
| Pedidos por usuario | `Orders` | `Query(UserIdCreatedAtIndex)` |
| Pedidos por estado | `Orders` | `Query(StatusCreatedAtIndex)` |
| Auditar evento de pedido | `OrderEventsAudit` | `PutItem(eventId)` |
| Reportes ejecutivos | `Orders`, `Products` | `Query` y `Scan` con proyecciones |
