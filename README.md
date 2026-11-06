# Stocking Westminster

Which industries pay UK MPs? This pipeline joins the Register of Members' Financial Interests to Companies House, so declared money can be traced to a sector using official industry codes.

**This isn't a trade tracker, despite the name.** UK MPs don't report share trades. The register covers things like employment, donations, gifts, hospitality, land and shareholdings above set thresholds, so the question it can answer is "who is paid by which sector?", not "what did they buy last week?"

## What the first full run found

From the Commons register published on 29 June 2026, which has 4,112 entries:

| Finding | Figure |
|---|---|
| Largest sector we could attribute | Trade unions: £362k across 70 MPs |
| Most concentrated large sector | Banking and finance: £339k across 18 MPs |
| Largest single sector-attributed entry | £250,000 from Trailfinders to David Davis |
| Entries with a company number | 698 of 4,112, about a sixth |

**That last row is the main limit on everything above it.** Only entries with a company number can be matched to a sector. Sector totals therefore leave out most of the register, including large employment payments with no corporate donor recorded. They are a floor, not a full picture. Only entries with a stated money value are summed, so shareholdings are counted but not valued.

These are declarations in a public register. They don't imply wrongdoing by anyone named.

## How it works

```
fetch register  -->  clean  -->  company number  -->  Companies House  -->  SIC code
                                                                               |
                     CSV tables  <--  aggregate by sector, party and MP  <--  sector
```

1. **Fetch** the latest register from Parliament.
2. **Clean** the data, including money values and company numbers. Identifiers that Parliament doesn't source to Companies House are discarded rather than risk a false match.
3. **Resolve** each company number to its official SIC industry codes, with results cached in SQLite and requests kept under the free API limit.
4. **Tag** each entry with a SIC section and a plain-English bucket, such as gambling, fossil fuels or defence. The official SIC codes are the source of truth, and the buckets in `buckets.yaml` are my own grouping, so they involve judgement.
5. **Report** the results as CSV tables in `data/out/`, and print the headlines.

## Run it

You'll need Python 3.10+ and a free [Companies House API key](https://developer.company-information.service.gov.uk/) (Live environment, REST type).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export COMPANIES_HOUSE_API_KEY=your-key

sw fetch      # download the latest register
sw resolve    # look up company numbers
sw report     # build the tables and print the headlines
```

Add `--no-party` to `sw report` to skip the party lookup. The tests run offline with mocked responses:

```bash
pytest
```

## Awkward bits of the real data

- Parliament's PDF document route doesn't serve CSVs. The working route is `/Interests/csv?registerId={id}`.
- That "CSV" is really a ZIP of one CSV per category, so the loader checks the file's contents rather than trusting its extension.
- The newest register ID isn't always a usable one, so the fetcher works down the list until one returns real data.

## How I built it

I built this with Claude Code. I'm an economics student rather than a software engineer, so I chose the question and data sources and ran the pipeline on the real register, rather than writing the code by hand.

## Data sources

| Source | Used for | Access |
|---|---|---|
| Parliament Interests API | The register | Open, under the Open Parliament Licence |
| Parliament Members API | MP party and constituency | Open |
| Companies House API | Company SIC codes | Free API key |

The raw data and outputs aren't stored in this repo. Run the pipeline to generate them.
