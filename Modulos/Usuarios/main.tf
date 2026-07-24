locals {
  lambda_function_name = "${var.name_prefix}-usuarios"

  routes = {
    list_users = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.usuarios.id
      source_path = "usuarios"
    }
    get_user = {
      method      = "GET"
      resource_id = aws_api_gateway_resource.user.id
      source_path = "usuarios/*"
    }
    update_user = {
      method      = "PUT"
      resource_id = aws_api_gateway_resource.user.id
      source_path = "usuarios/*"
    }
    deactivate_user = {
      method      = "DELETE"
      resource_id = aws_api_gateway_resource.user.id
      source_path = "usuarios/*"
    }
    change_role = {
      method      = "PATCH"
      resource_id = aws_api_gateway_resource.role.id
      source_path = "usuarios/*/rol"
    }
  }

  cors_resources = {
    usuarios = aws_api_gateway_resource.usuarios.id
    user     = aws_api_gateway_resource.user.id
    role     = aws_api_gateway_resource.role.id
  }
}

data "archive_file" "usuarios" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/usuarios_lambda.zip"
}

resource "aws_iam_role" "usuarios_lambda" {
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

resource "aws_cloudwatch_log_group" "usuarios_lambda" {
  name              = "/aws/lambda/${local.lambda_function_name}"
  retention_in_days = var.log_retention_days
  tags              = var.common_tags
}

resource "aws_iam_role_policy" "usuarios_lambda" {
  name = "${local.lambda_function_name}-policy"
  role = aws_iam_role.usuarios_lambda.id

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
        Resource = var.users_table_arn
      },
      {
        Sid      = "UpdateUsers"
        Effect   = "Allow"
        Action   = "dynamodb:UpdateItem"
        Resource = var.users_table_arn
      },
      {
        Sid      = "WriteAudit"
        Effect   = "Allow"
        Action   = "dynamodb:PutItem"
        Resource = var.audit_table_arn
      },
      {
        Sid    = "ManageCognitoUsers"
        Effect = "Allow"
        Action = [
          "cognito-idp:AdminAddUserToGroup",
          "cognito-idp:AdminRemoveUserFromGroup",
          "cognito-idp:AdminListGroupsForUser",
          "cognito-idp:AdminDisableUser",
          "cognito-idp:AdminEnableUser"
        ]
        Resource = var.user_pool_arn
      },
      {
        Sid    = "WriteLogs"
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

resource "aws_lambda_function" "usuarios_lambda" {
  function_name    = local.lambda_function_name
  filename         = data.archive_file.usuarios.output_path
  source_code_hash = data.archive_file.usuarios.output_base64sha256
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  role             = aws_iam_role.usuarios_lambda.arn
  layers           = [var.common_layer_arn]
  timeout          = 20
  memory_size      = 256

  environment {
    variables = {
      USERS_TABLE  = var.users_table_name
      AUDIT_TABLE  = var.audit_table_name
      USER_POOL_ID = var.user_pool_id
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.usuarios_lambda,
    aws_iam_role_policy.usuarios_lambda
  ]

  tags = merge(var.common_tags, { Module = "Usuarios" })
}

resource "aws_api_gateway_resource" "usuarios" {
  rest_api_id = var.rest_api_id
  parent_id   = var.root_resource_id
  path_part   = "usuarios"
}

resource "aws_api_gateway_resource" "user" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.usuarios.id
  path_part   = "{userId}"
}

resource "aws_api_gateway_resource" "role" {
  rest_api_id = var.rest_api_id
  parent_id   = aws_api_gateway_resource.user.id
  path_part   = "rol"
}

resource "aws_api_gateway_method" "usuarios" {
  for_each = local.routes

  rest_api_id   = var.rest_api_id
  resource_id   = each.value.resource_id
  http_method   = each.value.method
  authorization = "AWS_IAM"
}

resource "aws_api_gateway_integration" "usuarios" {
  for_each = local.routes

  rest_api_id             = var.rest_api_id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.usuarios[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.usuarios_lambda.invoke_arn
}

resource "aws_lambda_permission" "api_gateway" {
  for_each = local.routes

  statement_id  = "AllowSharedApi-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.usuarios_lambda.function_name
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
    "method.response.header.Access-Control-Allow-Methods" = "'GET,PUT,PATCH,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_integration.options]
}

resource "aws_iam_policy" "api" {
  for_each = {
    ADMINISTRADOR = [
      "${var.execution_arn}/${var.stage_name}/GET/usuarios",
      "${var.execution_arn}/${var.stage_name}/GET/usuarios/*",
      "${var.execution_arn}/${var.stage_name}/PUT/usuarios/*",
      "${var.execution_arn}/${var.stage_name}/DELETE/usuarios/*",
      "${var.execution_arn}/${var.stage_name}/PATCH/usuarios/*/rol"
    ]
    OPERADOR = [
      "${var.execution_arn}/${var.stage_name}/GET/usuarios/*",
      "${var.execution_arn}/${var.stage_name}/PUT/usuarios/*"
    ]
    CLIENTE = [
      "${var.execution_arn}/${var.stage_name}/GET/usuarios/*",
      "${var.execution_arn}/${var.stage_name}/PUT/usuarios/*"
    ]
  }

  name        = "${var.name_prefix}-usuarios-${lower(each.key)}"
  description = "Invocación mínima de Usuarios para ${each.key}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "execute-api:Invoke"
      Resource = each.value
    }]
  })
}
