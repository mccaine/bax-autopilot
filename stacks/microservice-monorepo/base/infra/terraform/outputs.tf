output "service_urls" {
  description = "Public URL of each Cloud Run service"
  value       = { for k, s in google_cloud_run_v2_service.svc : k => s.uri }
}

output "db_connection_name" {
  description = "Cloud SQL connection name"
  value       = google_sql_database_instance.db.connection_name
}
