# GitHub Codespaces setup (secondary, limited hosted environment)
1. Open https://github.com/jimedusot-beep/Toadsagemode in Safari and choose Code > Codespaces > Create codespace on main. This uses your account's compute/storage allowance.
2. In the Codespace terminal run `python3 --version; docker --version; free -h; df -h` to inspect the environment. Docker-in-Docker may require configuration and is not assumed available.
3. Since Ollama models use significant RAM and disk, decide whether the available Codespace machine is sufficient before downloading one. If available, install Ollama according to https://ollama.com/download and pull `qwen2.5-coder:1.5b`, then test the Ollama endpoint. Never forward port 11434 publicly.
4. The GitHub Pages dashboard is static; it does not connect to a Codespace. A local terminal can be used to run an agent separately.
5. If the separate agent package is present, install dependencies in a Python venv, build the sandbox image, and run one task first. A `tmux` session does not prevent the Codespace from stopping due to idle timeout.
6. Stop your Codespace after use to conserve usage allowances. Never assume this is suitable for an always-on autonomous loop.
