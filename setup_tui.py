import os
import sys
import json
import time
import subprocess
from pathlib import Path
import httpx
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from dotenv import set_key, load_dotenv

if os.name == "nt":
    import msvcrt
else:
    msvcrt = None

# Initialize Rich Console
console = Console()

CONFIG_FILE = Path("config.json")
DOTENV_FILE = Path(".env")

DEFAULT_CONFIG = {
    "selected_provider": "gemini",
    "target_model_name": "gemini-1.5-flash",
    "active_persona_profile": "cybernetic",
    "polling_frequency_seconds": 30,
    "authorized_phone_number": "919876543210",
    "gamification_level": 1,
    "accumulated_experience": 0,
    "llm_fallback_models": [
        "gemini/gemini-1.5-flash",
        "openrouter/google/gemini-flash-1.5",
        "ollama/gemma2"
    ],
    "openwa_gateway_url": "http://localhost:8080",
    "xp_per_task_completion": 50,
    "xp_level_thresholds": [0, 100, 300, 600, 1000, 1500, 2200, 3000, 4000, 5500]
}

PROVIDER_ENV_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "grok": "GROK_API_KEY",
    "nvidia_nim": "NVIDIA_API_KEY",
    "ollama": None
}

PROVIDER_DEFAULT_MODELS = {
    "gemini": "gemini-1.5-flash",
    "openrouter": "google/gemini-flash-1.5",
    "grok": "grok-2",
    "nvidia_nim": "meta/llama3-70b-instruct",
    "ollama": "gemma2"
}

def clear_terminal():
    os.system("cls" if os.name == "nt" else "clear")

def print_banner():
    banner_text = """
   ______ __                                ____        __ 
  / ____// /_   _____ ____   ____   ____   / __ \ ___  / /_
 / /    / __ \ / ___// __ \ / __ \ / __ \ / /_/ // _ \/ __/
/ /___ / / / // /   / /_/ // / / // /_/ // ____//  __/ /_  
\____//_/ /_//_/    \____//_/ /_/ \____//_/     \___/\__/  
                                                           
              Configuration & Setup Wizard
    """
    console.print(Panel(Text(banner_text, style="cyan bold"), border_style="blue"))

def load_config():
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        console.print(f"[bold red]Error loading config.json: {e}. Using defaults.[/bold red]")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        console.print(f"[bold red]Failed to save config.json: {e}[/bold red]")
        return False

def get_env_var(key):
    if not DOTENV_FILE.exists():
        return ""
    load_dotenv(DOTENV_FILE)
    return os.environ.get(key, "")

def set_env_var(key, value):
    if not DOTENV_FILE.exists():
        with open(DOTENV_FILE, "w") as f:
            f.write("")
    set_key(str(DOTENV_FILE), key, value)

PROCESS_STATE_FILE = Path(".active_processes.json")
LOGS_DIR = Path("logs")

def get_active_processes():
    if not PROCESS_STATE_FILE.exists():
        return {}
    try:
        with open(PROCESS_STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_active_processes(processes):
    try:
        with open(PROCESS_STATE_FILE, "w") as f:
            json.dump(processes, f, indent=4)
    except Exception as e:
        console.print(f"[bold red]Failed to save process state: {e}[/bold red]")

def is_pid_running(pid):
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                exit_code = ctypes.c_ulong()
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                kernel32.CloseHandle(handle)
                return exit_code.value == 259
            else:
                return kernel32.GetLastError() == 5
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        try:
            res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, timeout=1.0)
            return str(pid) in res.stdout
        except Exception:
            return False

def kill_process_tree(pid):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=True)
        else:
            import signal
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        return True
    except Exception:
        try:
            os.kill(pid, 9 if os.name != 'nt' else 15)
            return True
        except Exception:
            return False

def start_service(name, cmd, cwd, env=None):
    LOGS_DIR.mkdir(exist_ok=True)
    log_path = LOGS_DIR / f"{name}.log"
    log_file = open(log_path, "a", encoding="utf-8")
    log_file.write(f"\n--- SERVICE STARTED: {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    log_file.flush()
    try:
        proc_env = os.environ.copy()
        proc_env["PYTHONUNBUFFERED"] = "1"
        if env:
            proc_env.update({str(k): str(v) for k, v in env.items() if v is not None})
        use_shell = isinstance(cmd, str)
        if os.name == "nt":
            process = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                env=proc_env,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                shell=use_shell,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            process = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                env=proc_env,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                shell=use_shell,
                preexec_fn=os.setsid
            )
        log_file.close()
        state = get_active_processes()
        state[name] = {
            "pid": process.pid,
            "start_time": time.time(),
            "cmd": cmd,
            "cwd": str(cwd)
        }
        save_active_processes(state)
        return True
    except Exception as e:
        console.print(f"[bold red]Failed to start service {name}: {e}[/bold red]")
        return False

def stop_service(name):
    state = get_active_processes()
    if name not in state:
        return False
    pid = state[name]["pid"]
    success = kill_process_tree(pid)
    if name in state:
        del state[name]
    save_active_processes(state)
    return success

