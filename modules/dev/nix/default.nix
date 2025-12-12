# modules/dev/nix/default.nix
{
  config,
  lib,
  pkgs,
  ...
}:

let
  inherit (lib)
    mkIf
    mkOption
    mkEnableOption
    types
    ;
in
{
  options.yuko.dev.nix = {
    enable = mkEnableOption "Nix dev tooling (nixd, formatter, linters)";

    formatter = mkOption {
      type = types.enum [
        "alejandra"
        "nixfmt"
      ];
      default = "alejandra";
      description = "Which Nix formatter nixd should use.";
    };
  };

  config = mkIf config.yuko.dev.nix.enable {
    home.packages = [
      pkgs.nixd
      pkgs.statix
      pkgs.deadnix
    ]
    ++ lib.optional (config.yuko.dev.nix.formatter == "alejandra") pkgs.alejandra
    ++ lib.optional (config.yuko.dev.nix.formatter == "nixfmt") pkgs.nixfmt;
  };
}
