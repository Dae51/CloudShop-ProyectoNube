# CloudShop Enterprise

Documentacion tecnica del proyecto CloudShop Enterprise, una plataforma e-commerce serverless implementada en AWS con Terraform, API Gateway, Lambda, DynamoDB, EventBridge, SES, CloudFront, WAF y CloudWatch.

## Project Overview

CloudShop Enterprise esta organizado como una arquitectura modular. Cada modulo administra sus propios recursos de infraestructura y codigo Lambda dentro de `Modulos/`, siguiendo la separacion funcional del dominio:

- Usuarios: registro, consulta, actualizacion y desactivacion de usuarios.
- Productos: gestion de productos e inventario base.
- Tiendas: gestion de tiendas.
- Compras: carrito de compras.
- Pedidos: creacion, consulta y actualizacion de pedidos con flujo asincrono por eventos.
- Reportes: tablero ejecutivo basado en las tablas existentes.
- Frontend: sitio estatico servido por S3 y CloudFront.
- Seguridad: WAF para CloudFront y API Gateway.
- Observabilidad: dashboard, metricas, logs y alarmas de CloudWatch.

La infraestructura se declara exclusivamente con Terraform. No se requiere crear recursos manualmente desde la consola de AWS.

## Architecture Overview

El proyecto expone APIs REST mediante Amazon API Gateway. Cada API invoca funciones AWS Lambda escritas en Python 3.9. Las Lambdas persisten y consultan datos en Amazon DynamoDB.

El modulo de pedidos publica un evento `PedidoCreado` en un EventBridge Custom Event Bus. Tres consumidores desacoplados reaccionan a ese evento:

- Actualizacion de inventario.
- Auditoria del evento completo.
- Notificacion por correo mediante Amazon SES.

El frontend se publica como sitio estatico en S3, protegido por CloudFront Origin Access Control. La seguridad perimetral se implementa con AWS WAF.

## AWS Services Used

- AWS Lambda
- Amazon API Gateway REST API
- Amazon DynamoDB
- Amazon EventBridge
- Amazon SES
- Amazon S3
- Amazon CloudFront
- AWS WAF v2
- Amazon CloudWatch Logs
- Amazon CloudWatch Metrics, Dashboards y Alarms
- AWS IAM
- Terraform AWS Provider
- Terraform Archive Provider

## Folder Structure

```text
CloudShop-ProyectoNube-Clon/
  backend.tf
  provider.tf
  main.tf
  README.md
  ARCHITECTURE.md
  API.md
  DATABASE.md
  SECURITY.md
  DEPLOYMENT.md
  TESTING.md
  Modulos/
    Usuarios/
    Productos/
    Tiendas/
    Compras/
    Pedidos/
    Reportes/
    Seguridad/
    Observabilidad/
    Frontend/
  integration-tests/
```

Cada modulo contiene sus archivos Terraform (`main.tf`, `variables.tf`, `outputs.tf`) y, cuando aplica, el codigo de sus funciones Lambda.

## Deployment Instructions

Requisitos locales:

- Terraform `>= 1.6`.
- Credenciales AWS configuradas para crear recursos en la cuenta destino.
- Region AWS por defecto: `us-east-2`.
- Identidad SES verificada para el correo configurado en `ses_source_email`.

Flujo recomendado:

```powershell
cd CloudShop-ProyectoNube-Clon
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out cloudshop.tfplan
terraform apply cloudshop.tfplan
```

Al finalizar, Terraform publica salidas con URLs de APIs y frontend:

- `productos_api_url`
- `tiendas_api_url`
- `compras_api_url`
- `pedidos_api_url`
- `reportes_api_url`
- `frontend_url`
- `observabilidad_dashboard_name`

## Terraform Instructions

El archivo raiz `main.tf` instancia los modulos funcionales. Los modulos no estan reorganizados por servicios compartidos; cada modulo mantiene sus propios recursos.

El provider principal usa AWS en `us-east-2`. Tambien existe un alias `aws.us_east_1` requerido por WAF de CloudFront, porque los Web ACL de CloudFront deben crearse en `us-east-1`.

Comandos utiles:

```powershell
terraform fmt -recursive -check
terraform validate
terraform plan
terraform output
terraform output -json
```

Para destruir el ambiente:

```powershell
terraform destroy
```

## Environment Variables

Las variables de entorno principales son configuradas por Terraform en cada Lambda:

| Modulo | Funcion | Variables |
| --- | --- | --- |
| Usuarios | `usuarios-lambda` | `USERS_TABLE`, `AUDIT_TABLE`, `STATUS_INDEX` |
| Productos | `productos-lambda` | `PRODUCTS_TABLE`, `AUDIT_TABLE`, `STORE_INDEX` |
| Tiendas | `tiendas-lambda` | `STORES_TABLE`, `STATUS_INDEX` |
| Compras | `compras-carrito-lambda` | `CART_TABLE` |
| Pedidos API | `pedidos-lambda` | `ORDERS_TABLE`, `EVENT_BUS_NAME`, `USER_INDEX` |
| Pedidos Inventario | `pedidos-inventario-consumer-lambda` | `ORDERS_TABLE`, `PRODUCTS_TABLE` |
| Pedidos Auditoria | `pedidos-auditoria-consumer-lambda` | `AUDIT_TABLE` |
| Pedidos Correo | `pedidos-correo-consumer-lambda` | `SES_SOURCE_EMAIL` |
| Reportes | `reportes-lambda` | `ORDERS_TABLE`, `PRODUCTS_TABLE`, `STATUS_INDEX`, `USER_INDEX` |
| Frontend | `config.js` generado | URLs de API Gateway |

## API Endpoints

Todas las APIs estan publicadas como REST API de API Gateway con autorizacion `AWS_IAM`.

