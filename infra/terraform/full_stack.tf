data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "ecs_tasks_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${local.name_prefix}-ecs-task-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json
  tags               = local.tags
}

resource "aws_iam_role" "ecs_task" {
  name               = "${local.name_prefix}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_ssm" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess"
}

resource "aws_iam_role_policy_attachment" "ecs_task_xray" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

resource "random_password" "jwt_secret" {
  length  = 48
  special = false
}

resource "aws_secretsmanager_secret" "jwt" {
  name        = "${local.name_prefix}/app/jwt"
  description = "JWT secret for Complyra API"
  tags        = local.tags
}

resource "aws_secretsmanager_secret_version" "jwt" {
  secret_id     = aws_secretsmanager_secret.jwt.id
  secret_string = var.jwt_secret_value != "" ? var.jwt_secret_value : random_password.jwt_secret.result
}

resource "aws_secretsmanager_secret" "sentry" {
  count       = var.app_sentry_dsn != "" ? 1 : 0
  name        = "${local.name_prefix}/app/sentry"
  description = "Sentry DSN for Complyra API"
  tags        = local.tags
}

resource "aws_secretsmanager_secret_version" "sentry" {
  count         = var.app_sentry_dsn != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.sentry[0].id
  secret_string = var.app_sentry_dsn
}

locals {
  ecr_registry = var.ecr_registry != "" ? var.ecr_registry : "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"

  db_endpoint = aws_db_instance.postgres.address
  database_url = "postgresql+psycopg://${var.db_username}:${urlencode(var.db_password)}@${local.db_endpoint}:5432/${var.db_name}"

  redis_endpoint  = aws_elasticache_replication_group.redis.primary_endpoint_address
  redis_url_local = "redis://${local.redis_endpoint}:6379/0"
  redis_url       = var.app_redis_url_override != "" ? var.app_redis_url_override : local.redis_url_local

  sentry_secret_arn = var.app_sentry_dsn != "" ? aws_secretsmanager_secret.sentry[0].arn : ""

  api_container_secrets = concat(
    [
      {
        name      = "APP_JWT_SECRET_KEY"
        valueFrom = aws_secretsmanager_secret.jwt.arn
      }
    ],
    var.app_sentry_dsn != "" ? [
      {
        name      = "APP_SENTRY_DSN"
        valueFrom = local.sentry_secret_arn
      }
    ] : []
  )
}

data "aws_iam_policy_document" "ecs_task_secrets_access" {
  statement {
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]

    resources = compact([
      aws_secretsmanager_secret.jwt.arn,
      local.sentry_secret_arn,
    ])
  }
}

resource "aws_iam_role_policy" "ecs_task_secrets_access" {
  name   = "${local.name_prefix}-ecs-task-secrets-access"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.ecs_task_secrets_access.json
}

resource "aws_db_subnet_group" "postgres" {
  name       = "${local.name_prefix}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-db-subnet-group"
  })
}

resource "aws_db_instance" "postgres" {
  identifier                   = "${local.name_prefix}-postgres"
  engine                       = "postgres"
  engine_version               = var.db_engine_version
  instance_class               = var.db_instance_class
  allocated_storage            = var.db_allocated_storage
  max_allocated_storage        = var.db_max_allocated_storage
  storage_type                 = "gp3"
  storage_encrypted            = true
  db_name                      = var.db_name
  username                     = var.db_username
  password                     = var.db_password
  port                         = 5432
  db_subnet_group_name         = aws_db_subnet_group.postgres.name
  vpc_security_group_ids       = [aws_security_group.rds.id]
  backup_retention_period      = var.db_backup_retention_days
  maintenance_window           = var.db_maintenance_window
  backup_window                = var.db_backup_window
  multi_az                     = var.db_multi_az
  deletion_protection          = var.db_deletion_protection
  skip_final_snapshot          = var.db_skip_final_snapshot
  final_snapshot_identifier    = var.db_skip_final_snapshot ? null : "${local.name_prefix}-postgres-final"
  auto_minor_version_upgrade   = true
  publicly_accessible          = false
  apply_immediately            = var.db_apply_immediately
  performance_insights_enabled = var.db_performance_insights_enabled

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-postgres"
  })
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name_prefix}-redis-subnet-group"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${local.name_prefix}-redis"
  description                = "Redis cache for Complyra"
  node_type                  = var.redis_node_type
  port                       = 6379
  engine                     = "redis"
  engine_version             = var.redis_engine_version
  parameter_group_name       = var.redis_parameter_group_name
  num_cache_clusters         = var.redis_num_cache_clusters
  automatic_failover_enabled = var.redis_num_cache_clusters > 1
  multi_az_enabled           = var.redis_num_cache_clusters > 1
  at_rest_encryption_enabled = var.redis_at_rest_encryption_enabled
  transit_encryption_enabled = var.redis_transit_encryption_enabled
  auth_token                 = var.redis_auth_token != "" ? var.redis_auth_token : null
  security_group_ids         = [aws_security_group.redis.id]
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  apply_immediately          = var.redis_apply_immediately

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-redis"
  })
}

