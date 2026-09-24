# Numeri Gnocco

Display dei numeri d'ordine per il ritiro bevande.

- **TV** collegata al Raspberry Pi: mostra a schermo intero tutti i numeri
  esposti, uno di fianco all'altro, il piu' grossi possibile.
- **Smartphone**: pagina web con tastierino per inserire i numeri e toglierli
  quando vengono ritirati.

Tutto passa dal WiFi. Niente Bluetooth, niente app da installare, niente internet.

## Perche' WiFi e non Bluetooth

Web Bluetooth su Chrome funziona solo in *secure context* (HTTPS o localhost):
servendo la pagina dal Pi su `http://192.168.4.1` l'API risulta disabilitata.
In piu' il Pi dovrebbe fare da periferica BLE GATT, cosa fragile e lenta a
riconnettersi. Con il Pi come access point il telefono si collega alla rete,
apre una pagina e funziona, anche in piu' persone contemporaneamente.

## Struttura

    server.py              server HTTP + stream SSE (solo standard library)
    static/tv.html         pagina per la TV
    static/pad.html        pagina per lo smartphone
    static/ding.wav        campanello di cassa, generato da tools/make-ding.py
    state.json             numeri esposti (creato al primo avvio)
    cad/                   supporto stampabile in 3D per il tablet
    tools/make-ding.py     risintetizza static/ding.wav
    install/setup-pi.sh    installazione automatica sul Raspberry Pi
    install/               unit systemd, script kiosk, configurazione access point

## Prova in locale

    python3 server.py

Poi apri `http://localhost:8080/tv` e `http://localhost:8080/pad` in due finestre.

## Hardware

Configurazione di riferimento: **Raspberry Pi Zero 2 W** con **Raspberry Pi OS
Lite** (senza desktop), piu' un adattatore da mini-HDMI a HDMI per la TV.

Lo Zero 2 W ha 512 MB di RAM: un desktop completo con Chromium ci sta stretto e
va in swap. Per questo il kiosk usa `cog` (WPE WebKit), che disegna direttamente
sullo schermo via DRM senza X server. Sotto i 100 MB di RAM in esercizio.

Altri modelli: un Pi 3/4/5 va benissimo, con `cog` o con Chromium
(`USE_CHROMIUM=1`). Vedi *Note per il Raspberry Pi 4* piu' sotto: ha due porte
HDMI e un renderer DRM diverso, quindi qualche dettaglio cambia. Il Pi Zero
senza "W" non ha il WiFi e non e' utilizzabile.

## Installazione sul Raspberry Pi

Parti da **Raspberry Pi OS Lite (Trixie)**, la versione corrente. Va bene anche
Bookworm, ormai indicata come *legacy* nell'Imager: il setup e' identico sulle
due, perche' entrambe usano NetworkManager e il server e' sola standard library.
In Raspberry Pi Imager, nelle impostazioni, abilita SSH e imposta l'utente:
servono per entrare nel Pi prima che ci sia l'access point.

Copia la cartella sul Pi (per esempio in `/home/pi/numeri-gnocco`) e lancia:

    sudo WIFI_PASS='latuapassword' ./install/setup-pi.sh

Lo script installa `cog`, registra i due servizi systemd, crea l'access point
`GNOCCO` e configura il DNS jolly. Si puo' rilanciare quando vuoi, per esempio
per cambiare la password.

Al riavvio il Pi accende da solo la rete WiFi, il server e la pagina sulla TV.

### Collegare il telefono

Rete `GNOCCO` -> parte la notifica **"Accedi alla rete"** -> un tap e si apre il
tastierino. In alternativa `http://gnocco` a mano nel browser.

> **Importante.** Questa rete non ha internet, e Android per impostazione
> predefinita torna ai dati mobili quando se ne accorge, scollegandosi dal Pi.
> Alla prima connessione compare "La rete non ha accesso a Internet": scegli
> **"Mantieni la connessione"**. E' la cosa che fa perdere piu' tempo sul posto,
> falla con calma la prima volta su ogni telefono che userete.

### Entrare in SSH dopo l'installazione

Una volta attivo l'access point, `wlan0` fa da hotspot e non e' piu' collegato
alla rete di casa. Per entrare nel Pi:

    # collegati al WiFi GNOCCO, poi:
    ssh pi@10.42.0.1

Serve un canale con internet (aggiornamenti, `git pull`)? Lo Zero 2 W non ha la
porta ethernet, quindi o spegni l'hotspot per un momento:

    sudo nmcli con down Hotspot
    sudo nmcli dev wifi connect "MiaReteCasa" password "..."
    sudo nmcli con up Hotspot          # oppure riavvia: l'hotspot ritorna da solo

oppure aggiungi una seconda interfaccia sulla porta USB dati (adattatore
USB-ethernet o chiavetta WiFi): cosi' l'access point resta acceso e hai SSH
nello stesso momento.

### Note per il Raspberry Pi 4

**HDMI.** Usa **HDMI0**, la porta micro-HDMI piu' vicina all'alimentazione
USB-C: HDMI1 da sola spesso non da' segnale. Se accendi la TV dopo il Pi
l'uscita puo' restare spenta; in quel caso metti `hdmi_force_hotplug=1` in
`/boot/firmware/config.txt`.

