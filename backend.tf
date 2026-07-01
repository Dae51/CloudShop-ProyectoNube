terraform {

  backend "s3" {

    bucket = "cloudshop-terraform-esen2026"

    key = "terraform.tfstate"

    region = "us-east-2"

  }

}


