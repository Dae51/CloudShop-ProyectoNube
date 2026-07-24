# Reporte Phase 0

> Este reporte conserva la línea base inicial. No describe el estado final del
> repositorio; consulte `docs/technical-document.md`.

## Estado

**NOT READY FOR SUBMISSION.** La base de Productos tiene buenas validaciones,
transacciones y ocho pruebas, pero el sistema completo no existe todavía. La matriz
inicial registra 0 requisitos obligatorios demostrados end-to-end contra AWS.

## Diferencias frente a la auditoría adjunta

- El checkout actual no contiene `Modulos/Frontend`; las conclusiones específicas de
  `app.js`, `liveApi` y datos demo son NOT VERIFIED.
- No hay 30 endpoints disponibles: hay 8 rutas Terraform, de las cuales 7 son de
  Productos y 1 es un `GET /users` público.
- `AWS_IAM` no protege toda la API: Usuarios usa `NONE`.
- Los roles reales en Productos se normalizan a `ADMINISTRADOR`, `OPERADOR` y
  `CLIENTE`; no existe `EJECUTIVO` en código.
- La ausencia de catálogo público no se toma como falla. El contrato propuesto protege
  catálogo para los tres roles.

## Decisión y plan vertical

ADR-001 selecciona React + Vite, S3/CloudFront y Cognito User Pool + Identity Pool para
firmar SigV4 contra `AWS_IAM`.

1. **Spine seguro:** contratos, OpenAPI, Cognito, roles, errores, correlation ID,
   Usuarios protegido y una ruta Productos.
2. **Spike real:** login, credenciales temporales, GET permitido, DELETE 403 y logs.
3. **Cliente:** registro, catálogo protegido, carrito persistido, checkout y pedidos
   propios.
4. **Pedido confiable:** transacción de pedido/inventario/auditoría/outbox, relay
   EventBridge, SES, idempotencia, retry y DLQ.
5. **Administrador/Operador:** usuarios, tiendas, productos, inventario, estados y seis
   reportes.
6. **Plataforma:** S3, CloudFront, WAF válido, métricas, alarmas, plan y gate de apply.
7. **Evidencia:** pruebas por rol, TST-01..04, auditoría independiente y paquete final.

## Plan de archivos

- `contracts/openapi.yaml`: contrato HTTP.
- `docs/domain-contracts.md`, `docs/database-design.md`: roles, estados, permisos,
  claves, índices y condiciones.
- `Modulos/Autenticacion`: User Pool, Identity Pool, grupos y roles.
- `Modulos/Frontend`: aplicación React/Vite y hosting.
- `Modulos/{Usuarios,Productos,Tiendas,Carritos,Pedidos,Reportes}`: Lambdas, rutas,
  tablas/policies y pruebas.
- `Modulos/Eventos`: outbox relay, EventBridge, SES consumer y DLQ.
- `observability.tf`, `waf.tf`: dashboard, alarmas y Web ACL asociado a CloudFront.
- `tests/`: contratos, seguridad, dominio e integración/smoke.

## Plan de pruebas y evidencia

- Unitarias por handler y máquina de estados.
- Contrato: OpenAPI válido y rutas Terraform alineadas.
- Seguridad: matriz de rutas por rol, identidad/propiedad y 403.
- Concurrencia: stock insuficiente, idempotency key repetida y dos checkouts.
- Eventos: outbox duplicado, fallo temporal, DLQ y correlation ID.
- Frontend: lint, unit tests y build sin mocks de producción.
- Terraform: fmt, validate, tests estáticos, plan JSON y detección de
  create/change/destroy.
- AWS: identidad/rol, HTTP status, items DynamoDB, evento, auditoría, SES MessageId,
  dashboard/métricas y URL CloudFront.

Las evidencias se guardarán sanitizadas en `docs/evidence/` y se referenciarán desde la
matriz. Compilar o usar mocks nunca contará como evidencia AWS.

## Riesgos por severidad

- CRITICAL: endpoint de usuarios público; backend state inexistente; entorno del curso
  no confirmado.
- HIGH: no hay autenticación, frontend, pedidos/eventos/correo ni mayoría de módulos;
  presupuesto WAF e identidad SES ausentes.
- MEDIUM: región implícita, nombres no parametrizados, scans sin paginación, cobertura
  limitada y Cognito sujeto a restricciones docentes no conocidas.
- LOW: documentación/naming bilingüe heredado; se conservarán aliases solo en bordes
  de compatibilidad, no como roles de dominio.

## Decisiones y supuestos

- Roles canónicos: `ADMINISTRADOR`, `OPERADOR`, `CLIENTE`.
- Auto-registro: siempre `CLIENTE`.
- Dashboard: solo `ADMINISTRADOR`.
- Catálogo: autenticado para cumplir literalmente el control global de endpoints.
- Borrado: lógico para usuarios, tiendas y productos.
- Región propuesta: `us-east-1`, porque es la región activa; deberá coincidir con el
  entorno del curso antes de apply.
- WAF protege CloudFront con scope global. API Gateway queda detrás de la SPA y de IAM;
  un segundo WAF regional no se añade sin necesidad/costo aprobado.
- No se aplicará infraestructura mientras fallen backend, cuenta/región/presupuesto o
  SES.

## Preguntas estrictamente bloqueantes

Ninguna para implementación, pruebas locales o documentación. Para apply son
bloqueantes y actualmente no resueltas: cuenta/perfil autorizado del curso, región
acordada, estrategia de state, presupuesto WAF, identidad/remitente SES, destinatario
SES de demo y cualquier restricción docente sobre Cognito.
