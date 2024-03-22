import ast
import json
import re
import time
from abc import ABC

from openai import OpenAI

from lighteval.logging.hierarchical_logger import hlog_warn


# Abstract class for a judge
class Judge(ABC):
    def evaluate_answer(answers, questions, references) -> tuple[str, list[dict[str, str]], str]:
        pass


class JudgeOpenAI(Judge):
    def __init__(self, model: str, seed: int, temperature: float, templates_path: str):
        self.client = OpenAI()
        self.model = model
        self.seed = seed
        self.temperature = temperature

        data = []
        with open(templates_path, "r") as f:
            for line in f:
                tmp = json.loads(line)
                data.append(tmp)

        self.templates = {d["name"]: d for d in data}

        self.one_score_pattern = re.compile(r"\[\[(\d+\.?\d*)\]\]")
        self.one_score_pattern_backup = re.compile(r"\[(\d+\.?\d*)\]")

        self.API_MAX_RETRY = 16
        self.API_RETRY_SLEEP = 10
        self.max_tokens = 2048

    def evaluate_answer(
        self, questions: list[str], answers: list[str], references: list[str], single_turn: bool
    ) -> tuple[int, list[dict[str, str]], str]:
        if single_turn:
            prompts = self.__get_prompts_single_turn(
                questions[0], answers[0], references[0] if len(references) > 0 else None
            )
        else:
            prompts = self.__get_prompts_multi_turn(
                questions[0], answers[0], references[0] if len(references) > 0 else None
            )

        for _ in range(self.API_MAX_RETRY):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    seed=self.seed,
                    temperature=self.temperature,
                    messages=prompts,
                    max_tokens=self.max_tokens,
                    n=1,
                )
                break
            except Exception as e:
                hlog_warn(f"{type(e), e}")
                time.sleep(self.API_RETRY_SLEEP)

        judgment = response.choices[0].message.content
        score = self.__process_judge_response(judgment)

        return score, prompts, judgment

    def __get_prompts_multi_turn(self, questions, answers, references):
        if references is None or len(references) == 0:
            system_prompt = {"role": "system", "content": self.templates["single-v1-multi-turn"]["system_prompt"]}
            user_prompt_str = self.templates["single-v1-multi-turn"]["prompt_template"].format(
                question_1=questions[0], answer_1=answers[0], question_2=questions[1], answer_2=answers[1]
            )
        else:
            system_prompt = {"role": "system", "content": self.templates["single-math-v1-multi-turn"]["system_prompt"]}
            user_prompt_str = self.templates["single-math-v1-multi-turn"]["prompt_template"].format(
                question_1=questions[0],
                answer_1=answers[0],
                ref_answer_1=references[0],
                question_2=questions[1],
                answer_2=answers[1],
                ref_answer_2=references[1],
            )
        user_prompt = {"role": "user", "content": user_prompt_str}
        return [system_prompt, user_prompt]

    def __get_prompts_single_turn(self, question, answer, reference):
        if reference is None or len(reference) == 0:
            system_prompt = {"role": "system", "content": self.templates["single-v1"]["system_prompt"]}
            user_prompt_str = self.templates["single-v1"]["prompt_template"].format(question=question, answer=answer)
        else:
            system_prompt = {"role": "system", "content": self.templates["single-math-v1"]["system_prompt"]}
            user_prompt_str = self.templates["single-math-v1"]["prompt_template"].format(
                question=question, answer=answer, ref_answer_1=reference
            )
        user_prompt = {"role": "user", "content": user_prompt_str}
        return [system_prompt, user_prompt]

    def __process_judge_response(self, judgment: str) -> int:
        match = re.search(self.one_score_pattern, judgment)
        if not match:
            match = re.search(self.one_score_pattern_backup, judgment)
        if match:
            rating = ast.literal_eval(match.groups()[0])
        else:
            rating = -1

        return rating