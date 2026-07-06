variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Name prefix for all resources"
  type        = string
  default     = "paz-rav"
}

variable "db_password" {
  description = "Postgres master password (set via TF_VAR_db_password, never commit it)"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Claude API key, stored in Secrets Manager (set via TF_VAR_anthropic_api_key)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "underlyings" {
  description = "Comma-separated underlyings to scan"
  type        = string
  default     = "SPX,SPY,QQQ,IWM,NVDA,MSFT,GOOGL,AMZN,CSCO"
}
