# Auditoría del estado actual

Fecha de corte: 2026-07-23  
Rama: `refactor-shared-api-gateway` (`f5dd4e7`)  
Cuenta AWS observada: `190239490282` (`lab-user`)  
Región efectiva del perfil: `us-east-1`  
Backend declarado: S3 `cloudshop-terraform-esen2026`, key `terraform.tfstate`, región `us-east-2`

## Resultado ejecutivo

**NOT READY FOR SUBMISSION.** El repositorio actual es una implementación parcial de
Usuarios y Productos. No contiene el frontend descrito por la auditoría adjunta ni
implementaciones funcionales de Tiendas, Compras/Carrito o Pedidos. Tampoco declara S3
de frontend, CloudFront, WAF, EventBridge, SES, Cognito ni dashboards de CloudWatch.

Las comprobaciones locales disponibles son sanas pero de alcance limitado:

- `terraform fmt -check -recursive`: PASS.
- `terraform validate -no-color`: PASS con plugins previamente inicializados.
- `python3 -m unittest discover -s Modulos/Productos/tests -v`: PASS, 8/8.
- acceso al backend remoto: FAIL/BLOCKED; el bucket declarado no existe en la cuenta
  activa.
- recursos con tag `Project=CloudShop` en `us-east-1` y `us-east-2`: ninguno encontrado.

## Preservación del estado Git

Al iniciar se encontró `explicacion_modulo_2.txt` sin seguimiento. Es trabajo
preexistente y no se modifica ni se incorpora a commits automáticamente. La rama local
coincidía con `origin/refactor-shared-api-gateway`.

## Inventario real

| Área | Declarado | Evidencia | Estado |
|---|---:|---|---|
| API Gateway REST regional | 1 | `api_gateway.tf` | PARTIAL |
| Rutas desplegables | 8 | 1 de Usuarios + 7 de Productos | PARTIAL |
| Lambda | 2 | Usuarios y Productos | PARTIAL |
| Tablas DynamoDB | 3 | `Users`, `Products`, `ProductAudit` | PARTIAL |
| Roles Lambda | 2 | uno por Lambda | PARTIAL |
| Policies IAM | 5 | 2 de ejecución Lambda + 3 de invocación de Productos | PARTIAL |
| Log groups | 2 | retención de 30 días | PARTIAL |
| Frontend/S3/CloudFront | 0 | no existe `Modulos/Frontend` | FAIL |
| Cognito | 0 | no hay proveedor de identidad | FAIL |
| WAF | 0 | sin recursos `aws_wafv2_*` | FAIL |
| EventBridge/DLQ | 0 | sin recursos | FAIL |
| SES | 0 | sin recursos | FAIL |
| Dashboards/alarmas | 0 | sin recursos | FAIL |

### Endpoints verificables

| Método | Ruta | Autorización en API Gateway | Implementación |
|---|---|---|---|
| GET | `/users` | `NONE` | lista completa con `Scan` |
| POST | `/productos` | `AWS_IAM` | crea y audita |
| GET | `/productos` | `AWS_IAM` | lista |
| GET | `/productos/{productId}` | `AWS_IAM` | consulta |
| PUT | `/productos/{productId}` | `AWS_IAM` | reemplaza campos |
| DELETE | `/productos/{productId}` | `AWS_IAM` | borrado lógico y auditoría |
| PATCH | `/productos/{productId}/inventario` | `AWS_IAM` | actualiza inventario y audita |
| GET | `/tiendas/{storeId}/productos` | `AWS_IAM` | consulta por GSI |

La Lambda de Usuarios contiene ramas `POST`, `PUT` y `DELETE`, pero API Gateway no las
expone. No son endpoints implementados. Los archivos
`Modulos/Tiendas/aws_lambda_function.py`, `Modulos/Compras/aws_lambda_function.py` y
`Modulos/Pedidos/aws_lambda_function.py` tienen cero bytes.

## Verificación de la auditoría de frontend

La auditoría encontrada en `/home/javier/Downloads/cloudshop_frontend_audit.md` apunta
a un checkout distinto (`/home/jportillo/...`) y describe `Modulos/Frontend`, que no
existe en este repositorio, ninguna rama local/remota visible ni otra copia local
encontrada.

| Afirmación previa | Resultado contra este checkout |
|---|---|
| Vanilla JS concentrado en `app.js` | NOT VERIFIED; `app.js` no existe aquí |
| Login simulado y selector de roles | NOT VERIFIED; no hay frontend |
| Sin control real de acceso por rol | PARTIAL; no evaluable en UI, Usuarios es público y Productos sí revalida rol |
| Cliente HTTP solo GET | NOT VERIFIED; no hay cliente HTTP |
| `liveApi: false` y fallback demo | NOT VERIFIED; no existe `config.js.tftpl` |
| 0 de 30 endpoints integrados | La cifra no corresponde al checkout: solo hay 8 rutas desplegables |
| APIs con `AWS_IAM` | PARTIAL; Productos usa `AWS_IAM`, Usuarios usa `NONE` |
| Roles del frontend no coinciden | NOT VERIFIED en UI; backend normaliza alias además de roles oficiales |

La falta de catálogo público no se clasifica como incumplimiento: el PDF exige que los
endpoints validen autenticación, rol y permisos. El dashboard se asignará a
`ADMINISTRADOR`; `EJECUTIVO` queda fuera del modelo.

