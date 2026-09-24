#!/bin/bash
# Browser a schermo intero sulla pagina TV.
# Pensato per Raspberry Pi Zero 2 W su Raspberry Pi OS Lite (senza desktop).
set -u
URL="${URL:-http://localhost/tv}"
# Renderer DRM di cog: "gles" o "modeset". Sul Pi 4 (vc4) "modeset" non riesce
# ad allocare il framebuffer ("failed to create framebuffer"), quindi gles.
COG_RENDERER="${COG_RENDERER:-gles}"
# Senza questo l'audio degli elementi <audio> resta bloccato: sulla TV non
# arriva mai un gesto dell'utente.
COG_OPTS=(--media-playback-requires-user-gesture=false)

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
    exec cog --platform=x11 "${COG_OPTS[@]}" -F "$URL"
  fi
  # Niente exec qui: se il plugin DRM manca vogliamo poter ripiegare.
  cog --platform=drm --platform-params="renderer=$COG_RENDERER" \
      "${COG_OPTS[@]}" "$URL" && exit 0
  echo "kiosk: piattaforma DRM non disponibile, riprovo con quella predefinita" >&2
  exec cog "${COG_OPTS[@]}" "$URL"
fi

# Ripiego su Chromium (Pi 4, o installazione con desktop).
# Il pacchetto si chiama "chromium" su Trixie, "chromium-browser" su Bookworm.
CHROMIUM="$(command -v chromium || command -v chromium-browser || true)"
if [ -z "$CHROMIUM" ]; then
  echo "kiosk: nessun browser trovato (installa cog oppure chromium)" >&2
  exit 1
fi

CHROMIUM_OPTS=(
  --kiosk --noerrdialogs --disable-infobars
  --disable-session-crashed-bubble
  --check-for-update-interval=31536000
  --autoplay-policy=no-user-gesture-required
  # Niente proposta di tradurre la pagina, niente schermate di benvenuto:
  # sulla TV nessuno puo' chiuderle.
  --lang=it-IT
  --disable-features=Translate,TranslateUI
  --disable-translate-new-ux
  --no-first-run --no-default-browser-check
  --disable-search-engine-choice-screen
  --disable-component-update
  --password-store=basic
)

# Chromium ricorda il crash del riavvio precedente e mostra una barra gialla.
PREFS="$HOME/.config/chromium/Default/Preferences"
[ -f "$PREFS" ] && sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS"

if [ -n "${DISPLAY:-}" ]; then
  xset s off; xset -dpms; xset s noblank
  exec "$CHROMIUM" "${CHROMIUM_OPTS[@]}" "$URL"
fi

# Senza sessione grafica (Raspberry Pi OS Lite) Chromium non ha nessuno schermo
# su cui disegnare. cage e' un compositore Wayland minimo: una finestra sola,
# a tutto schermo, niente desktop intorno.
if command -v cage >/dev/null 2>&1; then
  exec cage -- "$CHROMIUM" "${CHROMIUM_OPTS[@]}" --ozone-platform=wayland "$URL"
fi

echo "kiosk: senza desktop Chromium ha bisogno di cage (sudo apt install cage)" >&2
exit 1