def get_last_n_lines(filepath, n=30):
    if not filepath.exists():
        return [f"[yellow]Log file {filepath.name} does not exist yet. Launch service to generate logs.[/yellow]"]
    try:
        with open(filepath, "rb") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            
            buffer_size = 1024
            lines = []
            leftover = b""
            position = file_size
            
            while position > 0 and len(lines) <= n:
                to_read = min(buffer_size, position)
                position -= to_read
                f.seek(position)
                chunk = f.read(to_read)
                chunk_str = chunk + leftover
                lines_in_chunk = chunk_str.split(b"\n")
                
                if position > 0:
                    leftover = lines_in_chunk[0]
                    lines_in_chunk = lines_in_chunk[1:]
                else:
                    leftover = b""
                lines = lines_in_chunk + lines
                
        decoded_lines = [line.decode("utf-8", errors="ignore") + "\n" for line in lines[-n:]]
        return decoded_lines
    except Exception:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.readlines()[-n:]
        except Exception as ex:
            return [f"[red]Error reading logs: {ex}[/red]"]

def stream_logs(name):
    log_path = LOGS_DIR / f"{name}.log"
    clear_terminal()
    
    if not log_path.exists():
        LOGS_DIR.mkdir(exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"--- LOG INITIALIZED FOR {name.upper()} ---\n")
            
    # Initial placeholder panel
    panel = Panel(
        Text("Loading logs..."),
        title=f"{name.upper()} LOGS",
        title_align="left",
        border_style="magenta",
        subtitle="[q/ESC/Ctrl+C to exit]"
    )
    
    try:
        with Live(panel, console=console, screen=False, refresh_per_second=4) as live:
            while True:
                lines = get_last_n_lines(log_path, 30)
                # Strip CRLF duplicate newline issues
                lines_cleaned = [line.rstrip("\r\n") + "\n" for line in lines]
                log_text = "".join(lines_cleaned)
                
                try:
                    text_obj = Text.from_ansi(log_text)
                except Exception:
                    text_obj = Text(log_text)
                    
                live.update(Panel(
                    text_obj,
                    title=f"{name.upper()} LOGS",
                    title_align="left",
                    border_style="magenta",
                    subtitle="[q/ESC/Ctrl+C to exit]"
                ))
                
                if os.name == 'nt' and msvcrt:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key in (b'q', b'Q', b'\x1b', b'\x03'):
                            break
                else:
                    import select
                    if select.select([sys.stdin], [], [], 0)[0]:
                        key = sys.stdin.read(1)
                        if key in ('q', 'Q', '\x1b', '\x03'):
                            break
                time.sleep(0.25)
    except KeyboardInterrupt:
        pass

def read_key():
    if os.name == "nt" and msvcrt:
        try:
            ch = msvcrt.getch()
            if ch in (b"\x00", b"\xe0"):
                ch2 = msvcrt.getch()
                return f"special_{ch2.decode('utf-8', errors='ignore')}"
            try:
                return ch.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        except Exception:
            return ""
    else:
        try:
            import tty
            import termios
            import select
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        ch2 = sys.stdin.read(1)
                        if ch2 == "[":
                            ch3 = sys.stdin.read(1)
                            if ch3 == "A": return "special_H"
                            elif ch3 == "B": return "special_P"
                            elif ch3 == "5":
                                sys.stdin.read(1) # consume ~
                                return "special_I"
                            elif ch3 == "6":
                                sys.stdin.read(1) # consume ~
                                return "special_Q"
                            elif ch3 == "H": return "special_G"
                            elif ch3 == "F": return "special_O"
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            try:
                return sys.stdin.read(1)
            except Exception:
                return ""

def interactive_pager(log_text, title):
    import shutil
    lines = log_text.splitlines()
    if not lines:
        lines = ["No entries found."]
        
    size = shutil.get_terminal_size()
    visible_height = max(5, size.lines - 6)
    scroll_offset = max(0, len(lines) - visible_height)
    
    rendered_lines = []
    for line in lines:
        try:
            rendered_lines.append(Text.from_ansi(line))
        except Exception:
            rendered_lines.append(Text(line))
            
    try:
        with Live(screen=True, console=console, auto_refresh=False) as live:
            while True:
                size = shutil.get_terminal_size()
                visible_height = max(5, size.lines - 6)
                
                max_offset = max(0, len(rendered_lines) - visible_height)
                scroll_offset = min(max(0, scroll_offset), max_offset)
                
                visible_slice = rendered_lines[scroll_offset : scroll_offset + visible_height]
                
                page_text = Text()
                for i, text_line in enumerate(visible_slice):
                    page_text.append(text_line)
                    if i < len(visible_slice) - 1:
                        page_text.append("\n")
                        
                panel = Panel(
                    page_text,
                    title=f"[cyan bold]📄 {title}[/cyan bold]",
                    title_align="left",
                    subtitle=(
                        f"[yellow]Line {scroll_offset + 1} to {min(len(rendered_lines), scroll_offset + visible_height)} of {len(rendered_lines)}[/yellow] │ "
                        f"[dim]Up/Down/PgUp/PgDn/Home/End to scroll, Q/ESC to exit[/dim]"
                    ),
                    border_style="magenta"
                )
                
                live.update(panel)
                live.refresh()
                
                key = read_key()
                if key in ("q", "Q", "\x1b", "\x03"):
                    break
                elif key == "special_H": # Up Arrow
                    scroll_offset -= 1
                elif key == "special_P": # Down Arrow
                    scroll_offset += 1
                elif key == "special_I": # Page Up
                    scroll_offset -= visible_height
                elif key == "special_Q": # Page Down
                    scroll_offset += visible_height
                elif key == "special_G": # Home
                    scroll_offset = 0
                elif key == "special_O": # End
                    scroll_offset = max_offset
    except Exception as e:
        console.print(f"[bold red]Interactive pager error: {e}[/bold red]")
        time.sleep(2)

