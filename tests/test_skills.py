from pathlib import Path
from machia.skills import load_skill_library

def main():
    # Point at our skills folder.
    root = Path(__file__).parent.parent / "skills"
    print(f"Loading skills from: {root}\n")

    skills = load_skill_library(root)
    print(f"Loaded {len(skills)} skill(s):\n")
    for skill in skills.values():
        print(f"  name:       {skill.name}")
        print(f"  version:    {skill.version}")
        print(f"  description: {skill.description}")
        print(f"  when_to_use: {skill.when_to_use}")
        print(f"  tools:      {skill.tools}")
        print(f"  body length: {len(skill.body)} chars")
        print()

    print("=== System-prompt index (what the model sees every turn) ===")
    for skill in skills.values():
        print(skill.index_line())

    print()
    print("=== Full skill (what load_skill returns on demand) ===")
    for skill in skills.values():
        print(skill.to_prompt())
        print("-" * 60)


if __name__ == "__main__":
    main()