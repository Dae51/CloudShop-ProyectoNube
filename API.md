# Documentacion de API REST

Todas las rutas usan API Gateway REST API con autorizacion `AWS_IAM`. Las solicitudes deben firmarse con AWS Signature Version 4. Las respuestas usan JSON salvo operaciones `204 No Content`.

Formato de error comun:

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "descripcion del error"
  }
}
```

Codigos comunes:

- `200 OK`: operacion exitosa.
- `201 Created`: recurso creado.
- `204 No Content`: eliminacion fisica o limpieza sin cuerpo.
- `400 Bad Request`: validacion fallida.
- `403 Forbidden`: falta autorizacion IAM.
- `404 Not Found`: ruta o recurso no encontrado.
- `409 Conflict`: conflicto de estado.
- `500 Internal Server Error`: error interno o error AWS no controlado.

## Usuarios

### `POST /usuarios`

Registra un usuario activo.

Autenticacion: `AWS_IAM`.

Request:

```json
{
  "name": "Cliente Demo",
  "email": "cliente@example.com",
  "role": "CLIENTE",
  "phone": "+50322223333"
}
```

Response `201`:

```json
{
  "data": {
    "userId": "uuid",
    "name": "Cliente Demo",
    "email": "cliente@example.com",
    "role": "CLIENTE",
    "status": "ACTIVE",
    "createdAt": "2026-07-11T00:00:00Z",
    "updatedAt": "2026-07-11T00:00:00Z"
  }
}
```

### `GET /usuarios`

Lista usuarios por estado usando `StatusCreatedAtIndex`.

Autenticacion: `AWS_IAM`.

Query string:

- `status`: `ACTIVE` o `DISABLED`. Si no se envia, usa `ACTIVE`.

Request body: no aplica.

Response `200`:

```json
{
  "data": [
    {
      "userId": "user-001",
      "name": "Cliente Demo"
    }
  ]
}
```

### `GET /usuarios/{userId}`

Obtiene un usuario por `userId`.

Autenticacion: `AWS_IAM`.

Response `200`:

```json
{
  "data": {
    "userId": "uuid",
    "name": "Cliente Demo",
    "email": "cliente@example.com",
    "role": "CLIENTE",
    "status": "ACTIVE"
  }
}
```

### `PUT /usuarios/{userId}`

Actualiza campos de un usuario activo.

Autenticacion: `AWS_IAM`.

Request:

```json
{
  "name": "Cliente Actualizado",
  "email": "cliente.actualizado@example.com",
  "role": "CLIENTE",
  "phone": "+50322224444"
}
```

Response `200`:

```json
{
  "data": {
    "userId": "uuid",
    "name": "Cliente Actualizado",
    "status": "ACTIVE"
  }
}
```

### `DELETE /usuarios/{userId}`

Desactiva logicamente un usuario estableciendo `status = DISABLED`.

Autenticacion: `AWS_IAM`.

Response `200`:

```json
{
  "data": {
    "userId": "uuid",
    "status": "DISABLED",
    "disabledAt": "2026-07-11T00:00:00Z"
  }
}
```

## Productos

### `POST /productos`

Crea un producto activo y registra auditoria en `ProductAudit`.

Autenticacion: `AWS_IAM`. Requiere permisos de administrador u operador segun politica adjunta.

Request:

```json
{
  "code": "SKU-001",
  "name": "Laptop Pro",
  "description": "Equipo portatil",
  "category": "Tecnologia",
  "price": 1200,
  "inventory": 10,
  "storeId": "store-001"
}
```

Response `201`:

```json
{
  "data": {
    "productId": "uuid",
    "code": "SKU-001",
    "name": "Laptop Pro",
    "description": "Equipo portatil",
    "category": "Tecnologia",
    "price": 1200,
    "inventory": 10,
    "storeId": "store-001",
    "status": "ACTIVE",
    "createdAt": "2026-07-11T00:00:00Z",
    "updatedAt": "2026-07-11T00:00:00Z"
  }
}
```

Estados: `201`, `400`, `403`, `409`, `500`.

### `GET /productos`

Lista productos con `status = ACTIVE`.

Autenticacion: `AWS_IAM`.

Response `200`:

```json
{
  "data": [],
  "count": 0
}
```

### `GET /productos/{productId}`

Obtiene un producto activo por `productId`.

Autenticacion: `AWS_IAM`.

Response `200`:

```json
{
  "data": {
    "productId": "uuid",
    "name": "Laptop Pro",
    "status": "ACTIVE"
  }
}
```

Estados: `200`, `400`, `403`, `404`, `500`.

### `PUT /productos/{productId}`

Actualiza completamente los campos principales del producto.

Autenticacion: `AWS_IAM`.

Request: mismo cuerpo requerido por `POST /productos`.

Response `200`:

```json
{
  "data": {
    "productId": "uuid",
    "name": "Laptop Pro Actualizada",
    "status": "ACTIVE"
  }
}
```

Estados: `200`, `400`, `403`, `404`, `409`, `500`.

### `PATCH /productos/{productId}/inventario`

Actualiza el inventario de un producto activo.

Autenticacion: `AWS_IAM`.

Request:

```json
{
  "inventory": 25
}
```

Response `200`:

```json
{
  "data": {
    "productId": "uuid",
    "inventory": 25,
    "status": "ACTIVE"
  }
}
```

Estados: `200`, `400`, `403`, `404`, `409`, `500`.

### `DELETE /productos/{productId}`

Realiza eliminacion logica marcando `status = DELETED`.

Autenticacion: `AWS_IAM`.

Response `200`:

```json
{
  "data": {
    "productId": "uuid",
    "status": "DELETED"
  }
}
```

### `GET /tiendas/{storeId}/productos`

Lista productos activos por tienda usando el indice `StoreIdCreatedAtIndex`.

Autenticacion: `AWS_IAM`.

Response `200`:

```json
{
  "data": [],
  "count": 0
}
```

## Tiendas

### `POST /tiendas`

Crea una tienda activa.

Autenticacion: `AWS_IAM`.

Request:

```json
{
  "name": "Tienda Central",
  "ownerId": "user-admin-001",
  "contactEmail": "owner@example.com",
  "description": "Sucursal principal",
  "phone": "+50322223333",
  "address": {
    "line1": "Calle Principal",
    "city": "San Salvador",
    "country": "SV"
  }
}
```

Response `201`:

```json
{
  "data": {
    "storeId": "uuid",
    "name": "Tienda Central",
    "ownerId": "user-admin-001",
    "contactEmail": "owner@example.com",
    "status": "ACTIVE",
    "createdAt": "2026-07-11T00:00:00Z",
    "updatedAt": "2026-07-11T00:00:00Z"
  }
}
```

Estados: `201`, `400`, `403`, `409`, `500`.

### `GET /tiendas`

Lista tiendas por estado usando `StatusCreatedAtIndex`.

Autenticacion: `AWS_IAM`.

Query string:

- `status`: `ACTIVE` o `DISABLED`. Si no se envia, usa `ACTIVE`.

Response `200`:

```json
{
  "data": [],
  "count": 0
}
```

### `GET /tiendas/{storeId}`

Obtiene una tienda por `storeId`.

Autenticacion: `AWS_IAM`.

Response `200`:

```json
{
  "data": {
    "storeId": "uuid",
    "name": "Tienda Central",
    "status": "ACTIVE"
  }
}
```

### `PUT /tiendas/{storeId}`

Actualiza campos permitidos de una tienda activa. `ownerId` no puede modificarse.

Autenticacion: `AWS_IAM`.

Request:

```json
{
  "name": "Tienda Central Renovada",
  "contactEmail": "owner@example.com",
  "phone": "+50322224444"
}
```

Response `200`:

```json
{
  "data": {
    "storeId": "uuid",
    "name": "Tienda Central Renovada",
    "status": "ACTIVE"
  }
}
```

Estados: `200`, `400`, `403`, `404`, `409`, `500`.

### `DELETE /tiendas/{storeId}`

Deshabilita logicamente una tienda estableciendo `status = DISABLED`.

Autenticacion: `AWS_IAM`.

Response `200`:

```json
{
  "data": {
    "storeId": "uuid",
    "status": "DISABLED",
    "disabledAt": "2026-07-11T00:00:00Z"
  }
}
```

## Carritos

### `POST /carritos/{userId}/items`

Agrega o reemplaza un item del carrito de un usuario.

Autenticacion: `AWS_IAM`.

Request:

```json
{
  "productId": "product-001",
  "quantity": 2,
  "unitPrice": 15.5,
  "productName": "Producto Demo",
  "storeId": "store-001"
}
```

Response `201`:

```json
{
  "data": {
    "userId": "user-001",
    "productId": "product-001",
    "quantity": 2,
    "unitPrice": 15.5,
    "productName": "Producto Demo"
  }
}
```

### `GET /carritos/{userId}`

Obtiene todos los items del carrito y el total calculado.

Autenticacion: `AWS_IAM`.

Response `200`:

```json
{
  "data": {
    "userId": "user-001",
    "items": [],
    "total": 0,
    "count": 0
  }
}
```

### `GET /carritos/{userId}/items/{productId}`

Obtiene un item especifico del carrito.

Autenticacion: `AWS_IAM`.

Response `200`:

```json
{
  "data": {
    "userId": "user-001",
    "productId": "product-001",
    "quantity": 2
  }
}
```

### `PATCH /carritos/{userId}/items/{productId}`

Actualiza la cantidad de un item.

Autenticacion: `AWS_IAM`.

Request:

```json
{
  "quantity": 3
}
```

Response `200`:

```json
{
  "data": {
    "userId": "user-001",
    "productId": "product-001",
    "quantity": 3
  }
}
```

### `DELETE /carritos/{userId}/items/{productId}`

Elimina un item del carrito.

Autenticacion: `AWS_IAM`.

Response: `204 No Content`.

### `DELETE /carritos/{userId}`

Vacia el carrito del usuario.

Autenticacion: `AWS_IAM`.

Response: `204 No Content`.

## Pedidos

### `POST /pedidos`

Crea un pedido, lo persiste en `Orders` y publica el evento `PedidoCreado`.

Autenticacion: `AWS_IAM`.

Request:

```json
{
  "userId": "user-001",
  "currency": "USD",
  "customerEmail": "cliente@example.com",
  "shippingAddress": {
    "line1": "Calle Principal",
    "city": "San Salvador"
  },
  "items": [
    {
      "productId": "product-001",
      "productName": "Producto Demo",
      "storeId": "store-001",
      "quantity": 2,
      "unitPrice": 15.5
    }
  ]
}
```

Response `201`:

```json
{
  "data": {
    "orderId": "uuid",
    "userId": "user-001",
    "status": "PENDIENTE",
    "total": 31,
    "currency": "USD",
    "inventoryStatus": "PENDIENTE",
    "eventPublicationStatus": "PUBLICADO"
  }
}
```

Estados: `201`, `400`, `403`, `500`.

### `GET /pedidos/{orderId}`

Obtiene un pedido por `orderId`.

Autenticacion: `AWS_IAM`.

Response `200`:

```json
{
  "data": {
    "orderId": "uuid",
    "status": "PENDIENTE"
  }
}
```

### `PATCH /pedidos/{orderId}`

Actualiza el estado del pedido si aun no esta en estado final.

Autenticacion: `AWS_IAM`.

Estados aceptados por la implementacion:

- `PENDIENTE`
- `CONFIRMADO`
- `EN_PREPARACION`
- `PAGADO`
- `ENVIADO`
- `ENTREGADO`
- `CANCELADO`

Request:

```json
{
  "status": "CONFIRMADO"
}
```

Response `200`:

```json
{
  "data": {
    "orderId": "uuid",
    "status": "CONFIRMADO"
  }
}
```

Estados: `200`, `400`, `403`, `404`, `409`, `500`.

### `GET /usuarios/{userId}/pedidos`

Lista pedidos de un usuario usando `UserIdCreatedAtIndex`.

Autenticacion: `AWS_IAM`.

Response `200`:

```json
{
  "data": [],
  "count": 0
}
```

## Reportes

Todas las rutas de reportes son de solo lectura y usan datos existentes en `Orders` y `Products`.

Parametros comunes cuando aplican:

- `from`: fecha ISO inicial.
- `to`: fecha ISO final.
- `status`: estado o lista separada por comas.
- `limit`: cantidad maxima de resultados.

### `GET /reportes/ventas/totales`

Response `200`:

```json
{
  "data": {
    "totalSales": 0,
    "orderCount": 0
  }
}
```

### `GET /reportes/ventas/tiendas`

Response `200`:

```json
{
  "data": [
    {
      "storeId": "store-001",
      "totalSales": 31,
      "quantitySold": 2
    }
  ],
  "count": 1
}
```

### `GET /reportes/productos/mas-vendidos`

Response `200`:

```json
{
  "data": [
    {
      "productId": "product-001",
      "productName": "Producto Demo",
      "quantitySold": 2,
      "totalSales": 31
    }
  ],
  "count": 1
}
```

### `GET /reportes/productos/sin-stock`

Response `200`:

```json
{
  "data": [
    {
      "productId": "product-001",
      "name": "Producto Demo",
      "inventory": 0,
      "status": "ACTIVE"
    }
  ],
  "count": 1
}
```

### `GET /reportes/clientes/mayores-compras`

Response `200`:

```json
{
  "data": [
    {
      "userId": "user-001",
      "totalPurchases": 31,
      "orderCount": 1
    }
  ],
  "count": 1
}
```

### `GET /reportes/pedidos/estados`

Response `200`:

```json
{
  "data": [
    {
      "status": "PENDIENTE",
      "orderCount": 1
    }
  ],
  "totalOrders": 1
}
```
