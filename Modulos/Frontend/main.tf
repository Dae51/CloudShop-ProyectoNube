data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  bucket_name = var.bucket_name != "" ? var.bucket_name : "cloudshop-frontend-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.name}"
  origin_id   = "cloudshop-frontend-s3-origin"

  mime_types = {
    html = "text/html"
    css  = "text/css"
    js   = "application/javascript"
    json = "application/json"
    png  = "image/png"
    jpg  = "image/jpeg"
    jpeg = "image/jpeg"
    svg  = "image/svg+xml"
    ico  = "image/x-icon"
  }

  site_files = toset([
    for file in fileset("${path.module}/site", "*") : file
    if !endswith(file, ".tftpl")
  ])
}

resource "aws_s3_bucket" "frontend" {
  bucket = local.bucket_name

  tags = {
    Module = "Frontend"
  }
}

resource "aws_s3_bucket_ownership_controls" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "cloudshop-frontend-oac"
  description                       = "OAC para acceso privado de CloudFront al bucket frontend"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "CloudShop Enterprise frontend"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  web_acl_id          = var.cloudfront_web_acl_arn

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
    origin_id                = local.origin_id
  }

  default_cache_behavior {
    target_origin_id       = local.origin_id
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Module = "Frontend"
  }
}

data "aws_iam_policy_document" "frontend_bucket" {
  statement {
    sid    = "AllowCloudFrontReadOnly"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions = ["s3:GetObject"]

    resources = ["${aws_s3_bucket.frontend.arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = data.aws_iam_policy_document.frontend_bucket.json
}

resource "aws_s3_object" "site_files" {
  for_each = local.site_files

  bucket       = aws_s3_bucket.frontend.id
  key          = each.value
  source       = "${path.module}/site/${each.value}"
  etag         = filemd5("${path.module}/site/${each.value}")
  content_type = lookup(local.mime_types, lower(element(split(".", each.value), length(split(".", each.value)) - 1)), "application/octet-stream")

  depends_on = [aws_s3_bucket_ownership_controls.frontend]
}

resource "aws_s3_object" "config" {
  bucket       = aws_s3_bucket.frontend.id
  key          = "config.js"
  content_type = "application/javascript"
  content = templatefile("${path.module}/site/config.js.tftpl", {
    environment       = var.environment
    usuarios_api_url  = var.usuarios_api_url
    productos_api_url = var.productos_api_url
    tiendas_api_url   = var.tiendas_api_url
    compras_api_url   = var.compras_api_url
    pedidos_api_url   = var.pedidos_api_url
    reportes_api_url  = var.reportes_api_url
  })

  depends_on = [aws_s3_bucket_ownership_controls.frontend]
}
