data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  lambda_function_names = sort(distinct(var.lambda_function_names))
  dynamodb_table_names  = sort(distinct(var.dynamodb_table_names))
  api_gateways = {
    for api in var.api_gateways : api.name => api
  }

  lambda_invocation_metrics = [
    for name in local.lambda_function_names : ["AWS/Lambda", "Invocations", "FunctionName", name]
  ]
  lambda_error_metrics = [
    for name in local.lambda_function_names : ["AWS/Lambda", "Errors", "FunctionName", name]
  ]
  lambda_duration_metrics = [
    for name in local.lambda_function_names : ["AWS/Lambda", "Duration", "FunctionName", name]
  ]

  api_request_metrics = [
    for api in var.api_gateways : ["AWS/ApiGateway", "Count", "ApiName", api.name, "Stage", api.stage_name]
  ]
  api_4xx_metrics = [
    for api in var.api_gateways : ["AWS/ApiGateway", "4XXError", "ApiName", api.name, "Stage", api.stage_name]
  ]
  api_5xx_metrics = [
    for api in var.api_gateways : ["AWS/ApiGateway", "5XXError", "ApiName", api.name, "Stage", api.stage_name]
  ]
  api_latency_metrics = [
    for api in var.api_gateways : ["AWS/ApiGateway", "Latency", "ApiName", api.name, "Stage", api.stage_name]
  ]

  dynamodb_read_metrics = [
    for table in local.dynamodb_table_names : ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", table]
  ]
  dynamodb_write_metrics = [
    for table in local.dynamodb_table_names : ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", table]
  ]

  dashboard_widgets = [
    {
      type   = "metric"
      x      = 0
      y      = 0
      width  = 12
      height = 6
      properties = {
        title   = "Lambda Invocations"
        region  = data.aws_region.current.name
        view    = "timeSeries"
        stacked = false
        period  = 300
        stat    = "Sum"
        metrics = local.lambda_invocation_metrics
      }
    },
    {
      type   = "metric"
      x      = 12
      y      = 0
      width  = 12
      height = 6
      properties = {
        title   = "Lambda Errors"
        region  = data.aws_region.current.name
        view    = "timeSeries"
        stacked = false
        period  = 300
        stat    = "Sum"
        metrics = local.lambda_error_metrics
      }
    },
    {
      type   = "metric"
      x      = 0
      y      = 6
      width  = 24
      height = 6
      properties = {
        title   = "Lambda Duration"
        region  = data.aws_region.current.name
        view    = "timeSeries"
        stacked = false
        period  = 300
        stat    = "Average"
        metrics = local.lambda_duration_metrics
      }
    },
    {
      type   = "metric"
      x      = 0
      y      = 12
      width  = 12
      height = 6
      properties = {
        title   = "API Gateway Requests"
        region  = data.aws_region.current.name
        view    = "timeSeries"
        stacked = false
        period  = 300
        stat    = "Sum"
        metrics = local.api_request_metrics
      }
    },
    {
      type   = "metric"
      x      = 12
      y      = 12
      width  = 12
      height = 6
      properties = {
        title   = "API Gateway 4XX Errors"
        region  = data.aws_region.current.name
        view    = "timeSeries"
        stacked = false
        period  = 300
        stat    = "Sum"
        metrics = local.api_4xx_metrics
      }
    },
    {
      type   = "metric"
      x      = 0
      y      = 18
      width  = 12
      height = 6
      properties = {
        title   = "API Gateway 5XX Errors"
        region  = data.aws_region.current.name
        view    = "timeSeries"
        stacked = false
        period  = 300
        stat    = "Sum"
        metrics = local.api_5xx_metrics
      }
    },
    {
      type   = "metric"
      x      = 12
      y      = 18
      width  = 12
      height = 6
      properties = {
        title   = "API Latency"
        region  = data.aws_region.current.name
        view    = "timeSeries"
        stacked = false
        period  = 300
        stat    = "Average"
        metrics = local.api_latency_metrics
      }
    },
    {
      type   = "metric"
      x      = 0
      y      = 24
      width  = 12
      height = 6
      properties = {
        title   = "DynamoDB Read Capacity"
        region  = data.aws_region.current.name
        view    = "timeSeries"
        stacked = false
        period  = 300
        stat    = "Sum"
        metrics = local.dynamodb_read_metrics
      }
    },
    {
      type   = "metric"
      x      = 12
      y      = 24
      width  = 12
      height = 6
      properties = {
        title   = "DynamoDB Write Capacity"
        region  = data.aws_region.current.name
        view    = "timeSeries"
        stacked = false
        period  = 300
        stat    = "Sum"
        metrics = local.dynamodb_write_metrics
      }
    }
  ]
}

