"""Shared note saying who is using the 5090 (llama-server on the PC). Both projects check it before sending calls.

Usage: gpu_lock.py status | acquire <who> <purpose> | release <who>
The file is ~/.gpu-5090.lock (JSON). It is advisory: it works because both sessions agree to read it first.
"""

import json
import sys
import time
from pathlib import Path

LOCK = Path.home() / ".gpu-5090.lock"


def status():
    return json.loads(LOCK.read_text()) if LOCK.exists() else None


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    held = status()
    if cmd == "status":
        print(json.dumps(held) if held else "free")
    elif cmd == "acquire":
        who, purpose = argv[2], " ".join(argv[3:]) or "unspecified"
        if held and held["who"] != who:
            print(f"BUSY: {held['who']} since {held['since']} ({held['purpose']})")
            return 1
        LOCK.write_text(json.dumps({"who": who, "purpose": purpose, "since": time.strftime("%Y-%m-%d %H:%M")}))
        print("acquired")
    elif cmd == "release":
        if held and held["who"] == argv[2]:
            LOCK.unlink()
        print("released")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
