locals {
  roles = {
    ADMINISTRADOR = {
      name = "${var.name_prefix}-administrador"
    }
    OPERADOR = {
      name = "${var.name_prefix}-operador"
    }
    CLIENTE = {
      name = "${var.name_prefix}-cliente"
    }
  }
  post_confirmation_name = "${var.name_prefix}-post-confirmation"
}

resource "aws_dynamodb_table" "users" {
  name         = "${var.name_prefix}-users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"

  attribute {
    name = "userId"
    type = "S"
  }

  attribute {
    name = "email"
    type = "S"
  }

  global_secondary_index {
    name            = "EmailIndex"
    hash_key        = "email"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = merge(var.common_tags, { Module = "Autenticacion" })
}

resource "aws_dynamodb_table" "audit" {
  name         = "${var.name_prefix}-audit"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "auditId"

  attribute {
    name = "auditId"
    type = "S"
  }

  attribute {
    name = "resourceKey"
    type = "S"
  }

  attribute {
    name = "occurredAt"
    type = "S"
  }

  attribute {
    name = "correlationId"
    type = "S"
  }

  global_secondary_index {
    name            = "ResourceOccurredAtIndex"
    hash_key        = "resourceKey"
    range_key       = "occurredAt"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "CorrelationIndex"
    hash_key        = "correlationId"
    range_key       = "occurredAt"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = merge(var.common_tags, { Module = "Auditoria" })
}

resource "aws_dynamodb_table" "idempotency" {
  name         = "${var.name_prefix}-idempotency"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "idempotencyKey"

  attribute {
    name = "idempotencyKey"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = merge(var.common_tags, { Module = "Idempotencia" })
}

data "archive_file" "post_confirmation" {
  type        = "zip"
  source_file = "${path.module}/lambda/post_confirmation.py"
  output_path = "${path.module}/post_confirmation.zip"
}

resource "aws_iam_role" "post_confirmation" {
  name = "${local.post_confirmation_name}-role"

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

resource "aws_cloudwatch_log_group" "post_confirmation" {
  name              = "/aws/lambda/${local.post_confirmation_name}"
  retention_in_days = var.log_retention_days
  tags              = var.common_tags
}

resource "aws_iam_role_policy" "post_confirmation_base" {
  name = "${local.post_confirmation_name}-base"
  role = aws_iam_role.post_confirmation.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadExistingUser"
        Effect   = "Allow"
        Action   = "dynamodb:GetItem"
        Resource = aws_dynamodb_table.users.arn
      },
      {
        Sid      = "CreateUserAndAudit"
        Effect   = "Allow"
        Action   = "dynamodb:PutItem"
        Resource = [aws_dynamodb_table.users.arn, aws_dynamodb_table.audit.arn]
      },
      {
        Sid    = "WriteLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.post_confirmation.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "post_confirmation_group" {
  name = "${local.post_confirmation_name}-group"
  role = aws_iam_role.post_confirmation.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "AssignDefaultClientGroup"
      Effect   = "Allow"
      Action   = "cognito-idp:AdminAddUserToGroup"
      Resource = aws_cognito_user_pool.cloudshop.arn
    }]
  })
}

resource "aws_lambda_function" "post_confirmation" {
  function_name    = local.post_confirmation_name
  filename         = data.archive_file.post_confirmation.output_path
  source_code_hash = data.archive_file.post_confirmation.output_base64sha256
  handler          = "post_confirmation.lambda_handler"
  runtime          = "python3.12"
  role             = aws_iam_role.post_confirmation.arn
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      USERS_TABLE = aws_dynamodb_table.users.name
      AUDIT_TABLE = aws_dynamodb_table.audit.name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.post_confirmation,
    aws_iam_role_policy.post_confirmation_base
  ]

  tags = merge(var.common_tags, { Module = "Autenticacion" })
}

resource "aws_lambda_permission" "cognito_post_confirmation" {
  statement_id  = "AllowCognitoPostConfirmation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.post_confirmation.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.cloudshop.arn
}

resource "aws_cognito_user_pool" "cloudshop" {
  name                     = "${var.name_prefix}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 3
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  user_attribute_update_settings {
    attributes_require_verification_before_update = ["email"]
  }

  lambda_config {
    post_confirmation = aws_lambda_function.post_confirmation.arn
  }

  schema {
    name                = "name"
    attribute_data_type = "String"
    mutable             = true
    required            = true

    string_attribute_constraints {
      min_length = 1
      max_length = 160
    }
  }

  tags = merge(var.common_tags, { Module = "Autenticacion" })
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "${var.name_prefix}-web"
  user_pool_id = aws_cognito_user_pool.cloudshop.id

  generate_secret                      = false
  prevent_user_existence_errors        = "ENABLED"
  supported_identity_providers         = ["COGNITO"]
  explicit_auth_flows                  = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  enable_token_revocation              = true
  access_token_validity                = 60
  id_token_validity                    = 60
  refresh_token_validity               = 7
  allowed_oauth_flows_user_pool_client = false

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  read_attributes  = ["email", "email_verified", "name"]
  write_attributes = ["email", "name"]
}

resource "aws_cognito_identity_pool" "cloudshop" {
  identity_pool_name               = replace("${var.name_prefix}-identities", "-", "_")
  allow_unauthenticated_identities = false

  cognito_identity_providers {
    client_id               = aws_cognito_user_pool_client.web.id
    provider_name           = aws_cognito_user_pool.cloudshop.endpoint
    server_side_token_check = true
  }

  tags = merge(var.common_tags, { Module = "Autenticacion" })
}

data "aws_iam_policy_document" "identity_role_trust" {
  for_each = local.roles

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = ["cognito-identity.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "cognito-identity.amazonaws.com:aud"
      values   = [aws_cognito_identity_pool.cloudshop.id]
    }

    condition {
      test     = "ForAnyValue:StringLike"
      variable = "cognito-identity.amazonaws.com:amr"
      values   = ["authenticated"]
    }
  }
}

resource "aws_iam_role" "identity" {
  for_each = local.roles

  name               = each.value.name
  assume_role_policy = data.aws_iam_policy_document.identity_role_trust[each.key].json
  tags               = merge(var.common_tags, { CloudShopRole = each.key })
}

resource "aws_cognito_user_group" "role" {
  for_each = local.roles

  name         = each.key
  user_pool_id = aws_cognito_user_pool.cloudshop.id
  description  = "Rol oficial CloudShop ${each.key}"
  precedence   = 0
  role_arn     = aws_iam_role.identity[each.key].arn
}

resource "aws_cognito_identity_pool_roles_attachment" "cloudshop" {
  identity_pool_id = aws_cognito_identity_pool.cloudshop.id

  roles = {
    authenticated = aws_iam_role.identity["CLIENTE"].arn
  }

  role_mapping {
    identity_provider         = "${aws_cognito_user_pool.cloudshop.endpoint}:${aws_cognito_user_pool_client.web.id}"
    ambiguous_role_resolution = "Deny"
    type                      = "Token"
  }
}
