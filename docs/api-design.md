# Diseño de API

La fuente ejecutable es [contracts/openapi.yaml](../contracts/openapi.yaml), OpenAPI
3.1. Contiene 34 operaciones de negocio y extensiones `x-cloudshop-roles`. Todas usan
SigV4 excepto `OPTIONS`; registro/login ocurren directamente con Cognito.

## Convenciones

- Base: `https://{apiId}.execute-api.{region}.amazonaws.com/{stage}`.
- JSON UTF-8 y nombres de dominio en inglés/camelCase.
- Cada respuesta lleva `X-Correlation-Id`.
- Comandos de pedido requieren `Idempotency-Key` UUID.
- Borrados de usuario/tienda/producto son lógicos.
- Errores: `{ "error": { "code", "message", "correlationId" } }`.
- `400` entrada, `401` sin autenticar, `403` sin permiso/ownership, `404` no visible,
  `409` conflicto/transición/stock, `500` error interno.

## Inventario de rutas

| Dominio | Rutas | Roles |
|---|---|---|
| Usuarios | `GET /usuarios`; `GET/PUT/DELETE /usuarios/{id}`; `PATCH .../rol` | admin o propietario según operación |
| Productos | `GET/POST /productos`; `GET/PUT/DELETE /productos/{id}`; `PATCH .../inventario`; `GET /tiendas/{id}/productos` | matriz por rol |
| Tiendas | `GET/POST /tiendas`; `GET/PUT/DELETE /tiendas/{id}` | lectura todos; escritura admin |
| Carrito | `GET/DELETE /carritos/mio`; `POST /items`; `PATCH/DELETE /items/{productId}` | CLIENTE |
| Pedidos | `GET/POST /pedidos`; `GET /pedidos/mios`; `GET /pedidos/{id}`; `PATCH .../estado`; `POST .../cancelacion` | CLIENTE/OPERADOR |
| Reportes | seis `GET /reportes/...` | ADMINISTRADOR |

## Contratos críticos

`POST /productos` exige `code`, `name`, `description`, `category`, `price`,
`inventory` y `storeId`; la tienda debe existir y estar activa.

`POST /pedidos` no acepta precio ni items en el body. Lee el carrito propio, vuelve a
consultar productos y calcula totales server-side. Una repetición con la misma clave
devuelve el pedido anterior.

`PATCH /pedidos/{id}/estado` solo acepta la siguiente arista:

```text
PENDIENTE → CONFIRMADO → EN_PREPARACION → ENVIADO → ENTREGADO
PENDIENTE/CONFIRMADO → CANCELADO
```

Los reportes consideran ventas/compras consumadas únicamente en pedidos `ENTREGADO`.
Pedidos por estado siempre devuelve los seis estados, incluso con contador cero.

## Alineación y prueba

`tests/test_openapi_contract.py` valida cantidad de operaciones, roles oficiales,
metadata de autorización y schemas básicos. Terraform registra exactamente rutas
`AWS_IAM`; la evidencia contra una URL real permanece BLOCKED.
