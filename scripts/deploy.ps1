# Production Deployment Script for Quantum-Safe Optimization Platform (PowerShell)
# Usage: .\scripts\deploy.ps1 -Environment staging -Version latest

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('local', 'staging', 'production')]
    [string]$Environment = 'staging',

    [Parameter(Mandatory=$false)]
    [string]$Version = 'latest',

    [Parameter(Mandatory=$false)]
    [string]$DockerRegistry = 'quay.io/quantum-opt'
)

$AppName = 'quantum-optimization'
$ErrorActionPreference = 'Stop'

# Colors
function Write-Info    { Write-Host "[INFO] $_" -ForegroundColor Green }
function Write-Warn    { Write-Host "[WARN] $_" -ForegroundColor Yellow }
function Write-Error2  { Write-Host "[ERROR] $_" -ForegroundColor Red }

# Check prerequisites
function Check-Prerequisites {
    Write-Info "Checking prerequisites..."

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error2 "Docker is not installed"
        exit 1
    }

    if ($Environment -eq 'production' -and -not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
        Write-Error2 "kubectl is required for production deployments"
        exit 1
    }

    Write-Info "Prerequisites check passed"
}

# Build Docker image
function Build-Image {
    Write-Info "Building Docker image..."

    docker build `
        -t "${DockerRegistry}/${AppName}:${Version}" `
        -t "${DockerRegistry}/${AppName}:latest" `
        --build-arg VERSION="${Version}" `
        --build-arg ENV="${Environment}" `
        .

    Write-Info "Docker image built successfully"
}

# Push Docker image
function Push-Image {
    Write-Info "Pushing Docker image to registry..."

    docker push "${DockerRegistry}/${AppName}:${Version}"
    docker push "${DockerRegistry}/${AppName}:latest"

    Write-Info "Docker image pushed successfully"
}

# Deploy to Kubernetes
function Deploy-Kubernetes {
    Write-Info "Deploying to Kubernetes (${Environment})..."

    kubectl config use-context "${Environment}"

    # Apply Kubernetes manifests
    kubectl apply -f k8s/base/
    kubectl apply -f "k8s/${Environment}/"

    # Set image version
    kubectl set image "deployment/${AppName}" `
        "${AppName}=${DockerRegistry}/${AppName}:${Version}" `
        -n ${AppName}

    # Wait for rollout
    kubectl rollout status "deployment/${AppName}" -n ${AppName} --timeout=300s

    Write-Info "Kubernetes deployment completed"
}

# Run database migrations
function Run-Migrations {
    Write-Info "Running database migrations..."

    kubectl run migration-job `
        "--image=${DockerRegistry}/${AppName}:${Version}" `
        "--env=APP_ENV=${Environment}" `
        --command -- `
        alembic upgrade head `
        -n ${AppName}

    Write-Info "Database migrations completed"
}

# Health check
function Health-Check {
    Write-Info "Running health checks..."

    if ($Environment -eq 'production' -or $Environment -eq 'staging') {
        $HealthUrl = "https://${AppName}.${Environment}.example.com/health"
    } else {
        $HealthUrl = "http://localhost:8000/health"
    }

    # Wait for service to be ready
    for ($i = 1; $i -le 30; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 10 -UseBasicParsing
            if ($response.StatusCode -eq 200) {
                Write-Info "Health check passed"
                return
            }
        } catch {
            Write-Warn "Health check attempt $i/30 failed, retrying..."
            Start-Sleep -Seconds 10
        }
    }

    Write-Error2 "Health check failed after 30 attempts"
    exit 1
}

# Main
try {
    Write-Info "Starting deployment for environment: ${Environment}"
    Write-Info "Version: ${Version}"

    Check-Prerequisites

    Build-Image

    if ($Environment -ne 'local') {
        Push-Image
    }

    switch ($Environment) {
        'production' {
            Deploy-Kubernetes
            Run-Migrations
        }
        'staging' {
            Deploy-Kubernetes
            Run-Migrations
        }
        'local' {
            Write-Info "Skipping deployment steps for local environment"
        }
    }

    Health-Check

    Write-Info "Deployment completed successfully!"
} catch {
    Write-Error2 "Deployment failed: $_"
    exit 1
}