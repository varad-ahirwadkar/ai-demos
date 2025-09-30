# TrustyAI Demos 
This repository contains demos showcasing TrustyAI's features within Red Hat Openshift AI.

### Prerequisites
#### 1. Enabling the TrustyAI component for RawDeployment  
Configure `DSCInitialization` and `DataScienceCluster` resources for RawDeployment
```
# Create DSCInitialization
oc create -f common/setup/dsci.yaml

# Verfiy DSCInitialization is in Ready state
oc get dsci
NAME           AGE   PHASE   CREATED AT
default-dsci   25h   Ready   2025-09-23T04:33:53Z

# Deploy DataScienceCluster
oc create -f common/setup/dsc.yaml

# Verfiy DataScienceCluster is in Ready state
oc get dsc
NAME          READY   REASON
default-dsc   True    
```

#### 2. Create a S3 secret  
In this demo, we will be using all the models from IBM Cloud S3 bucket.
Create the [s3-secret](common/setup/s3-secret.yaml) with creds for the accessing the models.
```
oc new-project trustyai-demo || oc project trustyai-demo
oc apply -f common/setup/s3-secret.yaml
```

#### 3. Enabling the TrustyAI Service 
This step is not required for Large Language Models Demos
To deploy TrustyAI Service, follow the instructions within the [Enable TrustyAI for RawDeployment](trustyai-svc-demos/README.md).

### Large Language Models Demos
#### 1. Evaluation Demo  
This demo will quickly get you started running an evaluation against an InferenceService which is already deployed and running in your namespace.  
Demo - [Evaluating large language models](eval-quickstart-demo/)

#### 2. Guardrail Demo  
A demo showing manual configuration of guardrails  
Demo - [Lemonade Stand Demo](guardails-lemonade-stand-demo/)

## Machine Learning Models Demos
#### 1. Data Drift Demo  
How to detect if the production data your models are receiving matches the data they were trained on.  
Demo - [Data Drift Demo](trustyai-svc-demos/data-drift/)

#### 2. Bias Monitoring Demo [Coming Soon]  
How to use TrustyAI to examine your deployed models for unfair biases.  

#### 3. Anomaly Detection [Coming Soon] 
How to identify and log anomalous inbound data, such as to clean or enrich your training data.  

#### 4. Explainability Demo [Coming Soon]
How to get per-point explanations of your models' predictions.  

## More information
- [TrustyAI Notes Repo](https://github.com/trustyai-explainability/reference/tree/main)
- [TrustyAI Github](https://github.com/trustyai-explainability)
