# profiles/yuko-core.nix
{ config, pkgs, ... }:

{
  imports = [
    ../modules/core.nix
    ../modules/shell/default.nix
    ../modules/tmux/default.nix
    ../modules/editors/nixvim.nix
  ];

  # Turn on the “default shell” behavior for this profile/mode
  yuko.shell.default = true;
}
