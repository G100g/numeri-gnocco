#!/usr/bin/env python3
"""Genera il supporto stampabile per il tablet-tastierino.

Due pezzi:
  corpo    cuneo cavo che tiene il tablet inclinato e contiene il Raspberry Pi.
           Fondo aperto: da sotto si monta il Pi e da sotto/dietro escono i cavi.
  cornice   bezel che entra nella tasca sopra il tablet e lo blocca, con 4
           clip a scatto che agganciano le scanalature nelle pareti della tasca.

Tablet di riferimento: Amazon Fire HD 8 dalla 5a alla 8a generazione
(214 x 128 x 9,7 mm, presa micro-USB), montato in verticale.

Uso:
    pip install manifold3d
    python3 cad/supporto-tablet.py

Scrive cad/supporto-tablet.3mf con entrambi i pezzi gia' orientati per la
stampa. Tutte le quote sono in millimetri e sono parametri qui sotto: per un
altro tablet basta cambiare TAB_L / TAB_W / TAB_T e rigenerare.
"""

import math
import os
import zipfile

from manifold3d import Manifold

# --------------------------------------------------------------------- quote

# Tablet
TAB_L, TAB_W, TAB_T = 214.0, 128.0, 9.7
GIOCO = 0.5            # aria su ogni lato del tablet nella tasca

# Schermo da lasciare libero (8" 16:10 = 172 x 108, arrotondato in eccesso)
FIN_L, FIN_W = 176.0, 111.0

# Inclinazione della faccia rispetto all'orizzontale: 50 gradi e' un buon
# compromesso fra leggibilita' da in piedi e comodita' nel digitare.
INCL = 50.0

# Spessori
PARETE = 3.0           # pareti del guscio
CORNICE_T = 3.0        # spessore della cornice
BORDO = 7.0            # materiale attorno alla tasca, sulla pendenza
FIANCO = 7.0           # parete laterale a fianco della tasca
ALT_FRONTE = 14.0      # altezza del bordo anteriore (il lato basso del cuneo)
TETTO = 16.0           # quota del soffitto della cavita' sotto la pendenza

# Tasca
TASCA_L = TAB_L + 2 * GIOCO
TASCA_W = TAB_W + 2 * GIOCO
TASCA_D = TAB_T + CORNICE_T + 0.3

# Clip della cornice
CLIP_N = 2             # per lato
CLIP_LUN = 16.0        # lunghezza del dente lungo la pendenza
CLIP_SP = 1.8          # spessore del dente (flessibilita')
CLIP_H = 14.0          # sbraccio
CLIP_DENTE = 0.9       # sporgenza del gancio
DENTE_H = 2.2          # altezza del gancio
# Le clip corrono fuori dalla sagoma del tablet, in un canale ricavato nella
# parete della tasca: dentro la sagoma schiaccerebbero il tablet.
CLIP_X = TAB_W / 2 + 0.2
DENTE_Z = -CORNICE_T - CLIP_H + 1.2

# Apertura sul lato alto per prese, tasti e cavo di ricarica del tablet
VARCO_W = 84.0

# Il fondo della tasca e' svuotato: il tablet appoggia su un bordo perimetrale
# e su due nervature. Meno plastica, stampa piu' corta, e il cavo di ricarica
# puo' salire dove serve. Le nervature corrono lungo la pendenza, cosi'
# reggono il bordo alto della finestra durante la stampa.
APPOGGIO = 14.0        # larghezza del bordo su cui posa il tablet
NERV_N = 2
NERV_W = 6.0

# Raspberry Pi Zero 2 W
PI_L, PI_W = 65.0, 30.0
PI_FORI_L, PI_FORI_W = 58.0, 23.0
PI_COL_H = 4.0         # altezza delle colonnine
PI_Z = 58.0            # quota del centro del Pi sulla parete posteriore
# Fasce verticali in cui stanno le feritoie: non devono invadere la zona del
# Pi (z da 43 a 73), altrimenti scalzano le colonnine.
FERITOIE_Z = ((14.0, 38.0), (80.0, 116.0), (126.0, 162.0))

