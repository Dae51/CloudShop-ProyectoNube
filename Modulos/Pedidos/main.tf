data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  orders_lambda_name    = "pedidos-lambda"
  inventory_lambda_name = "pedidos-inventario-consumer-lambda"
  audit_lambda_name     = "pedidos-auditoria-consumer-lambda"
  email_lambda_name     = "pedidos-correo-consumer-lambda"
  user_index_name       = "UserIdCreatedAtIndex"
  status_index_name     = "StatusCreatedAtIndex"
  event_order_index     = "OrderIdEventTimeIndex"
  products_table_arn    = "arn:aws:dynamodb:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/${var.products_table_name}"

  routes = {
    create_order = {
      method      = "POST"
      resource_id = aws_api_gateway_resource.orders.id
    }
    get_order = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.order.id
    }
    update_order = {
      method      = "PATCH"
      resource_id = aws_api_gateway_resource.order.id
    }
    list_user_orders = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.user_orders.id
    }
  }
}

resource "aws_dynamodb_table" "orders" {
  name         = var.orders_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "orderId"

  attribute {
    name = "orderId"
    type = "S"
  }

  attribute {
    name = "userId"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "createdAt"
    type = "S"
  }

  global_secondary_index {
    name            = local.user_index_name
    hash_key        = "userId"
    range_key       = "createdAt"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = local.status_index_name
    hash_key        = "status"
    range_key       = "createdAt"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Module = "Pedidos"
  }
}

resource "aws_dynamodb_table" "order_events_audit" {
  name         = var.orders_audit_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "eventId"

  attribute {
    name = "eventId"
    type = "S"
  }

  attribute {
    name = "orderId"
    type = "S"
  }

  attribute {
    name = "eventTime"
    type = "S"
  }

  global_secondary_index {
    name            = local.event_order_index
    hash_key        = "orderId"
    range_key       = "eventTime"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Module = "Pedidos"
  }
}

resource "aws_cloudwatch_event_bus" "orders" {
  name = var.event_bus_name

  tags = {
    Module = "Pedidos"
  }
}

resource "aws_ses_email_identity" "source" {
  email = var.ses_source_email
}

resource "aws_cloudwatch_event_rule" "inventory" {
  name           = "pedidos-actualizar-inventario"
  description    = "Dispara la actualizacion asincrona de inventario al crear pedidos"
  event_bus_name = aws_cloudwatch_event_bus.orders.name

  event_pattern = jsonencode({
    source        = ["cloudshop.pedidos"]
    "detail-type" = ["PedidoCreado"]
  })
}

resource "aws_cloudwatch_event_rule" "audit" {
  name           = "pedidos-auditar-evento"
  description    = "Persiste el evento completo de pedido creado"
  event_bus_name = aws_cloudwatch_event_bus.orders.name

  event_pattern = jsonencode({
    source        = ["cloudshop.pedidos"]
    "detail-type" = ["PedidoCreado"]
  })
}

resource "aws_cloudwatch_event_rule" "email" {
  name           = "pedidos-enviar-correo"
  description    = "Envia correo de confirmacion al crear pedidos"
  event_bus_name = aws_cloudwatch_event_bus.orders.name

  event_pattern = jsonencode({
    source        = ["cloudshop.pedidos"]
    "detail-type" = ["PedidoCreado"]
  })
}

resource "aws_cloudwatch_log_group" "orders_lambda" {
  name              = "/aws/lambda/${local.orders_lambda_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Module = "Pedidos"
  }
}

resource "aws_cloudwatch_log_group" "inventory_lambda" {
  name              = "/aws/lambda/${local.inventory_lambda_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Module = "Pedidos"
  }
}

resource "aws_cloudwatch_log_group" "audit_lambda" {
  name              = "/aws/lambda/${local.audit_lambda_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Module = "Pedidos"
  }
}

