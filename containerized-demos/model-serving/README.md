# Model Serving Demos

Demonstrations for serving models using inference servers. These demos showcase model training, deployment and inference.

## Available Demos

### ML Model Deployment Demos

- **[Iris Classification](iris-classification/)**: Multi-class classification using the Iris dataset
- **[Fraud Detection](fraud-detection/)**: Binary classification for credit card fraud detection

## Shared Utilities

The `shared/` directory contains utilities.

The following scripts are used to generate model configuration file for the Triton server:

- **`json_to_proto.py`**: Converts JSON model configuration files to Protocol Buffer format
- **`json_to_proto.sh`**: Shell script wrapper for the conversion utility
