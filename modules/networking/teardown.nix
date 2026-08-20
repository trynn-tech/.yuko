# modules/networking/teardown.nix
{ pkgs, lib, config, ... }:

let
  cfg = config.yuko.networking.teardown;

  yukoTeardownScript = pkgs.writeShellScriptBin "yuko-teardown" ''
    set -euo pipefail
    export PATH="${lib.makeBinPath [ pkgs.systemd pkgs.iproute2 pkgs.sudo pkgs.procps pkgs.coreutils ]}:$PATH"

    echo "[yuko-teardown] Inspecting active virtual router interfaces..."

    # 1. Terminate OpenWrt QEMU user service if active
    if systemctl --user is-active --quiet openwrt-fob.service 2>/dev/null; then
      echo "[yuko-teardown] Stopping openwrt-fob.service..."
      systemctl --user stop openwrt-fob.service || true
    fi

    # 2. Check and remove virtual network devices
    if ip link show br-yuko >/dev/null 2>&1 || ip link show tap-yuko >/dev/null 2>&1; then
      echo "[yuko-teardown] Tearing down br-yuko / tap-yuko bridge interfaces..."
      
      sudo ip link set dev br-yuko down 2>/dev/null || true
      sudo ip link set dev tap-yuko down 2>/dev/null || true
      sudo ip link delete br-yuko type bridge 2>/dev/null || true
      sudo ip link delete tap-yuko type tap 2>/dev/null || true

      echo "[yuko-teardown] Restarting NetworkManager to restore default host gateway..."
      sudo systemctl restart NetworkManager 2>/dev/null || true
    else
      echo "[yuko-teardown] No virtual bridge artifacts detected. Network clean."
    fi
  '';
in
{
  options.yuko.networking.teardown = {
    enable = lib.mkEnableOption "Yuko network teardown utility and activation hooks";
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ yukoTeardownScript ];

    home.activation.autoTeardownYukoNetwork = lib.hm.dag.entryBefore [ "writeBoundary" ] ''
      $DRY_RUN_CMD ${yukoTeardownScript}/bin/yuko-teardown
    '';
  };
}
