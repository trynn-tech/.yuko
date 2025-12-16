# modules/mail/accounts/trynn-primary.nix
{ config, lib, ... }:

# 1. Define variables outside the final output set
let
  home = config.home.homeDirectory;
  accountName = "trynn-primary";
  # Determine if the current deployment is for the personal user ("trynn")
  isPersonalUser = config.home.username == "trynn";
in

lib.mkIf isPersonalUser {

  # Configuration for Home Manager's built-in email accounts option
  accounts.email.accounts.${accountName} = {
    # Derived: this is primary iff it matches yuko.mail.activeAccount
    primary = config.yuko.mail.activeAccount == accountName;
    address = "tristen@trynn.tech";
    realName = "Tristen Young";
    userName = "tristen@trynn.tech";
    folders = {
      inbox = "INBOX";
      sent = "Sent";
      drafts = "Drafts";
      trash = "Trash";
    };
    imap = {
      host = "mail.hover.com";
      port = 993;
      tls = {
        enable = true;
        useStartTls = false; # 993 = implicit TLS
      };
    };
    smtp = {
      host = "mail.hover.com";
      port = 465;
      tls = {
        enable = true;
        useStartTls = false; # 465 = implicit TLS (smtps)
      };
    };
  };

  # Configuration for your custom yuko.mail option
  yuko.mail.accounts.${accountName} = {
    maildirBasePath = "${home}/Mail/${accountName}";
    imapPassEntry = "mail/trynn-tech-primary";
    smtpPassEntry = "mail/trynn-tech-primary";
  };
}
