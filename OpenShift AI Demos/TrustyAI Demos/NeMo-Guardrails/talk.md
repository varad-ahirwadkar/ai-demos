# NeMo Guardrails Demo - Talking Script
## Red Hat OpenShift AI Platform - TrustyAI Component

---

## 1. INTRODUCTION (2-3 minutes)

### Opening Statement
Good morning and evening everyone. Today, I'm am going to demonstrate **NVIDIA NeMo Guardrails**, a crusial component of the TrustyAI ecosystem within Red Hat OpenShift AI platform. As AI applications become more prevalent in enterprise environments, ensuring safe, controlled, and compliant AI interactions is no longer optional, it's essential.

### The Challenge
Deploying Large Language Models face several critical challenges:
- **Unpredictable outputs** - LLMs can generate inappropriate or harmful content
- **Data leakage risks** - Models might accidentally expose sensitive information
- **Compliance requirements** - Industries need to enforce strict content policies
- **Brand protection** - Companies must ensure AI interactions align with their values
- **User safety** - Preventing harmful or offensive responses

### The Solution
This is where NeMo Guardrails comes in - providing a programmable, deterministic layer of control over LLM behavior.

---

## 2. WHAT IS NEMO GUARDRAILS? (3-4 minutes)

### Core Definition
**NeMo Guardrails** is an open-source toolkit developed by NVIDIA that adds programmable guardrails to LLM-based conversational systems. Think of it as a safety framework that sits between your users and the AI model.

### Key Characteristics
Guardrails are **semi or fully deterministic controls** that:
- **Restrict** specific topics or conversation paths
- **Guide** conversations in desired directions  
- **Trigger** specific actions like escalating to human agents
- **Validate** both user inputs and model outputs
- **Enforce** compliance and safety policies

### Why "Guardrails"?
The name is intentional, just like highway guardrails keep vehicles on safe paths without stopping traffic, NeMo Guardrails keeps AI conversations safe and productive without blocking legitimate interactions.

---

## 3. NEMO GUARDRAILS IN THE TRUSTYAI ECOSYSTEM (2-3 minutes)

### TrustyAI Overview
Within Red Hat OpenShift AI, **TrustyAI** is the comprehensive framework for responsible AI deployment. It encompasses:
- **Model monitoring** - Tracking model performance and drift
- **Bias detection** - Identifying and mitigating unfair outcomes
- **Explainability** - Understanding model decisions
- **Guardrails** - Controlling model behavior (this is where NeMo fits)

### NeMo's Role in TrustyAI
While other TrustyAI components like **FMS Guardrails** focus on safety, risk detection, and compliance at the model level, **NeMo Guardrails** specializes in:
- **Conversation behavior control** - Managing dialogue flow and topics
- **Real-time interaction safety** - Immediate input/output validation
- **Deterministic policy enforcement** - Predictable, rule-based controls
- **Custom business logic** - Implementing organization-specific requirements

### Complementary Approach
Think of it this way: FMS Guardrails provides the safety net for model outputs, while NeMo Guardrails provides the steering wheel for conversation control. Together, they create a comprehensive safety system.

---

## 4. KEY CONCEPTS AND TERMINOLOGY (4-5 minutes)

### 4.1 Rails - The Core Concept

**Definition:**
"**Rails** are the fundamental building blocks of NeMo Guardrails. They are rules or policies that control how the LLM behaves."

**Three Types of Rails:**

#### Input Rails
"**Input Rails** run BEFORE the LLM processes user input. They:
- Validate user messages
- Filter sensitive data
- Block inappropriate requests
- Enforce message length limits
- Check for forbidden content

*Example:* Detecting and blocking political questions before they reach the model."

#### Output Rails  
"**Output Rails** run AFTER the LLM generates a response but BEFORE it's sent to the user. They:
- Scan for sensitive information leakage
- Validate response appropriateness
- Ensure compliance with policies
- Redact confidential data

*Example:* Detecting and masking personal information in model responses."

#### Dialogue Rails
"**Dialogue Rails** control the conversation flow itself. They:
- Define allowed conversation paths
- Manage topic transitions
- Implement predefined responses
- Handle escalation scenarios

*Example:* Redirecting political discussions to a standard response."

### 4.2 Colang - The Configuration Language

**What is Colang?**
"**Colang** (Conversation Language) is a domain-specific language designed specifically for defining conversational flows and guardrails. It's:
- **Human-readable** - Easy to understand and maintain
- **Declarative** - You describe WHAT should happen, not HOW
- **Flexible** - Supports simple rules to complex conversation logic"

**Colang Structure:**
```
define flow <flow_name>
  user <user_intent>
  bot <bot_response>
  [optional conditions and actions]
```

