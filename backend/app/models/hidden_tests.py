from pydantic import BaseModel

from app.models.test_case import TestCase


class HiddenTests(BaseModel):
    hidden_tests: list[TestCase]