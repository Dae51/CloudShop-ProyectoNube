# Evidencia de despliegue

## Estado

**BLOCKED — no se ejecutó `terraform apply`.** No existen URL, outputs ni evidencia de
servicios AWS reales atribuibles a esta iteración.

## Gate observado

| Check | Resultado |
|---|---|
| Identidad AWS | cuenta `190239490282`, usuario IAM `lab-user` |
| Región efectiva | `us-east-1` |
| Backend anterior | bucket `cloudshop-terraform-esen2026` devolvió 404 |
| Región del backend anterior | `us-east-2`, discrepante con provider |
| Identidades SES | 0 |
| Build/tests/validate | PASS; root revalidado tras fixer |
| Plan bootstrap | 5 create, 0 change, 0 destroy |
| Plan root aislado | histórico: 367 create, 0 change, 0 destroy; debe regenerarse tras fixer |
| Presupuesto WAF | no informado |
| Entorno/cuenta del curso | no confirmados inequívocamente |
| Apply | no ejecutado |

## Por qué no se aplicó

El plan raíz aislado parte de estado vacío. Aplicarlo no permitiría distinguir recursos
existentes, drift o propiedad y viola el gate automático. Además, WAF tiene costo fijo
y SES no puede demostrar correo real sin identidad verificada.

## Corrección preparada

`bootstrap/` declara un bucket de state privado, cifrado, versionado, sin acceso
público y con `prevent_destroy`. El backend raíz es parcial y recibe bucket/key/region
solo durante `terraform init`.

Comandos exactos:

```bash
terraform -chdir=bootstrap init
terraform -chdir=bootstrap plan -out=bootstrap.tfplan
terraform -chdir=bootstrap apply bootstrap.tfplan

terraform init -reconfigure \
  -backend-config="bucket=$(terraform -chdir=bootstrap output -raw state_bucket_name)" \
  -backend-config="key=$(terraform -chdir=bootstrap output -raw state_key)" \
  -backend-config="region=$(terraform -chdir=bootstrap output -raw state_region)" \
  -backend-config="encrypt=true" \
  -backend-config="use_lockfile=true"

terraform plan \
  -var='ses_sender_email=REMPLAZAR' \
  -var='ses_demo_recipient=REMPLAZAR' \
  -out=cloudshop.tfplan
terraform show -no-color cloudshop.tfplan
```

Solo después de confirmar 0 destrucciones/reemplazos dudosos, cuenta/región correctas
y costo aceptado:

```bash
terraform apply cloudshop.tfplan
```

## Acciones humanas inevitables

- Confirmar por correo la identidad SES creada por Terraform.
- Si la cuenta SES está en sandbox, verificar también el destinatario o solicitar
  production access.
- Ejecutar una vez `scripts/bootstrap_admin.py` según `docs/security-design.md`; los
  siguientes roles se asignan en la app protegida.
- Confirmar presupuesto WAF y restricciones docentes sobre Cognito.

Estas acciones no autorizan crear infraestructura manualmente.

## Evidencia requerida después

- outputs Terraform sanitizados y URL CloudFront;
- HTTP 200/403 por rol;
- items de pedido, inventario, auditoría/outbox con correlation ID;
- EventBridge invocation, DLQ vacía/controlada y SES MessageId;
- métricas y dashboard CloudWatch;
- Web ACL asociado al ARN del stage;
- `terraform plan` posterior sin cambios.
