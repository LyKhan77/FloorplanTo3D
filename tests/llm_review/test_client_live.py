from typing import Literal

import pytest
from pydantic import BaseModel


class YesNo(BaseModel):
    answer: Literal["yes", "no"]


@pytest.mark.strata
def test_live_strata_answers_schema_json(strata_live):
    r = strata_live.ask_json([{"role": "user", "content": 'Is 7 a prime number? Answer as {"answer": "yes"|"no"}.'}],
                             YesNo, effort="none", temperature=0)
    assert r.valid and r.parsed == {"answer": "yes"} and r.tokens["prompt"] > 0
