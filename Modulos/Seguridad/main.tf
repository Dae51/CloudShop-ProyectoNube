terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws.global]
    }
  }
}

resource "aws_wafv2_web_acl" "cloudfront" {
  provider    = aws.global
  name        = "cloudshop-cloudfront-web-acl"
  description = "Proteccion WAF global para el frontend CloudFront"
  scope       = "CLOUDFRONT"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
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
      metric_name                = "CloudShopCloudFrontCommonRules"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
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
      metric_name                = "CloudShopCloudFrontKnownBadInputs"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 30

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CloudShopCloudFrontSQLi"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "XSSProtection"
    priority = 40

    action {
      block {}
    }

    statement {
      or_statement {
        statement {
          xss_match_statement {
            field_to_match {
              uri_path {}
            }

            text_transformation {
              priority = 0
              type     = "URL_DECODE"
            }

            text_transformation {
              priority = 1
              type     = "HTML_ENTITY_DECODE"
            }
          }
        }

        statement {
          xss_match_statement {
            field_to_match {
              all_query_arguments {}
            }

            text_transformation {
              priority = 0
              type     = "URL_DECODE"
            }

            text_transformation {
              priority = 1
              type     = "HTML_ENTITY_DECODE"
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CloudShopCloudFrontXSS"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "RateLimitByIP"
    priority = 50

    action {
      block {}
    }

    statement {
      rate_based_statement {
        aggregate_key_type = "IP"
        limit              = var.rate_limit_requests_per_5_minutes
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CloudShopCloudFrontRateLimit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "CloudShopCloudFrontWebACL"
    sampled_requests_enabled   = true
  }

  tags = {
    Module = "Seguridad"
  }
}

resource "aws_wafv2_web_acl" "api_gateway" {
  name        = "cloudshop-api-gateway-web-acl"
  description = "Proteccion WAF regional para APIs de CloudShop"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
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
      metric_name                = "CloudShopApiCommonRules"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
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
      metric_name                = "CloudShopApiKnownBadInputs"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 30

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CloudShopApiSQLi"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "XSSProtection"
    priority = 40

    action {
      block {}
    }

    statement {
      or_statement {
        statement {
          xss_match_statement {
            field_to_match {
              uri_path {}
            }

            text_transformation {
              priority = 0
              type     = "URL_DECODE"
            }

            text_transformation {
              priority = 1
              type     = "HTML_ENTITY_DECODE"
            }
          }
        }

        statement {
          xss_match_statement {
            field_to_match {
              all_query_arguments {}
            }

            text_transformation {
              priority = 0
              type     = "URL_DECODE"
            }

            text_transformation {
              priority = 1
              type     = "HTML_ENTITY_DECODE"
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CloudShopApiXSS"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "RateLimitByIP"
    priority = 50

    action {
      block {}
    }

    statement {
      rate_based_statement {
        aggregate_key_type = "IP"
        limit              = var.rate_limit_requests_per_5_minutes
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CloudShopApiRateLimit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "CloudShopApiGatewayWebACL"
    sampled_requests_enabled   = true
  }

  tags = {
    Module = "Seguridad"
  }
}

resource "aws_wafv2_web_acl_association" "api_gateway" {
  for_each = var.api_gateway_stage_arns

  resource_arn = each.value
  web_acl_arn  = aws_wafv2_web_acl.api_gateway.arn
}
