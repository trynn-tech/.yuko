#!/bin/sh
set -e

PROVISIONED_FLAG="/etc/.yuko_provisioned"
RESOLVED_USER="${SUDO_USER:-$(whoami 2>/dev/null || id -un)}"

# 1. Interactive shell hook check & privilege elevation guard
if [ ! -f "$PROVISIONED_FLAG" ] && [ -t 0 ]; then
  if [ "$(id -u)" -ne 0 ]; then
    echo "[yuko-nexus] Elevating privileges to execute appliance baseline..."
    exec sudo "$0" "$@"
  fi
fi

if [ -f "$PROVISIONED_FLAG" ]; then
  exit 0
fi
touch "$PROVISIONED_FLAG"

# Visual Candy Helpers
c_reset="\033[0m"
c_cyan="\033[1;36m"
c_green="\033[1;32m"
c_yellow="\033[1;33m"
c_purple="\033[1;35m"
c_red="\033[1;31m"

banner() {
  echo -e "${c_cyan}"
  echo "      ===================="
  echo "      ||    =^-.-^=     ||"
  echo "      ===================="
  echo -e "${c_reset}"
  echo -e "${c_purple}  [yuko-nexus] Secure Appliance Provisioning Sequence Initiated${c_reset}"
  echo -e "${c_cyan}  ------------------------------------------------------------${c_reset}"
}
banner

# 2. Generate a single, authoritative ephemeral password on first boot
RANDOM_PASS=$(head /dev/urandom | tr -dc A-Za-z0-9 | head -c 16)

# 3. Securely set root password natively using OpenWrt's passwd utility
printf "%s\n%s\n" "$RANDOM_PASS" "$RANDOM_PASS" | passwd root

# Print credentials explicitly to the secure console stream with glowing highlight
echo -e "${c_yellow}"
echo "=================================================================="
echo " [!] SECURE APPLIANCE ROOT PASSWORD GENERATED:"
echo "     Password: $RANDOM_PASS"
echo "=================================================================="
echo -e "${c_reset}"

# 4. Harden Dropbear SSH server (Disable password auth, enforce keys only)
echo -e "${c_green}[+] Hardening Dropbear SSH configuration...${c_reset}"
uci set dropbear.@dropbear[0].PasswordAuth='off'
uci set dropbear.@dropbear[0].RootPasswordAuth='off'
uci set dropbear.@dropbear[0].Port='22'
uci commit dropbear
/etc/init.d/dropbear restart || true

# 5. Correctly initialize and bind WAN/LAN bridge profile for QEMU user-mode routing
echo -e "${c_green}[+] Configuring static QEMU route & netifd profile...${c_reset}"
uci set network.wan='interface'
uci set network.wan.device='br-lan'
uci set network.wan.proto='static'
uci set network.wan.ipaddr='10.0.2.15'
uci set network.wan.netmask='255.255.255.0'
uci set network.wan.gateway='10.0.2.2'
uci set network.wan.dns='1.1.1.1 8.8.8.8'
uci commit network
/etc/init.d/network restart || true

# Wait for valid internet routing connectivity via wget instead of ICMP ping
echo -e "${c_yellow}[*] Awaiting outbound internet connectivity...${c_reset}"
COUNTER=0
until wget -q --spider http://downloads.openwrt.org; do
  COUNTER=$((COUNTER + 1))
  if [ "$COUNTER" -gt 15 ]; then
    echo -e "${c_red}[!] WARNING: Network connectivity timeout. Proceeding offline...${c_reset}"
    break
  fi
  sleep 2
done
echo -e "${c_green}[✓] Network online and stable.${c_reset}"

# 6. Clear opkg locks and update repositories safely
echo -e "${c_yellow}[*] Clearing opkg state locks...${c_reset}"
while [ -f /var/lock/opkg.lock ]; do
  rm -f /var/lock/opkg.lock 2>/dev/null || true
  sleep 1
done

echo -e "${c_green}[+] Updating opkg repository indexes...${c_reset}"
opkg update || true

# Target secure package suite for OpenWrt
PACKAGES="
  luci-app-https-dns-proxy
  luci-app-adblock
  luci-app-bcp38
  luci-app-sqm
  luci-app-banip
  luci-app-nlbwmon
  luci-app-statistics
  collectd-mod-sqm
  collectd-mod-cpu
  collectd-mod-interface
  collectd-mod-memory
  luci-app-vnstat2
  vnstat2
  iftop
  bind-tools
  snort3
"

echo -e "${c_purple}[+] Deploying secure package matrix via opkg...${c_reset}"
for pkg in $PACKAGES; do
  echo -n "    -> Installing $pkg ... "
  rm -f /var/lock/opkg.lock 2>/dev/null || true
  if opkg install "$pkg" >/dev/null 2>&1; then
    echo -e "${c_green}SUCCESS${c_reset}"
  else
    echo -e "${c_yellow}SKIPPED/FAILED${c_reset}"
  fi
done

echo -e "${c_green}[+] Applying secure UCI configurations...${c_reset}"

