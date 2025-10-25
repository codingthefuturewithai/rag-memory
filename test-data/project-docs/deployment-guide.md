# Kubernetes Deployment Guide

## Prerequisites

### Required Tools
- kubectl v1.28+
- Helm v3.12+
- Docker Desktop or Minikube
- AWS CLI (for EKS deployments)

### Access Requirements
- Kubernetes cluster admin access
- Container registry credentials
- SSL certificates for ingress

## Quick Start

### 1. Clone Infrastructure Repository
```bash
git clone https://github.com/company/k8s-infrastructure.git
cd k8s-infrastructure
```

### 2. Configure Namespace
```bash
kubectl create namespace production
kubectl config set-context --current --namespace=production
```

### 3. Install Helm Charts

#### Install Ingress Controller
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace production \
  --set controller.service.type=LoadBalancer
```

#### Deploy Application Stack
```bash
helm install app-stack ./charts/application \
  --namespace production \
  --values ./environments/production/values.yaml \
  --set image.tag=v3.2.1
```

## Configuration Management

### ConfigMaps
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: production
data:
  database_host: "postgres.production.svc.cluster.local"
  redis_host: "redis.production.svc.cluster.local"
  log_level: "info"
```

### Secrets Management
```bash
# Create secret from literal values
kubectl create secret generic db-credentials \
  --from-literal=username=dbuser \
  --from-literal=password='S3cur3P@ssw0rd' \
  --namespace production

# Or from file
kubectl create secret generic tls-cert \
  --from-file=tls.crt=/path/to/cert.pem \
  --from-file=tls.key=/path/to/key.pem \
  --namespace production
```

## Deployment Strategies

### Rolling Update (Default)
```yaml
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 1
```

### Blue-Green Deployment
1. Deploy green version with new label
2. Test green deployment
3. Switch service selector
4. Monitor metrics
5. Remove blue deployment

### Canary Deployment
```bash
# Deploy canary version (10% traffic)
kubectl set image deployment/app-deployment \
  app=myapp:v3.3.0-canary \
  --record

# Gradually increase traffic using Flagger or Argo Rollouts
```

## Monitoring and Observability

### Health Checks
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Prometheus Metrics
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace
```

### Log Aggregation
```bash
kubectl logs -f deployment/app-deployment --all-containers=true
kubectl logs -f deployment/app-deployment --previous  # For crashed pods
```

## Troubleshooting

### Common Issues

#### Pod Stuck in Pending
```bash
kubectl describe pod <pod-name>
kubectl get events --sort-by=.metadata.creationTimestamp
```

#### Image Pull Errors
```bash
# Check secret exists
kubectl get secrets -n production

# Verify image pull secret
kubectl get secret regcred -o yaml
```

#### Resource Constraints
```bash
kubectl top nodes
kubectl top pods --all-namespaces
kubectl describe resourcequota -n production
```

### Rollback Procedure
```bash
# View rollout history
kubectl rollout history deployment/app-deployment

# Rollback to previous version
kubectl rollout undo deployment/app-deployment

# Rollback to specific revision
kubectl rollout undo deployment/app-deployment --to-revision=2
```

## Backup and Disaster Recovery

### Backup Strategy
1. Daily etcd snapshots
2. Persistent volume backups via Velero
3. Configuration stored in Git

### Restore Procedure
```bash
# Restore from Velero backup
velero restore create --from-backup production-backup-20240320

# Verify restoration
kubectl get all -n production
```

---
*Document Status: Published*
*Last Updated: March 2024*
*Maintained by: DevOps Team*