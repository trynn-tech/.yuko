# modules/networking/default.nix
{ config, lib, pkgs, ... }: {
  imports = [
    ./wan-gateway.nix
    ./syslog-receiver.nix
    ./openwrt-provision.nix
  ];
}
