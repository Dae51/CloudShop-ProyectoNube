# Bootstrap del estado Terraform

Este directorio crea únicamente el bucket privado y versionado que almacena el
estado del stack principal. Su estado inicial es local porque Terraform no puede
crear el mismo backend que necesita para inicializarse.

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
```

El bucket tiene cifrado, bloqueo público, versionado, propiedad forzada del
bucket y `prevent_destroy`. No se debe crear manualmente ni ejecutar
`terraform destroy`.
