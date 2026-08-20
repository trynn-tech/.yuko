{ pkgs, config, lib, ... }:

let
  cfg = config.yuko.openwrt-provision;
  dataDir = "${config.home.homeDirectory}/.local/share/openwrt";
  imgFile = "${dataDir}/openwrt.img";
  socketPath = "${dataDir}/qemu-serial.sock";
  sshKeyPath = "${config.home.homeDirectory}/.ssh/id_ed25519.pub";

  payloadScript = ./scripts/yuko-provision.sh;

  openwrtImageGz = pkgs.fetchurl {
    url = "https://downloads.openwrt.org/releases/23.05.2/targets/x86/64/openwrt-23.05.2-x86-64-generic-ext4-combined.img.gz";
    sha256 = "f8588a9937bd77010f88545ccd21bb59cf8b47462793d80ef7d49ad92ce8ab11";
  };

  firstBootScript = pkgs.writeText "99-first-boot-setup" ''
    #!/bin/sh
    echo "[yuko-init] Overriding Dropbear security config..."
    uci set dropbear.@dropbear[0].PasswordAuth='off'
    uci set dropbear.@dropbear[0].RootPasswordAuth='off'
    uci set dropbear.@dropbear[0].Port='22'
    uci commit dropbear

    echo "[yuko-init] Enforcing serial TTY authentication login prompt..."
    uci set system.@system[0].ttylogin='1'
    uci commit system

    if [ -f /root/yuko-provision.sh ]; then
      echo "[yuko-init] Executing inner payload script..."
      chmod +x /root/yuko-provision.sh
      /root/yuko-provision.sh
    fi
    exit 0
  '';

  bootScript = pkgs.writeShellScript "openwrt-fob-boot" ''
    set -euo pipefail
    echo "[yuko-fob] Launching Ext4 native OpenWrt sandbox..."
    rm -f "${socketPath}"

    if [ -w /dev/kvm ]; then
      echo "[yuko-fob] KVM acceleration enabled."
      KVM_ARGS=("-enable-kvm" "-cpu" "host")
    else
      echo "[yuko-fob] WARNING: Running via software emulation." >&2
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
    echo "[yuko] Opening serial console stream..."
    ${pkgs.netcat-openbsd}/bin/nc -U "${socketPath}"
  '';

in {
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
      e2fsprogs
      util-linux
      openssl
      yukoNexus
    ];

    home.activation.provisionOpenWrtImage = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      $DRY_RUN_CMD mkdir -p "${dataDir}"
      if [ ! -f "${imgFile}" ]; then
        $DRY_RUN_CMD echo "[yuko] Extracting vanilla ext4-combined OpenWrt image..."
        $DRY_RUN_CMD ${pkgs.gzip}/bin/gzip -d -c -q "${openwrtImageGz}" > "${imgFile}.tmp" || true
        $DRY_RUN_CMD chmod 644 "${imgFile}.tmp"
        
        $DRY_RUN_CMD echo "[yuko] Provisioning rootfs via offset extraction..."
        OFFSET=$(${pkgs.util-linux}/bin/partx -g -o START -n 2 "${imgFile}.tmp" 2>/dev/null | tr -d ' ' || echo "34816")
        SIZE=$(${pkgs.util-linux}/bin/partx -g -o SECTORS -n 2 "${imgFile}.tmp" 2>/dev/null | tr -d ' ' || echo "212992")

        EPHEMERAL_PASS=$(${pkgs.openssl}/bin/openssl rand -hex 8)
        SALT=$(${pkgs.openssl}/bin/openssl rand -base64 6 | tr -dc 'a-zA-Z0-9' | head -c 8)
        PASS_HASH=$(${pkgs.openssl}/bin/openssl passwd -6 -salt "$SALT" "$EPHEMERAL_PASS")

        echo ""
        echo "=================================================================="
        echo "[yuko-fob] OPENWRT INITIAL ROOT SERIAL PASSWORD GENERATED:"
        echo "           User:     root"
        echo "           Password: $EPHEMERAL_PASS"
        echo "=================================================================="
        echo ""

        PUBKEY=""
        if [ -f "${sshKeyPath}" ]; then
          PUBKEY=$(cat "${sshKeyPath}")
        fi

        TEMP_KEY_FILE=$(mktemp)
        printf "%s\n" "$PUBKEY" > "$TEMP_KEY_FILE"

        TEMP_PASSWD_FILE=$(mktemp)
        printf "root:x:0:0:root:/root:/bin/ash\n" > "$TEMP_PASSWD_FILE"

        TEMP_SHADOW_FILE=$(mktemp)
        printf "root:%s:19700:0:99999:7:::\n" "$PASS_HASH" > "$TEMP_SHADOW_FILE"

        TEMP_INITTAB_FILE=$(mktemp)
        cat << 'EOF' > "$TEMP_INITTAB_FILE"
::sysinit:/etc/init.d/rcS S boot
::shutdown:/etc/init.d/rcS K shutdown
::askfirst:/bin/login
ttyS0::askfirst:/bin/login
tty1::askfirst:/bin/login
EOF

        ROOTFS_TMP=$(mktemp)
        dd if="${imgFile}.tmp" of="$ROOTFS_TMP" bs=512 skip="$OFFSET" count="$SIZE" status=none

        ${pkgs.e2fsprogs}/bin/debugfs -w -R "write ${firstBootScript} /etc/uci-defaults/99-first-boot-setup" "$ROOTFS_TMP" >/dev/null 2>&1
        ${pkgs.e2fsprogs}/bin/debugfs -w -R "write ${payloadScript} /root/yuko-provision.sh" "$ROOTFS_TMP" >/dev/null 2>&1
        ${pkgs.e2fsprogs}/bin/debugfs -w -R "write $TEMP_PASSWD_FILE /etc/passwd" "$ROOTFS_TMP" >/dev/null 2>&1
        ${pkgs.e2fsprogs}/bin/debugfs -w -R "write $TEMP_SHADOW_FILE /etc/shadow" "$ROOTFS_TMP" >/dev/null 2>&1
        ${pkgs.e2fsprogs}/bin/debugfs -w -R "write $TEMP_INITTAB_FILE /etc/inittab" "$ROOTFS_TMP" >/dev/null 2>&1
        ${pkgs.e2fsprogs}/bin/debugfs -w -R "mkdir /etc/dropbear" "$ROOTFS_TMP" >/dev/null 2>&1 || true
        ${pkgs.e2fsprogs}/bin/debugfs -w -R "mkdir /root/.ssh" "$ROOTFS_TMP" >/dev/null 2>&1 || true
        ${pkgs.e2fsprogs}/bin/debugfs -w -R "write $TEMP_KEY_FILE /etc/dropbear/authorized_keys" "$ROOTFS_TMP" >/dev/null 2>&1
        ${pkgs.e2fsprogs}/bin/debugfs -w -R "write $TEMP_KEY_FILE /root/.ssh/authorized_keys" "$ROOTFS_TMP" >/dev/null 2>&1

        dd if="$ROOTFS_TMP" of="${imgFile}.tmp" bs=512 seek="$OFFSET" count="$SIZE" conv=notrunc status=none
        rm -f "$TEMP_KEY_FILE" "$TEMP_PASSWD_FILE" "$TEMP_SHADOW_FILE" "$TEMP_INITTAB_FILE" "$ROOTFS_TMP"
        $DRY_RUN_CMD mv "${imgFile}.tmp" "${imgFile}"
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
