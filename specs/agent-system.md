# Agent system requirements

## Objective
The app must behave like a single official GepLex AI workspace where the user can communicate naturally, assign tasks, and let the system act with a disciplined workflow without drift, stale branding, or accidental deletion of the default model.

## Core product requirements
1. The app identity is GepLex and uses the transparent custom logo across browser chrome, favicons, app shell, and status icons.
2. The default model is always `GepLex`.
3. The built-in default endpoint is `geplex-ai-core` and it must remain protected from deletion.
4. Only non-default models can be deleted through the normal admin workflow.
5. The app must allow communication with the user in a structured, readable, and transparent way.
6. The system must break work into tasks, use tools only when allowed, and confirm results before finalizing.
7. The system must validate work before presenting success.
8. The system must keep requirements, model defaults, and branding state frozen so they cannot drift over time.

## Communication requirements
- The assistant must answer in clear, concise language.
- It must explain what it understood, what it is doing, and what it verified.
- It must never claim success without evidence.
- It must preserve user context across interactions.
- If a task is uncertain, it must ask for missing facts before changing critical behavior.

## Agent workflow requirements
1. Parse request.
2. Extract goals, constraints, and risk areas.
3. Decompose the task into ordered steps.
4. Select the correct default model or route.
5. Use only approved tools.
6. Validate the result before returning it.
7. Summarize the outcome with evidence.

## Model routing requirements
- Default route: `geplex-ai-core`
- Task types map to the official default route
- Unknown or generic tasks still route to the same official model unless an override is explicitly required
- No second default model may be introduced in config or UI

## Tool-use requirements
- Tools must be registered explicitly.
- Unregistered tools must be rejected.
- Tool execution must be safe and bounded.
- Tool output must be surfaced as evidence, not hidden.
- Write operations should be logged and validated.

## Safety and governance requirements
- Protected official model and endpoint must never be deleted.
- Delete buttons must be hidden for the protected default entry.
- Non-default models remain configurable and deletable.
- The app must reapply the default seed on startup to reduce drift.
- Hidden stale model entries must not be reintroduced by default seeding.

## Acceptance criteria
- App loads with official GepLex branding.
- Default model is `GepLex` everywhere the app lists or seeds models.
- Endpoint `geplex-ai-core` is present and protected.
- Delete action is hidden for the protected model only.
- Agent runtime exposes status, plan, and run APIs.
- Agent execution returns a structured result with model id, tool calls, and validation.
- Focused tests pass for the runtime and official-model defaults.

## Implementation rule
The system must behave as a locked official configuration with a disciplined agent runtime. No extra model should become active by default, no protected model should be deleted, and no user-facing output should be presented without validation.
