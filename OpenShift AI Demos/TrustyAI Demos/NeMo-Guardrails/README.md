# NeMo Guardrails Demo

A guardrail is a semi or fully deterministic control that restricts or guides LLM behavior. Guardrails can block specific topics, steer conversations, or trigger actions such as escalating to a human.

NeMo Guardrails is an open source toolkit for controlling LLM behavior at runtime. It uses a rule based language called Colang to define conversation flows, restrict topics, and enforce policies. NeMo Guardrails is LLM agnostic and designed for low latency deployments, including GPU accelerated environments.

Within the TrustyAI ecosystem, NeMo Guardrails focuses on conversation behavior and control, while FMS Guardrails focuses on safety, risk detection, and compliance.

This demo shows how to deploy NVIDIA NeMo Guardrails on Red Hat OpenShift AI and use it to protect a deployed model. It uses the `Qwen2.5-1.5B-Instruct` model as a backend and implements custom logic for security, PII detection, and deterministic dialogue.

---
### Prerequisites  

Enable TrustyAI by following: 
- [Configure the RHOAI for RawDeployment](../README.md)

### 1. Model Configuration

We will be deploying the `Qwen2.5-1.5B-Instruct` model and use it as self-hosted vLLM backend (with an OpenAI-compatible API) for NeMo Guardrails.

#### Deploy the Model
Create and switch to the demo project:
```bash
oc new-project trustyai-demo || oc project trustyai-demo
```

Deploy the vLLM runtime and model:
```bash
oc process -n redhat-ods-applications vllm-cpu-runtime-template | oc create -f -
oc apply -f ../common/vllm-deployment/qwen.yaml
```

Wait for the model pod to be ready, for example `qwen-predictor-XXXXXX`

Test the raw model endpoint:
```bash
RAW_MODEL=https://$(oc get route qwen -o jsonpath='{.spec.host}')
curl -ks -X POST "$RAW_MODEL/v1/completions" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen",
    "prompt": "The capital of France is",
    "max_tokens": 20
  }' | jq
```

### 2. Configure NeMo Guardrails

#### 2.1 Create a token secret for the service account:
```bash
oc create secret generic openai-key-secret --from-literal=token=<YOUR_API_TOKEN>
```

#### 2.2 Create the Guardrails Configuration

**How This Demo Works**

We will be creating a ConfigMap which includes all required configuration. For this demo setup consists of three configs:
- a. config.yml
- b. rails.co
- c. actions.py


#### 2.2.1 config.yml
This includes the backend `model's configuration` along with the `rails config`:  
**Model's config**

```bash
    models:
      - type: main                          
        engine: vllm_openai
        parameters:
          openai_api_base: "http://qwen-predictor.nemo.svc.cluster.local:8080/v1"
          model_name: "qwen"
```

Where,
```
- type: main          # Identifies the primary LLM used for conversations
- engine: vllm_openai # Uses a self-hosted vLLM backend with an OpenAI-compatible API
- parameters          # Provider-specific connection details, including the model endpoint and name
```
For more information please refere [#models-configuration](https://docs.nvidia.com/nemo/guardrails/latest/configure-rails/configuration-reference.html#models-configuration) 

**Rails Config:**  
This section includes the built-in Microsoft Presidio integration to detect and mask sensitive information 
```
  config:
    sensitive_data_detection:
      input:
        entities:
          - EMAIL_ADDRESS
      output:
        entities:
          - PERSON
```
- Scans for `EMAIL_ADDRESS` - Prevents user contact info from being sent to or stored by the LLM 
- Scans for `PERSON` (names) - Prevents the model from accidentally leaking real-world identities in its responses

**Input rails**  
Run before the LLM is invoked and used to validate, filter and modify user input
```
  input:
    flows:
      - detect sensitive data on input
      - check message length
      - check forbidden words
```
- In this demo it has three flows
  - to detect sensitive data, enforce message length limits, block forbidden content
- If an input rail returns a deterministic response or stops execution, the LLM is not called

**Output rails**  
Run after the LLM responds and are used to validate, filter, or modify bot responses
```
  output:
    flows:
      - detect sensitive data on output
```
- In this demo it has one flows 
  - to detect sensitive data on output

#### 2.2.2 rails.co:
A Colang script is a `.co` file and is composed of one or more flow definitions. A flow is a sequence of statements describing the desired interaction between the user and the bot. In this demo we have the flow for:

- deterministic greetings
- blocking political topics
- message length enforcement
- forbidden content filtering
- fallback to the LLM for normal queries


Reference - https://docs.nvidia.com/nemo/guardrails/latest/configure-rails/colang/colang-2/getting-started/index.html 

#### 2.2.3 actions.py (Custom Actions):

Custom Python actions implement deterministic checks for:

- Message length validation
- Forbidden word detection

These actions run as system actions and ensure policy enforcement without relying on the model

**Apply the ConfigMap:**

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
          name: "openai-key-secret"
          key: "token"
EOF
```

#### ❗NOTE: Temporary image override:
At the time of this demo, an official image with the required fixes and architecture support is not yet available, so a custom image is used instead.  
This override should be removed once an official NeMo Guardrails image is available and published.
```bash
oc patch deployment nemo-guardrails-cr   -p '{
    "spec": {
      "template": {
        "spec": {
          "containers": [
            {
              "name": "nemo-guardrails",
              "image": "<custom-image>"
            }
          ],
          "initContainers": [
            {
              "name": "ca-bundle-initializer",
              "image": "<custom-image>"
            }
          ]
        }
      }
    }
  }'
