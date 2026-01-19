# modules/shell/ledger.nix

{ config, lib, pkgs, ... }:

{
  options.yuko.shell.ledger.enable = lib.mkEnableOption "Ledger Karma & Personal Finance";

  config = lib.mkIf config.yuko.shell.ledger.enable {
    home.packages = [ pkgs.ledger ];

    home.sessionVariables = {
      FINANCE_DIR = "${config.home.homeDirectory}/yang_wiki/finance";
      LEDGER_FILE = "$FINANCE_DIR/journal.ledger";
      KARMA_FILE   = "$FINANCE_DIR/karma.ledger";
      PERS_FILE    = "$FINANCE_DIR/personal.ledger";
    };

    programs.zsh.initContent = ''
      # --- PERSONAL SECTOR ---
      tadd() {
        local date=$(date +%Y-%m-%d)
        echo -e "\n$date * $2\n    Personal:Expenses:General      \$$1\n    Personal:Assets:Cash" >> "$PERS_FILE"
        echo "Logged \$$1 to Personal Expenses."
      }

      # --- AGENT SECTOR ---
      klog() {
        local date=$(date +%Y-%m-%d)
        echo -e "\n$date * $3\n    Agents:$1:Karma             $2 KARMA\n    Agents:System:Income" >> "$KARMA_FILE"
      }

      kbounty() {
        local date=$(date +%Y-%m-%d)
        echo -e "\n$date ! BOUNTY: $2\n    (Agents:Staging:Unassigned)    $1 KARMA\n    (Agents:System:Potential)" >> "$KARMA_FILE"
        task add "$2" project:Bounties +KARMA:$1
      }

      kclaim() {
        local date=$(date +%Y-%m-%d)
        echo -e "\n$date * Claim: $3\n    Agents:$1:Karma             $2 KARMA\n    Agents:Staging:Unassigned   -$2 KARMA" >> "$KARMA_FILE"
        task project:Bounties "/$3/" done
      }
    '';

    programs.zsh.shellAliases = {
      bal   = "ledger bal";
      kbal  = "ledger -f $KARMA_FILE bal Agents";
      sbal  = "ledger -f $KARMA_FILE bal Staging";
      tbal  = "ledger -f $PERS_FILE bal Assets";
      ledg  = "nvim $LEDGER_FILE";
    };
  };
}
