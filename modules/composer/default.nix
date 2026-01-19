# modules/composer/default.nix
{ ... }:
{
  imports = [
    ./cli.nix
    ./local-bin.nix
    ./ctags.nix
    ./aider.nix
  ];
}
