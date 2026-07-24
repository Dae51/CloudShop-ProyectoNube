# Handoff universitario — CloudShop Enterprise

Fecha de preparación: 2026-07-24.

## Estado del proyecto

**NOT READY FOR SUBMISSION / listo para handoff de despliegue.**

El repositorio contiene una implementación local completa y auditada, pero no existe
un despliegue AWS atribuible a este checkpoint. Ningún recurso fue creado durante la
preparación de este handoff.

- Checkpoint auditado de entrada: `2301173586b7b87faf9f6815bf0f6aead8b27f69`.
- Fixer de auditoría: `f12413c`.
- Informe vigente: `docs/audit-report.md`.
- Trazabilidad vigente: `docs/requirements-traceability.md`.
- Los requisitos de plataforma y las pruebas AWS permanecen `PARTIAL` o `BLOCKED`
  hasta desplegar y recopilar evidencia real.

## Implementación completada

- React + Vite estático para S3/CloudFront, sin fallback silencioso a datos demo.
- Cognito User Pool + Identity Pool, roles oficiales exactos y solicitudes SigV4.
- Registro siempre `CLIENTE` y bootstrap único/auditado del primer
  `ADMINISTRADOR`.
- APIs Lambda protegidas para usuarios, tiendas, productos, carrito, pedidos y seis
  reportes.
- Pedidos con transacción DynamoDB, control de stock, idempotencia, ownership,
  máquina de estados, cancelación y compensación de inventario.
- Outbox, DynamoDB Streams, EventBridge, consumidor SES, retries y DLQ separadas.
- WAF regional asociado a API Gateway, métricas/alarmas CloudWatch y logs
  estructurados con correlation ID.
- Terraform modular para la plataforma y bootstrap separado del state remoto.
- OpenAPI, ADR, diseños, matriz de requisitos, reporte de pruebas y auditoría.

## Pruebas ya ejecutadas

Resultados registrados antes de este handoff:

| Validación | Resultado |
|---|---|
| Backend global | PASS 44/44 antes del residual final |
| Backend focal tras residual | PASS 16/16 |
| Productos | PASS 12/12 |
| Frontend Vitest | PASS 8/8 |
| Build Vite | PASS, 670 módulos |
| Python compile / diff check / secret scan | PASS |
| `terraform fmt -check -recursive` | PASS |
| `terraform validate -no-color` raíz | PASS |
| `terraform validate` bootstrap | PASS |

Estos resultados son locales. No demuestran IAM, DynamoDB, Streams, EventBridge,
SES, WAF ni CloudWatch reales.

