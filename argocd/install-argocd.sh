#!/bin/bash
set -euo pipefail

# ArgoCD 安装脚本
# 用法: ./install-argocd.sh [--namespace NAMESPACE] [--version VERSION] [--dry-run]

set -o pipefail

NAMESPACE="argocd"
VERSION="v2.12.7"
DRY_RUN=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

echo "========================================="
echo "ArgoCD 安装脚本"
echo "========================================="
echo "命名空间: $NAMESPACE"
echo "版本: $VERSION"
echo "试运行: $DRY_RUN"
echo "========================================="

# 检查 kubectl
if ! command -v kubectl &> /dev/null; then
    echo "错误: kubectl 未安装"
    exit 1
fi

# 检查 helm
if ! command -v helm &> /dev/null; then
    echo "错误: helm 未安装"
    exit 1
fi

# 检查集群连接
if ! kubectl cluster-info &> /dev/null; then
    echo "错误: 无法连接到 Kubernetes 集群"
    exit 1
fi

echo "✓ 前置检查通过"

# 创建命名空间
if ! kubectl get namespace argocd &> /dev/null; then
    echo "创建命名空间: argocd"
    if [[ "$DRY_RUN" == "false" ]]; then
        kubectl create namespace argocd
    fi
else
    echo "命名空间 argocd 已存在"
fi

# 添加 ArgoCD Helm 仓库
echo "添加 ArgoCD Helm 仓库..."
helm repo add argocd https://argoproj.github.io/argo-helm 2>/dev/null || true
helm repo update

# 安装 ArgoCD CRDs
echo "安装 ArgoCD CRDs..."
kubectl apply -k "https://github.com/argoproj/argo-cd/releases/download/v2.12.7/crds" --dry-run=client >/dev/null 2>&1 || true

# 安装 ArgoCD
echo "安装 ArgoCD..."
HELM_ARGS=(
    upgrade --install argocd argo/argocd
    --namespace argocd
    --version 7.8.0
    --set global.domain=argocd.example.com
    --set server.ingress.enabled=true
    --set server.ingress.ingressClassName=nginx
    --set "server.ingress.annotations.cert-manager\\.io/cluster-issuer=letsencrypt-prod"
    --set "server.ingress.hosts[0]=argocd.example.com"
    --set "configs.params.server\\.insecure=true"
    --set server.replicas=2
    --set controller.replicas=2
    --set repoServer.replicas=2
    --set dex.enabled=true
    --set dex.config.connectors[0].type=github
    --set dex.config.connectors[0].id=github
    --set dex.config.connectors[0].name=GitHub
    --set dex.config.connectors[0].config.clientID=\$GITHUB_CLIENT_ID
    --set dex.config.connectors[0].config.clientSecret=\$GITHUB_CLIENT_SECRET
    --set dex.config.connectors[0].config.orgs[0].name=your-org
    --set dex.config.connectors[0].config.orgs[0].team=argocd-admins
)

if [[ "$DRY_RUN" == "true" ]]; then
    HELM_ARGS+=(--dry-run)
fi

helm "${HELM_ARGS[@]}"

# 等待 ArgoCD 就绪
echo "等待 ArgoCD 就绪..."
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s
kubectl wait --for=condition=available deployment/argocd-repo-server -n argocd --timeout=300s
kubectl wait --for=condition=available deployment/argocd-application-controller -n argocd --timeout=300s

# 安装 ArgoCD CLI
if ! command -v argocd &> /dev/null; then
    echo "安装 ArgoCD CLI..."
    curl -sSL -o /usr/local/bin/argocd https://github.com/argoproj/argo-cd/releases/download/v2.12.7/argocd-linux-amd64
    chmod +x /usr/local/bin/argocd
fi

# 登录 ArgoCD
echo "获取 ArgoCD 初始密码..."
ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
echo "ArgoCD 初始密码: $ARGOCD_PASSWORD"

# 登录
argocd login argocd.example.com --username admin --password "$ARGOCD_PASSWORD" --insecure

# 应用 AppProject
echo "应用 Project 配置..."
kubectl apply -f argocd/project.yaml

# 应用 ApplicationSets
echo "应用 ApplicationSets..."
kubectl apply -f argocd/applicationsets.yaml

# 应用主应用
echo "应用根应用..."
kubectl apply -f argocd/applications.yaml

echo "========================================="
echo "ArgoCD 安装完成！"
echo "========================================="
echo "访问地址: https://argocd.example.com"
echo "用户名: admin"
echo "密码: (见上方输出)"
echo "========================================="
echo ""
echo "后续步骤:"
echo "1. 修改默认密码: argocd account update-password"
echo "2. 配置 GitHub OAuth: 编辑 argocd/install.yaml 中的 dex 配置"
echo "3. 添加 GitHub 仓库: argocd repo add https://github.com/your-org/jcode-platform"
echo "4. 创建应用: argocd app create jcode-platform --repo https://github.com/your-org/jcode-platform --path helm/jcode-platform --dest-server https://kubernetes.default.svc --dest-namespace production"
echo "========================================="
