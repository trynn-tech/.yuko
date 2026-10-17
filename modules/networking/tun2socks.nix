# For your system-level configuration (e.g. /etc/nixos/configuration.nix or matching module)
# TODO: in development so commented out on default should provide mobile sock5 proxy to act as default modem [37c0f371-5f74-4d62-88ad-f2d827e3fef2]
{ pkgs, ... }:

let
  tunInterface = "tun0";
in
{
  # Explicitly grant network management capabilities to the binary
  security.wrappers.tun2socks = {
    owner = "root";
    group = "root";
    capabilities = "cap_net_admin+ep";
    source = "${pkgs.tun2socks}/bin/tun2socks";
  };

  systemd.services.tun2socks-global = {
    description = "System-Wide Layer 3 Universal SOCKS5 Proxy Tunnel";
    after = [ "network.target" ];
    wantedBy = [ "multi-user.target" ];

    serviceConfig = {
      # Use our capability-wrapped binary with auto-routing enabled
      ExecStart = "/run/wrappers/bin/tun2socks --device tun://${tunInterface} --proxy socks5://127.0.0.1:1080 --auto-route";
      Restart = "on-failure";
      RestartSec = 3;
      # Restrict everything else for system hardening
      CapabilityBoundingSet = [ "CAP_NET_ADMIN" ];
    };
  };
}

