def generate_onboarding_prompt(role, repository_context, git_history):
    """
    Create a prompt for generating a role-based
    developer onboarding plan.
    """

    prompt = f"""
You are IntelliOnboard, an AI developer onboarding assistant.

Create a practical onboarding plan for a developer who is joining
an unfamiliar GitHub repository.

Developer Role:
{role}

Repository Information:
{repository_context}

Git History:
{git_history}

Create a 7-day onboarding plan.

For each day include:
1. Day number
2. Topic to understand
3. Files or modules to explore
4. Practical task
5. Expected learning outcome

Keep the plan simple and practical.

Do not invent files or technologies that are not present
in the repository information.

Format the response clearly using:

Day 1:
Topic:
Files/Modules:
Task:
Outcome:

Day 2:
Topic:
Files/Modules:
Task:
Outcome:

Continue until Day 7.
"""

    return prompt


def normalize_role(role):
    """
    Convert the user's role into a simple standard format.
    """

    role = role.strip().lower()

    role_mapping = {
        "beginner": "Beginner Developer",
        "backend": "Backend Developer",
        "backend developer": "Backend Developer",
        "frontend": "Frontend Developer",
        "frontend developer": "Frontend Developer",
        "data scientist": "Data Scientist / ML Engineer",
        "data scientist / ml engineer": "Data Scientist / ML Engineer",
        "ml engineer": "Data Scientist / ML Engineer"
    }

    return role_mapping.get(
        role,
        role.title()
    )
