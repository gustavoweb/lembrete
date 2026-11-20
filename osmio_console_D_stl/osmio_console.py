"""
Ósmio Console · Conceito D (Cyberpunk neon) — case paramétrico
ESP32-C3 SuperMini + OLED 0.96" I2C + TP4056 USB-C + LiPo 701520
+ 3 botões táteis 6x6 + chave deslizante + pastilha piezo.

Gera os STLs prontos para fatiar:
  frente.stl          -> imprimir com a FACE na mesa
  traseira.stl        -> imprimir com as COSTAS na mesa
  suporte_botoes.stl  -> plano na mesa
  botao_esquerda.stl, botao_direita.stl, botao_a.stl -> aba (flange) na mesa

Uso:  python3 osmio_console.py   (precisa: pip install manifold3d trimesh matplotlib)

Coordenadas: vista de frente, x para a direita, y para cima, em mm.
"d" = profundidade a partir da face frontal (0 = face, cresce para dentro).
Todos os detalhes para pintar com canetinha são SULCOS de 0,6 mm na face
(imprimem perfeitos com a face na mesa e protegem a tinta do atrito).
"""
import math
from manifold3d import Manifold, CrossSection, FillRule, JoinType
import trimesh
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties

# ------------------------------------------------------------------ medidas
W, H = 46.0, 72.0          # contorno externo (vista frontal)
WALL = 1.8                 # parede lateral
FACE = 1.6                 # espessura da face frontal
BACK = 1.8                 # espessura do fundo
D = 18.3                   # espessura total
SPLIT = 9.5                # onde frente e traseira se encontram (d)
ENGR = 0.6                 # profundidade dos sulcos para pintar
GROOVE = 1.2               # largura dos sulcos (ponta de canetinha)
FIT = 0.25                 # folga por lado em furos de encaixe

# Tela OLED 0.96" (módulo azul/amarelo). MEÇA O SEU com paquímetro.
OLED_W, OLED_H = 27.6, 28.2       # placa do módulo + folga
OLED_C = (22.0, 51.5)             # centro do módulo
OLED_STACK = 2.9                  # vidro + fita + placa
WIN_W, WIN_H = 24.0, 13.0         # janela visível (área ativa 21,7 x 10,9)
WIN_DY = 1.0                      # deslocamento da área ativa em relação ao centro

# ESP32-C3 SuperMini (22,5 x 18), USB-C saindo pelo topo
ESP_X0, ESP_X1 = 13.0, 31.0
ESP_Y0 = 46.9                     # borda inferior da placa
ESP_PCB_D = 6.5                   # frente da placa (lado sem componentes)
USB_W, USB_T = 9.6, 4.0           # abertura para o plugue USB-C

# TP4056 USB-C (28 x 17,5), USB-C saindo por baixo
TP_X0, TP_X1 = 2.2, 19.7
TP_Y0, TP_Y1 = 2.4, 30.4
TP_PCB_D = 9.4

# Bateria 701520 (7 x 15 x 20)
BAT = (21.6, 6.0, 15.0, 20.0)     # x, y, largura, altura

# Botões táteis 6x6 (altura total SW_H até o topo do pino)
SW_H = 5.0
BTN_L, BTN_R, BTN_A = (9.0, 17.0), (20.5, 17.0), (36.0, 19.0)
DPAD = 8.0                        # lado do botão direcional
A_ACROSS = 11.0                   # largura do octógono do A
CAP_OUT = 1.4                     # quanto o botão sobressai da face
FLANGE = 1.0                      # aba de retenção
FLANGE_T = 1.3

# Chave deslizante mini (SS12D00), parede direita
SWITCH_Y = (38.0, 46.6)
SWITCH_D = 12.0

# Pastilha piezo (buzzer passivo de disco) colada no fundo
PIEZO_C, PIEZO_D = (22.0, 57.5), 15.0

# Parafusos M2 x 12
BOSSES = [(5.5, 67.0), (39.5, 61.0), (41.0, 13.0), (5.0, 34.0)]
BOSS_R = 2.6

SEG = 48


def z(d):
    """profundidade a partir da face -> altura z (fundo na mesa, z=0)."""
    return D - d


def slab(cs, d0, d1):
    """extruda uma seção 2D entre as profundidades d0 < d1."""
    return cs.extrude(d1 - d0).translate((0, 0, z(d1)))


def box(x0, y0, x1, y1, d0, d1):
    return slab(CrossSection.square((x1 - x0, y1 - y0)).translate((x0, y0)), d0, d1)


def cyl(cx, cy, r, d0, d1):
    return slab(CrossSection.circle(r, SEG).translate((cx, cy)), d0, d1)


def poly(pts):
    return CrossSection([pts], FillRule.EvenOdd)