# Derivate
PEND_L = TASCA_L + 2 * BORDO          # lunghezza della faccia inclinata
CORPO_W = TASCA_W + 2 * FIANCO        # larghezza esterna
PROF = PEND_L * math.cos(math.radians(INCL))
ALT = ALT_FRONTE + PEND_L * math.sin(math.radians(INCL))

SIN, COS = math.sin(math.radians(INCL)), math.cos(math.radians(INCL))


# ------------------------------------------------------------------- utility

def cubo(dim, pos=(0.0, 0.0, 0.0)):
    return Manifold.cube(list(dim)).translate(list(pos))


def su_pendenza(m):
    """Porta un solido dalle coordinate della pendenza a quelle del corpo.

    Nel sistema locale: x trasversale (centrato), y lungo la pendenza verso
    l'alto partendo dallo spigolo anteriore, z normale uscente dalla faccia.
    """
    return m.rotate([INCL, 0, 0]).translate([0, 0, ALT_FRONTE])


def cilindro_y(h, r, segmenti=48):
    """Cilindro con asse lungo -y, cioe' verso l'interno dalla parete dietro."""
    return Manifold.cylinder(h, r, r, segmenti).rotate([90, 0, 0])


# --------------------------------------------------------------------- corpo

def corpo():
    # Cuneo: parallelepipedo tagliato dal piano della pendenza.
    grezzo = cubo((CORPO_W, PROF, ALT), (-CORPO_W / 2, 0, 0))
    m = grezzo.trim_by_plane([0, SIN, -COS], -COS * ALT_FRONTE)

    # Cavita' interna, aperta sul fondo: il Pi si monta da sotto.
    cav = cubo((CORPO_W - 2 * PARETE, PROF - 2 * PARETE, ALT),
               (-(CORPO_W / 2 - PARETE), PARETE, 0))
    cav = cav.trim_by_plane([0, SIN, -COS], -COS * ALT_FRONTE + TETTO)
    m -= cav

    # Tasca per tablet + cornice.
    tasca = cubo((TASCA_W, TASCA_L, TASCA_D + 30),
                 (-TASCA_W / 2, BORDO, -TASCA_D))
    m -= su_pendenza(tasca)

    # Varco sul lato alto: prese, tasti e cavo di ricarica del tablet.
    varco = cubo((VARCO_W, BORDO + 2, TASCA_D + 30),
                 (-VARCO_W / 2, BORDO + TASCA_L - 1, -TASCA_D))
    m -= su_pendenza(varco)

    # Finestra nel fondo della tasca, con le nervature rimesse dentro.
    fin_w = TASCA_W - 2 * APPOGGIO
    fin_l = TASCA_L - 2 * APPOGGIO
    z0, z1 = -TASCA_D - PARETE - 2.0, -TASCA_D + 1.0
    m -= su_pendenza(cubo((fin_w, fin_l, z1 - z0),
                          (-fin_w / 2, BORDO + APPOGGIO, z0)))
    luce = (fin_w - NERV_N * NERV_W) / (NERV_N + 1)
    for i in range(NERV_N):
        x = -fin_w / 2 + luce * (i + 1) + NERV_W * i
        m += su_pendenza(cubo((NERV_W, fin_l, PARETE),
                              (x, BORDO + APPOGGIO, -TASCA_D - PARETE)))

    # Canale per il corpo della clip, gola per il gancio, e incavo che lascia
    # sfogare la punta sotto il fondo della tasca.
    can_in = CLIP_X - 0.2
    can_out = CLIP_X + CLIP_SP + 0.2
    gola_in = CLIP_X + CLIP_SP - 0.1
    gola_out = CLIP_X + CLIP_SP + CLIP_DENTE + 0.3
    for iy in range(CLIP_N):
        y = clip_y(iy)
        for sx in (-1, 1):
            def a(x0, x1, dz0, dz1, yy=y, s=sx):
                """Taglio speculare sui due fianchi."""
                x = x0 if s > 0 else -x1
                return cubo((x1 - x0, CLIP_LUN + 1.0, dz1 - dz0),
                            (x, yy - 0.5, dz0))
            m -= su_pendenza(a(can_in, can_out, -CORNICE_T - CLIP_H, 0.5))
            m -= su_pendenza(a(gola_in, gola_out, DENTE_Z - 0.5, DENTE_Z + DENTE_H + 0.5))
            m -= su_pendenza(a(can_in, gola_out, -TASCA_D - 6.0, -TASCA_D + 1.0))

    # Colonnine per il Raspberry Pi sulla faccia interna della parete dietro.
    m += colonnine_pi()
    m -= fori_pi()

    # Feritoie di sfiato, tenute fuori dalla zona occupata dal Pi.
    for fascia_z in FERITOIE_Z:
        for i in range(-2, 3):
            m -= cubo((9.0, PARETE + 2, fascia_z[1] - fascia_z[0]),
                      (i * 16.0 - 4.5, PROF - PARETE - 1, fascia_z[0]))

    return m


