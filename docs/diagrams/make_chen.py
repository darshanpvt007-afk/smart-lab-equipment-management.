"""Chen-notation ER diagram for the Smart Lab project.

Writes an SVG: python3 docs/diagrams/make_chen.py docs/diagrams/ER_Chen.svg
The PNG and PDF were exported from that SVG with a browser.
"""
import math
import sys

W, H = 2700, 2150
OX, OY = 60, 40  # global shift

# entity: (x, y, label, [(attr, dx, dy, is_pk)])
E = {
    "supplier": (350, 330, "SUPPLIER", [
        ("Supplier_ID", -40, -150, True), ("Supplier_Name", -235, -75, False),
        ("Contact_Number", -260, 20, False), ("Email", -200, 115, False),
        ("Address", -30, 150, False)]),
    "purchase": (1050, 330, "PURCHASE", [
        ("Purchase_ID", -110, -150, True), ("Purchase_Date", 110, -150, False),
        ("Invoice_Number", 250, -60, False), ("Total_Amount", 270, 40, False),
        ("Purchase_Status", -150, 130, False)]),
    "category": (2250, 330, "EQUIPMENT_CATEGORY", [
        ("Category_ID", -80, -150, True), ("Category_Name", 140, -150, False),
        ("Description", 230, 90, False)]),
    "equipment": (1300, 860, "EQUIPMENT", [
        ("Equipment_ID", 120, -155, True), ("Equipment_Name", -260, -120, False),
        ("Serial_Number", -290, 100, False), ("Condition", 230, 130, False),
        ("Availability_Status", -150, 190, False)]),
    "lab": (350, 860, "LAB", [
        ("Lab_ID", -40, -150, True), ("Lab_Name", -200, -90, False),
        ("Location", -230, 10, False), ("Capacity", -190, 110, False),
        ("Lab_Type", -20, 150, False)]),
    "maintenance": (2250, 860, "MAINTENANCE", [
        ("Maintenance_ID", -20, -150, True), ("Maintenance_Date", 250, -95, False),
        ("Maintenance_Type", 270, 5, False), ("Maintenance_Cost", 250, 105, False),
        ("Maintenance_Status", -200, 130, False), ("Remarks", 110, 165, False)]),
    "allocation": (1300, 1380, "EQUIPMENT_ALLOCATION", [
        ("Allocation_ID", -230, -120, True), ("Allocation_Date", 240, -120, False),
        ("Expected_Return_Date", -260, 120, False), ("Allocation_Status", 250, 120, False)]),
    "student": (350, 1380, "STUDENT", [
        ("Student_ID", -40, -150, True), ("Student_Name", -225, -95, False),
        ("Register_Number", -255, 5, False), ("Department", -215, 105, False),
        ("Year", -60, 150, False), ("Email", 110, 150, False)]),
    "staff": (2250, 1380, "LAB_STAFF", [
        ("Staff_ID", 200, -110, True), ("Staff_Name", 260, -10, False),
        ("Designation", 240, 90, False), ("Department", 120, 160, False),
        ("Contact_Number", -100, 165, False), ("Email", -230, 110, False)]),
    "return": (1300, 1900, "EQUIPMENT_RETURN", [
        ("Return_ID", -260, -50, True), ("Return_Date", -250, 70, False),
        ("Return_Condition", 260, -50, False), ("Remarks", 240, 70, False)]),
}

# relationship: (x, y, name, ent_a, card_a, ent_b, card_b, total_b)
# ent_a is the "1" side; total_b = ent_b participates totally (FK NOT NULL)
R = [
    (700, 330, "SUPPLIES", "supplier", "1", "purchase", "N", True),
    (1175, 595, "RESULTS_IN", "purchase", "1", "equipment", "N", True),
    (1775, 595, "CLASSIFIES", "category", "1", "equipment", "N", True),
    (825, 860, "CONTAINS", "lab", "1", "equipment", "N", True),
    (1775, 860, "UNDERGOES", "equipment", "1", "maintenance", "N", True),
    (1300, 1120, "IS_ALLOCATED", "equipment", "1", "allocation", "N", True),
    (825, 1380, "RECEIVES", "student", "1", "allocation", "N", True),
    (1775, 1380, "ISSUES", "staff", "1", "allocation", "N", True),
    (2250, 1120, "PERFORMS", "staff", "1", "maintenance", "N", True),
    (1300, 1650, "HAS_RETURN", "allocation", "1", "return", "1", True),
]

