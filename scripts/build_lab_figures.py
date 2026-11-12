"""Draws the four figures inside Lab 1 (Parts 1 to 4) in the same AWS style as
docs/diagrams/aws-by-hand.svg, with its icons and helpers. They are sized for a page:
text stays readable when a figure is printed 6 inches wide.

Writes docs/diagrams/lab1-part<N>.svg and .html. The PNG copies are screenshots of the
HTML pages; see build_aws_diagrams.py for the command.

Run: python scripts/build_lab_figures.py
"""
from build_aws_diagrams import GREY, NAVY, OUT, Svg

LABEL = 20


class Figure(Svg):
    def box(self, x, y, w, h, icon, title, lines=(), size=60):
        """A card with the icon on the left and the name and captions beside it."""
        self.card(x, y, w, h)
        self.icon(icon, x + 20, y + (h - size) / 2, size)
        top = y + h / 2 - 11 * len(lines) + 6
        self.text(x + size + 36, top, title, size=22, color=NAVY, bold=True)
        for i, line in enumerate(lines):
            self.text(x + size + 36, top + 26 + 24 * i, line, size=18)

    def label(self, x, y, text, anchor="middle"):
        """Arrow text on a white patch, so lines passing behind don't cut through it."""
        width = len(text) * LABEL * 0.52 + 16
        left = {"middle": x - width / 2, "start": x - 8, "end": x - width + 8}[anchor]
        self.add(f'<rect x="{left:.0f}" y="{y - LABEL}" width="{width:.0f}" height="{LABEL + 10}" rx="5" fill="#FFFFFF"/>')
        self.text(x, y, text, size=LABEL, color=GREY, anchor=anchor, italic=True)


def part1() -> tuple[str, int, int]:
    f, w, h = Figure(), 1460, 520
    f.box(30, 175, 260, 170, "person", "Browser", ["Plain HTTP for now"])
    f.card(400, 100, 420, 320)
    f.icon("beanstalk", 574, 120)
    f.text(610, 228, "Elastic Beanstalk", size=24, color=NAVY, bold=True, anchor="middle")
    f.text(610, 256, "Docker, one instance", size=18, anchor="middle")
    f.add(f'<rect x="420" y="280" width="380" height="120" rx="10" fill="#FFF4E8" stroke="#ED7100" '
          'stroke-dasharray="4 3"/>')
    f.icon("ec2", 438, 308, 64)
    f.text(520, 336, "EC2: the portal container", size=20, color=NAVY, bold=True)
    f.text(520, 362, "portal-app-sg", size=18)
    f.box(1100, 30, 330, 190, "aurora", "Aurora", ["PostgreSQL", "portal-db-sg: 5432", "from the app only"])
    f.box(1100, 300, 330, 190, "s3", "Amazon S3", ["Guide markdown files,", "versioned"])
    f.arrow("M290 260 H398")
    f.label(344, 248, "HTTP")
    f.arrow("M820 200 H900 V125 H1098")
    f.label(916, 113, "5432, private", anchor="start")
    f.arrow("M820 340 H900 V395 H1098")
    f.label(916, 383, "LabInstanceProfile", anchor="start")
    return f.render(w, h), w, h


def part2() -> tuple[str, int, int]:
    f, w, h = Figure(), 1460, 600
    f.box(30, 215, 220, 170, "person", "You")
    f.box(470, 205, 320, 190, "ec2", "Beanstalk", ["instance", "no SSH key pair"])
    f.box(1100, 20, 330, 170, "ssm", "Parameter Store", ["3 SecureStrings"])
    f.box(1100, 215, 330, 170, "aurora", "Aurora", ["database portal"])
    f.box(1100, 410, 330, 170, "s3", "Amazon S3", ["Plain HTTP refused"])
    f.arrow("M250 300 H468")
    f.icon("terminal", 334, 238, 44)
    f.label(360, 334, "Session Manager")
    f.arrow("M790 250 H880 V105 H1098")
    f.label(896, 60, "reads secrets via", anchor="start")
    f.label(896, 86, "LabInstanceProfile", anchor="start")
    f.arrow("M790 300 H1098")
    f.label(945, 285, "signs in as portal_app")
    f.arrow("M790 350 H880 V495 H1098")
    f.label(896, 483, "HTTPS only", anchor="start")
    return f.render(w, h), w, h


