locals {
  lambda_name       = "${var.name_prefix}-pedidos"
  relay_name        = "${var.name_prefix}-outbox-relay"
  notification_name = "${var.name_prefix}-notificaciones"
  routes = {
    create = { method = "POST", resource_id = aws_api_gateway_resource.orders.id, source_path = "pedidos" }
    list   = { method = "GET", resource_id = aws_api_gateway_resource.orders.id, source_path = "pedidos" }
    mine   = { method = "GET", resource_id = aws_api_gateway_resource.mine.id, source_path = "pedidos/mios" }
    get    = { method = "GET", resource_id = aws_api_gateway_resource.order.id, source_path = "pedidos/*" }
    status = { method = "PATCH", resource_id = aws_api_gateway_resource.status.id, source_path = "pedidos/*/estado" }
    cancel = { method = "POST", resource_id = aws_api_gateway_resource.cancel.id, source_path = "pedidos/*/cancelacion" }
  }
  cors_resources = {
    orders = aws_api_gateway_resource.orders.id
    mine   = aws_api_gateway_resource.mine.id
    order  = aws_api_gateway_resource.order.id
    status = aws_api_gateway_resource.status.id
    cancel = aws_api_gateway_resource.cancel.id
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_dynamodb_table" "orders" {
  name         = "${var.name_prefix}-orders"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "orderId"

  attribute {
    name = "orderId"
    type = "S"
  }
  attribute {
    name = "customerId"
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
    name            = "CustomerCreatedAtIndex"
    hash_key        = "customerId"
    range_key       = "createdAt"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "StatusCreatedAtIndex"
    hash_key        = "status"
    range_key       = "createdAt"
    projection_type = "ALL"
  }

  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }
  tags = merge(var.common_tags, { Module = "Pedidos" })
}

resource "aws_dynamodb_table" "outbox" {
  name             = "${var.name_prefix}-outbox"
  billing_mode     = "PAY_PER_REQUEST"
  hash_key         = "eventId"
  stream_enabled   = true
  stream_view_type = "NEW_IMAGE"

  attribute {
    name = "eventId"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }
  attribute {
    name = "occurredAt"
    type = "S"
  }
  global_secondary_index {
    name            = "StatusOccurredAtIndex"
    hash_key        = "status"
    range_key       = "occurredAt"
    projection_type = "ALL"
  }
  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }
  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }
  tags = merge(var.common_tags, { Module = "Eventos" })
}

data "archive_file" "orders" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/pedidos_lambda.zip"
}

resource "aws_iam_role" "orders" {
  name = "${local.lambda_name}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Action = "sts:AssumeRole",
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = var.common_tags
}

resource "aws_cloudwatch_log_group" "orders" {
  name              = "/aws/lambda/${local.lambda_name}"
  retention_in_days = var.log_retention_days
  tags              = var.common_tags
}

resource "aws_iam_role_policy" "orders" {
  name = "${local.lambda_name}-policy"
  role = aws_iam_role.orders.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadOrders"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:Scan"]
        Resource = aws_dynamodb_table.orders.arn
      },
      {
        Sid      = "QueryOrdersIndexes"
        Effect   = "Allow"
        Action   = "dynamodb:Query"
        Resource = "${aws_dynamodb_table.orders.arn}/index/*"
      },
      {
        Sid      = "ReadCart"
        Effect   = "Allow"
        Action   = "dynamodb:GetItem"
        Resource = var.carts_table_arn
      },
      {
        Sid      = "ReadProducts"
        Effect   = "Allow"
        Action   = "dynamodb:GetItem"
        Resource = var.products_table_arn
      },
      {
        Sid      = "ValidateStores"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:ConditionCheckItem"]
        Resource = var.stores_table_arn
      },
      {
        Sid      = "ReadIdempotency"
        Effect   = "Allow"
        Action   = "dynamodb:GetItem"
        Resource = var.idempotency_table_arn
      },
      {
        Sid      = "WriteOrders"
        Effect   = "Allow"
        Action   = "dynamodb:PutItem"
        Resource = aws_dynamodb_table.orders.arn
      },
      {
        Sid      = "UpdateInventory"
        Effect   = "Allow"
        Action   = "dynamodb:UpdateItem"
        Resource = var.products_table_arn
      },
      {
        Sid      = "ClearCart"
        Effect   = "Allow"
        Action   = "dynamodb:DeleteItem"
        Resource = var.carts_table_arn
      },
      {
        Sid      = "WriteAuditOutboxAndIdempotency"
        Effect   = "Allow"
        Action   = "dynamodb:PutItem"
        Resource = [var.audit_table_arn, aws_dynamodb_table.outbox.arn, var.idempotency_table_arn]
      },
      {
        Sid      = "WriteLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.orders.arn}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "orders" {
  function_name    = local.lambda_name
  filename         = data.archive_file.orders.output_path
  source_code_hash = data.archive_file.orders.output_base64sha256
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  role             = aws_iam_role.orders.arn
  layers           = [var.common_layer_arn]
  timeout          = 30
  memory_size      = 512
  environment {
    variables = {
      ORDERS_TABLE      = aws_dynamodb_table.orders.name
      CARTS_TABLE       = var.carts_table_name
      PRODUCTS_TABLE    = var.products_table_name
      STORES_TABLE      = var.stores_table_name
      AUDIT_TABLE       = var.audit_table_name
      OUTBOX_TABLE      = aws_dynamodb_table.outbox.name
      IDEMPOTENCY_TABLE = var.idempotency_table_name
    }
  }
  depends_on = [aws_cloudwatch_log_group.orders, aws_iam_role_policy.orders]
  tags       = merge(var.common_tags, { Module = "Pedidos" })
}

