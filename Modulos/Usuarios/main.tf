resource "aws_dynamodb_table" "users" {

  name         = "Users"
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "userId"

  attribute {

    name = "userId"
    type = "S"

  }

}

resource "aws_iam_role" "usuarios_lambda_role" {

  name = "usuarios-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Action = "sts:AssumeRole"

        Effect = "Allow"

        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

}

resource "aws_iam_policy" "usuarios_policy" {

  name = "usuarios-policy"

  policy = jsonencode({

    Version = "2012-10-17"

    Statement = [

      {
        Effect = "Allow"

        Action = [

          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Scan"

        ]

        Resource = aws_dynamodb_table.users.arn

      },

      {
        Effect = "Allow"

        Action = [

          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"

        ]

        Resource = "*"

      }

    ]

  })

}


resource "aws_iam_role_policy_attachment" "usuarios_attach" {

  role = aws_iam_role.usuarios_lambda_role.name

  policy_arn = aws_iam_policy.usuarios_policy.arn

}

resource "aws_lambda_function" "usuarios_lambda" {

  function_name = "usuarios-lambda"

  filename = "${path.module}/lambda.zip"

  source_code_hash = filebase64sha256("${path.module}/lambda.zip")

  handler = "lambda_function.lambda_handler"

  runtime = "python3.12"

  role = aws_iam_role.usuarios_lambda_role.arn

}

resource "aws_api_gateway_rest_api" "usuarios_api" {

  name = "usuarios-api"

}

resource "aws_api_gateway_resource" "users" {

  rest_api_id = aws_api_gateway_rest_api.usuarios_api.id

  parent_id = aws_api_gateway_rest_api.usuarios_api.root_resource_id

  path_part = "users"

}

resource "aws_api_gateway_method" "get_users" {

  rest_api_id = aws_api_gateway_rest_api.usuarios_api.id

  resource_id = aws_api_gateway_resource.users.id

  http_method = "GET"

  authorization = "NONE"

}

resource "aws_api_gateway_integration" "get_users" {

  rest_api_id = aws_api_gateway_rest_api.usuarios_api.id

  resource_id = aws_api_gateway_resource.users.id

  http_method = aws_api_gateway_method.get_users.http_method

  integration_http_method = "POST"

  type = "AWS_PROXY"

  uri = aws_lambda_function.usuarios_lambda.invoke_arn

}

resource "aws_lambda_permission" "api_gateway" {

  statement_id = "AllowExecutionFromAPIGateway"

  action = "lambda:InvokeFunction"

  function_name = aws_lambda_function.usuarios_lambda.function_name

  principal = "apigateway.amazonaws.com"

  source_arn = "${aws_api_gateway_rest_api.usuarios_api.execution_arn}/*/*"

}

resource "aws_api_gateway_deployment" "usuarios" {

  depends_on = [

    aws_api_gateway_integration.get_users

  ]

  rest_api_id = aws_api_gateway_rest_api.usuarios_api.id

  stage_name = "dev"

}