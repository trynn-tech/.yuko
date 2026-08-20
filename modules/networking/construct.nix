# modules/networking/construct.nix
{ pkgs, lib, config, ... }:

let
  cfg = config.yuko.networking.construct;

  yukoConstructScript = pkgs.writeShellScriptBin "yuko-construct" ''
    set -euo pipefail
    export PATH="${lib.makeBinPath [ pkgs.systemd pkgs.iproute2 pkgs.sudo pkgs.coreutils ]}:$PATH"

    echo "[yuko-construct] Initializing virtual router network pipeline..."

    # 1. Ensure TAP/Bridge interfaces exist on the host
    if ! ip link show br-yuko >/dev/null 2>&1 || ! ip link show tap-yuko >/dev/null 2>&1; then
      echo "[yuko-construct] Virtual interface br-yuko or tap-yuko missing. Creating interfaces..."
      
      sudo ip link add dev br-yuko type bridge 2>/dev/null || true
      sudo ip tuntap add dev tap-yuko mode tap user "$USER" 2>/dev/null || true
      sudo ip link set dev tap-yuko master br-yuko 2>/dev/null || true
      sudo ip link set dev br-yuko up 2>/dev/null || true
      sudo ip link set dev tap-yuko up 2>/dev/null || true
    else
      echo "[yuko-construct] Virtual bridge interfaces (br-yuko, tap-yuko) verified."
    fi

    # 2. Reload unit files and start openwrt-fob service
    echo "[yuko-construct] Registering and starting openwrt-fob.service..."
    systemctl --user daemon-reload
    systemctl --user restart openwrt-fob.service

    echo "[yuko-construct] Network scaffolding construction complete."
  '';
in
{
  options.yuko.networking.construct = {
    enable = lib.mkEnableOption "Yuko network construct scaffolding utility and activation hooks";
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ yukoConstructScript ];

    # Shift execution to run AFTER linkGeneration so systemd files are guaranteed to exist on disk
    home.activation.autoConstructYukoNetwork = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
      $DRY_RUN_CMD ${yukoConstructScript}/bin/yuko-construct
    '';
  };
}