def open_in_pager(name):
    log_path = LOGS_DIR / f"{name}.log"
    if not log_path.exists():
        console.print(f"[yellow]Log file {log_path.name} does not exist yet.[/yellow]\n")
        questionary.press_any_key_to_continue().ask()
        return
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            log_text = f.read()
        interactive_pager(log_text, f"{name.upper()} LOGS")
    except Exception as e:
        console.print(f"[bold red]Failed to open pager: {e}[/bold red]\n")
        questionary.press_any_key_to_continue().ask()

# ─── WhatsApp Module ──────────────────────────────────────────────
def is_docker_running():
    try:
        # 1-second timeout prevents hanging if Docker Desktop is offline
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=1.0)
        return True
    except Exception:
        return False

def run_compose_cmd(args):
    try:
        subprocess.run(["docker", "compose"] + args, check=True, capture_output=True, timeout=5.0)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        try:
            subprocess.run(["docker-compose"] + args, check=True, capture_output=True, timeout=5.0)
            return True
        except Exception:
            return False

def is_openwa_running():
    try:
        res = subprocess.run(["docker", "ps", "--filter", "name=chronospet-openwa", "--format", "{{.Status}}"], capture_output=True, text=True, check=True, timeout=1.0)
        return "Up" in res.stdout
    except Exception:
        return False

def is_native_gateway_running():
    try:
        if os.name == "nt":
            # Quick check if node.exe is even running using tasklist (under 50ms)
            try:
                res_tl = subprocess.run(["tasklist", "/FI", "IMAGENAME eq node.exe"], capture_output=True, text=True, timeout=1.0)
                if "node.exe" not in res_tl.stdout:
                    return False
            except Exception:
                pass

            # wmic is extremely fast (under 100ms) compared to launching powershell.exe
            res = subprocess.run(
                ["wmic", "process", "where", "name='node.exe'", "get", "commandline"],
                capture_output=True, text=True, shell=True, timeout=1.0
            )
            if "index.js" in res.stdout:
                return True
            # Fallback in case wmic is disabled/missing
            res_ps = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-WmiObject Win32_Process -Filter \"name='node.exe'\" | Select-Object -ExpandProperty CommandLine"],
                capture_output=True, text=True, timeout=2.0
            )
            return "index.js" in res_ps.stdout
        else:
            res = subprocess.run(["pgrep", "-f", "node.*index.js"], capture_output=True, timeout=1.0)
            return res.returncode == 0
    except Exception:
        return False

def run_native_whatsapp(config):
    clear_terminal()
    print_banner()
    console.print("[bold yellow]🟢 Run WhatsApp Gateway Natively[/bold yellow]\n")

    gateway_path = Path("gateway")
    node_modules_path = gateway_path / "node_modules"

    if not node_modules_path.exists():
        console.print("[cyan]Installing Node.js dependencies for WhatsApp Gateway (first-time setup)...[/cyan]")
        try:
            subprocess.run(["npm", "install"], cwd=str(gateway_path), check=True, shell=True)
            console.print("[green]✔ Dependencies installed successfully![/green]\n")
        except Exception as e:
            console.print(f"[bold red]Failed to install dependencies: {e}[/bold red]")
            questionary.press_any_key_to_continue().ask()
            return

    console.print("[cyan]Starting WhatsApp client... (Press Ctrl+C to stop and return to menu)[/cyan]")
    console.print("[dim]Generating QR code in terminal... Scan it with your phone's WhatsApp Link Devices feature.[/dim]\n")

    # Sanitize environment dict: cast keys/values to strings and filter out any None values
    env = {str(k): str(v) for k, v in os.environ.items() if v is not None}
    env["AUTHORIZED_PHONE"] = str(config.get("authorized_phone_number") or "919876543210")
    env["BACKEND_WEBHOOK_URL"] = "http://localhost:8000/api/v1/webhook/ingest"
    env["LINK_ONLY"] = "true"

    try:
        # Spawn node index.js
        process = subprocess.Popen(
            ["node", "index.js"],
            cwd=str(gateway_path),
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr,
            shell=True
        )
        process.wait()
        if process.returncode == 0:
            console.print("\n[bold green]✔ WhatsApp Gateway successfully linked and saved![/bold green]")
        else:
            console.print(f"\n[bold red]❌ Linking process exited with code {process.returncode}[/bold red]")
        time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[cyan]Stopping WhatsApp Gateway...[/cyan]")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        console.print("[green]✔ Gateway stopped.[/green]")
        time.sleep(1.5)

def run_docker_whatsapp():
    if not is_docker_running():
        console.print("[bold red]❌ Docker is not running or not installed.[/bold red]")
        console.print("Please make sure Docker Desktop is started and running, then try again.\n")
        questionary.press_any_key_to_continue().ask()
        return

    running = is_openwa_running()
    status_str = "[green]Running[/green]" if running else "[red]Stopped[/red]"
    console.print(f"Current Container Status: {status_str}\n")

    actions = [
        "🟢 Start WhatsApp Gateway Container",
        "🛑 Stop WhatsApp Gateway Container",
        "📋 View Container Logs & Scan QR Code",
        "🔙 Back"
    ]

    choice = questionary.select(
        "Select an action:",
        choices=actions
    ).ask()

    if choice == actions[0]:
        console.print("[cyan]Spinning up OpenWA WhatsApp container via Docker Compose...[/cyan]")
        success = run_compose_cmd(["up", "-d", "openwa"])
        if success:
            console.print("[green]✔ Container started successfully![/green]")
            time.sleep(1)
            view_logs()
        else:
            console.print("[bold red]Failed to start container. Make sure docker-compose.yml exists and is valid.[/bold red]")
            questionary.press_any_key_to_continue().ask()

    elif choice == actions[1]:
        console.print("[cyan]Stopping OpenWA container...[/cyan]")
        success = run_compose_cmd(["stop", "openwa"])
        if success:
            console.print("[green]✔ Container stopped successfully.[/green]")
        else:
            console.print("[bold red]Failed to stop container.[/bold red]")
        time.sleep(1)

    elif choice == actions[2]:
        view_logs()

