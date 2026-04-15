# Docker & Cloud Deployment Guide

Cover Selector v0.2.0 is fully containerized and supports deployment to multiple cloud platforms.

## 📦 Local Docker Development

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- Git

### Quick Start

1. **Clone and navigate to project:**
   ```bash
   git clone https://github.com/redredchen01/cover-selector-mvp.git
   cd cover-selector-mvp
   ```

2. **Build and run locally:**
   ```bash
   docker-compose up --build
   ```

3. **Access the application:**
   - Web UI: http://localhost:8000
   - Health check: http://localhost:8000/health

4. **Stop containers:**
   ```bash
   docker-compose down
   ```

### Volume Mappings

The docker-compose.yml exposes these volumes for local development:
- `./uploads` → `/tmp/uploads` - Processed video uploads
- `./cache` → `/tmp/cache` - Frame and feature cache
- `./history` → `/tmp/history` - Session history

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `WORKERS` | `4` | Number of worker threads |
| `PYTHONUNBUFFERED` | `1` | Unbuffered output |

---

## ☁️ AWS Deployment (ECS + ECR)

### Prerequisites
- AWS Account with ECR, ECS, and CloudWatch permissions
- AWS CLI v2 configured
- Docker Desktop

### Step 1: Create ECR Repository

```bash
aws ecr create-repository \
  --repository-name cover-selector \
  --region us-east-1

# Output: note the repositoryUri
```

### Step 2: Build and Push Docker Image

```bash
# Set your ECR URI
ECR_URI="123456789012.dkr.ecr.us-east-1.amazonaws.com"

# Authenticate Docker with ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $ECR_URI

# Build and tag image
docker build -t cover-selector:latest .
docker tag cover-selector:latest $ECR_URI/cover-selector:latest
docker tag cover-selector:latest $ECR_URI/cover-selector:v0.2.0

# Push to ECR
docker push $ECR_URI/cover-selector:latest
docker push $ECR_URI/cover-selector:v0.2.0
```

### Step 3: Create ECS Task Definition

Create `ecs-task-definition.json`:

```json
{
  "family": "cover-selector",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "cover-selector",
      "image": "ECR_URI/cover-selector:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "hostPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "HOST",
          "value": "0.0.0.0"
        },
        {
          "name": "PORT",
          "value": "8000"
        },
        {
          "name": "WORKERS",
          "value": "4"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/cover-selector",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 5
      }
    }
  ],
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT_ID:role/ecsTaskRole"
}
```

### Step 4: Create ECS Cluster and Service

```bash
# Create CloudWatch log group
aws logs create-log-group --log-group-name /ecs/cover-selector

# Register task definition
aws ecs register-task-definition \
  --cli-input-json file://ecs-task-definition.json

# Create ECS cluster
aws ecs create-cluster --cluster-name cover-selector-cluster

# Create ECS service (requires existing VPC and ALB)
aws ecs create-service \
  --cluster cover-selector-cluster \
  --service-name cover-selector-service \
  --task-definition cover-selector \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:ACCOUNT_ID:targetgroup/cover-selector/xxx,containerName=cover-selector,containerPort=8000"
```

### Monitoring

- **CloudWatch Dashboard:**
  ```bash
  # View logs
  aws logs tail /ecs/cover-selector --follow
  ```
- **Auto-scaling:** Configure CPU/memory based scaling policies
- **Alarms:** Set up alarms for container health and error rates

---

## 🔵 Google Cloud Deployment (Cloud Run)

### Prerequisites
- Google Cloud Project with Cloud Run, Artifact Registry permissions
- gcloud CLI installed and configured

### Step 1: Enable Required APIs

```bash
gcloud services enable \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com
```

### Step 2: Create Artifact Registry Repository

```bash
gcloud artifacts repositories create cover-selector \
  --repository-format=docker \
  --location=us-central1 \
  --description="Cover Selector Docker Repository"
```

### Step 3: Build and Push Image

```bash
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/PROJECT_ID/cover-selector/cover-selector:latest \
  --timeout=1800s
```

### Step 4: Deploy to Cloud Run

```bash
gcloud run deploy cover-selector \
  --image us-central1-docker.pkg.dev/PROJECT_ID/cover-selector/cover-selector:latest \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 1 \
  --timeout 3600 \
  --max-instances 100 \
  --allow-unauthenticated \
  --set-env-vars "WORKERS=4,PYTHONUNBUFFERED=1"
```

### Step 5: Verify Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe cover-selector \
  --platform managed \
  --region us-central1 \
  --format 'value(status.url)')

# Test health endpoint
curl $SERVICE_URL/health
```

### Monitoring

```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=cover-selector" \
  --limit 50 \
  --format json

# View metrics
gcloud monitoring dashboards create \
  --config-from-file=cloud-run-dashboard.json