**Example from our demo:**
```colang
# Political topics guardrail
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
```

"This defines a flow that intercepts political questions and provides a predetermined response, preventing the LLM from generating potentially controversial content."

### 4.3 Actions - Custom Python Logic

**What are Actions?**
"**Actions** are custom Python functions that implement deterministic checks and business logic. They allow you to:
- Perform complex validations
- Integrate with external systems
- Implement custom algorithms
- Execute side effects (logging, alerts, etc.)"

**Action Decorator:**
"Actions are marked with the `@action` decorator and can be called from Colang flows."

**Example from our demo:**
```python
@action(is_system_action=True)
async def check_forbidden_words(context: Optional[dict] = None) -> str:
    user_message = (context or {}).get("user_message", "").lower()
    forbidden_topics = {
        "security": ["password", "hack", "exploit", "vulnerability"],
        "inappropriate": ["violence", "illegal", "harmful"],
        "competitors": ["chatgpt", "openai", "claude", "anthropic"],
    }
    
    for category, words in forbidden_topics.items():
        for word in words:
            if word in user_message:
                return f"blocked_{category}_{word}"
    
    return "allowed"
```

"This action scans user input for forbidden words across multiple categories and returns a deterministic result."

---

## 5. DEMO CONFIGURATION EXPLAINED (5-6 minutes)

### 5.1 Architecture Overview

"Our demo uses a three-file configuration structure:
1. **config.yaml** - Model backend and rails configuration
2. **rails.co** - Colang conversation flows
3. **actions.py** - Custom Python validation logic"

### 5.2 config.yaml - The Foundation

**Model Configuration:**
```yaml
models:
  - type: main
    engine: vllm_openai
    parameters:
      openai_api_base: "http://qwen-predictor.trustyai-demo.svc.cluster.local:8080/v1"
      model_name: "qwen"
```

"We're using **Qwen 2.5-1.5B-Instruct**, a compact but capable model, deployed as a self-hosted vLLM backend. This gives us:
- **Full control** over the model deployment
- **OpenAI-compatible API** for easy integration
- **Low latency** for real-time interactions
- **Cost efficiency** for enterprise deployments"

**Rails Configuration:**
```yaml
rails:
  config:
    sensitive_data_detection:
      input:
        entities:
          - EMAIL_ADDRESS
      output:
        entities:
          - PERSON
```

"This configures **Microsoft Presidio** integration for PII detection:
- **Input scanning** - Detects and can mask email addresses in user messages
- **Output scanning** - Detects person names in model responses to prevent identity leakage"

### 5.3 Input Rails Configuration

**Three Input Flows:**

#### 1. Sensitive Data Detection
```colang
input:
  flows:
    - detect sensitive data on input
```
"Automatically scans for EMAIL_ADDRESS entities and can mask or reject messages containing them."

#### 2. Message Length Validation  
```colang
- check message length
```
"Enforces a 100-word limit on user messages to prevent:
- Prompt injection attacks
- Resource exhaustion
- Overly complex queries"

**Implementation:**
```python
word_count = len(user_message.split())
MAX_WORDS = 100
if word_count > MAX_WORDS:
    return "blocked_too_long"
elif word_count > MAX_WORDS + 0.8:
    return "warning_long"
return "allowed"
```

#### 3. Forbidden Content Detection
```colang
- check forbidden words
```
"Uses our custom action to block messages containing:
- **Security-related terms** (password, hack, exploit)
- **Inappropriate content** (violence, illegal, harmful)  
- **Competitor mentions** (chatgpt, openai, claude)"

### 5.4 Output Rails Configuration

**Single Output Flow:**
```colang
output:
  flows:
    - detect sensitive data on output
```

"Scans model responses for PERSON entities (names) to prevent accidental disclosure of real identities."

### 5.5 Conversation Flows (rails.co)

**Greeting Flow:**
```colang
define flow greeting
  user express greeting
  bot express greeting
  bot ask how are you
```
"Provides a consistent, friendly greeting experience."

**Political Topics Flow:**
```colang
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
```
"Completely blocks political discussions with a predetermined response—the LLM never sees these queries."

---

## 6. DEMO SCENARIOS (8-10 minutes)

### Setup Context
"I'll now demonstrate four scenarios that showcase different guardrail capabilities."

### Scenario 1: Normal Greeting

**What we're testing:** "Basic functionality and greeting flow"

**Expected Output:**
```json
{
  "messages": [
    {
      "role": "assistant",
      "content": "Hello! Welcome to our service. How can I help you today?"
    }
  ]
}
```

**Key Points:**
- The greeting flow activates automatically
- We get a consistent, friendly response
- This establishes the baseline for normal operation

