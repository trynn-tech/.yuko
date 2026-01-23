{ config, pkgs, ... }:

{
  imports = [ ./hardware-configuration.nix ];

  boot.loader.grub.device = "/dev/sda";

  networking.hostName = "nixos"; # Define your hostname.

  # Set your time zone.
  time.timeZone = "America/New_York";

  # Enable the OpenSSH daemon.
  services.openssh.enable = true;

  # Enable the NixOS Walled Garden flake.
  nixpkgs.config.allowUnfree = true;

  # Define a user account. Don't forget to set a password with `passwd`!
  users.users.john = {
    isNormalUser = true;
    home = "/home/john";
    shell = pkgs.zsh;
  };

  # Define a new user account.
  users.users.jane = {
    isNormalUser = true;
    home = "/home/jane";
    shell = pkgs.zsh;
  };

  # Define a new user group.
  users.groups.john = {
    members = [ "john"