**Renderer.** Sul vc4 del Pi 4 il renderer DRM predefinito di `cog` non riesce
ad allocare il framebuffer (`failed to create framebuffer: Invalid argument`) e
lo schermo resta nero. `install/kiosk.sh` usa quindi `renderer=gles`; sullo
Zero 2 W, se dovesse servire, si torna indietro con `COG_RENDERER=modeset`.

**SSH sempre disponibile.** A differenza dello Zero 2 W, il Pi 4 ha la porta
ethernet: collega il cavo e resti raggiungibile in SSH (con internet) anche con
l'access point acceso su `wlan0`. Niente `nmcli con down Hotspot`.

**Chromium.** `cog` non fa partire l'audio da solo: il flag
`--media-playback-requires-user-gesture=false` copre gli elementi media, ma
WebKit decide l'autoplay dell'audio a un livello che `cog` non espone, quindi
sulla TV resta l'avviso "tocca lo schermo" finche' non premi un tasto. Su
Chromium `--autoplay-policy=no-user-gesture-required` funziona, ed e' il motivo
per cui sul Pi 4 conviene Chromium. Su Raspberry Pi OS Lite non c'e' un server
grafico, quindi serve un compositore: `install/kiosk.sh` usa `cage`, e `cage` ha
bisogno di `seatd` per accedere a schermo e input (il servizio gira su tty1,
quindi il kiosk non si prova da SSH). Ci pensa il setup:

    sudo USE_CHROMIUM=1 WIFI_PASS='latuapassword' ./install/setup-pi.sh

Installa `chromium`, `cage` e `seatd`, fa partire `seatd` con `-g video` (il suo
socket e' riservato a root, e il gruppo dedicato non esiste su Debian) e aggiunge
`Environment=USE_CHROMIUM=1` al servizio del kiosk.

### Comandi utili

    systemctl status numeri-gnocco           # stato del server
    journalctl -u numeri-gnocco-kiosk -f     # log del browser sulla TV
    systemctl restart numeri-gnocco-kiosk    # ricarica la pagina sulla TV

### Installazione manuale

Se preferisci fare i passi a mano, o sei su una Raspberry Pi OS piu' vecchia di
Bookworm (Bullseye usa `dhcpcd` invece di NetworkManager, quindi richiede
`hostapd` + `dnsmasq`), i file di configurazione sono tutti in `install/` e lo
script `setup-pi.sh` e' leggibile come traccia dei comandi.

## Uso

Un numero c'e' o non c'e': niente stati intermedi.

**1. Quando l'ordine e' pronto** — digita il numero e premi **AGGIUNGI**.
Compare subito sulla TV, con lampeggio e segnale acustico.

**2. Quando il cliente ritira** — tocca il numero nella lista e scegli
**TOGLI DAL TABELLONE**. Sparisce dal display.

In giallo c'e' sempre l'ultimo numero inserito fra quelli ancora esposti: se lo
togli, il giallo passa da solo a quello inserito prima. Il suono invece si sente
solo ai nuovi inserimenti.

Toccando un numero non succede mai niente senza una seconda conferma: il tap
apre solo un menu.

A fine serata il tasto **Svuota** azzera tutto, sempre con conferma.

Piu' telefoni possono comandare lo stesso display (per esempio uno alla cassa e
uno al banco): tutte le pagine restano allineate in tempo reale.

## Note operative

- Lo stato sopravvive al riavvio: e' salvato in `state.json`.
- Se cade la rete, TV e telefono si riconnettono da soli e mostrano un avviso
  rosso finche' sono scollegati.
- Il suono di cassa e' un file, `static/ding.wav`, riprodotto con un elemento
  `<audio>`. La sintesi (colpo di cassetto piu' due "deng" con parziali
  inarmoniche) sta in `tools/make-ding.py`: per cambiare il suono si modificano
  i parametri la' e si rilancia lo script. Prima era sintetizzato nella pagina
  con le Web Audio API, ma un `AudioContext` dal vivo resta sospeso finche' non
  arriva un gesto dell'utente, e la TV nessuno la tocca.
- Lo script kiosk passa i flag che sbloccano l'audio degli elementi media
  (`--media-playback-requires-user-gesture=false` per `cog`,
  `--autoplay-policy=no-user-gesture-required` per Chromium). Se manca uno dei
  due, la TV mostra in basso a sinistra **"tocca lo schermo o premi un tasto per
  attivare il suono"** e al primo tocco suona una volta per conferma.
- Il suono passa da GStreamer: senza `gstreamer1.0-alsa` e
  `gstreamer1.0-plugins-good` WebKit non trova un sink audio
  (`GStreamer element autoaudiosink not found`) e non si sente niente.
  `setup-pi.sh` li installa.
- Numeri ammessi: da 1 a 9999. Un numero gia' sul tabellone viene rifiutato con
  un avviso.
- La TV dispone i numeri da sola: piu' sono, piu' rimpiccioliscono, ma sempre
  nella disposizione che li rende i piu' grossi possibile sullo schermo.
- Qualsiasi indirizzo digitato sul telefono finisce sul tastierino: il server
  risponde con un redirect a `/pad` a ogni URL sconosciuto. E' anche il
  meccanismo che fa comparire la notifica "accedi alla rete".
- In locale il server usa la porta 8080; sul Pi il servizio systemd la porta 80.
  Cambiala con la variabile d'ambiente `PORT`.
