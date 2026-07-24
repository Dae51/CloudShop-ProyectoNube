locals {
  lambda_name = "${var.name_prefix}-reportes"
  routes = {
    total_sales    = { resource_id = aws_api_gateway_resource.total.id, source_path = "reportes/ventas/total" }
    sales_by_store = { resource_id = aws_api_gateway_resource.by_store.id, source_path = "reportes/ventas/por-tienda" }
    top_products   = { resource_id = aws_api_gateway_resource.top_products.id, source_path = "reportes/productos/mas-vendidos" }
    out_of_stock   = { resource_id = aws_api_gateway_resource.out_of_stock.id, source_path = "reportes/productos/agotados" }
    top_customers  = { resource_id = aws_api_gateway_resource.top_customers.id, source_path = "reportes/clientes/mas-compras" }
    orders_status  = { resource_id = aws_api_gateway_resource.by_status.id, source_path = "reportes/pedidos/por-estado" }
  }
}

data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/reportes_lambda.zip"
}

resource "aws_iam_role" "lambda" {
  name = "${local.lambda_name}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
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
        Sid      = "ReadDashboardSources"
        Effect   = "Allow"
        Action   = ["dynamodb:Scan"]
        Resource = [var.orders_table_arn, var.products_table_arn]
      },
      {
        Sid      = "WriteStructuredLogs"
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
  timeout          = 30
  memory_size      = 512

  environment {
    variables = {
      ORDERS_TABLE   = var.orders_table_name
      PRODUCTS_TABLE = var.products_table_name
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda]
  tags       = merge(var.common_tags, { Module = "Reportes" })
}

resource "aws_api_gateway_resource" "reports" {
  rest_api_id = var.rest_api_id
  parent_id   = var.root_resource_id
  path_part   = "reportes"
}

resource "aws_api_gateway_resource" "sales" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.reports.id
  path_part   = "ventas"
}

resource "aws_api_gateway_resource" "total" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.sales.id
  path_part   = "total"
}

resource "aws_api_gateway_resource" "by_store" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.sales.id
  path_part   = "por-tienda"
}

resource "aws_api_gateway_resource" "products" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.reports.id
  path_part   = "productos"
}

resource "aws_api_gateway_resource" "top_products" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.products.id
  path_part   = "mas-vendidos"
}

resource "aws_api_gateway_resource" "out_of_stock" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.products.id
  path_part   = "agotados"
}

resource "aws_api_gateway_resource" "customers" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.reports.id
  path_part   = "clientes"
}

resource "aws_api_gateway_resource" "top_customers" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.customers.id
  path_part   = "mas-compras"
}

resource "aws_api_gateway_resource" "orders" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.reports.id
  path_part   = "pedidos"
}

resource "aws_api_gateway_resource" "by_status" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.orders.id
  path_part   = "por-estado"
}

resource "aws_api_gateway_method" "route" {
  for_each = local.routes

  rest_api_id   = var.rest_api_id
  resource_id   = each.value.resource_id
  http_method   = "GET"
  authorization = "AWS_IAM"
}

resource "aws_api_gateway_integration" "route" {
  for_each = local.routes

  rest_api_id             = var.rest_api_id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.route[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.lambda.invoke_arn
}

resource "aws_lambda_permission" "api" {
  for_each = local.routes

  statement_id  = "AllowSharedApi-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.execution_arn}/${var.stage_name}/GET/${each.value.source_path}"
}

resource "aws_api_gateway_method" "options" {
  for_each = local.routes

  rest_api_id   = var.rest_api_id
  resource_id   = each.value.resource_id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options" {
  for_each = local.routes

  rest_api_id       = var.rest_api_id
  resource_id       = each.value.resource_id
  http_method       = aws_api_gateway_method.options[each.key].http_method
  type              = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 204}" }
}

resource "aws_api_gateway_method_response" "options" {
  for_each = local.routes

  rest_api_id = var.rest_api_id
  resource_id = each.value.resource_id
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = "204"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options" {
  for_each = local.routes

  rest_api_id = var.rest_api_id
  resource_id = each.value.resource_id
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = aws_api_gateway_method_response.options[each.key].status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Correlation-Id'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

resource "aws_iam_policy" "api_administrator" {
  name = "${local.lambda_name}-api-administrador"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "execute-api:Invoke"
      Resource = ["${var.execution_arn}/${var.stage_name}/GET/reportes/*"]
    }]
  })
  tags = var.common_tags
}
