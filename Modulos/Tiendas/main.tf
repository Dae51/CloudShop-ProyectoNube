locals {
  lambda_function_name = "tiendas-lambda"
  status_index_name    = "StatusCreatedAtIndex"

  routes = {
    create_store = {
      method      = "POST"
      resource_id = aws_api_gateway_resource.stores.id
    }
    list_stores = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.stores.id
    }
    get_store = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.store.id
    }
    update_store = {
      method      = "PUT"
      resource_id = aws_api_gateway_resource.store.id
    }
    disable_store = {
      method      = "DELETE"
      resource_id = aws_api_gateway_resource.store.id
    }
  }
}

resource "aws_dynamodb_table" "stores" {
  name         = var.stores_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "storeId"

  attribute {
    name = "storeId"
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
    Module = "Tiendas"
  }
}

resource "aws_iam_role" "stores_lambda" {
  name = "tiendas-lambda-role"

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

resource "aws_cloudwatch_log_group" "stores_lambda" {
  name              = "/aws/lambda/${local.lambda_function_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Module = "Tiendas"
  }
}

resource "aws_iam_policy" "stores_lambda" {
  name        = "tiendas-lambda-policy"
  description = "Acceso minimo de tiendas a DynamoDB y CloudWatch Logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadStores"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.stores.arn
      },
      {
        Sid      = "QueryStoresByStatus"
        Effect   = "Allow"
        Action   = "dynamodb:Query"
        Resource = "${aws_dynamodb_table.stores.arn}/index/${local.status_index_name}"
      },
      {
        Sid    = "WriteStores"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.stores.arn
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.stores_lambda.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "stores_lambda" {
  role       = aws_iam_role.stores_lambda.name
  policy_arn = aws_iam_policy.stores_lambda.arn
}

data "archive_file" "stores_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/tiendas_lambda.zip"
}

resource "aws_lambda_function" "stores" {
  function_name    = local.lambda_function_name
  filename         = data.archive_file.stores_lambda.output_path
  source_code_hash = data.archive_file.stores_lambda.output_base64sha256
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.9"
  role             = aws_iam_role.stores_lambda.arn
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      STORES_TABLE = aws_dynamodb_table.stores.name
      STATUS_INDEX = local.status_index_name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.stores_lambda,
    aws_iam_role_policy_attachment.stores_lambda
  ]

  tags = {
    Module = "Tiendas"
  }
}

resource "aws_api_gateway_rest_api" "stores" {
  name        = "tiendas-api"
  description = "API del modulo de gestion de tiendas"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_resource" "stores" {
  rest_api_id = aws_api_gateway_rest_api.stores.id
  parent_id   = aws_api_gateway_rest_api.stores.root_resource_id
  path_part   = "tiendas"
}

resource "aws_api_gateway_resource" "store" {
  rest_api_id = aws_api_gateway_rest_api.stores.id
  parent_id   = aws_api_gateway_resource.stores.id
  path_part   = "{storeId}"
}

resource "aws_api_gateway_method" "stores" {
  for_each = local.routes

  rest_api_id   = aws_api_gateway_rest_api.stores.id
  resource_id   = each.value.resource_id
  http_method   = each.value.method
  authorization = "AWS_IAM"
}

resource "aws_api_gateway_integration" "stores" {
  for_each = local.routes

  rest_api_id             = aws_api_gateway_rest_api.stores.id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.stores[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.stores.invoke_arn
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowStoresApiGatewayInvocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stores.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.stores.execution_arn}/${var.stage_name}/*/*"
}

resource "aws_api_gateway_deployment" "stores" {
  rest_api_id = aws_api_gateway_rest_api.stores.id

  triggers = {
    redeployment = sha1(jsonencode({
      resources    = [aws_api_gateway_resource.stores.id, aws_api_gateway_resource.store.id]
      methods      = [for method in aws_api_gateway_method.stores : method.id]
      integrations = [for integration in aws_api_gateway_integration.stores : integration.id]
    }))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_api_gateway_integration.stores]
}

resource "aws_api_gateway_stage" "stores" {
  deployment_id = aws_api_gateway_deployment.stores.id
  rest_api_id   = aws_api_gateway_rest_api.stores.id
  stage_name    = var.stage_name

  tags = {
    Module = "Tiendas"
  }
}

resource "aws_iam_policy" "stores_api_administrador" {
  name        = "tiendas-api-administrador"
  description = "Permite administracion completa de tiendas"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.stores.execution_arn}/${var.stage_name}/POST/tiendas",
        "${aws_api_gateway_rest_api.stores.execution_arn}/${var.stage_name}/GET/tiendas",
        "${aws_api_gateway_rest_api.stores.execution_arn}/${var.stage_name}/GET/tiendas/*",
        "${aws_api_gateway_rest_api.stores.execution_arn}/${var.stage_name}/PUT/tiendas/*",
        "${aws_api_gateway_rest_api.stores.execution_arn}/${var.stage_name}/DELETE/tiendas/*"
      ]
    }]
  })
}

resource "aws_iam_policy" "stores_api_operador" {
  name        = "tiendas-api-operador"
  description = "Permite consultar y actualizar tiendas"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.stores.execution_arn}/${var.stage_name}/GET/tiendas",
        "${aws_api_gateway_rest_api.stores.execution_arn}/${var.stage_name}/GET/tiendas/*",
        "${aws_api_gateway_rest_api.stores.execution_arn}/${var.stage_name}/PUT/tiendas/*"
      ]
    }]
  })
}

resource "aws_iam_policy" "stores_api_cliente" {
  name        = "tiendas-api-cliente"
  description = "Permite consultar tiendas activas"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.stores.execution_arn}/${var.stage_name}/GET/tiendas",
        "${aws_api_gateway_rest_api.stores.execution_arn}/${var.stage_name}/GET/tiendas/*"
      ]
    }]
  })
}

