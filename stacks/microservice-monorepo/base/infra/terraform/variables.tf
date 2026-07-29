variable "project_id" {
  type        = string
  description = "GCP project id"
}

variable "region" {
  type        = string
  description = "GCP region"
  default     = "us-central1"
}

variable "image_tag" {
  type        = string
  description = "Container image tag to deploy"
  default     = "latest"
}

variable "db_password" {
  type        = string
  description = "Password for the app database user"
  default     = "change-me-in-secret-manager"
  sensitive   = true
}
