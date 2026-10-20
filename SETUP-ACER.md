# Acer / Windows setup

The engine can manage feeds before installing a model or Docker. The computer's specifications and eligibility for Docker/Ollama are not assumed.

1. Install or confirm Python 3.11+: `python --version`. Obtain this repository's source through Git clone or GitHub's source download and open a terminal in its folder.
2. Run `python -m toad_core status`, then ingest a harmless text/source file and export a backup. There are no runtime pip dependencies. For an optional virtual environment: `python -m venv .venv`, activate it using the shell's normal command, and optionally `python -m pip install -e .` to add `toad`.
3. Export the iPhone inbox with **Export backup**, transfer the JSON privately to the computer, and run `python -m toad_core ingest toad-library.json`. Use `python -m toad_core library list`. Browser data is not synced automatically.
4. For restricted tests, separately install a supported Docker Linux backend. On Windows this commonly uses WSL2/Docker Desktop; verify current OS, virtualization, memory and installation requirements with [Docker's official Windows guide](https://docs.docker.com/desktop/setup/install/windows-install/). Administrative setup/restarts and Docker Desktop terms may apply. This chat has not installed it on your Acer.
5. From the checkout, `docker build -t toad-sage-lab:1 lab`, then `python -m toad_core lab status`. The worker requires reported cgroup v2/resource/seccomp enforcement and refuses unsupported hosts. Follow [LAB.md](docs/LAB.md) and run its local containment probes before relying on the environment.
6. For model-assisted missions, install [Ollama](https://ollama.com/download) on the same supported local environment as the engine. Decide the model using actual available RAM/disk; `qwen2.5-coder:1.5b` is a lightweight starting example, not a hardware recommendation or coding-quality guarantee. Run `ollama list`, then `python -m toad_core model status`.
7. Engine/model HTTP must be reachable through loopback. Windows/WSL localhost behavior varies; do not expose Ollama publicly to work around it. Run the engine and Ollama in the same local environment if necessary. See [MISSIONS.md](docs/MISSIONS.md) for configuration and actual commands.
8. Run one bounded harmless mission first. Sleep/reboot stops the process; no background service is installed. The public dashboard has no execution connection to this computer. Keep private catalogs and backups outside the public repository.

Do not place keys, SSH credentials, payment information or browser profiles into the lab. Hardware/robot access and external dependency installation are not supported in the initial worker.
