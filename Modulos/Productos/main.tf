locals {
  lambda_function_name = "${var.name_prefix}-productos"
  store_index_name     = "StoreIdCreatedAtIndex"

  routes = {
    create_product = {
      method      = "POST"
      resource_id = aws_api_gateway_resource.productos.id
      source_path = "productos"
    }
    list_products = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.productos.id
      source_path = "productos"
    }
    get_product = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.product.id
      source_path = "productos/*"
    }
    update_product = {
      method      = "PUT"
      resource_id = aws_api_gateway_resource.product.id
      source_path = "productos/*"
    }
    delete_product = {
      method      = "DELETE"
      resource_id = aws_api_gateway_resource.product.id
      source_path = "productos/*"
    }
    update_inventory = {
      method      = "PATCH"
      resource_id = aws_api_gateway_resource.inventario.id
      source_path = "productos/*/inventario"
    }
    list_store_products = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.store_products.id
      source_path = "tiendas/*/productos"
    }
  }

  cors_resources = {
    productos      = aws_api_gateway_resource.productos.id
    product        = aws_api_gateway_resource.product.id
    inventario     = aws_api_gateway_resource.inventario.id
    store_products = aws_api_gateway_resource.store_products.id
  }
}

resource "aws_dynamodb_table" "products" {
  name         = var.products_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "productId"

  attribute {
    name = "productId"
    type = "S"
  }

  attribute {
    name = "storeId"
    type = "S"
  }

  attribute {
    name = "createdAt"
    type = "S"
  }

  global_secondary_index {
    name            = local.store_index_name
    hash_key        = "storeId"
    range_key       = "createdAt"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = merge(var.common_tags, { Module = "Productos" })
}

resource "aws_dynamodb_table" "product_audit" {
  name         = var.audit_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "auditId"

  attribute {
    name = "auditId"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = merge(var.common_tags, { Module = "Productos" })
}

resource "aws_iam_role" "products_lambda" {
  name = "${local.lambda_function_name}-role"

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

  tags = var.common_tags
}

resource "aws_iam_policy" "products_lambda" {
  name        = "${local.lambda_function_name}-policy"
  description = "Acceso mínimo del servicio de productos a DynamoDB y CloudWatch Logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadProductsTable"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.products.arn
      },
      {
        Sid      = "QueryProductsByStore"
        Effect   = "Allow"
        Action   = "dynamodb:Query"
        Resource = "${aws_dynamodb_table.products.arn}/index/${local.store_index_name}"
      },
      {
        Sid      = "ValidateOwningStore"
        Effect   = "Allow"
        Action   = "dynamodb:GetItem"
        Resource = var.stores_table_arn
      },
      {
        Sid      = "WriteProducts"
        Effect   = "Allow"
        Action   = "dynamodb:PutItem"
        Resource = aws_dynamodb_table.products.arn
      },
      {
        Sid      = "WriteProductAudit"
        Effect   = "Allow"
        Action   = "dynamodb:PutItem"
        Resource = aws_dynamodb_table.product_audit.arn
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.products_lambda.arn}:*"
      }
    ]
  })

  tags = var.common_tags
}

resource "aws_iam_role_policy_attachment" "products_lambda" {
  role       = aws_iam_role.products_lambda.name
  policy_arn = aws_iam_policy.products_lambda.arn
}

resource "aws_cloudwatch_log_group" "products_lambda" {
  name              = "/aws/lambda/${local.lambda_function_name}"
  retention_in_days = var.log_retention_days

  tags = merge(var.common_tags, { Module = "Productos" })
}

data "archive_file" "products_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/productos_lambda.zip"
}

resource "aws_lambda_function" "products" {
  function_name    = local.lambda_function_name
  filename         = data.archive_file.products_lambda.output_path
  source_code_hash = data.archive_file.products_lambda.output_base64sha256
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  role             = aws_iam_role.products_lambda.arn
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      PRODUCTS_TABLE = aws_dynamodb_table.products.name
      AUDIT_TABLE    = aws_dynamodb_table.product_audit.name
      STORES_TABLE   = var.stores_table_name
      STORE_INDEX    = local.store_index_name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.products_lambda,
    aws_iam_role_policy_attachment.products_lambda
  ]

  tags = merge(var.common_tags, { Module = "Productos" })
}

