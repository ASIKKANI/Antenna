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

# ─── WhatsApp Module ──────────────────────────────────────────────
def is_docker_running():
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True)
        return True
    except Exception:
        return False

def run_compose_cmd(args):
    # Try 'docker compose' first, fallback to 'docker-compose'
    try:
        subprocess.run(["docker", "compose"] + args, check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run(["docker-compose"] + args, check=True, capture_output=True)
            return True
        except Exception:
            return False

def is_openwa_running():
    try:
        res = subprocess.run(["docker", "ps", "--filter", "name=chronospet-openwa", "--format", "{{.Status}}"], capture_output=True, text=True, check=True)
        return "Up" in res.stdout
    except Exception:
        return False

def handle_whatsapp():
    clear_terminal()
    print_banner()
    console.print("[bold yellow]📱 WhatsApp Gateway Connector[/bold yellow]\n")

    if not is_docker_running():
        console.print("[bold red]❌ Docker is not running or not installed.[/bold red]")
        console.print("Please make sure Docker Desktop is started and running, then try again.\n")
        questionary.press_any_key_to_continue().ask()
        return

    running = is_openwa_running()
    status_str = "[green]Running[/green]" if running else "[red]Stopped[/red]"
    console.print(f"Current Gateway Status: {status_str}\n")

    actions = [
        "🟢 Start WhatsApp Gateway",
        "🛑 Stop WhatsApp Gateway",
        "📋 View Logs & Scan QR Code",
        "🔙 Back to Main Menu"
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
            # Auto go to logs to scan QR code
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

def view_logs():
    clear_terminal()
    print_banner()
    console.print("[bold green]📋 Streaming Logs (Press Ctrl+C to return to menu)[/bold green]")
    console.print("[dim]Waiting for QR code or connection confirmation...[/dim]\n")
    
    cmd = ["docker", "compose", "logs", "-f", "openwa"]
    try:
        subprocess.run(cmd)
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run(["docker-compose", "logs", "-f", "openwa"])
        except KeyboardInterrupt:
            pass
        except Exception as e:
            console.print(f"[bold red]Error launching logs: {e}[/bold red]")
            questionary.press_any_key_to_continue().ask()
    except KeyboardInterrupt:
        pass

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
    clear_terminal()
    print_banner()
    console.print("[bold yellow]⚙️ Edit Application Settings[/bold yellow]\n")

    config = load_config()

    phone = questionary.text(
        "Authorized phone number (WhatsApp sender, with country code):",
        default=config.get("authorized_phone_number", "919876543210")
    ).ask()

    persona = questionary.select(
        "Active pet companion persona profile:",
        choices=["cybernetic", "rival", "zen"],
        default=config.get("active_persona_profile", "cybernetic")
    ).ask()

    frequency = questionary.text(
        "Sentinel focus polling frequency (seconds):",
        default=str(config.get("polling_frequency_seconds", 30))
    ).ask()

    xp_completion = questionary.text(
        "XP awarded per completed task:",
        default=str(config.get("xp_per_task_completion", 50))
    ).ask()

    try:
        config["authorized_phone_number"] = phone
        config["active_persona_profile"] = persona
        config["polling_frequency_seconds"] = int(frequency)
        config["xp_per_task_completion"] = int(xp_completion)
        
        if save_config(config):
            console.print("[green]✔ Settings updated successfully![/green]\n")
    except ValueError:
        console.print("[bold red]Error: Polling frequency and XP must be integers. Settings not saved.[/bold red]\n")

    questionary.press_any_key_to_continue().ask()

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

    # 5. WhatsApp Gateway Server Status (port 8080)
    try:
        res = httpx.get("http://localhost:8080/", timeout=1.5)
        table.add_row("WhatsApp Gateway", f"Active (Reachable)", "[green]OK[/green]")
    except httpx.RequestError:
        table.add_row("WhatsApp Gateway", "Gateway offline (Port 8080 unreachable)", "[yellow]OFFLINE[/yellow]")

    console.print(table)
    console.print("\n")
    questionary.press_any_key_to_continue().ask()

# ─── Main Program ─────────────────────────────────────────────────
def main():
    while True:
        clear_terminal()
        print_banner()
        
        choice = questionary.select(
            "Select setup category:",
            choices=[
                "📱 Link WhatsApp Gateway",
                "🧠 Configure LLM Routing & API Keys",
                "⚙️ Edit App Settings (Persona, Phone, Polling)",
                "🚀 Run System Health Diagnostics",
                "🚪 Exit Setup"
            ]
        ).ask()

        if not choice or "Exit Setup" in choice:
            console.print("[cyan]Setup wizard exited. Happy focusing! 🤖[/cyan]")
            break
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
        console.print("\n[cyan]Wizard aborted. Bye![/cyan]")
