#!/usr/bin/env python3
"""Display numeri ordini - server.

Un ordine ha un solo stato: e' esposto sulla TV finche' qualcuno non lo toglie.

Espone:
  GET  /tv          pagina a schermo intero per la TV
  GET  /pad         pagina di controllo per lo smartphone
  GET  /events      stream SSE con lo stato corrente
  POST /api/add     {"number": 42}   -> compare sulla TV, in giallo
  POST /api/remove  {"number": 42}   -> ritirato, via dal display
  POST /api/clear   {}
  GET  <altro>      redirect a /pad (captive portal)

Solo standard library: gira su qualsiasi Raspberry Pi OS senza pip install.
"""

import json
import os
import queue
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
STATE_FILE = os.path.join(HERE, "state.json")

PORT = int(os.environ.get("PORT", "8080"))
MAX_NUMBER = 9999
HEARTBEAT_SECONDS = 15


class State:
    """Numeri esposti, persistiti su disco, in ordine di inserimento."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.numbers = []
        self.adds = 0               # quanti inserimenti: fa suonare la TV
        self.version = 0
        self.subscribers = []
        self._load()

    # ------------------------------------------------------------ persistenza

    def _load(self):
        try:
            with open(self.path) as fh:
                data = json.load(fh)
            raw = data.get("numbers")
            if raw is None:
                # File scritto dalla versione con "in preparazione"/"pronto":
                # i due stati collassano in una lista sola.
                raw = [item["n"] for item in data.get("orders", [])]
            numbers = []
            for item in raw:
                n = int(item)
                if n not in numbers:
                    numbers.append(n)
            self.numbers = numbers
        except (OSError, ValueError, TypeError, KeyError):
            self.numbers = []

    def _save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w") as fh:
                json.dump({"numbers": self.numbers}, fh)
            os.replace(tmp, self.path)
        except OSError:
            pass  # un disco pieno non deve fermare il servizio

    # ------------------------------------------------------------------ stato

    def snapshot(self):
        # `numbers` e' in ordine di inserimento: l'ultimo e' quello da
        # evidenziare, e togliendolo il giallo torna da solo al precedente.
        return {
            "numbers": list(self.numbers),
            "highlight": self.numbers[-1] if self.numbers else None,
            "adds": self.adds,
            "version": self.version,
        }

    def add(self, number):
        with self.lock:
            if number in self.numbers:
                return False, "gia_presente"
            self.numbers.append(number)
            self.adds += 1
            self._commit()
        return True, None

    def remove(self, number):
        with self.lock:
            if number not in self.numbers:
                return False, "non_trovato"
            self.numbers.remove(number)
            self._commit()
        return True, None

    def clear(self):
        with self.lock:
            self.numbers = []
            self._commit()
        return True, None

    # -------------------------------------------------------------- broadcast

    def _commit(self):
        """Da chiamare con il lock gia' acquisito."""
        self.version += 1
        self._save()
        payload = self.snapshot()
        for q in list(self.subscribers):
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass

    def subscribe(self):
        q = queue.Queue(maxsize=32)
        with self.lock:
            self.subscribers.append(q)
            q.put_nowait(self.snapshot())
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)


STATE = State(STATE_FILE)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "NumeriGnocco/1.0"

    def log_message(self, fmt, *args):
        if self.path != "/events":
            super().log_message(fmt, *args)

    # ---------------------------------------------------------------- helpers

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, name, content_type):
        try:
            with open(os.path.join(STATIC, name), "rb") as fh:
                body = fh.read()
        except OSError:
            self._send_json({"error": "not_found"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return {}
        if length <= 0 or length > 4096:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except (ValueError, UnicodeDecodeError):
            return {}

    def _parse_number(self, data):
        """Restituisce (numero, errore)."""
        try:
            number = int(data.get("number"))
        except (TypeError, ValueError):
            return None, "numero_non_valido"
        if not 0 < number <= MAX_NUMBER:
            return None, "fuori_intervallo"
        return number, None

    def _reply(self, ok, err):
        self._send_json({"ok": ok, "error": err, "state": STATE.snapshot()})

    # -------------------------------------------------------------- endpoints

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/pad", "/pad.html"):
            self._send_file("pad.html", "text/html; charset=utf-8")
        elif path in ("/tv", "/tv.html"):
            self._send_file("tv.html", "text/html; charset=utf-8")
        elif path == "/ding.wav":
            self._send_file("ding.wav", "audio/wav")
        elif path == "/events":
            self._stream_events()
        elif path == "/api/state":
            self._send_json(STATE.snapshot())
        elif path.startswith("/api/"):
            self._send_json({"error": "not_found"}, 404)
        else:
            # Captive portal: Android, iOS e Windows chiamano un URL di prova per
            # capire se la rete ha internet. Rispondendo con un redirect invece
            # che con il 204 atteso, il telefono mostra la notifica "accedi alla
            # rete": un tap e si apre il tastierino, senza digitare indirizzi.
            self._redirect("/pad")

    def do_POST(self):
        path = self.path.split("?")[0]
        data = self._read_json()

        if path == "/api/clear":
            STATE.clear()
            self._reply(True, None)
            return

        if path not in ("/api/add", "/api/remove"):
            self._send_json({"error": "not_found"}, 404)
            return

        number, err = self._parse_number(data)
        if err:
            self._send_json({"ok": False, "error": err}, 400)
            return

        if path == "/api/add":
            ok, err = STATE.add(number)
        else:
            ok, err = STATE.remove(number)
        self._reply(ok, err)

    def _stream_events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        q = STATE.subscribe()
        try:
            while True:
                try:
                    payload = q.get(timeout=HEARTBEAT_SECONDS)
                    chunk = "data: %s\n\n" % json.dumps(payload)
                except queue.Empty:
                    chunk = ": ping\n\n"   # tiene viva la connessione
                self.wfile.write(chunk.encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            STATE.unsubscribe(q)


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    print("Numeri Gnocco in ascolto sulla porta %d" % PORT)
    print("  TV      -> http://localhost:%d/tv" % PORT)
    print("  Comando -> http://<ip-del-pi>:%d/pad" % PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto.")
        server.shutdown()


if __name__ == "__main__":
    main()
