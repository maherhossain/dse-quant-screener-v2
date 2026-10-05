@'

# DSE Quant Screener v2

Research-driven quantitative trading system for the Dhaka Stock Exchange.
See CONTEXT.md for scope, hypotheses, and research-integrity rules.

## Two-machine setup

| Machine | Project root                         | MySQL  | Python |
| ------- | ------------------------------------ | ------ | ------ |
| Laptop  | D:\laragon\www\dse-quant-screener-v2 | 8.0.30 | 3.12.0 |
| Office  | C:\laragon\www\dse-quant-screener-v2 | 8.4.3  | 3.12.0 |

MySQL version differs between machines. All DDL must be 8.0-compatible.
No 8.4-only syntax. Verify collation with SHOW TABLE STATUS after schema load.

## Rules

- Code reads paths via pathlib.Path(**file**) — never hardcode drive letters.
- Credentials come from .env (git-ignored), never from code.
- Dependencies pinned in requirements.txt with ==.
- audit/raw/ and data/ are git-ignored.
- Every experiment logs git rev-parse HEAD.

## First-time setup on a machine

    git clone https://github.com/YOURNAME/dse-quant-screener-v2.git
    cd dse-quant-screener-v2
    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    Copy-Item .env.example .env
    # edit .env with this machine s DB credentials

## Daily workflow

    git pull --rebase
    # ... work ...
    git add <files>
    git commit -m "Module X: ..."
    git push

'@ | Set-Content -Encoding UTF8 README.md
