# modules/networking/default.nix
{ config, lib, pkgs, ... }: {
  imports = [
    ./wan-gateway.nix
    ./syslog-receiver.nix
    ./openwrt-provision.nix
    ./construct.nix
    ./teardown.nix
    #./tun2socks.nix see dev note in source code
  ];
}
