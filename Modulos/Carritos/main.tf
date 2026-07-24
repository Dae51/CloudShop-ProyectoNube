locals {
  lambda_name = "${var.name_prefix}-carritos"
  routes = {
    get    = { method = "GET", resource_id = aws_api_gateway_resource.mine.id, source_path = "carritos/mio" }
    clear  = { method = "DELETE", resource_id = aws_api_gateway_resource.mine.id, source_path = "carritos/mio" }
    add    = { method = "POST", resource_id = aws_api_gateway_resource.items.id, source_path = "carritos/mio/items" }
    update = { method = "PATCH", resource_id = aws_api_gateway_resource.item.id, source_path = "carritos/mio/items/*" }
    remove = { method = "DELETE", resource_id = aws_api_gateway_resource.item.id, source_path = "carritos/mio/items/*" }
  }
  cors_resources = {
    mine  = aws_api_gateway_resource.mine.id
    items = aws_api_gateway_resource.items.id
    item  = aws_api_gateway_resource.item.id
  }
}

resource "aws_dynamodb_table" "carts" {
  name         = "${var.name_prefix}-carts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "customerId"
  attribute {
    name = "customerId"
    type = "S"
  }
  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }
  tags = merge(var.common_tags, { Module = "Carritos" })
}

data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/carritos_lambda.zip"
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
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
        Resource = aws_dynamodb_table.carts.arn
      },
      {
        Effect   = "Allow"
        Action   = "dynamodb:GetItem"
        Resource = var.products_table_arn
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
      CARTS_TABLE    = aws_dynamodb_table.carts.name
      PRODUCTS_TABLE = var.products_table_name
    }
  }
  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda]
  tags       = merge(var.common_tags, { Module = "Carritos" })
}

resource "aws_api_gateway_resource" "carts" {
  rest_api_id = var.rest_api_id
  parent_id   = var.root_resource_id
  path_part   = "carritos"
}
resource "aws_api_gateway_resource" "mine" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.carts.id
  path_part   = "mio"
}
resource "aws_api_gateway_resource" "items" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.mine.id
  path_part   = "items"
}
resource "aws_api_gateway_resource" "item" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.items.id
  path_part   = "{productId}"
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
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PATCH,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
  depends_on = [aws_api_gateway_integration.options]
}

resource "aws_iam_policy" "cliente" {
  name = "${var.name_prefix}-carritos-cliente"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${var.execution_arn}/${var.stage_name}/GET/carritos/mio",
        "${var.execution_arn}/${var.stage_name}/DELETE/carritos/mio",
        "${var.execution_arn}/${var.stage_name}/POST/carritos/mio/items",
        "${var.execution_arn}/${var.stage_name}/PATCH/carritos/mio/items/*",
        "${var.execution_arn}/${var.stage_name}/DELETE/carritos/mio/items/*"
      ]
    }]
  })
}
