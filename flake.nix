{
  description = "Yuko HM profiles (modes) with shared modules + nixCats";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nixCats = {
      url = "github:BirdeeHub/nixCats-nvim";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, nixCats, ... }:
  let
    system = "x86_64-linux";  # adjust if needed
    pkgs   = import nixpkgs { inherit system; };
  in {
    # Profile 1: main mode
    homeConfigurations."yuko-core" =
      home-manager.lib.homeManagerConfiguration {
        inherit pkgs;

        modules = [
          ./profiles/yuko-core.nix
        ];

        extraSpecialArgs = {
          inherit nixCats;
        };
      };

    # Profile 2: minimal mode (example alt)
    homeConfigurations."yuko-minimal" =
      home-manager.lib.homeManagerConfiguration {
        inherit pkgs;

        modules = [
          ./profiles/yuko-minimal.nix
        ];

        extraSpecialArgs = {
          inherit nixCats;
        };
      };
  };
}