def handle_whatsapp():
    while True:
        clear_terminal()
        print_banner()
        console.print("[bold yellow]📱 WhatsApp Gateway Manager (OpenClaw-style)[/bold yellow]\n")

        config = load_config()
        
        # Determine status
        session_file = Path("gateway/session/chronospet.data.json")
        is_linked = session_file.exists()
        is_running = is_native_gateway_running()
        
        status_text = "[green]Linked & Active (Listening)[/green]" if (is_linked and is_running) else \
                      "[yellow]Linked (Offline)[/yellow]" if is_linked else \
                      "[red]Not Linked / Logged Out[/red]"
                      
        console.print(f"Current Connection Status: {status_text}")
        console.print(f"Authorized Phone Number:   [cyan]{config.get('authorized_phone_number') or 'Not Configured'}[/cyan]")
        console.print(f"Gateway URL / Port:        [cyan]{config.get('openwa_gateway_url', 'http://localhost:8080')}[/cyan]\n")

        choices = [
            "🔗 Link / Pair WhatsApp Device (Native Node.js)",
            "🔓 Unlink / Logout WhatsApp Session (Reset Connection)",
            "📞 Change Authorized Phone Number (Sender Filter)",
            "🔌 Configure Gateway Port",
            "🚀 Run System Diagnostics (Verify Endpoint & Docker)",
            "🔙 Back to Main Menu"
        ]

        choice = questionary.select(
            "Select an action:",
            choices=choices
        ).ask()

        if not choice or "Back to Main" in choice:
            break
            
        elif "Link / Pair" in choice:
            run_native_whatsapp(config)
            
        elif "Unlink / Logout" in choice:
            confirm = questionary.confirm(
                "Are you sure you want to unlink and logout your WhatsApp session? (This clears saved login data)",
                default=False
            ).ask()
            if confirm:
                session_dir = Path("gateway/session")
                persist_dir = Path("gateway/.node-persist")
                
                # Delete session folders
                import shutil
                if session_dir.exists():
                    shutil.rmtree(session_dir, ignore_errors=True)
                if persist_dir.exists():
                    shutil.rmtree(persist_dir, ignore_errors=True)
                
                # Also delete local config cache files if any
                config_json_path = Path("gateway/chronospet.data.json")
                if config_json_path.exists():
                    config_json_path.unlink(missing_ok=True)
                
                console.print("[green]✔ WhatsApp session unlinked successfully.[/green]")
                time.sleep(2)
                
        elif "Change Authorized" in choice:
            current_num = config.get("authorized_phone_number") or ""
            phone = questionary.text(
                "Enter authorized phone number (WhatsApp sender, with country code, e.g. 919876543210):",
                default=current_num
            ).ask()
            if phone:
                config["authorized_phone_number"] = phone.strip()
                save_config(config)
                console.print("[green]✔ Authorized phone number updated.[/green]")
                time.sleep(1.5)
                
        elif "Configure Gateway" in choice:
            current_url = config.get("openwa_gateway_url", "http://localhost:8080")
            current_port = "8080"
            if ":" in current_url:
                current_port = current_url.split(":")[-1].replace("/", "")
            
            port = questionary.text(
                "Enter local gateway port:",
                default=current_port
            ).ask()
            if port and port.isdigit():
                config["openwa_gateway_url"] = f"http://localhost:{port}"
                save_config(config)
                console.print(f"[green]✔ Gateway port updated to {port}.[/green]")
                time.sleep(1.5)
                
        elif "Run System Diagnostics" in choice:
            run_diagnostics()

# ─── LLM Routing Module ───────────────────────────────────────────
def handle_llm():
    clear_terminal()
    print_banner()
    console.print("[bold yellow]🧠 Configure LLM Routing & API Keys[/bold yellow]\n")

    config = load_config()
    current_prov = config.get("selected_provider", "gemini")
    
    provider = questionary.select(
        "Select your primary LLM provider:",
        choices=["gemini", "openrouter", "grok", "nvidia_nim", "ollama"],
        default=current_prov
    ).ask()

    if not provider:
        return

    env_key = PROVIDER_ENV_KEYS[provider]
    if env_key:
        current_key = get_env_var(env_key)
        masked_key = f"...{current_key[-6:]}" if len(current_key) > 6 else ""
        key_prompt = f"Enter API key for {provider.upper()} ({env_key}):"
        if masked_key:
            key_prompt += f" [Current: {masked_key}]"

        key_value = questionary.password(
            key_prompt
        ).ask()

        # Update key if user entered anything (otherwise keep old one)
        if key_value:
            set_env_var(env_key, key_value)
            console.print(f"[green]✔ API Key updated for {provider.upper()}.[/green]")
    else:
        console.print("[cyan]Ollama selected. No API key required for local models.[/cyan]")

    # Select target model name
    default_model = PROVIDER_DEFAULT_MODELS[provider]
    current_model = config.get("target_model_name") if config.get("selected_provider") == provider else default_model

    model_name = questionary.text(
        "Enter target model name:",
        default=current_model
    ).ask()

    # Update config.json
    config["selected_provider"] = provider
    config["target_model_name"] = model_name

    # Check if they want to adjust the fallback sequence
    fallbacks_choice = questionary.confirm(
        "Would you like to keep the default fallback sequence?",
        default=True
    ).ask()

    if not fallbacks_choice:
        fallbacks_str = questionary.text(
            "Enter comma-separated fallback models (e.g. gemini/gemini-1.5-flash,ollama/gemma2):",
            default=",".join(config.get("llm_fallback_models", []))
        ).ask()
        if fallbacks_str:
            config["llm_fallback_models"] = [f.strip() for f in fallbacks_str.split(",") if f.strip()]

    if save_config(config):
        console.print("[green]✔ Config updated and saved successfully![/green]\n")
    
    questionary.press_any_key_to_continue().ask()

