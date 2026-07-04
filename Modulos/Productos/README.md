# Módulo 2 - Gestión de Productos

Este módulo registra sus rutas en la API REST regional compartida de CloudShop.
La raíz del proyecto crea API Gateway, el deployment y el stage; Productos
recibe `rest_api_id`, `root_resource_id`, `execution_arn` y `stage_name`. El
módulo conserva su Lambda de Python, las tablas DynamoDB `Products` y
`ProductAudit`, el log group de CloudWatch y políticas IAM de mínimo privilegio.

## Autorización

API Gateway rechaza solicitudes sin firma SigV4. La Lambda vuelve a validar el
rol antes de despachar cada acción. Reconoce `Administrador`, `Operador` y
`Cliente` desde un contexto de authorizer (`role`, `custom:role` o grupos) o
desde el nombre del rol IAM asumido en `requestContext.identity.userArn`.

Como el repositorio todavía no contiene un proveedor de identidad ni roles de
usuarios desplegables, el módulo genera tres políticas administradas y expone
sus ARN en `api_role_policy_arns`. Deben adjuntarse a roles empresariales cuyos
nombres terminen en `Administrador`, `Operador` o `Cliente`; por ejemplo,
`CloudShop-Operador`. El módulo no crea relaciones de confianza amplias ni
credenciales.

## Rutas

| Método | Ruta | Roles |
|---|---|---|
| POST | `/productos` | Administrador |
| GET | `/productos` | Administrador, Operador, Cliente |
| GET | `/productos/{productId}` | Administrador, Operador, Cliente |
| GET | `/tiendas/{storeId}/productos` | Administrador, Operador, Cliente |
| PUT | `/productos/{productId}` | Administrador |
| PATCH | `/productos/{productId}/inventario` | Administrador, Operador |
| DELETE | `/productos/{productId}` | Administrador |

`DELETE` actualiza el estado a `DELETED`. Las consultas normales solo devuelven
productos `ACTIVE`; un Administrador puede usar `?includeDeleted=true` en las
consultas generales o por identificador.

Las mutaciones y sus auditorías exitosas se escriben en una sola transacción de
DynamoDB. Los intentos fallidos que llegan a la Lambda generan un registro con
`resultado=FALLIDO`. Una solicitud bloqueada previamente por API Gateway no
invoca la Lambda y, por tanto, no crea un registro en `ProductAudit`.
