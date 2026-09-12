# Technical Status Update


## Yuko Workspace & Environment Setup For Windows 
<!--
 /\_/\   /\_/\   /\_/\
( o.o ) ( =.= ) ( ^.^ )
 > ^ <   > ^ <   > ^ <
-->

Welcome to the **Yuko Workspace**! This repository provides a fully automated, declarative provisioning pipeline for both native Windows host environments and containerized/WSL NixOS setups. Whether you are running tiling window managers on Windows or hacking inside WSL, everything is configured for maximum keyboard ergonomics and speed!

---

### Integration Log & Recent Changes
* In the windows directory ...
* **`YukoWindows.exe`**: Launch the core Windows desktop stack! Provisions and starts GlazeWM (tiling window manager), Zebar status bar, Tailscale network node, WinDirStat, and Firefox using Chocolatey.
* **`RunYukoDeploy.exe`**: Orchestrates the main WSL environment—bootstrapping the NixOS container environment and syncing home profile modules seamlessly. To be run if you want the WSL nixos virtual machine alone without additional Window's gui applications
* **WSL Tmux Local Services Integration**: Automated background startup script that initializes local developer services inside your terminal environment upon session start:
* **LocalAI API**: Ready and active at `http://localhost:8081`
* **SearXNG Metasearch Engine**: Ready and active at `http://localhost:8888`

---

### Surfingkeys for Firefox

[Surfingkeys](https://github.com/brookhong/Surfingkeys) is a modal keyboard navigation extension that brings pure Vim-like navigation to Firefox! With custom JavaScript configurations, you can navigate without touching the mouse, trigger customized link hints, and interface directly with local media tools.

#### Key Mappings Cheat Sheet

* **`?`**: Trigger visual hints.

---

### How to Load `surfingkeys.js` into Firefox

Linking your declarative `modules/programs/firefox/surfingkeys.js` configuration to Firefox takes just a few seconds:

1. **Open Extension Options** *(10s)*: Open Firefox, press `Ctrl + Shift + A` to open **Add-ons and Themes**, and ensure **Surfingkeys** is installed. Type `;e` in any active tab or click the extension icon to open the settings panel.
2. **Import Your Configuration** *(15s)*: Copy the complete contents of `modules/programs/firefox/surfingkeys.js` from your local repo and paste it into the main code editor in the Surfingkeys settings page.
3. **Save and Apply** *(5s)*: Click **Save** at the bottom right of the page. Your custom *Cyber Rosé Pine* theme and custom keybindings will take effect across all browser tabs immediately!


## Filters at with function keys to MPV and Synth Overview added to vincinae with pagination Alt+h and Alt+l `(=^･ω･^=)`
Shifted system dashboard orchestration from raw `tmux` imperative script loops to declarative Zellij layout topologies (`modules/shell/zellij/default.nix`) alongside expanded audio graph tools and keyboard filter controls.

- **Declarative KDL Architecture:** Built structured layout templates (`overview.kdl`) specifying exact pane geometry, process execution paths, and top-level vertical/horizontal split ratios.
- **Dynamic Swap Layouts:** Implemented native KDL `swap_tiled_layout` blocks (`stacked_main`) to dynamically restructure focus across active system monitoring views.
- **PipeWire Audio Control Stack:** Integrated `coppwr` (low-level PipeWire state inspector/control GUI) and `qpwgraph` (Qt-based PipeWire graph manager) for visual audio routing alongside terminal-based `pw-top`.
- **Atomic Session Lifecycle:** Resolved nested shell issues and stale process blocks in `synth-overview` by utilizing `zellij attach --create "$SESSION"` with automated `EXITED` state cleanup.
- **Pagination & Navigation:** Integrated `Alt+h` and `Alt+l` keybindings for fluid pagination and focused navigation across split view contexts in synth overview.


## Stream Intake Processing Engine (`yuko -s`) `=^._.^=`
Added native stream intake parsing via `synth -s` to ingest, apply, and execute LLM-driven workspace mutations over standard input.

### Standard Stdin Stream Payload Template
```bash
synth -s << 'EOF'
=^-.-^=
CREATE path/to/file.ext
```language
# Source code body goes here

=^-.-^=
EOF
```

#### Core Intake Capabilities
* **Declarative File Operations:** Standardized parsing for `CREATE`, `EDIT`, and `DELETE` directives targeting single or multiple workspace targets.
* **Contextual Target Dispatch:** Automatically detects created/modified entrypoints (`main.py`, `driver.py`, `default.nix`) and executes them post-mutation.
* **Resilient Patch Application:** Supports search/replace anchor blocks for non-destructive, surgical edits across existing source files.
* **Ephemeral Driver Execution:** Executes self-destructing Python helper scripts when inline `ephemeral: true` metadata or dynamic mutation heuristics are detected.


## AST Consumption & Code Synthesis Pipeline (synth) `=^-.-^=`

Refined function-level abstract syntax tree (AST) anchor patching within the core engine modules (`modules/synths/src/engine`).

* **Targeted Code Generation:** Executed via `synth filename.ext -i "prompt"`.
* **Coordinated Analysis:** Operations now heavily utilize `synth -c` for multi-file analysis, extended prose evaluation, and interface-level chaining of thought frames.

## Networking Infrastructure & Provisioning `=^._.^=`

Integrated new internal routing and gateway constructs (`modules/networking/`).

* **Authentication Status:** Serial authentication discrepancies during automated provisioning are currently being ironed out.
* **Protocol Behavior:** SSH behaves normally; machines parse their own handshakes while firewalls and routing rules are being locked down.

## Dotfiles, Infrastructure, and Ghosts `(=^·ｪ·^=)`

Continued refinement of system composition across distinct host profiles.

* **Environment Parameters:** Streamlining declarative environment parameters and asset management.
* **Host Profiles:** Applied across `yuko-core` compile with `ym` and `yuko-fob` compile that style with `yf`.
* **System State:** Accompanied by the subtle, necessary ghost in the machine.

## Outlook & System Integration `(=^‥^=)`

Gradually aligning task orchestration to feed `synth` deeper intelligence capabilities, bridging the gap toward native OS integration.

* *Operational Note:* Neuromancing for the fun ... currently considor this to be a type of Front-End Operating System development

# _Architecture developed in with OpenAI models such as ChatGPT_
# **_Engineering and Design developed with Google models such as Gemini_**
