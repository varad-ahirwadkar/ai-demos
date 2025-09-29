# TrustyAI Evaluation Quickstart

TrustyAI's LM-Eval framework brings popular open-source evaluation toolkits to OpenShift AI. Currently,
it supports the [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness/tree/main).

In this example, we'll deploy a Phi3 model and run an Arc-Easy evaluation against it.
[Arc](https://huggingface.co/datasets/allenai/ai2_arc) is an immensely popular evaluation that measures a model against a number of grade-school level, multiple-choice science questions.

---
### Prerequisites
1. Cluster with default Storage Class  

2. Before deploying LMEval job, please follow [Configure the RHOAI for RawDeployment](../README.md) and make sure that DSC should set following variables to allow downloading remote datasets
```
spec:
  trustyai:
    eval:
      lmeval:
        permitCodeExecution: true
        permitOnline: true
    managementState: Managed
```

By default, TrustyAI prevents evaluation jobs from accessing the internet or running downloaded code.
A typical evaluation job will download two items from Huggingface:
1) The dataset of the evaluation task, and any dataset processing code
2) The tokenizer of your model

If you trust the source of your dataset and tokenizer, you can override TrustyAI's default setting.
In our case, we'll be downloading:
1) [allenai/ai2_arc](https://huggingface.co/datasets/allenai/ai2_arc)
2) [Phi-3-mini-4k-instruct's tokenizer](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct)

---
### 1. Deploy Phi3 Model
```bash
oc new-project trustyai-demo || oc project trustyai-demo
```

Deploy the model
```
oc process -n redhat-ods-applications vllm-cpu-runtime-template | oc create -f -
oc apply -f common/setup/vllm-deployment/phi3.yaml
```

Wait for the model pod to spin up, should look something like `phi3-predictor-XXXXXX`

You can test the model by sending some inferences to it:

```bash
curl -ks -X POST "https://phi3-trustyai-demo.apps.rdr-varad-418.ocp-rhoai.com/v1/chat/completions"   -H 'accept: application/json'   -H 'Content-Type: application/json'   -d '{
    "model": "phi3",
    "messages": [
      {
        "content": "The capital of France is",
        "role": "user"
      }
]}' | jq
````
---

### 2. Run the evaluation
To start an evaluation, apply an `LMEvalJob` custom resource:
```bash
oc apply -f evaluation_job.yaml
```

Check out [evaluation_job.yaml](evaluation_job.yaml) to learn more about the `LMEvalJob` specification.


If everything has worked, you should see a pod called `arc-easy-eval-job` running in your namespace. 
You can watch the progress of your evaluation job by running:

```bash
oc logs -f arc-easy-eval-job
```

---
### 3. Check out the results
After the evaluation finishes, you can take a look at the results. These are stored in the `status.results` field of the LMEvalJob resource:

```bash
oc get LMEvalJob arc-easy-eval-job -o template --template '{{.status.results}}' | jq  .results
```
returns:
```json
{
  "arc_challenge": {
    "alias": "arc_challenge",
    "acc,none": 0.64,
    "acc_stderr,none": 0.06857142857142856,
    "acc_norm,none": 0.62,
    "acc_norm_stderr,none": 0.06934092056863767
  }
}
```

The Phi model a 64% accuracy on the `arc_challenge` task and a slightly lower 62% when using a more stringent, normalized scoring method. Both scores have a margin of error of about ±7%. This performance is typically used to compare the reasoning abilities of this language model against others.

### More info:
- [Redhat Doc](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_cloud_service/1/html/monitoring_data_science_models/evaluating-large-language-models_monitor)
- [GitHub lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)