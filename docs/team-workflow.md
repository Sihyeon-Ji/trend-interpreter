# Team workflow

Use Notion for problem research, interviews and decisions. Keep executable setup, architecture
and operations documents in this repository so each release has matching instructions.

Suggested GitHub Project status: Backlog / Ready / In progress / Review / Done.
Each issue should state the user outcome, acceptance criteria, owner, and evidence link.
The developer owns implementation/infrastructure; teammates can own interview evidence,
data access, evaluation cases and the demo script.

Before choosing a theme, record:
- Target user and a concrete repeated task.
- Available real data, access rights and a small representative sample.
- Baseline time/error rate and the intended improvement.
- Three-minute demonstration path.
- Five success cases and five failure/edge cases.

Notion, GitHub and GCP MCP connections are optional developer tools, not product dependencies.
No MCP connection is established merely by saving a URL. This setup has GitHub CLI and gcloud
automation; Notion requires an authenticated connector or a separately scoped integration.
Do not store Notion tokens, GCP credentials, or GitHub tokens in the repository.
