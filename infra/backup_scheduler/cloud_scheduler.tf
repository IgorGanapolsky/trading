# Google Cloud Scheduler Backup Configuration
#
# This Terraform config sets up Cloud Scheduler as a backup to GitHub Actions.
# Cloud Scheduler calls a Cloud Run service which runs the trading script.
#
# Prerequisites:
# 1. GCP project with Cloud Scheduler and Cloud Run enabled
# 2. Service account with run.invoker role
# 3. Cloud Run service deployed (see cloud_run.tf)
#
# Usage:
#   cd infra/backup_scheduler
#   terraform init
#   terraform plan -var="project_id=YOUR_PROJECT"
#   terraform apply -var="project_id=YOUR_PROJECT"
#
# Cost: ~$0.10/month for Cloud Scheduler + Cloud Run invocations
# Well within the $100/month budget.

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "trading_service_url" {
  description = "URL of the Cloud Run trading service"
  type        = string
  default     = ""  # Set after deploying Cloud Run
}

# Enable required APIs
resource "google_project_service" "cloudscheduler" {
  project = var.project_id
  service = "cloudscheduler.googleapis.com"
}

resource "google_project_service" "cloudrun" {
  project = var.project_id
  service = "run.googleapis.com"
}

# Service account for scheduler
resource "google_service_account" "scheduler_sa" {
  account_id   = "trading-backup-scheduler"
  display_name = "Trading Backup Scheduler"
  project      = var.project_id
}

# Grant invoker role to scheduler service account
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  count    = var.trading_service_url != "" ? 1 : 0
  project  = var.project_id
  location = var.region
  service  = "trading-backup"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_sa.email}"
}

# Weekday trading backup (every 30 mins, 9:30 AM - 4:00 PM ET)
# UTC offset: 14:30 - 21:00 UTC (EST) or 13:30 - 20:00 UTC (EDT)
resource "google_cloud_scheduler_job" "weekday_trading_backup" {
  name        = "weekday-trading-backup"
  description = "Backup scheduler for weekday trading (if GitHub Actions fails)"
  project     = var.project_id
  region      = var.region
  schedule    = "*/30 14-21 * * 1-5"  # Every 30 mins, Mon-Fri, 9:30 AM - 4 PM ET
  time_zone   = "America/New_York"

  retry_config {
    retry_count          = 3
    min_backoff_duration = "60s"
    max_backoff_duration = "300s"
  }

  http_target {
    http_method = "POST"
    uri         = var.trading_service_url != "" ? "${var.trading_service_url}/run" : "https://placeholder.run.app/run"
    body        = base64encode(jsonencode({
      source = "cloud_scheduler_backup"
      check_github_actions = true
    }))
    headers = {
      "Content-Type" = "application/json"
    }
    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }

  depends_on = [google_project_service.cloudscheduler]
}

# Weekend crypto trading backup (every 4 hours)
resource "google_cloud_scheduler_job" "weekend_crypto_backup" {
  name        = "weekend-crypto-backup"
  description = "Backup scheduler for 24/7 crypto trading"
  project     = var.project_id
  region      = var.region
  schedule    = "0 */4 * * 0,6"  # Every 4 hours on Sat/Sun
  time_zone   = "UTC"

  retry_config {
    retry_count = 2
  }

  http_target {
    http_method = "POST"
    uri         = var.trading_service_url != "" ? "${var.trading_service_url}/run" : "https://placeholder.run.app/run"
    body        = base64encode(jsonencode({
      source = "cloud_scheduler_crypto_backup"
      crypto_only = true
    }))
    headers = {
      "Content-Type" = "application/json"
    }
    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }

  depends_on = [google_project_service.cloudscheduler]
}

# Heartbeat check (every 15 mins - checks if GitHub Actions is healthy)
resource "google_cloud_scheduler_job" "heartbeat_check" {
  name        = "trading-heartbeat-check"
  description = "Monitor GitHub Actions health and alert if stale"
  project     = var.project_id
  region      = var.region
  schedule    = "*/15 * * * *"  # Every 15 minutes
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = var.trading_service_url != "" ? "${var.trading_service_url}/health" : "https://placeholder.run.app/health"
    body        = base64encode(jsonencode({
      check = "github_actions_heartbeat"
    }))
    headers = {
      "Content-Type" = "application/json"
    }
    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }

  depends_on = [google_project_service.cloudscheduler]
}

output "scheduler_service_account" {
  value = google_service_account.scheduler_sa.email
}

output "weekday_job_name" {
  value = google_cloud_scheduler_job.weekday_trading_backup.name
}

output "crypto_job_name" {
  value = google_cloud_scheduler_job.weekend_crypto_backup.name
}
