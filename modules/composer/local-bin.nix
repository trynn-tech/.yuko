# modules/composer/local-bin.nix
# modules/composer/local-bin.nix
{ config, lib, ... }:

let
  inherit (lib) mkOption mkIf types;
  homeDir = config.home.homeDirectory;
in
{
  ########################################
  ## Options
  ########################################
  options.yuko.composer.localBin.enable = mkOption {
    type = types.bool;
    default = true;
    description = "Ensure ~/.local/bin exists and is added to PATH.";
  };

  ########################################
  ## Config
  ########################################
  config = mkIf config.yuko.composer.localBin.enable {

    # 1) Add ~/.local/bin to PATH (no self-reference!)
    home.sessionPath = lib.mkAfter [
      "${homeDir}/.local/bin"
    ];

    # 2) Ensure directory exists on activation
    home.activation.ensureLocalBin = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      mkdir -p "${homeDir}/.local/bin"
    '';
  };
}
