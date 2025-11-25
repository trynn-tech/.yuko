# modules/mail/neomutt.nix
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkIf;

  # Dynamic resolution from core.nix
  hmAccount   = config.yuko.mail.activeHmAccount;
  yukoAccount = config.yuko.mail.activeAccountMeta;

  maildirBase = yukoAccount.maildirBasePath;
in
{
  programs.neomutt = {
    enable = true;

    settings = {
      # Core folders (Maildir)
      folder      = maildirBase;       # e.g. /home/trynn/Mail/trynn-primary
      spoolfile   = "+INBOX";
      mbox        = maildirBase;       # “mbox” also points at the same Maildir root
      record      = "+Sent";
      postponed   = "+Drafts";
      trash       = "+Trash";

      # Identity (could also pull from hmAccount, but you already know the address)
      realname    = ''"Tristen Young"'';
      from        = hmAccount.address or "tristen@trynn.tech";

      # Send via msmtp account we set up
      sendmail    = ''"msmtp -a trynn-primary"'';

      # UX
      editor      = "nvim";
      sort        = "threads";
      sort_aux    = "reverse-last-date-received";
      mark_old    = "no";
      date_format = ''"%Y-%m-%d %H:%M"'';
      timeout     = "5";
      check_new   = "yes";

      # Caches
      header_cache    = "~/.cache/neomutt/headers";
      message_cachedir = "~/.cache/neomutt/messages";
    };

    sidebar = {
      enable    = true;
      shortPath = true;
      format    = "%D%?F? [%F]?%* %?N?%N/?%S";
      width     = 30;
    };

    binds = [
      { map = [ "index" ]; key = "q";           action = "quit"; }
      { map = [ "index" ]; key = "<space>";     action = "next-page"; }
      { map = [ "index" ]; key = "<backspace>"; action = "previous-page"; }
      { map = [ "index" ]; key = "m";           action = "mail"; }
    ];

    # You can uncomment later for raw extra neomutt rc snippets:
    # extraConfig = ''
    #   # Adjunct Code here ...
    # '';
  };

  ########################################
  ## Clean override of legacy configs
  ########################################
  home.activation.neomuttCleanLegacy =
    mkIf config.programs.neomutt.enable
      (lib.hm.dag.entryBefore [ "writeBoundary" ] ''
        # Delete old user mutt configs that might override Home Manager.
        for f in ".muttrc" ".neomuttrc"; do
          if [ -f "$HOME/$f" ]; then
            echo "YukoNix: removing legacy mutt config $HOME/$f (Home Manager now owns neomutt)."
            rm -f "$HOME/$f"
          fi
        done

        if [ -d "$HOME/.config/mutt" ]; then
          echo "YukoNix: removing legacy ~/.config/mutt directory."
          rm -rf "$HOME/.config/mutt"
        fi
      '');
}
