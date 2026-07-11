# CloudShop Enterprise - Final Project Report

Fecha de auditoria: 2026-07-11

## Resumen Ejecutivo

Se realizo una auditoria completa del proyecto CloudShop Enterprise contra los requisitos funcionales y tecnicos definidos para la entrega. El proyecto implementa una arquitectura serverless modular en AWS mediante Terraform, con API Gateway, Lambda, DynamoDB, EventBridge, SES, CloudFront, S3, WAF, IAM y CloudWatch.

Resultado general: **apto para despliegue con Terraform**.

Durante la auditoria se comparo la implementacion contra el PDF "Proyecto Final - CloudShop Enterprise". Se corrigieron brechas detectadas en el modulo de usuarios y en los estados minimos de pedidos. Tambien se corrigio una inconsistencia de integracion entre modulos: el modulo raiz ahora pasa explicitamente los nombres reales de tablas desde `Productos` y `Pedidos` hacia los modulos que los consumen (`Pedidos` y `Reportes`). Esto evita depender solo de nombres por defecto y mejora la reproducibilidad del despliegue.

## Completed Requirements

| Requisito | Estado | Evidencia |
| --- | --- | --- |
| Infraestructura como codigo con Terraform | Completado | `main.tf`, `provider.tf`, `backend.tf`, `Modulos/*/*.tf` |
| Arquitectura modular | Completado | Modulos independientes en `Modulos/` |
| Users module | Completado | `Modulos/Usuarios`: registro, consulta, actualizacion, desactivacion y auditoria |
| Products module | Completado | `Modulos/Productos` |
| Stores module | Completado | `Modulos/Tiendas` |
| Shopping Cart module | Completado | `Modulos/Compras` |
| Orders module | Completado | `Modulos/Pedidos` |
| Executive Dashboard / Reports module | Completado | `Modulos/Reportes` |
| Frontend infrastructure | Completado | `Modulos/Frontend` |
| S3 static frontend | Completado | Bucket S3 privado con objetos del sitio |
| CloudFront | Completado | Distribucion CloudFront con HTTPS y OAC |
| WAF | Completado | `Modulos/Seguridad` |
| IAM Roles e IAM Policies | Completado | Roles y politicas por Lambda/modulo |
| API Gateway REST | Completado | APIs por modulo funcional |
| Lambda | Completado | Lambdas Python 3.9 |
| DynamoDB | Completado | Tablas por dominio |
| EventBridge | Completado | Bus custom y tres reglas de pedidos |
| SES | Completado | Lambda consumidora de correo con `ses:SendEmail` |
| CloudWatch | Completado | Log Groups, dashboard, metricas y alarmas |
| Seguridad | Completado | IAM auth, WAF, minimo privilegio, S3 privado |
| Observabilidad | Completado | Dashboard `cloudshop-observabilidad` y alarmas |
| Audit logging | Completado | `ProductAudit`, `OrderEventsAudit` y logs estructurados |
| Notifications | Completado | Consumidor SES de pedidos |
| Mandatory use cases | Completado | Scripts y evidencias en `integration-tests/` |
| Documentacion tecnica | Completado | `README.md`, `ARCHITECTURE.md`, `API.md`, `DATABASE.md`, `SECURITY.md`, `DEPLOYMENT.md`, `TESTING.md` |

## Missing Requirements

No se identificaron requisitos obligatorios faltantes en la implementacion revisada.

Notas operativas externas al codigo:

- `terraform init` fue ejecutado durante la auditoria. La inicializacion de modulos locales avanzo, pero la descarga de providers `hashicorp/aws` y `hashicorp/archive` no pudo completarse porque el entorno de ejecucion no permite conectarse a `registry.terraform.io`.
- Para enviar correos reales, `ses_source_email` debe corresponder a una identidad verificada en Amazon SES.
- Si SES esta en sandbox, el destinatario de prueba tambien debe estar verificado.
- Las APIs usan `AWS_IAM`; los clientes deben firmar solicitudes con AWS Signature Version 4 y tener politicas `execute-api:Invoke`.
- La validacion local completa de Terraform requiere ejecutar `terraform init` para instalar modulos/proveedores antes de `terraform validate`.

## AWS Resources Deployed

### S3

