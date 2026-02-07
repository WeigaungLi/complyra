resource "random_string" "synthetics_bucket_suffix" {
  count   = var.enable_synthetics ? 1 : 0
  length  = 8
  upper   = false
  special = false
}

resource "aws_s3_bucket" "synthetics_artifacts" {
  count         = var.enable_synthetics ? 1 : 0
  bucket        = "${local.name_prefix}-synthetics-${random_string.synthetics_bucket_suffix[0].result}"
  force_destroy = var.synthetics_artifacts_force_destroy

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-synthetics-artifacts"
  })
}

resource "aws_s3_bucket_public_access_block" "synthetics_artifacts" {
  count                   = var.enable_synthetics ? 1 : 0
  bucket                  = aws_s3_bucket.synthetics_artifacts[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "synthetics_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["synthetics.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "synthetics" {
  count              = var.enable_synthetics ? 1 : 0
  name               = "${local.name_prefix}-synthetics-role"
  assume_role_policy = data.aws_iam_policy_document.synthetics_assume_role.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "synthetics_managed" {
  count      = var.enable_synthetics ? 1 : 0
  role       = aws_iam_role.synthetics[0].name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchSyntheticsFullAccess"
}

resource "aws_iam_role_policy_attachment" "synthetics_xray" {
  count      = var.enable_synthetics ? 1 : 0
  role       = aws_iam_role.synthetics[0].name
  policy_arn = "arn:aws:iam::aws:policy/AWSXrayWriteOnlyAccess"
}

data "archive_file" "synthetics_login_chat_approval" {
  count       = var.enable_synthetics ? 1 : 0
  type        = "zip"
  source_dir  = "${path.module}/../synthetics/login_chat_approval"
  output_path = "${path.module}/login_chat_approval.zip"
}

resource "aws_synthetics_canary" "login_chat_approval" {
  count                = var.enable_synthetics ? 1 : 0
  name                 = "${local.name_prefix}-login-chat-approval"
  artifact_s3_location = "s3://${aws_s3_bucket.synthetics_artifacts[0].id}/artifacts/"
  execution_role_arn   = aws_iam_role.synthetics[0].arn
  handler              = "index.handler"
  runtime_version      = var.synthetics_runtime_version
  zip_file             = data.archive_file.synthetics_login_chat_approval[0].output_path
  start_canary         = var.synthetics_start_canary

  schedule {
    expression = var.synthetics_schedule_expression
  }

  run_config {
    timeout_in_seconds = var.synthetics_timeout_seconds
    memory_in_mb       = var.synthetics_memory_in_mb
    active_tracing     = var.synthetics_active_tracing

    environment_variables = {
      API_BASE_URL   = var.synthetics_api_base_url
      APP_USERNAME   = var.synthetics_username
      APP_PASSWORD   = var.synthetics_password
      TENANT_ID      = var.synthetics_tenant_id
      CHECK_QUESTION = var.synthetics_check_question
    }
  }

  success_retention_period = var.synthetics_success_retention_days
  failure_retention_period = var.synthetics_failure_retention_days

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-login-chat-approval-canary"
  })

  depends_on = [
    aws_s3_bucket_public_access_block.synthetics_artifacts,
    aws_iam_role_policy_attachment.synthetics_managed,
  ]
}
