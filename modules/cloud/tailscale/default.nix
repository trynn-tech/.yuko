# yuko:todo taking a break to implement vagrant and doing taskfile sftp until
{ config, pkgs, lib, ... }:
let
  # Commands that require elevated permissions and must be pre-authorized in /etc/sudoers
  # We use the 'which' wrapper to ensure the target command exists before running sudo.
  installCommands = ''
    echo "Attempting automated Tailscale setup (requires NOPASSWD in sudoers)..."
    
    # 1. Install Tailscale APT package if not already installed
    if ! command -v tailscaled &> /dev/null; then
      echo "Installing Tailscale via apt..."
      sudo /usr/bin/apt install tailscale -y
    fi

    # 2. Enable and start the system service
    if ! /usr/bin/systemctl is-enabled tailscaled &> /dev/null; then
        echo "Enabling tailscaled system service..."
        sudo /usr/bin/systemctl enable tailscaled
        sudo /usr/bin/systemctl start tailscaled
    fi

    echo "Tailscale daemon is running."
  '';
in
{
  # 1. Activation Hook: Executes the script after the user environment is ready
  home.activation.tailscaleDaemonSetup = lib.hm.dag.entryAfter [ "writeBoundary" ] installCommands;

  # 2. Tailscale CLI: Ensure the 'tailscale' command is available to the user
  home.packages = [ pkgs.tailscale ];
  
  # 3. User Service: The user-level service that connects to the daemon
  services.tailscale.enable = true;
  services.tailscale.extraOptions = [ "--ssh=false" ];
}

###==========================================================
###=== Poetential Pre-Install Admin For System Networking ===
###==========================================================
##!/bin/bash
#set -euo pipefail
#
#TARGET_USER=${SUDO_USER:-$(whoami)} 
#
#if [ "$TARGET_USER" == "root" ]; then
#    echo "ERROR: Please run this script using your non-root user account (e.g., './pre-install.sh')." >&2
#    exit 1
#fi
#
#echo "--- YUKO-MAIN SETUP ---"
#echo "Tailscale requires system-level installation."
#
## Ask for the password once upfront, which grants sudo access for the rest of the script.
#sudo echo "Password accepted. Proceeding with system setup..."
#
## 1. Install Tailscale System Daemon (uses the password granted above)
#echo "--- 1. Installing Tailscale System Daemon ---"
#if ! command -v tailscaled &> /dev/null
#then
#    echo "Installing Tailscale via apt..."
#    sudo curl -fsSL https://tailscale.com/install.sh | sudo sh
#    sudo systemctl enable tailscaled
#    sudo systemctl start tailscaled
#else
#    echo "Tailscale Daemon already installed."
#fi
#
## 2. Deploy Nix Home Manager Configuration
#echo "--- 2. Deploying Home Manager Configuration for user: ${TARGET_USER} ---"
## This runs the Nix deployment for the current user.
#/run/current-system/sw/bin/home-manager switch --flake .#yuko-main
## If Home Manager is not yet in the PATH, use: /path/to/home-manager switch --flake .#yuko-main
#
#echo " "
#echo "=========================================================="
#echo "      ✅ YUKO-MAIN SETUP COMPLETE"
#echo "=========================================================="
#echo "Next Step: You must now connect this machine to your mesh."
#echo " "
#echo "1. Authenticate Tailscale (uses the password granted above):"
#echo "   sudo tailscale up"
#echo "   (Follow the URL provided in the output to log in)"
#echo " "
#echo "2. Check Syncthing status: systemctl --user status syncthing.service"
#echo "=========================================================="