resource "aws_iam_role" "api_gateway_cloudwatch" {
  name = "cloudshop-api-gateway-cloudwatch-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = {
        Service = "apigateway.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy" "api_gateway_cloudwatch" {
  name        = "cloudshop-api-gateway-cloudwatch-policy"
  description = "Permite a API Gateway publicar logs detallados en CloudWatch"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteApiGatewayLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:FilterLogEvents",
          "logs:GetLogEvents",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = aws_iam_policy.api_gateway_cloudwatch.arn
}

resource "aws_api_gateway_account" "cloudwatch" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn

  depends_on = [aws_iam_role_policy_attachment.api_gateway_cloudwatch]
}

resource "aws_api_gateway_method_settings" "all_methods" {
  for_each = local.api_gateways

  rest_api_id = each.value.rest_api_id
  stage_name  = each.value.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled    = true
    logging_level      = "INFO"
    data_trace_enabled = false
  }

  depends_on = [aws_api_gateway_account.cloudwatch]
}

resource "aws_cloudwatch_dashboard" "cloudshop" {
  dashboard_name = var.dashboard_name

  dashboard_body = jsonencode({
    widgets = local.dashboard_widgets
  })
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = toset(local.lambda_function_names)

  alarm_name          = "cloudshop-lambda-${each.value}-errors"
  alarm_description   = "Errores en Lambda ${each.value}"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = each.value }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.lambda_error_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  for_each = local.api_gateways

  alarm_name          = "cloudshop-api-${each.key}-5xx"
  alarm_description   = "Errores 5XX en API Gateway ${each.key}"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5XXError"
  dimensions          = { ApiName = each.value.name, Stage = each.value.stage_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.api_5xx_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions
}

resource "aws_cloudwatch_metric_alarm" "api_latency" {
  for_each = local.api_gateways

  alarm_name          = "cloudshop-api-${each.key}-high-latency"
  alarm_description   = "Latencia alta en API Gateway ${each.key}"
  namespace           = "AWS/ApiGateway"
  metric_name         = "Latency"
  dimensions          = { ApiName = each.value.name, Stage = each.value.stage_name }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = var.api_latency_threshold_ms
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions
}

resource "aws_cloudwatch_metric_alarm" "dynamodb_read_throttles" {
  for_each = toset(local.dynamodb_table_names)

  alarm_name          = "cloudshop-dynamodb-${each.value}-read-throttles"
  alarm_description   = "Throttling de lectura en DynamoDB ${each.value}"
  namespace           = "AWS/DynamoDB"
  metric_name         = "ReadThrottleEvents"
  dimensions          = { TableName = each.value }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.dynamodb_throttle_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions
}

resource "aws_cloudwatch_metric_alarm" "dynamodb_write_throttles" {
  for_each = toset(local.dynamodb_table_names)

  alarm_name          = "cloudshop-dynamodb-${each.value}-write-throttles"
  alarm_description   = "Throttling de escritura en DynamoDB ${each.value}"
  namespace           = "AWS/DynamoDB"
  metric_name         = "WriteThrottleEvents"
  dimensions          = { TableName = each.value }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.dynamodb_throttle_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions
}
