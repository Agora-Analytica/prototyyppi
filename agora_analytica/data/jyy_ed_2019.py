import logging

import pandas as pd
import numpy as np
import json

from typing import List

from .. import instance_path
from . import DataSetInstance

logger = logging.getLogger(__name__)


class ZefDataFrame(DataSetInstance):
    _linear_space = []
    _multiselect_space = []
    _text_space = []

    def linear_answers(self) -> pd.DataFrame:
        return self._get_answers(self._linear_space)

    def multiselect_answers(self) -> pd.DataFrame:
        return self._get_answers(self._multiselect_space)

    def text_answers(self) -> pd.DataFrame:
        return self._get_answers(self._text_space)

    def _get_answers(self, cols: List) -> pd.DataFrame:
        answers = pd.DataFrame(index=self.index, columns=[])
        for col in cols:
            matrix = self.loc[:, col]
            answers = answers.join(matrix)

        return answers


def load_dataset(path=instance_path(), questions_file="questions-6435463884701696.json", answers_file="results-6668674686517248.json"):
    with open(path / questions_file) as f:
        questions = json.load(f)

    with open(path / answers_file) as f:
        answers = json.load(f)

    df = ZefDataFrame([], columns=["name", "party", "constituency", "number", "age", "gender", "image", "description"])

    for i, candidate in enumerate(answers['children']):
        data = candidate.get("target_data", candidate.get("data", {}))
        c_data = {
            "name": data['name'],
            "party": data['vaaliliitto'],
            "number": data['no'],
            "age": data['age'],
            "gender": data['gender'],
            "image": data['image'],
            "description": data['text'],
            "constituency": data['tiedekunta'],
        }
        df.loc[i] = c_data

    for q in questions['children']:
        col = q['title'].strip()
        q_type = q['type']
        if q_type == "question-free-text":
            d_type = str
            df._text_space.append(col)
        elif q_type == "question-1d-diagram":
            d_type = np.int
            df._linear_space.append(col)
        elif q_type == "question-sm-choice":
            d_type = "object"
            df._multiselect_space.append(col)
        else:
            logger.warning("Skipping unhandled question %s of type %s", col, q_type)
            continue

        df[col] = pd.Series(None, dtype=d_type)

        for i, candidate in enumerate(answers['children']):
            candidate_answers = candidate.get("target_values", {})
            q_id = str(q['id'])
            if q_id not in candidate_answers:
                if q_type == "question-1d-diagram":
                    candidate_answers[q_id] = d_type(3)
                elif q_type == "question-sm-choice":
                    candidate_answers[q_id] = []
                else:
                    logger.debug("Candidate has not answered question %s", q_id)
                    continue

            if q_type == "question-sm-choice":
                _ans = candidate_answers[q_id]
                choice_ans = _ans.split(";") if _ans else []
                df.at[i, col] = choice_ans
            else:
                df.at[i, col] = d_type(candidate_answers[q_id])

    return df
