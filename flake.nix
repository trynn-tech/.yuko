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

    synths.url = "path:./modules/synths";
  };

  outputs = { self, nixpkgs, home-manager, nur, nixvim, nix-alien, microvm, synths, ... } @ inputs:
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
      mkYuko = { userName, homeDir, profileModule }:
        home-manager.lib.homeManagerConfiguration {
          inherit pkgs;
          extraSpecialArgs = { inherit inputs; };
          modules = [
            profileModule
            nixvim.homeModules.nixvim
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
        # Core Workstation Profile (can import networking analysis tools)
        yuko-core = mkYuko {
          inherit (yukoEnv) userName homeDir;
          profileModule = ./profiles/yuko-core.nix;
        };

        # Forward Operating Base Profile (provisions and runs local OpenWrt QEMU sandbox)
        yuko-fob = mkYuko {
          inherit (yukoEnv) userName homeDir;
          profileModule = ./profiles/yuko-fob.nix;
        };

        # Forward Operating Base Profile (provisions and runs local OpenWrt QEMU sandbox)
        yuko-windows = mkYuko {
          inherit (yukoEnv) userName homeDir;
          profileModule = ./profiles/yuko-windows.nix;
        };
      };
    };
}
