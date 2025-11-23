{
  description = "YukoNix Scaffold – Home Manager + nixvim profiles";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nixvim = {
      url = "github:nix-community/nixvim";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, nixvim, ... }:
  let
    system = "x86_64-linux";
    pkgs   = import nixpkgs { inherit system; };
  in {
    homeConfigurations."yuko-core" =
      home-manager.lib.homeManagerConfiguration {
        inherit pkgs;

        modules = [
          ./profiles/yuko-core.nix
          nixvim.homeManagerModules.nixvim
        ];
      };
  };
}
