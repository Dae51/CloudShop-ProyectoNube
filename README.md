# CloudShop Enterprise

La infraestructura se organiza en módulos Terraform por dominio. API Gateway
es un recurso compartido del proyecto: la raíz crea una sola API REST regional,
su deployment y el stage; cada módulo recibe los identificadores de esa API y
registra únicamente sus propios recursos, métodos e integraciones.

Actualmente la API compartida publica:

- `/users`, registrado por `Modulos/Usuarios`.
- `/productos` y `/tiendas/{storeId}/productos`, registrados por
  `Modulos/Productos`.

Los módulos exponen una huella de configuración de sus rutas. El deployment
raíz depende de todos los módulos de rutas y usa esas huellas como trigger, por
lo que un cambio en recursos, métodos, autorización o integraciones genera un
nuevo deployment de forma segura.

## Salidas principales

- `cloudshop_api_url`: URL base compartida por todos los módulos.
- `cloudshop_api_execution_arn`: ARN para políticas e invocaciones.
- `productos_routes`: resumen de las siete rutas de Productos.
- `productos_table_name` y `product_audit_table_name`: tablas DynamoDB.
- `productos_lambda_name`: Lambda del servicio de Productos.
- `productos_role_policy_arns`: políticas para Administrador, Operador y
  Cliente.

El módulo de Usuarios conserva por compatibilidad su autorización existente
`NONE` en `GET /users`. Las rutas de Productos continúan usando `AWS_IAM` y
validación adicional de rol dentro de Lambda.
