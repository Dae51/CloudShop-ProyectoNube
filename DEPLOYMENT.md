# Despliegue

## Required AWS Credentials

La identidad usada para desplegar debe poder crear y administrar:

- Lambda
- API Gateway
- DynamoDB
- EventBridge
- SES permissions de envio usados por Lambda
- S3
- CloudFront
- WAF v2
- CloudWatch Logs, Dashboards y Alarms
- IAM Roles y Policies

Terraform no crea recursos manualmente desde la consola. Todo el ambiente sale del codigo de infraestructura.

## Initialization

Desde la raiz:

```powershell
cd CloudShop-ProyectoNube-Clon
terraform init
```

El provider AWS usa por defecto:

```hcl
aws_region = "us-east-2"
```

## Validation

```powershell
terraform fmt -recursive -check
terraform validate
```

Si se necesita aplicar formato:

```powershell
terraform fmt -recursive
```

## Plan

```powershell
terraform plan -out cloudshop.tfplan
```

Tambien puede generarse salida JSON para automatizaciones:

```powershell
terraform show -json cloudshop.tfplan
```

## Apply

```powershell
terraform apply cloudshop.tfplan
```

Despues del despliegue:

```powershell
terraform output
terraform output -json
```

Outputs relevantes:

- `productos_api_url`
- `tiendas_api_url`
- `compras_api_url`
- `pedidos_api_url`
- `reportes_api_url`
- `frontend_url`
- `cloudfront_web_acl_arn`
- `api_gateway_web_acl_arn`
- `observabilidad_dashboard_name`

## Destroy

```powershell
terraform destroy
```

Antes de destruir, validar si existen datos que deban exportarse desde DynamoDB.

## Deployment Order

El despliegue se ejecuta desde el modulo raiz. Terraform resuelve dependencias mediante referencias entre modulos.

Orden logico de recursos:

1. Tablas DynamoDB funcionales.
2. IAM Roles y Policies.
3. CloudWatch Log Groups.
4. Lambdas y paquetes generados por `archive_file`.
5. APIs Gateway y permisos de invocacion.
6. EventBridge bus, reglas y targets del modulo `Pedidos`.
7. Frontend S3 y CloudFront.
8. WAF y asociaciones.
9. Observabilidad, dashboards, metricas, logs detallados y alarmas.

No se debe desplegar modulo por modulo manualmente si se busca reproducibilidad total. Usar siempre el `main.tf` raiz.

## Terraform Commands

Comandos de operacion diaria:

```powershell
terraform init
terraform fmt -recursive
terraform validate
terraform plan
terraform apply
terraform output
terraform destroy
```

Comandos usados por las pruebas de despliegue:

```powershell
terraform fmt -recursive -check
terraform init
terraform validate
terraform plan -out cloudshop.tfplan
terraform apply -auto-approve cloudshop.tfplan
```

## Configuration Notes

Variables principales:

- `aws_region`: region AWS del provider principal.
- `stage_name`: cada modulo API usa stage, por defecto `dev` segun variables modulares.
- `ses_source_email`: correo de origen de SES para notificaciones de pedidos.
- Nombres de tablas pueden parametrizarse en modulos especificos.

Requisitos SES:

- Verificar el correo de origen configurado.
- Si SES esta en sandbox, verificar tambien el destinatario usado en pruebas.

## Post-deployment Verification

Verificaciones recomendadas:

```powershell
terraform output frontend_url
terraform output pedidos_api_url
aws cloudwatch describe-alarms --alarm-name-prefix cloudshop
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/
```

Luego ejecutar las pruebas de `integration-tests` segun [TESTING.md](TESTING.md).