resource "aws_lb" "app" {
  name                       = "${local.name_prefix}-alb"
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = aws_subnet.public[*].id
  drop_invalid_header_fields = true

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-alb"
  })
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name_prefix}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.this.id

  health_check {
    path                = "/api/health/live"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-api-tg"
  })
}

resource "aws_lb_target_group" "web" {
  name        = "${local.name_prefix}-web-tg"
  port        = 80
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.this.id

  health_check {
    path                = "/healthz"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-web-tg"
  })
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_listener_rule" "api_http" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    path_pattern {
      values = ["/api/*", "/docs", "/openapi.json"]
    }
  }
}

resource "aws_lb_listener" "https" {
  count             = var.acm_certificate_arn != "" ? 1 : 0
  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_listener_rule" "api_https" {
  count        = var.acm_certificate_arn != "" ? 1 : 0
  listener_arn = aws_lb_listener.https[0].arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    path_pattern {
      values = ["/api/*", "/docs", "/openapi.json"]
    }
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name_prefix}-api"
  retention_in_days = var.log_retention_days
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.name_prefix}-worker"
  retention_in_days = var.log_retention_days
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "web" {
  name              = "/ecs/${local.name_prefix}-web"
  retention_in_days = var.log_retention_days
  tags              = local.tags
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.api_task_cpu)
  memory                   = tostring(var.api_task_memory)
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "${local.name_prefix}-api"
      image     = "${local.ecr_registry}/complyra-api:${var.image_tag}"
      essential = true
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      environment = [
        { name = "APP_ENV", value = var.app_env },
        { name = "APP_LOG_LEVEL", value = var.app_log_level },
        { name = "APP_LOG_FORMAT", value = var.app_log_format },
        { name = "APP_DATABASE_URL", value = local.database_url },
        { name = "APP_REDIS_URL", value = local.redis_url },
        { name = "APP_QDRANT_URL", value = var.app_qdrant_url },
        { name = "APP_OLLAMA_BASE_URL", value = var.app_ollama_base_url },
        { name = "APP_OLLAMA_MODEL", value = var.app_ollama_model },
        { name = "APP_CORS_ORIGINS", value = var.app_cors_origins },
        { name = "APP_TRUSTED_HOSTS", value = var.app_trusted_hosts },
        { name = "APP_COOKIE_SECURE", value = "true" },
        { name = "APP_REQUIRE_APPROVAL", value = var.app_require_approval ? "true" : "false" },
        { name = "APP_OUTPUT_POLICY_ENABLED", value = var.app_output_policy_enabled ? "true" : "false" },
        { name = "APP_OUTPUT_POLICY_BLOCK_PATTERNS", value = var.app_output_policy_block_patterns },
        { name = "APP_OUTPUT_POLICY_BLOCK_MESSAGE", value = var.app_output_policy_block_message },
      ]
      secrets = local.api_container_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live').read()\" || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.worker_task_cpu)
  memory                   = tostring(var.worker_task_memory)
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "${local.name_prefix}-worker"
      image     = "${local.ecr_registry}/complyra-api:${var.image_tag}"
      essential = true
      command   = ["rq", "worker", "ingest", "--url", local.redis_url]
      environment = [
        { name = "APP_ENV", value = var.app_env },
        { name = "APP_LOG_LEVEL", value = var.app_log_level },
        { name = "APP_LOG_FORMAT", value = var.app_log_format },
        { name = "APP_DATABASE_URL", value = local.database_url },
        { name = "APP_REDIS_URL", value = local.redis_url },
        { name = "APP_QDRANT_URL", value = var.app_qdrant_url },
        { name = "APP_OLLAMA_BASE_URL", value = var.app_ollama_base_url },
        { name = "APP_OLLAMA_MODEL", value = var.app_ollama_model },
        { name = "APP_COOKIE_SECURE", value = "true" },
      ]
      secrets = [
        {
          name      = "APP_JWT_SECRET_KEY"
          valueFrom = aws_secretsmanager_secret.jwt.arn
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${local.name_prefix}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.web_task_cpu)
  memory                   = tostring(var.web_task_memory)
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "${local.name_prefix}-web"
      image     = "${local.ecr_registry}/complyra-web:${var.image_tag}"
      essential = true
      portMappings = [
        {
          containerPort = 80
          hostPort      = 80
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.web.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "wget -qO- http://127.0.0.1/healthz || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 10
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_service" "api" {
  name            = "${local.name_prefix}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.web.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "${local.name_prefix}-api"
    container_port   = 8000
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 30

  depends_on = [
    aws_lb_listener.http,
    aws_lb_listener_rule.api_http,
  ]

  tags = local.tags
}

resource "aws_ecs_service" "worker" {
  name            = "${local.name_prefix}-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.worker.id]
    assign_public_ip = false
  }

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 200

  tags = local.tags
}

resource "aws_ecs_service" "web" {
  name            = "${local.name_prefix}-web"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = var.web_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "${local.name_prefix}-web"
    container_port   = 80
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 20

  depends_on = [aws_lb_listener.http]

  tags = local.tags
}
