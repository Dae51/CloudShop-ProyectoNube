locals {
  lambda_function_name = "compras-carrito-lambda"
  product_index_name   = "ProductIdUserIdIndex"

  routes = {
    add_item = {
      method      = "POST"
      resource_id = aws_api_gateway_resource.cart_items.id
    }
    get_cart = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.cart.id
    }
    get_item = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.cart_item.id
    }
    update_item = {
      method      = "PATCH"
      resource_id = aws_api_gateway_resource.cart_item.id
    }
    delete_item = {
      method      = "DELETE"
      resource_id = aws_api_gateway_resource.cart_item.id
    }
    clear_cart = {
      method      = "DELETE"
      resource_id = aws_api_gateway_resource.cart.id
    }
  }
}

resource "aws_dynamodb_table" "cart_items" {
  name         = var.cart_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "productId"

  attribute {
    name = "userId"
    type = "S"
  }

  attribute {
    name = "productId"
    type = "S"
  }

  global_secondary_index {
    name            = local.product_index_name
    hash_key        = "productId"
    range_key       = "userId"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Module = "Compras"
  }
}

resource "aws_iam_role" "cart_lambda" {
  name = "compras-carrito-lambda-role"

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

resource "aws_cloudwatch_log_group" "cart_lambda" {
  name              = "/aws/lambda/${local.lambda_function_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Module = "Compras"
  }
}

resource "aws_iam_policy" "cart_lambda" {
  name        = "compras-carrito-lambda-policy"
  description = "Acceso minimo del carrito a DynamoDB y CloudWatch Logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ManageCartItems"
        Effect = "Allow"
        Action = [
          "dynamodb:DeleteItem",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.cart_items.arn
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.cart_lambda.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "cart_lambda" {
  role       = aws_iam_role.cart_lambda.name
  policy_arn = aws_iam_policy.cart_lambda.arn
}

data "archive_file" "cart_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/compras_carrito_lambda.zip"
}

resource "aws_lambda_function" "cart" {
  function_name    = local.lambda_function_name
  filename         = data.archive_file.cart_lambda.output_path
  source_code_hash = data.archive_file.cart_lambda.output_base64sha256
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.9"
  role             = aws_iam_role.cart_lambda.arn
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      CART_TABLE = aws_dynamodb_table.cart_items.name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.cart_lambda,
    aws_iam_role_policy_attachment.cart_lambda
  ]

  tags = {
    Module = "Compras"
  }
}

resource "aws_api_gateway_rest_api" "cart" {
  name        = "compras-carrito-api"
  description = "API REST del modulo de carrito"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_resource" "carts" {
  rest_api_id = aws_api_gateway_rest_api.cart.id
  parent_id   = aws_api_gateway_rest_api.cart.root_resource_id
  path_part   = "carritos"
}

resource "aws_api_gateway_resource" "cart" {
  rest_api_id = aws_api_gateway_rest_api.cart.id
  parent_id   = aws_api_gateway_resource.carts.id
  path_part   = "{userId}"
}

resource "aws_api_gateway_resource" "cart_items" {
  rest_api_id = aws_api_gateway_rest_api.cart.id
  parent_id   = aws_api_gateway_resource.cart.id
  path_part   = "items"
}

resource "aws_api_gateway_resource" "cart_item" {
  rest_api_id = aws_api_gateway_rest_api.cart.id
  parent_id   = aws_api_gateway_resource.cart_items.id
  path_part   = "{productId}"
}

resource "aws_api_gateway_method" "cart" {
  for_each = local.routes

  rest_api_id   = aws_api_gateway_rest_api.cart.id
  resource_id   = each.value.resource_id
  http_method   = each.value.method
  authorization = "AWS_IAM"
}

resource "aws_api_gateway_integration" "cart" {
  for_each = local.routes

  rest_api_id             = aws_api_gateway_rest_api.cart.id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.cart[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.cart.invoke_arn
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowCartApiGatewayInvocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cart.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.cart.execution_arn}/${var.stage_name}/*/*"
}

resource "aws_api_gateway_deployment" "cart" {
  rest_api_id = aws_api_gateway_rest_api.cart.id

  triggers = {
    redeployment = sha1(jsonencode({
      resources    = [aws_api_gateway_resource.carts.id, aws_api_gateway_resource.cart.id, aws_api_gateway_resource.cart_items.id, aws_api_gateway_resource.cart_item.id]
      methods      = [for method in aws_api_gateway_method.cart : method.id]
      integrations = [for integration in aws_api_gateway_integration.cart : integration.id]
    }))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_api_gateway_integration.cart]
}

resource "aws_api_gateway_stage" "cart" {
  deployment_id = aws_api_gateway_deployment.cart.id
  rest_api_id   = aws_api_gateway_rest_api.cart.id
  stage_name    = var.stage_name

  tags = {
    Module = "Compras"
  }
}

resource "aws_iam_policy" "cart_api_cliente" {
  name        = "compras-carrito-api-cliente"
  description = "Permite administrar el carrito del cliente"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.cart.execution_arn}/${var.stage_name}/GET/carritos/*",
        "${aws_api_gateway_rest_api.cart.execution_arn}/${var.stage_name}/POST/carritos/*/items",
        "${aws_api_gateway_rest_api.cart.execution_arn}/${var.stage_name}/GET/carritos/*/items/*",
        "${aws_api_gateway_rest_api.cart.execution_arn}/${var.stage_name}/PATCH/carritos/*/items/*",
        "${aws_api_gateway_rest_api.cart.execution_arn}/${var.stage_name}/DELETE/carritos/*"
      ]
    }]
  })
}
