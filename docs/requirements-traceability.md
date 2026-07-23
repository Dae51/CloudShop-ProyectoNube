# Matriz de trazabilidad de requisitos

Estados permitidos: PASS, PARTIAL, FAIL, BLOCKED, NOT VERIFIED. Esta fotografía
corresponde a Phase 0; PASS exige evidencia reproducible proporcional al requisito.

| ID | Requisito | Implementación encontrada | Evidencia | Estado | Brecha | Prueba necesaria |
|---|---|---|---|---|---|---|
| PLAT-01 | S3 frontend | Ninguna | Sin `aws_s3_bucket` | FAIL | Hosting ausente | Build y acceso vía CloudFront |
| PLAT-02 | CloudFront | Ninguna | Sin distribución | FAIL | CDN ausente | URL y headers |
| PLAT-03 | IAM | Roles/policies Lambda y Productos | Terraform módulos | PARTIAL | Cobertura incompleta | Plan + policy simulation |
| PLAT-04 | IAM Roles | 2 roles Lambda | `Usuarios/main.tf`, `Productos/main.tf` | PARTIAL | Sin roles de usuarios | STS por rol |
| PLAT-05 | IAM Policies | 5 policies | Terraform | PARTIAL | Dominios faltantes | Análisis mínimo privilegio |
| PLAT-06 | WAF | Ninguna | Sin `aws_wafv2_web_acl` | FAIL | WAF ausente | Asociación real |
| PLAT-07 | API Gateway | Una REST API, 8 rutas | `api_gateway.tf` | PARTIAL | API incompleta | Smoke por ruta |
| PLAT-08 | Múltiples Lambda | 2 Lambdas | Terraform | PARTIAL | Servicios vacíos | Invocaciones reales |
| PLAT-09 | Múltiples DynamoDB | 3 tablas | Terraform | PARTIAL | Esquema incompleto | CRUD/consistencia AWS |
| PLAT-10 | EventBridge | Ninguna | Búsqueda Terraform | FAIL | Eventos ausentes | Evento y targets |
| PLAT-11 | CloudWatch | 2 log groups | Terraform | PARTIAL | Sin métricas/dashboard | Dashboard real |
| PLAT-12 | SES | Ninguna | Búsqueda Terraform | FAIL | Correo ausente | MessageId real |
| PLAT-13 | Terraform único | Recursos existentes en Terraform | `.tf` raíz/módulos | PARTIAL | Plataforma incompleta/backend roto | Plan/apply completo |
| USR-01 | Registrar usuarios | Cognito post-confirmation fuerza CLIENTE y audita | `test_post_confirmation.py` PASS | PARTIAL | Falta spike AWS | Registro CLIENTE + auditoría real |
| USR-02 | Consultar usuarios | Lista admin y perfil propio protegidos | `test_users.py` PASS | PARTIAL | Falta integración AWS | Admin 200, otros 403 |
| USR-03 | Actualizar usuarios | Nombre propio/admin con transacción | `test_users.py` PASS | PARTIAL | Falta integración AWS | PUT firmado |
| USR-04 | Desactivar usuarios | Admin, Cognito disable y compensación | Handler/contrato | PARTIAL | Falta prueba AWS | Soft delete real |
| USR-05 | ADMINISTRADOR | Alias en Productos | `ROLE_ALIASES` | PARTIAL | Sin identidad/rol asumible | Login y policy |
| USR-06 | OPERADOR | Alias en Productos | `ROLE_ALIASES` | PARTIAL | Sin identidad/rol asumible | Login y policy |
| USR-07 | CLIENTE | Alias en Productos | `ROLE_ALIASES` | PARTIAL | Sin default de registro | Registro y login |
| PRD-01 | Crear producto | Handler + transacción | Productos Lambda/test | PARTIAL | Sin integración AWS | POST firmado |
| PRD-02 | Actualizar producto | Handler + transacción | Productos Lambda | PARTIAL | Sin integración AWS | PUT firmado |
| PRD-03 | Eliminar producto | Soft delete + auditoría | Test unitario | PARTIAL | Sin TST-01 AWS | DELETE admin/no admin |
| PRD-04 | Consultar productos | Lista/detalle/tienda | Productos Lambda | PARTIAL | Paginación/frontend | GET firmado |
| PRD-05 | Campo código | Validado | `validate_product` | PARTIAL | Sin contrato AWS | Schema + persistencia |
| PRD-06 | Campo nombre | Validado | `validate_product` | PARTIAL | Sin contrato AWS | Schema + persistencia |
| PRD-07 | Campo descripción | Validado | `validate_product` | PARTIAL | Sin contrato AWS | Schema + persistencia |
| PRD-08 | Campo categoría | Validado | `validate_product` | PARTIAL | Sin contrato AWS | Schema + persistencia |
| PRD-09 | Campo precio | Decimal positivo | `parse_price` | PARTIAL | Sin límites de negocio | Casos frontera |
| PRD-10 | Inventario disponible | Entero >= 0 | `parse_inventory` | PARTIAL | Sin checkout concurrente | Concurrencia |
| PRD-11 | Tienda propietaria | `storeId` obligatorio + GSI | Tabla Products | PARTIAL | No valida tienda activa | FK lógica |
| STR-01 | Crear tienda | Ninguna | Archivo vacío | FAIL | Módulo ausente | POST admin |
| STR-02 | Actualizar tienda | Ninguna | Archivo vacío | FAIL | Módulo ausente | PUT admin |
| STR-03 | Consultar tienda | Solo productos por storeId | Productos | FAIL | Tienda no existe | GET autenticado |
| STR-04 | Desactivar tienda | Ninguna | Archivo vacío | FAIL | Módulo ausente | DELETE lógico |
| STR-05 | Tienda posee productos | GSI por `storeId` | Products GSI | PARTIAL | Sin entidad tienda | Consulta relación |
| CRT-01 | Agregar productos | Ninguna | Archivo Compras vacío | FAIL | Carrito ausente | POST item |
| CRT-02 | Modificar cantidades | Ninguna | Archivo Compras vacío | FAIL | Carrito ausente | PATCH item |
| CRT-03 | Eliminar productos | Ninguna | Archivo Compras vacío | FAIL | Carrito ausente | DELETE item |
| CRT-04 | Vaciar carrito | Ninguna | Archivo Compras vacío | FAIL | Carrito ausente | DELETE carrito |
| ORD-01 | Crear pedido | Ninguna | Archivo Pedidos vacío | FAIL | Pedidos ausentes | Checkout E2E |
| ORD-02 | Consultar pedido | Ninguna | Archivo Pedidos vacío | FAIL | Pedidos ausentes | Propiedad/roles |
| ORD-03 | Actualizar estado | Ninguna | Archivo Pedidos vacío | FAIL | Máquina ausente | Transiciones |
| ORD-04 | Cancelar pedido | Ninguna | Archivo Pedidos vacío | FAIL | Compensación ausente | Cancelación |
| ORD-05 | PENDIENTE | Ninguna | Sin constantes | FAIL | Estado ausente | State machine |
| ORD-06 | CONFIRMADO | Ninguna | Sin constantes | FAIL | Estado ausente | State machine |
| ORD-07 | EN_PREPARACION | Ninguna | Sin constantes | FAIL | Estado ausente | State machine |
| ORD-08 | ENVIADO | Ninguna | Sin constantes | FAIL | Estado ausente | State machine |
| ORD-09 | ENTREGADO | Ninguna | Sin constantes | FAIL | Estado ausente | State machine |
| ORD-10 | CANCELADO | Ninguna | Sin constantes | FAIL | Estado ausente | State machine |
| DSH-01 | Total ventas | Ninguna | Sin Reportes | FAIL | Métrica ausente | Datos reales |
| DSH-02 | Ventas por tienda | Ninguna | Sin Reportes | FAIL | Métrica ausente | Datos reales |
| DSH-03 | Más vendidos | Ninguna | Sin Reportes | FAIL | Métrica ausente | Datos reales |
| DSH-04 | Agotados | Ninguna | Sin Reportes | FAIL | Métrica ausente | Datos reales |
| DSH-05 | Mejores clientes | Ninguna | Sin Reportes | FAIL | Métrica ausente | Datos reales |
| DSH-06 | Pedidos por estado | Ninguna | Sin Reportes | FAIL | Métrica ausente | Datos reales |
| SEC-01 | Autenticación por endpoint | Usuarios y Productos usan AWS_IAM; Cognito/Identity Pool declarados | Terraform validate PASS | PARTIAL | Dominios y spike AWS faltan | No auth rechazado |
| SEC-02 | Validación de rol | Productos revalida | `get_identity` | PARTIAL | Usuarios/dominios faltan | Matriz por rol |
| SEC-03 | Validación de permiso | Set por rol en Productos | `PERMISSIONS` | PARTIAL | Cobertura parcial | Negativos por acción |
| SEC-04 | Admin gestiona/reporta | Solo Productos | Policies Productos | PARTIAL | Usuarios/tiendas/reportes | Suite admin |
| SEC-05 | Operador inventario/pedidos | Inventario solamente | Policy/handler | PARTIAL | Pedidos ausentes | Suite operador |
| SEC-06 | Cliente compra/pedidos propios | Consulta productos solamente | Policy Productos | FAIL | Compra/propiedad ausentes | Dos clientes |
| SEC-07 | DELETE producto 403 no autorizado | Unitario a Operador | 8 tests PASS | PARTIAL | Falta API Gateway real | TST-01 AWS |
| SEC-08 | IAM mínimo privilegio | Policies de Productos acotadas | Terraform | PARTIAL | Sistema incompleto/sin simulación | IAM Access Analyzer |
| EVT-01 | Pedido produce evento | Ninguna | Sin EventBridge | FAIL | Evento ausente | Evento trazable |
| EVT-02 | Inventario no negativo | Solo setter >= 0 | Productos | FAIL | No checkout atómico | Stock concurrente |
| EVT-03 | Flujo registra auditoría | Solo mutaciones Productos | ProductAudit | FAIL | Pedido ausente | Correlation común |
| EVT-04 | Flujo envía correo | Ninguna | Sin SES | FAIL | Consumidor ausente | SES MessageId |
| EVT-05 | Idempotencia | Condición optimistic lock Producto | TransactWrite | PARTIAL | Sin order/event idempotency | Duplicados |
| AUD-01 | Creación usuarios | Post-confirmation transaccional | Test unitario PASS | PARTIAL | Falta evidencia AWS | Registro real |
| AUD-02 | Eliminación productos | Sí local | Test PASS | PARTIAL | Sin evidencia AWS/correlation | Registro AWS |
| AUD-03 | Creación pedidos | Ninguna | Sin Pedidos | FAIL | Auditoría ausente | Checkout |
| AUD-04 | Cancelación pedidos | Ninguna | Sin Pedidos | FAIL | Auditoría ausente | Cancelación |
| AUD-05 | Inventario | Sí local | Test PASS | PARTIAL | Sin evidencia AWS/correlation | Update/checkout |
| AUD-06 | Actor, acción, fecha, resultado, correlación | Todos menos correlación | `build_audit` | PARTIAL | Falta correlationId | Schema/test |
| MON-01 | Logs Lambda estructurados | Productos JSON; Usuarios no | `log_event` | PARTIAL | Cobertura/correlación | Logs Insights |
| MON-02 | Métricas API Gateway | Ninguna explícita | Stage sin settings | FAIL | Métricas/logs ausentes | CloudWatch |
| MON-03 | Errores auth visibles | Log Lambda solo si invocada | Productos | PARTIAL | 4XX Gateway no instrumentado | Métrica 4XX |
| MON-04 | Errores app visibles | Logs Productos | Handler | PARTIAL | Sin alarmas/UI | Filtro/alarma |
| MON-05 | Latencia promedio | Ninguna | Sin dashboard | FAIL | Widget ausente | Dashboard |
| IAC-01 | Toda infraestructura Terraform | Solo parcial | `.tf` | PARTIAL | Servicios ausentes | Inventario/state |
| IAC-02 | Bucket S3 | Ninguno | Búsqueda | FAIL | Recurso ausente | Plan |
| IAC-03 | CloudFront | Ninguno | Búsqueda | FAIL | Recurso ausente | Plan |
| IAC-04 | WAF | Ninguno | Búsqueda | FAIL | Recurso ausente | Plan/asociación |
| IAC-05 | API Gateway | Sí | `api_gateway.tf` | PARTIAL | Config incompleta | Plan/smoke |
| IAC-06 | Múltiples Lambdas | 2 | módulos | PARTIAL | Flujos faltantes | Plan/invoke |
| IAC-07 | Múltiples tablas | 3 | módulos | PARTIAL | Dominios faltantes | Plan/data |
| IAC-08 | IAM Roles | 2 Lambda | módulos | PARTIAL | Roles usuario/evento | Plan/STS |
| IAC-09 | IAM Policies | 5 | módulos | PARTIAL | Cobertura incompleta | Plan/simulate |
| IAC-10 | EventBridge | Ninguno | Búsqueda | FAIL | Recurso ausente | Plan/evento |
| IAC-11 | CloudWatch | Log groups | módulos | PARTIAL | Dashboard/alarmas | Plan/dashboard |
| IAC-12 | SES | Ninguno | Búsqueda | FAIL | Identidad/config ausente | Plan/MessageId |
| IAC-13 | Variables/outputs sin hardcoding | Proyecto, entorno, región, retención y outputs Cognito parametrizados | Terraform validate PASS | PARTIAL | Backend y módulos restantes | Entorno limpio |
| TST-01 | 403 sin permiso | Lambda unit test | Operador DELETE PASS | PARTIAL | No API real | SigV4 403 |
| TST-02 | Pedido completo | Ninguna | Sin Pedido | FAIL | Flujo completo ausente | E2E AWS |
| TST-03 | Métricas CloudWatch | Ninguna | Sin dashboard | FAIL | Evidencia ausente | Captura + query |
| TST-04 | Terraform completo | Validate parcial; backend no existe | comandos Phase 0 | BLOCKED | Infra/state/entorno | init/plan/apply |
| DEL-01 | Repo Git ordenado | Rama pequeña; un untracked previo | `git status` | PARTIAL | Paquete incompleto | Clon limpio |
| DEL-02 | Terraform completo | Parcial | validate PASS | PARTIAL | Servicios faltantes | Plan completo |
| DEL-03 | Documento técnico | README mínimo | `README.md` | FAIL | Documento ausente | Revisión |
| DEL-04 | Arquitectura | Solo PDF externo conceptual | PDF oficial | FAIL | Arquitectura real ausente | Diagrama/ADR |
| DEL-05 | Diseño APIs | Rutas en README Productos | README módulo | PARTIAL | OpenAPI ausente | Lint contrato |
| DEL-06 | Diseño BD | Documento de tablas, índices, acceso y condiciones | `docs/database-design.md` | PARTIAL | Implementación/AWS incompletos | Revisión contra state |
| DEL-07 | Diseño seguridad | README Productos parcial | README módulo | PARTIAL | Modelo global ausente | Threat review |
| DEL-08 | Evidencia despliegue | Ninguna; backend inexistente | AWS read-only | BLOCKED | Sin apply seguro | TST-04 |
| DEL-09 | Guía exposición | Ninguna | Búsqueda repo | FAIL | Guía ausente | Ensayo técnico |

## Resumen Phase 0

| Estado | Cantidad |
|---|---:|
| PASS | 0 |
| PARTIAL | 56 |
| FAIL | 48 |
| BLOCKED | 2 |
| NOT VERIFIED | 0 |
| Total | 106 |

> El conteo se recalculará automáticamente o manualmente en cada gate. Un requisito no
> cambia a PASS por compilar, por existir en Terraform o por usar mocks.
