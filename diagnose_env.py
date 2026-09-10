import sys
import os

out = []
out.append("Python: " + sys.version)
out.append("stdout isatty: " + str(sys.stdout.isatty()))
out.append("stderr isatty: " + str(sys.stderr.isatty()))

for var in ["TERM", "WT_SESSION", "COLUMNS", "LINES", "COLORTERM",
            "TEXTUAL_DRIVER", "NO_COLOR", "ConEmuPID", "ANSICON"]:
    out.append(var + ": " + os.environ.get(var, "(nao definido)"))

with open("diag.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
