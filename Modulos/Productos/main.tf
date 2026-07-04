locals {
  lambda_function_name = "productos-lambda"
  store_index_name     = "StoreIdCreatedAtIndex"

  routes = {
    create_product = {
      method      = "POST"
      resource_id = aws_api_gateway_resource.productos.id
    }
    list_products = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.productos.id
    }
    get_product = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.product.id
    }
    update_product = {
      method      = "PUT"
      resource_id = aws_api_gateway_resource.product.id
    }
    delete_product = {
      method      = "DELETE"
      resource_id = aws_api_gateway_resource.product.id
    }
    update_inventory = {
      method      = "PATCH"
      resource_id = aws_api_gateway_resource.inventario.id
    }
    list_store_products = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.store_products.id
    }
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

  tags = {
    Module = "Productos"
  }
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

  tags = {
    Module = "Productos"
  }
}

resource "aws_iam_role" "products_lambda" {
  name = "productos-lambda-role"

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

resource "aws_iam_policy" "products_lambda" {
  name        = "productos-lambda-policy"
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
        Sid    = "WriteProductsAndAudit"
        Effect = "Allow"
        Action = "dynamodb:PutItem"
        Resource = [
          aws_dynamodb_table.products.arn,
          aws_dynamodb_table.product_audit.arn
        ]
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
}

resource "aws_iam_role_policy_attachment" "products_lambda" {
  role       = aws_iam_role.products_lambda.name
  policy_arn = aws_iam_policy.products_lambda.arn
}

resource "aws_cloudwatch_log_group" "products_lambda" {
  name              = "/aws/lambda/${local.lambda_function_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Module = "Productos"
  }
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
      STORE_INDEX    = local.store_index_name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.products_lambda,
    aws_iam_role_policy_attachment.products_lambda
  ]

  tags = {
    Module = "Productos"
  }
}

resource "aws_api_gateway_rest_api" "products" {
  name        = "productos-api"
  description = "API del módulo de gestión de productos"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_resource" "productos" {
  rest_api_id = aws_api_gateway_rest_api.products.id
  parent_id   = aws_api_gateway_rest_api.products.root_resource_id
  path_part   = "productos"
}

resource "aws_api_gateway_resource" "product" {
  rest_api_id = aws_api_gateway_rest_api.products.id
  parent_id   = aws_api_gateway_resource.productos.id
  path_part   = "{productId}"
}

resource "aws_api_gateway_resource" "inventario" {
  rest_api_id = aws_api_gateway_rest_api.products.id
  parent_id   = aws_api_gateway_resource.product.id
  path_part   = "inventario"
}

resource "aws_api_gateway_resource" "tiendas" {
  rest_api_id = aws_api_gateway_rest_api.products.id
  parent_id   = aws_api_gateway_rest_api.products.root_resource_id
  path_part   = "tiendas"
}

resource "aws_api_gateway_resource" "store" {
  rest_api_id = aws_api_gateway_rest_api.products.id
  parent_id   = aws_api_gateway_resource.tiendas.id
  path_part   = "{storeId}"
}

resource "aws_api_gateway_resource" "store_products" {
  rest_api_id = aws_api_gateway_rest_api.products.id
  parent_id   = aws_api_gateway_resource.store.id
  path_part   = "productos"
}

resource "aws_api_gateway_method" "products" {
  for_each = local.routes

  rest_api_id   = aws_api_gateway_rest_api.products.id
  resource_id   = each.value.resource_id
  http_method   = each.value.method
  authorization = "AWS_IAM"
}

resource "aws_api_gateway_integration" "products" {
  for_each = local.routes

  rest_api_id             = aws_api_gateway_rest_api.products.id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.products[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.products.invoke_arn
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowProductsApiGatewayInvocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.products.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/*/*"
}

resource "aws_api_gateway_deployment" "products" {
  rest_api_id = aws_api_gateway_rest_api.products.id

  triggers = {
    redeployment = sha1(jsonencode({
      resources = [
        aws_api_gateway_resource.productos.id,
        aws_api_gateway_resource.product.id,
        aws_api_gateway_resource.inventario.id,
        aws_api_gateway_resource.tiendas.id,
        aws_api_gateway_resource.store.id,
        aws_api_gateway_resource.store_products.id
      ]
      methods      = [for method in aws_api_gateway_method.products : method.id]
      integrations = [for integration in aws_api_gateway_integration.products : integration.id]
    }))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_api_gateway_integration.products]
}

resource "aws_api_gateway_stage" "products" {
  deployment_id = aws_api_gateway_deployment.products.id
  rest_api_id   = aws_api_gateway_rest_api.products.id
  stage_name    = var.stage_name

  tags = {
    Module = "Productos"
  }
}

resource "aws_iam_policy" "products_api_administrador" {
  name        = "productos-api-administrador"
  description = "Permite administración completa de productos"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/POST/productos",
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/GET/productos",
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/GET/productos/*",
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/PUT/productos/*",
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/PATCH/productos/*/inventario",
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/DELETE/productos/*",
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/GET/tiendas/*/productos"
      ]
    }]
  })
}

resource "aws_iam_policy" "products_api_operador" {
  name        = "productos-api-operador"
  description = "Permite consultar productos y administrar inventario"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/GET/productos",
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/GET/productos/*",
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/PATCH/productos/*/inventario",
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/GET/tiendas/*/productos"
      ]
    }]
  })
}

resource "aws_iam_policy" "products_api_cliente" {
  name        = "productos-api-cliente"
  description = "Permite consultar productos"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/GET/productos",
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/GET/productos/*",
        "${aws_api_gateway_rest_api.products.execution_arn}/${var.stage_name}/GET/tiendas/*/productos"
      ]
    }]
  })
}