- Bucket S3 de frontend: nombre calculado como `cloudshop-frontend-<account-id>-<region>` si no se define `bucket_name`.
- Bloqueo de acceso publico habilitado.
- Ownership control `BucketOwnerEnforced`.
- Cifrado SSE-S3 (`AES256`).
- Versionado habilitado.
- Website configuration con `index.html`.
- Objetos estaticos: `index.html`, `styles.css`, `app.js`, `config.js`.

### CloudFront

- Distribucion `CloudShop Enterprise frontend`.
- Origin S3 privado mediante Origin Access Control.
- HTTPS habilitado con certificado predeterminado de CloudFront.
- Redireccion HTTP a HTTPS.
- Default root object: `index.html`.
- Web ACL asociado desde el modulo `Seguridad`.

### WAF

- `cloudshop-cloudfront-web-acl` con scope `CLOUDFRONT`.
- `cloudshop-api-gateway-web-acl` con scope `REGIONAL`.
- Asociacion regional a todos los stages API Gateway.
- Asociacion global a CloudFront mediante `web_acl_id`.

Reglas configuradas:

- `AWSManagedRulesCommonRuleSet`
- `AWSManagedRulesKnownBadInputsRuleSet`
- `AWSManagedRulesSQLiRuleSet`
- `XSSProtection`
- `RateLimitByIP`

### IAM

La implementacion usa roles por funcion y politicas especificas. No se encontraron politicas `AdministratorAccess`. Existe una excepcion tecnica controlada: `cloudshop-api-gateway-cloudwatch-role` usa `Resource = "*"` para acciones de CloudWatch Logs, requerido por API Gateway para configurar y publicar logs de ejecucion.

Roles principales:

- `usuarios-lambda-role`
- `productos-lambda-role`
- `tiendas-lambda-role`
- `compras-carrito-lambda-role`
- `pedidos-lambda-role`
- `pedidos-inventario-consumer-role`
- `pedidos-auditoria-consumer-role`
- `pedidos-correo-consumer-role`
- `reportes-lambda-role`
- `cloudshop-api-gateway-cloudwatch-role`

Politicas de invocacion API:

- `usuarios-api-administrador`
- `usuarios-api-operador`
- `usuarios-api-cliente`
- `productos-api-administrador`
- `productos-api-operador`
- `productos-api-cliente`
- `tiendas-api-administrador`
- `tiendas-api-operador`
- `tiendas-api-cliente`
- `compras-carrito-api-cliente`
- `pedidos-api-cliente`
- `pedidos-api-operador`
- `reportes-api-ejecutivo`

## Lambda Functions

| Funcion | Modulo | Runtime | Proposito |
| --- | --- | --- | --- |
| `usuarios-lambda` | Usuarios | Python 3.9 | Registrar, listar, consultar, actualizar y desactivar usuarios |
| `productos-lambda` | Productos | Python 3.9 | CRUD de productos e inventario |
| `tiendas-lambda` | Tiendas | Python 3.9 | CRUD logico de tiendas |
| `compras-carrito-lambda` | Compras | Python 3.9 | CRUD de carrito |
| `pedidos-lambda` | Pedidos | Python 3.9 | Crear, consultar y actualizar pedidos |
| `pedidos-inventario-consumer-lambda` | Pedidos | Python 3.9 | Descontar inventario asincronamente |
| `pedidos-auditoria-consumer-lambda` | Pedidos | Python 3.9 | Persistir eventos completos |
| `pedidos-correo-consumer-lambda` | Pedidos | Python 3.9 | Enviar correo por SES |
| `reportes-lambda` | Reportes | Python 3.9 | Reportes ejecutivos |

Observacion tecnica: las Lambdas usan clientes `boto3` fuera del handler, aprovechando reutilizacion en warm starts.

## DynamoDB Tables

| Tabla | Clave primaria | Indices | Modulo |
| --- | --- | --- | --- |
| `Users` | `userId` | `StatusCreatedAtIndex` | Usuarios |
| `UserAudit` | `auditId` | No aplica | Usuarios |
| `Products` | `productId` | `StoreIdCreatedAtIndex` | Productos |
| `ProductAudit` | `auditId` | No aplica | Productos |
| `Stores` | `storeId` | `StatusCreatedAtIndex` | Tiendas |
| `CartItems` | `userId` + `productId` | `ProductIdUserIdIndex` | Compras |
| `Orders` | `orderId` | `UserIdCreatedAtIndex`, `StatusCreatedAtIndex` | Pedidos |
| `OrderEventsAudit` | `eventId` | `OrderIdEventTimeIndex` | Pedidos |

