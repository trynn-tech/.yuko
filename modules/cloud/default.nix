# modules/cloud/default.nix
{ ... }:
{
  imports = [
    ./tailscale.nix
    ./syncthing.nix
  ];
}
