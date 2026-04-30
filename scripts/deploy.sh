#!/bin/bash
# Production Deployment Script for Quantum-Safe Optimization Platform
# Usage: ./scripts/deploy.sh [environment] [version]

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV=${1:-staging}  # Default to staging
VERSION=${2:-latest}
APP_NAME="quantum-optimization"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-quay.io/quantum-opt}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check kubectl for Kubernetes deployments
    if [ "$ENV" == "production" ] && ! command -v kubectl &> /dev/null; then
        log_error "kubectl is required for production deployments"
        exit 1
    fi
    
    # Check environment variables
    if [ "$ENV" == "production" ] && [ -z "$DOCKER_REGISTRY" ]; then
        log_error "DOCKER_REGISTRY environment variable is required"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Build Docker image
build_image() {
    log_info "Building Docker image..."
    
    docker build \
        -t "${DOCKER_REGISTRY}/${APP_NAME}:${VERSION}" \
        -t "${DOCKER_REGISTRY}/${APP_NAME}:latest" \
        --build-arg VERSION="${VERSION}" \
        --build-arg ENV="${ENV}" \
        .
    
    log_info "Docker image built successfully"
}

# Push Docker image
push_image() {
    log_info "Pushing Docker image to registry..."
    
    docker push "${DOCKER_REGISTRY}/${APP_NAME}:${VERSION}"
    docker push "${DOCKER_REGISTRY}/${APP_NAME}:latest"
    
    log_info "Docker image pushed successfully"
}

# Deploy to Kubernetes
deploy_kubernetes() {
    log_info "Deploying to Kubernetes (${ENV})..."
    
    kubectl config use-context "${ENV}"
    
    # Apply Kubernetes manifests
    kubectl apply -f k8s/base/
    kubectl apply -f k8s/${ENV}/
    
    # Set image version
    kubectl set image deployment/${APP_NAME} \
        ${APP_NAME}="${DOCKER_REGISTRY}/${APP_NAME}:${VERSION}" \
        -n ${APP_NAME}
    
    # Wait for rollout
    kubectl rollout status deployment/${APP_NAME} -n ${APP_NAME} --timeout=300s
    
    log_info "Kubernetes deployment completed"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    kubectl run migration-job \
        --image="${DOCKER_REGISTRY}/${APP_NAME}:${VERSION}" \
        --env="APP_ENV=${ENV}" \
        --command -- \
        alembic upgrade head \
        -n ${APP_NAME}
    
    log_info "Database migrations completed"
}

# Health check
health_check() {
    log_info "Running health checks..."
    
    if [ "$ENV" == "production" ] || [ "$ENV" == "staging" ]; then
        HEALTH_URL="https://${APP_NAME}.${ENV}.example.com/health"
    else
        HEALTH_URL="http://localhost:8000/health"
    fi
    
    # Wait for service to be ready
    for i in {1..30}; do
        if curl -s -f "$HEALTH_URL" > /dev/null; then
            log_info "Health check passed"
            return 0
        fi
        log_warn "Health check attempt $i/30 failed, retrying..."
        sleep 10
    done
    
    log_error "Health check failed after 30 attempts"
    return 1
}

# Rollback deployment
rollback() {
    log_warn "Rolling back deployment..."
    
    if [ "$ENV" == "production" ] || [ "$ENV" == "staging" ]; then
        kubectl rollout undo deployment/${APP_NAME} -n ${APP_NAME}
    else
        log_error "Rollback not supported for local deployments"
        exit 1
    fi
    
    log_info "Rollback completed"
}

# Main deployment function
main() {
    log_info "Starting deployment for environment: ${ENV}"
    log_info "Version: ${VERSION}"
    
    check_prerequisites
    
    # Build and push
    build_image
    
    if [ "$ENV" != "local" ]; then
        push_image
    fi
    
    # Deploy
    case "$ENV" in
        "production"|"staging")
            deploy_kubernetes
            run_migrations
            ;;
        "local")
            log_info "Skipping deployment steps for local environment"
            ;;
        *)
            log_error "Unknown environment: ${ENV}"
            exit 1
            ;;
    esac
    
    # Health check
    health_check
    
    log_info "Deployment completed successfully!"
}

# Handle errors
trap 'log_error "Deployment failed!"; exit 1' ERR

# Run main function
main "$@"