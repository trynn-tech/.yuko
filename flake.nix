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

    # TODO: remove this with custom refactor [6ae36097-9c64-48bf-b0ce-01f972fa221b]
    hermes-agent.url = "github:NousResearch/hermes-agent";
    
    # Register your local synth engine module as a flake input
    synths.url = "path:./modules/synths";
  };
  
  outputs = { self, nixpkgs, home-manager, nur, nixvim, nix-alien, hermes-agent, synths, ... } @ inputs:
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
