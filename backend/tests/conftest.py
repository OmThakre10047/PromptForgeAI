import pytest

from app.core.config import Settings
from app.llm.service import LLMService
from app.services.runs import RunService

PROBLEM = """Given n integers, find the maximum sum of a non-empty contiguous subarray.

Input: n on the first line, then n integers.
Output: the maximum subarray sum.

Example Input:
5
-2 1 -3 4 -1

Example Output:
4
"""


@pytest.fixture
def settings(tmp_path):
    return Settings(MOCK_MODE="true", DATA_DIR=tmp_path, RUN_TIMEOUT_S=2.0, _env_file=None)


@pytest.fixture
def llm(settings):
    return LLMService(settings)


@pytest.fixture
def runs(settings, llm):
    return RunService(llm=llm, settings=settings)
