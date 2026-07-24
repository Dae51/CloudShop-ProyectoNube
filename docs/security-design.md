# Diseño de seguridad

## Modelo de confianza

El navegador es no confiable. Cognito prueba identidad, STS entrega credenciales
temporales y API Gateway verifica SigV4. Las Lambdas no confían en botones ocultos ni
en IDs enviados por el cliente: derivan actor/rol desde el contexto y aplican
ownership.

Roles canónicos: `ADMINISTRADOR`, `OPERADOR`, `CLIENTE`. `EJECUTIVO` no existe. Un ARN
IAM solo se reconoce si el token final del nombre de rol es oficial; nombres como
`cloudshop-dev-administrador-falso` fallan cerrados. Una sesión con cero o múltiples
grupos oficiales tampoco obtiene un rol válido.

## Matriz de autorización

| Recurso | ADMINISTRADOR | OPERADOR | CLIENTE |
|---|---|---|---|
| Usuarios | listar, editar, desactivar, rol | perfil propio | perfil propio |
| Tiendas | CRUD lógico | lectura | lectura |
| Productos | CRUD + inventario | lectura + inventario | lectura |
| Carrito/checkout | no | no | propio |
| Pedidos | reportes solamente | listar, estado, cancelar | propios; cancelar permitido |
| Reportes | seis métricas | no | no |

Cada rol Cognito recibe policies `execute-api:Invoke` con métodos y paths explícitos.
No se usa `execute-api:*`, `Action="*"` ni `Resource="*"`.

## Registro y roles privilegiados

- El formulario de registro no contiene rol.
- Post-confirmation asigna y persiste `CLIENTE`.
- Cambiar rol requiere `PATCH /usuarios/{userId}/rol`, rol ADMINISTRADOR y auditoría.
- El administrador no puede cambiar su propio rol ni desactivarse.
- El bootstrap inicial se ejecuta una sola vez por un operador AWS autorizado:

```bash
python scripts/bootstrap_admin.py \
  --profile "$AWS_PROFILE" \
  --region "REGION_CONFIRMADA" \
  --expected-account "CUENTA_CONFIRMADA" \
  --user-pool-id "$(terraform output -raw cognito_user_pool_id)" \
  --users-table "$(terraform output -raw users_table_name)" \
  --audit-table "$(terraform output -raw audit_table_name)" \
  --username "USUARIO_COGNITO_CONFIRMADO"
```

El script valida cuenta y estado CLIENTE activo, rechaza un segundo administrador,
sincroniza Cognito/Users, registra `BOOTSTRAP_ADMIN_ROLE` junto al cambio DynamoDB y
compensa los grupos Cognito si falla la transacción. Hasta que exista el despliegue
real, la ejecución de este procedimiento permanece BLOCKED.

## Controles de aplicación

- Validación de cuerpos con listas exactas de campos y límites.
- React escapa texto por defecto; no se usa `dangerouslySetInnerHTML`.
- CSP: scripts/estilos solo del mismo origen; `connect-src` limitado a AWS/Cognito.
- No hay tokens ni credenciales persistidos manualmente en `localStorage`.
- Configuración pública contiene solo IDs/URLs no secretos.
- Errores internos no exponen stack traces; incluyen un correlation ID.
- Logs filtran nombres sensibles como authorization, token, password, secret y email.
- Producto requiere tienda existente y activa.
- Ownership de carrito/pedido deriva de la identidad federada, no del body.

## Protección de infraestructura

- S3 bloquea ACL/policy pública, cifra y versiona.
- CloudFront usa TLS 1.2, OAC, HSTS, CSP, `DENY` framing y no-cache para `config.js`.
- WAF aplica rate limit, Common Rule Set y Known Bad Inputs a API Gateway.
- Headers Authorization y `X-Amz-Security-Token` se redactan de logs WAF.
- DynamoDB cifra y habilita PITR; state S3 añade `prevent_destroy`.
- SES solo se habilita con identidad configurada; sin sender el consumidor registra
  `skipped_unconfigured` y no afirma envío.

## Amenazas y mitigaciones

| Amenaza | Mitigación | Evidencia local | Pendiente AWS |
|---|---|---|---|
| Escalamiento por selector de rol | No existe selector; post-confirmation CLIENTE | tests post-confirmation/frontend | registro real |
| Invocar DELETE sin permiso | Policy por ruta + guard Lambda | tests 403 | TST-01 SigV4 |
| IDOR de pedido | comparación `customerId` | test dos propietarios | dos usuarios reales |
| Sobreventa | transacción y condición de stock | tests stock | concurrencia real |
| Evento/correo duplicado | outbox + claims idempotentes | tests relay/notification | retry AWS |
| XSS | React + CSP | build/revisión | headers CloudFront |
| Credential leakage | temporales, sin secretos en repo/log | secret scan | inspección CloudWatch |
| Abuso HTTP | WAF + throttling | Terraform validate/plan estático | métricas WAF |

## CORS

La SPA y API usan orígenes diferentes, por lo que CORS es necesario. Los preflight
permiten solo headers/métodos usados por SigV4; no se habilitan cookies
cross-origin. `Access-Control-Allow-Origin: *` es aceptable aquí porque no se usan
credenciales de navegador basadas en cookies, pero una distribución con dominio
propio debería fijar el origen exacto.

## Verificación pendiente

IAM Access Analyzer/simulation, ARN STS por rol, 403 previo a Lambda, headers reales,
logs WAF y ausencia de tokens en CloudWatch requieren despliegue. No son PASS.
