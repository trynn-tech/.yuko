# modules/composer/default.nix
{ ... }:
{
  imports = [
    ./ctags.nix
    #./yk.nix
    # later: ./lint.nix ./formatter.nix etc.
  ];
}
