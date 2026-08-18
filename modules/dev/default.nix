# modules/dev/default.nix
{ config, lib, pkgs, ... }:
{
  imports = [
    ./nix
  ];

  # Essential system utility packages housed directly in core
  home.packages = with pkgs; [
    ghidra
    gdb
    nix-index
    nix-alien
  ];
}
