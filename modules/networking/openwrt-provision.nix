# modules/networking/openwrt-provision.nix
{ pkgs, config, lib, ... }:

let
  cfg = config.yuko.openwrt-provision;
  dataDir = "${config.home.homeDirectory}/.local/share/openwrt";
  imgFile = "${dataDir}/openwrt.img";
  socketPath = "${dataDir}/qemu-serial.sock";
  sshKeyPath = "${config.home.homeDirectory}/.ssh/id_ed25519.pub";

  openwrtImageGz = pkgs.fetchurl {
    url = "https://downloads.openwrt.org/releases/23.05.2/targets/x86/64/openwrt-23.05.2-x86-64-generic-ext4-combined.img.gz";
    sha256 = "f8588a9937bd77010f88545ccd21bb59cf8b47462793d80ef7d49ad92ce8ab11";
  };

  bootScript = pkgs.writeShellScript "openwrt-fob-boot" ''
    set -euo pipefail
    echo "[yuko-fob] Launching Ext4 native OpenWrt sandbox..."
    rm -f "${socketPath}"

    if [ -w /dev/kvm ]; then
      KVM_ARGS=("-enable-kvm" "-cpu" "host")
    else
      KVM_ARGS=("-cpu" "qemu64")
    fi

    exec ${pkgs.qemu}/bin/qemu-system-x86_64 \
      "''${KVM_ARGS[@]}" \
      -m ${toString cfg.memory} \
      -nographic \
      -serial unix:"${socketPath}",server,nowait \
      -nic user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:2222-:22,hostfwd=tcp:127.0.0.1:8082-:80 \
      -drive file=${imgFile},format=raw,if=virtio
  '';

  yukoNexus = pkgs.writeShellScriptBin "yuko-nexus" ''
    if [ ! -S "${socketPath}" ]; then
      echo "[yuko] Socket ${socketPath} unavailable. Is openwrt-fob running?" >&2
      exit 1
    fi
    echo "[yuko] Opening serial console stream (Press Ctrl-C to detach)..."
    nc -U "${socketPath}"
  '';

in
{
  options.yuko.openwrt-provision = {
    enable = lib.mkEnableOption "Offline Local OpenWrt QEMU Sandbox";
    memory = lib.mkOption {
      type = lib.types.int;
      default = 2048;
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = with pkgs; [
      qemu
      gzip
      guestfs-tools
      yukoNexus
    ];

    home.activation.provisionOpenWrtImage = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      $DRY_RUN_CMD mkdir -p "${dataDir}"
      if [ ! -f "${imgFile}" ]; then
        $DRY_RUN_CMD echo "[yuko] Extracting vanilla ext4-combined OpenWrt image..."
        $DRY_RUN_CMD ${pkgs.gzip}/bin/zcat "${openwrtImageGz}" > "${imgFile}" || true
        $DRY_RUN_CMD chmod 644 "${imgFile}"

        $DRY_RUN_CMD echo "[yuko] Patching rootfs (Partition 2) via libguestfs..."
        
        PUBKEY=""
        if [ -f "${sshKeyPath}" ]; then
          PUBKEY=$(cat "${sshKeyPath}")
        fi

        ${pkgs.guestfs-tools}/bin/guestfish --rw -a "${imgFile}" << EOF
run
mount /dev/sda2 /

# Inject first-boot UCI initializer
mkdir-p /etc/uci-defaults
write /etc/uci-defaults/99-yuko-init "#!/bin/sh\nuci set dropbear.@dropbear[0].Interface=''\nuci set dropbear.@dropbear[0].Port='22'\nuci set dropbear.@dropbear[0].PasswordAuth='on'\nuci set dropbear.@dropbear[0].RootPasswordAuth='on'\nuci commit dropbear\nexit 0\n"
chmod 0755 /etc/uci-defaults/99-yuko-init

# Inject SSH keys
mkdir-p /etc/dropbear
mkdir-p /root/.ssh
write /etc/dropbear/authorized_keys "$PUBKEY\n"
write /root/.ssh/authorized_keys "$PUBKEY\n"
chmod 0600 /etc/dropbear/authorized_keys
chmod 0600 /root/.ssh/authorized_keys

umount-all
EOF
      fi
    '';

    systemd.user.services.openwrt-fob = {
      Unit = {
        Description = "Offline OpenWrt Local MicroVM Engine";
        After = [ "network.target" ];
      };
      Service = {
        Type = "simple";
        ExecStart = "${bootScript}";
        Restart = "on-failure";
        StandardOutput = "journal";
        StandardError = "journal";
      };
      Install = {
        WantedBy = [ "default.target" ];
      };
    };
  };
}