def chamfer_rect(cx, cy, w, h, c):
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
    return poly([(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c),
                 (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c)])


def dpad_shape(cx, cy, s, grow=0.0):
    """quadrado com o canto inferior direito cortado (como no conceito)."""
    h = s / 2 + grow
    c = s * 0.3 + grow * 0.4
    return poly([(cx - h, cy - h), (cx + h - c, cy - h), (cx + h, cy - h + c),
                 (cx + h, cy + h), (cx - h, cy + h)])


def octagon(cx, cy, across, grow=0.0):
    r = (across / 2 + grow) / math.cos(math.pi / 8)
    return poly([(cx + r * math.cos(math.pi / 8 + k * math.pi / 4),
                  cy + r * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)])


def ring(cs, inner, outer):
    return cs.offset(outer, JoinType.Miter) - cs.offset(inner, JoinType.Miter)


def line(p0, p1, w=GROOVE):
    """sulco reto com pontas arredondadas."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    a = math.degrees(math.atan2(y1 - y0, x1 - x0))
    bar = CrossSection.square((L, w)).translate((0, -w / 2)).rotate(a).translate((x0, y0))
    return bar + CrossSection.circle(w / 2, 16).translate((x0, y0)) \
               + CrossSection.circle(w / 2, 16).translate((x1, y1))


def text(s, height, cx, cy, mirror=False, bold=True):
    fp = FontProperties(family="DejaVu Sans", weight="bold" if bold else "normal")
    tp = TextPath((0, 0), s, size=10, prop=fp)
    polys = [[tuple(p) for p in pg] for pg in tp.to_polygons() if len(pg) > 2]
    cs = CrossSection(polys, FillRule.EvenOdd)
    b = cs.bounds()  # (xmin, ymin, xmax, ymax)
    k = height / (b[3] - b[1])
    cs = cs.translate((-(b[0] + b[2]) / 2, -(b[1] + b[3]) / 2)).scale((k, k))
    if mirror:
        cs = cs.mirror((1, 0))
    return cs.translate((cx, cy))


# ------------------------------------------------------------------ contorno
OUTLINE = poly([(0, 0), (39.56, 0), (46, 8.64), (46, 67.68), (36.8, 67.68),
                (33.12, 72), (0, 72), (0, 63.36), (3, 60.48), (0, 57.6)])
INNER = OUTLINE.offset(-WALL, JoinType.Miter)


def usb_slot(cx, y_wall, dc, top=True):
    """rasgo de USB-C atravessando a parede de cima (top) ou de baixo."""
    r = USB_T / 2
    cs = (CrossSection.square((USB_W - USB_T, USB_T)).translate((-(USB_W - USB_T) / 2, -r))
          + CrossSection.circle(r, 24).translate((-(USB_W - USB_T) / 2, 0))
          + CrossSection.circle(r, 24).translate(((USB_W - USB_T) / 2, 0)))
    # seção no plano x-d; extrudar através da parede ao longo de y
    m = cs.extrude(WALL * 3).translate((0, 0, -WALL * 1.5))
    m = m.rotate((90, 0, 0))                     # agora seção no plano x-z
    return m.translate((cx, y_wall, z(dc)))


ESP_USB = usb_slot((ESP_X0 + ESP_X1) / 2, H - WALL / 2, ESP_PCB_D + 1.0 + 1.6)
TP_USB = usb_slot((TP_X0 + TP_X1) / 2, WALL / 2, TP_PCB_D + 1.0 + 1.6)


# ------------------------------------------------------------------ FRENTE
def front_shell():
    m = slab(OUTLINE, 0, SPLIT) - slab(INNER, FACE, SPLIT + 1)

    # argola do chaveiro
    tab = (CrossSection.square((10, 5)).translate((5, 70))
           + CrossSection.circle(5, SEG).translate((10, 75)))
    tab -= CrossSection.circle(2.3, SEG).translate((10, 75))
    m += slab(tab, 0, 6.0)

    # janela da tela + moldura para o módulo
    win = chamfer_rect(OLED_C[0], OLED_C[1] + WIN_DY, WIN_W, WIN_H, 1.5)
    m -= slab(win, -1, FACE + 1)
    mod = CrossSection.square((OLED_W, OLED_H)).translate(
        (OLED_C[0] - OLED_W / 2, OLED_C[1] - OLED_H / 2))
    frame = ring(mod, 0, 1.2) - CrossSection.square((10, 4)).translate(
        (OLED_C[0] - 5, OLED_C[1] + OLED_H / 2 - 1))       # passagem dos fios no topo
    m += slab(frame ^ INNER.offset(0.6, JoinType.Miter), FACE, FACE + OLED_STACK)

    # furos dos botões
    m -= slab(dpad_shape(*BTN_L, DPAD, FIT), -1, FACE + 1)
    m -= slab(dpad_shape(*BTN_R, DPAD, FIT), -1, FACE + 1)
    m -= slab(octagon(*BTN_A, A_ACROSS, FIT), -1, FACE + 1)

    # colunas do suporte dos botões (furo para os pinos)
    plate_d = PLATE_D0
    for (px, py) in PLATE_POSTS:
        post = cyl(px, py, 1.7, FACE, plate_d) - cyl(px, py, 1.0, plate_d - 2.6, plate_d + 1)
        m += post

    # torres dos parafusos
    for (bx, by) in BOSSES:
        m += cyl(bx, by, BOSS_R, FACE, SPLIT)
        m -= cyl(bx, by, 0.8, 3.0, SPLIT + 1)

    # rasgo do USB do ESP32 (metade dele fica na frente)
    m -= ESP_USB

    # -------- sulcos para pintar (canetinha) --------
    g = CrossSection()
    # magenta: aro da tela e aro do A, ventilação
    g += ring(win, 1.2, 1.2 + GROOVE)
    g += ring(octagon(*BTN_A, A_ACROSS, FIT), 1.0, 1.0 + GROOVE)
    for k in range(6):
        g += line((40.6, 44 + 2.2 * k), (43.8, 44 + 2.2 * k), 1.0)
    # ciano: trilhas de circuito com "pads"
    g += line((3.4, 36), (3.4, 54)) + line((3.4, 36), (6.5, 36))
    g += ring(CrossSection.circle(1.0, 24).translate((3.4, 55.8)), 0, GROOVE)
    g += line((28.6, 5.5), (37.2, 5.5)) + line((37.2, 5.5), (37.2, 10.2))
    g += ring(CrossSection.circle(1.0, 24).translate((26.4, 5.5)), 0, GROOVE)
    # amarelo: listras de alerta + número de série
    band = CrossSection.square((34, 4)).translate((5, 29.5))
    stripes = CrossSection()
    for k in range(-2, 14):
        x = 5 + k * 3.2
        stripes += poly([(x, 29.5), (x + 1.6, 29.5), (x + 1.6 + 4, 33.5), (x + 4, 33.5)])
    g += stripes ^ band
    g += text("OSM-01", 3.4, 18.5, 67.4)
    # verde: LEDs de status
    for x in (6.0, 9.6, 13.2):
        g += CrossSection.circle(0.95, 24).translate((x, 3.6))

    m -= slab(g ^ OUTLINE.offset(-0.6, JoinType.Miter), -1, ENGR)
    return m


# ------------------------------------------------------------------ SUPORTE DOS BOTÕES
PLATE_POSTS = [(6.0, 27.0), (27.4, 27.0), (27.4, 9.4), (6.0, 9.4)]
PLATE_D0 = FACE + FLANGE_T + SW_H     # frente do suporte = base dos botões
PLATE_T = 1.2


def button_plate():
    """plano: base dos 3 botões táteis. Imprimir deitado."""
    outline = CrossSection.square((37.4, 20.6)).translate((3.0, 8.2))
    outline -= CrossSection.circle(BOSS_R + 0.4, SEG).translate(BOSSES[2])
    m = outline.extrude(PLATE_T)
    for (cx, cy) in (BTN_L, BTN_R, BTN_A):
        pocket = CrossSection.square((6.3, 6.3)).translate((cx - 3.15, cy - 3.15))
        m -= pocket.extrude(1).translate((0, 0, PLATE_T - 0.6))
    for (px, py) in PLATE_POSTS:
        m += CrossSection.circle(0.9, 24).translate((px, py)).extrude(2.2).translate((0, 0, PLATE_T))
    return m


# ------------------------------------------------------------------ TRASEIRA
def back_shell():
    m = slab(OUTLINE, SPLIT, D) - slab(INNER, SPLIT - 1, D - BACK)

    # aba de encaixe que entra na frente
    lip = ring(INNER, -(0.15 + 0.95), -0.15)
    for (bx, by) in BOSSES:
        lip -= CrossSection.circle(BOSS_R + 0.5, SEG).translate((bx, by))
    lip -= CrossSection.square((14, 6)).translate((15, 66))      # USB do ESP32
    lip -= CrossSection.square((19, 5)).translate((1.5, 0))      # placa TP4056
    lip -= CrossSection.square((6, 11)).translate((40, 37))      # chave
    m += slab(lip, SPLIT - 1.6, SPLIT)

    # torres + rebaixo da cabeça do parafuso
    for (bx, by) in BOSSES:
        m += cyl(bx, by, BOSS_R, SPLIT, D - BACK)
        m -= cyl(bx, by, 1.2, SPLIT - 1, D + 1)
        m -= cyl(bx, by, 2.15, D - 1.5, D + 1)

    # berço do ESP32 (encaixa a borda de baixo da placa)
    cradle = box(18, ESP_Y0 - 2.5, 26, ESP_Y0 + 0.5, ESP_PCB_D - 0.5, D - BACK)
    cradle -= box(17, ESP_Y0 - 0.2, 27, ESP_Y0 + 1, ESP_PCB_D - 0.1, ESP_PCB_D + 1.15)
    cradle -= box(17, ESP_Y0 - 0.2, 27, ESP_Y0 + 1, ESP_PCB_D + 1.15, D - BACK)  # livre p/ componentes
    m += cradle

    # divisória entre TP4056 e bateria + moldura da bateria
    m += box(TP_X1 + 0.3, 3.0, TP_X1 + 1.5, 29.0, TP_PCB_D - 0.2, D - BACK)
    bx, by, bw, bh = BAT
    bat = CrossSection.square((bw + 0.6, bh + 0.6)).translate((bx - 0.3, by - 0.3))
    m += slab(ring(bat, 0, 1.0) - CrossSection.square((bw + 4, 6)).translate((bx - 2, by + bh - 2)),
              D - BACK - 2.0, D - BACK)

    # chave deslizante: rasgo na parede direita + guias
    sy0, sy1 = SWITCH_Y
    sc = (sy0 + sy1) / 2
    m -= box(W - WALL - 1, sc - 2.3, W + 1, sc + 2.3, SWITCH_D - 1.1, SWITCH_D + 1.1)
    for yy in (sy0 - 0.8, sy1):
        m += box(W - WALL - 3.6, yy, W - WALL, yy + 0.8, SWITCH_D - 1.8, D - BACK)

    # USBs
    m -= ESP_USB
    m -= TP_USB

    # pastilha piezo: anel de fixação + furos de som
    px, py = PIEZO_C
    m += slab(ring(CrossSection.circle(PIEZO_D / 2 + 0.3, SEG).translate((px, py)), 0, 1.0),
              D - BACK - 1.2, D - BACK)
    for k in range(7):
        a = 2 * math.pi * k / 7
        m -= cyl(px + 3.4 * math.cos(a), py + 3.4 * math.sin(a), 0.7, D - BACK - 1, D + 1)
    m -= cyl(px, py, 0.7, D - BACK - 1, D + 1)

    # gravação nas costas (espelhada para ler por trás)
    g = text("ÓSMIO", 4.2, W - 20, 24, mirror=True)
    g += text("UNIT 3B", 2.6, W - 20, 17.5, mirror=True)
    g = g.translate((0, 0))
    m -= slab(g, D - ENGR, D + 1)
    return m


# ------------------------------------------------------------------ BOTÕES
def cap(shape_body, mark):
    """flange na mesa (z=0); topo com sulco do símbolo."""
    flange = shape_body.offset(FLANGE, JoinType.Miter)
    m = flange.extrude(FLANGE_T) + shape_body.extrude(FACE + CAP_OUT).translate((0, 0, FLANGE_T))
    top = FLANGE_T + FACE + CAP_OUT
    m -= mark.extrude(1).translate((0, 0, top - ENGR))
    return m


def triangle(cx, cy, s, left):
    k = -1 if left else 1
    return poly([(cx + k * s * 0.55, cy), (cx - k * s * 0.45, cy - s * 0.55),
                 (cx - k * s * 0.45, cy + s * 0.55)][::(-1 if left else 1)])


def caps():
    body_l = dpad_shape(0, 0, DPAD)
    body_a = octagon(0, 0, A_ACROSS)
    return {
        "botao_esquerda": cap(body_l, triangle(0, 0, 3.6, True)),
        "botao_direita": cap(body_l, triangle(0, 0, 3.6, False)),
        "botao_a": cap(body_a, text("A", 4.6, 0, 0)),
    }


# ------------------------------------------------------------------ export
def export(m, name, flip=False):
    if flip:  # face para baixo na mesa
        m = m.rotate((0, 180, 0))
    b = m.bounding_box()
    m = m.translate((-b[0], -b[1], -b[2]))
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(vertices=mesh.vert_properties[:, :3], faces=mesh.tri_verts)
    tm.merge_vertices()
    tm.export(f"{name}.stl")
    return tm


if __name__ == "__main__":
    parts = {
        "frente": (front_shell(), True),
        "traseira": (back_shell(), False),
        "suporte_botoes": (button_plate(), False),
    }
    for k, v in caps().items():
        parts[k] = (v, False)
    for name, (m, flip) in parts.items():
        tm = export(m, name, flip)
        print(f"{name:16s} watertight={tm.is_watertight}  {tm.extents.round(1)} mm  vol={tm.volume/1000:.2f} cm3")
