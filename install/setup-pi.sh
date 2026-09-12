#!/bin/bash
# Installazione completa su Raspberry Pi Zero 2 W (Raspberry Pi OS Lite, Bookworm).
# Rieseguibile senza danni: si puo' rilanciare per cambiare la password.
set -euo pipefail

SSID="${SSID:-GNOCCO}"
WIFI_PASS="${WIFI_PASS:-}"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_USER="${SUDO_USER:-pi}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Rilancia con sudo:  sudo ./install/setup-pi.sh" >&2
  exit 1
fi

if [ -z "$WIFI_PASS" ]; then
  echo "Imposta la password del WiFi (almeno 8 caratteri):" >&2
  echo "  sudo WIFI_PASS='latuapassword' ./install/setup-pi.sh" >&2
  exit 1
fi
if [ "${#WIFI_PASS}" -lt 8 ]; then
  echo "La password deve avere almeno 8 caratteri." >&2
  exit 1
fi

echo "==> Applicazione in: $APP_DIR (utente: $APP_USER)"

echo "==> Installazione browser leggero"
apt-get update -qq
apt-get install -y cog curl

echo "==> Servizio applicazione"
sed -e "s|/home/pi/numeri-gnocco|$APP_DIR|g" \
    -e "s|^User=pi|User=$APP_USER|" \
    "$APP_DIR/install/numeri-gnocco.service" > /etc/systemd/system/numeri-gnocco.service

echo "==> Servizio browser"
sed -e "s|/home/pi/numeri-gnocco|$APP_DIR|g" \
    -e "s|^User=pi|User=$APP_USER|" \
    -e "s|HOME=/home/pi|HOME=/home/$APP_USER|" \
    -e "s|XDG_RUNTIME_DIR=/run/user/1000|XDG_RUNTIME_DIR=/run/user/$(id -u "$APP_USER")|" \
    "$APP_DIR/install/numeri-gnocco-kiosk.service" > /etc/systemd/system/numeri-gnocco-kiosk.service

echo "==> Access point $SSID"
nmcli connection delete Hotspot >/dev/null 2>&1 || true
nmcli device wifi hotspot ifname wlan0 con-name Hotspot ssid "$SSID" password "$WIFI_PASS"
nmcli connection modify Hotspot \
  connection.autoconnect yes \
  connection.autoconnect-priority 100 \
  802-11-wireless.band bg          # lo Zero 2 W e' solo 2.4 GHz

echo "==> DNS jolly (captive portal + nome http://gnocco)"
mkdir -p /etc/NetworkManager/dnsmasq-shared.d
cat > /etc/NetworkManager/dnsmasq-shared.d/gnocco.conf <<'DNS'
address=/#/10.42.0.1
DNS

echo "==> Avvio servizi"
systemctl daemon-reload
systemctl enable numeri-gnocco numeri-gnocco-kiosk
systemctl restart numeri-gnocco
systemctl restart NetworkManager
sleep 2
systemctl restart numeri-gnocco-kiosk

cat <<FINE

============================================================
  Fatto.

  Dal telefono:  rete WiFi "$SSID"
                 poi tap sulla notifica "Accedi alla rete"
                 oppure apri  http://gnocco

  ATTENZIONE: questa rete non ha internet. Alla prima
  connessione Android chiede se restare collegato:
  rispondi "Mantieni la connessione", altrimenti torna
  ai dati mobili e il tastierino non raggiunge il Pi.

  Stato:   systemctl status numeri-gnocco
  Log TV:  journalctl -u numeri-gnocco-kiosk -f
============================================================
FINE
