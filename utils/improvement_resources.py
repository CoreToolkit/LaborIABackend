from __future__ import annotations

# Catálogo de recursos hardcodeados por skill.
# Cada recurso tiene: title, url, type (course | article | video | practice)
SKILL_RESOURCES: dict[str, list[dict]] = {
    "python": [
        {"title": "Python oficial — Tutorial", "url": "https://docs.python.org/3/tutorial/", "type": "article"},
        {"title": "Real Python — Intermediate Python", "url": "https://realpython.com/", "type": "course"},
        {"title": "Exercism — Python Track", "url": "https://exercism.org/tracks/python", "type": "practice"},
    ],
    "sql": [
        {"title": "SQLZoo — Interactive SQL", "url": "https://sqlzoo.net/", "type": "practice"},
        {"title": "Mode Analytics SQL Tutorial", "url": "https://mode.com/sql-tutorial/", "type": "course"},
        {"title": "LeetCode Database Problems", "url": "https://leetcode.com/problemset/database/", "type": "practice"},
    ],
    "javascript": [
        {"title": "MDN Web Docs — JavaScript", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide", "type": "article"},
        {"title": "JavaScript.info", "url": "https://javascript.info/", "type": "course"},
        {"title": "Exercism — JavaScript Track", "url": "https://exercism.org/tracks/javascript", "type": "practice"},
    ],
    "typescript": [
        {"title": "TypeScript Handbook", "url": "https://www.typescriptlang.org/docs/handbook/intro.html", "type": "article"},
        {"title": "Total TypeScript — Free Tutorials", "url": "https://www.totaltypescript.com/tutorials", "type": "course"},
    ],
    "react": [
        {"title": "React — Documentación oficial", "url": "https://react.dev/learn", "type": "article"},
        {"title": "Scrimba — Learn React", "url": "https://scrimba.com/learn/learnreact", "type": "course"},
    ],
    "docker": [
        {"title": "Docker — Get Started", "url": "https://docs.docker.com/get-started/", "type": "article"},
        {"title": "Play with Docker", "url": "https://labs.play-with-docker.com/", "type": "practice"},
    ],
    "git": [
        {"title": "Pro Git Book (free)", "url": "https://git-scm.com/book/en/v2", "type": "article"},
        {"title": "Learn Git Branching", "url": "https://learngitbranching.js.org/", "type": "practice"},
    ],
    "algorithms": [
        {"title": "NeetCode — Roadmap", "url": "https://neetcode.io/roadmap", "type": "course"},
        {"title": "LeetCode — Top Interview 150", "url": "https://leetcode.com/studyplan/top-interview-150/", "type": "practice"},
    ],
    "data structures": [
        {"title": "Visualgo — Visualización de estructuras", "url": "https://visualgo.net/en", "type": "article"},
        {"title": "CS50x — Harvard (free)", "url": "https://cs50.harvard.edu/x/", "type": "course"},
    ],
    "system design": [
        {"title": "System Design Primer", "url": "https://github.com/donnemartin/system-design-primer", "type": "article"},
        {"title": "ByteByteGo — System Design", "url": "https://bytebytego.com/", "type": "course"},
    ],
    "java": [
        {"title": "Oracle — Java Tutorials", "url": "https://docs.oracle.com/javase/tutorial/", "type": "article"},
        {"title": "Exercism — Java Track", "url": "https://exercism.org/tracks/java", "type": "practice"},
    ],
    "kotlin": [
        {"title": "Kotlin — Documentación oficial", "url": "https://kotlinlang.org/docs/home.html", "type": "article"},
        {"title": "Kotlin Koans", "url": "https://play.kotlinlang.org/koans/overview", "type": "practice"},
    ],
    "aws": [
        {"title": "AWS Skill Builder (free)", "url": "https://skillbuilder.aws/", "type": "course"},
        {"title": "AWS Well-Architected Framework", "url": "https://aws.amazon.com/architecture/well-architected/", "type": "article"},
    ],
    "fastapi": [
        {"title": "FastAPI — Documentación oficial", "url": "https://fastapi.tiangolo.com/tutorial/", "type": "article"},
        {"title": "TestDriven.io — FastAPI", "url": "https://testdriven.io/blog/topics/fastapi/", "type": "course"},
    ],
    "default": [
        {"title": "freeCodeCamp — Cursos gratuitos", "url": "https://www.freecodecamp.org/learn", "type": "course"},
        {"title": "The Odin Project", "url": "https://www.theodinproject.com/", "type": "course"},
        {"title": "Roadmap.sh — Developer Roadmaps", "url": "https://roadmap.sh/", "type": "article"},
    ],
}


def get_resources_for_skill(skill_name: str) -> list[dict]:
    """Returns hardcoded resources for a skill, falling back to defaults if not found."""
    key = skill_name.lower().strip()
    return SKILL_RESOURCES.get(key, SKILL_RESOURCES["default"])
