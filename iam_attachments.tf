resource "aws_iam_role_policy_attachment" "usuarios_identity" {
  for_each = module.usuarios.api_role_policy_arns

  role       = module.autenticacion.role_names[each.key]
  policy_arn = each.value
}

resource "aws_iam_role_policy_attachment" "productos_identity" {
  for_each = module.productos.api_role_policy_arns

  role       = module.autenticacion.role_names[upper(each.key)]
  policy_arn = each.value
}