```

---

## 🟦 Azure Deployment (Container Instances + Container Registry)

### Prerequisites
- Azure Account with Container Registry and Container Instances permissions
- Azure CLI installed and configured
- Logged in: `az login`

### Step 1: Create Container Registry

```bash
az group create \
  --name cover-selector-rg \
  --location eastus

az acr create \
  --resource-group cover-selector-rg \
  --name coverselectoracr \
  --sku Basic
```

### Step 2: Build and Push Image

```bash
# Authenticate
az acr login --name coverselectoracr

# Build in ACR
az acr build \
  --registry coverselectoracr \
  --image cover-selector:latest \
  --image cover-selector:v0.2.0 \
  .

# Get login server
ACR_SERVER=$(az acr show \
  --name coverselectoracr \
  --query loginServer \
  --output tsv)
```

### Step 3: Deploy to Container Instances

```bash
# Get ACR credentials
ACR_USERNAME=$(az acr credential show \
  --name coverselectoracr \
  --query username \
  --output tsv)

ACR_PASSWORD=$(az acr credential show \
  --name coverselectoracr \
  --query 'passwords[0].value' \
  --output tsv)

# Deploy container instance
az container create \
  --resource-group cover-selector-rg \
  --name cover-selector \
  --image $ACR_SERVER/cover-selector:latest \
  --cpu 1 \
  --memory 2 \
  --ports 8000 \
  --registry-login-server $ACR_SERVER \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --environment-variables \
    HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=4
```

### Step 4: Verify Deployment

```bash
# Get public IP
az container show \
  --resource-group cover-selector-rg \
  --name cover-selector \
  --query ipAddress.ip \
  --output tsv

# Test (replace IP)
curl http://YOUR_IP:8000/health
```

### Monitoring

```bash
# View logs
az container logs \
  --resource-group cover-selector-rg \
  --name cover-selector \
  --follow

# View metrics
az monitor metrics list \
  --resource /subscriptions/SUB_ID/resourceGroups/cover-selector-rg/providers/Microsoft.ContainerInstance/containerGroups/cover-selector
```

---

## 🔐 Security Best Practices

### 1. Image Security
- Use specific Python version (3.11-slim)
- Run as non-root user (appuser, UID 1000)
- Regular security scanning: `docker scan cover-selector`
- Multi-stage build to minimize image size

### 2. Environment Configuration
- Use secrets management services (AWS Secrets Manager, Azure Key Vault)
- Never commit secrets to version control
- Rotate credentials regularly

### 3. Network Security
- Use VPC/subnets for isolation
- Implement security groups/network policies
- Enable TLS/SSL encryption in production
- Use private registries (ECR, Artifact Registry, ACR)

### 4. Runtime Security
- Enable container health checks
- Set resource limits (CPU, memory)
- Use read-only filesystems where possible
- Enable audit logging

---

## 📊 Performance Tuning

### Memory & CPU
- **Light workload** (< 10 GB videos): 1 CPU, 2 GB RAM
- **Standard workload** (10-50 GB videos): 2 CPU, 4 GB RAM
- **Heavy workload** (> 50 GB videos): 4 CPU, 8 GB RAM

### Workers Configuration
```
WORKERS = min(CPU_CORES * 2, AVAILABLE_MEMORY_GB / 0.5)
```

### Caching
- Use persistent volumes for frame/feature cache
- Configure cache directory: `/tmp/cache`
- Monitor cache size to prevent disk exhaustion

---

## 🔄 Continuous Integration/Deployment

### GitHub Actions Example

```yaml
name: Build and Push

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: docker build -t cover-selector:${{ github.ref_name }} .
      
      - name: Push to Registry
        run: |
          docker tag cover-selector:${{ github.ref_name }} $ECR_URI/cover-selector:${{ github.ref_name }}
          docker push $ECR_URI/cover-selector:${{ github.ref_name }}
        env:
          ECR_URI: ${{ secrets.AWS_ECR_URI }}
```

---

## 🐛 Troubleshooting

### Image Build Issues

```bash
# View build logs
docker build --progress=plain -t cover-selector:latest .

# Check base image
docker pull python:3.11-slim
```

### Runtime Issues

```bash
# Check container logs
docker logs cover-selector

# Debug inside container
docker exec -it cover-selector /bin/bash

# Test health endpoint
curl -v http://localhost:8000/health
```

### Performance Issues

```bash
# Monitor resource usage
docker stats cover-selector

# Check disk usage
docker system df
docker image history cover-selector:latest
```

---

## 📝 Version Management

- **Stable:** `latest` tag for production deployments
- **Release:** `v0.2.0` tag for specific versions
- **Development:** `dev` tag for development builds

---

## 📞 Support

For issues or questions:
- GitHub Issues: https://github.com/redredchen01/cover-selector-mvp/issues
- Documentation: https://github.com/redredchen01/cover-selector-mvp#readme

---

**Last Updated:** 2026-04-15  
**Version:** 0.2.0
