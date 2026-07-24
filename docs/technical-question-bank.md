# Banco de preguntas técnicas

## Arquitectura

**¿Por qué CloudFront no apunta a WAF después de S3?**
WAF se asocia a un recurso de entrada. En esta solución CloudFront lee S3 mediante OAC
y un Web ACL regional se asocia directamente al stage API Gateway. S3 no reenvía
peticiones a WAF.

**¿Por qué React + Vite si el hosting sigue siendo estático?**
El build son HTML/CSS/JS para S3. React organiza estados, formularios y guards; Vite
produce assets versionados sin servidor permanente.

**¿Por qué `AWS_IAM` en vez de bearer token?**
El backend ya usaba IAM y la opción permite policies por método/ruta y credenciales
temporales. La Lambda todavía controla objeto/ownership.

**¿Qué pasa si un usuario pertenece a dos grupos?**
Los grupos tienen igual precedencia y el Identity Pool usa resolución ambigua `Deny`;
el frontend también exige exactamente un grupo oficial.

## Seguridad

**¿Ocultar un botón autoriza?**
No. Es UX. La policy IAM y la Lambda deciden.

**¿Cómo se evita que el registro cree un admin?**
No se envía rol; post-confirmation fuerza CLIENTE. Cambiar rol requiere endpoint admin
auditado.

**¿Cómo se evita IDOR?**
Carrito deriva `customerId` del contexto firmado. Pedido compara ese ID antes de
consultar/cancelar; el cliente no elige propietario.

**¿Por qué CORS `*` no expone credenciales?**
No se usan cookies cross-origin y las credenciales STS firman cada solicitud. Aun así,
con dominio definitivo se recomienda fijar el origen.

**¿Dónde se guardan tokens?**
La librería Cognito administra sesión; la app no persiste manualmente credenciales STS
ni secretos.

## Pedidos y eventos

**¿Cómo impiden sobreventa?**
`TransactWriteItems` resta inventario con `inventory >= quantity`. Si cualquier item
falla, toda la transacción cancela.

**¿EventBridge sincroniza inventario, auditoría y correo?**
No. Inventario/auditoría/outbox son parte de la transacción. EventBridge procesa el
correo después; no es una barrera.

**¿Qué garantiza idempotencia?**
Claves por scope/operación, token de transacción UUID5, outbox con condición y claim de
consumidor por `eventId`.

**¿Puede duplicarse un correo?**
Sí, en la ventana posterior a SES y anterior a persistir MessageId. El procesamiento
es al-menos-una-vez; se minimiza con claim/estado, no se promete exactly-once externo.

**¿Cómo funciona cancelar?**
Solo PENDIENTE/CONFIRMADO. Una transacción repone items, marca CANCELADO,
`inventoryRestored=true`, audita y publica outbox.

## Datos

**¿Por qué varias tablas?**
Cada agregado tiene patrones/accesos/retención distintos y reduce acoplamiento. Los
pedidos usan GSI por cliente y estado.

**¿Por qué reportes usan Scan?**
Es una decisión académica para volumen pequeño. Producción materializaría agregados
desde eventos para costo/latencia predecible.

**¿DynamoDB tiene foreign keys?**
No. Productos hace lectura consistente de Stores y exige `ACTIVE`; checkout vuelve a
validar productos.

## Operación

**¿Un plan prueba despliegue?**
No. Solo calcula acciones contra un state. El plan aislado sin backend es evidencia
estática, no AWS end-to-end.

**¿Por qué no se aplicó?**
El backend previo no existe, región discrepaba, SES tiene cero identidades y no hay
presupuesto WAF/confirmación del entorno. El gate exige detenerse.

**¿Qué observa CloudWatch?**
Logs JSON/correlation, Count, 4XX, 5XX, latencia, errores Lambda, filtros de
auth/aplicación, WAF y alarmas.

**¿Cuál es el costo más visible?**
WAF tiene costo fijo por Web ACL/reglas además de requests/logs. Los demás servicios
son mayormente por uso, pero deben estimarse para la cuenta concreta.
