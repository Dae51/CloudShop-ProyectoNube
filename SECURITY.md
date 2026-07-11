# Seguridad

## IAM Roles

Cada Lambda tiene un rol IAM dedicado:

| Funcion | Rol | Permisos principales |
| --- | --- | --- |
| `usuarios-lambda` | `usuarios-lambda-role` | Lectura/escritura limitada en `Users`, escritura en `UserAudit`, logs |
| `productos-lambda` | `productos-lambda-role` | Lectura/escritura limitada en `Products`, escritura en `ProductAudit`, logs |
| `tiendas-lambda` | `tiendas-lambda-role` | Lectura/escritura limitada en `Stores`, consulta de GSI, logs |
| `compras-carrito-lambda` | `compras-carrito-lambda-role` | CRUD de items en `CartItems`, logs |
| `pedidos-lambda` | `pedidos-lambda-role` | Lectura/escritura en `Orders`, `events:PutEvents` al bus de pedidos, logs |
| `pedidos-inventario-consumer-lambda` | `pedidos-inventario-consumer-role` | Transacciones sobre `Products` y `Orders`, logs |
| `pedidos-auditoria-consumer-lambda` | `pedidos-auditoria-consumer-role` | `dynamodb:PutItem` en `OrderEventsAudit`, logs |
| `pedidos-correo-consumer-lambda` | `pedidos-correo-consumer-role` | `ses:SendEmail`, logs |
| `reportes-lambda` | `reportes-lambda-role` | Lectura en `Orders`, indices de `Orders` y `Products`, logs |
| API Gateway | `cloudshop-api-gateway-cloudwatch-role` | Escritura de logs de API Gateway |

## IAM Policies

El proyecto evita politicas administradas amplias como `AdministratorAccess`. Las politicas estan declaradas por modulo y limitan recursos por ARN.

Politicas de invocacion de API:

- `productos-api-administrador`
- `productos-api-operador`
- `productos-api-cliente`
- `usuarios-api-administrador`
- `usuarios-api-operador`
- `usuarios-api-cliente`
- `tiendas-api-administrador`
- `tiendas-api-operador`
- `tiendas-api-cliente`
- `compras-carrito-api-cliente`
- `pedidos-api-cliente`
- `pedidos-api-operador`
- `reportes-api-ejecutivo`

Estas politicas controlan `execute-api:Invoke` sobre rutas concretas. Deben adjuntarse a identidades IAM segun el rol funcional del usuario.

## API Authorization

Todas las rutas API Gateway implementadas usan:

```hcl
authorization = "AWS_IAM"
```

Implicaciones:

- Las solicitudes sin firma SigV4 son rechazadas.
- Una identidad sin permiso `execute-api:Invoke` recibe `403 Forbidden`.
- La autorizacion ocurre antes de invocar Lambda.
- Los intentos fallidos quedan visibles en logs y metricas de API Gateway cuando el modulo de observabilidad esta aplicado.

## WAF Rules

El modulo `Seguridad` crea dos Web ACL:

- `cloudshop-cloudfront-web-acl` con scope `CLOUDFRONT`.
- `cloudshop-api-gateway-web-acl` con scope `REGIONAL`.

Reglas configuradas en ambos Web ACL:

- `AWSManagedRulesCommonRuleSet`
- `AWSManagedRulesKnownBadInputsRuleSet`
- `AWSManagedRulesSQLiRuleSet`
- `XSSProtection` sobre URI path y query string.
- `RateLimitByIP` con limite de 2000 solicitudes por ventana de evaluacion.

Asociaciones:

- El Web ACL de CloudFront se entrega al modulo `Frontend` y se asocia a la distribucion CloudFront.
- El Web ACL regional se asocia a los stages de API Gateway.

## Principle of Least Privilege

La implementacion aplica minimo privilegio mediante:

- Roles separados por Lambda.
- Politicas por modulo.
- Acceso a tablas especificas, no a todas las tablas.
- Acceso a indices DynamoDB concretos cuando una consulta lo requiere.
- `events:PutEvents` limitado al bus `cloudshop-pedidos-bus`.
- Permisos SES limitados a envio de correo.
- Permisos CloudWatch Logs limitados a los Log Groups de cada funcion.

Excepcion tecnica:

- El rol `cloudshop-api-gateway-cloudwatch-role` usa `Resource = "*"` para acciones de CloudWatch Logs porque API Gateway valida ese rol con los permisos requeridos para crear y publicar logs de ejecucion. No otorga permisos administrativos ni acceso a servicios fuera de CloudWatch Logs.

## CloudFront Security

El frontend se distribuye por CloudFront con:

- HTTPS habilitado usando el certificado predeterminado de CloudFront.
- `viewer_protocol_policy = redirect-to-https`.
- `default_root_object = index.html`.
- Origin Access Control para acceder al bucket S3.
- Bucket S3 privado, sin acceso publico abierto.
- Bucket Policy que permite `s3:GetObject` solo al principal `cloudfront.amazonaws.com` y solo cuando `AWS:SourceArn` coincide con la distribucion.

## Threat Protection

Controles implementados:

- Proteccion contra entradas comunes maliciosas por AWS Managed Rules.
- Proteccion contra SQL Injection por AWS Managed Rules.
- Proteccion XSS adicional por regla custom de WAF.
- Rate limiting por IP.
- Autorizacion IAM por ruta.
- Logs estructurados para eventos de aplicacion, rechazos y excepciones.
- Alarmas CloudWatch para errores Lambda, 5XX de API, latencia y throttling DynamoDB.

Limitaciones conocidas:

- El frontend es demostrativo y no implementa un flujo completo de autenticacion federada.
- La autorizacion de negocio depende de adjuntar las politicas IAM correctas a las identidades que consumen la API.
- SES requiere identidades verificadas; si la cuenta esta en sandbox, tambien debe verificarse el destinatario.