def part3() -> tuple[str, int, int]:
    f, w, h = Figure(), 1560, 640
    c0, c1, c2, c3 = 30, 340, 760, 1230
    r0, r1, r2, ch = 30, 245, 460, 150
    f.box(c0, r0, 230, ch, "person", "Browser")
    f.box(c1, r0, 300, ch, "apigateway", "API Gateway", ["The portal's", "HTTPS address"])
    f.box(c3, r0, 300, ch, "beanstalk", "Beanstalk app")
    f.box(c2, r1, 330, ch, "lambda", "Lambda", ["cloud-dev-portal-mode"])
    f.box(c1, r2, 300, ch, "eventbridge", "EventBridge", ["2 rules"])
    f.box(c3, r1, 300, ch, "ssm", "Parameter Store", ["mode"])
    f.box(c3, r2, 300, ch, "aurora", "Aurora")
    f.arrow(f"M{c0 + 230} {r0 + 75} H{c1 - 2}")
    f.label((c0 + 230 + c1) / 2, r0 + 63, "HTTPS")
    f.arrow(f"M{c1 + 300} {r0 + 75} H{c3 - 2}")
    f.label((c1 + 300 + c3) / 2, r0 + 63, "pages, /api + secret header")
    f.arrow(f"M{c1 + 150} {r0 + ch} V{r1 + 75} H{c2 - 2}")
    f.label(c1 + 160, r1 + 63, "/launch, /_wake/*", anchor="start")
    f.arrow(f"M{c1 + 300} {r2 + 75} H{c2 + 150} V{r1 + ch + 2}")
    f.label(c1 + 318, r2 + 63, "every 15 min; midnight", anchor="start")
    f.arrow(f"M{c2 + 270} {r1} V{r0 + ch + 30} H{c3 + 150} V{r0 + ch + 2}", dashed=True)
    f.label(c2 + 286, r0 + ch + 18, "instances 1 / 0", anchor="start")
    f.arrow(f"M{c2 + 332} {r1 + 75} H{c3 - 2}", both=True)
    f.label((c2 + 330 + c3) / 2, r1 + 63, "mode")
    f.arrow(f"M{c2 + 270} {r1 + ch} V{r2 + 75} H{c3 - 2}", dashed=True)
    f.label(c2 + 286, r2 + 63, "start / stop", anchor="start")
    return f.render(w, h), w, h


def part4() -> tuple[str, int, int]:
    f, w, h = Figure(), 1400, 900
    lanes = {"browser": 230, "app": 700, "cognito": 1170}
    heads = [("browser", "person", "Browser"), ("app", "beanstalk", "Portal app"), ("cognito", "cognito", "Cognito page")]
    for key, icon, name in heads:
        x = lanes[key]
        f.box(x - 170, 20, 340, 120, icon, name)
        f.add(f'<path d="M{x} 140 V880" stroke="#AAB7B8" stroke-width="2" stroke-dasharray="6 6"/>')
    messages = [("browser", "app", "Press the sign-in button", False),
                ("app", "browser", "Redirect to Cognito", True),
                ("browser", "cognito", "Email and password", False),
                ("cognito", "browser", "Redirect to /api/auth/callback?code=…", True),
                ("browser", "app", "One-time code", False),
                ("app", "cognito", "Swap the code for an ID token (PKCE)", False),
                ("app", "browser", "Session cookie", True)]
    for i, (src, dst, text, back) in enumerate(messages):
        y = 215 + 95 * i
        a, b = lanes[src], lanes[dst]
        end = b - 4 if b > a else b + 4
        f.arrow(f"M{a} {y} H{end}", dashed=back)
        mid = (a + b) / 2
        f.label(mid + 18, y - 14, text)
        f.number(mid - len(text) * LABEL * 0.26 - 20, y - 20, str(i + 1))
    return f.render(w, h), w, h


def main() -> None:
    for n, draw in enumerate((part1, part2, part3, part4), start=1):
        svg, _, _ = draw()
        (OUT / f"lab1-part{n}.svg").write_text(svg, encoding="utf-8", newline="\n")
        (OUT / f"lab1-part{n}.html").write_text(
            '<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0}'
            "svg{display:block}</style></head><body>" + svg + "</body></html>\n", encoding="utf-8", newline="\n")
        print(f"docs/diagrams/lab1-part{n}.svg and .html")


if __name__ == "__main__":
    main()
