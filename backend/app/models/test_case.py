from pydantic import BaseModel, field_validator


class TestCase(BaseModel):
    input: str
    expected_output: str

    @field_validator("expected_output", mode="before")
    @classmethod
    def convert_expected_output(cls, value):
        return str(value)