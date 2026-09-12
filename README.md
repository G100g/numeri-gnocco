# Numeri Gnocco

Display dei numeri d'ordine per il ritiro bevande.

- **TV** collegata al Raspberry Pi: mostra a schermo intero il numero appena
  pronto, la lista di quelli da ritirare e quella degli ordini in preparazione.
- **Smartphone**: pagina web con tastierino per inserire gli ordini,
  segnarli pronti e toglierli quando vengono ritirati.

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
    state.json             lista corrente (creato al primo avvio)
    cad/                   supporto stampabile in 3D per il tablet
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

Altri modelli: un Pi 3/4/5 fa girare Chromium senza problemi, e
`install/kiosk.sh` ripiega da solo su Chromium se `cog` non e' installato
(oppure forzalo con `USE_CHROMIUM=1`). Il Pi Zero senza "W" non ha il WiFi e non
e' utilizzabile.

## Installazione sul Raspberry Pi

Parti da **Raspberry Pi OS Lite (Bookworm)**. In Raspberry Pi Imager, nelle
impostazioni, abilita SSH e imposta l'utente: servono per entrare nel Pi prima
che ci sia l'access point.

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

### Comandi utili

    systemctl status numeri-gnocco           # stato del server
    journalctl -u numeri-gnocco-kiosk -f     # log del browser sulla TV
    systemctl restart numeri-gnocco-kiosk    # ricarica la pagina sulla TV

### Installazione manuale

Se preferisci fare i passi a mano, o sei su Raspberry Pi OS Bullseye (che usa
`dhcpcd` invece di NetworkManager, quindi richiede `hostapd` + `dnsmasq`), i
file di configurazione sono tutti in `install/` e lo script `setup-pi.sh` e'
leggibile come traccia dei comandi.

## Uso

Ogni ordine attraversa due stati.

**1. Alla cassa** — digita il numero e premi **AGGIUNGI IN CODA**.
Finisce tra gli ordini *in preparazione*: compare sulla TV in basso a destra,
in grigio e piu' piccolo. Nessun suono: il cliente vede che l'ordine e' preso
in carico, ma non deve ancora muoversi.

**2. Al banco, quando la bevanda e' pronta** — tocca il numero nella lista
*In preparazione* e scegli **È PRONTO**. Il numero passa tra quelli da
ritirare: appare in verde nella zona grande, e il piu' recente riempie il
pannello giallo a sinistra, con lampeggio e segnale acustico.

**3. Quando il cliente ritira** — tocca il numero tra i *Pronti* e scegli
**RITIRATO**. Sparisce dal display.

Toccando un numero non succede mai niente senza una seconda conferma: il tap
apre solo un menu.

### Correzioni

- **Numero sbagliato passato a pronto**: toccalo tra i pronti e scegli
  *Torna in preparazione*.
- **Ordine annullato**: toccalo e scegli *Cancella ordine*, poi conferma.
  E' l'unica azione che chiede una conferma in piu', perche' butta via
  l'ordine invece di farlo avanzare.
- **Fine serata**: il tasto **Svuota** azzera tutto, sempre con conferma.

Piu' telefoni possono comandare lo stesso display (per esempio uno alla cassa e
uno al banco): tutte le pagine restano allineate in tempo reale.

## Note operative

- Lo stato sopravvive al riavvio: e' salvato in `state.json`.
- Se cade la rete, TV e telefono si riconnettono da soli e mostrano un avviso
  rosso finche' sono scollegati.
- Il primo suono sulla TV potrebbe non partire finche' non si tocca/clicca la
  pagina una volta: e' la policy autoplay di Chromium. Lo script kiosk passa
  gia' `--autoplay-policy=no-user-gesture-required` per evitarlo.
- Numeri ammessi: da 1 a 9999. Un numero gia' in corso viene rifiutato con un
  avviso, in qualunque dei due stati si trovi.
- Qualsiasi indirizzo digitato sul telefono finisce sul tastierino: il server
  risponde con un redirect a `/pad` a ogni URL sconosciuto. E' anche il
  meccanismo che fa comparire la notifica "accedi alla rete".
- In locale il server usa la porta 8080; sul Pi il servizio systemd la porta 80.
  Cambiala con la variabile d'ambiente `PORT`.