resource "aws_cloudwatch_log_group" "email_lambda" {
  name              = "/aws/lambda/${local.email_lambda_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Module = "Pedidos"
  }
}

resource "aws_iam_role" "orders_lambda" {
  name = "pedidos-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role" "inventory_lambda" {
  name = "pedidos-inventario-consumer-role"

  assume_role_policy = aws_iam_role.orders_lambda.assume_role_policy
}

resource "aws_iam_role" "audit_lambda" {
  name = "pedidos-auditoria-consumer-role"

  assume_role_policy = aws_iam_role.orders_lambda.assume_role_policy
}

resource "aws_iam_role" "email_lambda" {
  name = "pedidos-correo-consumer-role"

  assume_role_policy = aws_iam_role.orders_lambda.assume_role_policy
}

resource "aws_iam_policy" "orders_lambda" {
  name        = "pedidos-lambda-policy"
  description = "Acceso minimo para crear y actualizar pedidos y publicar eventos"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadWriteOrders"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.orders.arn
      },
      {
        Sid      = "QueryOrdersByUser"
        Effect   = "Allow"
        Action   = "dynamodb:Query"
        Resource = "${aws_dynamodb_table.orders.arn}/index/${local.user_index_name}"
      },
      {
        Sid      = "PublishOrderEvents"
        Effect   = "Allow"
        Action   = "events:PutEvents"
        Resource = aws_cloudwatch_event_bus.orders.arn
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.orders_lambda.arn}:*"
      }
    ]
  })
}

resource "aws_iam_policy" "inventory_lambda" {
  name        = "pedidos-inventario-consumer-policy"
  description = "Acceso minimo para descontar inventario y marcar estado en pedidos"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TransactInventoryAndOrder"
        Effect = "Allow"
        Action = [
          "dynamodb:TransactWriteItems",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          local.products_table_arn,
          aws_dynamodb_table.orders.arn
        ]
      },
      {
        Sid      = "MarkOrderInventoryFailure"
        Effect   = "Allow"
        Action   = "dynamodb:UpdateItem"
        Resource = aws_dynamodb_table.orders.arn
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.inventory_lambda.arn}:*"
      }
    ]
  })
}

resource "aws_iam_policy" "audit_lambda" {
  name        = "pedidos-auditoria-consumer-policy"
  description = "Acceso minimo para auditar eventos de pedidos"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "WriteOrderEventAudit"
        Effect   = "Allow"
        Action   = "dynamodb:PutItem"
        Resource = aws_dynamodb_table.order_events_audit.arn
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.audit_lambda.arn}:*"
      }
    ]
  })
}

resource "aws_iam_policy" "email_lambda" {
  name        = "pedidos-correo-consumer-policy"
  description = "Acceso minimo para enviar correos SES"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SendOrderEmail"
        Effect   = "Allow"
        Action   = "ses:SendEmail"
        Resource = aws_ses_email_identity.source.arn
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.email_lambda.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "orders_lambda" {
  role       = aws_iam_role.orders_lambda.name
  policy_arn = aws_iam_policy.orders_lambda.arn
}

resource "aws_iam_role_policy_attachment" "inventory_lambda" {
  role       = aws_iam_role.inventory_lambda.name
  policy_arn = aws_iam_policy.inventory_lambda.arn
}

resource "aws_iam_role_policy_attachment" "audit_lambda" {
  role       = aws_iam_role.audit_lambda.name
  policy_arn = aws_iam_policy.audit_lambda.arn
}

resource "aws_iam_role_policy_attachment" "email_lambda" {
  role       = aws_iam_role.email_lambda.name
  policy_arn = aws_iam_policy.email_lambda.arn
}

data "archive_file" "orders_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/orders_handler.py"
  output_path = "${path.module}/pedidos_lambda.zip"
}

data "archive_file" "inventory_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/inventory_handler.py"
  output_path = "${path.module}/pedidos_inventario_consumer.zip"
}

