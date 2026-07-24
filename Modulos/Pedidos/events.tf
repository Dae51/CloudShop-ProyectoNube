resource "aws_cloudwatch_event_bus" "orders" {
  name = "${var.name_prefix}-orders"
  tags = merge(var.common_tags, { Module = "Eventos" })
}

data "archive_file" "relay" {
  type        = "zip"
  source_file = "${path.module}/lambda/outbox_relay.py"
  output_path = "${path.module}/outbox_relay_lambda.zip"
}

resource "aws_iam_role" "relay" {
  name = "${local.relay_name}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Action = "sts:AssumeRole",
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = var.common_tags
}

resource "aws_cloudwatch_log_group" "relay" {
  name              = "/aws/lambda/${local.relay_name}"
  retention_in_days = var.log_retention_days
  tags              = var.common_tags
}

resource "aws_iam_role_policy" "relay" {
  name = "${local.relay_name}-policy"
  role = aws_iam_role.relay.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeStream",
          "dynamodb:GetRecords",
          "dynamodb:GetShardIterator",
          "dynamodb:ListStreams"
        ]
        Resource = aws_dynamodb_table.outbox.stream_arn
      },
      {
        Effect   = "Allow"
        Action   = "dynamodb:UpdateItem"
        Resource = aws_dynamodb_table.outbox.arn
      },
      {
        Effect   = "Allow"
        Action   = "events:PutEvents"
        Resource = aws_cloudwatch_event_bus.orders.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.relay.arn}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "relay" {
  function_name    = local.relay_name
  filename         = data.archive_file.relay.output_path
  source_code_hash = data.archive_file.relay.output_base64sha256
  handler          = "outbox_relay.lambda_handler"
  runtime          = "python3.12"
  role             = aws_iam_role.relay.arn
  timeout          = 30
  memory_size      = 256
  environment {
    variables = {
      EVENT_BUS_NAME = aws_cloudwatch_event_bus.orders.name
      OUTBOX_TABLE   = aws_dynamodb_table.outbox.name
    }
  }
  depends_on = [aws_cloudwatch_log_group.relay, aws_iam_role_policy.relay]
  tags       = merge(var.common_tags, { Module = "Eventos" })
}

resource "aws_lambda_event_source_mapping" "outbox" {
  event_source_arn                   = aws_dynamodb_table.outbox.stream_arn
  function_name                      = aws_lambda_function.relay.arn
  starting_position                  = "LATEST"
  batch_size                         = 10
  maximum_batching_window_in_seconds = 1
  maximum_retry_attempts             = 3
  bisect_batch_on_function_error     = true
  function_response_types            = ["ReportBatchItemFailures"]
}

resource "aws_sqs_queue" "event_dlq" {
  name                      = "${var.name_prefix}-event-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = merge(var.common_tags, { Module = "Eventos" })
}

resource "aws_cloudwatch_event_rule" "notifications" {
  name           = "${var.name_prefix}-order-notifications"
  description    = "Eventos de pedido que requieren notificación"
  event_bus_name = aws_cloudwatch_event_bus.orders.name
  event_pattern = jsonencode({
    source      = ["cloudshop.orders"]
    detail-type = ["OrderCreated", "OrderCancelled"]
  })
  tags = merge(var.common_tags, { Module = "Eventos" })
}

resource "aws_sesv2_configuration_set" "cloudshop" {
  configuration_set_name = "${var.name_prefix}-transactional"
}

resource "aws_sesv2_email_identity" "sender" {
  count = var.ses_sender_email == "" ? 0 : 1

  email_identity = var.ses_sender_email
  tags           = merge(var.common_tags, { Module = "Notificaciones" })
}

data "archive_file" "notification" {
  type        = "zip"
  source_file = "${path.module}/lambda/notification.py"
  output_path = "${path.module}/notification_lambda.zip"
}

resource "aws_iam_role" "notification" {
  name = "${local.notification_name}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Action = "sts:AssumeRole",
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = var.common_tags
}

resource "aws_cloudwatch_log_group" "notification" {
  name              = "/aws/lambda/${local.notification_name}"
  retention_in_days = var.log_retention_days
  tags              = var.common_tags
}

resource "aws_iam_role_policy" "notification" {
  name = "${local.notification_name}-policy"
  role = aws_iam_role.notification.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "dynamodb:GetItem"
        Resource = [var.users_table_arn, var.idempotency_table_arn]
      },
      {
        Effect   = "Allow"
        Action   = "dynamodb:UpdateItem"
        Resource = var.idempotency_table_arn
      },
      {
        Effect = "Allow"
        Action = "ses:SendEmail"
        Resource = [
          "arn:aws:ses:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:identity/${var.ses_sender_email == "" ? "unconfigured.invalid" : var.ses_sender_email}",
          "arn:aws:ses:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:configuration-set/${aws_sesv2_configuration_set.cloudshop.configuration_set_name}"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.notification.arn}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "notification" {
  function_name    = local.notification_name
  filename         = data.archive_file.notification.output_path
  source_code_hash = data.archive_file.notification.output_base64sha256
  handler          = "notification.lambda_handler"
  runtime          = "python3.12"
  role             = aws_iam_role.notification.arn
  timeout          = 30
  memory_size      = 256
  environment {
    variables = {
      USERS_TABLE            = var.users_table_name
      IDEMPOTENCY_TABLE      = var.idempotency_table_name
      SES_SENDER             = var.ses_sender_email
      SES_CONFIGURATION_SET  = aws_sesv2_configuration_set.cloudshop.configuration_set_name
      SES_OVERRIDE_RECIPIENT = var.ses_override_recipient
    }
  }
  depends_on = [aws_cloudwatch_log_group.notification, aws_iam_role_policy.notification]
  tags       = merge(var.common_tags, { Module = "Notificaciones" })
}

resource "aws_lambda_permission" "eventbridge_notification" {
  statement_id  = "AllowEventBridgeOrders"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.notification.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.notifications.arn
}

resource "aws_cloudwatch_event_target" "notification" {
  rule           = aws_cloudwatch_event_rule.notifications.name
  event_bus_name = aws_cloudwatch_event_bus.orders.name
  arn            = aws_lambda_function.notification.arn

  retry_policy {
    maximum_event_age_in_seconds = 3600
    maximum_retry_attempts       = 3
  }

  dead_letter_config {
    arn = aws_sqs_queue.event_dlq.arn
  }

  depends_on = [aws_lambda_permission.eventbridge_notification]
}

data "aws_iam_policy_document" "event_dlq" {
  statement {
    effect    = "Allow"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.event_dlq.arn]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.notifications.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "event_dlq" {
  queue_url = aws_sqs_queue.event_dlq.id
  policy    = data.aws_iam_policy_document.event_dlq.json
}
