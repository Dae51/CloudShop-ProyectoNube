variable "name_prefix" { type = string }
variable "rest_api_id" { type = string }
variable "root_resource_id" { type = string }
variable "execution_arn" { type = string }
variable "stage_name" { type = string }
variable "products_table_name" { type = string }
variable "products_table_arn" { type = string }
variable "stores_table_name" { type = string }
variable "stores_table_arn" { type = string }
variable "carts_table_name" { type = string }
variable "carts_table_arn" { type = string }
variable "audit_table_name" { type = string }
variable "audit_table_arn" { type = string }
variable "idempotency_table_name" { type = string }
variable "idempotency_table_arn" { type = string }
variable "common_layer_arn" { type = string }
variable "log_retention_days" { type = number }
variable "users_table_name" { type = string }
variable "users_table_arn" { type = string }
variable "ses_sender_email" {
  type    = string
  default = ""
}
variable "ses_override_recipient" {
  type    = string
  default = ""
}
variable "common_tags" {
  type    = map(string)
  default = {}
}
