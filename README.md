# AI Demos

A collection of AI/ML demonstrations and examples for various platforms and use cases.

## Repository Structure

```
ai-demos/
├── containerized-demos/      # Containerized ML demos (local deployment)
│   └── model-serving/        # Model serving with ONNX Runtime
│       ├── fraud-detection/
│       └── iris-classification/
│
└── openshift-ai/             # Red Hat OpenShift AI demos
    ├── model-serving/        # LLM serving with KServe and vLLM
    └── trustyai/             # TrustyAI demos
        ├── llm-evaluation/   # LLM evaluation
        └── guardrails/       # Guardrails (FMS & NeMo)
```

## Available Demos

### [Containerized Demos](containerized-demos/)
Local containerized demonstrations for ML model serving:
- **Fraud Detection**: Credit card fraud detection using ONNX Runtime
- **Iris Classification**: Multi-class classification with ONNX Runtime

### [Red Hat OpenShift AI](openshift-ai/)
Demonstrations for Red Hat OpenShift AI platform:
- **Model Serving**: Deploy LLMs (Phi-3, Qwen) using KServe and vLLM
- **TrustyAI**: Responsible AI toolkit for LLM evaluation and guardrails
  - **Evaluation**: LLM evaluation with lm-eval-harness
  - **Guardrails**: Safety guardrails using FMS and NeMo frameworks

## Getting Started

Each demo directory contains its own README with detailed setup instructions. Choose a demo category above and follow the specific documentation.

## Contributing

This project requires contributors to agree to the Developer Certificate of Origin.

Please refer to [DCO.txt](DCO.txt) for more information.