data "archive_file" "audit_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/audit_handler.py"
  output_path = "${path.module}/pedidos_auditoria_consumer.zip"
}

data "archive_file" "email_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/email_handler.py"
  output_path = "${path.module}/pedidos_correo_consumer.zip"
}

resource "aws_lambda_function" "orders" {
  function_name    = local.orders_lambda_name
  filename         = data.archive_file.orders_lambda.output_path
  source_code_hash = data.archive_file.orders_lambda.output_base64sha256
  handler          = "orders_handler.lambda_handler"
  runtime          = "python3.9"
  role             = aws_iam_role.orders_lambda.arn
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      ORDERS_TABLE   = aws_dynamodb_table.orders.name
      EVENT_BUS_NAME = aws_cloudwatch_event_bus.orders.name
      USER_INDEX     = local.user_index_name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.orders_lambda,
    aws_iam_role_policy_attachment.orders_lambda
  ]

  tags = {
    Module = "Pedidos"
  }
}

resource "aws_lambda_function" "inventory" {
  function_name    = local.inventory_lambda_name
  filename         = data.archive_file.inventory_lambda.output_path
  source_code_hash = data.archive_file.inventory_lambda.output_base64sha256
  handler          = "inventory_handler.lambda_handler"
  runtime          = "python3.9"
  role             = aws_iam_role.inventory_lambda.arn
  timeout          = 20
  memory_size      = 256

  environment {
    variables = {
      ORDERS_TABLE   = aws_dynamodb_table.orders.name
      PRODUCTS_TABLE = var.products_table_name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.inventory_lambda,
    aws_iam_role_policy_attachment.inventory_lambda
  ]

  tags = {
    Module = "Pedidos"
  }
}

resource "aws_lambda_function" "audit" {
  function_name    = local.audit_lambda_name
  filename         = data.archive_file.audit_lambda.output_path
  source_code_hash = data.archive_file.audit_lambda.output_base64sha256
  handler          = "audit_handler.lambda_handler"
  runtime          = "python3.9"
  role             = aws_iam_role.audit_lambda.arn
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      AUDIT_TABLE = aws_dynamodb_table.order_events_audit.name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.audit_lambda,
    aws_iam_role_policy_attachment.audit_lambda
  ]

  tags = {
    Module = "Pedidos"
  }
}

resource "aws_lambda_function" "email" {
  function_name    = local.email_lambda_name
  filename         = data.archive_file.email_lambda.output_path
  source_code_hash = data.archive_file.email_lambda.output_base64sha256
  handler          = "email_handler.lambda_handler"
  runtime          = "python3.9"
  role             = aws_iam_role.email_lambda.arn
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      SES_SOURCE_EMAIL = var.ses_source_email
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.email_lambda,
    aws_iam_role_policy_attachment.email_lambda
  ]

  tags = {
    Module = "Pedidos"
  }
}

resource "aws_cloudwatch_event_target" "inventory" {
  rule           = aws_cloudwatch_event_rule.inventory.name
  event_bus_name = aws_cloudwatch_event_bus.orders.name
  arn            = aws_lambda_function.inventory.arn
}

resource "aws_cloudwatch_event_target" "audit" {
  rule           = aws_cloudwatch_event_rule.audit.name
  event_bus_name = aws_cloudwatch_event_bus.orders.name
  arn            = aws_lambda_function.audit.arn
}

resource "aws_cloudwatch_event_target" "email" {
  rule           = aws_cloudwatch_event_rule.email.name
  event_bus_name = aws_cloudwatch_event_bus.orders.name
  arn            = aws_lambda_function.email.arn
}

resource "aws_lambda_permission" "allow_eventbridge_inventory" {
  statement_id  = "AllowOrdersEventBridgeInventory"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.inventory.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.inventory.arn
}

resource "aws_lambda_permission" "allow_eventbridge_audit" {
  statement_id  = "AllowOrdersEventBridgeAudit"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.audit.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.audit.arn
}