def colonnine_pi():
    y_par = PROF - PARETE
    col = None
    for sx in (-1, 1):
        for sz in (-1, 1):
            c = cilindro_y(PI_COL_H, 2.6).translate(
                [sx * PI_FORI_L / 2, y_par, PI_Z + sz * PI_FORI_W / 2])
            col = c if col is None else col + c
    return col


def fori_pi():
    y_par = PROF - PARETE
    fori = None
    for sx in (-1, 1):
        for sz in (-1, 1):
            f = cilindro_y(PI_COL_H + 1.5, 1.1).translate(
                [sx * PI_FORI_L / 2, y_par + 1.5, PI_Z + sz * PI_FORI_W / 2])
            fori = f if fori is None else fori + f
    return fori


def clip_y(i):
    """Posizione lungo la pendenza della i-esima clip (coordinate locali)."""
    passo = TASCA_L / (CLIP_N + 1)
    return BORDO + passo * (i + 1) - CLIP_LUN / 2


# ------------------------------------------------------------------- cornice

def cornice():
    """Costruita nelle coordinate della pendenza: piastra in z da -T a 0."""
    fit = 0.3
    L, W = TASCA_L - fit, TASCA_W - fit

    m = cubo((W, L, CORNICE_T), (-W / 2, BORDO + fit / 2, -CORNICE_T))
    # Finestra sullo schermo.
    m -= cubo((FIN_W, FIN_L, CORNICE_T + 2),
              (-FIN_W / 2, BORDO + (TASCA_L - FIN_L) / 2, -CORNICE_T - 1))
    # Apertura sul lato alto, allineata al varco del corpo.
    m -= cubo((VARCO_W, 40.0, CORNICE_T + 2),
              (-VARCO_W / 2, BORDO + TASCA_L - 22.0, -CORNICE_T - 1))

    # Clip: sbraccio appena fuori dalla sagoma del tablet, gancio verso
    # l'esterno che va a incastrarsi nella gola del corpo.
    for iy in range(CLIP_N):
        y = clip_y(iy)
        for sx in (-1, 1):
            braccio_x = CLIP_X if sx > 0 else -(CLIP_X + CLIP_SP)
            m += cubo((CLIP_SP, CLIP_LUN, CLIP_H + CORNICE_T),
                      (braccio_x, y, -CORNICE_T - CLIP_H))
            dente_x = (CLIP_X + CLIP_SP) if sx > 0 else -(CLIP_X + CLIP_SP + CLIP_DENTE)
            m += cubo((CLIP_DENTE, CLIP_LUN, DENTE_H),
                      (dente_x, y, DENTE_Z))
    return m


# ---------------------------------------------------------------------- 3mf

