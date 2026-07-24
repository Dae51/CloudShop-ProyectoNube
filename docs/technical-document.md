# Documento técnico

## Resultado

CloudShop está implementado y validado localmente, pero **NOT READY FOR SUBMISSION**.
La suite, build, contratos y Terraform pasan; no existe despliegue verificable porque
el backend anterior daba 404 y faltan identidad SES, presupuesto y confirmación del
entorno.

## Solución

La SPA React/Vite se distribuye por CloudFront desde S3 privado. Cognito autentica y
entrega credenciales STS por rol mediante Identity Pool. Un cliente central firma
todos los métodos HTTP con SigV4 y presenta errores/correlation IDs; no hay datos demo.

API Gateway REST usa `AWS_IAM`. Los dominios Usuarios, Productos, Tiendas, Carritos,
Pedidos y Reportes se implementan como Lambdas independientes, con roles de ejecución
y policies acotadas. DynamoDB usa tablas por agregado y operaciones condicionales.

El checkout realiza una única transacción para decrementar stock, crear pedido,
auditoría, outbox e idempotencia y borrar carrito. Streams + EventBridge desacoplan el
correo SES, con retry y DLQ. Esta secuencia es realizable y no supone una barrera de
fan-out.

## Frontend

- Registro, confirmación y login Cognito.
- Registro sin selector de rol; nuevo usuario CLIENTE.
- Guards y navegación por rol.
- CLIENTE: catálogo, carrito persistente, checkout, pedidos propios/cancelación.
- OPERADOR: inventario y máquina de estados.
- ADMINISTRADOR: usuarios/roles, tiendas, productos y seis reportes.
- Estados loading/empty/error/validation visibles.
- Runtime config generado por Terraform y fail-closed si falta.

## Backend y datos

- Usuarios: perfil propio/admin, desactivación Cognito compensada y cambio de grupos.
- Productos: CRUD, inventario, tienda activa y auditoría.
- Tiendas: CRUD lógico con control optimista.
- Carritos: ownership por Identity Pool y versión optimista.
- Pedidos: transacción, estados, cancelación compensada e idempotencia.
- Reportes: scans paginados para dataset académico y solo ADMINISTRADOR.

El diseño de tablas/índices está en [database-design.md](database-design.md).

## Seguridad

La autorización tiene tres capas: rutas/policies IAM, rol/permiso en Lambda y
ownership. WAF se asocia al stage de API; CloudFront usa OAC. Los logs son JSON con
correlation ID y no registran tokens/email. Véase
[security-design.md](security-design.md).

## Observabilidad

- 10 log groups con retención configurable (9 Lambdas + WAF).
- Métricas detalladas del stage.
- Filtros `AuthenticationErrors` y `ApplicationErrors`.
- Dashboard: Count/4XX/5XX, latencia/integración, errores Lambda y WAF.
- Alarmas: 5XX, pico 4XX, latencia y errores de aplicación.
- No se habilitó el rol CloudWatch global de API Gateway porque es configuración de
  cuenta compartida y podría afectar recursos ajenos.

## Infraestructura y reproducibilidad

Terraform declara el bootstrap del state y el stack. El bootstrap produjo un plan de
5 altas, 0 cambios y 0 destrucciones. Una copia temporal con backend local produjo
una fotografía inicial de 367 altas, 0 cambios y 0 destrucciones; no equivale al plan
remoto porque no conoce state/drift.

El WAF añade costo fijo (Web ACL + reglas + requests/logs), por lo que apply requiere
presupuesto explícito. SES necesita identidad/destinatario verificados. Los recursos
no se reparan manualmente.

## Limitaciones conocidas

- No hay URL CloudFront, MessageId SES ni métricas AWS reales.
- No se ejecutaron TST-01..04 contra AWS.
- El primer ADMINISTRADOR necesita bootstrap de confianza por un operador AWS.
- Los reportes por Scan son adecuados para la demo, no para gran volumen.
- Productos conserva una tabla de auditoría heredada además de la auditoría central.
- CORS usa `*` sin cookies; un dominio definitivo debe fijar el origen.

## Evidencia

Los resultados, comandos y distinción local/AWS están en
[test-report.md](test-report.md) y
[deployment-evidence.md](deployment-evidence.md). La matriz completa está en
[requirements-traceability.md](requirements-traceability.md).