INK = "#1f2a37"
ENT_FILL = "#dbeafe"; ENT_STROKE = "#1d4ed8"
REL_FILL = "#fde68a"; REL_STROKE = "#b45309"
ATT_FILL = "#ffffff"; ATT_STROKE = "#475569"
PK_FILL = "#dcfce7"; PK_STROKE = "#15803d"
FONT = "DejaVu Sans, Arial, sans-serif"

out = []
a = out.append


def tw(text, size):
    return len(text) * size * 0.6


def ent_box(key):
    x, y, label, _ = E[key]
    w = max(170, tw(label, 17) + 50)
    return x, y, w, 56


def line(x1, y1, x2, y2, color=INK, width=2):
    a(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
      f'stroke="{color}" stroke-width="{width}"/>')


def double_line(x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L * 3.5, dx / L * 3.5
    line(x1 + nx, y1 + ny, x2 + nx, y2 + ny)
    line(x1 - nx, y1 - ny, x2 - nx, y2 - ny)


def clip_box(cx, cy, w, h, tx, ty):
    """Point where the segment from box centre towards (tx,ty) leaves the box."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = (w / 2) / abs(dx) if dx else float("inf")
    sy = (h / 2) / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def clip_diamond(cx, cy, w, h, tx, ty):
    dx, dy = tx - cx, ty - cy
    s = 1 / (abs(dx) / (w / 2) + abs(dy) / (h / 2))
    return cx + dx * s, cy + dy * s


def clip_ellipse(cx, cy, rx, ry, tx, ty):
    dx, dy = tx - cx, ty - cy
    s = 1 / math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
    return cx + dx * s, cy + dy * s


a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
  f'viewBox="0 0 {W} {H}" font-family="{FONT}">')
a(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
a(f'<g transform="translate({OX},{OY})">')

# title
a(f'<text x="{(W - 2 * OX) / 2}" y="40" text-anchor="middle" font-size="34" '
  f'font-weight="bold" fill="{INK}">Smart Laboratory Equipment Inventory, Allocation and '
  f'Maintenance Management System</text>')
a(f'<text x="{(W - 2 * OX) / 2}" y="82" text-anchor="middle" font-size="24" '
  f'fill="#475569">ER Diagram (Chen notation)</text>')

# attribute links + ellipses (drawn first so entities sit on top)
for key, (x, y, label, attrs) in E.items():
    bx, by, bw, bh = ent_box(key)
    for name, dx, dy, pk in attrs:
        ax, ay = x + dx, y + dy
        rx = tw(name, 15) / 2 + 20
        ry = 24
        p1 = clip_box(bx, by, bw, bh, ax, ay)
        p2 = clip_ellipse(ax, ay, rx, ry, x, y)
        line(*p1, *p2, color=ATT_STROKE, width=1.6)
for key, (x, y, label, attrs) in E.items():
    for name, dx, dy, pk in attrs:
        ax, ay = x + dx, y + dy
        rx = tw(name, 15) / 2 + 20
        fill, stroke = (PK_FILL, PK_STROKE) if pk else (ATT_FILL, ATT_STROKE)
        a(f'<ellipse cx="{ax}" cy="{ay}" rx="{rx:.1f}" ry="24" fill="{fill}" '
          f'stroke="{stroke}" stroke-width="2"/>')
        deco = ' font-weight="bold"' if pk else ""
        a(f'<text x="{ax}" y="{ay + 5}" text-anchor="middle" font-size="15" '
          f'fill="{INK}"{deco}>{name}</text>')
        if pk:  # explicit underline (text-decoration support varies)
            half = tw(name, 15) / 2
            line(ax - half, ay + 9, ax + half, ay + 9, color=INK, width=1.4)

# relationship links
DW, DH = 190, 86
for rx_, ry_, name, ea, ca, eb, cb, total_b in R:
    for ent, card, total in ((ea, ca, False), (eb, cb, total_b)):
        bx, by, bw, bh = ent_box(ent)
        p1 = clip_box(bx, by, bw, bh, rx_, ry_)
        p2 = clip_diamond(rx_, ry_, DW, DH, bx, by)
        (double_line if total else line)(*p1, *p2)
        # cardinality label near the diamond, offset from the line
        mx = p2[0] + (p1[0] - p2[0]) * 0.28
        my = p2[1] + (p1[1] - p2[1]) * 0.28
        dx, dy = p1[0] - p2[0], p1[1] - p2[1]
        L = math.hypot(dx, dy) or 1
        ox, oy = -dy / L * 18, dx / L * 18
        if oy > 0 or (oy == 0 and ox < 0):
            ox, oy = -ox, -oy
        a(f'<text x="{mx + ox:.1f}" y="{my + oy + 7:.1f}" text-anchor="middle" '
          f'font-size="22" font-weight="bold" fill="#b91c1c">{card}</text>')

# diamonds
for rx_, ry_, name, *_ in R:
    pts = f"{rx_},{ry_ - DH/2} {rx_ + DW/2},{ry_} {rx_},{ry_ + DH/2} {rx_ - DW/2},{ry_}"
    a(f'<polygon points="{pts}" fill="{REL_FILL}" stroke="{REL_STROKE}" stroke-width="2.5"/>')
    a(f'<text x="{rx_}" y="{ry_ + 5}" text-anchor="middle" font-size="15" '
      f'font-weight="bold" fill="{INK}">{name}</text>')

# entities
for key, (x, y, label, attrs) in E.items():
    bx, by, bw, bh = ent_box(key)
    a(f'<rect x="{bx - bw/2:.1f}" y="{by - bh/2}" width="{bw:.1f}" height="{bh}" '
      f'fill="{ENT_FILL}" stroke="{ENT_STROKE}" stroke-width="2.5"/>')
    a(f'<text x="{x}" y="{y + 6}" text-anchor="middle" font-size="17" '
      f'font-weight="bold" fill="{INK}">{label}</text>')

# legend
lx, ly = 0, 1845
a(f'<rect x="{lx}" y="{ly}" width="560" height="225" fill="#f8fafc" stroke="#cbd5e1"/>')
a(f'<text x="{lx + 20}" y="{ly + 32}" font-size="19" font-weight="bold" fill="{INK}">Legend</text>')
a(f'<rect x="{lx + 20}" y="{ly + 50}" width="70" height="30" fill="{ENT_FILL}" stroke="{ENT_STROKE}" stroke-width="2"/>')
a(f'<text x="{lx + 105}" y="{ly + 71}" font-size="15" fill="{INK}">Entity</text>')
a(f'<polygon points="{lx+55},{ly+92} {lx+90},{ly+110} {lx+55},{ly+128} {lx+20},{ly+110}" fill="{REL_FILL}" stroke="{REL_STROKE}" stroke-width="2"/>')
a(f'<text x="{lx + 105}" y="{ly + 115}" font-size="15" fill="{INK}">Relationship</text>')
a(f'<ellipse cx="{lx + 55}" cy="{ly + 155}" rx="35" ry="16" fill="{ATT_FILL}" stroke="{ATT_STROKE}" stroke-width="2"/>')
a(f'<text x="{lx + 105}" y="{ly + 160}" font-size="15" fill="{INK}">Attribute</text>')
a(f'<ellipse cx="{lx + 55}" cy="{ly + 196}" rx="35" ry="16" fill="{PK_FILL}" stroke="{PK_STROKE}" stroke-width="2"/>')
a(f'<text x="{lx + 55}" y="{ly + 201}" text-anchor="middle" font-size="13" font-weight="bold" fill="{INK}">ID</text>')
line(lx + 45, ly + 204, lx + 65, ly + 204, width=1.2)
a(f'<text x="{lx + 105}" y="{ly + 201}" font-size="15" fill="{INK}">Primary key (underlined)</text>')
line(lx + 300, ly + 65, lx + 370, ly + 65)
a(f'<text x="{lx + 385}" y="{ly + 71}" font-size="15" fill="{INK}">Partial participation</text>')
double_line(lx + 300, ly + 110, lx + 370, ly + 110)
a(f'<text x="{lx + 385}" y="{ly + 115}" font-size="15" fill="{INK}">Total participation</text>')
a(f'<text x="{lx + 300}" y="{ly + 160}" font-size="20" font-weight="bold" fill="#b91c1c">1 / N</text>')
a(f'<text x="{lx + 385}" y="{ly + 160}" font-size="15" fill="{INK}">Cardinality</text>')

a('</g></svg>')

with open(sys.argv[1], "w") as f:
    f.write("\n".join(out))
