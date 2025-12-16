# modules/syncthing/default.nix 
{ config, lib, pkgs, ... }:

let
  # --- Path Definitions ---
  syncthingConfigDir = "${config.home.homeDirectory}/.config/syncthing";
  syncthingExecutable = "${lib.getExe pkgs.syncthing}"; 
in
{
  # --------------------------------------------------------
  # STEP 1: BLACKLIST THE BUILT-IN SYNCTHING MODULE
  # --------------------------------------------------------
  services.syncthing.enable = lib.mkForce false;

  # --------------------------------------------------------
  # STEP 2: WRITE THE UNIT FILE DIRECTLY VIA .text
  # This uses the correct attribute for string content, bypassing the 'absolute path' error.
  # --------------------------------------------------------
  home.file.".config/systemd/user/syncthing.service" = {
    # Use 'text' instead of 'source' to provide the content as a string.
    text = lib.mkForce ''
      [Unit]
      Description=Syncthing - Open Source Continuous File Synchronization (Manual)
      After=network-online.target
      Wants=network-online.target

      [Service]
      # ExecStart contains the fixes for paths and the service command
      ExecStart=${syncthingExecutable} serve --no-browser --no-restart --home ${syncthingConfigDir}
      
      # FIX: Disables the failing User Namespacing feature that caused status=217/USER.
      PrivateUsers=false
      
      Restart=on-failure
      RestartSec=10
      StandardOutput=journal
      StandardError=journal

      [Install]
      WantedBy=default.target
    ''; 
    
    target = ".config/systemd/user/syncthing.service";
  };


  # --------------------------------------------------------
  # STEP 3: ACTIVATE CONFIGURATION DIRECTORY CREATION 
  # (No changes here)
  # --------------------------------------------------------
  home.activation.syncthingDir = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    echo "Creating Syncthing directories:"
    
    # Configuration Directory
    echo "  - Config: ${syncthingConfigDir}"
    mkdir -p ${syncthingConfigDir}
    chown -R ${config.home.username}:${config.home.username} ${syncthingConfigDir}
    chmod 700 ${syncthingConfigDir}
    
    # State and Data directories (keeping existing definitions for completeness)
    echo "  - State: ${config.home.homeDirectory}/.local/state/syncthing"
    mkdir -p ${config.home.homeDirectory}/.local/state/syncthing
    chown -R ${config.home.username}:${config.home.username} ${config.home.homeDirectory}/.local/state/syncthing
    chmod 700 ${config.home.homeDirectory}/.local/state/syncthing

    echo "  - Data: ${config.home.homeDirectory}/.local/share/syncthing"
    mkdir -p ${config.home.homeDirectory}/.local/share/syncthing
    chown -R ${config.home.username}:${config.home.username} ${config.home.homeDirectory}/.local/share/syncthing
    chmod 700 ${config.home.homeDirectory}/.local/share/syncthing
  '';

  # --------------------------------------------------------
  # STEP 4: ADD PACKAGE TO PATH
  # --------------------------------------------------------
  home.packages = [ pkgs.syncthing ];
}
