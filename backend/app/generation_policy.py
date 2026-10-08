"""Resolve the saved workflow policy without mutating the project's manual settings."""


def generation_target(project, purpose):
    if project.workflow_mode in ("hybrid", "hybrid_gemini") and purpose in ("master", "turnaround", "concept", "enhance"):
        if purpose == "enhance" and project.workflow_mode == "hybrid":
            return "bfl", "flux-2-pro", "1MP"
        return "gemini", "gemini-nano-banana-2.1", "1K"
    return project.provider, project.model, None
