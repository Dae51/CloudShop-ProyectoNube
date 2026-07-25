# CloudShop Enterprise

> Plataforma de comercio electrónico serverless sobre AWS — React + Vite · API Gateway · Lambda · DynamoDB · Cognito · Terraform

---

## Índice

1. [Descripción general](#1-descripción-general)
2. [Arquitectura](#2-arquitectura)
3. [Stack tecnológico](#3-stack-tecnológico)
4. [Módulos de backend](#4-módulos-de-backend)
5. [Frontend](#5-frontend)
6. [Seguridad y autorización](#6-seguridad-y-autorización)
7. [API REST](#7-api-rest)
8. [Base de datos](#8-base-de-datos)
9. [Observabilidad](#9-observabilidad)
10. [Pruebas](#10-pruebas)
11. [Infraestructura Terraform](#11-infraestructura-terraform)
12. [Guía de despliegue en AWS](#12-guía-de-despliegue-en-aws)
13. [Variables de Terraform](#13-variables-de-terraform)
14. [Outputs](#14-outputs)
15. [Archivos prohibidos en repositorio](#15-archivos-prohibidos-en-repositorio)
16. [Decisiones de arquitectura](#16-decisiones-de-arquitectura)
17. [Limitaciones conocidas](#17-limitaciones-conocidas)

---

## 1. Descripción general

CloudShop Enterprise es una aplicación de e-commerce de múltiples roles construida íntegramente sobre servicios administrados de AWS. La plataforma permite a clientes explorar catálogos, gestionar carritos y realizar pedidos; a operadores administrar el flujo de estados y el inventario; y a administradores controlar usuarios, tiendas, productos y consultar reportes ejecutivos.

Toda la infraestructura está declarada en **Terraform modular**. No se crea ni modifica ningún recurso AWS fuera de Terraform.

### Características principales

- **SPA React + Vite** distribuida desde S3 privado a través de CloudFront con OAC.
- **Autenticación** mediante Cognito User Pool + Identity Pool con credenciales STS temporales y firma SigV4.
- **API REST unificada** en API Gateway con autorización `AWS_IAM` y policies de mínimo privilegio por ruta y rol.
- **Checkout transaccional** con control de stock, idempotencia y outbox en una única operación DynamoDB.
- **Eventos desacoplados**: DynamoDB Streams → Lambda Relay → EventBridge → Lambda Notificaciones → SES.
- **Observabilidad completa**: CloudWatch Logs estructurados, métricas detalladas, alarmas y dashboard.
- **WAF regional** asociado directamente al stage de API Gateway con rate limit y reglas administradas.

---

## 2. Arquitectura

### Vista de contexto

```
Usuario → CloudFront (OAC) → S3 privado (SPA estática)
Usuario → Cognito User Pool → Identity Pool → STS (credenciales temporales)
Usuario → WAF regional → API Gateway REST (AWS_IAM) → Lambda por dominio → DynamoDB
Lambda Pedidos → DynamoDB Streams → Lambda Relay → EventBridge → Lambda Notificaciones → SES
Todas las Lambdas → CloudWatch Logs / Métricas
```

### Flujo de identidad

1. El navegador autentica contra Cognito User Pool y recibe un ID token con el grupo del usuario.
2. El Identity Pool intercambia el token por credenciales STS temporales del rol IAM asociado al grupo.
3. Cada petición HTTP se firma con SigV4 usando las credenciales temporales.
4. API Gateway verifica la firma y la policy `execute-api:Invoke` antes de invocar la Lambda.
5. La Lambda revalida rol, permiso y propiedad del recurso.

### Flujo de pedido (Outbox + EventBridge)

```
POST /pedidos → TransactWriteItems (stock + pedido + auditoría + outbox + idempotencia + borrar carrito)
             → DynamoDB Stream → Lambda Relay → EventBridge PutEvents
             → Lambda Notificaciones → SES SendEmail
```

Los fallos del relay y de la notificación se dirigen a **DLQ separadas** (SQS). La semántica de entrega es *al-menos-una-vez*; consumidores son idempotentes por `eventId`.

---

## 3. Stack tecnológico

| Capa | Tecnología |
|---|---|
| Frontend | React 18, Vite, AWS Amplify Auth |
| Hosting frontend | S3 (privado) + CloudFront (OAC, TLS 1.2) |
| Autenticación | Amazon Cognito User Pool + Identity Pool |
| API | Amazon API Gateway REST (`AWS_IAM`) |
| Lógica de negocio | AWS Lambda (Python 3.12) |
| Base de datos | Amazon DynamoDB (PAY_PER_REQUEST, PITR, cifrado) |
| Eventos | DynamoDB Streams + Amazon EventBridge + Amazon SQS (DLQ) |
| Correo | Amazon SES |
| Protección | AWS WAF v2 (Regional) |
| Observabilidad | Amazon CloudWatch (Logs, Métricas, Alarmas, Dashboard) |
| IaC | Terraform ≥ 1.5, provider AWS ≥ 5.x |

---

## 4. Módulos de backend

La carpeta `Modulos/` contiene un módulo Terraform + Lambda por cada dominio:

| Módulo | Descripción |
|---|---|
| `Autenticacion` | Cognito User Pool, Identity Pool, tablas Users / Audit / Idempotency |
| `Usuarios` | CRUD de perfiles, desactivación y cambio de rol auditado |
| `Tiendas` | CRUD lógico con control optimista (`updatedAt`) |
| `Productos` | CRUD, actualización de inventario, auditoría transaccional |
| `Carritos` | Carrito persistente por identidad federada con versión optimista |
| `Pedidos` | Checkout transaccional, máquina de estados, cancelación, outbox, relay, SES |
| `Reportes` | Seis métricas ejecutivas exclusivas del rol ADMINISTRADOR |
| `Frontend` | S3 bucket + CloudFront + invalidación + `config.js` de runtime |
| `Shared` | Lambda Layer con utilidades comunes (logger, errors, responses) |

---

## 5. Frontend

La SPA se construye con **React + Vite** y se despliega en S3/CloudFront. No existen datos demo en tiempo de ejecución; si falta `config.js`, la aplicación falla de forma cerrada.

### Vistas por rol

| Rol | Vistas disponibles |
|---|---|
| **CLIENTE** | Registro, login, catálogo, detalle de producto, carrito, checkout, mis pedidos, cancelar pedido |
| **OPERADOR** | Lista de pedidos, detalle, avance de estado, gestión de inventario |
| **ADMINISTRADOR** | Usuarios y roles, tiendas, productos, seis reportes ejecutivos |

### Seguridad frontend

- Guards de navegación por rol (solo UX; no son control de seguridad).
- Cliente SigV4 centralizado; no hay tokens en `localStorage`.
- React escapa texto por defecto; sin `dangerouslySetInnerHTML`.
- CSP configurado en CloudFront: scripts/estilos del mismo origen; `connect-src` limitado a AWS y Cognito.

---

## 6. Seguridad y autorización

### Roles canónicos

| Rol | Cognito Group | IAM Role |
|---|---|---|
| ADMINISTRADOR | `ADMINISTRADOR` | `cloudshop-{env}-administrador` |
| OPERADOR | `OPERADOR` | `cloudshop-{env}-operador` |
| CLIENTE | `CLIENTE` | `cloudshop-{env}-cliente` |

> `EJECUTIVO` no existe. Una sesión con cero o múltiples grupos oficiales no recibe credenciales.

### Matriz de permisos

| Capacidad | ADMINISTRADOR | OPERADOR | CLIENTE |
|---|:---:|:---:|:---:|
| Listar / editar usuarios | ✅ | ❌ | Solo propio |
| Asignar roles | ✅ | ❌ | ❌ |
| CRUD tiendas | ✅ | ❌ | ❌ |
| CRUD productos | ✅ | ❌ | ❌ |
| Actualizar inventario | ✅ | ✅ | ❌ |
| Carrito / checkout | ❌ | ❌ | ✅ |
| Gestionar estados de pedidos | ❌ | ✅ | ❌ |
| Ver pedidos | Todos | Todos | Solo propios |
| Cancelar pedido | ❌ | ✅ | Solo propio (PENDIENTE/CONFIRMADO) |
| Reportes ejecutivos | ✅ | ❌ | ❌ |

### Capas de autorización

1. **IAM (API Gateway):** policy `execute-api:Invoke` por método y path específico. Sin `execute-api:*` ni `Resource="*"`.
2. **Dominio (Lambda):** validación de rol, permiso y propiedad derivados del contexto de identidad.
3. **UI (React):** oculta rutas ajenas al rol (no es control de seguridad, solo UX).

---

## 7. API REST

- **Base URL:** `https://{apiId}.execute-api.{region}.amazonaws.com/{stage}`
- **Autorización:** `AWS_IAM` + SigV4 en todos los endpoints de negocio.
- **Contrato ejecutable:** [`contracts/openapi.yaml`](contracts/openapi.yaml) — 34 operaciones, OpenAPI 3.1.
- **Correlation ID:** todas las respuestas incluyen `X-Correlation-Id`.

### Resumen de rutas

| Dominio | Rutas principales |
|---|---|
| Usuarios | `GET /usuarios`, `GET/PUT/DELETE /usuarios/{id}`, `PATCH /usuarios/{id}/rol` |
| Tiendas | `GET/POST /tiendas`, `GET/PUT/DELETE /tiendas/{id}` |
| Productos | `GET/POST /productos`, `GET/PUT/DELETE /productos/{id}`, `PATCH /productos/{id}/inventario` |
| Carrito | `GET/DELETE /carritos/mio`, `POST /items`, `PATCH/DELETE /items/{productId}` |
| Pedidos | `GET/POST /pedidos`, `GET /pedidos/mios`, `GET/PATCH /pedidos/{id}`, `POST /pedidos/{id}/cancelacion` |
| Reportes | `GET /reportes/ventas`, `/productos-mas-vendidos`, `/pedidos-por-estado`, `/ingresos-por-tienda`, `/clientes-top`, `/inventario-bajo` |

### Formato de error

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "No tiene permisos para realizar esta acción",
    "correlationId": "8cb69bd7-..."
  }
}
```

### Máquina de estados de pedidos

```
PENDIENTE → CONFIRMADO → EN_PREPARACION → ENVIADO → ENTREGADO
     |            |
     +----------→ CANCELADO
```

---

## 8. Base de datos

Todas las tablas usan `PAY_PER_REQUEST`, cifrado administrado y Point-in-Time Recovery.

| Tabla | PK | Índices secundarios |
|---|---|---|
| Users | `userId` | GSI `EmailIndex(email)` |
| Stores | `storeId` | — |
| Products | `productId` | GSI `StoreIdCreatedAtIndex(storeId, createdAt)` |
| Carts | `customerId` | — |
| Orders | `orderId` | GSI `CustomerCreatedAtIndex`, GSI `StatusCreatedAtIndex` |
| Audit | `auditId` | GSI `ResourceOccurredAtIndex`, GSI `CorrelationIndex` |
| Outbox | `eventId` | GSI `StatusOccurredAtIndex` + DynamoDB Streams |
| Idempotency | `idempotencyKey` | TTL `expiresAt` |

### Garantías de consistencia

- Stock nunca baja de cero: condición `inventory >= quantity` dentro de la transacción.
- Checkout valida tienda `ACTIVE` con `ConditionCheck` transaccional.
- Cancelación repone inventario exactamente una vez con flag `inventoryRestored`.
- Idempotency TTL: 24 h para comandos, 30 días para eventos.

---

## 9. Observabilidad

- **Log Groups:** 10 grupos (9 Lambdas + WAF), retención configurable (default 30 días).
- **Logs estructurados:** JSON con `correlationId`; tokens, email y secretos filtrados.
- **Métricas:** stage metrics detalladas en API Gateway.
- **Filtros de métricas:** `AuthenticationErrors` y `ApplicationErrors`.
- **Dashboard CloudWatch:** Count, 4XX, 5XX, latencia, integración, errores Lambda y WAF.
- **Alarmas:** tasa de 5XX, pico de 4XX, latencia P99 y errores de aplicación.

---

## 10. Pruebas

Todos los resultados siguientes son locales. Las pruebas TST-01..04 contra AWS permanecen PARTIAL/BLOCKED hasta ejecutar el despliegue.

| Suite | Comando | Resultado |
|---|---|---|
| Backend global | `python -m unittest discover -s tests -v` | ✅ PASS 44/44 |
| Backend residual | pruebas focales tras fixer | ✅ PASS 16/16 |
| Productos heredado | `python -m unittest discover -s Modulos/Productos/tests -v` | ✅ PASS 12/12 |
| Frontend Vitest | `npm test --run` en `Modulos/Frontend/app` | ✅ PASS 8/8 |
| Build Vite | `npm run build` | ✅ PASS, 670 módulos |
| Terraform fmt | `terraform fmt -check -recursive` | ✅ PASS |
| Terraform validate raíz | `terraform validate -no-color` | ✅ PASS |
| Terraform validate bootstrap | `terraform -chdir=bootstrap validate -no-color` | ✅ PASS |

### Comando de validación completa (ejecutar antes de cualquier despliegue)

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s Modulos/Productos/tests -v
cd Modulos/Frontend/app && npm install && npm test -- --run && npm run build && cd ../../..
terraform fmt -check -recursive
terraform validate -no-color
terraform -chdir=bootstrap validate -no-color
```

---

## 11. Infraestructura Terraform

### Estructura

```
.
├── bootstrap/          # Bucket S3 remoto para Terraform state
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── Modulos/
│   ├── Autenticacion/  # Cognito + tablas base
│   ├── Usuarios/
│   ├── Tiendas/
│   ├── Productos/
│   ├── Carritos/
│   ├── Pedidos/        # Checkout + Streams + EventBridge + SES
│   ├── Reportes/
│   ├── Frontend/       # S3 + CloudFront
│   └── Shared/         # Lambda Layer
├── main.tf             # Composición de módulos
├── api_gateway.tf      # REST API unificada
├── observability.tf    # CloudWatch + WAF
├── variables.tf
├── outputs.tf
├── provider.tf
└── contracts/
    └── openapi.yaml
```

### Módulo bootstrap

Crea el bucket S3 de state con:
- Acceso público bloqueado.
- Cifrado SSE-AES256.
- Versionado habilitado.
- `prevent_destroy = true`.

---

## Guía de despliegue en AWS

> ⚠️ **No crear recursos manualmente.** Toda la infraestructura debe permanecer declarada en Terraform.

### Prerrequisitos

- AWS CLI configurado con perfil del entorno del curso (`lab-user` o equivalente).
- Terraform ≥ 1.5 instalado.
- Python 3.12 y Node.js 20+ instalados localmente.
- Región confirmada con el docente (por defecto `us-east-1`).
- Presupuesto WAF aprobado (costo fijo por Web ACL + reglas + requests).
- Cuenta SES con capacidad de verificar identidades (o producción habilitada).

---

### Paso 1 — Confirmar identidad y entorno

```bash
aws sts get-caller-identity
aws configure list
```

Verificar que la cuenta y región correspondan al entorno del curso antes de continuar.

---

### Paso 2 — Ejecutar validaciones locales completas

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s Modulos/Productos/tests -v
cd Modulos/Frontend/app && npm install && npm test -- --run && npm run build && cd ../../..
terraform fmt -check -recursive
terraform validate -no-color
terraform -chdir=bootstrap validate -no-color
```

No continuar si alguna validación falla.

---

### Paso 3 — Desplegar el bootstrap (bucket de state remoto)

```bash
terraform -chdir=bootstrap init
terraform -chdir=bootstrap plan -out=bootstrap.tfplan
```

Revisar el plan: debe mostrar exactamente **5 create, 0 change, 0 destroy**.

```bash
terraform -chdir=bootstrap apply bootstrap.tfplan
```

Guardar el log sanitizado (sin credenciales).

---

### Paso 4 — Inicializar la raíz con el state remoto

```bash
terraform init -reconfigure \
  -backend-config="bucket=$(terraform -chdir=bootstrap output -raw state_bucket_name)" \
  -backend-config="key=$(terraform -chdir=bootstrap output -raw state_key)" \
  -backend-config="region=$(terraform -chdir=bootstrap output -raw state_region)" \
  -backend-config="encrypt=true" \
  -backend-config="use_lockfile=true"
```

---

### Paso 5 — Configurar SES (acción humana obligatoria)

Antes de generar el plan raíz, definir las variables de SES:

```bash
export TF_VAR_ses_sender_email="remitente@dominio.com"
export TF_VAR_ses_demo_recipient="destinatario@dominio.com"
```

Después de aplicar, confirmar el correo de verificación que SES enviará a ambas direcciones. Si la cuenta SES está en sandbox, verificar también el destinatario o solicitar acceso a producción.

---

### Paso 6 — Generar el plan raíz

```bash
terraform plan \
  -var="ses_sender_email=$TF_VAR_ses_sender_email" \
  -var="ses_demo_recipient=$TF_VAR_ses_demo_recipient" \
  -out=cloudshop.tfplan

terraform show -no-color cloudshop.tfplan
```

**Revisar obligatoriamente:**
- Cuenta y región correctas.
- Sin `destroy` ni `replace` inesperados.
- Costos estimados aceptables (WAF tiene costo fijo).
- Recursos son exclusivos de CloudShop.

No aplicar si aparece destrucción o reemplazo dudoso.

---

### Paso 7 — Aplicar el plan aprobado

```bash
terraform apply cloudshop.tfplan
```

Solo aplicar exactamente el plan revisado. No realizar cambios manuales en AWS antes ni después.

---

### Paso 8 — Bootstrap de usuarios iniciales CLI (Solo usar para desarrollo o demo)

Una vez desplegada la infraestructura es necesario registrar los usuarios de demostración directamente desde la CLI. El flujo es siempre: **primero Cognito, luego DynamoDB**. Nunca crear un registro en DynamoDB sin el usuario Cognito correspondiente.

> Exportar las variables de entorno antes de comenzar para no repetirlas en cada comando:
>
> ```bash
> export USER_POOL_ID=$(terraform output -raw cognito_user_pool_id)
> export USERS_TABLE=$(terraform output -raw users_table_name)
> export AUDIT_TABLE=$(terraform output -raw audit_table_name)
> export AWS_REGION=$(terraform output -raw aws_region)
> ```

---

#### 8a — Crear usuario CLIENTE desde la CLI

**Crear el usuario en Cognito**

```bash
aws cognito-idp admin-create-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "cliente@dominio.com" \
  --user-attributes \
      Name=email,Value="cliente@dominio.com" \
      Name=email_verified,Value=true \
  --message-action SUPPRESS \
  --region "$AWS_REGION"
```

`SUPPRESS` evita que Cognito envíe el correo de bienvenida automático.

**Establecer contraseña permanente**

```bash
aws cognito-idp admin-set-user-password \
  --user-pool-id "$USER_POOL_ID" \
  --username "cliente@dominio.com" \
  --password "ClSh0p-Temp#2026" \
  --permanent \
  --region "$AWS_REGION"
```

La contraseña debe cumplir la política del User Pool (mayúsculas, minúsculas, número, símbolo, mínimo 8 caracteres). `--permanent` evita el flujo de cambio de contraseña en el primer login.

**Asignar el grupo CLIENTE en Cognito**

```bash
aws cognito-idp admin-add-user-to-group \
  --user-pool-id "$USER_POOL_ID" \
  --username "cliente@dominio.com" \
  --group-name CLIENTE \
  --region "$AWS_REGION"
```

**Verificar estado y obtener el `sub` (userId)**

```bash
aws cognito-idp admin-get-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "cliente@dominio.com" \
  --region "$AWS_REGION"
```

Confirmar que `UserStatus` sea `CONFIRMED` y `Enabled` sea `true`. Guardar el `sub`:

```bash
export CLIENTE_USER_ID=$(aws cognito-idp admin-get-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "cliente@dominio.com" \
  --region "$AWS_REGION" \
  --query "UserAttributes[?Name=='sub'].Value" \
  --output text)

echo "userId del CLIENTE: $CLIENTE_USER_ID"
```

**Registrar el perfil en DynamoDB**

```bash
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

aws dynamodb put-item \
  --table-name "$USERS_TABLE" \
  --item "{
    \"userId\":    {\"S\": \"$CLIENTE_USER_ID\"},
    \"email\":     {\"S\": \"cliente@dominio.com\"},
    \"username\":  {\"S\": \"cliente@dominio.com\"},
    \"role\":      {\"S\": \"CLIENTE\"},
    \"status\":    {\"S\": \"ACTIVE\"},
    \"createdAt\": {\"S\": \"$TIMESTAMP\"},
    \"updatedAt\": {\"S\": \"$TIMESTAMP\"}
  }" \
  --condition-expression "attribute_not_exists(userId)" \
  --region "$AWS_REGION"
```

`attribute_not_exists(userId)` evita sobrescribir un registro existente.

**Registrar la auditoría de creación**

```bash
AUDIT_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
CORRELATION_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
CALLER_ARN=$(aws sts get-caller-identity --query Arn --output text)

aws dynamodb put-item \
  --table-name "$AUDIT_TABLE" \
  --item "{
    \"auditId\":       {\"S\": \"$AUDIT_ID\"},
    \"actorId\":       {\"S\": \"$CALLER_ARN\"},
    \"action\":        {\"S\": \"CREATE_USER\"},
    \"resourceType\":  {\"S\": \"USER\"},
    \"resourceId\":    {\"S\": \"$CLIENTE_USER_ID\"},
    \"resourceKey\":   {\"S\": \"USER#$CLIENTE_USER_ID\"},
    \"occurredAt\":    {\"S\": \"$TIMESTAMP\"},
    \"result\":        {\"S\": \"EXITOSO\"},
    \"correlationId\": {\"S\": \"$CORRELATION_ID\"}
  }" \
  --region "$AWS_REGION"
```

**Verificar el registro completo**

```bash
aws dynamodb get-item \
  --table-name "$USERS_TABLE" \
  --key "{\"userId\": {\"S\": \"$CLIENTE_USER_ID\"}}" \
  --consistent-read \
  --region "$AWS_REGION"
```

Confirmar que `role` es `CLIENTE` y `status` es `ACTIVE`.

---

#### 8b — Crear y promover el primer ADMINISTRADOR desde la CLI

El usuario administrador **debe existir primero como CLIENTE** en Cognito y DynamoDB. Repetir los pasos 1 al 7 del apartado anterior con el correo del administrador, luego ejecutar los siguientes pasos de promoción.

```bash
export ADMIN_USER_ID=$(aws cognito-idp admin-get-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "admin@dominio.com" \
  --region "$AWS_REGION" \
  --query "UserAttributes[?Name=='sub'].Value" \
  --output text)

echo "userId del futuro ADMINISTRADOR: $ADMIN_USER_ID"
```

**Agregar el grupo ADMINISTRADOR en Cognito**

```bash
aws cognito-idp admin-add-user-to-group \
  --user-pool-id "$USER_POOL_ID" \
  --username "admin@dominio.com" \
  --group-name ADMINISTRADOR \
  --region "$AWS_REGION"
```

**Quitar el grupo CLIENTE en Cognito**

```bash
aws cognito-idp admin-remove-user-from-group \
  --user-pool-id "$USER_POOL_ID" \
  --username "admin@dominio.com" \
  --group-name CLIENTE \
  --region "$AWS_REGION"
```

**Verificar los grupos actuales**

```bash
aws cognito-idp admin-list-groups-for-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "admin@dominio.com" \
  --region "$AWS_REGION"
```

El resultado debe mostrar únicamente el grupo `ADMINISTRADOR`.

**Actualizar el rol en DynamoDB**

```bash
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

aws dynamodb update-item \
  --table-name "$USERS_TABLE" \
  --key "{\"userId\": {\"S\": \"$ADMIN_USER_ID\"}}" \
  --update-expression "SET #role = :admin, updatedAt = :ts" \
  --condition-expression "#role = :cliente AND #status = :active" \
  --expression-attribute-names '{"#role":"role","#status":"status"}' \
  --expression-attribute-values "{\
    \":admin\":   {\"S\": \"ADMINISTRADOR\"},\
    \":cliente\": {\"S\": \"CLIENTE\"},\
    \":active\":  {\"S\": \"ACTIVE\"},\
    \":ts\":      {\"S\": \"$TIMESTAMP\"}\
  }" \
  --region "$AWS_REGION"
```

Si falla con `ConditionalCheckFailedException`, el usuario no estaba como `CLIENTE ACTIVE` en DynamoDB. Revisar el estado antes de continuar.

**Registrar la auditoría de promoción**

```bash
AUDIT_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
CORRELATION_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
CALLER_ARN=$(aws sts get-caller-identity --query Arn --output text)

aws dynamodb put-item \
  --table-name "$AUDIT_TABLE" \
  --item "{
    \"auditId\":       {\"S\": \"$AUDIT_ID\"},
    \"actorId\":       {\"S\": \"$CALLER_ARN\"},
    \"action\":        {\"S\": \"BOOTSTRAP_ADMIN_ROLE\"},
    \"resourceType\":  {\"S\": \"USER\"},
    \"resourceId\":    {\"S\": \"$ADMIN_USER_ID\"},
    \"resourceKey\":   {\"S\": \"USER#$ADMIN_USER_ID\"},
    \"occurredAt\":    {\"S\": \"$TIMESTAMP\"},
    \"result\":        {\"S\": \"EXITOSO\"},
    \"correlationId\": {\"S\": \"$CORRELATION_ID\"}
  }" \
  --region "$AWS_REGION"
```

**Verificar el estado final del administrador**

```bash
# Confirmar rol en DynamoDB
aws dynamodb get-item \
  --table-name "$USERS_TABLE" \
  --key "{\"userId\": {\"S\": \"$ADMIN_USER_ID\"}}" \
  --consistent-read \
  --region "$AWS_REGION"

# Confirmar grupo en Cognito
aws cognito-idp admin-list-groups-for-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "admin@dominio.com" \
  --region "$AWS_REGION"
```

Ambas verificaciones deben mostrar `ADMINISTRADOR`. Los roles posteriores se asignan desde la propia aplicación con el endpoint `PATCH /usuarios/{id}/rol`.

> **Alternativa automatizada:** los scripts `scripts/bootstrap_cliente.py` y `scripts/bootstrap_admin.py` ejecutan todos los pasos anteriores con compensación automática y verificaciones de idempotencia.

---

### Paso 9 — Smoke tests y validación post-despliegue

```bash
# Verificar outputs
terraform output

# Verificar que no haya drift
terraform plan \
  -var="ses_sender_email=$TF_VAR_ses_sender_email" \
  -var="ses_demo_recipient=$TF_VAR_ses_demo_recipient"
# Resultado esperado: 0 to add, 0 to change, 0 to destroy
```

Ejecutar los casos de prueba obligatorios:

| ID | Prueba |
|---|---|
| **TST-01** | Con un rol sin permiso, verificar que `DELETE /productos/{id}` retorna `403 Forbidden` con SigV4 real. |
| **TST-02** | Crear un pedido completo: stock decrementado, outbox publicado, evento EventBridge, correo SES con `MessageId` y `correlationId` común en todos los registros. |
| **TST-03** | En CloudWatch: visualizar Count, 4XX/5XX, latencia, errores Lambda y métricas WAF en el dashboard. |
| **TST-04** | Demostrar bootstrap → `terraform init/plan/apply` → outputs → smoke tests → plan posterior sin cambios. |

---

### Paso 10 — Capturar evidencia

Registrar y conservar (sin datos sensibles ni credenciales):

- Resumen de cada plan y apply (create/change/destroy + exit code).
- Outputs no sensibles y URL de CloudFront.
- ARN STS asumido por cada rol y grupo Cognito.
- Respuestas HTTP 200 y 403 con `X-Correlation-Id`.
- Items de pedido, inventario, auditoría, outbox e idempotencia (sanitizados).
- Evento EventBridge, retry/DLQ controlada y `MessageId` SES.
- Dashboard CloudWatch con series visibles.
- Web ACL asociado al ARN del stage de API Gateway.
- `terraform plan` final con 0 cambios.

---

### Rollback y limpieza

- **No usar `terraform destroy`** como mecanismo de rollback rutinario.
- Ante fallo de `apply`, detenerse, inspeccionar state/drift y corregir Terraform. No reparar recursos manualmente.
- El frontend puede restaurarse con un nuevo `plan`/`apply` desde un commit aprobado; registrar invalidación CloudFront si corresponde.
- Cualquier limpieza requiere plan revisado, 0 destrucciones fuera de CloudShop y autorización del equipo.
- Conservar state remoto versionado, logs y planes sanitizados.

---

## 13. Variables de Terraform

| Variable | Tipo | Default | Descripción |
|---|---|---|---|
| `project_name` | string | `cloudshop` | Prefijo de todos los recursos |
| `environment` | string | `dev` | `dev`, `test` o `prod` |
| `aws_region` | string | `us-east-1` | Región principal |
| `api_stage_name` | string | `dev` | Stage compartido de API Gateway |
| `log_retention_days` | number | `30` | Retención de logs CloudWatch |
| `ses_sender_email` | string | `""` | Remitente SES verificado; vacío deshabilita envío |
| `ses_demo_recipient` | string | `""` | Destinatario de demo en sandbox SES |
| `waf_rate_limit` | number | `500` | Máx. solicitudes por IP en ventana de 5 minutos |

---

## 14. Outputs

| Output | Descripción |
|---|---|
| `frontend_url` | URL HTTPS de CloudFront |
| `cloudshop_api_url` | URL base de la API (invoke URL del stage) |
| `cognito_user_pool_id` | User Pool ID para el frontend |
| `cognito_user_pool_client_id` | App client público (sin secret) |
| `cognito_identity_pool_id` | Identity Pool para credenciales STS |
| `users_table_name` | Tabla de usuarios |
| `audit_table_name` | Tabla central de auditoría |
| `orders_table_name` | Tabla de pedidos |
| `event_bus_name` | Bus de EventBridge |
| `event_dlq_url` | DLQ de notificaciones agotadas |
| `relay_failure_dlq_url` | DLQ de registros de Streams agotados |
| `cloudwatch_dashboard_name` | Dashboard operativo |
| `waf_web_acl_arn` | ARN del Web ACL regional |
| `frontend_bucket_name` | Bucket privado S3 del frontend |
| `frontend_distribution_id` | ID de distribución CloudFront |

---

## 15. Archivos prohibidos en repositorio

Nunca confirmar ni subir:

- Credenciales, access keys, tokens, cookies o private keys.
- `.env`, `.env.*`, archivos `credentials` o perfiles AWS.
- `*.tfstate`, `*.tfstate.*`, `*.tfplan` o planes con datos sensibles.
- Directorios `.terraform/`.
- `node_modules/`, `dist/`, `build/`, caches o `__pycache__/`.
- ZIPs de Lambda generados, logs sin sanitizar o exports con datos personales.

Antes de cada commit:

```bash
git status --short
git diff --staged
```

---

## 16. Decisiones de arquitectura

### ADR-001 — Autenticación y frontend

**Decisión:** Cognito User Pool + Identity Pool + SigV4 sobre `AWS_IAM` (en lugar de JWT authorizer o Lambda authorizer).

**Justificación:**
- Reutiliza el modelo `AWS_IAM` ya implementado en el módulo de Productos.
- API Gateway rechaza con 403 antes de invocar Lambda cuando el rol no tiene `execute-api:Invoke`.
- Credenciales temporales STS sin secretos en la SPA.
- Evidencia clara de rol asumido y policy efectiva para la rúbrica.
- Mínimo privilegio expresado en ARN de método/path.

**Criterio de reversión:** si el entorno del curso prohíbe Identity Pools o no puede demostrarse el spike real, se adopta Cognito User Pool Authorizer con bearer tokens (opción 2).

---

## 17. Limitaciones conocidas

| Limitación | Impacto | Alcance |
|---|---|---|
| No hay despliegue AWS verificado | TST-01..04 son PARTIAL/BLOCKED | Requiere aplicar infraestructura |
| Reportes usan `Scan` paginado | No escala a grandes volúmenes | Adecuado para dataset académico |
| CORS usa `Access-Control-Allow-Origin: *` | Aceptable sin cookies; dominio definitivo debe fijar origen exacto | Producción con dominio propio |
| Un fallo post-`SendEmail` puede duplicar correo | Semántica al-menos-una-vez documentada | El `subject` incluye número de pedido |
| SES requiere identidades verificadas manualmente | Sin identidad SES, el consumidor registra `skipped_unconfigured` | Acción humana obligatoria post-deploy |
| Tabla `ProductAudit` heredada | Redundancia de auditoría en Productos | Compatibilidad con módulo anterior |
| Primer ADMINISTRADOR requiere bootstrap manual | No puede crearse desde la app antes del bootstrap | Script `scripts/bootstrap_admin.py` |

---

*Infraestructura gestionada con Terraform — CloudShop Enterprise © 2026*
