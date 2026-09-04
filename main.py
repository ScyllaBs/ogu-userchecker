import argparse
import csv
import itertools
import os
import string
import time
from pathlib import Path

import requests

LETTERS = string.ascii_lowercase
DIGITS = string.digits


def expand_pattern(pattern: str):
    pools = []
    for ch in pattern:
        if ch == "L":
            pools.append(LETTERS)
        elif ch == "N":
            pools.append(DIGITS)
        else:
            pools.append(ch)
    for parts in itertools.product(*pools):
        yield "".join(parts)


def write_candidates(items, output: str):
    path = Path(output)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(item + "\n")
            count += 1
    print(f"\nGenerated {count:,} candidates -> {path}\n")


def filter_words(input_path: str, min_length: int, max_length: int):
    seen = set()
    with open(input_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            word = raw.strip().lower()
            if not word or word in seen:
                continue
            if not word.isalpha():
                continue
            if min_length <= len(word) <= max_length:
                seen.add(word)
                yield word


def classify_response(response: requests.Response):
    available_status = os.getenv("AVAILABLE_STATUS")
    taken_status = os.getenv("TAKEN_STATUS")
    available_text = os.getenv("AVAILABLE_TEXT", "").strip().lower()
    taken_text = os.getenv("TAKEN_TEXT", "").strip().lower()

    body = response.text.lower()

    if available_text and available_text in body:
        return "available"
    if taken_text and taken_text in body:
        return "taken"

    if available_status and response.status_code == int(available_status):
        return "available"
    if taken_status and response.status_code == int(taken_status):
        return "taken"

    if not available_status and not taken_status:
        if response.status_code == 404:
            return "available"
        if response.status_code == 200:
            return "taken"

    if response.status_code == 429:
        return "rate_limited"
    return "unknown"


def check_username(username: str, session: requests.Session):
    template = os.getenv("CHECK_URL_TEMPLATE", "").strip()
    if not template:
        raise RuntimeError(
            "CHECK_URL_TEMPLATE is not configured. Add an authorized OGU availability endpoint first."
        )

    url = template.format(username=username)
    headers = {"User-Agent": "ogu-userchecker/1.0"}
    response = session.get(url, headers=headers, timeout=15)
    return classify_response(response), response.status_code


def load_already_checked(csv_path: Path):
    checked = set()
    if not csv_path.exists():
        return checked
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            username = row.get("username")
            if username:
                checked.add(username)
    return checked


def run_checker(input_path: str, output_path: str):
    delay = max(float(os.getenv("DELAY_SECONDS", "1.5")), 0.5)
    output = Path(output_path)
    checked = load_already_checked(output)
    new_file = not output.exists()
    session = requests.Session()

    with open(input_path, "r", encoding="utf-8") as source, output.open(
        "a", encoding="utf-8", newline=""
    ) as dest:
        writer = csv.writer(dest)
        if new_file:
            writer.writerow(["username", "status", "http_status"])

        for raw in source:
            username = raw.strip()
            if not username or username in checked:
                continue

            try:
                status, http_status = check_username(username, session)
            except requests.RequestException as exc:
                status, http_status = "error", ""
                print(f"[error] {username}: {exc}")
            except RuntimeError as exc:
                print(f"\n{exc}\n")
                return

            writer.writerow([username, status, http_status])
            dest.flush()
            checked.add(username)
            print(f"[{status}] @{username} ({http_status})")

            if status == "rate_limited":
                print("Rate limit detected; stopping safely.")
                return

            time.sleep(delay)


def interactive_menu():
    while True:
        print("=" * 48)
        print("           OGU USER CHECKER")
        print("=" * 48)
        print("1. Generate usernames")
        print("2. Check generated usernames")
        print("3. Show candidate count")
        print("4. Exit")
        print()

        choice = input("Choose an option: ").strip()

        if choice == "1":
            print("\nPattern examples:")
            print("  LLL = 3 letters")
            print("  LLN = 2 letters + 1 number")
            print("  L_L = letter + underscore + letter")
            print("  L.L = letter + dot + letter")
            pattern = input("Pattern: ").strip()
            if not pattern:
                print("No pattern entered.\n")
                continue
            write_candidates(expand_pattern(pattern), "candidates.txt")

        elif choice == "2":
            if not Path("candidates.txt").exists():
                print("\nNo candidates.txt yet. Generate usernames first.\n")
                continue
            print()
            run_checker("candidates.txt", "results.csv")

        elif choice == "3":
            path = Path("candidates.txt")
            if not path.exists():
                print("\nNo candidates generated yet.\n")
            else:
                with path.open("r", encoding="utf-8") as f:
                    count = sum(1 for line in f if line.strip())
                print(f"\n{count:,} candidates in candidates.txt\n")

        elif choice == "4":
            print("Bye.")
            return
        else:
            print("\nInvalid choice.\n")


def build_parser():
    parser = argparse.ArgumentParser(description="Configurable username generator/checker")
    sub = parser.add_subparsers(dest="command")

    generate = sub.add_parser("generate", help="Generate usernames from a pattern")
    generate.add_argument("--pattern", required=True, help="L=letter, N=number; other chars are literal")
    generate.add_argument("--output", default="candidates.txt")

    words = sub.add_parser("words", help="Filter a word list by length")
    words.add_argument("--input", required=True)
    words.add_argument("--min-length", type=int, required=True)
    words.add_argument("--max-length", type=int, required=True)
    words.add_argument("--output", default="candidates.txt")

    check = sub.add_parser("check", help="Check candidate usernames")
    check.add_argument("--input", default="candidates.txt")
    check.add_argument("--output", default="results.csv")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        interactive_menu()
    elif args.command == "generate":
        write_candidates(expand_pattern(args.pattern), args.output)
    elif args.command == "words":
        if args.min_length < 1 or args.max_length < args.min_length:
            parser.error("Invalid word length range")
        write_candidates(
            filter_words(args.input, args.min_length, args.max_length),
            args.output,
        )
    elif args.command == "check":
        run_checker(args.input, args.output)


if __name__ == "__main__":
    main()
