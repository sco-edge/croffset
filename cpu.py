import sys
import re

old = []
new = []
expr = re.compile(r"cpu(\d+): (\d+)%$")

with open(sys.argv[1]) as file:
    lines = file.readlines()
    for l in lines:
        tokens = list(map(str.strip, l.split(',')))
        print(f"{tokens[0]}: ", end="")
        for token in tokens[1:]:
            match = expr.search(token)
            if int(match.group(2)) > 50:
                print(f"C{match.group(1)}: {match.group(2)}%, ", end="")
        print("")

