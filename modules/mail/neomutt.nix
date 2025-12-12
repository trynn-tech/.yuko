# modules/mail/neomutt.nix
{
  config,
  lib,
  pkgs,
  ...
}:

let
  active = config.yuko.mail.activeAccount;
  hmAccount = config.yuko.mail.activeHmAccount;
  yukoAccount = config.yuko.mail.activeAccountMeta;

  maildir = yukoAccount.maildirBasePath;
in
{
  programs.neomutt.enable = true;

  xdg.configFile."neomutt/neomuttrc".text = ''
    # ---- NeoMutt Config (YukoNix) ----

    # Maildir root for all folders
    set folder = "${maildir}"

    # INBOX path
    set spoolfile = "${maildir}/Inbox"

    # Where read mail gets stored (we keep it Inbox-neutral)
    set mbox = "${maildir}/Inbox"

    # Identity
    set realname = "${hmAccount.realName}"
    set from = "${hmAccount.address}"

    # Sorting
    set sort = "threads"
    set sort_aux = "reverse-last-date-received"

    # UI
    set editor = "nvim"
    set mark_old = "no"
    set check_new = "yes"

    # Caches
    set header_cache = "~/.cache/neomutt/headers"
    set message_cachedir = "~/.cache/neomutt/messages"
  '';

  # Optional: add your own binds here if you want:
  # xdg.configFile."neomutt/bindings".text = ''
}