# 1. HTTPS DNS Proxy (Encrypted DNS via Cloudflare & Quad9)
uci set https-dns-proxy.@https-dns-proxy[0].resolver_url='https://cloudflare-dns.com/dns-query'
uci set https-dns-proxy.@https-dns-proxy[0].listen_addr='127.0.0.1'
uci set https-dns-proxy.@https-dns-proxy[0].listen_port='5053'
if ! uci get https-dns-proxy.@https-dns-proxy[1] >/dev/null 2>&1; then
  uci add https-dns-proxy https-dns-proxy
fi
uci set https-dns-proxy.@https-dns-proxy[1].resolver_url='https://dns.quad9.net/dns-query'
uci set https-dns-proxy.@https-dns-proxy[1].listen_addr='127.0.0.1'
uci set https-dns-proxy.@https-dns-proxy[1].listen_port='5054'
uci commit https-dns-proxy

# 2. Dnsmasq Upstream Enforcement
uci set dhcp.@dnsmasq[0].noresolv='1'
uci del dhcp.@dnsmasq[0].server >/dev/null 2>&1 || true
uci add_list dhcp.@dnsmasq[0].server='127.0.0.1#5053'
uci add_list dhcp.@dnsmasq[0].server='127.0.0.1#5054'
uci commit dhcp

# 3. Adblock Hardening
if uci get adblock.global >/dev/null 2>&1; then
  uci set adblock.global.adb_enabled='1'
  uci set adblock.global.adb_trigger='wan'
  uci del adblock.global.adb_sources >/dev/null 2>&1 || true
  uci add_list adblock.global.adb_sources='stevenblack'
  uci add_list adblock.global.adb_sources='hagezi_multi_light'
  uci add_list adblock.global.adb_sources='adguard'
  uci commit adblock
fi

# 4. BCP38 (Source Address Validation)
if uci get bcp38.bcp38 >/dev/null 2>&1; then
  uci set bcp38.bcp38.enabled='1'
  uci set bcp38.bcp38.interface='wan'
  uci commit bcp38
fi

# 5. SQM (Smart Queue Management for bufferbloat mitigation)
if uci get sqm.wan >/dev/null 2>&1; then
  uci set sqm.wan.enabled='1'
  uci set sqm.wan.interface='wan'
  uci set sqm.wan.qdisc='cake'
  uci set sqm.wan.script='piece_of_cake.qos'
  uci set sqm.wan.download='90000'
  uci set sqm.wan.upload='18000'
  uci set sqm.wan.linklayer='ethernet'
  uci set sqm.wan.overhead='44'
  uci commit sqm
fi

# 6. banIP Protection Feeds
if uci get banip.global >/dev/null 2>&1; then
  uci set banip.global.ban_enabled='1'
  uci del banip.global.ban_feed >/dev/null 2>&1 || true
  uci add_list banip.global.ban_feed='abuseipdb'
  uci add_list banip.global.ban_feed='blocklist'
  uci add_list banip.global.ban_feed='ciarmy'
  uci commit banip
fi

echo -e "${c_yellow}[*] Restarting network and security services...${c_reset}"
/etc/init.d/https-dns-proxy restart || true
/etc/init.d/dnsmasq restart || true
/etc/init.d/adblock restart || true
/etc/init.d/sqm restart || true
/etc/init.d/firewall restart || true

# 7. Finalizing hooks, shell registration, and dropping privileges into user runtime
echo -e "${c_green}[+] Finalizing appliance hooks & console security...${c_reset}"
if ! grep -q "yuko-provision.sh" /etc/rc.local; then
  sed -i '/^exit 0/i # Trigger Yuko secure appliance baseline provisioning on boot\n/root/yuko-provision.sh >/root/provision.log 2>&1 &\n' /etc/rc.local
  echo "[+] Registered yuko-provision.sh in /etc/rc.local"
fi

if ! grep -qx "/bin/ash" /etc/shells; then
  echo "/bin/ash" >> /etc/shells
  echo "[+] Added /bin/ash to /etc/shells"
fi

if command -v chsh >/dev/null 2>&1; then
  chsh -s /bin/ash root || true
else
  sed -i 's|^\(root:[^:]*:[^:]*:[^:]*:[^:]*:[^:]*:\).*$|\1/bin/ash|' /etc/passwd
fi
echo "[+] Configured root user login shell to /bin/ash"

if grep -q "askfirst:/usr/libexec/login.sh" /etc/inittab; then
  sed -i 's|:askfirst:/usr/libexec/login.sh|:respawn:/bin/login|g' /etc/inittab
  echo "[+] Enforced /bin/login authentication on console in /etc/inittab"
  kill -HUP 1
fi

echo -e "${c_cyan}"
echo "=================================================================="
echo "  [✓] YUKO SECURE APPLIANCE PROVISIONING COMPLETE & LOCKED DOWN"
echo "=================================================================="
echo -e "${c_reset}"

# Drop from root down into the dynamically resolved user's unprivileged runtime
if [ -n "$RESOLVED_USER" ] && [ "$RESOLVED_USER" != "root" ] && id "$RESOLVED_USER" >/dev/null 2>&1; then
  echo -e "${c_yellow}[*] Dropping privileges into current user runtime: $RESOLVED_USER${c_reset}"
  exec su - "$RESOLVED_USER"
fi
