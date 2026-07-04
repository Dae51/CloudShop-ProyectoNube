# Pruebas del módulo de productos

## Pruebas unitarias

Desde la raíz del repositorio:

```bash
python3 -m unittest discover -s Modulos/Productos/tests -v
```

La suite cubre creación por Administrador, rechazo de creación a Cliente,
consulta por Cliente, modificación de inventario por Operador, rechazo de
eliminación a Operador, borrado lógico por Administrador y los registros de
auditoría de eliminación e inventario.

## Evidencia contra AWS

La API usa autorización `AWS_IAM`; las llamadas deben ir firmadas con SigV4.
Configure `API_URL` con el output compartido `cloudshop_api_url` y use
credenciales de un rol que tenga adjunta la política generada para
Administrador, Operador o Cliente. Un cliente como `awscurl` permite firmar las
solicitudes:

```bash
export API_URL="$(terraform output -raw cloudshop_api_url)"

# Administrador: crear (esperado 201)
awscurl --service execute-api --region REGION -X POST \
  -H 'Content-Type: application/json' \
  -d '{"code":"SKU-100","name":"Laptop","description":"Equipo empresarial","category":"Tecnología","price":999.99,"inventory":10,"storeId":"store-1"}' \
  "$API_URL/productos"

# Cliente: crear (esperado 403 por IAM/API Gateway)
awscurl --service execute-api --region REGION -X POST \
  -H 'Content-Type: application/json' \
  -d '{"code":"SKU-101","name":"Monitor","description":"Monitor 27 pulgadas","category":"Tecnología","price":249.99,"inventory":5,"storeId":"store-1"}' \
  "$API_URL/productos"

# Cliente: consultar (esperado 200)
awscurl --service execute-api --region REGION "$API_URL/productos"

# Operador: inventario (esperado 200)
awscurl --service execute-api --region REGION -X PATCH \
  -H 'Content-Type: application/json' -d '{"inventory":7}' \
  "$API_URL/productos/PRODUCT_ID/inventario"

# Operador: eliminar (esperado 403 por IAM/API Gateway)
awscurl --service execute-api --region REGION -X DELETE \
  "$API_URL/productos/PRODUCT_ID"

# Administrador: eliminar lógicamente (esperado 200 y status DELETED)
awscurl --service execute-api --region REGION -X DELETE \
  "$API_URL/productos/PRODUCT_ID"

# Verificar auditorías de eliminación e inventario
aws dynamodb scan --table-name ProductAudit \
  --filter-expression 'resourceId = :id' \
  --expression-attribute-values '{":id":{"S":"PRODUCT_ID"}}'
```

Las dos llamadas que esperan `403` deben ejecutarse con credenciales del rol
indicado. La verificación de auditoría requiere una identidad de diagnóstico
separada con permiso `dynamodb:Scan`; ese permiso no se concede a la Lambda.
