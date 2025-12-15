# .yuko/flake.nix
{

  description = "YukoNix Scaffold – Home Manager + nixvim profiles";
  #========
  # Inputs
  #========
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

  #========
  # Outputs
  #========
  outputs =
    {
      self,
      nixpkgs,
      home-manager,
      nixvim,
      ...
    }:
    let
      system = "x86_64-linux";

      pkgs = import nixpkgs { inherit system; };

      yukoEnv =
        if builtins.pathExists ./.yuko-env.nix then
          import ./.yuko-env.nix
        else
          import ./.yuko-env.example.nix;

      mkYuko =
        { userName, homeDir, profilePath }:
        home-manager.lib.homeManagerConfiguration {
          inherit pkgs;

          modules = [
            profilePath 
            nixvim.homeModules.nixvim
            {
              home.username = yukoEnv.userName;
              home.homeDirectory = yukoEnv.homeDir;
              home.stateVersion = "23.11";
            }
          ];
        };
    in
    {
      homeConfigurations = {
        yuko-core = mkYuko {
          inherit (yukoEnv) userName homeDir;
          profilePath = ./profiles/yuko-core.nix; # Pass the core profile file
        };

        "yuko-dev" = mkYuko {
          inherit (yukoEnv) userName homeDir;
          profilePath = ./profiles/yuko-dev.nix; # Pass the new dev profile file
        };
      };
    };
}
