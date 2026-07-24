locals {
  lambda_name = "${var.name_prefix}-tiendas"
  routes = {
    create = { method = "POST", resource_id = aws_api_gateway_resource.stores.id, source_path = "tiendas" }
    list   = { method = "GET", resource_id = aws_api_gateway_resource.stores.id, source_path = "tiendas" }
    get    = { method = "GET", resource_id = aws_api_gateway_resource.store.id, source_path = "tiendas/*" }
    update = { method = "PUT", resource_id = aws_api_gateway_resource.store.id, source_path = "tiendas/*" }
    delete = { method = "DELETE", resource_id = aws_api_gateway_resource.store.id, source_path = "tiendas/*" }
  }
  cors_resources = {
    stores = aws_api_gateway_resource.stores.id
    store  = aws_api_gateway_resource.store.id
  }
}

resource "aws_dynamodb_table" "stores" {
  name         = "${var.name_prefix}-stores"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "storeId"

  attribute {
    name = "storeId"
    type = "S"
  }

  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }
  tags = merge(var.common_tags, { Module = "Tiendas" })
}

data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/tiendas_lambda.zip"
}

resource "aws_iam_role" "lambda" {
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

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.lambda_name}"
  retention_in_days = var.log_retention_days
  tags              = var.common_tags
}

resource "aws_iam_role_policy" "lambda" {
  name = "${local.lambda_name}-policy"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:Scan", "dynamodb:PutItem"]
        Resource = [aws_dynamodb_table.stores.arn, var.audit_table_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.lambda.arn}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "lambda" {
  function_name    = local.lambda_name
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  role             = aws_iam_role.lambda.arn
  layers           = [var.common_layer_arn]
  timeout          = 20
  memory_size      = 256

  environment {
    variables = {
      STORES_TABLE = aws_dynamodb_table.stores.name
      AUDIT_TABLE  = var.audit_table_name
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda]
  tags       = merge(var.common_tags, { Module = "Tiendas" })
}

resource "aws_api_gateway_resource" "stores" {
  rest_api_id = var.rest_api_id
  parent_id   = var.root_resource_id
  path_part   = "tiendas"
}

resource "aws_api_gateway_resource" "store" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.stores.id
  path_part   = "{storeId}"
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
  uri                     = aws_lambda_function.lambda.invoke_arn
}

resource "aws_lambda_permission" "api" {
  for_each      = local.routes
  statement_id  = "AllowSharedApi-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda.function_name
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
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization,X-Amz-Date,X-Amz-Security-Token,X-Amz-Content-Sha256,X-Correlation-Id'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
  depends_on = [aws_api_gateway_integration.options]
}

resource "aws_iam_policy" "api" {
  for_each = {
    ADMINISTRADOR = [
      "${var.execution_arn}/${var.stage_name}/GET/tiendas",
      "${var.execution_arn}/${var.stage_name}/POST/tiendas",
      "${var.execution_arn}/${var.stage_name}/GET/tiendas/*",
      "${var.execution_arn}/${var.stage_name}/PUT/tiendas/*",
      "${var.execution_arn}/${var.stage_name}/DELETE/tiendas/*"
    ]
    OPERADOR = [
      "${var.execution_arn}/${var.stage_name}/GET/tiendas",
      "${var.execution_arn}/${var.stage_name}/GET/tiendas/*"
    ]
    CLIENTE = [
      "${var.execution_arn}/${var.stage_name}/GET/tiendas",
      "${var.execution_arn}/${var.stage_name}/GET/tiendas/*"
    ]
  }
  name = "${var.name_prefix}-tiendas-${lower(each.key)}"
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "execute-api:Invoke", Resource = each.value }]
  })
}