# ─── Settings Editor ──────────────────────────────────────────────
def handle_settings():
    while True:
        clear_terminal()
        print_banner()
        console.print("[bold yellow]⚙️ Edit Application Settings[/bold yellow]\n")

        config = load_config()

        # Display current settings in a neat list
        console.print(f"1. Authorized Phone Number:     [cyan]{config.get('authorized_phone_number') or 'Not Configured'}[/cyan]")
        console.print(f"2. Companion Persona Profile:    [cyan]{config.get('active_persona_profile', 'cybernetic')}[/cyan]")
        console.print(f"3. Sentinel Polling Frequency:   [cyan]{config.get('polling_frequency_seconds', 30)} seconds[/cyan]")
        console.print(f"4. XP Awarded Per Task:          [cyan]{config.get('xp_per_task_completion', 50)} XP[/cyan]")
        console.print(f"5. Enable Vision AI (Local MiniCPM):[cyan]{'Yes' if config.get('vision_enabled', False) else 'No'}[/cyan]")
        console.print(f"6. Screen Analysis Min Interval: [cyan]{config.get('vision_min_interval_seconds', 30)} seconds[/cyan]")
        console.print(f"7. Gamification Progress:        [cyan]Level {config.get('gamification_level', 1)} (XP: {config.get('accumulated_experience', 0)})[/cyan]\n")

        choices = [
            "📞 Edit Authorized Phone Number",
            "🎭 Edit Companion Persona Profile",
            "⏱ Edit Sentinel Polling Frequency",
            "✨ Edit XP Per Task Completion",
            "📷 Toggle Vision AI (Local MiniCPM)",
            "⏱ Edit Screen Analysis Min Interval",
            "🎛 Reset Gamification Level & XP Progress",
            "🔙 Back to Main Menu"
        ]

        choice = questionary.select(
            "Select an option to edit:",
            choices=choices
        ).ask()

        if not choice or "Back to Main" in choice:
            break

        elif "Edit Authorized" in choice:
            current = config.get("authorized_phone_number") or ""
            phone = questionary.text(
                "Enter authorized phone number (WhatsApp sender, with country code, e.g. 919876543210):",
                default=current
            ).ask()
            if phone:
                config["authorized_phone_number"] = phone.strip()
                save_config(config)
                console.print("[green]✔ Phone number updated successfully![/green]")
                time.sleep(1.0)

        elif "Edit Companion Persona" in choice:
            current = config.get("active_persona_profile", "cybernetic")
            persona = questionary.select(
                "Select active pet companion persona profile:",
                choices=["cybernetic", "rival", "zen"],
                default=current
            ).ask()
            if persona:
                config["active_persona_profile"] = persona
                save_config(config)
                console.print("[green]✔ Persona profile updated successfully![/green]")
                time.sleep(1.0)

        elif "Edit Sentinel Polling" in choice:
            current = str(config.get("polling_frequency_seconds", 30))
            freq = questionary.text(
                "Enter Sentinel focus polling frequency (seconds):",
                default=current
            ).ask()
            if freq and freq.isdigit():
                config["polling_frequency_seconds"] = int(freq)
                save_config(config)
                console.print("[green]✔ Polling frequency updated successfully![/green]")
                time.sleep(1.0)
            else:
                console.print("[bold red]Error: Polling frequency must be a valid integer.[/bold red]")
                time.sleep(2.0)

        elif "Edit XP Per Task" in choice:
            current = str(config.get("xp_per_task_completion", 50))
            xp = questionary.text(
                "Enter XP awarded per completed task:",
                default=current
            ).ask()
            if xp and xp.isdigit():
                config["xp_per_task_completion"] = int(xp)
                save_config(config)
                console.print("[green]✔ XP reward updated successfully![/green]")
                time.sleep(1.0)
            else:
                console.print("[bold red]Error: XP value must be a valid integer.[/bold red]")
                time.sleep(2.0)

        elif "Toggle Vision AI" in choice:
            current = config.get("vision_enabled", False)
            vision = questionary.confirm(
                "Enable Vision AI (takes screenshots every poll cycle to analyze with local MiniCPM)?",
                default=current
            ).ask()
            config["vision_enabled"] = vision
            save_config(config)
            status_str = "enabled" if vision else "disabled"
            console.print(f"[green]✔ Vision AI {status_str} successfully![/green]")
            time.sleep(1.0)

        elif "Edit Screen Analysis Min Interval" in choice or "Edit Vision AI Min Interval" in choice:
            current = str(config.get("vision_min_interval_seconds", 30))
            interval = questionary.text(
                "Enter minimum seconds between screen scans (safety valve):",
                default=current
            ).ask()
            if interval and interval.isdigit():
                config["vision_min_interval_seconds"] = int(interval)
                save_config(config)
                console.print("[green]✔ Screen analysis min interval updated successfully![/green]")
                time.sleep(1.0)
            else:
                console.print("[bold red]Error: Min interval must be a valid integer.[/bold red]")
                time.sleep(2.0)

        elif "Reset Gamification" in choice:
            confirm = questionary.confirm(
                "Are you sure you want to reset all Level and XP progress? (This cannot be undone)",
                default=False
            ).ask()
            if confirm:
                config["gamification_level"] = 1
                config["accumulated_experience"] = 0
                save_config(config)
                console.print("[green]✔ Gamification level and XP reset successfully.[/green]")
                time.sleep(1.5)


