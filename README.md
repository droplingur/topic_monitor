# Topic Monitor

Topic Monitor is a small local research tool for collecting web sources from the You.com Search API.

Its grounding workflow is:

```text
topic -> search API -> source records -> saved evidence -> AI answer
```

The search step finds useful sources. The saved title, URL, summary, and article text can then be passed to an AI model as evidence for a grounded answer.

## Setup

Create or activate a Python environment, then install the dependency:

```bash
python3 -m pip install python-dotenv
```

Create `topic_monitor/.env` from the example file:

```bash
cp .env.example .env
```

Add your You.com key to `.env`:

```env
YDC_API_KEY=your-key-here
```

Never commit `.env` or place an API key directly in Python source code. The folder's `.gitignore` already excludes `.env`.

## Command Line

Run a search directly from the terminal:

```bash
python3 topic_monitor.py --topic "renewable energy in Switzerland"
```

Example with filters:

```bash
python3 topic_monitor.py \
  --topic "AI regulation in Europe" \
  --count 5 \
  --freshness month \
  --language en \
  --domains europa.eu,ec.europa.eu \
  --extraction-mode highlights
```

`full_page` returns more article text. `highlights` returns shorter passages that are often cheaper and easier to pass to a model. Extraction can add latency or cost.

## Saved Data

Every successful search saves JSON and CSV files under a UTC date folder:

```text
topic_data/YYYY-MM-DD/topic-name_YYYYMMDD_HHMMSS.json
topic_data/YYYY-MM-DD/topic-name_YYYYMMDD_HHMMSS.csv
```

Each record contains:

```text
source
url
title
short_summary
article_text
published_date
extracted_date
```

Keep the `url` with any notes or AI-generated answer. It is the provenance link that lets a reader check the evidence.

## Project Structure

```text
topic_monitor/
├── .env                  # Local secrets; do not commit
├── .env.example          # Safe configuration template
├── topic_data/           # Saved search evidence
└── topic_monitor.py      # API client, normalization, and exports
```
