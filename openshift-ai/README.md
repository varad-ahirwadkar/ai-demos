# Red Hat OpenShift AI Demos
Demonstrations for Red Hat OpenShift AI (RHOAI) showcasing model serving, LLM evaluation, and guardrails.

## Directory Structure
```
openshift-ai/
├── shared/                   # Shared configuration files
├── model-serving/            # Model serving demos
└── trustyai/                 # TrustyAI demos
    ├── llm-evaluation/       # LLM evaluation
    └── guardrails/           # Guardrails
```

## Getting Started

### 1. Prerequisites
- OpenShift Cluster
- Cluster admin access
- Red Hat OpenShift AI operator installed

### 2. Clone and Configure OpenShift AI
```bash
# Clone the repository
git clone https://github.com/IBM/ai-demos.git
cd openshift-ai/

# Create DSCInitialization
oc create -f shared/dsci.yaml

# Verify DSCInitialization is in Ready state
oc get dsci
NAME           AGE   PHASE   CREATED AT
default-dsci   25h   Ready   2025-09-23T04:33:53Z

# Deploy DataScienceCluster
oc create -f shared/dsc.yaml

# Verify DataScienceCluster is in Ready state
oc get dsc
NAME          READY   REASON
default-dsc   True    
```

### 3. S3 Storage
Update [`shared/s3-secret.yaml`](shared/s3-secret.yaml) with your credentials:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION`
- `AWS_S3_BUCKET`
- `AWS_S3_ENDPOINT`

Apply the secret to your target data science project namespace:
```bash
oc new-project <your-project> || oc project <your-project>
oc apply -f shared/s3-secret.yaml
```

## Available Demos
### 1. Model Serving
Deploy and serve Large Language Models (LLMs) using KServe -

**Location:** [`model-serving`](model-serving/)  

**Models included:**
  - Phi-3-mini-4k-instruct
  - Qwen2.5-1.5B-Instruct

### 2. TrustyAI
Explore Responsible AI workflows and LLM safety techniques.

**Location:** [`TrustyAI`](trustyai/)  

**Included Demos**
  - [`LLM Evaluation`](trustyai/llm-evaluation/): Evaluate models against benchmarks.
  - [`Guardrails`](trustyai/guardrails/): Safety guardrails for LLM applications.
    - FMS Guardrails (Lemonade Stand demo)
    - NeMo Guardrails (TechGear Assistant demo)

## Shared Resources
[`shared/`](shared/) directory contains reusable cluster configuration and setup resources:
- [`dsci.yaml`](shared/dsci.yaml) - DSCInitialization
- [`dsc.yaml`](shared/dsc.yaml) - DataScienceCluster
- [`s3-secret.yaml`](shared/s3-secret.yaml) - S3 credentials template


## Resources
- [Red Hat OpenShift AI Docs](https://access.redhat.com/documentation/en-us/red_hat_openshift_ai_self-managed/)
