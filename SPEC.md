# Character Studio — Implementation Spec for Coding Agent

## Objective
Build a local-first web app that transforms multiple photos of ONE person into a consistent stylized 3D character, creates a multi-angle turnaround, generates nine lifestyle concepts in two batches (5+4), and enhances selected concepts. UI language: Vietnamese. Keep facial identity and individual body morphology consistent.

## Stack
- React + TypeScript + Vite, Tailwind, shadcn/ui, TanStack Query.
- FastAPI + Python 3.12, SQLite + SQLAlchemy + Alembic, Pillow.
- Files stored locally under `data/assets/`; database stores metadata and references.
- Async persistent jobs with bounded concurrency; allow retry, failure isolation and polling.
- pytest, Vitest, Playwright. `.env.example`, README, optional Docker Compose.

## Providers
Implement a provider adapter interface with capabilities, generate/edit, and job polling where applicable.
1. **Google Gemini image generation (Nano Banana family)**: official SDK/API, multiple image references where supported.
2. **Black Forest Labs FLUX**: official API, model-specific image input requirements, polling and result download.
3. **Midjourney**: informational disabled option only; do not use unofficial automation.

Verify CURRENT official model IDs, endpoint payloads, reference limits, supported aspect ratios and pricing during implementation. Never silently discard image references. Show capability errors and model choices. Keys live server-side in environment variables, never in browser code or logs.

## Workflow
### Step 1 — References
Create project; upload 3–8 photos of the same person (allow fewer with warning), preview/reorder/remove; optional side-profile photos. Validate content type, size and image integrity. Ask user to confirm rights/permission to use photos.

### Step 2 — Master character
Generate ONE full-body master character from reference photos. Offer variants, compare, approve one. Save source references, provider, model, prompt, output and approval history. **Preserve facial landmarks, individual proportions and body morphology; change render treatment, not anatomy.** Stylized 3D animation materials, sculpted hair, clean surfaces and soft cinematic lighting. Neutral studio background.

### Step 3 — Turnaround
From approved master (plus real side photos if available), generate SIX angles: front 0°, left 45°, left profile 90°, right 45°, right profile 90°, back 180°. Prefer SIX independent images then assemble sheet in UI. Same character/outfit/lighting/scale. Allow regenerating an individual angle and approval. Turnaround is an AI inference, not verified identity evidence; master remains authoritative.

### Step 4 — Concept generation
Generate **individual standalone images**, NOT one low-resolution collage. Assemble them into a contact sheet in the frontend, with optional export. This ensures each image is already available for full-resolution viewing and enhancement.

**Batch A — 5 slots:**
- A1 Cute & Cozy — front-facing
- A2 Playful & Mischievous — left three-quarter
- A3 Soft & Dreamy — right profile
- A4 Fresh & Adventurous — over-the-shoulder
- A5 Casual & Charming — high-angle candid

**Batch B — 4 slots:**
- B6 Elegant & Confident — right three-quarter
- B7 Chic & Fashionable — low-angle environmental
- B8 Glamorous & Bold — wide full-body
- B9 Mysterious & Cinematic — dynamic off-center

These are mood and angle directions, NOT fixed scenes. Generate a distinct concept brief per slot (setting, activity, outfit, pose, expression, gaze, camera, lighting). Vary scenes and compositions; avoid reusing settings from earlier batches. Shuffle angle-to-mood assignments for later runs while keeping coverage. Preserve master identity and rendering style. Show card statuses independently; allow single-slot regenerate. Mood should be expressed through styling and attitude, not altered anatomy.

### Step 5 — Enhance
Select a concept card; use approved master as identity authority, turnaround as angle reference, and selected concept image as scene/composition reference. Re-render ONE standalone image, default portrait 3:4, with better material, detail and lighting. Preserve chosen outfit, activity, pose, gaze, camera, expression and atmosphere. Do NOT crop/upscale the thumbnail. Provide before/after, version history, downloads. If provider reference limits are exceeded, show a warning and prioritize master then selected concept then relevant turnaround view.

## Main UI
- Dashboard: projects, thumbnails, progress, recent activity.
- Workspace tabs/stepper: References / Master / Turnaround / Concepts (Batch A, Batch B) / Enhance / History.
- Provider settings: model selection, key configured status, capability display, optional connection test.
- Concept grid with independent images, numbered slots, mood, view direction, regenerate/enhance/download.
- Lightbox and side-by-side comparison, prompt editor with reset-to-default, per-job progress and errors.
- Export individual PNG/JPEG and ZIP of project images; optional assembled contact sheet.
- Responsive desktop-first UI, Vietnamese labels, clear empty/loading/error states.

## Prompt templates
Store versioned prompt templates as backend files, with per-project overrides and per-job snapshots. Do not hardcode long prompts in React components.

**Master default:**
```text
Use ALL uploaded photos of the SAME PERSON to create ONE canonical full-body stylized 3D animated character. Preserve distinctive face shape, eye spacing, eyebrows, nose, lips, jaw, chin, hairstyle, skin tone and individual body morphology. Do not impose generic cartoon or fashion-model proportions. Stylize the rendering through smooth sculpted surfaces, dimensional eyes, designed hair masses, simplified materials and soft cinematic lighting, without changing recognizable anatomy. Neutral studio background, natural pose, one complete character, no collage or text. Keep the PERSON. Change the MEDIUM.
```