resource "aws_lambda_permission" "allow_eventbridge_email" {
  statement_id  = "AllowOrdersEventBridgeEmail"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.email.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.email.arn
}

resource "aws_api_gateway_rest_api" "orders" {
  name        = "pedidos-api"
  description = "API REST del modulo de pedidos"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_resource" "orders" {
  rest_api_id = aws_api_gateway_rest_api.orders.id
  parent_id   = aws_api_gateway_rest_api.orders.root_resource_id
  path_part   = "pedidos"
}

resource "aws_api_gateway_resource" "order" {
  rest_api_id = aws_api_gateway_rest_api.orders.id
  parent_id   = aws_api_gateway_resource.orders.id
  path_part   = "{orderId}"
}

resource "aws_api_gateway_resource" "users" {
  rest_api_id = aws_api_gateway_rest_api.orders.id
  parent_id   = aws_api_gateway_rest_api.orders.root_resource_id
  path_part   = "usuarios"
}

resource "aws_api_gateway_resource" "user" {
  rest_api_id = aws_api_gateway_rest_api.orders.id
  parent_id   = aws_api_gateway_resource.users.id
  path_part   = "{userId}"
}

resource "aws_api_gateway_resource" "user_orders" {
  rest_api_id = aws_api_gateway_rest_api.orders.id
  parent_id   = aws_api_gateway_resource.user.id
  path_part   = "pedidos"
}

resource "aws_api_gateway_method" "orders" {
  for_each = local.routes

  rest_api_id   = aws_api_gateway_rest_api.orders.id
  resource_id   = each.value.resource_id
  http_method   = each.value.method
  authorization = "AWS_IAM"
}

resource "aws_api_gateway_integration" "orders" {
  for_each = local.routes

  rest_api_id             = aws_api_gateway_rest_api.orders.id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.orders[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.orders.invoke_arn
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowOrdersApiGatewayInvocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.orders.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.orders.execution_arn}/${var.stage_name}/*/*"
}

resource "aws_api_gateway_deployment" "orders" {
  rest_api_id = aws_api_gateway_rest_api.orders.id

  triggers = {
    redeployment = sha1(jsonencode({
      resources    = [aws_api_gateway_resource.orders.id, aws_api_gateway_resource.order.id, aws_api_gateway_resource.users.id, aws_api_gateway_resource.user.id, aws_api_gateway_resource.user_orders.id]
      methods      = [for method in aws_api_gateway_method.orders : method.id]
      integrations = [for integration in aws_api_gateway_integration.orders : integration.id]
    }))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_api_gateway_integration.orders]
}

resource "aws_api_gateway_stage" "orders" {
  deployment_id = aws_api_gateway_deployment.orders.id
  rest_api_id   = aws_api_gateway_rest_api.orders.id
  stage_name    = var.stage_name

  tags = {
    Module = "Pedidos"
  }
}

resource "aws_iam_policy" "orders_api_cliente" {
  name        = "pedidos-api-cliente"
  description = "Permite crear y consultar pedidos"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.orders.execution_arn}/${var.stage_name}/POST/pedidos",
        "${aws_api_gateway_rest_api.orders.execution_arn}/${var.stage_name}/GET/pedidos/*",
        "${aws_api_gateway_rest_api.orders.execution_arn}/${var.stage_name}/GET/usuarios/*/pedidos"
      ]
    }]
  })
}

resource "aws_iam_policy" "orders_api_operador" {
  name        = "pedidos-api-operador"
  description = "Permite consultar y actualizar estado de pedidos"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.orders.execution_arn}/${var.stage_name}/GET/pedidos/*",
        "${aws_api_gateway_rest_api.orders.execution_arn}/${var.stage_name}/PATCH/pedidos/*",
        "${aws_api_gateway_rest_api.orders.execution_arn}/${var.stage_name}/GET/usuarios/*/pedidos"
      ]
    }]
  })
}
