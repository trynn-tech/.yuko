# modules/networking/syslog-receiver.nix

{ pkgs, ... }: {
#  services.syslog-ng = {
#    enable = true;
#    config = ''
#      @version: 4.2
#      @include "scl.conf"
#
#      source s_openwrt_network {
#        udp(ip(0.0.0.0) port(514));
#      };
#
#      destination d_openwrt_logs {
#        file("/var/log/openwrt-remote.log");
#      };
#
#      log {
#        source(s_openwrt_network);
#        destination(d_openwrt_logs);
#      };
#    '';
#  };
}