**Turnaround default:**
```text
Use the approved master as identity authority. Render the SAME character at {angle} with unchanged face, body, hair, outfit, lighting and scale. Rotate character relative to camera, not just eyes. Neutral standing pose and background. Do not mirror or redesign facial features. Output one view only.
```

**Concept default:**
```text
Use the approved master and available turnaround as identity references. Generate ONE cinematic lifestyle scene of the SAME character. Mood: {mood}. Camera/head orientation: {camera}. Avoid previous concepts: {prior_briefs}. Invent a fresh setting, activity, outfit, expression, gaze, lighting and atmosphere. Preserve recognizable facial geometry, hairstyle, body morphology and stylized 3D design. Avoid generic beauty portraits, repeated poses and photographic drift. Output one standalone image without text.
```

**Enhance default:**
```text
Use MASTER as identity authority, TURNAROUND for angle guidance, and SELECTED CONCEPT as scene reference. Recreate this exact scene as ONE polished standalone 3:4 cinematic stylized 3D image. Preserve person, outfit, pose, expression, gaze, camera, environment and mood. Improve detail, materials and lighting without changing the scene or identity. No collage, borders, numbers or text.
```

## Architecture and persistence
Entities: `Project`, `Asset`, `MasterVersion`, `TurnaroundVersion`, `Concept` (batch/slot/mood/brief), `EnhancementVersion`, `GenerationJob`, `PromptTemplate`. Store source asset IDs, approved master version, turnaround version, resolved prompt, provider/model, settings, status, errors, timestamps, outputs, and estimated/actual costs where available. Never overwrite approved outputs; new master approval marks downstream generations as based on an older master, without deleting them.

Suggested API:
```text
GET/POST /api/projects
GET/PATCH/DELETE /api/projects/{id}
POST/GET /api/projects/{id}/assets
GET /api/assets/{asset_id}/content
POST /api/projects/{id}/master/generate
POST /api/projects/{id}/master/{version_id}/approve
POST /api/projects/{id}/turnaround/generate
POST /api/projects/{id}/turnaround/{version_id}/approve
POST /api/projects/{id}/concepts/generate  {batch: "A"|"B"}
POST /api/projects/{id}/concepts/{concept_id}/regenerate
POST /api/projects/{id}/concepts/{concept_id}/enhance
GET /api/projects/{id}/concepts
GET /api/projects/{id}/jobs
GET /api/jobs/{id}
POST /api/jobs/{id}/cancel
GET /api/projects/{id}/export
GET /api/providers
GET /api/providers/{provider}/models
GET/PUT /api/prompts/{name}
```
Use typed request/response schemas, OpenAPI docs and meaningful error codes.

## Jobs, cost and privacy
- Queue image jobs with bounded concurrency, independent slot statuses, retries for safe transient failures, exponential backoff and request-ID tracking. Avoid double-billing on ambiguous submission retries.
- If generation is asynchronous, poll server-side and download provider-hosted assets promptly.
- Show estimated per-image/batch costs if pricing is known, otherwise state unavailable. Configurable spend guard and confirmation before bulk jobs.
- Validate upload contents and sizes; sanitize filenames, avoid path traversal, protect assets from unauthorized network exposure. Bind local server to loopback by default.
- Explain that reference images are sent to chosen third-party provider. No raw base64 or API keys in logs. Document deletion and provider retention limitations.

## Acceptance criteria
1. Create a project, upload photos and generate/approve a master.
2. Generate and approve six independently viewable turnaround angles.
3. Batch A produces exactly FIVE independent image assets; Batch B exactly FOUR, each with saved mood, brief and camera metadata.
4. One failed concept does not destroy successful results; single-slot retry works.
5. Select any slot, enhance to a standalone 3:4 image and compare with source.
6. Project data and generation history survive restart.
7. Secrets never appear in frontend bundles, API responses or logs.
8. Download originals, enhancements, contact sheets and ZIP exports.
9. Mock provider enables full local end-to-end tests without spending API credits.
10. Automated tests pass and README contains copy-paste startup commands.

## Agent execution plan
**Phase 1:** Scaffold repo, DB migrations, asset storage, mock provider, project and upload UI.  
**Phase 2:** Provider abstraction, Gemini and BFL adapters, model registry and jobs.  
**Phase 3:** Master/turnaround workflow, approval/version history.  
**Phase 4:** Nine concept slots, 5+4 batches, diversity briefs, gallery/contact sheet.  
**Phase 5:** Enhance, exports, settings, error handling, tests, documentation.

At the end of each phase: run tests, report changed files and remaining blockers. Do not fabricate successful provider calls; if API credentials are absent, demonstrate flows using the mock provider. Avoid building unrelated features before the MVP works.

## First instruction to the coding agent
Implement this specification as a working local-first application. Start with a concise architecture plan and repository structure, then implement the MVP phase by phase. Verify provider APIs against official current documentation. Prioritize an end-to-end working flow using a mock provider before connecting paid APIs. Provide runnable code, migrations, tests, `.env.example`, and a README with exact startup commands. Ask for clarification only when an irreversible architecture or security decision is blocked.
