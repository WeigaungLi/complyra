# 你需要手动完成的事项（Manual Actions）

仓库里已经包含了所有“无需 AWS 账号凭据即可自动化执行”的步骤。

## 1. 账号与计费（必须你本人完成）

- 创建 AWS 账号：`https://aws.amazon.com/`
- 完成手机验证和支付方式验证
- 为 root 账号开启 MFA
- 配置预算与计费告警邮箱

## 2. IAM 配置（必须你本人完成）

- 创建日常运维使用的 IAM 管理员用户
- 为该用户创建 Access Key（CLI 使用）
- 在本机运行 `aws configure`

## 3. 本地工具安装（必须你本人完成）

- 安装 AWS CLI v2
- 安装 Docker Desktop 或 Docker Engine

安装后运行：

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/00_preflight.sh
```

## 4. 填写生产环境配置（必须你本人完成）

- 编辑 `/Users/liweiguang/aiagent/complyra/.env.prod`
- 至少替换以下配置项：
  - `APP_CORS_ORIGINS`
  - `APP_TRUSTED_HOSTS`
  - `APP_DATABASE_URL`
  - `APP_REDIS_URL`
  - `APP_QDRANT_URL`
  - `APP_OLLAMA_BASE_URL`
  - `APP_SENTRY_DSN`（可选）

编辑后校验：

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/04_validate_env_prod.sh
```

## 5. 云资源创建（必须你本人完成）

- VPC、子网、路由表、NAT
- 安全组
- RDS PostgreSQL
- ElastiCache Redis
- Qdrant 服务
- Ollama GPU 推理服务
- ECS 集群和服务
- ALB、Route 53、ACM TLS 证书

可选 Terraform 全栈基础设施初始化（网络 + ALB + ECS + RDS + Redis + 巡检）：

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/07_terraform_plan.sh
./scripts/iac/01_conftest_check.sh
```

## 6. 部署命令（脚本已准备好）

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/02_bootstrap_ecr.sh
./scripts/aws/03_build_and_push.sh <release_tag>
./scripts/aws/08_register_taskdefs_from_release.sh <release_tag>
./scripts/aws/09_deploy_services_from_release.sh <cluster_name> <release_tag>
```

## 7. 最终验收

- 打开 `https://api.<your-domain>/api/health/live`
- 打开 `https://api.<your-domain>/api/health/ready`
- 跑通完整流程：登录 -> 上传 -> 提问 -> 审批 -> 审计

可选自动冒烟：

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/05_smoke_test.sh https://api.<your-domain> <username> <password>
```

可选回滚准备：

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/06_prepare_rollback.sh <release_tag>
```

可选蓝绿发布触发（需要先完成 CodeDeploy 配置）：

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/10_trigger_codedeploy_ecs.sh <codedeploy_app_name> <deployment_group_name> <task_definition_arn>
```
