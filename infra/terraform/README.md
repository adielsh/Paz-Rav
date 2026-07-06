# Paz Rav — AWS Terraform (Stage 1: App Runner)

**Status: scaffold only — nothing has been applied or deployed.** These files describe
the cheapest real deployment from [`docs/DEPLOYMENT.md`](../../docs/DEPLOYMENT.md)
(App Runner + RDS + ElastiCache), so going live is `terraform apply` once you have an
AWS account and credentials — not a rewrite.

## What this provisions
- **ECR** repository (push the same image `docker compose build` already produces)
- **App Runner** service running that image (0.25 vCPU / 0.5 GB — the cheap tier)
- **RDS** Postgres (db.t4g.micro)
- **ElastiCache** Redis (cache.t4g.micro)
- **Secrets Manager** entries for `DATABASE_URL` / `REDIS_URL` / `ANTHROPIC_API_KEY`

Estimated cost at this tier: **~$30-40/month** (see `docs/DEPLOYMENT.md` for the
breakdown and the cheaper/pricier alternatives).

## Before you run this
1. An AWS account + credentials (`aws configure` or environment variables) — **not provided
   by this repo or by Claude**; you supply these.
2. `terraform >= 1.7`.
3. Push the image once: `docker build -t paz-rav .` then tag/push to the ECR repo this
   creates (two-step: `terraform apply -target=aws_ecr_repository.app` first, then push,
   then `terraform apply` for the rest — see comments in `main.tf`).

## Usage
```bash
cd infra/terraform
terraform init
terraform plan     # review — creates nothing yet
terraform apply    # your explicit go-ahead; this is the only step that costs money
```

## Teardown
```bash
terraform destroy
```
