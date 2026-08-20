# modules/networking/wan-gateway.nix
{ pkgs, config, lib, ... }: {
  options.yuko.wan = {
    enable = lib.mkEnableOption "Direct WAN Gateway & Secure Log Receiver";
    wanInterface = lib.mkOption {
      type = lib.types.str;
      default = "vm-fob-wan";
      description = "Virtual interface connected directly to the modem/WAN";
    };
  };

  config = lib.mkIf config.yuko.wan.enable {
    home.packages = with pkgs; [
      openssh
      netcat
    ];
  };
}
