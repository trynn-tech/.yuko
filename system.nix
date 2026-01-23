# system.nix
{ config, pkgs, ... }:

{
  imports = [ ./hardware-configuration.nix ];

  # Define a new user account.
  users.users.john = {
    isNormalUser = true;
    home = "/home/john";
    shell = pkgs.zsh;
  };

  # Define a new user group.
  users.groups.john = {
    members = [ "john" ];
  };

  # Define a new user account.
  users.users.jane = {
    isNormalUser = true;
    home = "/home/jane";
    shell = pkgs.zsh;