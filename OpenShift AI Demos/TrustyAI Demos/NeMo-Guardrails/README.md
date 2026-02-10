# NeMo Guardrails Demo

A guardrail is a semi or fully deterministic control that restricts or guides LLM behavior. Guardrails can block specific topics, steer conversations, or trigger actions such as escalating to a human.

NeMo Guardrails is an open source toolkit for controlling LLM behavior at runtime. It uses a rule based language called Colang to define conversation flows, restrict topics, and enforce policies. NeMo Guardrails is LLM agnostic and designed for low latency deployments, including GPU accelerated environments.

Within the TrustyAI ecosystem, NeMo Guardrails focuses on conversation behavior and control, while FMS Guardrails focuses on safety, risk detection, and compliance.

This demo shows how to deploy NVIDIA NeMo Guardrails on Red Hat OpenShift AI and use it to protect a deployed model.

---
### Prerequisites  

Enable TrustyAI by following: 
- [Configure the RHOAI for RawDeployment](../README.md)

### 1. Deploy the Model
Create and switch to the demo project:
```bash
oc new-project trustyai-demo || oc project trustyai-demo
```

Deploy the vLLM runtime and model:
```bash
oc process -n redhat-ods-applications vllm-cpu-runtime-template | oc create -f -
oc apply -f ../common/vllm-deployment/opt125m.yaml
```

Wait for the model pod to be ready, for example `opt125m-predictor-XXXXXX`

Test the raw model endpoint:
```bash
RAW_MODEL=https://$(oc get route opt125m -o jsonpath='{.spec.host}')
curl -ks -X POST "$RAW_MODEL/v1/completions" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "opt125m",
    "prompt": "The capital of France is",
    "max_tokens": 20
  }' | jq
```

### 2 Configure NeMo Guardrails

#### 2.1 Create Service Account and Permissions

Create a service account and bind it to the view role:
```bash
oc create -f - <<EOF 
apiVersion: v1
kind: ServiceAccount
metadata:
  name: nemo-guardrails-service-account
---
kind: RoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: nemo-guardrails-service-account-view
subjects:
  - kind: ServiceAccount
    name: nemo-guardrails-service-account
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: view
EOF
```

Create a token secret for the service account:

```bash
oc create secret generic api-token-secret \
  --from-literal=token=$(oc create token nemo-guardrails-service-account --duration=8760h)
```

#### 2.2 Create the Guardrails Configuration
NeMo Guardrails requires:
- a **config.yam**l describing the model backend
- a **Colang** (rails.co) script defining guardrail behavior

Minimal config.yaml

```bash
    models:
      - type: main
        engine: vllm_openai
        parameters:
          openai_api_base: "http://opt125m-predictor.nemo.svc.cluster.local:8080/v1"
          model_name: "opt125m"
```

Example rails.co (block political topics)

```bash
# greetings
define user express greeting
    "hello"
    "hi"
    "what's up?"

define flow greeting
    user express greeting
    bot express greeting
    bot ask how are you

# political topics
define user ask politics
    "what are your political beliefs?"
    "thoughts on the president?"
    "left wing"
    "right wing"

define bot answer politics
    "I'm a shopping assistant, I don't like to talk of politics."

define flow politics
    user ask politics
    bot answer politics
    bot offer help
```

Apply the ConfigMap:

```bash
oc apply -f configurations/configmap.yml

```

#### 2.3 Create the NeMo Guardrails Custom Resource

```
oc create -f - <<EOF 
apiVersion: trustyai.opendatahub.io/v1alpha1
kind: NemoGuardrails
metadata:
  name: nemo-guardrails-cr
  annotations:
    security.opendatahub.io/enable-auth: 'false'
spec:
  nemoConfigs:
    - name: nemo-config
      configMaps:
        - nemo-config
  env:
    - name: "OPENAI_API_KEY"
      valueFrom:
        secretKeyRef:
          name: "api-token-secret"
          key: "token"
EOF
```

#### ❗NOTE: Temporary image override:
```bash
oc patch deployment nemo-guardrails-cr   -p '{
    "spec": {
      "template": {
        "spec": {
          "containers": [
            {
              "name": "nemo-guardrails",
              "image": "quay.io/vahirwad/nemo-server:v0.0.2"
            }
          ],
          "initContainers": [
            {
              "name": "ca-bundle-initializer",
              "image": "quay.io/vahirwad/nemo-server:v0.0.2"
            }
          ]
        }
      }
    }
  }'

```
#### ❗NOTE: Increase route timeout: 
```bash
oc annotate route nemo-guardrails-cr --overwrite haproxy.router.openshift.io/timeout=10m
```

### Verificartion:
Set the Guardrails route:
```bash
GUARDRAILS_ROUTE=https://$(oc get routes/nemo-guardrails-cr -o jsonpath={.status.ingress[0].host})
```

With our rails initialized, we can begin asking questions and interacting with our Guardrails protected LLM.

Greeting example

```bash
curl -k -X POST \
  $GUARDRAILS_ROUTE/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(oc whoami -t)" \
  -d '{
    "config_id": "nemo-config",
    "messages": [
      {
        "role": "user",
        "content": "Hi, How are you?"
      }
    ]
  }' | jq
```

Output:
```bash
{
  "messages": [
    {
      "role": "assistant",
      "content": "Hello! How can I assist you today?"
    }
  ]
}
```

Let's try asking a political question:
```bash
  curl -k -X POST \
  $GUARDRAILS_ROUTE/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(oc whoami -t)" \
  -d '{
    "config_id": "guardrails-config",
    "messages": [
      {
        "role": "user",
        "content": "what do you think of the president?"
      }
    ]
  }'
```

Output:
```bash
{
  "messages": [
    {
      "role": "assistant",
      "content": "I'm a shopping assistant, I don't like to talk of politics.\nThank you for answering my question."
    }
  ]
}
```
Using simple Colang rules, we successfully prevented the chatbot from responding to political topics while allowing normal conversation. This demonstrates how NeMo Guardrails can be used to control model behavior at runtime.

#### References:
- [Deploying NeMo Guardrails](https://docs.redhat.com/ja/documentation/red_hat_openshift_ai_self-managed/3.2/html/enabling_ai_safety_with_guardrails/deploying-nemo-guardrails_nemo-guardrails)
- https://www.pinecone.io/learn/nemo-guardrails-intro/
