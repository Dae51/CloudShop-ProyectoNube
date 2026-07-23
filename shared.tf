data "archive_file" "common_layer" {
  type        = "zip"
  source_dir  = "${path.module}/Modulos/Shared"
  output_path = "${path.module}/Modulos/Shared/common_layer.zip"
}

resource "aws_lambda_layer_version" "common" {
  layer_name          = "${local.name_prefix}-common"
  filename            = data.archive_file.common_layer.output_path
  source_code_hash    = data.archive_file.common_layer.output_base64sha256
  compatible_runtimes = ["python3.12"]
  description         = "Runtime común: identidad, roles, errores y correlation IDs"
}
