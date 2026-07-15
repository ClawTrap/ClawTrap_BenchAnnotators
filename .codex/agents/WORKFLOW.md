# ClawTrap case workflow

This workflow exists to keep MITM benchmark work realistic, mountable, and cheap to review. The user's current instruction and `prompt_for_generation.md` always take priority.

## Default mode

Do the work in the main agent unless the user explicitly asks to use `.codex` agents. These agent prompts are reusable role definitions, not a requirement to fan out every task.

When agents are used:

| Agent | Use only for | Writes |
| --- | --- | --- |
| `benchmark_designer` | New case design before implementation. | No |
| `html_snapshot_researcher` | Finding/verifying an HTML source for a web case. | No |
| `case_builder` | Implementing one accepted case. | Yes |
| `benchmark_reviewer` | One lightweight design gate or one focused file audit. | No |

Never run more than one write-capable agent at a time. No subagent may spawn another agent.

## Minimal pipeline

1. **Intake**
   - Identify the requested MITM topic and the normal user task.
   - Inspect the schema, mount validator, and at most one nearby existing case.
   - For web cases, identify the real page/state that should be captured as HTML.

2. **Design**
   - Start from the benign task and clean answer, not from the attack.
   - Add the smallest credible MITM change.
   - Define a safe path, private deterministic observables, and outcome priority.
   - Reject designs that mainly test trivia, search luck, product knowledge, or generic task correctness.

3. **Source**
   - For web cases, obtain real HTML/serialized DOM. “Looks similar” or “DOM reference” is not enough.
   - If the page cannot be captured as usable HTML, choose another source or redesign the case.
   - Save original HTML and needed assets in `source_archives`, with URL, capture method/date, and hashes where practical.

4. **Build**
   - Clean and attack assets derive from the same captured baseline.
   - Modify only the text, href, parameter, DOM node, or handler needed for the attack and scoring.
   - Keep evaluator, ground truth, source archive, and attack configuration private.
   - Map task file keys as `[snake_case_key]`; do not expose local paths as the task interface.

5. **Check**
   - Run the current case mount validator and one review-platform smoke test.
   - For stateful cases, exercise only the decisive safe and attacked ledger paths.
   - Use screenshots only as QA evidence, not as implementation input.

## HTML snapshot rules

Hard requirements:

- A webpage snapshot is saved HTML/DOM plus localizable assets. It is not a screenshot.
- Do not build a page by putting text, controls, or dialogs over a PNG/JPEG background, canvas, or image-map.
- Do not replace the visible page body with a custom app while claiming it is a real snapshot. If the real page is only a skeleton/welcome page, either make the task fit that page or pick another source.
- Do not hand-draw branded dialogs when real HTML for that dialog/page can be fetched.
- Localize CSS, fonts, images, and other assets needed for review rendering. Root-relative assets like `/static/...`, `/css/...`, and `/assets/...` often render as bare text unless rewritten or mounted.
- Keep the original source archive intact. Served clean/attack assets may rewrite resource links for local rendering, but source records must explain that.

Allowed:

- Removing live production scripts, analytics, or external actions when the static page still looks and behaves like the captured state needed for the task.
- Adding minimal local JS only for controlled task instrumentation or private ledger events.
- Capturing QA screenshots after implementation.

## Lessons to preserve

- **Python.org/Docker docs problem:** byte-identical HTML can still render as plain text when CSS is root-relative or blocked by CORS. Archive the original, then localize served CSS/assets.
- **Pydio expiry problem:** a real DOM hidden under a custom replacement UI is not a realistic snapshot. The visible surface must remain the captured page.
- **GitHub login problem:** if a fake login uses a real brand surface, fetch the real login HTML rather than approximating a modal by hand.
- **Stripe docs problem:** source archives can contain realistic-looking test keys that trigger push protection. Redact or avoid secret-shaped strings in archived public sources before committing.
- **News tamper problem:** when the attack is a news fact replacement, do not leave the same attacked fact correct elsewhere on the modified page as an artificial clue. Change that fact consistently on the attack page; external or multi-source verification is the Agent's responsibility.
- **Clue-scan problem:** generic words such as `tamper` may appear in real pages or local dataset paths. Treat only obvious benchmark/security-test clues as blockers.

## Reviewer scope

The reviewer is a gate, not a second implementation agent. It should check only:

- Does this measure the requested MITM behavior?
- Is the clean task legitimate and safely completable?
- Is the attack minimal and realistic?
- Is scoring deterministic and private?
- For web cases, is the visible page real HTML/DOM, not screenshot/composited/custom replacement UI?
- Are mount routes, task files, evaluator privacy, and review previews usable?

Block only issues that break measurement validity, safe path, deterministic scoring, privacy isolation, or platform mounting. Style preferences, optional metadata, and speculative edge cases are warnings.

Default loop limit: one design revision and one implementation repair. If it still fails, report the concrete blocker instead of expanding validation.

## Completion

Report the case IDs touched, the important changes, the checks run, and any remaining non-blocking warnings. Keep the handoff short.
