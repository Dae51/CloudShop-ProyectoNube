# ADR-001: Autenticación y arquitectura de frontend

- Estado: Aceptado para implementación y sujeto al spike de Phase 2
- Fecha: 2026-07-23
- Decisores: equipo CloudShop

## Contexto

El checkout actual no contiene frontend ni proveedor de identidad. Siete rutas de
Productos usan `AWS_IAM` y policies `execute-api:Invoke` diferenciadas, mientras
`GET /users` es público. El PDF exige autenticación, rol y permiso en todos los
endpoints protegidos y mínimo privilegio.

Se necesita una SPA estática en S3/CloudFront, auto-registro seguro como `CLIENTE`,
administración protegida de roles y una forma demostrable de obtener 403 antes de
ejecutar una Lambda no autorizada.

## Opciones

### 1. User Pool + Identity Pool + SigV4 sobre `AWS_IAM`

El User Pool autentica; grupos con roles IAM generan `cognito:roles` y
`cognito:preferred_role`; el Identity Pool entrega credenciales temporales del rol y
el navegador firma SigV4.

Ventajas:

- reutiliza el modelo `AWS_IAM` de Productos;
- expresa mínimo privilegio en ARN de método/ruta;
- API Gateway produce 403 antes de Lambda cuando el rol no tiene `execute-api:Invoke`;
- credenciales temporales, sin secretos en la SPA;
- evidencia clara de rol asumido y policy efectiva.

Costos/riesgos:

- mayor complejidad de frontend y configuración que bearer tokens;
- se deben renovar credenciales y firmar correctamente;
- los roles de grupo y la resolución ambigua deben configurarse con denegación;
- aun se necesita autorización de objeto dentro de Lambda.

### 2. Cognito User Pool authorizer con bearer tokens

API Gateway valida el JWT. Las Lambdas usan claims/grupos para autorización.

Ventajas:

- cliente HTTP más sencillo;
- menos recursos que Identity Pool;
- buena autenticación administrada.

Costos/riesgos:

- reemplaza la autorización ya implementada;
- en REST API los grupos no producen por sí mismos policies por método; la Lambda debe
  decidir permisos o se necesitan scopes y resource server;
- la evidencia de mínimo privilegio IAM por rol de usuario es menos directa;
- un error de guard compartido afecta todas las rutas.

### 3. Lambda authorizer/JWT

Un authorizer propio valida token y genera policies.

Ventajas:

- máxima flexibilidad para claims, tenant y rutas;
- puede centralizar permisos.

Costos/riesgos:

- más código de seguridad, pruebas, latencia y observabilidad;
- riesgo de errores criptográficos/caché/policy;
- no existe implementación reutilizable en el repositorio;
- menor encaje con el tiempo y la rúbrica que los servicios administrados.

## Decisión

Se elige la opción 1. React + Vite será el frontend y se conservará `AWS_IAM` en API
Gateway. Cognito User Pool + Identity Pool entregará credenciales temporales. Los
grupos oficiales se asociarán a roles con precedencia y el Identity Pool usará
selección por token con resolución ambigua `Deny`.

La decisión se apoya en el estado real: Productos ya usa `AWS_IAM`, la rúbrica pondera
arquitectura/integración y cloud, y el caso TST-01 se demuestra tanto en IAM como en la
validación de Lambda. AWS documenta que los grupos pueden aportar
`cognito:preferred_role` y que un Identity Pool entrega credenciales temporales
limitadas:

- [Role-based access control con Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/role-based-access-control.html)
- [Grupos de User Pool y roles IAM](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-user-groups.html)
- [Cognito con API Gateway y AWS_IAM](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-integrate-with-cognito.html)

## Controles obligatorios

- El app client no tiene client secret.
- No se habilitan identidades no autenticadas.
- El formulario de registro no incluye rol.
- Post-confirmation asigna únicamente `CLIENTE`.
- Solo una Lambda administrativa puede cambiar grupos privilegiados y registra actor,
  rol anterior/nuevo, resultado y correlation ID.
- Las trust policies de roles exigen el Identity Pool exacto y `amr=authenticated`.
- La resolución sin claim de rol es `Deny`.
- Cada role policy enumera métodos/rutas, sin `execute-api:*` ni `Resource="*"`.
- Cada Lambda revalida rol/permiso y propiedad; ocultar UI no autoriza.
- Tokens y credenciales no se persisten manualmente en `localStorage`.
- Errores de API son visibles; no existen datos demo en runtime de producción.

## Spike y criterio de reversión

Antes de expandir la UI se demostrará con AWS real:

1. login de `CLIENTE`;
2. credenciales cuyo ARN corresponde solo al rol Cliente;
3. `GET /productos` firmado devuelve 200;
4. `DELETE /productos/{id}` firmado devuelve 403;
5. correlation ID y error aparecen en logs/métricas.

Si no puede demostrarse sin permisos excesivos o la cuenta del curso prohíbe Identity
Pools, se actualizará este ADR y se adoptará la opción 2. No se construirá el resto de
la SPA sobre un spike fallido.

## Consecuencias

- Terraform añadirá providers regional y `us-east-1` para WAF de CloudFront.
- La SPA incluirá un cliente Cognito/credenciales y un signer SigV4 centralizado.
- Las policies de los tres roles se compondrán desde todos los dominios.
- La autorización de API seguirá siendo una combinación de IAM (ruta) y dominio
  (rol, permiso y propiedad).