## Hallazgos priorizados

### CRITICAL

1. `GET /users` usa autorización `NONE` y devuelve la tabla completa. Impacta
   SEC-01..04 y datos personales.
2. No existe identidad real ni mecanismo para entregar credenciales temporales por
   rol. Las policies de Productos no están adjuntas a roles asumibles por usuarios.
3. El backend remoto Terraform no existe. Sin state no se puede demostrar propiedad,
   drift ni aplicar con seguridad.

### HIGH

1. La autorregistración de la Lambda de Usuarios copia `body["role"]`, lo que permitiría
   elegir un rol privilegiado si se expusiera.
2. 25 de los 33 endpoints de contrato propuestos todavía no existen; carrito, pedidos,
   reportes y tiendas no son funcionales.
3. No existe el flujo pedido-inventario-evento-auditoría-correo.
4. No existen frontend, S3, CloudFront, WAF, EventBridge ni SES.
5. Los registros de auditoría de Productos no incluyen correlation ID.

### MEDIUM

1. La región del provider queda implícita (`us-east-1` por perfil) mientras el backend
   fija `us-east-2`; el entorno no es reproducible.
2. Los nombres de recursos son globales/fijos y no incluyen proyecto/entorno.
3. `Scan` sin paginación se usa en Usuarios y Productos.
4. Solo Productos tiene pruebas; no hay OpenAPI, pruebas de contrato, integración ni
   frontend.
5. La policy de Usuarios permite ramas que hoy no están expuestas y la Lambda usa
   nombres de tabla hardcodeados.

## Arquitectura realizable propuesta

1. React + Vite produce archivos estáticos privados en S3.
2. CloudFront usa Origin Access Control para S3. Un Web ACL de scope `CLOUDFRONT`,
   creado mediante provider alias `us-east-1`, se asocia directamente a la
   distribución.
3. Cognito User Pool autentica. El auto-registro no permite escribir roles y un trigger
   post-confirmación asigna exclusivamente `CLIENTE`.
4. Grupos Cognito `ADMINISTRADOR`, `OPERADOR` y `CLIENTE` se asocian a roles IAM
   acotados. Identity Pool selecciona `cognito:preferred_role` y entrega credenciales
   temporales.
5. El cliente central obtiene credenciales y firma cada llamada a API Gateway con
   SigV4. No hay fallback silencioso a datos demo.
6. API Gateway usa `AWS_IAM`; cada Lambda vuelve a validar actor, rol, permiso y
   propiedad del recurso.
7. Checkout ejecuta una transacción DynamoDB que crea pedido, decrementa inventario con
   condiciones, registra auditoría y crea un outbox. Un relay de DynamoDB Streams
   publica en EventBridge. Consumidores idempotentes procesan notificación SES; los
   reintentos agotados llegan a SQS DLQ.
8. Correlation ID viaja desde API Gateway por orden, auditoría, outbox, evento, logs y
   notificación.

Esta secuencia evita fingir que el fan-out de EventBridge es una barrera. Pedido,
inventario, auditoría y outbox son atómicos; correo es posterior y reintentable.

## Riesgos, dependencias y costo

| Riesgo/dependencia | Severidad | Tratamiento |
|---|---|---|
| Backend S3 inexistente | CRITICAL | bootstrap separado y luego migración explícita; nunca crear state manualmente |
| Cuenta/entorno del curso sin confirmar | CRITICAL para apply | bloquear apply hasta coincidencia inequívoca |
| Presupuesto WAF no informado | HIGH para apply | WAF estándar parte de USD 5/mes por Web ACL + USD 1/mes por regla y solicitudes |
| Identidad/destinatario SES no configurados | HIGH para prueba real | variables opcionales; correo real queda BLOCKED hasta verificación |
| Restricción docente sobre Cognito desconocida | MEDIUM | ADR justifica servicio adicional; arquitectura puede cambiar a authorizer |
| Credenciales de usuario IAM de laboratorio | MEDIUM | no ampliar permisos; plan/apply solo tras gate |
| Plazo y división del equipo desconocidos | MEDIUM | entregar slices y guía de exposición reproducible |

Para tráfico académico bajo, Lambda, API Gateway, DynamoDB, S3, CloudFront y Cognito
pueden permanecer cerca de sus capas gratuitas o de pocos dólares según antigüedad y
uso de la cuenta. El costo fijo más visible es WAF: con un Web ACL y tres reglas
simples, el orden base es aproximadamente USD 8/mes más solicitudes y logs. Debe
validarse en AWS Pricing Calculator antes de apply.

Fuentes: [AWS WAF Pricing](https://aws.amazon.com/waf/pricing/),
[Amazon Cognito Pricing](https://aws.amazon.com/cognito/pricing/) y
[CloudFront Pricing](https://aws.amazon.com/cloudfront/pricing/).

## Gates de Phase 0

- Fuentes oficiales y auditoría leídas: PASS.
- Estado Git preservado: PASS.
- Inventario y endpoints verificados: PASS.
- Pruebas locales existentes ejecutadas: PASS.
- Configuración AWS y state identificados: PARTIAL/BLOCKED.
- Matriz, auditoría y ADR creados: PASS.
- Preguntas estrictamente bloqueantes para trabajo local: ninguna.
- Dependencias que bloquean solo despliegue: cuenta/entorno, backend, presupuesto WAF,
  identidad y destinatario SES.