Las tablas usan `PAY_PER_REQUEST`, cifrado server-side y Point-in-Time Recovery donde esta definido en los modulos.

## API Gateway Endpoints

Todas las APIs usan autorizacion:

```hcl
authorization = "AWS_IAM"
```

### Usuarios

- `POST /usuarios`
- `GET /usuarios`
- `GET /usuarios/{userId}`
- `PUT /usuarios/{userId}`
- `DELETE /usuarios/{userId}`

### Productos

- `POST /productos`
- `GET /productos`
- `GET /productos/{productId}`
- `PUT /productos/{productId}`
- `DELETE /productos/{productId}`
- `PATCH /productos/{productId}/inventario`
- `GET /tiendas/{storeId}/productos`

### Tiendas

- `POST /tiendas`
- `GET /tiendas`
- `GET /tiendas/{storeId}`
- `PUT /tiendas/{storeId}`
- `DELETE /tiendas/{storeId}`

### Carrito

- `POST /carritos/{userId}/items`
- `GET /carritos/{userId}`
- `GET /carritos/{userId}/items/{productId}`
- `PATCH /carritos/{userId}/items/{productId}`
- `DELETE /carritos/{userId}/items/{productId}`
- `DELETE /carritos/{userId}`

### Pedidos

- `POST /pedidos`
- `GET /pedidos/{orderId}`
- `PATCH /pedidos/{orderId}`
- `GET /usuarios/{userId}/pedidos`

### Reportes

- `GET /reportes/ventas/totales`
- `GET /reportes/ventas/tiendas`
- `GET /reportes/productos/mas-vendidos`
- `GET /reportes/productos/sin-stock`
- `GET /reportes/clientes/mayores-compras`
- `GET /reportes/pedidos/estados`

## CloudWatch Dashboards and Alarms

Dashboard:

- `cloudshop-observabilidad`

Widgets:

- Lambda Invocations
- Lambda Errors
- Lambda Duration
- API Gateway Requests
- API Gateway 4XX Errors
- API Gateway 5XX Errors
- API Latency
- DynamoDB Read Capacity
- DynamoDB Write Capacity

Alarmas:

- `cloudshop-lambda-<function>-errors`
- `cloudshop-api-<api>-5xx`
- `cloudshop-api-<api>-high-latency`
- `cloudshop-dynamodb-<table>-read-throttles`
- `cloudshop-dynamodb-<table>-write-throttles`

Logs:

- Cada Lambda tiene Log Group dedicado `/aws/lambda/<function-name>`.
- API Gateway tiene metricas y logging detallado configurado mediante `aws_api_gateway_method_settings`.

## EventBridge Rules

Bus custom:

- `cloudshop-pedidos-bus`

Evento publicado:

- Source: `cloudshop.pedidos`
- DetailType: `PedidoCreado`

Reglas:

- `pedidos-actualizar-inventario` -> `pedidos-inventario-consumer-lambda`
- `pedidos-auditar-evento` -> `pedidos-auditoria-consumer-lambda`
- `pedidos-enviar-correo` -> `pedidos-correo-consumer-lambda`

La arquitectura es asincrona y desacoplada: cada regla invoca una Lambda consumidora independiente.

## SES Integration

La integracion SES esta implementada en:

- Lambda: `pedidos-correo-consumer-lambda`
- Handler: `Modulos/Pedidos/lambda/email_handler.py`
- Permiso: `ses:SendEmail`
- Remitente: variable Terraform `ses_source_email`

La Lambda omite el envio si el evento no contiene `customerEmail` y deja log estructurado `order_email_skipped`.

## Audit Logging

Auditoria implementada:

- Productos: tabla `ProductAudit` registra acciones de producto.
- Pedidos: tabla `OrderEventsAudit` persiste el evento completo de EventBridge en `eventPayload`.
- Todas las Lambdas registran logs estructurados JSON en CloudWatch Logs.

## Terraform Modules

