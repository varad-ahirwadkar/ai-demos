# TrustyAI Demos

Demonstrations for responsible AI practices including LLM evaluation, guardrails, bias monitoring, and data drift detection.

## Prerequisites

Complete the setup steps in the [main OpenShift AI README](../README.md#getting-started):
1. Configure DSCInitialization and DataScienceCluster
2. Create S3 secret with your storage credentials

## Available Demos

### LLM Evaluation
Evaluate Large Language Models against deployed InferenceServices - [Eval Quickstart Demo](llm-evaluation/eval-quickstart/)

### Guardrails
Safety guardrails for LLM applications.

**FMS Guardrails:**  
Manual configuration of guardrails - [Lemonade Stand Demo](guardrails/fms-guardrails/lemonade-stand/)

**NeMo Guardrails:**  
Conversational guardrails with topic blocking, input validation, and sensitive data detection - [TechGear Assistant Demo](guardrails/nemo-guardrails/techgear-assistant/)

## Coming Soon

### Machine Learning Model Monitoring

**Data Drift Detection**  
How to detect if the production data your models are receiving matches the data they were trained on.  

**Bias Monitoring**  
How to use TrustyAI to examine your deployed models for unfair biases.  

**Anomaly Detection**  
How to identify and log anomalous inbound data, such as to clean or enrich your training data.  

**Explainability**  
How to get per-point explanations of your models' predictions.  

## Resources

- [TrustyAI Reference](https://github.com/trustyai-explainability/reference/tree/main)
- [TrustyAI GitHub](https://github.com/trustyai-explainability)
