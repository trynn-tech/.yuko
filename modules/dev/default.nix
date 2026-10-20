# modules/dev/default.nix
{ config, lib, pkgs, ... }:
{
  imports = [
    ./nix
    ./git.nix
  ];

  # Essential system utility packages housed directly in core
  home.packages = with pkgs; [
    ghidra
    gdb
    gcc
    gnumake
    nodejs
    nix-index
    nix-alien
  ];
}
