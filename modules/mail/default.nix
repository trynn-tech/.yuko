# modules/mail/default.nix 
{ config, lib, ... }:

let
  isPersonalUser = config.home.username == "trynn";
in
{
  # Import the personal account module ONLY IF the user is 'trynn'.
  imports = lib.optionals isPersonalUser [
    ./accounts/trynn-primary.nix
    ./mbsync.nix
    ./msmtp.nix
    ./neomutt.nix
  ];
  
  # ... other mail settings or programs (like mu4e, notmuch, etc.)
}

