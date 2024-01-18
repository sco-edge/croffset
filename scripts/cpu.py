#!/usr/bin/python3
import sys
import re
import argparse

def main(args):
    old = []
    new = []
    expr = re.compile(r"cpu(\d+): (\d+)%$")

    with open(args.filename) as file:
        lines = file.readlines()
        print("     ", end="")
        for i in range(0, 64):
            print(f"{i:>3}", end="")
        print("")
        for l in lines:
            tokens = list(map(str.strip, l.split(',')))
            index = str(tokens[0].split()[1])
            print(f"{index:>3}: ", end="")
            for token in tokens[1:]:
                match = expr.search(token)
                util = int(match.group(2))
                if args.color:
                    if util == 100:
                        print(f' \033[31m##\033[0m', end="")
                    elif util >= 80:
                        print(f'\033[31m{util:3}\033[0m', end="")
                    elif util >= 60:
                        print(f'\033[33m{util:3}\033[0m', end="")
                    elif util >= 20:
                        print(f"{util:3}", end="")
                    else:
                        print("  .", end="")
                else:
                    if util == 100:
                        print(f' ##', end="")
                    elif util >= 80:
                        print(f'{util:3}', end="")
                    elif util >= 60:
                        print(f'{util:3}', end="")
                    elif util >= 20:
                        print(f"{util:3}", end="")
                    else:
                        print("  .", end="")
            print("")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('--color', '-c', action='store_true')

    args = parser.parse_args()
    main(args)