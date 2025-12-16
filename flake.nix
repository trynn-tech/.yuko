# flake.nix 
{
  description = "YukoNix Scaffold – Home Manager + nixvim profiles";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.11";
    home-manager = {
      url = "github:nix-community/home-manager/release-23.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixvim = {
      url = "github:nix-community/nixvim/nixos-23.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, nixvim, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };

      trynnDefaults = {
        userName = "trynn";
        homeDir  = "/home/trynn";
      };

      yukoEnv = if builtins.pathExists ./.yuko-env.nix
        then import ./.yuko-env.nix
        else trynnDefaults;

      # 3. mkYuko function - ONLY includes the user-specific module
      mkYuko = { userName, homeDir }: [
          ./profiles/yuko-core.nix      # All module imports are now nested inside here
          {
            home.username = userName;
            home.homeDirectory = homeDir;
            home.stateVersion = "23.11";
          }
        ];

    in {
      homeConfigurations = {
        ${yukoEnv.userName} = home-manager.lib.homeManagerConfiguration {
          inherit pkgs;
          modules = mkYuko yukoEnv;
        };

        yuko-core = home-manager.lib.homeManagerConfiguration {
          inherit pkgs;
          modules = mkYuko yukoEnv;
        };
      };
    };
}