resource "aws_api_gateway_resource" "orders" {
  rest_api_id = var.rest_api_id
  parent_id   = var.root_resource_id
  path_part   = "pedidos"
}
resource "aws_api_gateway_resource" "mine" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.orders.id
  path_part   = "mios"
}
resource "aws_api_gateway_resource" "order" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.orders.id
  path_part   = "{orderId}"
}
resource "aws_api_gateway_resource" "status" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.order.id
  path_part   = "estado"
}
resource "aws_api_gateway_resource" "cancel" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.order.id
  path_part   = "cancelacion"
}

resource "aws_api_gateway_method" "route" {
  for_each      = local.routes
  rest_api_id   = var.rest_api_id
  resource_id   = each.value.resource_id
  http_method   = each.value.method
  authorization = "AWS_IAM"
}
resource "aws_api_gateway_integration" "route" {
  for_each                = local.routes
  rest_api_id             = var.rest_api_id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.route[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.orders.invoke_arn
}
resource "aws_lambda_permission" "api" {
  for_each      = local.routes
  statement_id  = "AllowSharedApi-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.orders.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.execution_arn}/${var.stage_name}/${each.value.method}/${each.value.source_path}"
}

resource "aws_api_gateway_method" "options" {
  for_each      = local.cors_resources
  rest_api_id   = var.rest_api_id
  resource_id   = each.value
  http_method   = "OPTIONS"
  authorization = "NONE"
}
resource "aws_api_gateway_integration" "options" {
  for_each          = local.cors_resources
  rest_api_id       = var.rest_api_id
  resource_id       = each.value
  http_method       = aws_api_gateway_method.options[each.key].http_method
  type              = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 204}" }
}
resource "aws_api_gateway_method_response" "options" {
  for_each    = local.cors_resources
  rest_api_id = var.rest_api_id
  resource_id = each.value
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = "204"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}
resource "aws_api_gateway_integration_response" "options" {
  for_each    = local.cors_resources
  rest_api_id = var.rest_api_id
  resource_id = each.value
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = aws_api_gateway_method_response.options[each.key].status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization,X-Amz-Date,X-Amz-Security-Token,X-Amz-Content-Sha256,X-Correlation-Id,Idempotency-Key'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PATCH,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
  depends_on = [aws_api_gateway_integration.options]
}

resource "aws_iam_policy" "api" {
  for_each = {
    OPERADOR = [
      "${var.execution_arn}/${var.stage_name}/GET/pedidos",
      "${var.execution_arn}/${var.stage_name}/GET/pedidos/*",
      "${var.execution_arn}/${var.stage_name}/PATCH/pedidos/*/estado",
      "${var.execution_arn}/${var.stage_name}/POST/pedidos/*/cancelacion"
    ]
    CLIENTE = [
      "${var.execution_arn}/${var.stage_name}/POST/pedidos",
      "${var.execution_arn}/${var.stage_name}/GET/pedidos/mios",
      "${var.execution_arn}/${var.stage_name}/GET/pedidos/*",
      "${var.execution_arn}/${var.stage_name}/POST/pedidos/*/cancelacion"
    ]
  }
  name = "${var.name_prefix}-pedidos-${lower(each.key)}"
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "execute-api:Invoke", Resource = each.value }]
  })
}
