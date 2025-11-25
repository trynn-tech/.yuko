# modules/mail/default.nix
{ ... }:

{
  imports = [
    ./accounts/trynn-primary.nix
    ./mbsync.nix
    ./msmtp.nix
    ./neomutt.nix
  ];
}
