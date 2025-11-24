
import wishful
wishful.clear_cache()


from wishful.dynamic.ideas import generate_project_idea
idea1 = generate_project_idea(topic="space", include_project_brief=True, include_plan=True, plan_levels=["Milestone", "Story", "Task"], format="markdown")
print(f"{idea1}")

idea2 = generate_project_idea(topic="space", include_project_brief=True, include_plan=True, plan_levels=["Milestone", "Story", "Task"], format="json", old_ideas_to_avoid=[idea1])
print(f"{idea2}")

