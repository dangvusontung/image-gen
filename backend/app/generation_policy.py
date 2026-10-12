"""Resolve the saved workflow policy without mutating the project's manual settings."""


WORKFLOW_STEPS = ("master", "turnaround", "concept", "enhance")


def generation_target(project, purpose):
    # A preset is an explicit per-step choice, so it wins over the built-in shortcuts.
    preset = getattr(project, "preset", None)
    step = (preset.steps or {}).get(purpose) if preset else None
    if step and step.get("provider") and step.get("model"):
        return step["provider"], step["model"], step.get("size") or None
    if project.workflow_mode in ("hybrid", "hybrid_gemini") and purpose in ("master", "turnaround", "concept", "enhance"):
        if purpose == "enhance" and project.workflow_mode == "hybrid":
            return "bfl", "flux-2-pro", "1MP"
        return "gemini", "gemini-nano-banana-2.1", "1K"
    return project.provider, project.model, None
