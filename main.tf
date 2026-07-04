# archivo raiz de terraform


module "usuarios" {
  source = "./Modulos/Usuarios"
}

module "productos" {
  source = "./Modulos/Productos"
}

output "productos_api_url" {
  description = "URL base de la API del módulo de productos"
  value       = module.productos.api_url
}
