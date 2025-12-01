# modules/composer/default.nix
{ ... }:
{
  imports = [
    ./ctags.nix
    #./sculpt.nix
    ./cli.nix
    # later: ./lint.nix ./formatter.nix etc.
  ];
}
