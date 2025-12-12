# modules/mail/accounts/trynn-primary.nix
{ config, lib, ... }:

let
  home = config.home.homeDirectory;
  accountName = "trynn-primary";
in
{
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

  yuko.mail.accounts.${accountName} = {
    maildirBasePath = "${home}/Mail/${accountName}";
    imapPassEntry = "mail/trynn-tech-primary";
    smtpPassEntry = "mail/trynn-tech-primary";
  };
}
