#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# deploy.sh — Build & Deploy da Sales Platform API no Cloud Run
# ============================================================================
# Reaproveita o mesmo projeto GCP do Hub Operacional (billing já habilitado)
# para não duplicar custo fixo de projeto. Padrão de baixo custo:
#   - Cloud Run scale-to-zero (min-instances=0)
#   - Sem Load Balancer / IAP (API pública, protegida por CORS + validação
#     de payload; autenticação de usuário fica para uma etapa futura)
#   - Firestore Native mode no free tier (1GiB armazenamento,
#     50k leituras / 20k escritas / 20k exclusões por dia, de graça)
#   - Service Account dedicada com apenas roles/datastore.user
#     (princípio do menor privilégio — não usa a SA default do projeto)
#
# Pré-requisitos:
#   - gcloud CLI autenticado como engfraga.gabriel@gmail.com (rodar via
#     Cloud Shell, igual ao Hub Operacional — ver nota em CLAUDE memory
#     sobre separação de contas GCP)
#   - Rodar este script de dentro da raiz do repo sales-platform (onde
#     está o Dockerfile e a pasta app/)
# ============================================================================

PROJECT_ID="${PROJECT_ID:-gen-lang-client-0375194901}"
REGION="southamerica-east1"
SERVICE_NAME="sales-platform-api"
SERVICE_ACCOUNT_NAME="sales-platform-sa"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Ajuste esta lista quando o domínio final da loja (Palhas Douradas) for
# definido. Em ambiente de validação, pode manter "*" temporariamente —
# mas o CORSMiddleware não aceita "*" junto com allow_credentials=True em
# alguns browsers, então prefira já listar os domínios reais assim que
# souber (ex.: Vercel/Netlify preview + domínio de produção).
ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-https://palhas-douradas-frontend-337796419771.southamerica-east1.run.app}"

echo "==> Configurando projeto ${PROJECT_ID}..."
gcloud config set project "${PROJECT_ID}"

echo "==> Habilitando APIs necessárias..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  firestore.googleapis.com

echo "==> Verificando se o banco Firestore (Native mode) já existe..."
if ! gcloud firestore databases describe --database="(default)" >/dev/null 2>&1; then
  echo "    Nenhum banco Firestore encontrado. Criando em modo Native (${REGION})..."
  gcloud firestore databases create --location="${REGION}" --type=firestore-native
else
  echo "    Banco Firestore já existe, pulando criação."
fi

echo "==> Criando Service Account dedicada (princípio do menor privilégio)..."
if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
    --display-name="Sales Platform API - Cloud Run"
else
  echo "    Service Account já existe, pulando criação."
fi

echo "==> Concedendo apenas a role de leitura/escrita no Firestore (datastore.user)..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/datastore.user" \
  --condition=None

echo "==> Build da imagem via Cloud Build..."
gcloud builds submit --tag "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest" .

echo "==> Deploy no Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest" \
  --region="${REGION}" \
  --platform=managed \
  --service-account="${SERVICE_ACCOUNT_EMAIL}" \
  --allow-unauthenticated \
  --set-env-vars="ENVIRONMENT=production,GCP_PROJECT_ID=${PROJECT_ID},USE_IN_MEMORY_DB=false,ALLOWED_ORIGINS=${ALLOWED_ORIGINS}" \
  --min-instances=0 \
  --max-instances=2 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=60

URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format="value(status.url)")
echo ""
echo "==> Deploy concluído."
echo "    URL da API: ${URL}"
echo "    Documentação interativa (Swagger UI): ${URL}/docs"
echo "    Health check: ${URL}/health"
echo ""
echo "    Lembrete: como o serviço está --allow-unauthenticated, qualquer"
echo "    pessoa com a URL acessa a API. Não há autenticação de usuário"
echo "    ainda (isso fica para o módulo de Checkout/Auth, próximo ticket)."
echo "    O ALLOWED_ORIGINS atual é: ${ALLOWED_ORIGINS}"