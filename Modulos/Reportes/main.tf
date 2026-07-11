data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  lambda_function_name = "reportes-lambda"
  orders_table_arn     = "arn:aws:dynamodb:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/${var.orders_table_name}"
  products_table_arn   = "arn:aws:dynamodb:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/${var.products_table_name}"

  routes = {
    total_sales = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.sales_totals.id
    }
    sales_by_store = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.sales_stores.id
    }
    best_selling_products = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.products_best_selling.id
    }
    out_of_stock_products = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.products_out_of_stock.id
    }
    top_customers = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.customers_top_purchases.id
    }
    orders_by_status = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.orders_statuses.id
    }
  }
}

resource "aws_iam_role" "reports_lambda" {
  name = "reportes-lambda-role"

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

resource "aws_cloudwatch_log_group" "reports_lambda" {
  name              = "/aws/lambda/${local.lambda_function_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Module = "Reportes"
  }
}

resource "aws_iam_policy" "reports_lambda" {
  name        = "reportes-lambda-policy"
  description = "Acceso de solo lectura de reportes a tablas existentes y CloudWatch Logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadOrders"
        Effect = "Allow"
        Action = [
          "dynamodb:Scan",
          "dynamodb:Query"
        ]
        Resource = [
          local.orders_table_arn,
          "${local.orders_table_arn}/index/${var.orders_status_index_name}"
        ]
      },
      {
        Sid    = "ReadProducts"
        Effect = "Allow"
        Action = [
          "dynamodb:Scan"
        ]
        Resource = local.products_table_arn
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.reports_lambda.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "reports_lambda" {
  role       = aws_iam_role.reports_lambda.name
  policy_arn = aws_iam_policy.reports_lambda.arn
}

data "archive_file" "reports_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/reportes_lambda.zip"
}

resource "aws_lambda_function" "reports" {
  function_name    = local.lambda_function_name
  filename         = data.archive_file.reports_lambda.output_path
  source_code_hash = data.archive_file.reports_lambda.output_base64sha256
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.9"
  role             = aws_iam_role.reports_lambda.arn
  timeout          = 30
  memory_size      = 512

  environment {
    variables = {
      ORDERS_TABLE   = var.orders_table_name
      PRODUCTS_TABLE = var.products_table_name
      STATUS_INDEX   = var.orders_status_index_name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.reports_lambda,
    aws_iam_role_policy_attachment.reports_lambda
  ]

  tags = {
    Module = "Reportes"
  }
}

resource "aws_api_gateway_rest_api" "reports" {
  name        = "reportes-api"
  description = "API REST del modulo de reportes ejecutivos"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_resource" "reports" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_rest_api.reports.root_resource_id
  path_part   = "reportes"
}

resource "aws_api_gateway_resource" "sales" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_resource.reports.id
  path_part   = "ventas"
}

resource "aws_api_gateway_resource" "sales_totals" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_resource.sales.id
  path_part   = "totales"
}

resource "aws_api_gateway_resource" "sales_stores" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_resource.sales.id
  path_part   = "tiendas"
}

resource "aws_api_gateway_resource" "products" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_resource.reports.id
  path_part   = "productos"
}

resource "aws_api_gateway_resource" "products_best_selling" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_resource.products.id
  path_part   = "mas-vendidos"
}

resource "aws_api_gateway_resource" "products_out_of_stock" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_resource.products.id
  path_part   = "sin-stock"
}

resource "aws_api_gateway_resource" "customers" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_resource.reports.id
  path_part   = "clientes"
}

resource "aws_api_gateway_resource" "customers_top_purchases" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_resource.customers.id
  path_part   = "mayores-compras"
}

resource "aws_api_gateway_resource" "orders" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_resource.reports.id
  path_part   = "pedidos"
}

resource "aws_api_gateway_resource" "orders_statuses" {
  rest_api_id = aws_api_gateway_rest_api.reports.id
  parent_id   = aws_api_gateway_resource.orders.id
  path_part   = "estados"
}

resource "aws_api_gateway_method" "reports" {
  for_each = local.routes

  rest_api_id   = aws_api_gateway_rest_api.reports.id
  resource_id   = each.value.resource_id
  http_method   = each.value.method
  authorization = "AWS_IAM"
}

resource "aws_api_gateway_integration" "reports" {
  for_each = local.routes

  rest_api_id             = aws_api_gateway_rest_api.reports.id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.reports[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.reports.invoke_arn
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowReportsApiGatewayInvocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reports.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.reports.execution_arn}/${var.stage_name}/*/*"
}

resource "aws_api_gateway_deployment" "reports" {
  rest_api_id = aws_api_gateway_rest_api.reports.id

  triggers = {
    redeployment = sha1(jsonencode({
      resources = [
        aws_api_gateway_resource.reports.id,
        aws_api_gateway_resource.sales.id,
        aws_api_gateway_resource.sales_totals.id,
        aws_api_gateway_resource.sales_stores.id,
        aws_api_gateway_resource.products.id,
        aws_api_gateway_resource.products_best_selling.id,
        aws_api_gateway_resource.products_out_of_stock.id,
        aws_api_gateway_resource.customers.id,
        aws_api_gateway_resource.customers_top_purchases.id,
        aws_api_gateway_resource.orders.id,
        aws_api_gateway_resource.orders_statuses.id
      ]
      methods      = [for method in aws_api_gateway_method.reports : method.id]
      integrations = [for integration in aws_api_gateway_integration.reports : integration.id]
    }))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_api_gateway_integration.reports]
}

resource "aws_api_gateway_stage" "reports" {
  deployment_id = aws_api_gateway_deployment.reports.id
  rest_api_id   = aws_api_gateway_rest_api.reports.id
  stage_name    = var.stage_name

  tags = {
    Module = "Reportes"
  }
}

resource "aws_iam_policy" "reports_api_ejecutivo" {
  name        = "reportes-api-ejecutivo"
  description = "Permite consultar reportes ejecutivos"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.reports.execution_arn}/${var.stage_name}/GET/reportes/ventas/totales",
        "${aws_api_gateway_rest_api.reports.execution_arn}/${var.stage_name}/GET/reportes/ventas/tiendas",
        "${aws_api_gateway_rest_api.reports.execution_arn}/${var.stage_name}/GET/reportes/productos/mas-vendidos",
        "${aws_api_gateway_rest_api.reports.execution_arn}/${var.stage_name}/GET/reportes/productos/sin-stock",
        "${aws_api_gateway_rest_api.reports.execution_arn}/${var.stage_name}/GET/reportes/clientes/mayores-compras",
        "${aws_api_gateway_rest_api.reports.execution_arn}/${var.stage_name}/GET/reportes/pedidos/estados"
      ]
    }]
  })
}