def scrivi_3mf(percorso, pezzi):
    """pezzi: lista di (nome, Manifold). Le trasformazioni sono gia' applicate."""
    risorse, elementi = [], []
    for idx, (nome, solido) in enumerate(pezzi, start=1):
        mesh = solido.to_mesh()
        vert = mesh.vert_properties[:, :3]
        tri = mesh.tri_verts
        v = "".join('<vertex x="%.4f" y="%.4f" z="%.4f"/>' % tuple(p) for p in vert)
        t = "".join('<triangle v1="%d" v2="%d" v3="%d"/>' % tuple(f) for f in tri)
        risorse.append(
            '<object id="%d" type="model" name="%s"><mesh>'
            '<vertices>%s</vertices><triangles>%s</triangles>'
            '</mesh></object>' % (idx, nome, v, t))
        elementi.append('<item objectid="%d"/>' % idx)

    modello = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="it"'
        ' xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        '<metadata name="Title">Supporto tablet - numeri gnocco</metadata>'
        '<resources>%s</resources><build>%s</build></model>'
        % ("".join(risorse), "".join(elementi)))

    tipi = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels"'
            ' ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="model"'
            ' ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
            '</Types>')

    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0"'
            ' Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
            '</Relationships>')

    with zipfile.ZipFile(percorso, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipi)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", modello)


# ------------------------------------------------------------------ verifiche

def volume_tablet():
    """Il volume che occupa il tablet, in coordinate del corpo."""
    slab = cubo((TAB_W, TAB_L, TAB_T),
                (-TAB_W / 2, BORDO + GIOCO, -TASCA_D + 0.0))
    return su_pendenza(slab)


def verifica(corpo_m, cornice_m):
    ok = True
    tab = volume_tablet()

    def dimmi(etichetta, valore, atteso):
        nonlocal ok
        buono = valore <= atteso
        ok = ok and buono
        print("   %-46s %9.2f mm3   %s" % (etichetta, valore, "ok" if buono else "DA RIVEDERE"))

    print("\n-- montaggio --")
    dimmi("tablet contro corpo (deve stare nella tasca)", (tab ^ corpo_m).volume(), 1.0)
    dimmi("tablet contro cornice (non deve schiacciarlo)", (tab ^ cornice_m).volume(), 1.0)
    dimmi("cornice contro corpo (le gole hanno gioco)",
          (cornice_m ^ corpo_m).volume(), 1.0)
    print("   %-46s %9.2f mm     %s"
          % ("presa del gancio nella gola", CLIP_DENTE,
             "ok" if CLIP_DENTE >= 0.6 else "TROPPO POCO"))

    attese = colonnine_pi() - fori_pi()
    mancante = (attese - corpo_m).volume()
    dimmi("colonnine del Pi integre (niente mangiato via)", mancante, 1.0)

    luce = (TASCA_W - 2 * APPOGGIO - NERV_N * NERV_W) / (NERV_N + 1)
    print("   %-46s %9.2f mm     %s"
          % ("luce fra gli appoggi (ponte in stampa)", luce,
             "ok" if luce <= 45 else "TROPPO LARGA"))

    print("\n-- solidi --")
    for nome, m in (("corpo", corpo_m), ("cornice", cornice_m)):
        x0, y0, z0, x1, y1, z1 = m.bounding_box()
        print("   %-10s %6.1f x %6.1f x %6.1f mm   volume %8.1f cm3   genere %d"
              % (nome, x1 - x0, y1 - y0, z1 - z0, m.volume() / 1000.0, m.genus()))
    return ok


# ---------------------------------------------------------------------- main

def main():
    qui = os.path.dirname(os.path.abspath(__file__))
    c = corpo()
    f_assieme = su_pendenza(cornice())          # in posizione, per le verifiche
    buono = verifica(c, f_assieme)

    # Cornice posata sul piano: capovolta, con le clip verso l'alto.
    f_stampa = cornice().rotate([180, 0, 0])
    x0, y0, z0, x1, y1, z1 = f_stampa.bounding_box()
    f_stampa = f_stampa.translate([0, -y0, -z0])
    f_stampa = f_stampa.translate([CORPO_W / 2 + (x1 - x0) / 2 + 12, 0, 0])

    uscita = os.path.join(qui, "supporto-tablet.3mf")
    scrivi_3mf(uscita, [("corpo", c), ("cornice", f_stampa)])
    print("\nScritto %s (%.1f kB)" % (uscita, os.path.getsize(uscita) / 1024.0))
    print("Inclinazione %g gradi. Ingombro corpo %.0f x %.0f x %.0f mm."
          % (INCL, CORPO_W, PROF, ALT))
    if not buono:
        raise SystemExit("Le verifiche di montaggio non passano.")


if __name__ == "__main__":
    main()