# ─── Diagnostic Checks ────────────────────────────────────────────
def run_diagnostics():
    clear_terminal()
    print_banner()
    console.print("[bold yellow]🚀 System Health Diagnostics[/bold yellow]\n")

    table = Table(title="Diagnostic Status Matrix")
    table.add_column("Component", style="cyan")
    table.add_column("Details", style="magenta")
    table.add_column("Status", style="bold")

    # 1. config.json
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                json.load(f)
            table.add_row("config.json", "Valid JSON structure", "[green]OK[/green]")
        except Exception:
            table.add_row("config.json", "Corrupted config.json", "[red]ERROR[/red]")
    else:
        table.add_row("config.json", "File missing", "[yellow]WARNING (Created defaults)[/yellow]")
        load_config()

    # 2. Env Keys
    config = load_config()
    prov = config.get("selected_provider", "gemini")
    env_key = PROVIDER_ENV_KEYS[prov]
    if env_key:
        key_val = get_env_var(env_key)
        if key_val:
            table.add_row("API Key (.env)", f"Found key for {prov.upper()}", "[green]OK[/green]")
        else:
            table.add_row("API Key (.env)", f"Missing key for {prov.upper()}", "[red]MISSING[/red]")
    else:
        table.add_row("API Key (.env)", f"No key required for {prov.upper()}", "[green]OK[/green]")

    # 3. Docker status
    if is_docker_running():
        status_text = "Docker is active"
        if is_openwa_running():
            status_text += " (OpenWA container UP)"
        table.add_row("Docker Engine", status_text, "[green]OK[/green]")
    else:
        table.add_row("Docker Engine", "Docker Desktop not running", "[yellow]OFFLINE[/yellow]")

    # 4. Backend Server Status (FastAPI port 8000)
    try:
        res = httpx.get("http://localhost:8000/health", timeout=1.5)
        if res.status_code == 200:
            data = res.json()
            table.add_row("FastAPI Backend", f"Active (Version {data.get('version', 'unknown')})", "[green]OK[/green]")
        else:
            table.add_row("FastAPI Backend", f"Responded with status {res.status_code}", "[yellow]UNEXPECTED[/yellow]")
    except httpx.RequestError:
        table.add_row("FastAPI Backend", "Service offline (Not listening on port 8000)", "[yellow]OFFLINE[/yellow]")

    # 5. WhatsApp Gateway Status (Docker or Native Process)
    is_docker_wa = is_openwa_running()
    is_native_wa = is_native_gateway_running()
    
    if is_docker_wa:
        table.add_row("WhatsApp Gateway", "Running (Docker Container)", "[green]OK[/green]")
    elif is_native_wa:
        table.add_row("WhatsApp Gateway", "Running (Native Node.js)", "[green]OK[/green]")
    else:
        table.add_row("WhatsApp Gateway", "Offline", "[yellow]OFFLINE[/yellow]")

    console.print(table)
    console.print("\n")
    questionary.press_any_key_to_continue().ask()

