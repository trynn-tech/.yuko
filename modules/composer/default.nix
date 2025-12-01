# modules/composer/default.nix
{ ... }:
{
  imports = [
    ./cli.nix
    ./local-bin.nix
    ./ctags.nix
    # later: ./lint.nix ./formatter.nix etc.
  ];
}
