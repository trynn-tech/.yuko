# modules/core/default.nix
{ config, lib, pkgs, ... }:

let
  narDir = "$HOME/.local/share/yuko";
  narPath = "${narDir}/system-closure.nar";

  # Offline detection and prompt script
  offlinePromptScript = pkgs.writeScriptBin "yuko-offline-check" ''
    #!${pkgs.bash}/bin/bash
    
    # Quick connectivity check against a reliable IP
    if ! ${pkgs.iputils}/bin/ping -c 1 -w 2 1.1.1.1 &>/dev/null; then
      echo "--------------------------------------------------------"
      echo "[yuko] No internet connection detected."
      if [ -f "${narPath}" ]; then
        echo "[yuko] Local NAR fallback available at: ${narPath}"
        read -p "Would you like to import the local system-closure.nar? [y/N]: " choice
        case "$choice" in 
          y|Y)
            echo "[yuko] Importing NAR into local Nix store..."
            ${pkgs.nix}/bin/nix-store --import < "${narPath}"
            echo "[yuko] Import complete. Proceeding with offline configuration."
            ;;
          *)
            echo "[yuko] Skipping NAR import. Proceeding with current store."
            ;;
        esac
      else
        echo "[yuko] Warning: No local system-closure.nar found and offline."
      fi
      echo "--------------------------------------------------------"
    fi
  '';

  # Export script to backup /etc/nixos, ~/.yuko, and all local binary NAR iterations
  yukoExportScript = pkgs.writeShellScriptBin "yuko-export" ''
    #!${pkgs.bash}/bin/bash

    TARGET_MOUNT="''${1:-/mnt}"
    BACKUP_DIR="$TARGET_MOUNT/yuko-backups"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    ARCHIVE_NAME="yuko-snapshot-$TIMESTAMP.tar.zst"

    echo "--------------------------------------------------------"
    echo "[yuko-export] Initiating system state & library backup..."
    echo "--------------------------------------------------------"

    if [ ! -d "$TARGET_MOUNT" ]; then
      echo "[yuko-export] Error: Target mount point $TARGET_MOUNT does not exist or is not mounted."
      exit 1
    fi

    mkdir -p "$BACKUP_DIR"

    # Temporary staging area
    STAGING_DIR=$(mktemp -d)
    mkdir -p "$STAGING_DIR/etc_nixos" "$STAGING_DIR/yuko_repo" "$STAGING_DIR/nar_libraries"

    echo "[yuko-export] Gathering /etc/nixos..."
    if [ -d /etc/nixos ]; then
      sudo cp -r /etc/nixos/* "$STAGING_DIR/etc_nixos/" 2>/dev/null || echo "[yuko-export] Note: Requires sudo permissions for full /etc/nixos copy."
    fi

    echo "[yuko-export] Gathering ~/.yuko directory..."
    if [ -d "$HOME/.yuko" ]; then
      cp -r "$HOME/.yuko" "$STAGING_DIR/yuko_repo/"
    fi

    echo "[yuko-export] Gathering binary libraries (system-closure.nar iterations)..."
    if [ -d "$HOME/.local/share/yuko" ]; then
      cp -r "$HOME/.local/share/yuko"/* "$STAGING_DIR/nar_libraries/" 2>/dev/null || true
    fi

    echo "[yuko-export] Compressing bundle into $BACKUP_DIR/$ARCHIVE_NAME..."
    ${pkgs.zstd}/bin/tar --zstd -cf "$BACKUP_DIR/$ARCHIVE_NAME" -C "$STAGING_DIR" .

    # Cleanup staging
    rm -rf "$STAGING_DIR"

    echo "--------------------------------------------------------"
    echo "[yuko-export] Success! Backup safely stored at:"
    echo "              $BACKUP_DIR/$ARCHIVE_NAME"
    echo "--------------------------------------------------------"
  '';
in
{
  imports = [
    ../dev
    ../editors
    ../shell
    ../synths
  ];

  programs.home-manager.enable = true;

  # Provision share directory and automatically generate initial baseline NAR on activation if missing
  home.activation.createYukoShare = lib.hm.dag.entryAfter ["writeBoundary"] ''
    $DRY_RUN_CMD mkdir -p "$HOME/.local/share/yuko"
    if [ ! -f "$HOME/.local/share/yuko/system-closure.nar" ]; then
      echo "[yuko] Generating initial system-closure.nar baseline..."
      $DRY_RUN_CMD ${pkgs.nix}/bin/nix-store --export $(${pkgs.nix}/bin/nix-store -qR /run/current-system) > "$HOME/.local/share/yuko/system-closure.nar"
    fi
  '';

  # Essential system utility packages housed directly in core
  home.packages = with pkgs; [
    e2fsprogs 
    dosfstools 
    zip 
    unzip
    pulseaudio
    offlinePromptScript 
    yukoExportScript 
  ];
}
