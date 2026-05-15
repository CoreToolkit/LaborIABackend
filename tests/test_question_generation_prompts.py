from datetime import date

from utils.prompts.question_generation import (
    build_group_question_generation_prompts,
    build_question_generation_prompts,
)


class _DummyProfile:
    def __init__(self):
        self.full_name = "Ada Lovelace"
        self.career = "Software Engineer"
        self.university = "Example University"
        self.graduation_date = date(2020, 6, 1)
        self.description = "Backend engineer with Python and APIs."
        self.english_level = type("EnglishLevel", (), {"value": "Advanced"})()


class _DummyItem:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_build_question_generation_prompts_includes_profile_context():
    profile = _DummyProfile()
    skills = [_DummyItem(name="Python", level="Senior", category="backend")]
    experiences = [_DummyItem(position="Developer", company="Acme", start_date=date(2021, 1, 1), end_date=None, currently_working=True, description="Built APIs")]

    system_prompt, user_prompt = build_question_generation_prompts(
        profile=profile,
        skills=skills,
        experiences=experiences,
        target_skill="Python",
        difficulty="intermediate",
        previous_questions=["What is a database index?"],
    )

    assert "entrevistas técnicas" in system_prompt
    assert "Ada Lovelace" in user_prompt
    assert "Python" in user_prompt
    assert "What is a database index?" in user_prompt


def test_build_group_question_generation_prompts_includes_role_and_profile_context():
    profile = _DummyProfile()
    skills = [_DummyItem(name="Python", level="Senior", category="backend")]
    experiences = []

    system_prompt, user_prompt = build_group_question_generation_prompts(
        profile=profile,
        skills=skills,
        experiences=experiences,
        role_name="Backend Developer",
        role_description="Build APIs and services.",
        target_skill="Python",
        difficulty="intermediate",
        previous_questions=["Explain threading in Python."],
    )

    assert "entrevista grupal" in system_prompt
    assert "Ada Lovelace" in user_prompt
    assert "Backend Developer" in user_prompt
    assert "Build APIs and services." in user_prompt
    assert "Explain threading in Python." in user_prompt