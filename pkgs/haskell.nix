{ pkgs ? import <nixpkgs/nixpkgs-unstable> { overlays = [ (self: super: { haskell = super.haskell // { packages = super.haskell.packages.ghc924; }); } ]; }
