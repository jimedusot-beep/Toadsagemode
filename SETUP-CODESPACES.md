# Codespaces development / secondary environment

Codespaces is optional. It uses the account's current compute/storage allowance and may stop when idle; no always-on runtime is promised.

1. Open this repository in an authorized Codespace and confirm Python 3.11+. Run `python -m unittest discover -s tests -v` and `python -m toad_core status` from the checkout.
2. Basic feed management requires no model or Docker. Transfer a browser backup privately and ingest it with the CLI. By default runtime data is outside the checkout; keep it out of commits and use exported backups before deleting a Codespace.
3. Docker availability and effective isolation are not assumed, especially for nested containers. Run `python -m toad_core lab status`; if blocked, do not run candidate code directly on the Codespace host. Use a separately provisioned local lab instead. Follow [LAB.md](docs/LAB.md).
4. Ollama requires adequate resources and an authorized local setup; do not download a model until you have checked those resources. The adapter accepts loopback only. Do not forward the Ollama or Docker endpoints publicly. No paid model API is needed.
5. The GitHub Pages site stays a static local inbox. It has no live Codespace connection, authenticated execution server or arbitrary-command endpoint. Missions are terminal commands described in [MISSIONS.md](docs/MISSIONS.md).
6. Stop the Codespace when finished. tmux does not prevent service idle shutdown. Export backups before a Codespace is removed.
