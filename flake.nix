# flake.nix
{
  description = "YukoNix Scaffold – Home Manager + nixvim profiles";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nur.url = "github:nix-community/NUR";
    nixvim.url = "github:nix-community/nixvim";
    nix-alien.url = "github:thiagokokada/nix-alien";

    # MicroVM framework for localized routing and SOC sandbox
    microvm = {
      url = "github:microvm-nix/microvm.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Autonomous Subrepo / Submodule Inputs
    synths.url = "path:./modules/synths";
    frag.url = "path:./modules/editors/frag";
  };

  outputs = { self, nixpkgs, home-manager, nur, nixvim, nix-alien, microvm, synths, frag, ... } @ inputs:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
        overlays = [
          nur.overlays.default
          nix-alien.overlays.default
        ];
      };

      yukoEnv =
        if builtins.pathExists ./.yuko-env.nix then
          import ./.yuko-env.nix
        else
          import ./.yuko-env.example.nix;

      # Helper to instantiate Home Manager profiles consistently
      mkYuko = { userName, homeDir, profileModule, extraModules ? [] }:
        home-manager.lib.homeManagerConfiguration {
          inherit pkgs;
          extraSpecialArgs = { inherit inputs; };
          modules = [
            profileModule
            nixvim.homeModules.nixvim
            # Register module definitions so options like yuko.frag and yuko.synths are recognized
            ./modules/synths
            ./modules/editors/frag
          ] ++ extraModules ++ [
            {
              home.username = userName;
              home.homeDirectory = homeDir;
              home.stateVersion = "23.11";
            }
          ];
        };
    in
    {
      homeConfigurations = {
        # Core Workstation Profile (Enables frag & synths in profiles/yuko-core.nix)
        yuko-core = mkYuko {
          inherit (yukoEnv) userName homeDir;
          profileModule = ./profiles/yuko-core.nix;
        };

        # Forward Operating Base Profile
        yuko-fob = mkYuko {
          inherit (yukoEnv) userName homeDir;
          profileModule = ./profiles/yuko-fob.nix;
        };

        # Minimal / Windows Sandbox Profile (Can selectively omit yuko.frag / yuko.synths)
        yuko-windows = mkYuko {
          inherit (yukoEnv) userName homeDir;
          profileModule = ./profiles/yuko-windows.nix;
        };
      };
    };
}