resource "aws_api_gateway_resource" "productos" {
  rest_api_id = var.rest_api_id
  parent_id   = var.root_resource_id
  path_part   = "productos"
}

resource "aws_api_gateway_resource" "product" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.productos.id
  path_part   = "{productId}"
}

resource "aws_api_gateway_resource" "inventario" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.product.id
  path_part   = "inventario"
}

resource "aws_api_gateway_resource" "store_products" {
  rest_api_id = var.rest_api_id
  parent_id   = var.store_resource_id
  path_part   = "productos"
}

resource "aws_api_gateway_method" "products" {
  for_each = local.routes

  rest_api_id   = var.rest_api_id
  resource_id   = each.value.resource_id
  http_method   = each.value.method
  authorization = "AWS_IAM"
}

resource "aws_api_gateway_integration" "products" {
  for_each = local.routes

  rest_api_id             = var.rest_api_id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.products[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.products.invoke_arn
}

resource "aws_lambda_permission" "api_gateway" {
  for_each = local.routes

  statement_id  = "AllowSharedApi-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.products.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.execution_arn}/${var.stage_name}/${each.value.method}/${each.value.source_path}"
}

resource "aws_api_gateway_method" "options" {
  for_each = local.cors_resources

  rest_api_id   = var.rest_api_id
  resource_id   = each.value
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options" {
  for_each = local.cors_resources

  rest_api_id = var.rest_api_id
  resource_id = each.value
  http_method = aws_api_gateway_method.options[each.key].http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 204}"
  }
}

resource "aws_api_gateway_method_response" "options" {
  for_each = local.cors_resources

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
  for_each = local.cors_resources

  rest_api_id = var.rest_api_id
  resource_id = each.value
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = aws_api_gateway_method_response.options[each.key].status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization,X-Amz-Date,X-Amz-Security-Token,X-Amz-Content-Sha256,X-Correlation-Id,Idempotency-Key'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,PATCH,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_integration.options]
}

resource "aws_iam_policy" "products_api_administrador" {
  name        = "${var.name_prefix}-productos-api-administrador"
  description = "Permite administración completa de productos"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${var.execution_arn}/${var.stage_name}/POST/productos",
        "${var.execution_arn}/${var.stage_name}/GET/productos",
        "${var.execution_arn}/${var.stage_name}/GET/productos/*",
        "${var.execution_arn}/${var.stage_name}/PUT/productos/*",
        "${var.execution_arn}/${var.stage_name}/PATCH/productos/*/inventario",
        "${var.execution_arn}/${var.stage_name}/DELETE/productos/*",
        "${var.execution_arn}/${var.stage_name}/GET/tiendas/*/productos"
      ]
    }]
  })
}

resource "aws_iam_policy" "products_api_operador" {
  name        = "${var.name_prefix}-productos-api-operador"
  description = "Permite consultar productos y administrar inventario"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${var.execution_arn}/${var.stage_name}/GET/productos",
        "${var.execution_arn}/${var.stage_name}/GET/productos/*",
        "${var.execution_arn}/${var.stage_name}/PATCH/productos/*/inventario",
        "${var.execution_arn}/${var.stage_name}/GET/tiendas/*/productos"
      ]
    }]
  })
}

resource "aws_iam_policy" "products_api_cliente" {
  name        = "${var.name_prefix}-productos-api-cliente"
  description = "Permite consultar productos"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${var.execution_arn}/${var.stage_name}/GET/productos",
        "${var.execution_arn}/${var.stage_name}/GET/productos/*",
        "${var.execution_arn}/${var.stage_name}/GET/tiendas/*/productos"
      ]
    }]
  })
}