---

### Scenario 2: Political Topic Blocking

**What we're testing:** "Topic restriction using dialogue rails"

**User Input:** "what do you think of the president?"

**Expected Output:**
```json
{
  "messages": [
    {
      "role": "assistant",
      "content": "I'm a shopping assistant, I don't like to talk of politics."
    }
  ]
}
```

**Key Points:**
- The political topic is detected BEFORE reaching the LLM
- A predetermined response is returned instantly
- This prevents the model from generating potentially controversial content
- This is a **dialogue rail** in action

**Why This Matters:**
"For enterprise applications, you cannot risk the LLM expressing political opinions that might alienate customers or create PR issues."

---

### Scenario 3: Forbidden Word Detection

**What we're testing:** "Content filtering using input rails"

**User Input:** "I yearn for violence"

**Expected Output:**
```json
{
  "messages": [
    {
      "role": "assistant",
      "content": "I can't help with that type of request. Please ask something else."
    }
  ]
}
```

**Key Points:**
- The word 'violence' triggers our custom action
- The action runs BEFORE the LLM sees the message
- The conversation is stopped with a safe response
- This is an **input rail** with a **custom action**

**Technical Flow:**
1. User message arrives
2. Input rails execute
3. `check_forbidden_words` action scans
4. Detects 'violence' in inappropriate category
5. Returns blocked status
6. Safe response returned
7. **LLM never processes this request**

---

### Scenario 4: Message Length Validation

**What we're testing:** "Input validation and user guidance"

**User Input:** Long message exceeding 100 words

**Expected Output:**
```json
{
  "messages": [
    {
      "role": "assistant",
      "content": "Please keep your message under 100 words for better assistance."
    }
  ]
}
```

**Key Points:**
- Messages exceeding 100 words are rejected
- Users receive helpful guidance
- Prevents prompt injection attacks
- Ensures performance and fair usage

---

## 7. KEY TAKEAWAYS (2-3 minutes)

### What We Demonstrated

✅ **Topic Control** - Blocked political discussions  
✅ **Content Filtering** - Prevented inappropriate content  
✅ **Input Validation** - Enforced message length limits  
✅ **PII Protection** - Detected sensitive information  
✅ **Deterministic Behavior** - Predictable safety controls

### Core Principles

**1. Guardrails are Essential**  
"In production AI, guardrails ensure user safety, compliance, and brand protection."

**2. Layered Defense Works Best**  
"Combine input rails, dialogue rails, output rails, and custom actions."

**3. Deterministic > Probabilistic**  
"Use guardrails for safety-critical controls, not just prompts."

**4. Integration is Seamless**  
"NeMo fits naturally into OpenShift AI and TrustyAI ecosystem."

---

## 8. QUESTIONS AND DISCUSSION

### Common Questions to Prepare For:

**Q: How does this compare to prompt engineering?**  
A: Guardrails provide guaranteed enforcement at the system level, while prompts can be bypassed or ignored by the model.

**Q: What's the performance impact?**  
A: Input rails add 10-50ms, output rails 20-100ms. Minimal overhead for significant safety benefits.

**Q: Can we use this with any LLM?**  
A: Yes! NeMo Guardrails is model-agnostic and works with OpenAI, open-source, and custom models.

**Q: How do we update guardrails in production?**  
A: Configurations are stored in ConfigMaps, allowing hot-reloading without service restarts.

**Q: What about false positives?**  
A: Monitor metrics, adjust thresholds, and refine rules based on real usage patterns.

---

## CLOSING STATEMENT

Thank you for your attention. NeMo Guardrails represents a critical capability for responsible AI deployment. By providing deterministic, programmable controls over LLM behavior, it enables organizations to deploy AI confidently while maintaining safety, compliance, and brand integrity.

The integration with Red Hat OpenShift AI and TrustyAI makes this enterprise-ready, scalable, and production-proven.

I'm happy to answer any questions or provide additional demonstrations.

---

## APPENDIX: TECHNICAL REFERENCES

### Repository Structure
```
nemo-guardrails-demo/
├── configurations/
│   └── configmap.yml (contains config.yaml, rails.co, actions.py)
└── README.md
```

### Key Configuration Files

**config.yaml** - Model and rails setup
**rails.co** - Colang conversation flows  
**actions.py** - Custom Python validation logic

### Useful Links
- NeMo Guardrails Documentation: https://docs.nvidia.com/nemo/guardrails/
- Colang Reference: https://docs.nvidia.com/nemo/guardrails/latest/configure-rails/colang-2/
- Red Hat OpenShift AI: https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai
- Demo Repository: https://github.com/varad-ahirwadkar/ai-demos/tree/nemo-demo/