```
#### ❗NOTE: Increase route timeout: 
OpenShift routes have a default timeout of 30 seconds.
NeMo Guardrails may exceed this limit due to multiple guardrail checks and LLM inference latency.  
Tune the timeout according to your model size and expected response times.
```bash
oc annotate route nemo-guardrails-cr --overwrite haproxy.router.openshift.io/timeout=10m
```

### Verificartion:
Set the Guardrails route:
```bash
GUARDRAILS_ROUTE=https://$(oc get routes/nemo-guardrails-cr -o jsonpath={.status.ingress[0].host})
```

With our rails initialized, we can begin asking questions and interacting with the Guardrails-protected LLM.

**Greeting example**

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
      "content": "Hello! Welcome to our service.\nHow can I help you today?"
    }
  ]
}
```

**Let's try asking a political question:**
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
        "content": "what do you think of the president?"
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
      "content": "I'm a shopping assistant, I don't like to talk of politics.\nHowever, if you have any questions about products, services, or shopping-related topics, I'd be more than happy to assist you."
    }
  ]
}
```
Using simple Colang rules, we successfully prevented the chatbot from responding to political topics while allowing normal conversation. 

**Asking a question with forbidden words:**
```bash
curl -k -X POST   $GUARDRAILS_ROUTE/v1/chat/completions   -H "Content-Type: application/json"   -H "Authorization: Bearer $(oc whoami -t)"   -d '{
    "config_id": "nemo-config",
    "messages": [
      {
        "role": "user",
        "content": "I yearn for violence"
      }
    ]
  }' | jq
```

```bash
  "messages": [
    {
      "role": "assistant",
      "content": "I can't help with that type of request. Please ask something else."
    }
  ]
}
```

**Asking a query longer than 100 words:**  

```bash
QUERY="Act as an expert personal shopping assistant specializing in sustainable, high-quality home office equipment. I am looking to purchase an ergonomic desk chair for my home office setup. I work from home full-time, spending approximately 8-10 hours a day at my desk, and I have recently started experiencing lower back pain, so lumbar support is my top priority. I prefer a modern, minimalist aesthetic, preferably in a neutral color like charcoal grey or black, and I strongly prefer materials that are breathable to prevent overheating.  Based on these requirements, please provide a ranked list of top 3 recommendations available in the market."

# curl -k -X POST \
  "$GUARDRAILS_ROUTE/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(oc whoami -t)" \
  -d "{
    \"config_id\": \"nemo-config\",
    \"messages\": [
      {
        \"role\": \"user\",
        \"content\": \"${QUERY}\"
      }
    ]
  }" | jq
```
Output:
```bash
{
  "messages": [
    {
      "role": "assistant",
      "content": "Please keep your message under 100 words for better assistance."
    }
  ]
}
```

**Asking a question that should be blocked by Guardrail's output rail:**
```bash
 # curl -k -X POST \
  $GUARDRAILS_ROUTE/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(oc whoami -t)" \
  -d '{
    "config_id": "nemo-config",
    "messages": [
      {
        "role": "user",
        "content": "In just two words, provide a typical American first and last name."
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
      "content": "I don't know the answer to that."
    }
  ]
}
```

#### Summary:

This demonstrates how NeMo Guardrails can be used to control model behavior at runtime, enforcing topic restrictions, content safety, and input constraints while still enabling natural and useful interactions.  

#### References:
- [Deploying NeMo Guardrails](https://docs.redhat.com/ja/documentation/red_hat_openshift_ai_self-managed/3.2/html/enabling_ai_safety_with_guardrails/deploying-nemo-guardrails_nemo-guardrails)
- https://docs.nvidia.com/nemo/guardrails/latest/configure-rails/configuration-reference.html
- https://www.pinecone.io/learn/nemo-guardrails-intro/
