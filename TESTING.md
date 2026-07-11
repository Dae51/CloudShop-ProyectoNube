# Pruebas y Validacion

El proyecto incluye scripts de integracion en `integration-tests/`. Estos scripts estan pensados para ejecutarse contra una infraestructura ya desplegada en AWS. No crean recursos manuales; consumen lo desplegado por Terraform.

## Mandatory Test Cases

### Case 1: Unauthorized Access

Objetivo:

- Intentar acceder a un endpoint administrativo con una identidad sin permisos.
- Verificar respuesta `403 Forbidden`.
- Evidenciar el intento fallido en logs de API Gateway.

Endpoint usado:

```http
POST /productos
```

Resultado esperado:

```json
{
  "status": 403
}
```

Evidencia esperada:

- Respuesta HTTP 403.
- Log en `API-Gateway-Execution-Logs_<productos-rest-api-id>/dev`.

### Case 2: Complete Order Flow

Objetivo:

- Crear un producto con inventario.
- Crear un pedido.
- Verificar persistencia en `Orders`.
- Verificar publicacion del evento EventBridge.
- Verificar descuento de inventario.
- Verificar auditoria en `OrderEventsAudit`.
- Verificar intento de correo mediante SES.
- Mostrar logs de ejecucion.

Flujo:

1. Crear producto en `POST /productos`.
2. Crear pedido en `POST /pedidos`.
3. Consultar `Orders`.
4. Consultar `Products` para inventario actualizado.
5. Consultar `OrderEventsAudit`.
6. Consultar logs de:
   - `/aws/lambda/pedidos-lambda`
   - `/aws/lambda/pedidos-inventario-consumer-lambda`
   - `/aws/lambda/pedidos-auditoria-consumer-lambda`
   - `/aws/lambda/pedidos-correo-consumer-lambda`

Respuesta esperada al crear pedido:

```json
{
  "status": 201,
  "body": {
    "data": {
      "orderId": "uuid",
      "eventPublicationStatus": "PUBLICADO",
      "inventoryStatus": "PENDIENTE"
    }
  }
}
```

El estado `inventoryStatus` puede actualizarse asincronicamente a `DESCONTADO` despues de que EventBridge invoque al consumidor de inventario.

### Case 3: CloudWatch Monitoring

Objetivo:

- Demostrar logs Lambda.
- Consultar metricas API Gateway.
- Consultar metricas de errores.
- Verificar dashboard.
- Verificar estado de alarmas.

Resultado esperado:

- Dashboard `cloudshop-observabilidad` existe.
- Alarmas con prefijo `cloudshop` existen.
- Las consultas de metricas retornan datos o arreglos vacios sin error.

### Case 4: Terraform Deployment

Objetivo:

- Verificar que la infraestructura puede desplegarse desde cero solo con Terraform.

Comandos esperados:

```powershell
terraform fmt -recursive -check
terraform init
terraform validate
terraform plan -out cloudshop.tfplan
terraform apply -auto-approve cloudshop.tfplan
```

Resultado esperado:

- Codigo de salida `0` para cada comando.
- Outputs de Terraform disponibles despues de `apply`.
- No se requiere creacion manual de recursos AWS.

## Test Scripts

Archivos existentes:

- `integration-tests/cloudshop_integration.py`
- `integration-tests/run-integration-tests.ps1`
- `integration-tests/cloudshop-test-config.example.json`
- `integration-tests/EXPECTED_RESPONSES.md`
- `integration-tests/VERIFICATION_CHECKLIST.md`
- `integration-tests/requests/case1-unauthorized-request.json`
- `integration-tests/requests/case2-create-product.json`
- `integration-tests/requests/case2-create-order.json`
- `integration-tests/requests/case3-monitoring-queries.json`

## Execution

Preparar configuracion:

```powershell
cd CloudShop-ProyectoNube-Clon\integration-tests
Copy-Item .\cloudshop-test-config.example.json .\cloudshop-test-config.local.json
```

Editar `cloudshop-test-config.local.json` con:

- Region.
- Perfil AWS administrador.
- Perfil AWS no autorizado.
- Correo de cliente verificado si SES esta en sandbox.
- URLs de API si no se leen desde `terraform output -json`.

Ejecutar todos los casos:

```powershell
.\run-integration-tests.ps1 -Config .\cloudshop-test-config.local.json -Case all
```

Ejecutar un caso:

```powershell
.\run-integration-tests.ps1 -Config .\cloudshop-test-config.local.json -Case case2
```

Permitir `terraform apply` durante el caso 4:

```powershell
.\run-integration-tests.ps1 -Config .\cloudshop-test-config.local.json -Case case4 -Apply
```

Sin `-Apply`, el caso 4 ejecuta formato, inicializacion, validacion y plan.

## Sample Requests

### Crear producto

```http
POST /productos
Content-Type: application/json
Authorization: AWS4-HMAC-SHA256 ...
```

```json
{
  "code": "SKU-TEST-001",
  "name": "Producto de Prueba",
  "description": "Producto usado por pruebas de integracion",
  "category": "Testing",
  "price": 10,
  "inventory": 5,
  "storeId": "store-test-001"
}
```

### Crear pedido

```http
POST /pedidos
Content-Type: application/json
Authorization: AWS4-HMAC-SHA256 ...
```

```json
{
  "userId": "user-test-001",
  "currency": "USD",
  "customerEmail": "cliente@example.com",
  "items": [
    {
      "productId": "product-id-generado",
      "productName": "Producto de Prueba",
      "storeId": "store-test-001",
      "quantity": 1,
      "unitPrice": 10
    }
  ]
}
```

## Sample Responses

### Producto creado

```json
{
  "data": {
    "productId": "uuid",
    "status": "ACTIVE",
    "inventory": 5
  }
}
```

### Pedido creado

```json
{
  "data": {
    "orderId": "uuid",
    "status": "PENDIENTE",
    "total": 10,
    "eventPublicationStatus": "PUBLICADO"
  }
}
```

### Error de autorizacion

```json
{
  "message": "Forbidden"
}
```

## Validation Procedures

Validaciones operativas:

- Confirmar que cada Lambda tiene Log Group `/aws/lambda/<funcion>`.
- Confirmar que APIs usan autorizacion `AWS_IAM`.
- Confirmar que WAF esta asociado a CloudFront y API Gateway.
- Confirmar que `POST /pedidos` escribe en `Orders`.
- Confirmar que `OrderEventsAudit` recibe eventos.
- Confirmar que `Products.inventory` disminuye despues del flujo asincrono.
- Confirmar que CloudWatch Dashboard existe.
- Confirmar que alarmas `cloudshop-*` existen.
- Confirmar que `terraform plan` puede ejecutarse desde la raiz.

## Evidence Logs

Cada ejecucion de los scripts escribe evidencia JSON en:

```text
integration-tests/evidence/
```

La evidencia incluye:

- Solicitudes y respuestas API.
- Registros DynamoDB consultados.
- Evidencia del flujo EventBridge.
- Logs Lambda.
- Logs API Gateway.
- Metricas CloudWatch.
- Estado de alarmas.
- Salidas de comandos Terraform.

