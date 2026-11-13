"""Draws the two AWS diagrams in docs/diagrams/: built by hand (Lab 1) and built by
CloudFormation (Lab 2). Both show the same services in the same places, so they can be
compared side by side; only the numbers, the left column and the stack outline differ.

The style follows the TOR staff dev-VM diagram: a 1920x1080 SVG, white cards, AWS
category colours on the icon tiles, navy step numbers and a legend underneath.
Each SVG also gets an HTML page around it, for printing to PDF at that size. The PNG
copies are screenshots of those pages, from a headless browser:

    msedge --headless=new --window-size=1920,1080 --screenshot=<file.png> <file.html>

Run: python scripts/build_aws_diagrams.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "docs" / "diagrams"

NAVY, GREY, BORDER = "#232F3E", "#545B64", "#D5DBDB"
ORANGE, RED, PINK, GREEN, PURPLE = "#ED7100", "#DD344C", "#E7157B", "#7AA116", "#C925D1"

# Icon drawings on a 72x72 tile, in white strokes.
ICONS = {
    "person": (NAVY, '<circle cx="36" cy="27" r="10"/><path d="M18 57 C18 41 54 41 54 57"/>'),
    "console": (NAVY, '<rect x="13" y="16" width="46" height="38" rx="4"/><path d="M13 26 H59"/>'
                      '<path d="M36 34 V52 L40 48 L44 56 L48 54 L44 46 L50 46 Z"/>'),
    "cloudformation": (PINK, '<path d="M36 14 L58 25 L36 36 L14 25 Z"/><path d="M14 36 L36 47 L58 36"/>'
                             '<path d="M14 47 L36 58 L58 47"/>'),
    "cognito": (RED, '<rect x="12" y="18" width="48" height="36" rx="4"/><circle cx="27" cy="32" r="6"/>'
                     '<path d="M18 47 C18 39 36 39 36 47"/><path d="M42 30 H52 M42 38 H52 M42 46 H48"/>'),
    "apigateway": (PINK, '<path d="M26 20 L14 36 L26 52"/><path d="M46 20 L58 36 L46 52"/>'
                         '<path d="M30 36 H31 M36 36 H37 M42 36 H43"/>'),
    "beanstalk": (ORANGE, '<path d="M36 58 V26"/><path d="M36 42 C24 42 17 35 17 24 C29 24 36 31 36 42"/>'
                          '<path d="M36 33 C48 33 55 26 55 15 C43 15 36 22 36 33"/>'),
    "ec2": (ORANGE, '<rect x="24" y="24" width="24" height="24" rx="2"/>'
                    '<path d="M30 15 V24 M36 15 V24 M42 15 V24 M30 48 V57 M36 48 V57 M42 48 V57 '
                    'M15 30 H24 M15 36 H24 M15 42 H24 M48 30 H57 M48 36 H57 M48 42 H57"/>'),
    "aurora": (PURPLE, '<ellipse cx="36" cy="20" rx="17" ry="6"/><path d="M19 20 V52 C19 60 53 60 53 52 V20"/>'
                       '<path d="M19 31 C19 39 53 39 53 31 M19 42 C19 50 53 50 53 42"/>'),
    "s3": (GREEN, '<ellipse cx="36" cy="23" rx="18" ry="6"/><path d="M18 23 L23 53 C25 58 47 58 49 53 L54 23"/>'),
    "lambda": (ORANGE, '<path d="M20 17 H29 L48 55 H55"/><path d="M38 35 L25 55"/>'),
    "eventbridge": (PINK, '<circle cx="36" cy="36" r="19"/><path d="M36 25 V36 L45 42"/>'),
    "ssm": (PINK, '<path d="M17 24 H55 M17 36 H55 M17 48 H55"/><circle cx="27" cy="24" r="4" fill="#E7157B"/>'
                  '<circle cx="45" cy="36" r="4" fill="#E7157B"/><circle cx="33" cy="48" r="4" fill="#E7157B"/>'),
    "secrets": (RED, '<rect x="20" y="33" width="32" height="23" rx="3"/><path d="M27 33 V26 C27 15 45 15 45 26 V33"/>'
                     '<path d="M36 42 V48"/>'),
    "shield": (RED, '<path d="M36 13 L55 20 V35 C55 47 47 55 36 59 C25 55 17 47 17 35 V20 Z"/>'
                    '<path d="M27 36 L33 42 L45 30"/>'),
    "terminal": (PINK, '<rect x="14" y="19" width="44" height="34" rx="4"/><path d="M23 30 L30 36 L23 42"/>'
                       '<path d="M34 43 H47"/>'),
    "key": (RED, '<circle cx="26" cy="36" r="10"/><path d="M36 36 H57 M51 36 V45 M44 36 V43"/>'),
}


class Svg:
    def __init__(self):
        self.parts: list[str] = []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self, x, y, s, size=16, color=GREY, bold=False, anchor="start", italic=False, spacing=None):
        attrs = f'x="{x}" y="{y}" font-size="{size}" fill="{color}"'
        attrs += ' font-weight="bold"' * bold + ' font-style="italic"' * italic
        attrs += f' text-anchor="{anchor}"' if anchor != "start" else ""
        attrs += f' letter-spacing="{spacing}"' if spacing else ""
        self.add(f"<text {attrs}>{escape(s)}</text>")

    def card(self, x, y, w, h):
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#FFFFFF" stroke="{BORDER}" stroke-width="1.5"/>')

    def icon(self, name, x, y, size=72):
        color, body = ICONS[name]
        scale = size / 72
        stroke = 3 if size >= 72 else 4
        self.add(f'<g transform="translate({x},{y}) scale({scale:.4f})" stroke="#FFFFFF" stroke-width="{stroke}" '
                 f'fill="none" stroke-linecap="round" stroke-linejoin="round">'
                 f'<rect width="72" height="72" rx="10" fill="{color}" stroke="none"/>{body}</g>')

    def number(self, cx, cy, n):
        """A navy step marker: a circle for one number, a pill for several."""
        width = max(28, 9 * len(n) + 16)
        self.add(f'<rect x="{cx - width / 2:.0f}" y="{cy - 14}" width="{width}" height="28" rx="14" fill="{NAVY}"/>')
        self.text(cx, cy + 6, n, size=16, color="#FFFFFF", bold=True, anchor="middle")

    def arrow(self, d, dashed=False, both=False):
        extra = ' stroke-dasharray="7 5"' * dashed + ' marker-start="url(#ah)"' * both
        self.add(f'<path d="{d}" fill="none" stroke="{GREY}" stroke-width="2" marker-end="url(#ah)"{extra}/>')

    def service(self, x, y, w, h, icon, title, lines, step=None):
        """A card with a 72px icon on top, a bold name and grey caption lines."""
        self.card(x, y, w, h)
        cx = x + w / 2
        self.icon(icon, cx - 36, y + 18)
        self.text(cx, y + 122, title, size=19, color=NAVY, bold=True, anchor="middle")
        for i, line in enumerate(lines):
            self.text(cx, y + 148 + 21 * i, line, anchor="middle")
        if step:
            self.number(x + w - 22 - 4.5 * len(step), y, step)

    def compact(self, x, y, w, h, icon, title, lines, step=None):
        """A shorter card: a 56px icon, the name and captions, all centred."""
        self.card(x, y, w, h)
        cx = x + w / 2
        self.icon(icon, cx - 28, y + 16, 56)
        self.text(cx, y + 98, title, size=19, color=NAVY, bold=True, anchor="middle")
        for i, line in enumerate(lines):
            self.text(cx, y + 122 + 20 * i, line, size=15, anchor="middle")
        if step:
            self.number(x + w - 22 - 4.5 * len(step), y, step)

    def render(self, width=1920, height=1080) -> str:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                f'viewBox="0 0 {width} {height}" font-family="Arial, Helvetica, sans-serif">\n'
                '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="{GREY}"/></marker></defs>\n'
                f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>\n' + "\n".join(self.parts) + "\n</svg>\n")


# Card positions, the same in both diagrams.
ROW1, ROW1_H = 290, 250
ROW2, ROW2_H = 600, 190
COGNITO, API, BEANSTALK, AURORA, S3 = 380, 660, 940, 1310, 1590
CARD_W, BEANSTALK_W = 210, 300


def draw(by_hand: bool) -> str:
    s = Svg()
    step = (lambda hand, stack: hand if by_hand else stack)

    # Title and badge
    s.text(40, 92, "Gargantua Developer Portal on AWS", size=44, color=NAVY, bold=True)
    s.text(40, 135, step("Built by hand in the AWS Console. Numbers are the steps of Lab 1, in the order you do them.",
                         "Built from one CloudFormation template in about 12 minutes. Numbers are the order it builds (Lab 2)."),
           size=22)
    badge = step("Lab 1 · by hand · 16 steps", "Lab 2 · one stack · delete = reset")
    s.add(f'<rect x="1500" y="62" width="380" height="50" rx="25" fill="#FFF4E8" stroke="{ORANGE}" stroke-width="1.5"/>')
    s.text(1690, 94, badge, size=19, color=NAVY, bold=True, anchor="middle")

    # Zones and the AWS Cloud group
    s.add('<rect x="40" y="165" width="240" height="670" rx="18" fill="#F7F7F5"/>')
    s.text(60, 198, "PEOPLE", size=16, bold=True, spacing=1.5)
    s.add('<rect x="300" y="165" width="1580" height="670" rx="18" fill="#F6F9FC"/>')
    s.text(320, 198, "AWS ACADEMY LEARNER LAB · us-east-1", size=16, bold=True, spacing=1.5)
    s.add(f'<rect x="320" y="214" width="1540" height="600" fill="none" stroke="{NAVY}" stroke-width="2"/>')
    s.add(f'<rect x="320" y="214" width="52" height="40" fill="{NAVY}"/>')
    s.text(346, 237, "aws", size=17, color="#FFFFFF", bold=True, anchor="middle")
    s.add('<path d="M332 243 C340 249 352 249 360 243" fill="none" stroke="#FF9900" stroke-width="2.5" stroke-linecap="round"/>')
    s.text(384, 240, "AWS Cloud – Learner Lab account (runs as LabRole)", size=19, color=NAVY, bold=True)

    if not by_hand:
        # Everything the stack owns sits inside this outline; the CloudFormation card doesn't.
        s.add(f'<path d="M350 256 H1830 V800 H630 V578 H350 Z" fill="none" stroke="{PINK}" stroke-width="2" '
              'stroke-dasharray="9 6"/>')
        s.add(f'<rect x="1508" y="243" width="322" height="26" rx="13" fill="#FDECF4" stroke="{PINK}" stroke-width="1.5"/>')
        s.text(1669, 261, "Stack “gargantua” · deleted as one", size=15, color=NAVY, bold=True, anchor="middle")

    # People
    s.service(60, ROW1, 200, ROW1_H, "person", "Visitors", ["Browser, over HTTPS"])
    s.service(60, ROW2, 200, ROW2_H - 0, "person", "You",
              step(["AWS Console;", "app zip from your PC"], ["portal_stack.py create,", "or upload in the console"]))

    # Row 1: the request path
    s.service(COGNITO, ROW1, CARD_W, ROW1_H, "cognito", "Amazon Cognito",
              ["Sign-in & sign-up pages,", "passwords, email codes", step("", "+ your admin user")],
              step("14 · 15", "2"))
    s.service(API, ROW1, CARD_W, ROW1_H, "apigateway", "API Gateway",
              ["The HTTPS address;", "/launch wakes the portal"], step("11", "2 · 6"))
    s.card(BEANSTALK, ROW1, BEANSTALK_W, ROW1_H)
    s.icon("beanstalk", BEANSTALK + BEANSTALK_W / 2 - 36, ROW1 + 18)
    s.text(BEANSTALK + BEANSTALK_W / 2, ROW1 + 122, "Elastic Beanstalk", size=19, color=NAVY, bold=True, anchor="middle")
    s.text(BEANSTALK + BEANSTALK_W / 2, ROW1 + 146, "Docker, one instance, no SSH", anchor="middle")
    s.add(f'<rect x="{BEANSTALK + 14}" y="{ROW1 + 160}" width="{BEANSTALK_W - 28}" height="76" rx="10" '
          f'fill="#FFF4E8" stroke="{ORANGE}" stroke-width="1" stroke-dasharray="4 3"/>')
    s.icon("ec2", BEANSTALK + 24, ROW1 + 172, 52)
    s.text(BEANSTALK + 88, ROW1 + 192, "Amazon EC2 t3.small", size=17, color=NAVY, bold=True)
    s.text(BEANSTALK + 88, ROW1 + 214, "The portal container", size=15)
    s.number(BEANSTALK + BEANSTALK_W / 2, ROW1, step("4 · 5 · 7d · 12 · 16", "5"))
    s.service(AURORA, ROW1, CARD_W, ROW1_H, "aurora", "Aurora PostgreSQL",
              ["db.t3.medium; systems,", step("people, checklists", "own user made by the app")], step("3 · 7b", "4"))
    s.service(S3, ROW1, CARD_W, ROW1_H, "s3", "Amazon S3",
              ["Guide markdown files;", "versioned, HTTPS only"], step("2 · 7e", "2"))

    # Row 2
    if by_hand:
        s.compact(COGNITO, ROW2, CARD_W, ROW2_H, "console", "AWS Console",
                  ["You create each", "service yourself,", "in the numbered order"])
    else:
        s.compact(COGNITO, ROW2, CARD_W, ROW2_H, "cloudformation", "CloudFormation",
                  ["Reads full-stack.yaml;", "helpers copy the app", "from GitHub into S3"], "1 · 3")

    # Wake and sleep
    s.card(API, ROW2, AURORA - 70 - API, ROW2_H)
    s.icon("eventbridge", API + 26, ROW2 + 30, 56)
    s.text(API + 54, ROW2 + 112, "EventBridge", size=15, color=NAVY, anchor="middle")
    s.arrow(f"M{API + 92} {ROW2 + 58} H{API + 130}")
    s.icon("lambda", API + 136, ROW2 + 30, 56)
    s.text(API + 164, ROW2 + 112, "Lambda", size=15, color=NAVY, anchor="middle")
    if by_hand:
        s.number(API + 54, ROW2 + 30, "10")
        s.number(API + 164, ROW2 + 30, "8 · 13")
    else:
        s.number(API + 110, ROW2, "6")
    s.text(API + 236, ROW2 + 44, "Wake & sleep", size=19, color=NAVY, bold=True)
    for i, line in enumerate(["Every 15 minutes: asleep after 30 idle minutes",
                              "Midnight (Thai time): everything stops",
                              "/launch: the waking-up page starts it",
                              "Stops and starts Aurora and the instance"]):
        s.text(API + 236, ROW2 + 72 + 22 * i, line, size=15)

    if by_hand:
        s.compact(AURORA, ROW2, CARD_W, ROW2_H, "ssm", "Parameter Store",
                  ["Mode and woken-at,", "plus 3 secrets", "as SecureStrings"], "7c · 9")
    else:
        s.compact(AURORA, ROW2, CARD_W, ROW2_H, "secrets", "Secrets Manager",
                  ["4 generated secrets;", "Parameter Store keeps", "mode and woken-at"], "2 · 6")

    # Guards: one row each
    s.card(S3, ROW2, CARD_W, ROW2_H)
    s.text(S3 + 20, ROW2 + 32, "Guards", size=19, color=NAVY, bold=True)
    s.number(S3 + CARD_W - 22 - 4.5 * len(step("1 · 7a", "2")), ROW2, step("1 · 7a", "2"))
    guards = [("shield", "Security groups", "Database: app only"),
              ("terminal", "Session Manager", "A shell without SSH"),
              ("key", "IAM", "LabRole, no own roles")]
    for i, (icon, name, caption) in enumerate(guards):
        y = ROW2 + 48 + 46 * i
        s.icon(icon, S3 + 18, y, 36)
        s.text(S3 + 64, y + 15, name, size=15, color=NAVY, bold=True)
        s.text(S3 + 64, y + 33, caption, size=13)

    # How requests and switches flow
    s.arrow(f"M260 {ROW1 + 70} H{COGNITO - 2}")
    s.text(290, ROW1 + 62, "sign in", size=15, italic=True)
    s.arrow(f"M260 {ROW1 + 190} H342 V565 H{API + 60} V{ROW1 + ROW1_H + 2}")
    s.text(386, 558, "HTTPS", size=15, italic=True)
    s.arrow(f"M{API + CARD_W} {ROW1 + 125} H{BEANSTALK - 2}")
    s.arrow(f"M{BEANSTALK + BEANSTALK_W} {ROW1 + 125} H{AURORA - 2}")
    s.arrow(f"M{BEANSTALK + 280} {ROW1} V272 H{S3 + 105} V{ROW1 - 2}")
    s.arrow(f"M{BEANSTALK + 20} {ROW1} V272 H{COGNITO + 105} V{ROW1 - 2}")
    s.arrow(f"M{API + 150} {ROW1 + ROW1_H} V{ROW2 - 2}")
    s.text(API + 158, 582, "/launch", size=15, italic=True)
    s.arrow(f"M{BEANSTALK + 150} {ROW2} V{ROW1 + ROW1_H + 2}", dashed=True)
    s.arrow(f"M{BEANSTALK + 270} {ROW2} V570 H{AURORA + 105} V{ROW1 + ROW1_H + 2}", dashed=True)
    s.text(BEANSTALK + 160, 582, "start / stop", size=15, italic=True)
    s.arrow(f"M{AURORA - 2} {ROW2 + 150} H{AURORA - 68}")
    s.text(AURORA - 60, ROW2 + 140, "mode", size=15, italic=True)
    s.arrow(f"M260 {ROW2 + 95} H{COGNITO - 2}")

    # Legend
    if by_hand:
        s.text(40, 880, "Build order (Lab 1)", size=19, color=NAVY, bold=True)
        parts = [
            ("Part 1 · The portal", ["1  Security groups", "2  S3 bucket", "3  Aurora PostgreSQL",
                                      "4  App bundle (zip)", "5  Elastic Beanstalk", "6  Check it works"]),
            ("Part 2 · Security", ["7a  SSH closed; Session Manager", "7b  The app's own database user",
                                    "7c  Secrets into Parameter Store", "7d  Remove the admin password",
                                    "7e  S3 over HTTPS only"]),
            ("Part 3 · Hibernate & HTTPS", ["8  Lambda function", "9  Mode parameter", "10  EventBridge rules",
                                             "11  API Gateway", "12  Lock the app to HTTPS", "13  Test the switches"]),
            ("Part 4 · Cognito", ["14  User pool", "15  First admin user", "16  Switch the app to Cognito"]),
        ]
        for col, (head, lines) in enumerate(parts):
            x = 40 + 470 * col
            s.text(x, 914, head, size=17, color=NAVY, bold=True)
            for i, line in enumerate(lines):
                number, _, rest = line.partition("  ")
                s.text(x, 942 + 22 * i, number, size=15, color=NAVY, bold=True)
                s.text(x + 34, 942 + 22 * i, rest, size=15, color=NAVY)
        s.text(1450, 1060, "→ requests    - - › wake & sleep", size=15, italic=True)
    else:
        s.text(40, 900, "How the stack builds (Lab 2)", size=19, color=NAVY, bold=True)
        items = ["Upload full-stack.yaml with your email", "Network rules, S3, secrets, Cognito, API address",
                 "Helpers copy the app from GitHub to S3", "Aurora starts (about 6 minutes)",
                 "Beanstalk runs the app (about 6 minutes)", "Lambda, rules and mode; the API's routes go live",
                 "Delete the stack: everything goes, users too"]
        for i, item in enumerate(items):
            x, y = 40 + 460 * (i % 4), 935 + 45 * (i // 4)
            s.number(x + 14, y, str(i + 1))
            s.text(x + 38, y + 6, item, color=NAVY)
        s.text(1450, 1045, "→ requests    - - › wake & sleep", size=15, italic=True)
        s.text(40, 1045, "Unlike Lab 1: secrets are generated, nobody sees them, and the app creates its own database user.",
               size=15, italic=True)
    return s.render()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, by_hand in (("aws-by-hand", True), ("aws-cloudformation", False)):
        svg = draw(by_hand)
        (OUT / f"{name}.svg").write_text(svg, encoding="utf-8", newline="\n")
        (OUT / f"{name}.html").write_text(
            '<!doctype html><html><head><meta charset="utf-8"><style>@page{size:1920px 1080px;margin:0}'
            "html,body{margin:0;padding:0}svg{display:block}</style></head><body>" + svg + "</body></html>\n",
            encoding="utf-8", newline="\n")
        print(f"docs/diagrams/{name}.svg and .html")


if __name__ == "__main__":
    main()
