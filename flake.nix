# flake.nix
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

    nur.url = "github:nix-community/NUR";
  };

  outputs = { self, nixpkgs, home-manager, nixvim, nur, ... } @ inputs:
    let
      system = "x86_64-linux";

      pkgs = import nixpkgs { 
        inherit system; 
        config.allowUnfree = true; # Required for many Firefox extensions
        overlays = [ 
          nur.overlays.default 
        ];
      };

      yukoEnv =
        if builtins.pathExists ./.yuko-env.nix then
          import ./.yuko-env.nix
        else
          import ./.yuko-env.example.nix;

      mkYuko = { userName, homeDir }:
        home-manager.lib.homeManagerConfiguration {
          inherit pkgs;
          extraSpecialArgs = { inherit inputs; }; 

          modules = [
            ./profiles/yuko-core.nix
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
      homeConfigurations.yuko-core = mkYuko yukoEnv;
    };
}