Resumen:

- `POST /usuarios`
- `GET /usuarios`
- `GET /usuarios/{userId}`
- `PUT /usuarios/{userId}`
- `DELETE /usuarios/{userId}`
- `POST /productos`
- `GET /productos`
- `GET /productos/{productId}`
- `PUT /productos/{productId}`
- `DELETE /productos/{productId}`
- `PATCH /productos/{productId}/inventario`
- `GET /tiendas/{storeId}/productos`
- `POST /tiendas`
- `GET /tiendas`
- `GET /tiendas/{storeId}`
- `PUT /tiendas/{storeId}`
- `DELETE /tiendas/{storeId}`
- `POST /carritos/{userId}/items`
- `GET /carritos/{userId}`
- `GET /carritos/{userId}/items/{productId}`
- `PATCH /carritos/{userId}/items/{productId}`
- `DELETE /carritos/{userId}/items/{productId}`
- `DELETE /carritos/{userId}`
- `POST /pedidos`
- `GET /pedidos/{orderId}`
- `PATCH /pedidos/{orderId}`
- `GET /usuarios/{userId}/pedidos`
- `GET /reportes/ventas/totales`
- `GET /reportes/ventas/tiendas`
- `GET /reportes/productos/mas-vendidos`
- `GET /reportes/productos/sin-stock`
- `GET /reportes/clientes/mayores-compras`
- `GET /reportes/pedidos/estados`

Detalle completo en [API.md](API.md).

## Authentication Flow

API Gateway usa `AWS_IAM`. Los clientes deben firmar las solicitudes con AWS Signature Version 4 y contar con permisos `execute-api:Invoke` sobre las rutas correspondientes.

El proyecto incluye politicas IAM de cliente por modulo, por ejemplo:

- `productos-api-administrador`
- `productos-api-operador`
- `productos-api-cliente`
- `usuarios-api-administrador`
- `usuarios-api-operador`
- `usuarios-api-cliente`
- `tiendas-api-administrador`
- `tiendas-api-operador`
- `tiendas-api-cliente`
- `compras-carrito-api-cliente`
- `pedidos-api-cliente`
- `pedidos-api-operador`
- `reportes-api-ejecutivo`

Estas politicas representan permisos de invocacion. Deben adjuntarse a usuarios, roles o grupos de la organizacion segun el perfil requerido.

## EventBridge Workflow

Cuando se ejecuta `POST /pedidos`, la Lambda `pedidos-lambda`:

1. Valida el cuerpo de la solicitud.
2. Crea el pedido en DynamoDB `Orders`.
3. Publica un evento `PedidoCreado` en el bus `cloudshop-pedidos-bus`.
4. Actualiza el pedido con `eventPublicationStatus = PUBLICADO` si la publicacion fue exitosa.

EventBridge ejecuta tres reglas independientes:

- `pedidos-actualizar-inventario`
- `pedidos-auditar-evento`
- `pedidos-enviar-correo`

Cada regla invoca una Lambda consumidora distinta. Las consumidoras no se llaman entre si.

## CloudWatch Monitoring

El modulo `Observabilidad` crea:

- Dashboard `cloudshop-observabilidad`.
- Metricas de Lambda: invocaciones, errores y duracion.
- Metricas de API Gateway: solicitudes, 4XX, 5XX y latencia.
- Metricas DynamoDB: capacidad leida/escrita.
- Alarmas por errores Lambda.
- Alarmas por 5XX en API Gateway.
- Alarmas de alta latencia.
- Alarmas de throttling de DynamoDB.
- Configuracion de logs y metricas detalladas para API Gateway.

Cada Lambda tiene su propio Log Group en CloudWatch con nombre `/aws/lambda/<nombre-funcion>`.

## Security Model

La seguridad implementada combina:

- Autorizacion IAM en API Gateway.
- Politicas IAM de Lambda con permisos especificos por tabla, indice o servicio.
- AWS WAF para CloudFront y API Gateway.
- CloudFront con HTTPS y redireccion a HTTPS.
- Bucket S3 privado con acceso permitido solo desde CloudFront mediante Origin Access Control.
- Logs estructurados en las Lambdas para auditoria operacional.

Detalle completo en [SECURITY.md](SECURITY.md).

## IAM Roles

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

Cada rol tiene una politica propia de minimo privilegio en lugar de permisos administrados amplios.

## DynamoDB Tables

Tablas creadas por Terraform:

- `Users`
- `UserAudit`
- `Products`
- `ProductAudit`
- `Stores`
- `CartItems`
- `Orders`
- `OrderEventsAudit`

Detalle de claves, indices y patrones de acceso en [DATABASE.md](DATABASE.md).

## Troubleshooting Guide

Problemas frecuentes:

- `403 Forbidden`: la solicitud no esta firmada con SigV4 o la identidad no tiene `execute-api:Invoke`.
- `400 Bad Request`: el cuerpo JSON no cumple las validaciones de la Lambda.
- `404 Not Found`: el recurso no existe o la ruta no esta definida.
- `409 Conflict`: conflicto de estado o condicion DynamoDB no cumplida.
- `500 Internal Server Error`: error de AWS SDK, publicacion de evento, SES o permisos insuficientes.
- El correo SES no llega: verificar identidad de origen y destino si la cuenta SES esta en sandbox.
- El frontend carga pero las APIs fallan: confirmar que el cliente este autorizado para invocar APIs `AWS_IAM`.
- WAF bloquea una solicitud: revisar metricas del Web ACL y reglas administradas.

Para diagnostico:

```powershell
terraform output
aws logs tail /aws/lambda/pedidos-lambda --follow
aws cloudwatch describe-alarms --alarm-name-prefix cloudshop
```
