# Language Model Evaluation Harness

## Table of Contents
- [Prerequisites](#prerequisites)
- [What is LLM Evaluation?](#what-is-llm-evaluation)
- [Why Evaluation Matters](#why-evaluation-matters)
- [How It Differs from Traditional Testing](#how-it-differs-from-traditional-testing)
- [Understanding Hallucination](#understanding-hallucination)
- [Large Language Model Evaluation Harness](#large-language-model-evaluation-harness)
- [Tasks and Metrics](#tasks-and-metrics)
- [Hands-on Examples](#hands-on-examples)
- [Interpreting Results](#interpreting-results)

## Prerequisites

Before running the evaluation examples, ensure you have:

- `ollama` running locally with the `llama3.2:3b` model
  - Install Ollama: https://ollama.ai
  - Pull the model: `ollama pull llama3.2:3b`
  - Start Ollama: `ollama serve`

Install the `lm_eval` tool:
```
% python3.12 -m venv .eval
% source .eval/bin/activate
% pip install "lm_eval[api,hf]"
```

## What is LLM Evaluation?

LLM evaluation is the process of measuring how well a language model performs across different tasks using standardized datasets and metrics. These tasks typically include reasoning, math problem solving, question answering, coding, and general knowledge.

Unlike traditional software testing, LLM outputs can vary in wording and format. Evaluation therefore often includes answer extraction and normalization before comparing outputs with ground truth answers. Automated evaluation makes this process scalable, consistent, and reproducible.

## Why Evaluation Matters

- Enables objective comparison between models
- Tracks improvements after fine-tuning or optimization
- Detects regressions after changes
- Helps select models based on accuracy, performance, and cost

## How It Differs from Traditional Testing

### Traditional Software Test

You write a function:
```python
def add(a, b):
    return a + b
```

Test case:
```python
Input: add(2, 3)
Expected output: 5
```

Output is deterministic - exact match required. Pass or fail is clear.

### LLM Evaluation Example

Task: Solve a math word problem (like GSM8K)

```
Question: John has 2 apples and buys 3 more. How many apples does he have?
```

Possible model outputs:
```
"John now has 5 apples."
"He ends up with 5."
"2 + 3 = 5, so the answer is 5."
```

Even though all are correct, they are not identical strings.

So evaluation requires:
- Extracting the final answer (5)
- Comparing it with ground truth (5)

## Understanding Hallucination

Hallucination occurs when a language model generates information that sounds correct and confident but is actually false, misleading, or unsupported.

### Examples of Hallucination
- Providing incorrect historical facts
- Inventing APIs or command options
- Giving misleading medical or scientific advice

## Language Model Evaluation Harness

[`lm-eval`](https://github.com/EleutherAI/lm-evaluation-harness) is an open-source framework developed by EleutherAI that standardizes how language models are evaluated.

### Key Features

- A unified interface to test different models
- Support for multiple benchmarks and NLP tasks
- Consistent evaluation logic across models
- Task versioning to ensure reproducibility

The framework eliminates the need to write custom evaluation code and ensures results can be compared fairly across different models and implementations.

### How LM Eval Works (Simplified Flow)

1. A prompt or question from a dataset is given to the model
2. The model generates a response
3. The response is processed to extract the final answer
4. The extracted answer is compared with the correct answer
5. Scores are aggregated across many examples

This standardized pipeline ensures reliable and reproducible measurement of model performance.

### In Short

LLM evaluation provides a systematic way to measure and compare model performance, while LM Eval offers a practical, standardized framework to perform these evaluations efficiently and reproducibly.

## Tasks and Metrics

### What are Tasks?

In LM Eval, a task is a complete definition of how to evaluate a language model on a specific problem.

It brings together everything needed to run an evaluation in one place:
- What data to use (dataset)
- How to ask the model (prompt format)
- What the correct answer is (ground truth)
- How to interpret the model's response (answer extraction)
- How to score it (metrics)

In simple terms, a task is a self-contained evaluation setup for a particular capability - like a standardized test setup for an LLM.

### Common Metrics

- `acc` (Accuracy): The simplest metric. It is the percentage of times the model's predicted answer matches the correct answer exactly

- `acc_norm` (Length-Normalized Accuracy): Accuracy adjusted to avoid bias toward shorter answer choices

- `bleu` (Bilingual Evaluation Understudy): The classic translation metric. It counts how many sequences of words (1-word, 2-word, 3-word chunks) match the reference text perfectly (Precision). It is rigid; it cares about exact wording

- `ROUGE` (Recall-Oriented Understudy for Gisting Evaluation): Measures how much of the reference text is captured by the model, focusing on recall and commonly used for summarization tasks
  - `ROUGE-1`: Measures overlap of individual words between generated and reference text.
  - `ROUGE-2`: Measures overlap of two-word sequences (bigrams).
  - `ROUGE-L`: Measures the longest common sequence of words in the same order, capturing structure and fluency.
  - `ROUGE-W`: A weighted version of `ROUGE-L` that gives more importance to consecutive word matches. 

More info - https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/task_guide.md
### Task-Specific Considerations

Some tasks have specific requirements:
- **Zero-shot tasks** (like `arc_challenge_chat`, `truthfulqa_gen`): These tasks are designed to test the model without examples, so `--num_fewshot` is ignored even if specified
- **Chat-based tasks**: Require `--apply_chat_template` to format prompts correctly

## Hands-on Examples

### Example 1: GSM8K (Math Reasoning)

```bash
lm_eval \
    --model local-chat-completions \
    --model_args base_url=http://127.0.0.1:11434/v1/chat/completions,model=llama3.2:3b \
    --tasks gsm8k \
    --limit 10 \
    --num_fewshot 3 \
    --apply_chat_template \
    --batch_size 1 \
    --gen_kwargs "max_tokens=128" \
    --output_path results.json \
    --log_samples
```

#### Parameters Explained
```
--model                     # Model type/provider or Backend
    local-chat-completions  # Uses OpenAI-compatible chat API
                            # Expects input as: [{"role": "user", "content": "..."}]

--model_args          # Model constructor arguments
    base_url          # Points to your local model server
    model             # Specifies which model to use 

--tasks               # Tasks to evaluate
  
--limit               # Example limit per task

--num_fewshot         # Few-shot example count
                      # Ignored if task config sets num_fewshot: 0 (forces zero-shot)

--apply_chat_template # Converts prompt into chat format required by API

--batch_size          # Number of samples processed per request          
                      # Not supported for chat-completions APIs, use num_concurrent=N for parallel requests instead
                      # Ensure your API supports batched requests

--gen_kwargs          # Controls model generation behavior

--output_path         # Where to save detailed results

--log_samples         # Save all model inputs and outputs for analysis
```

#### About GSM8K

- **Full name**: Grade School Math 8K
- **Task config**: [gsm8k.yaml](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/gsm8k/gsm8k.yaml)
- **Purpose**: Tests multi-step mathematical reasoning (2-8 sequential steps)
- **Dataset**: 8,500 high-quality, human-written math word problems
- **Created by**: OpenAI
- **Metric**: `exact_match` - the extracted numerical answer must match exactly

#### Result

```
|Tasks|Version|     Filter     |n-shot|  Metric   |   |Value|   |Stderr|
|-----|------:|----------------|-----:|-----------|---|----:|---|-----:|
|gsm8k|      3|flexible-extract|     3|exact_match|↑  |  0.7|±  |0.1528|
|     |       |strict-match    |     3|exact_match|↑  |  0.6|±  |0.1633|
```

**Filter explanation**:
- `flexible-extract`: More lenient answer extraction (e.g., "the answer is 5" → 5)
- `strict-match`: Stricter extraction requiring specific format

### Example 2: ARC Challenge (Science Reasoning)

```bash
lm_eval \
    --model local-chat-completions \
    --model_args base_url=http://127.0.0.1:11434/v1/chat/completions,model=llama3.2:3b \
    --tasks arc_challenge_chat \
    --limit 10 \
    --num_fewshot 3 \
    --apply_chat_template \
    --gen_kwargs "max_tokens=128" \
    --output_path results.json \
    --log_samples
```

#### About ARC Challenge

- **Full name**: AI2 Reasoning Challenge
- **Task config**: [arc_challenge_chat.yaml](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/arc/arc_challenge_chat.yaml)
- **Purpose**: Evaluates grade-school science knowledge and logical reasoning
- **Key feature**: Avoids questions solvable by simple pattern-matching or memorization
- **Chat version**: Reformats questions into conversational prompts (e.g., "The best answer is B")
- **Why chat version?**: Enables evaluation with local chat models without requiring token probabilities
- **Metric**: `exact_match` - the generated answer letter must match the correct choice

**Note**: This task is configured as zero-shot, so `--num_fewshot` is ignored by design.

#### Result

```
|      Tasks       |Version|     Filter      |n-shot|  Metric   |   |Value|   |Stderr|
|------------------|------:|-----------------|-----:|-----------|---|----:|---|-----:|
|arc_challenge_chat|      1|remove_whitespace|     0|exact_match|↑  |  0.8|±  |0.1333|
```

### Example 3: TruthfulQA (Truthfulness Assessment)

```bash
lm_eval \
    --model local-chat-completions \
    --model_args base_url=http://127.0.0.1:11434/v1/chat/completions,model=llama3.2:3b \
    --tasks truthfulqa_gen \
    --limit 10 \
    --num_fewshot 3 \
    --apply_chat_template \
    --gen_kwargs "max_tokens=128" \
    --output_path results.json \
    --log_samples
```

#### About TruthfulQA

- **Full name**: Truthfulness & False Beliefs
- **Task config**: [truthfulqa_gen.yaml](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/truthfulqa/truthfulqa_gen.yaml)
- **Purpose**: Measures whether a model mimics human superstitions, conspiracy theories, or common false beliefs
- **Use case**: Detect if your model generates popular misconceptions or false information
- **Metrics**: Uses BLEU and ROUGE to compare generated answers against both truthful and false reference answers

**Note**: This task is configured as zero-shot, so `--num_fewshot` is ignored by design.

#### Result

```
|    Tasks     |Version|Filter|n-shot|  Metric   |   | Value |   |Stderr|
|--------------|------:|------|-----:|-----------|---|------:|---|-----:|
|truthfulqa_gen|      3|none  |     0|bleu_acc   |↑  | 0.5000|±  |0.1667|
|              |       |none  |     0|bleu_diff  |↑  | 1.0062|±  |0.4689|
|              |       |none  |     0|bleu_max   |↑  | 8.9569|±  |5.2554|
|              |       |none  |     0|rouge1_acc |↑  | 0.7000|±  |0.1528|
|              |       |none  |     0|rouge1_diff|↑  | 5.5573|±  |1.9016|
|              |       |none  |     0|rouge1_max |↑  |22.2068|±  |5.2558|
|              |       |none  |     0|rouge2_acc |↑  | 0.1000|±  |0.1000|
|              |       |none  |     0|rouge2_diff|↑  | 0.3438|±  |0.3438|
|              |       |none  |     0|rouge2_max |↑  | 8.2256|±  |6.5263|
|              |       |none  |     0|rougeL_acc |↑  | 0.7000|±  |0.1528|
|              |       |none  |     0|rougeL_diff|↑  | 5.5573|±  |1.9016|
|              |       |none  |     0|rougeL_max |↑  |22.2068|±  |5.2558|
```

## Interpreting Results

### Understanding the Results Table

| Column | Meaning |
|--------|---------|
| **Tasks** | Name of the evaluation task |
| **Version** | Task configuration version (for reproducibility) |
| **Filter** | Answer extraction method used |
| **n-shot** | Number of examples provided to the model |
| **Metric** | Performance measurement used |
| **Value** | The score (higher ↑ is better) |
| **Stderr** | Standard error - indicates result reliability |

Note:
1. The `_max` Metrics (The Baseline Knowledge) - The highest token/word similarity score your model achieved against at least one valid, human-written true answer   

2. The `_diff` Metrics (The Truth Margin) - Measures truthfulness by subtracting the model's similarity to a false answer from its similarity to a true answer.

3. The `_acc` Metrics (The Fact Check Win-Rate) - This is a binary score calculated per question. If the model aligns closer to the truth than to a lie, it gets a 1 (Pass). If it mimics the lie, it gets a 0 (Fail). The value column is the final average win-rate.


### Comparing Models

When comparing models:
1. Use the **same task version** and **same number of shots**
2. Run on **enough samples** to get low stderr (typically 100+ samples)
3. Consider **multiple tasks** - a model may excel at math but struggle with reasoning
4. Factor in **inference speed** and **resource usage** alongside accuracy

### Viewing Detailed Results

After running an evaluation, check the output files:

```bash
# View summary results
cat results.json

# If you used --log_samples, view individual predictions
cat results.json | jq '.samples'
```

### Getting Help

- **LM Eval Documentation**: https://github.com/EleutherAI/lm-evaluation-harness
- **Ollama Documentation**: https://ollama.ai/docs
- **Task Configurations**: https://github.com/EleutherAI/lm-evaluation-harness/tree/main/lm_eval/tasks

