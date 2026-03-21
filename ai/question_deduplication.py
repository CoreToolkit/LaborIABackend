"""
Question deduplication logic for interview question generation.
Handles normalization, similarity detection, and merge of previous questions.
"""

from difflib import SequenceMatcher

# Configuration constants
MAX_QUESTION_HISTORY = 30
MAX_GENERATION_ATTEMPTS = 3
SIMILARITY_THRESHOLD = 0.82


def normalize_question(text: str) -> str:
    """Normalize question text for comparison (lowercase, strip whitespace)."""
    return " ".join((text or "").strip().lower().split())


def merge_previous_questions(*question_lists: list[str]) -> list[str]:
    """
    Merge multiple question lists, removing duplicates by normalized text.
    
    Args:
        *question_lists: Variable number of question lists to merge
    
    Returns:
        Merged list with duplicates removed
    """
    merged: list[str] = []
    seen: set[str] = set()

    for questions in question_lists:
        for question in questions:
            normalized = normalize_question(question)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(question)

    return merged


def question_similarity(a: str, b: str) -> float:
    """
    Calculate similarity between two questions using SequenceMatcher.
    
    Args:
        a: First question
        b: Second question
    
    Returns:
        Float between 0 and 1, where 1 is identical
    """
    return SequenceMatcher(
        None, normalize_question(a), normalize_question(b)
    ).ratio()


def is_repeated_or_too_similar(
    question: str, previous_questions: list[str]
) -> bool:
    """
    Check if question is repeated or too similar to previous questions.
    
    Args:
        question: Question to check
        previous_questions: List of previous questions to compare against
    
    Returns:
        True if repeated or too similar, False otherwise
    """
    normalized_question = normalize_question(question)
    if not normalized_question:
        return True

    for prev in previous_questions:
        normalized_prev = normalize_question(prev)
        
        # Exact match
        if normalized_question == normalized_prev:
            return True
        
        # Similarity threshold
        if question_similarity(normalized_question, normalized_prev) >= SIMILARITY_THRESHOLD:
            return True

    return False
