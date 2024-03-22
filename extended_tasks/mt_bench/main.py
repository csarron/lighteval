# MIT License

# Copyright (c) 2024 The HuggingFace Team

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


# ruff: noqa: F405, F403, F401
"""
Custom evaluation tasks for lighteval. Copy this file and complete it with the info for your task.
This file generally create just a TASKS_TABLE and TASKS_GROUPS which are then imported by LightEval.
Author:
"""

import numpy as np
from aenum import extend_enum
from transformers import AutoModelForCausalLM, AutoTokenizer

from extended_tasks.mt_bench.judges import JudgeOpenAI
from lighteval.metrics import Metrics
from lighteval.metrics.utils import MetricCategory, MetricUseCase, SampleLevelMetric, SampleLevelMetricGrouping
from lighteval.tasks.lighteval_task import LightevalTaskConfig
from lighteval.tasks.requests import Doc
from lighteval.tasks.tasks_prompt_formatting import LETTER_INDICES


# EVAL WITH NO SUBSET ##
# This is how you create a simple tasks (like hellaswag) which has one single subset
# attached to it, and one evaluation possible.
task = LightevalTaskConfig(
    name="mt_bench",
    prompt_function="prompt_fn",  # must be defined in the file or imported from src/lighteval/tasks/tasks_prompt_formatting.py
    suite=["extended"],
    hf_repo="SaylorTwift/mt-bench",
    hf_subset="default",
    hf_avail_splits=["train"],
    evaluation_splits=["train"],
    few_shots_split="",
    few_shots_select="random",
    metric=["mt_bench_metric"],
    generation_size=1024,
    stop_sequence=[],
)


# DEFINE YOUR PROMPT FUNCTIONS
# Define as many as you need for your different tasks
def prompt_fn(line, task_name: str = None):
    """Defines how to go from a dataset line to a doc object.
    Follow examples in src/lighteval/tasks/tasks_prompt_formatting.py, or get more info
    about what this function should do in the README.
    """
    return Doc(
        task_name=task_name,
        query=f"{line['turns'][0]}",
        choices=None,
        instruction=None,
        gold_index=[],
        specific={
            "reference": line["reference"],
            "category": line["category"],
            "multi_turn_queries": line["turns"],
            "id": line["question_id"],
        },
    )


def mt_bench_metric(predictions: list[str], formatted_doc: Doc, **kwargs) -> dict[str, float]:
    """Defines how to go from a list of predictions to a score.
    Follow examples in src/lighteval/metrics/metrics.py, or get more info
    about what this function should do in the README.
    """

    judge = JudgeOpenAI(
        model="gpt-3.5-turbo",
        seed=42,
        temperature=0.0,
        templates_path="extended_tasks/mt_bench/judge_prompts.jsonl",
    )

    questions = formatted_doc.specific["multi_turn_queries"]
    ref_answers = formatted_doc.specific["reference"]

    score, messages, judgement = judge.evaluate_answer(questions, predictions, ref_answers, single_turn=True)
    score_mt, messages_mt, judgement_mt = judge.evaluate_answer(questions, predictions, ref_answers, single_turn=False)

    return {
        "single_turn": score,
        "multi_turn": score_mt,
        "user_prompt": [messages, messages_mt],
        "judgement": [judgement, judgement_mt],
    }


mt_bench_metric = SampleLevelMetricGrouping(
    metric="mt_bench_metric",
    higher_is_better=True,
    category=MetricCategory.GENERATIVE_MULTI_TURN,
    use_case=MetricUseCase.SUMMARIZATION,
    sample_level_fn=mt_bench_metric,
    corpus_level_fn={
        "single_turn": np.mean,
        "multi_turn": np.mean,
    },
)

# STORE YOUR EVALS
_TASKS = [task]

# MODULE LOGIC
# You should not need to touch this
# Convert to dict for lighteval
TASKS_TABLE = [task.as_dict() for task in _TASKS]
extend_enum(
    Metrics,
    "mt_bench_metric",
    mt_bench_metric,
)

if __name__ == "__main__":
    print(t["name"] for t in TASKS_TABLE)
    print(len(TASKS_TABLE))
