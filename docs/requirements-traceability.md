# Matriz de trazabilidad de requisitos

Estados permitidos: PASS, PARTIAL, FAIL, BLOCKED, NOT VERIFIED. Corte actual:
2026-07-24. PASS exige evidencia reproducible proporcional al requisito; un recurso
solo planificado permanece PARTIAL.

| ID | Requisito | Implementación encontrada | Evidencia | Estado | Brecha | Prueba necesaria |
|---|---|---|---|---|---|---|
| PLAT-01 | S3 frontend | Bucket privado, cifrado y versionado | `Modulos/Frontend/main.tf`; plan estático | PARTIAL | Falta bucket real | Acceso solo CloudFront |
| PLAT-02 | CloudFront | Distribución OAC, TLS, caché y headers | módulo Frontend; build PASS | PARTIAL | Falta URL real | URL y headers |
| PLAT-03 | IAM | Roles/policies por Lambda y usuario | Terraform validate + secret scan | PARTIAL | Falta AWS/Analyzer | Plan remoto + simulation |
| PLAT-04 | IAM Roles | 3 roles de identidad + 9 de Lambda | módulos Terraform | PARTIAL | Falta STS real | ARN asumido por rol |
| PLAT-05 | IAM Policies | Policies de ejecución e invocación acotadas | sin `Action/Resource="*"` | PARTIAL | Falta simulación AWS | Access Analyzer |
| PLAT-06 | WAF | Web ACL regional y asociación al stage | `observability.tf`; validate PASS | PARTIAL | Falta asociación real | GetWebACLForResource |
| PLAT-07 | API Gateway | REST regional con 34 operaciones | OpenAPI/route hashes | PARTIAL | Falta smoke AWS | Smoke por ruta |
| PLAT-08 | Múltiples Lambda | 9 Lambdas declaradas | plan estático/outputs | PARTIAL | Sin invocación real | Logs/invoke |
| PLAT-09 | Múltiples DynamoDB | 9 tablas declaradas | plan estático/diseño BD | PARTIAL | Sin persistencia AWS | CRUD/consistencia AWS |
| PLAT-10 | EventBridge | Bus, outbox relay, regla, retry y DLQ declarados | Terraform validate PASS | PARTIAL | Falta evidencia AWS | Evento y targets reales |
| PLAT-11 | CloudWatch | Logs, filtros, métricas, dashboard y alarmas | `observability.tf`; validate PASS | PARTIAL | Falta series AWS | Dashboard real |
| PLAT-12 | SES | Configuration Set, identidad opcional y consumidor idempotente | `test_order_events.py` PASS | PARTIAL | Identidad/destinatario y MessageId AWS | MessageId real |
| PLAT-13 | Terraform único | Stack + bootstrap de state declarados | validate; planes históricos 5/0/0 y 367/0/0 | PARTIAL | Falta backend/apply remoto | Plan/apply completo |
| USR-01 | Registrar usuarios | Cognito post-confirmation fuerza CLIENTE y audita | `test_post_confirmation.py` PASS | PARTIAL | Falta spike AWS | Registro CLIENTE + auditoría real |
| USR-02 | Consultar usuarios | Lista admin y perfil propio protegidos | `test_users.py` PASS | PARTIAL | Falta integración AWS | Admin 200, otros 403 |
| USR-03 | Actualizar usuarios | Nombre propio/admin con transacción | `test_users.py` PASS | PARTIAL | Falta integración AWS | PUT firmado |
| USR-04 | Desactivar usuarios | Admin, Cognito disable y compensación | Handler/contrato | PARTIAL | Falta prueba AWS | Soft delete real |
| USR-05 | ADMINISTRADOR | Grupo, role IAM, flujo protegido y bootstrap único | script compila + runbook | PARTIAL | Falta ejecución AWS | Bootstrap/login/policy |
| USR-06 | OPERADOR | Grupo, role IAM y UI operativa | Terraform/frontend/tests | PARTIAL | Falta identidad AWS | Login y policy |
| USR-07 | CLIENTE | Registro default, role IAM y UI | post-confirmation test PASS | PARTIAL | Falta registro AWS | Registro y login |
| PRD-01 | Crear producto | Handler + transacción | Productos Lambda/test | PARTIAL | Sin integración AWS | POST firmado |
| PRD-02 | Actualizar producto | Handler + transacción | Productos Lambda | PARTIAL | Sin integración AWS | PUT firmado |
| PRD-03 | Eliminar producto | Soft delete + auditoría | Test unitario | PARTIAL | Sin TST-01 AWS | DELETE admin/no admin |
| PRD-04 | Consultar productos | Lista/detalle/tienda y UI | Lambda/frontend | PARTIAL | Falta GET AWS | GET firmado |
| PRD-05 | Campo código | Validado | `validate_product` | PARTIAL | Sin contrato AWS | Schema + persistencia |
| PRD-06 | Campo nombre | Validado | `validate_product` | PARTIAL | Sin contrato AWS | Schema + persistencia |
| PRD-07 | Campo descripción | Validado | `validate_product` | PARTIAL | Sin contrato AWS | Schema + persistencia |
| PRD-08 | Campo categoría | Validado | `validate_product` | PARTIAL | Sin contrato AWS | Schema + persistencia |
| PRD-09 | Campo precio | Decimal positivo, máximo dos decimales | test frontera PASS | PARTIAL | Falta persistencia AWS | Casos frontera AWS |
| PRD-10 | Inventario disponible | Entero 0..1,000,000 | test frontera PASS | PARTIAL | Sin checkout concurrente AWS | Concurrencia |
| PRD-11 | Tienda propietaria | `storeId`, GSI y validación de tienda ACTIVE | test tienda inactiva PASS | PARTIAL | Falta integración AWS | FK lógica real |
| STR-01 | Crear tienda | Handler ADMINISTRADOR y auditoría transaccional | `test_stores.py` PASS | PARTIAL | Falta POST AWS | POST admin |
| STR-02 | Actualizar tienda | Handler con control optimista | Terraform/handler | PARTIAL | Falta PUT AWS | PUT admin |
| STR-03 | Consultar tienda | Lista/detalle para roles oficiales | `test_stores.py` PASS | PARTIAL | Falta GET AWS | GET autenticado |
| STR-04 | Desactivar tienda | Borrado lógico; checkout exige tienda ACTIVE | tests Stores/Orders PASS | PARTIAL | Falta DELETE/checkout AWS | DELETE lógico |
| STR-05 | Tienda posee productos | Stores + GSI Products por storeId | Terraform validate PASS | PARTIAL | Falta relación AWS | Consulta relación |
| CRT-01 | Agregar productos | Carrito propio valida producto/stock | `test_carts.py` PASS | PARTIAL | Falta POST AWS | POST item |
| CRT-02 | Modificar cantidades | PATCH con optimistic lock | `test_carts.py` PASS | PARTIAL | Falta PATCH AWS | PATCH item |
| CRT-03 | Eliminar productos | DELETE de item propio | `test_carts.py` PASS | PARTIAL | Falta DELETE AWS | DELETE item |
| CRT-04 | Vaciar carrito | DELETE 204 del carrito propio | `test_carts.py` PASS | PARTIAL | Falta DELETE AWS | DELETE carrito |
| ORD-01 | Crear pedido | Checkout transaccional e idempotente | `test_orders.py` PASS | PARTIAL | Falta E2E AWS | Checkout E2E |
| ORD-02 | Consultar pedido | Operador o propietario y lista propia | `test_orders.py` PASS | PARTIAL | Falta AWS | Propiedad/roles |
| ORD-03 | Actualizar estado | Máquina de estados y comando idempotente | `test_orders.py` PASS | PARTIAL | Falta AWS | Transiciones |
| ORD-04 | Cancelar pedido | Compensación atómica exactamente una vez por comando | `test_orders.py` PASS | PARTIAL | Falta concurrencia AWS | Cancelación |
| ORD-05 | PENDIENTE | Estado inicial implementado | Handler/test | PARTIAL | Falta AWS | State machine E2E |
| ORD-06 | CONFIRMADO | Transición permitida | Handler/test | PARTIAL | Falta AWS | State machine E2E |
| ORD-07 | EN_PREPARACION | Transición permitida | Handler/test | PARTIAL | Falta AWS | State machine E2E |
| ORD-08 | ENVIADO | Transición permitida | Handler/test | PARTIAL | Falta AWS | State machine E2E |
| ORD-09 | ENTREGADO | Terminal implementado | Handler/test | PARTIAL | Falta AWS | State machine E2E |
| ORD-10 | CANCELADO | Terminal y compensación implementados | Handler/test | PARTIAL | Falta AWS | State machine E2E |
| DSH-01 | Total ventas | Suma ENTREGADO + contador | Reportes/UI/test PASS | PARTIAL | Falta dato AWS | Datos reales |
| DSH-02 | Ventas por tienda | Agregado por storeId | Reportes/UI/test PASS | PARTIAL | Falta dato AWS | Datos reales |
| DSH-03 | Más vendidos | Top 10 unidades ENTREGADO | Reportes/UI/test PASS | PARTIAL | Falta dato AWS | Datos reales |
| DSH-04 | Agotados | Productos ACTIVE con inventario 0 | Reportes/UI/test PASS | PARTIAL | Falta dato AWS | Datos reales |
| DSH-05 | Mejores clientes | Top por pedidos/gasto ENTREGADO | Reportes/UI/test PASS | PARTIAL | Falta dato AWS | Datos reales |
| DSH-06 | Pedidos por estado | Seis estados, incluye ceros | Reportes/UI/test PASS | PARTIAL | Falta dato AWS | Datos reales |
| SEC-01 | Autenticación por endpoint | 34 operaciones AWS_IAM; OPTIONS excepción | OpenAPI/Terraform validate | PARTIAL | Falta spike AWS | No auth rechazado |
| SEC-02 | Validación de rol | Runtime común + Producto fail-closed | tests matriz/ARN PASS | PARTIAL | Falta roles AWS | Matriz por rol |
| SEC-03 | Validación de permiso | Policies de ruta + guards dominio | tests negativos PASS | PARTIAL | Falta IAM simulation | Negativos por acción |
| SEC-04 | Admin gestiona/reporta | Usuarios, tiendas, productos, dashboard | UI/Lambda/policies | PARTIAL | Falta E2E admin | Suite admin |
| SEC-05 | Operador inventario/pedidos | UI/Lambda/policies completas | tests estados/403 | PARTIAL | Falta E2E operador | Suite operador |
| SEC-06 | Cliente compra/pedidos propios | Ownership validado antes de replay idempotente | regresión dos clientes PASS | PARTIAL | Falta prueba AWS con dos clientes | Dos clientes |
| SEC-07 | DELETE producto 403 no autorizado | Unitario a Operador | 8 tests PASS | PARTIAL | Falta API Gateway real | TST-01 AWS |
| SEC-08 | IAM mínimo privilegio | Acciones/ARN acotados por módulo | source scan + validate | PARTIAL | Sin Analyzer AWS | IAM Access Analyzer |
| EVT-01 | Pedido produce evento | Outbox, relay y DLQ propia de Streams | tests relay + validate PASS | PARTIAL | Falta evento/DLQ AWS | Evento trazable |
| EVT-02 | Inventario no negativo | Update condicional dentro de TransactWriteItems | Tests stock/cancel PASS | PARTIAL | Falta concurrencia AWS | Stock concurrente |
| EVT-03 | Flujo registra auditoría | Pedido/auditoría/outbox/inventario atómicos | `test_orders.py` PASS | PARTIAL | Falta registro AWS | Correlation común |
| EVT-04 | Flujo envía correo | Destinatario propietario; falta SES queda durable | tests consumer PASS | PARTIAL | Sender/destinatario y MessageId AWS | SES MessageId |
| EVT-05 | Idempotencia | Comandos, outbox relay y consumidor usan claves idempotentes | Tests duplicados PASS | PARTIAL | Falta retry/concurrencia AWS | Duplicados reales |
| AUD-01 | Creación usuarios | Post-confirmation transaccional | Test unitario PASS | PARTIAL | Falta evidencia AWS | Registro real |
| AUD-02 | Eliminación productos | Sí local | Test PASS | PARTIAL | Sin evidencia AWS/correlation | Registro AWS |
| AUD-03 | Creación pedidos | Auditoría en transacción de checkout | `test_orders.py` PASS | PARTIAL | Falta DynamoDB AWS | Checkout |
| AUD-04 | Cancelación pedidos | Auditoría y compensación en transacción | `test_orders.py` PASS | PARTIAL | Falta DynamoDB AWS | Cancelación |
| AUD-05 | Inventario | Sí local | Test PASS | PARTIAL | Sin evidencia AWS/correlation | Update/checkout |
| AUD-06 | Actor, acción, fecha, resultado, correlación | Schema común y compatibilidad Productos | handlers/tests | PARTIAL | Falta consulta AWS | Schema/data real |
| MON-01 | Logs Lambda estructurados | JSON y correlation en dominios | runtime/handlers | PARTIAL | Falta Logs Insights | Logs reales |
| MON-02 | Métricas API Gateway | `metrics_enabled` y widget Count/4XX/5XX | observability validate | PARTIAL | Falta series AWS | CloudWatch |
| MON-03 | Errores auth visibles | API 4XX + Gateway Responses 401/403 con CORS/correlation | validate PASS | PARTIAL | Falta evento AWS | Métrica 4XX |
| MON-04 | Errores app visibles | catches 500, filtros, Lambda Errors y alarmas | source + validate PASS | PARTIAL | Falta evento AWS | Filtro/alarma |
| MON-05 | Latencia promedio | Widgets Latency/IntegrationLatency | dashboard Terraform | PARTIAL | Falta serie AWS | Dashboard |
| IAC-01 | Toda infraestructura Terraform | Stack y bootstrap completos | validate; plan aislado histórico | PARTIAL | Falta apply/state y replan | Inventario remoto |
| IAC-02 | Bucket S3 | Frontend + bootstrap declarados | planes estáticos | PARTIAL | Falta AWS | Plan remoto |
| IAC-03 | CloudFront | Distribución OAC declarada | validate/build | PARTIAL | Falta AWS | URL |
| IAC-04 | WAF | Web ACL + asociación stage | validate | PARTIAL | Falta AWS | Asociación |
| IAC-05 | API Gateway | API, stage, 34 operaciones y settings | OpenAPI/validate | PARTIAL | Falta smoke | Plan/smoke |
| IAC-06 | Múltiples Lambdas | 9 funciones | plan estático | PARTIAL | Falta AWS | Plan/invoke |
| IAC-07 | Múltiples tablas | 9 tablas | plan estático | PARTIAL | Falta AWS | Plan/data |
| IAC-08 | IAM Roles | 12 roles | plan estático | PARTIAL | Falta STS | Plan/STS |
| IAC-09 | IAM Policies | 14 managed + inline | plan/source scan | PARTIAL | Falta simulation | Plan/simulate |
| IAC-10 | EventBridge | Bus, regla, target, relay y DLQ | Terraform validate PASS | PARTIAL | Falta plan/apply | Plan/evento |
| IAC-11 | CloudWatch | logs/dashboard/filtros/alarmas | observability.tf | PARTIAL | Falta AWS | Plan/dashboard |
| IAC-12 | SES | Configuration Set e identidad condicional Terraform | Terraform validate PASS | PARTIAL | Email externo no configurado | Plan/MessageId |
| IAC-13 | Variables/outputs sin hardcoding | proyecto/entorno/región/SES/WAF/outputs y backend parcial | validate PASS | PARTIAL | Falta init remoto | Entorno limpio |
| TST-01 | 403 sin permiso | Lambda unit test | Operador DELETE PASS | PARTIAL | No API real | SigV4 403 |
| TST-02 | Pedido completo | Flujo local cubre pedido, stock, outbox, auditoría y consumer | 11 tests de pedido/eventos PASS | PARTIAL | Falta ejecución AWS y MessageId real | E2E AWS |
| TST-03 | Métricas CloudWatch | Dashboard/filtros/alarmas declarados | validate PASS | PARTIAL | Evidencia AWS ausente | Captura + query |
| TST-04 | Terraform completo | validate + planes estáticos | backend 404, no apply | BLOCKED | State/entorno | init/plan/apply |
| DEL-01 | Repo Git ordenado | Commits atómicos; un untracked ajeno preservado | `git log/status` | PARTIAL | Validar clon limpio | Clon limpio |
| DEL-02 | Terraform completo | Stack + bootstrap | validate/planes | PARTIAL | Falta apply | Plan remoto |
| DEL-03 | Documento técnico | Documento y README reproducibles | `docs/technical-document.md` | PASS | Ninguna local | Revisión evaluador |
| DEL-04 | Arquitectura | Diagramas y asociaciones reales | `docs/architecture.md` | PASS | Ninguna local | Revisión evaluador |
| DEL-05 | Diseño APIs | OpenAPI 3.1 + guía | test contrato PASS | PASS | Ninguna local | Lint/revisión |
| DEL-06 | Diseño BD | Tablas, índices, patrones y condiciones | `docs/database-design.md` | PASS | Ninguna local | Revisión |
| DEL-07 | Diseño seguridad | Modelo, matriz, amenazas y controles | `docs/security-design.md` | PASS | Ninguna local | Threat review |
| DEL-08 | Evidencia despliegue | Ninguna; backend inexistente | AWS read-only | BLOCKED | Sin apply seguro | TST-04 |
| DEL-09 | Guía exposición | Guion + banco de preguntas | docs demo/question bank | PASS | Ensayo pendiente | Ensayo técnico |

## Resumen actual

| Estado | Cantidad |
|---|---:|
| PASS | 6 |
| PARTIAL | 98 |
| FAIL | 0 |
| BLOCKED | 2 |
| NOT VERIFIED | 0 |
| Total | 106 |

> Un requisito no cambia a PASS por compilar, por existir en Terraform o por usar
> mocks. Los seis PASS corresponden únicamente a artefactos documentales reproducibles.
