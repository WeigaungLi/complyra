# AWS Account Onboarding (From Zero)

This guide is for users who do not have an AWS account yet.

## What cannot be automated by this repository

The following actions must be completed by you in the AWS web console:

- Register an AWS account
- Complete phone verification and payment method verification
- Configure billing alerts and budget limits
- Enable MFA for the root user
- Create IAM admin user and access keys

## Step 1: Create an AWS account

1. Open `https://aws.amazon.com/` and click **Create an AWS Account**.
2. Use an email you control long-term.
3. Complete identity verification and payment method setup.
4. Choose **Basic Support** if you are starting with MVP cost control.

## Step 2: Secure the root account immediately

1. Sign in as root user once.
2. Enable MFA on root user.
3. Do not use root access keys.
4. Keep root credentials in a secure offline store.

## Step 3: Configure billing guardrails

1. Open **Billing and Cost Management**.
2. Enable billing alerts.
3. Create a monthly budget with alert thresholds (for example 50%, 80%, 100%).
4. Add an alert email you monitor daily.

## Step 4: Create IAM admin user for daily operations

1. Open **IAM** -> **Users** -> **Create user**.
2. Grant admin permissions (for MVP phase only).
3. Create programmatic access key for CLI usage.
4. Save the key securely (do not commit it to source control).

## Step 5: Configure local AWS CLI

Run on your machine:

```bash
aws configure
aws sts get-caller-identity
```

Expected: account identity JSON is returned.

## Step 6: Run Complyra automation scripts

From repository root:

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/00_preflight.sh
./scripts/aws/01_prepare_prod_env.sh
./scripts/aws/04_validate_env_prod.sh
./scripts/aws/02_bootstrap_ecr.sh
./scripts/aws/03_build_and_push.sh
./scripts/aws/07_terraform_plan.sh
./scripts/iac/01_conftest_check.sh
./scripts/aws/08_register_taskdefs_from_release.sh <release_tag>
./scripts/aws/09_deploy_services_from_release.sh <cluster_name> <release_tag>
```

## China-specific note

If you are in mainland China and do not require mainland hosting compliance initially, start with `ap-southeast-1`.
Use `aws-cn` regions only when your legal and compliance requirements require mainland deployment.
