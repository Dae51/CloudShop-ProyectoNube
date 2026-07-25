locals {
  observable_lambda_names = toset([
    module.autenticacion.post_confirmation_lambda_name,
    module.usuarios.lambda_function_name,
    module.productos.lambda_function_name,
    module.tiendas.lambda_function_name,
    module.carritos.lambda_function_name,
    module.pedidos.lambda_function_name,
    module.pedidos.relay_lambda_name,
    module.pedidos.notification_lambda_name,
    module.reportes.lambda_function_name,
  ])
}

resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.cloudshop.id
  stage_name  = aws_api_gateway_stage.cloudshop.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled        = true
    data_trace_enabled     = false
    logging_level          = "OFF"
    throttling_burst_limit = 200
    throttling_rate_limit  = 100
  }
}

resource "aws_wafv2_web_acl" "api" {
  name        = "${local.name_prefix}-api"
  description = "Proteccion regional de API Gateway CloudShop"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "RateLimitByIp"
    priority = 0
    action {
      block {}
    }
    statement {
      rate_based_statement {
        aggregate_key_type = "IP"
        limit              = var.waf_rate_limit
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedCommon"
    priority = 10
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-common-rules"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedKnownBadInputs"
    priority = 20
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-known-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name_prefix}-api-waf"
    sampled_requests_enabled   = true
  }

  tags = merge(local.common_tags, { Module = "Seguridad" })
}

resource "aws_wafv2_web_acl_association" "api" {
  resource_arn = aws_api_gateway_stage.cloudshop.arn
  web_acl_arn  = aws_wafv2_web_acl.api.arn
}

resource "aws_cloudwatch_log_group" "waf" {
  name              = "aws-waf-logs-${local.name_prefix}-api"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags, { Module = "Seguridad" })
}

resource "aws_wafv2_web_acl_logging_configuration" "api" {
  log_destination_configs = [aws_cloudwatch_log_group.waf.arn]
  resource_arn            = aws_wafv2_web_acl.api.arn

  redacted_fields {
    single_header {
      name = "authorization"
    }
  }

  redacted_fields {
    single_header {
      name = "x-amz-security-token"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "authentication_errors" {
  for_each = local.observable_lambda_names

  name           = "cloudshop-authentication-errors"
  pattern        = "{ $.statusCode = 401 }"
  log_group_name = "/aws/lambda/${each.value}"

  metric_transformation {
    name      = "AuthenticationErrors"
    namespace = "CloudShop"
    value     = "1"
  }

  depends_on = [
    module.autenticacion,
    module.usuarios,
    module.productos,
    module.tiendas,
    module.carritos,
    module.pedidos,
    module.reportes,
  ]
}

resource "aws_cloudwatch_log_metric_filter" "application_errors" {
  for_each = local.observable_lambda_names

  name           = "cloudshop-application-errors"
  pattern        = "{ $.statusCode >= 500 }"
  log_group_name = "/aws/lambda/${each.value}"

  metric_transformation {
    name      = "ApplicationErrors"
    namespace = "CloudShop"
    value     = "1"
  }

  depends_on = [
    module.autenticacion,
    module.usuarios,
    module.productos,
    module.tiendas,
    module.carritos,
    module.pedidos,
    module.reportes,
  ]
}

resource "aws_cloudwatch_dashboard" "cloudshop" {
  dashboard_name = "${local.name_prefix}-operations"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "API Gateway: tráfico y errores"
          region  = var.aws_region
          view    = "timeSeries"
          stacked = false
          period  = 300
          stat    = "Sum"
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiName", aws_api_gateway_rest_api.cloudshop.name, "Stage", aws_api_gateway_stage.cloudshop.stage_name],
            [".", "4XXError", ".", ".", ".", "."],
            [".", "5XXError", ".", ".", ".", "."],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "API Gateway: latencia promedio"
          region = var.aws_region
          view   = "timeSeries"
          period = 300
          stat   = "Average"
          metrics = [
            ["AWS/ApiGateway", "Latency", "ApiName", aws_api_gateway_rest_api.cloudshop.name, "Stage", aws_api_gateway_stage.cloudshop.stage_name],
            [".", "IntegrationLatency", ".", ".", ".", "."],
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Errores de autenticación y aplicación"
          region = var.aws_region
          view   = "timeSeries"
          period = 300
          stat   = "Sum"
          metrics = [
            ["CloudShop", "AuthenticationErrors"],
            [".", "ApplicationErrors"],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Errores Lambda por función"
          region = var.aws_region
          view   = "timeSeries"
          period = 300
          stat   = "Sum"
          metrics = [
            for function_name in sort(tolist(local.observable_lambda_names)) :
            ["AWS/Lambda", "Errors", "FunctionName", function_name]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 24
        height = 6
        properties = {
          title  = "WAF: solicitudes permitidas y bloqueadas"
          region = var.aws_region
          view   = "timeSeries"
          period = 300
          stat   = "Sum"
          metrics = [
            ["AWS/WAFV2", "AllowedRequests", "WebACL", aws_wafv2_web_acl.api.name, "Region", var.aws_region, "Rule", "ALL"],
            [".", "BlockedRequests", ".", ".", ".", ".", ".", "."],
          ]
        }
      },
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${local.name_prefix}-api-5xx"
  alarm_description   = "API CloudShop produjo errores de servidor"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5XXError"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    ApiName = aws_api_gateway_rest_api.cloudshop.name
    Stage   = aws_api_gateway_stage.cloudshop.stage_name
  }
  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "api_4xx" {
  alarm_name          = "${local.name_prefix}-api-4xx-spike"
  alarm_description   = "Pico de rechazos de autenticación, autorización o entrada"
  namespace           = "AWS/ApiGateway"
  metric_name         = "4XXError"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    ApiName = aws_api_gateway_rest_api.cloudshop.name
    Stage   = aws_api_gateway_stage.cloudshop.stage_name
  }
  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "api_latency" {
  alarm_name          = "${local.name_prefix}-api-latency"
  alarm_description   = "Latencia promedio de API superior a dos segundos"
  namespace           = "AWS/ApiGateway"
  metric_name         = "Latency"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 2000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    ApiName = aws_api_gateway_rest_api.cloudshop.name
    Stage   = aws_api_gateway_stage.cloudshop.stage_name
  }
  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "application_errors" {
  alarm_name          = "${local.name_prefix}-application-errors"
  alarm_description   = "Errores 5XX estructurados en funciones CloudShop"
  namespace           = "CloudShop"
  metric_name         = "ApplicationErrors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  tags                = local.common_tags
}
