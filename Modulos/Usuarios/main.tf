locals {
  lambda_function_name = "usuarios-lambda"
  status_index_name    = "StatusCreatedAtIndex"

  routes = {
    create_user = {
      method      = "POST"
      resource_id = aws_api_gateway_resource.usuarios.id
    }
    list_users = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.usuarios.id
    }
    get_user = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.usuario.id
    }
    update_user = {
      method      = "PUT"
      resource_id = aws_api_gateway_resource.usuario.id
    }
    disable_user = {
      method      = "DELETE"
      resource_id = aws_api_gateway_resource.usuario.id
    }
  }
}

resource "aws_dynamodb_table" "users" {
  name         = var.users_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"

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
    Module = "Usuarios"
  }
}

resource "aws_dynamodb_table" "user_audit" {
  name         = var.user_audit_table_name
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
    Module = "Usuarios"
  }
}

resource "aws_iam_role" "usuarios_lambda" {
  name = "usuarios-lambda-role"

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

resource "aws_cloudwatch_log_group" "usuarios_lambda" {
  name              = "/aws/lambda/${local.lambda_function_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Module = "Usuarios"
  }
}

resource "aws_iam_policy" "usuarios_lambda" {
  name        = "usuarios-lambda-policy"
  description = "Acceso minimo de usuarios a DynamoDB y CloudWatch Logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadUsers"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.users.arn
      },
      {
        Sid      = "QueryUsersByStatus"
        Effect   = "Allow"
        Action   = "dynamodb:Query"
        Resource = "${aws_dynamodb_table.users.arn}/index/${local.status_index_name}"
      },
      {
        Sid    = "WriteUsers"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.users.arn
      },
      {
        Sid      = "WriteUserAudit"
        Effect   = "Allow"
        Action   = "dynamodb:PutItem"
        Resource = aws_dynamodb_table.user_audit.arn
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.usuarios_lambda.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "usuarios_lambda" {
  role       = aws_iam_role.usuarios_lambda.name
  policy_arn = aws_iam_policy.usuarios_lambda.arn
}

data "archive_file" "usuarios_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/usuarios_lambda.zip"
}

resource "aws_lambda_function" "usuarios" {
  function_name    = local.lambda_function_name
  filename         = data.archive_file.usuarios_lambda.output_path
  source_code_hash = data.archive_file.usuarios_lambda.output_base64sha256
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.9"
  role             = aws_iam_role.usuarios_lambda.arn
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      USERS_TABLE  = aws_dynamodb_table.users.name
      AUDIT_TABLE  = aws_dynamodb_table.user_audit.name
      STATUS_INDEX = local.status_index_name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.usuarios_lambda,
    aws_iam_role_policy_attachment.usuarios_lambda
  ]

  tags = {
    Module = "Usuarios"
  }
}

resource "aws_api_gateway_rest_api" "usuarios" {
  name        = "usuarios-api"
  description = "API REST del modulo de gestion de usuarios"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_resource" "usuarios" {
  rest_api_id = aws_api_gateway_rest_api.usuarios.id
  parent_id   = aws_api_gateway_rest_api.usuarios.root_resource_id
  path_part   = "usuarios"
}

resource "aws_api_gateway_resource" "usuario" {
  rest_api_id = aws_api_gateway_rest_api.usuarios.id
  parent_id   = aws_api_gateway_resource.usuarios.id
  path_part   = "{userId}"
}

resource "aws_api_gateway_method" "usuarios" {
  for_each = local.routes

  rest_api_id   = aws_api_gateway_rest_api.usuarios.id
  resource_id   = each.value.resource_id
  http_method   = each.value.method
  authorization = "AWS_IAM"
}

resource "aws_api_gateway_integration" "usuarios" {
  for_each = local.routes

  rest_api_id             = aws_api_gateway_rest_api.usuarios.id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.usuarios[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.usuarios.invoke_arn
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowUsuariosApiGatewayInvocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.usuarios.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.usuarios.execution_arn}/${var.stage_name}/*/*"
}

resource "aws_api_gateway_deployment" "usuarios" {
  rest_api_id = aws_api_gateway_rest_api.usuarios.id

  triggers = {
    redeployment = sha1(jsonencode({
      resources    = [aws_api_gateway_resource.usuarios.id, aws_api_gateway_resource.usuario.id]
      methods      = [for method in aws_api_gateway_method.usuarios : method.id]
      integrations = [for integration in aws_api_gateway_integration.usuarios : integration.id]
    }))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_api_gateway_integration.usuarios]
}

resource "aws_api_gateway_stage" "usuarios" {
  deployment_id = aws_api_gateway_deployment.usuarios.id
  rest_api_id   = aws_api_gateway_rest_api.usuarios.id
  stage_name    = var.stage_name

  tags = {
    Module = "Usuarios"
  }
}

resource "aws_iam_policy" "usuarios_api_administrador" {
  name        = "usuarios-api-administrador"
  description = "Permite administracion completa de usuarios"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.usuarios.execution_arn}/${var.stage_name}/POST/usuarios",
        "${aws_api_gateway_rest_api.usuarios.execution_arn}/${var.stage_name}/GET/usuarios",
        "${aws_api_gateway_rest_api.usuarios.execution_arn}/${var.stage_name}/GET/usuarios/*",
        "${aws_api_gateway_rest_api.usuarios.execution_arn}/${var.stage_name}/PUT/usuarios/*",
        "${aws_api_gateway_rest_api.usuarios.execution_arn}/${var.stage_name}/DELETE/usuarios/*"
      ]
    }]
  })
}

resource "aws_iam_policy" "usuarios_api_operador" {
  name        = "usuarios-api-operador"
  description = "Permite consultar usuarios"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.usuarios.execution_arn}/${var.stage_name}/GET/usuarios",
        "${aws_api_gateway_rest_api.usuarios.execution_arn}/${var.stage_name}/GET/usuarios/*"
      ]
    }]
  })
}

resource "aws_iam_policy" "usuarios_api_cliente" {
  name        = "usuarios-api-cliente"
  description = "Permite consultar usuarios"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "execute-api:Invoke"
      Resource = [
        "${aws_api_gateway_rest_api.usuarios.execution_arn}/${var.stage_name}/GET/usuarios/*"
      ]
    }]
  })
}
