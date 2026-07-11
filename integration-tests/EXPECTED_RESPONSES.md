# Expected Responses

## Unauthorized Administrator Endpoint

Request:

```http
POST /productos
Authorization: AWS4-HMAC-SHA256 ...unauthorized principal...
Content-Type: application/json
```

Expected:

```json
{
  "status": 403,
  "body": "Forbidden or API Gateway authorization error"
}
```

## Create Product

Expected:

```json
{
  "status": 201,
  "body": {
    "data": {
      "productId": "generated uuid",
      "code": "FLOW-*",
      "name": "Producto Integracion",
      "inventory": 5,
      "status": "ACTIVE"
    }
  }
}
```

## Create Order

Expected:

```json
{
  "status": 201,
  "body": {
    "data": {
      "orderId": "generated uuid",
      "userId": "integration-user",
      "status": "PENDIENTE",
      "inventoryStatus": "PENDIENTE",
      "eventPublicationStatus": "PUBLICADO"
    }
  }
}
```

## Asynchronous Order Evidence

Expected DynamoDB order item:

```json
{
  "orderId": { "S": "<order id>" },
  "eventPublicationStatus": { "S": "PUBLICADO" }
}
```

Expected inventory result:

```json
{
  "productId": { "S": "<product id>" },
  "inventory": { "N": "4" }
}
```

Expected audit query:

```json
{
  "Count": 1,
  "Items": [
    {
      "orderId": { "S": "<order id>" },
      "detailType": { "S": "PedidoCreado" }
    }
  ]
}
```

Expected email evidence:

```json
{
  "logGroup": "/aws/lambda/pedidos-correo-consumer-lambda",
  "contains": "order_email_sent"
}
```

## Monitoring Evidence

Expected:

```json
{
  "dashboard": "cloudshop-observabilidad",
  "alarmsPrefix": "cloudshop",
  "metrics": [
    "AWS/Lambda Errors",
    "AWS/ApiGateway Count",
    "AWS/ApiGateway 5XXError"
  ]
}
```

