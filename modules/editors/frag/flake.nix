# modules/editors/frag/flake.nix
{
  description = "Frag: Modular TUI AST and Block Editor";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };
    in
    {
      packages.${system}.default = import ./default.nix { inherit pkgs; };
      
      # Allows running directly via `nix run`
      apps.${system}.default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/frag";
      };
    };
}