Después de cualquier cambio de código o Terraform relacionado con despliegue se debe
repetir la suite completa, no solamente las pruebas focales:

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s Modulos/Productos/tests -v
(cd Modulos/Frontend/app && npm install && npm test -- --run && npm run build)
terraform fmt -check -recursive
terraform validate -no-color
terraform -chdir=bootstrap validate -no-color
```

## Bloqueos pendientes

- Confirmar cuenta, perfil y región AWS del curso.
- Confirmar presupuesto, especialmente el costo continuo de WAF.
- El backend remoto anterior no existe; el bootstrap no se ha aplicado.
- SES no tiene identidad ni destinatario de demostración verificados.
- No existen URL CloudFront, outputs reales, smoke tests ni evidencias TST-01..04.
- Confirmar restricciones del profesor sobre Cognito y servicios adicionales.

## Secuencia de despliegue AWS

No crear recursos manualmente. Toda infraestructura debe permanecer en Terraform.

1. Confirmar identidad, región, presupuesto y propiedad del entorno.
2. Ejecutar nuevamente format, validate, pruebas completas y secret scan.
3. Generar un plan nuevo del módulo `bootstrap/`; revisar que solo cree el bucket de
   state exclusivo de CloudShop.
4. Aplicar el bootstrap únicamente con autorización del equipo y conservar el log
   sanitizado.
5. Inicializar la raíz con los outputs del bootstrap y locking S3.
6. Confirmar/verificar mediante Terraform la identidad SES y el destinatario de demo.
7. Generar un **plan raíz nuevo** contra el state remoto.
8. Revisar cuenta, región, costos, ownership y acciones create/change/destroy. No
   aplicar si aparece destrucción o reemplazo dudoso.
9. Aplicar exactamente el plan aprobado, sin cambios manuales en AWS.
10. Ejecutar smoke tests, casos por rol, TST-01..04 y un plan posterior que no muestre
    drift.
11. Actualizar trazabilidad, reporte de pruebas y evidencia de despliegue.

El plan aislado histórico que mostró aproximadamente **367 altas** fue generado sin
state remoto y antes del último fixer. **No debe reutilizarse ni aplicarse.** Se debe
generar un plan fresco desde este commit.

## Pruebas obligatorias

- **TST-01:** demostrar con credenciales reales que un rol sin permiso recibe
  `403 Forbidden`, incluido `DELETE /productos/{productId}`.
- **TST-02:** crear un pedido y demostrar pedido persistido, stock actualizado sin
  negativos, evento/outbox, auditoría, correo SES y correlation ID común.
- **TST-03:** demostrar en CloudWatch Count, 4XX/5XX, errores de autenticación y
  aplicación, latencia promedio, logs Lambda y métricas WAF.
- **TST-04:** demostrar bootstrap, `terraform init/plan/apply`, outputs, smoke tests y
  un plan posterior sin cambios inesperados.

## Evidencia que debe capturarse

- Identidad AWS y región sanitizadas; nunca credenciales.
- Resumen de cada plan y apply: create/change/destroy y exit code.
- Outputs no sensibles, URL CloudFront y headers de seguridad.
- Rol/grupo Cognito y ARN STS asumido para cada rol.
- Respuestas HTTP 200/403 con correlation ID.
- Items sanitizados de pedido, inventario, auditoría, outbox e idempotencia.
- Evento EventBridge, retry/DLQ controlado y `MessageId` SES sin PII.
- Dashboard/métricas CloudWatch y asociación real del WAF.
- `terraform plan` final que demuestre ausencia de drift.

## Archivos prohibidos

Nunca confirmar, subir ni incorporar a otro paquete:

- credenciales, access keys, tokens, cookies, private keys o passwords;
- `.env`, `.env.*`, archivos `credentials` o perfiles AWS;
- `*.tfstate`, `*.tfstate.*`, `*.tfplan` o planes en texto con datos sensibles;
- directorios `.terraform/`;
- `node_modules/`, `dist/`, `build/`, caches, coverage o `__pycache__/`;
- ZIP generados de Lambda, logs sin sanitizar o exports con datos personales.

Antes de cada commit ejecutar `git status --short` y revisar el diff staged.

## Rollback y limpieza

- No usar `terraform destroy` como mecanismo rutinario de rollback.
- Conservar state remoto versionado y los planes/logs sanitizados del despliegue.
- Ante fallo de aplicación, detenerse, inspeccionar state/drift y corregir Terraform;
  no reparar recursos manualmente.
- El frontend puede volver a un commit/build previamente aprobado mediante un nuevo
  plan; registrar invalidación CloudFront si corresponde.
- Cualquier limpieza debe apuntar únicamente a recursos exclusivos de CloudShop,
  tener plan revisado y autorización explícita del equipo/docente.
- No borrar auditoría, evidencia, identidades compartidas ni recursos cuya propiedad
  no sea inequívoca.

## Instrucciones para el equipo

1. Clonar el bundle o la rama remota de handoff.
2. Leer README, ADR-001, este documento, `docs/deployment-evidence.md` y
   `docs/audit-report.md`.
3. Comparar el SHA-256 de los artefactos recibidos.
4. Trabajar desde una rama propia; no desplegar desde `main/master`.
5. Confirmar los bloqueos externos y ejecutar la secuencia anterior.
6. No declarar `READY FOR SUBMISSION` hasta que todos los requisitos obligatorios,
   TST-01..04 y el despliegue Terraform real tengan evidencia reproducible.