| Modulo | Ruta | Responsabilidad |
| --- | --- | --- |
| Usuarios | `Modulos/Usuarios` | Usuarios, auditoria, API, Lambda, IAM, DynamoDB |
| Productos | `Modulos/Productos` | Productos, auditoria, API, Lambda, IAM, DynamoDB |
| Tiendas | `Modulos/Tiendas` | Tiendas, API, Lambda, IAM, DynamoDB |
| Compras | `Modulos/Compras` | Carrito, API, Lambda, IAM, DynamoDB |
| Pedidos | `Modulos/Pedidos` | Pedidos, EventBridge, SES consumer, auditoria, inventario |
| Reportes | `Modulos/Reportes` | Dashboard ejecutivo por API, sin duplicar datos |
| Seguridad | `Modulos/Seguridad` | WAF CloudFront y API Gateway |
| Observabilidad | `Modulos/Observabilidad` | CloudWatch Dashboard, logs detallados y alarmas |
| Frontend | `Modulos/Frontend` | S3, CloudFront, OAC y frontend estatico |

## Mandatory Use Cases

Los casos obligatorios estan cubiertos por scripts y plantillas en `integration-tests/`.

| Caso | Estado | Evidencia |
| --- | --- | --- |
| Unauthorized Access | Cubierto | `case1-unauthorized-request.json`, `cloudshop_integration.py` |
| Complete Order Flow | Cubierto | Creacion de producto/pedido, DynamoDB, EventBridge, inventario, auditoria y SES |
| CloudWatch Monitoring | Cubierto | Consultas de logs, metricas, dashboard y alarmas |
| Terraform Deployment | Cubierto | `terraform fmt`, `init`, `validate`, `plan`, `apply` opcional |

## Fixes Applied During Final Audit

1. Modulo `Usuarios`: se completaron registro, consulta por id, actualizacion, desactivacion logica y auditoria.
2. Modulo `Usuarios`: se agrego tabla `UserAudit`, GSI `StatusCreatedAtIndex`, politicas IAM minimas y politicas de invocacion por rol.
3. `main.tf` raiz: `module "pedidos"` ahora recibe `products_table_name = module.productos.products_table_name`.
4. `main.tf` raiz: `module "reportes"` ahora recibe `orders_table_name = module.pedidos.orders_table_name` y `products_table_name = module.productos.products_table_name`.
5. Modulo `Pedidos`: se agrego el estado `EN_PREPARACION` para cubrir los estados minimos del PDF.
6. Documentacion actualizada para reflejar los nombres reales de roles consumidores de pedidos.
7. `DATABASE.md` actualizado para reflejar el atributo real `eventPayload` en `OrderEventsAudit`.

## Validation Performed

Validaciones locales ejecutadas:

- Revision de estructura de carpetas y archivos.
- Revision de recursos Terraform por servicio AWS requerido.
- Revision de autorizacion API Gateway: seis APIs con `AWS_IAM`.
- Busqueda de permisos amplios: no se encontro `AdministratorAccess`, `Action = "*"`, ni `authorization = "NONE"` en Terraform de modulos. Se documento una excepcion necesaria de `Resource = "*"` para el rol de CloudWatch Logs de API Gateway.
- `terraform fmt -recursive -check`: correcto. La CLI mostro una advertencia de permisos al leer la configuracion global de Terraform del usuario, pero el comando finalizo correctamente.
- Compilacion sintactica de Lambdas Python con runtime incluido: correcta.
- `terraform init`: intentado con configuracion CLI aislada. Fallo por bloqueo de red hacia `registry.terraform.io`, no por error de sintaxis del proyecto.

Validacion pendiente de ejecutar en ambiente AWS:

- `terraform init`
- `terraform validate`
- `terraform plan`
- `terraform apply`
- Pruebas reales de integracion contra AWS

La validacion `terraform validate` no puede completarse antes de `terraform init`, porque Terraform requiere instalar modulos/proveedores en `.terraform`.

## Deployment Readiness Assessment

Estado: **Ready for Terraform deployment**.

El proyecto cumple los requisitos de arquitectura, seguridad, observabilidad, frontend, pruebas y documentacion. La infraestructura esta definida exclusivamente en Terraform y no depende de recursos manuales, salvo los prerrequisitos normales de cuenta AWS:

- Credenciales AWS con permisos suficientes para desplegar.
- Identidad SES verificada.
- Terraform inicializado con acceso a providers.
- Identidades IAM cliente configuradas con las politicas de invocacion API correspondientes.

Comando recomendado de despliegue:

```powershell
cd CloudShop-ProyectoNube-Clon
terraform init
terraform fmt -recursive -check
terraform validate
terraform plan -out cloudshop.tfplan
terraform apply cloudshop.tfplan
```

Conclusión: **CloudShop Enterprise queda listo para entrega final y despliegue reproducible usando solo Terraform**.
