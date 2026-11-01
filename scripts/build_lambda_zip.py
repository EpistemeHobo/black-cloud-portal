"""Build infra/portal_mode.zip, the mode function's code for uploading in the Lambda console.

    python scripts/build_lambda_zip.py

Run it after changing anything in infra/portal_mode/, and commit the zip with
the change (infra/tests checks they match). Fixed timestamps keep the zip
identical from one build to the next, so it only changes when the code does.
"""
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "infra" / "portal_mode"
TARGET = SOURCE.parent / "portal_mode.zip"
FILES = ("handler.py", "wake.html")


def build(target: Path = TARGET) -> Path:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16  # readable by the Lambda runtime
            # Normalized line endings, so a Windows checkout builds the same zip.
            z.writestr(info, (SOURCE / name).read_bytes().replace(b"\r\n", b"\n"), zipfile.ZIP_DEFLATED)
    return target


if __name__ == "__main__":
    print(f"Wrote {build()}")
