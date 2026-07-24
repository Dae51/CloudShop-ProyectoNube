# CloudShop Enterprise

CloudShop es una solución de comercio electrónico serverless para AWS. El repositorio
incluye SPA React, autenticación Cognito, autorización `AWS_IAM`, API Gateway,
Lambdas por dominio, DynamoDB, EventBridge, SES, CloudWatch, WAF y Terraform.

Estado de entrega: **NOT READY FOR SUBMISSION**. El código, los tests y los planes
estáticos están disponibles, pero el despliegue real está bloqueado porque el backend
S3 anterior no existe, SES no tiene identidades verificadas y no se confirmó
presupuesto/entorno del curso. No se ejecutó `terraform apply`.

## Arquitectura resumida

- React + Vite produce un build estático.
- CloudFront usa Origin Access Control para leer un bucket S3 privado.
- Cognito User Pool autentica; Identity Pool entrega credenciales temporales del rol
  `ADMINISTRADOR`, `OPERADOR` o `CLIENTE`.
- El navegador firma solicitudes SigV4. Todas las rutas de negocio usan `AWS_IAM`.
- WAF regional se asocia directamente al stage de API Gateway.
- Checkout usa `TransactWriteItems` para pedido, inventario, auditoría, outbox,
  idempotencia y vaciado de carrito.
- DynamoDB Streams publica el outbox en EventBridge; un consumidor idempotente envía
  correo con SES y EventBridge entrega fallos agotados a una DLQ SQS.

El detalle y los diagramas están en [docs/architecture.md](docs/architecture.md).

## Requisitos locales

- Terraform `>= 1.6`
- AWS CLI v2
- Python con `boto3==1.40.76` y `PyYAML==6.0.2`
- Node.js `>= 20.19` y npm

No se necesitan secretos para ejecutar tests, build o `terraform validate`.

## Validación local reproducible

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s Modulos/Productos/tests -v

cd Modulos/Frontend/app
npm ci
npm test
npm run build
cd ../../..

terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

El frontend falla de forma visible si falta su configuración real; no usa mocks ni
fallback demo. Terraform genera `config.js` al subir el build.

## Backend y despliegue

El backend se crea mediante el stack separado [bootstrap](bootstrap/README.md). No se
debe crear el bucket manualmente.

```bash
terraform -chdir=bootstrap init
terraform -chdir=bootstrap plan -out=bootstrap.tfplan
terraform -chdir=bootstrap apply bootstrap.tfplan

terraform init -reconfigure \
  -backend-config="bucket=$(terraform -chdir=bootstrap output -raw state_bucket_name)" \
  -backend-config="key=$(terraform -chdir=bootstrap output -raw state_key)" \
  -backend-config="region=$(terraform -chdir=bootstrap output -raw state_region)" \
  -backend-config="encrypt=true" \
  -backend-config="use_lockfile=true"

terraform plan \
  -var='ses_sender_email=remitente-verificado@example.edu' \
  -var='ses_demo_recipient=destinatario-verificado@example.edu' \
  -out=cloudshop.tfplan
```

Antes de aplicar deben coincidir cuenta, región y entorno; el plan debe tener cero
destrucciones/reemplazos dudosos y debe existir presupuesto para WAF. Solo se aplica
el plan binario revisado.

## Roles y rutas

- `CLIENTE`: catálogo, carrito, checkout, pedidos propios y cancelación permitida.
- `OPERADOR`: catálogo, inventario y máquina de estados de pedidos.
- `ADMINISTRADOR`: usuarios/roles, tiendas, productos y seis reportes.

El auto-registro siempre crea `CLIENTE`. La primera identidad administrativa requiere
un bootstrap de confianza ejecutado por un operador AWS autorizado; después, todos los
cambios de rol pasan por `PATCH /usuarios/{userId}/rol` y quedan auditados.

El contrato completo está en [contracts/openapi.yaml](contracts/openapi.yaml).

## Documentación de entrega

- [Documento técnico](docs/technical-document.md)
- [Arquitectura](docs/architecture.md)
- [Diseño de API](docs/api-design.md)
- [Diseño de base de datos](docs/database-design.md)
- [Diseño de seguridad](docs/security-design.md)
- [Trazabilidad](docs/requirements-traceability.md)
- [Reporte de pruebas](docs/test-report.md)
- [Evidencia de despliegue](docs/deployment-evidence.md)
- [Guion de demo](docs/demo-script.md)
- [Banco de preguntas](docs/technical-question-bank.md)
- [ADR de autenticación/frontend](docs/adr/ADR-001-auth-and-frontend.md)

## Reglas operativas

- No ejecutar `terraform destroy`.
- No crear recursos CloudShop manualmente.
- No versionar `.tfvars`, planes, state, tokens, contraseñas ni correos de evidencia.
- No considerar un plan como despliegue.
- No considerar mocks como integración AWS.
