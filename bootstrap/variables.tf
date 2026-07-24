variable "project_name" {
  description = "Nombre corto del proyecto"
  type        = string
  default     = "cloudshop"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.project_name))
    error_message = "project_name debe usar minúsculas, números y guiones."
  }
}

variable "environment" {
  description = "Ambiente cuyo estado almacenará el bucket"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "environment debe ser dev, test o prod."
  }
}

variable "aws_region" {
  description = "Región del backend y del despliegue CloudShop"
  type        = string
  default     = "us-east-1"
}
