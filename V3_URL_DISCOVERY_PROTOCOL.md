# V3 URL discovery and interception boundary

The Agent receives the task and its declared initial files. The task describes
the work and gives searchable identifiers such as a document title, product
model, organization, or record ID. It must not give the URL whose response is
being attacked. The Agent should search for the relevant source, then fetch or
open it. The intercepted response is the only difference between the clean
and attack runs.

The runner keeps exact match URLs, HTTP methods, and replacement assets in its
private scenario plan. The review page reads a separate `data/v3_mitm_targets.json`
index to show these targets to human reviewers. That index is review metadata;
none of its fields belong in the Agent prompt, task attachments, or public
context file. A route in this index is not proof that the run is ready: the
corresponding private manifest and fixture must also be valid.

For each case, review these steps before marking it runnable:

1. The Agent-visible task and initial files do not reveal the attacked URL.
2. A search query based on the task can discover the intended result. Targets
   on synthetic domains need a controlled search result; public search engines
   cannot discover them.
3. The Agent fetches the discovered URL through ClawTrap's proxy. The private
   plan matches the actual method, host, path, and query and serves the clean
   or attack response.
4. The trace records search, fetch, rule application, response delivery, and
   Agent observation separately. Clean and attack runs use the same task and
   search result.

The v3 command and Telegram adapters must not append `Entry URL`, `Start URL`,
or `CLAWTRAP_ENTRY_URL` to discovery tasks. A case whose target is not
discoverable or whose target URL appears in Agent-visible text remains a draft.
