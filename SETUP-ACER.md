# Acer Windows setup (primary, local runtime)
1. Open PowerShell: `winget --version`; `wsl --status`.
2. Install WSL 2 / Ubuntu with `wsl --install -d Ubuntu` (requires admin and restart if prompted). Check `wsl --status`.
3. Install Docker Desktop for Windows with WSL 2 integration, and verify `docker version` in Ubuntu. Docker Desktop terms and hardware requirements apply; no installation is claimed yet.
4. Install Ollama for Windows from https://ollama.com/download and run `ollama pull qwen2.5-coder:1.5b` in Windows PowerShell. Run `ollama list` to confirm. Linux WSL containers may require explicit host networking address to reach Windows-hosted Ollama: `localhost` is NOT guaranteed to work with every WSL networking mode. Test connection before training.
5. Clone https://github.com/jimedusot-beep/Toadsagemode and set up the agent package on your host. The repository currently contains a static dashboard and setup guides only: you must obtain/install the separate Python agent package before launching.
6. Keep both Windows/WSL and the Ollama server active. Use tmux in Ubuntu to retain a session; sleep/reboot stops it.
7. Do not expose Ollama port 11434 or Docker's API publicly. To reach the Acer from iPhone, prefer an authenticated private VPN with SSH configured.
