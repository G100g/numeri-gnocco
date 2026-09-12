#!/bin/bash
# Browser a schermo intero sulla pagina TV.
# Pensato per Raspberry Pi Zero 2 W su Raspberry Pi OS Lite (senza desktop).
set -u
URL="${URL:-http://localhost/tv}"

# Il browser deve partire solo quando il server risponde, altrimenti mostra
# una pagina di errore e resta li'.
for _ in $(seq 1 60); do
  curl -fsS -o /dev/null "$URL" && break
  sleep 1
done

# Niente spegnimento schermo ne' cursore lampeggiante sulla TV.
if [ -w /sys/class/graphics/fb0/blank ]; then
  echo 0 > /sys/class/graphics/fb0/blank 2>/dev/null || true
fi
setterm --cursor off >/dev/tty1 2>/dev/null || true

if command -v cog >/dev/null 2>&1 && [ "${USE_CHROMIUM:-0}" != "1" ]; then
  # cog = WPE WebKit, leggerissimo. Su Lite disegna via DRM senza X server;
  # se il plugin DRM non c'e' (o siamo dentro una sessione grafica) usa X11.
  if [ -n "${DISPLAY:-}" ]; then
    exec cog --platform=x11 -F "$URL"
  fi
  # Niente exec qui: se il plugin DRM manca vogliamo poter ripiegare.
  cog --platform=drm "$URL" && exit 0
  echo "kiosk: piattaforma DRM non disponibile, riprovo con quella predefinita" >&2
  exec cog "$URL"
fi

# Ripiego su Chromium (Pi 4, o installazione con desktop).
xset s off; xset -dpms; xset s noblank
PREFS="$HOME/.config/chromium/Default/Preferences"
[ -f "$PREFS" ] && sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS"
exec chromium-browser \
  --kiosk --noerrdialogs --disable-infobars \
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 \
  --autoplay-policy=no-user-gesture-required \
  "$URL"
