# OGU Username Checker

A small configurable username generator/checker scaffold for OGU.

## What it does

- Generate letter-only usernames such as 1L, 2L, 3L, etc.
- Optionally include digits and separators such as `_`, `.`, and `-`.
- Generate by pattern, e.g. `LLL`, `LLN`, `L_L`, `L.L`.
- Filter words from a local wordlist by minimum/maximum length.
- Save generated candidates and results locally.
- Use a configurable delay between remote checks.

## Important

This repository does **not** include a private or reverse-engineered OGU endpoint. Configure `CHECK_URL_TEMPLATE` only if OGU provides an endpoint you are authorized to use, for example:

```bash
export CHECK_URL_TEMPLATE='https://example.com/check?username={username}'
```

The checker intentionally runs sequentially and respects `DELAY_SECONDS`. Do not use it to bypass rate limits, CAPTCHAs, access controls, or other protections.

## Run in Codespaces

```bash
python -m pip install -r requirements.txt
python main.py generate --pattern LLL --output candidates.txt
python main.py check --input candidates.txt
```

Examples:

```bash
# all two-letter combinations
python main.py generate --pattern LL

# letter/letter/number
python main.py generate --pattern LLN

# letters with a literal underscore in the middle
python main.py generate --pattern L_L

# words between 4 and 6 characters
python main.py words --input words.txt --min-length 4 --max-length 6 --output candidates.txt
```

Pattern symbols:

- `L` = lowercase letter a-z
- `N` = digit 0-9
- `_`, `.`, `-` = literal separator
- any other character = literal character

## Checker response modes

By default, a response is considered available when its HTTP status is `404`. You can change this with environment variables:

```bash
export AVAILABLE_STATUS=404
export TAKEN_STATUS=200
export DELAY_SECONDS=1.5
```

You can also make availability depend on response text:

```bash
export AVAILABLE_TEXT='available'
export TAKEN_TEXT='taken'
```

If neither status nor text gives a clear answer, the result is saved as `unknown` rather than guessed.
