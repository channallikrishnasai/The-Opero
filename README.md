# <div align="center">

**📧** [channallikrishnasai@gmail.com](mailto:channallikrishnasai%40gmail.com) &nbsp;&nbsp;|&nbsp;&nbsp; **🔗** [LinkedIn](https://www.linkedin.com/in/krishna-sai-channalli-4528262b3)

```text
 ██████╗ ██████╗ ███████╗██████╗  ██████╗
██╔═══██╗██╔══██╗██╔════╝██╔══██╗██╔═══██╗
██║   ██║██████╔╝█████╗  ██████╔╝██║   ██║
██║   ██║██╔═══╝ ██╔══╝  ██╔══██╗██║   ██║
╚██████╔╝██║     ███████╗██║  ██║╚██████╔╝
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═╝ ╚═════╝
```

<img src="assets/hero.svg" alt="OPERO Animated Hero" width="100%">

**Open Personal Execution & Response Operator**
*Your desktop. Your AI. Fully autonomous.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-GUI-41cd52?style=for-the-badge&logo=qt&logoColor=white)](https://pypi.org/project/PyQt6/)
[![Gemini](https://img.shields.io/badge/Gemini-AI%20Brain-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![License: MIT](https://img.shields.io/badge/License-MIT-00d4ff?style=for-the-badge)](LICENSE)

[🚀 Quick Start](#-quick-start) · [🤖 Automations](#-autonomous-modules--capabilities) · [🔀 Architecture](#-architecture--pipeline) · [🔧 Setup](#-setup--configuration) · [🤝 Connect](#-connect)

</div>

---

## 🌟 What is OPERO?

**OPERO** is a multi‑modal, local‑first living AI assistant and dynamic desktop operating system powered by **Google Gemini**. It sees your screen, hears your voice, understands your intent, and executes real actions on your computer autonomously.

Unlike traditional chatbots, OPERO is an **action engine** – it **does** the work for you.

---

## 🔀 Architecture & Pipeline

### Core Flow (Mermaid)
```mermaid
sequenceDiagram
    participant User as User
    participant Input as Input Layer (Mic/Screen)
    participant Brain as Gemini AI Brain
    participant Dispatch as Action Dispatcher
    participant Module as Action Module (50+)
    participant UI as UI & TTS Output
    
    User->>Input: "Hey Opero, email John the Q3 report"
    Input->>Brain: Context + Audio Transcript + Screen Capture
    Note over Brain: Understand intent, extract entities
    Brain->>Dispatch: Function Call: gmail_send(to="John", subject="Q3")
    Dispatch->>Module: Route to actions/gmail.py
    Module-->>Dispatch: Execution Result (Success ID)
    Dispatch-->>Brain: Return Context
    Brain->>UI: "I've sent the Q3 report to John."
    UI-->>User: (Spoken Audio + HUD Update)
```

### System Layer Diagram (SVG)
<div align="center">
  <img src="assets/pipeline.svg" alt="OPERO Pipeline Flowchart" width="100%">
</div>

---

## 🤖 Autonomous Modules & Capabilities

OPERO ships with **50+ Action Modules**. Click any category to explore the automations.

<details>
<summary><b>🛡️ 1️⃣ Self‑Heal Engine</b></summary>

Detects runtime errors, generates Gemini patches, validates with an AST sandbox, and auto‑rolls back if needed.

```mermaid
graph TD
    A[Runtime Traceback] -->|Captured| B(Traceback Analyzer)
    B --> C{Core Protected File?}
    C -->|Yes| D[Abort: Cannot patch core]
    C -->|No| E[Gemini: Synthesize Patch]
    E --> F(Safety Sandbox: AST Validation)
    F --> G{Syntax Valid?}
    G -->|No| H[Abort: Rejected by Sandbox]
    G -->|Yes| I[Create Atomic Backup]
    I --> J[Apply Patch to Disk]
    J --> K(py_compile check)
    K -->|Fail| L[Auto‑Rollback]
    K -->|Pass| M((Patch Successful))
```
</details>

<details>
<summary><b>📧 2️⃣ Gmail Automation</b></summary>

Fully integrated OAuth2/App‑Passcode email engine.
- **Read & Search** – "Find the email from my boss about the Q3 report."
- **Draft & Send** – "Reply saying I will have it done by 5 PM."
- **Summarize** – "Summarize my unread emails today."
</details>

<details>
<summary><b>🌐 3️⃣ Live Web Research</b></summary>

DuckDuckGo + Gemini powered instant research.
- **Compare** – "Compare iPhone 15 vs Galaxy S24."
- **News** – "Top tech headlines today."
- **Scrape** – Structured data extraction from live pages.
</details>

<details>
<summary><b>📝 4️⃣ Document & Media Generation</b></summary>

Create rich files locally.
- **Word (.docx)** – Project proposals.
- **PowerPoint (.pptx)** – AI‑generated decks.
- **PDF** – Formatted reports.
- **HTML/CSS** – Landing pages.
</details>

<details>
<summary><b>🎵 5️⃣ Spotify Voice Control</b></summary>

Hands‑free music management via the Spotify Web API.
- Play, pause, skip, add to playlist.
</details>

<details>
<summary><b>💻 6️⃣ Full Desktop & File System Control</b></summary>

Orchestrate your PC with PyAutoGUI and OS utilities.
- Move/rename files, UI clicks, system monitoring.
</details>

<details>
<summary><b>🔍 7️⃣ Stanford MOSS Plagiarism Detection</b></summary>

Upload source code to MOSS, receive similarity matrix & web report URL.
</details>

---

## 📊 Feature Matrix

| **Module Category** | **Example Files** | **Inputs** | **Outputs** |
|---------------------|-------------------|------------|-------------|
| System Control      | `computer_control.py`, `system_manager.py` | Voice, Text | Mouse/Keyboard events, Settings changes |
| Media & Audio       | `spotify_controller.py`, `youtube_video.py` | Voice | Audio playback, Spotify API triggers |
| File Processing     | `file_controller.py`, `file_processor.py` | File paths, NL description | Moved/renamed files, OCR text, extracted data |
| Document Generation | `docx_tools.py`, `ppt_builder.py`, `pdf_tools.py` | Topic, content guidelines | `.docx`, `.pptx`, `.pdf` |
| Web & Research      | `web_search.py`, `browser_control.py` | Search queries, URLs | JSON summaries, Markdown reports |
| Communication       | `gmail.py`, `instagram_mcp.py` | Credentials, draft content | Sent emails, Direct messages |
| Self‑Healing        | `auto_heal_engine.py`, `recovery.py` | Tracebacks, exceptions | AST‑validated `.py` patches |

---

## 🚀 Quick Start

### 1️⃣ Prerequisites
- **Python 3.10+** (Windows 10/11 recommended)
- **Microphone & Speakers**
- **Google Gemini API Key** – obtain from the [Gemini AI Studio](https://deepmind.google/technologies/gemini/).

### 2️⃣ Installation
```bash
# Clone the repo
git clone https://github.com/channallikrishnasai/The-Opero.git
cd The-Opero

# (Optional) create a virtual env
python -m venv venv && .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3️⃣ Configuration
Place your secret keys in `config/api_keys.json`:
```json
{
  "gemini": "YOUR_GEMINI_API_KEY",
  "gmail": {
    "client_id": "...",
    "client_secret": "...",
    "refresh_token": "..."
  },
  "spotify": {
    "client_id": "...",
    "client_secret": "..."
  }
}
```
> **Tip:** The UI includes a Settings overlay where you can paste the Gemini key directly.

### 4️⃣ Run OPERO
```bash
python main.py
```
The desktop HUD will appear, embedding the interactive **`site/index.html`** dashboard.

---

## 🔧 Verification & Testing
| **Subsystem** | **Command** | **Expected Result** |
|---------------|-------------|---------------------|
| Core Boot | `python -c "import main; print('OK')"` | No import errors |
| Action Loader | `python -c "from core.action_loader import discover_actions; discover_actions(None)"` | 50+ actions discovered |
| Gmail OAuth | `python -c "from actions.gmail import execute; print(execute({'action':'status'}))"` | Shows active token status |
| Self‑Heal Demo | `python demo/demo_selfheal.py` | Runs 3 auto‑repair cycles |
| UI Load | Open `http://localhost:8000/site/` (or run `main.py`) | 3D galaxy background, interactive cards |

---

## 🖼️ UI Highlights (Live Demo)
<div align="center">
  <img src="assets/hero.svg" alt="Animated Hero" width="48%" style="margin:4px"/>
  <img src="assets/pipeline.svg" alt="Pipeline Flow" width="48%" style="margin:4px"/>
</div>

- **Full‑screen 3D galaxy** built with Three.js – stars, nebulae, floating geometry.
- **Custom neon cursor** with interactive halo.
- **Feature cards** tilt on mouse hover (desktop) and pop‑out on tap (mobile).
- **Scroll progress bar** at the top.
- **Mini‑mode (F10)** – shrinks HUD to a floating avatar that stays on top.
- **Live HUD** updates via Gemini responses (voice & text).

---

## 🤝 Connect & Contribute
<div align="center">

**Built by [Krishna Sai Channalli](https://www.linkedin.com/in/krishna-sai-channalli-4528262b3)**

[![GitHub ★](https://img.shields.io/badge/⭐_Star_on_GitHub-181717?style=for-the-badge&logo=github)](https://github.com/channallikrishnasai/The-Opero)
[![LinkedIn](https://img.shields.io/badge/Connect_on_LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/krishna-sai-channalli-4528262b3)
[![Issues](https://img.shields.io/badge/Report_a_Bug-ff3355?style=for-the-badge&logo=github)](https://github.com/channallikrishnasai/The-Opero/issues)

</div>

- 🐛 **Found a bug?** Open an issue.
- 💡 **Feature request?** Start a discussion.
- 🤝 **Pull requests** are warmly welcome – see `CONTRIBUTING.md` for guidelines.

---

<div align="center">

Made with ❤️ in India 🇮🇳

**[⭐ Star this repo](https://github.com/channallikrishnasai/The-Opero) if OPERO made your day easier!**

</div>
