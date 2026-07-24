# Guion de demostración

Duración objetivo: 12–15 minutos. Este guion se ejecuta únicamente después de un
deploy PASS; actualmente los pasos AWS están BLOCKED.

## 1. Apertura (1 minuto)

- Mostrar la matriz y declarar el estado real.
- Explicar ponderaciones: funcionalidad 30%, arquitectura 25%, cloud 15%, calidad 15%,
  documentación 15%.
- Aclarar arquitectura: CloudFront→S3 privado y WAF→API Gateway.

## 2. Infraestructura (2 minutos)

- Mostrar `terraform plan` limpio y outputs no sensibles.
- Abrir CloudFront, API Gateway stage con WAF, Cognito groups/roles, Lambdas y tablas.
- Señalar que todo recurso fue creado por Terraform.

## 3. CLIENTE (3 minutos)

1. Registrar una cuenta; mostrar que no existe selector de rol.
2. Confirmar que queda en grupo CLIENTE.
3. Login, catálogo protegido y producto con stock.
4. Agregar, cambiar cantidad, eliminar y volver a agregar.
5. Checkout y recargar; pedido persiste.
6. Mostrar pedidos propios y que no puede ver otro pedido.

## 4. TST-01 seguridad (2 minutos)

- Con CLIENTE, firmar `DELETE /productos/{id}`.
- Mostrar `403 FORBIDDEN`, correlation ID y 4XX en CloudWatch.
- Explicar doble guard: IAM por ruta + validación Lambda.

## 5. OPERADOR (2 minutos)

- Ajustar inventario.
- Avanzar `PENDIENTE→CONFIRMADO→EN_PREPARACION→ENVIADO→ENTREGADO`.
- Intentar un salto inválido y mostrar `409`.

## 6. ADMINISTRADOR (2 minutos)

- Consultar usuarios y asignar un rol sin auto-modificación.
- Crear/editar/desactivar tienda.
- CRUD de producto.
- Abrir las seis métricas; confirmar que OPERADOR no accede.

## 7. Pedido/evento/correo (2 minutos)

- Seguir el mismo correlation ID en pedido, Audit, Outbox y logs.
- Mostrar stock decrementado y condición que impide negativo.
- Mostrar EventBridge, claim idempotente y SES MessageId.
- Explicar retry y SQS DLQ; repetir evento sin duplicar procesamiento.

## 8. Cierre (1 minuto)

- Abrir dashboard CloudWatch: Count, 4XX/5XX, latencia, Lambda y WAF.
- Mostrar suite PASS y `terraform plan` sin drift.
- Nombrar límites: reportes por Scan para dataset académico y SES sandbox.