def get_service_definitions():
    config = load_config()
    
    backend_venv_path = Path("backend") / "venv" / "Scripts" / "python.exe"
    if backend_venv_path.exists():
        backend_cmd = [str(backend_venv_path), "-u", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"]
    else:
        backend_venv_path_unix = Path("backend") / "venv" / "bin" / "python"
        if backend_venv_path_unix.exists():
            backend_cmd = [str(backend_venv_path_unix), "-u", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"]
        else:
            backend_cmd = ["python", "-u", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"]
            
    gateway_env = {
        "AUTHORIZED_PHONE": str(config.get("authorized_phone_number") or "919876543210"),
        "BACKEND_WEBHOOK_URL": "http://localhost:8000/api/v1/webhook/ingest",
        "LINK_ONLY": "false"
    }
    gateway_cmd = ["node", "index.js"]
    tauri_cmd = "npm run tauri dev"
    
    return {
        "backend": {
            "display_name": "FastAPI Backend",
            "cmd": backend_cmd,
            "cwd": Path("backend"),
            "env": None,
            "url": "http://localhost:8000"
        },
        "gateway": {
            "display_name": "WhatsApp Gateway",
            "cmd": gateway_cmd,
            "cwd": Path("gateway"),
            "env": gateway_env,
            "url": "http://localhost:8080"
        },
        "tauri": {
            "display_name": "Tauri Pet Companion",
            "cmd": tauri_cmd,
            "cwd": Path("."),
            "env": None,
            "url": "http://localhost:1420"
        }
    }

def handle_process_control():
    while True:
        clear_terminal()
        print_banner()
        console.print("[bold yellow]🖥️ Universal Process Control Panel[/bold yellow]\n")
        
        services = get_service_definitions()
        state = get_active_processes()
        
        table = Table(title="Background Services Status")
        table.add_column("Service Name", style="cyan")
        table.add_column("PID", style="magenta")
        table.add_column("Uptime", style="green")
        table.add_column("Endpoint", style="blue")
        table.add_column("Status", style="bold")
        
        updated_state = {}
        for key, srv in services.items():
            is_running = False
            pid_str = "N/A"
            uptime_str = "N/A"
            
            if key in state:
                pid = state[key]["pid"]
                if is_pid_running(pid):
                    is_running = True
                    pid_str = str(pid)
                    start_time = state[key].get("start_time", time.time())
                    uptime_sec = int(time.time() - start_time)
                    if uptime_sec < 60:
                        uptime_str = f"{uptime_sec}s"
                    elif uptime_sec < 3600:
                        uptime_str = f"{uptime_sec // 60}m {uptime_sec % 60}s"
                    else:
                        uptime_str = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m"
                    updated_state[key] = state[key]
                    
            status_text = "[green]RUNNING[/green]" if is_running else "[red]OFFLINE[/red]"
            table.add_row(
                srv["display_name"],
                pid_str,
                uptime_str,
                srv["url"],
                status_text
            )
            
        save_active_processes(updated_state)
        console.print(table)
        console.print("\n")
        
        choices = []
        for key, srv in services.items():
            is_running = key in updated_state
            action = "🛑 Stop" if is_running else "🚀 Start"
            choices.append(f"{action} {srv['display_name']}")
            
        choices.append("📋 View Service Logs")
        choices.append("🧹 Stop All Services")
        choices.append("🔙 Back to Main Menu")
        
        choice = questionary.select(
            "Select action:",
            choices=choices
        ).ask()
        
        if not choice or "Back to Main Menu" in choice:
            break
            
        elif "Stop All Services" in choice:
            console.print("[cyan]Stopping all services...[/cyan]")
            for key in list(updated_state.keys()):
                stop_service(key)
            console.print("[green]✔ All processes terminated.[/green]")
            time.sleep(1.5)
            
        elif "View Service Logs" in choice:
            log_choices = [f"📄 {srv['display_name']} Logs" for srv in services.values()]
            log_choices.append("🔙 Back")
            
            log_choice = questionary.select(
                "Select log stream to view:",
                choices=log_choices
            ).ask()
            
            if log_choice and "Back" not in log_choice:
                selected_key = None
                for key, srv in services.items():
                    if srv['display_name'] in log_choice:
                        selected_key = key
                        break
                if selected_key:
                    view_mode = questionary.select(
                        "Select viewing mode:",
                        choices=[
                            "📡 Stream in Real-Time (Live View)",
                            "📄 Open in Scrollable Pager (Interactive Scroll & Search)",
                            "🔙 Back"
                        ]
                    ).ask()
                    
                    if view_mode == "📡 Stream in Real-Time (Live View)":
                        stream_logs(selected_key)
                    elif view_mode == "📄 Open in Scrollable Pager (Interactive Scroll & Search)":
                        open_in_pager(selected_key)
                    
        else:
            selected_key = None
            is_start = "Start" in choice
            
            for key, srv in services.items():
                if srv['display_name'] in choice:
                    selected_key = key
                    break
                    
            if selected_key:
                srv = services[selected_key]
                if is_start:
                    console.print(f"[cyan]Starting {srv['display_name']}...[/cyan]")
                    if start_service(selected_key, srv["cmd"], srv["cwd"], srv["env"]):
                        console.print(f"[green]✔ Started {srv['display_name']} successfully![/green]")
                    time.sleep(1.5)
                else:
                    console.print(f"[cyan]Stopping {srv['display_name']}...[/cyan]")
                    if stop_service(selected_key):
                        console.print(f"[green]✔ Stopped {srv['display_name']}.[/green]")
                    else:
                        console.print(f"[yellow]Could not stop {srv['display_name']} cleanly (or already stopped).[/yellow]")
                    time.sleep(1.5)

def check_exit_cleanup():
    state = get_active_processes()
    running_keys = []
    for key, info in state.items():
        if is_pid_running(info["pid"]):
            running_keys.append(key)
            
    if running_keys:
        clear_terminal()
        print_banner()
        console.print("[bold yellow]⚠️ Active Background Processes Detected[/bold yellow]\n")
        for key in running_keys:
            srv_name = key
            definitions = get_service_definitions()
            if key in definitions:
                srv_name = definitions[key]["display_name"]
            console.print(f" - {srv_name} (PID: {state[key]['pid']})")
        console.print("\n")
        
        confirm = questionary.confirm(
            "Would you like to stop all running background processes before exiting?",
            default=True
        ).ask()
        
        if confirm:
            console.print("[cyan]Terminating services...[/cyan]")
            for key in running_keys:
                stop_service(key)
            console.print("[green]✔ Cleaned up processes.[/green]")
            time.sleep(1.5)
        else:
            console.print("[cyan]Processes left running in the background. Enjoy focusing! 🤖[/cyan]")
            time.sleep(2.0)

def handle_chromadb_view():
    clear_terminal()
    print_banner()
    console.print("[bold yellow]📦 ChromaDB Task Store Explorer[/bold yellow]\n")
    
    try:
        import chromadb
    except ImportError:
        console.print("[bold red]Error: chromadb package is not installed in the current environment.[/bold red]")
        console.print("Please install it or run setup_tui.py with the backend virtualenv.\n")
        questionary.press_any_key_to_continue().ask()
        return
        
    try:
        from datetime import datetime
        client = chromadb.PersistentClient(path="backend/chroma_data")
        collections = client.list_collections()
        col_names = [c.name for c in collections]
        if "chronospet_tasks" not in col_names:
            console.print("[yellow]ChromaDB collection 'chronospet_tasks' does not exist yet.[/yellow]")
            console.print("This collection will be created once the first task is successfully parsed and stored.\n")
            questionary.press_any_key_to_continue().ask()
            return
            
        collection = client.get_collection("chronospet_tasks")
        results = collection.get()
        
        ids = results.get("ids", [])
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        
        if not ids:
            console.print("[yellow]ChromaDB is active but contains no task vectors yet.[/yellow]")
            console.print("Try sending a task description (e.g. 'finish math homework by 5pm') via your linked WhatsApp device!\n")
            questionary.press_any_key_to_continue().ask()
            return
            
        table = Table(title=f"Vector Tasks Database ({len(ids)} items stored)")
        table.add_column("Task ID (Short)", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Raw WhatsApp Message", style="magenta")
        table.add_column("Priority", style="bold")
        table.add_column("Deadline", style="yellow")
        
        for idx in range(len(ids)):
            task_id = ids[idx]
            doc = documents[idx]
            meta = metadatas[idx] or {}
            
            short_id = task_id[:8] if len(task_id) > 8 else task_id
            title = meta.get("clean_title", "Untitled")
            priority = str(meta.get("priority", "medium")).upper()
            
            deadline_val = meta.get("deadline", 0)
            try:
                deadline_dt = datetime.fromtimestamp(float(deadline_val)).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                deadline_dt = "N/A"
                
            table.add_row(
                short_id,
                title,
                doc,
                priority,
                deadline_dt
            )
            
        with console.capture() as capture:
            console.print(table)
        table_str = capture.get()
        
        interactive_pager(table_str, f"ChromaDB Tasks Database ({len(ids)} items)")
        
        choices = [
            "🧹 Clear All Task Vectors from ChromaDB",
            "🔙 Back to Main Menu"
        ]
        action = questionary.select("Select action:", choices=choices).ask()
        if action == "🧹 Clear All Task Vectors from ChromaDB":
            confirm = questionary.confirm("Are you sure you want to permanently delete all task vectors?", default=False).ask()
            if confirm:
                collection.delete(ids=ids)
                console.print("[green]✔ ChromaDB task store cleared successfully![/green]\n")
                time.sleep(1.5)
                
    except Exception as e:
        console.print(f"[bold red]Failed to query ChromaDB: {e}[/bold red]")
        console.print("Make sure the backend is not locking the database file, or that the path 'backend/chroma_data' is correct.\n")
        questionary.press_any_key_to_continue().ask()

def handle_activity_view():
    clear_terminal()
    print_banner()
    console.print("[bold yellow]🔍 Ambient Activity Monitor[/bold yellow]\n")
    console.print(
        "The activity log shows [bold green]what app/website you're on[/bold green], "
        "interpreted in real-time against your active task.\n"
    )

    # Force an immediate sentinel poll so fresh data appears even if the 30s interval hasn't fired
    try:
        import requests as req
        r = req.post("http://localhost:8000/api/v1/debug/sentinel-poll", timeout=3)
        if r.status_code == 200:
            data = r.json()
            window = data.get("window", "?")
            task_active = data.get("active_task") or "None (Idle)"
            console.print(f"[bold cyan]📡 Immediate poll done[/bold cyan] │ Window: [yellow]{window}[/yellow] │ Task: [green]{task_active}[/green]\n")
        else:
            console.print(f"[yellow]Could not poll backend (status {r.status_code}). Is backend running?[/yellow]\n")
    except Exception as e:
        console.print(f"[yellow]Could not reach backend for instant poll: {e}[/yellow]\n")

    activity_log = LOGS_DIR / "activity.log"

    choice = questionary.select(
        "How do you want to view activity?",
        choices=[
            "📡 Live Stream (real-time, auto-refresh every 250ms)",
            "📜 Full History (scrollable pager)",
            "⬅️  Back",
        ]
    ).ask()

    if not choice or "Back" in choice:
        return

    if "Live Stream" in choice:
        stream_logs("activity")
    elif "Full History" in choice:
        if not activity_log.exists():
            console.print("[yellow]No ambient activity has been logged yet.[/yellow]")
            console.print("Make sure the backend service is started and you have an active task!\n")
            questionary.press_any_key_to_continue().ask()
            return
        try:
            with open(activity_log, "r", encoding="utf-8", errors="ignore") as f:
                log_text = f.read()
            interactive_pager(log_text, "AMBIENT ACTIVITY LOGS")
        except Exception as e:
            console.print(f"[bold red]Failed to read activity log: {e}[/bold red]\n")
            questionary.press_any_key_to_continue().ask()

# ─── Main Program ─────────────────────────────────────────────────
def main():
    while True:
        clear_terminal()
        print_banner()
        
        choice = questionary.select(
            "Select setup category:",
            choices=[
                "🖥️ Universal Process Control Panel",
                "📦 View ChromaDB Task Store",
                "🔍 View Ambient Activity Logs",
                "📱 Link WhatsApp Gateway",
                "🧠 Configure LLM Routing & API Keys",
                "⚙️ Edit App Settings (Persona, Phone, Polling)",
                "🚀 Run System Health Diagnostics",
                "🚪 Exit Setup"
            ]
        ).ask()

        if not choice or "Exit Setup" in choice:
            check_exit_cleanup()
            console.print("[cyan]Setup wizard exited. Happy focusing! 🤖[/cyan]")
            break
        elif "Process Control" in choice:
            handle_process_control()
        elif "View ChromaDB" in choice:
            handle_chromadb_view()
        elif "View Ambient Activity" in choice:
            handle_activity_view()
        elif "Link WhatsApp" in choice:
            handle_whatsapp()
        elif "Configure LLM" in choice:
            handle_llm()
        elif "Edit App Settings" in choice:
            handle_settings()
        elif "System Health" in choice:
            run_diagnostics()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        check_exit_cleanup()
        console.print("\n[cyan]Wizard aborted. Bye![/cyan]")
