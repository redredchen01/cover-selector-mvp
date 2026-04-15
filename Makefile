.PHONY: help build push run stop clean lint test docker-build docker-push docker-run docker-stop

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
RED := \033[0;31m
NC := \033[0m # No Color

# Configuration
IMAGE_NAME ?= cover-selector
IMAGE_TAG ?= latest
REGISTRY ?= docker.io
FULL_IMAGE := $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)

# AWS Configuration (optional)
AWS_REGION ?= us-east-1
ECR_REPOSITORY ?= cover-selector

help:
	@echo "$(BLUE)Cover Selector - Docker & Development Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Local Development:$(NC)"
	@echo "  make build          - Build Docker image locally"
	@echo "  make run            - Run application locally (docker-compose)"
	@echo "  make stop           - Stop running containers"
	@echo "  make clean          - Remove containers and volumes"
	@echo ""
	@echo "$(GREEN)Testing & Linting:$(NC)"
	@echo "  make test           - Run tests"
	@echo "  make lint           - Run code linting"
	@echo "  make coverage       - Generate coverage report"
	@echo ""
	@echo "$(GREEN)Docker Image Management:$(NC)"
	@echo "  make docker-build   - Build Docker image"
	@echo "  make docker-push    - Push to registry (requires REGISTRY set)"
	@echo "  make docker-scan    - Scan image for vulnerabilities"
	@echo ""
	@echo "$(GREEN)Cloud Deployment:$(NC)"
	@echo "  make aws-push       - Push to AWS ECR"
	@echo "  make gcp-push       - Push to Google Artifact Registry"
	@echo "  make azure-push     - Push to Azure Container Registry"
	@echo ""
	@echo "$(GREEN)Variables:$(NC)"
	@echo "  IMAGE_NAME=$(IMAGE_NAME)  IMAGE_TAG=$(IMAGE_TAG)  REGISTRY=$(REGISTRY)"

# Local Development
build:
	@echo "$(BLUE)Building Docker image...$(NC)"
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .
	@echo "$(GREEN)✓ Image built: $(IMAGE_NAME):$(IMAGE_TAG)$(NC)"

run:
	@echo "$(BLUE)Starting application with docker-compose...$(NC)"
	docker-compose up --build
	@echo "$(GREEN)✓ Application running at http://localhost:8000$(NC)"

run-bg:
	@echo "$(BLUE)Starting application in background...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Application running (detached)$(NC)"

stop:
	@echo "$(BLUE)Stopping containers...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Containers stopped$(NC)"

logs:
	@echo "$(BLUE)Following application logs...$(NC)"
	docker-compose logs -f

clean:
	@echo "$(BLUE)Cleaning up Docker resources...$(NC)"
	docker-compose down -v
	docker image prune -f --filter "dangling=true"
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

# Testing & Code Quality
test:
	@echo "$(BLUE)Running tests...$(NC)"
	python -m pytest tests/ -v

test-fast:
	@echo "$(BLUE)Running tests (fast mode)...$(NC)"
	python -m pytest tests/ -q --tb=no

coverage:
	@echo "$(BLUE)Generating coverage report...$(NC)"
	python -m pytest tests/ --cov=src/cover_selector --cov-report=html
	@echo "$(GREEN)✓ Coverage report: htmlcov/index.html$(NC)"

lint:
	@echo "$(BLUE)Linting code...$(NC)"
	black --check src/ tests/ 2>/dev/null || echo "Run: black src/ tests/"
	isort --check-only src/ tests/ 2>/dev/null || echo "Run: isort src/ tests/"
	flake8 src/ tests/ --max-line-length=100 2>/dev/null || echo "Fix linting issues above"
	mypy src/ --ignore-missing-imports 2>/dev/null || echo "Fix type issues above"

format:
	@echo "$(BLUE)Formatting code...$(NC)"
	black src/ tests/
	isort src/ tests/
	@echo "$(GREEN)✓ Code formatted$(NC)"

# Docker Image Management
docker-build:
	@echo "$(BLUE)Building Docker image: $(FULL_IMAGE)$(NC)"
	docker build -t $(FULL_IMAGE) -t $(IMAGE_NAME):latest .
	@echo "$(GREEN)✓ Image built successfully$(NC)"
	docker image ls | grep $(IMAGE_NAME)

docker-push: docker-build
	@echo "$(BLUE)Pushing image to registry: $(REGISTRY)$(NC)"
	docker push $(FULL_IMAGE)
	docker push $(IMAGE_NAME):latest
	@echo "$(GREEN)✓ Image pushed successfully$(NC)"

docker-scan:
	@echo "$(BLUE)Scanning image for vulnerabilities...$(NC)"
	docker scan $(FULL_IMAGE)
	@echo "$(GREEN)✓ Scan complete$(NC)"

docker-size:
	@echo "$(BLUE)Checking image size...$(NC)"
	@docker images $(IMAGE_NAME) --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

# AWS Deployment
aws-login:
	@echo "$(BLUE)Logging into AWS ECR...$(NC)"
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin $$(aws sts get-caller-identity --query Account --output text).dkr.ecr.$(AWS_REGION).amazonaws.com

aws-create-repo:
	@echo "$(BLUE)Creating ECR repository...$(NC)"
	aws ecr create-repository \
		--repository-name $(ECR_REPOSITORY) \
		--region $(AWS_REGION) || echo "Repository may already exist"

aws-push: aws-login aws-create-repo
	@echo "$(BLUE)Building and pushing to AWS ECR...$(NC)"
	@ECR_URI=$$(aws sts get-caller-identity --query Account --output text).dkr.ecr.$(AWS_REGION).amazonaws.com; \
	docker build -t $$ECR_URI/$(ECR_REPOSITORY):latest .; \
	docker tag $$ECR_URI/$(ECR_REPOSITORY):latest $$ECR_URI/$(ECR_REPOSITORY):v0.2.0; \
	docker push $$ECR_URI/$(ECR_REPOSITORY):latest; \
	docker push $$ECR_URI/$(ECR_REPOSITORY):v0.2.0; \
	echo "$(GREEN)✓ Image pushed to AWS ECR$(NC)"

# Google Cloud Deployment
gcp-push:
	@echo "$(BLUE)Building and pushing to Google Artifact Registry...$(NC)"
	gcloud builds submit \
		--tag us-central1-docker.pkg.dev/$$(gcloud config get-value project)/cover-selector/cover-selector:latest \
		--timeout=1800s
	@echo "$(GREEN)✓ Image pushed to Google Artifact Registry$(NC)"

# Azure Deployment
azure-build:
	@echo "$(BLUE)Building image in Azure Container Registry...$(NC)"
	az acr build \
		--registry coverselectoracr \
		--image cover-selector:latest \
		--image cover-selector:v0.2.0 \
		.

azure-push: azure-build
	@echo "$(GREEN)✓ Image built in Azure ACR$(NC)"

# Shell
shell:
	@echo "$(BLUE)Opening shell in running container...$(NC)"
	docker exec -it $$(docker-compose ps -q cover-selector) /bin/bash

# Info
info:
	@echo "$(BLUE)Project Information:$(NC)"
	@echo "Image Name: $(IMAGE_NAME)"
	@echo "Image Tag: $(IMAGE_TAG)"
	@echo "Registry: $(REGISTRY)"
	@echo "Full Image: $(FULL_IMAGE)"
	@echo ""
	@echo "$(BLUE)Docker Status:$(NC)"
	@docker ps --filter "ancestor=$(FULL_IMAGE)" --format "table {{.ID}}\t{{.Status}}\t{{.Ports}}"

# Version
version:
	@python -c "import sys; print(f'Python {sys.version_info.major}.{sys.version_info.minor}')"
	@docker --version
	@docker-compose --version
