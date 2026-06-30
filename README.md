# Multi-Source Candidate Data Transformer

> Eightfold Engineering Intern (Jul–Dec 2026) — Assignment

A deterministic, source-aware pipeline that ingests messy candidate data from
multiple sources and emits one clean, canonical profile per candidate — with
**provenance** for every value and a **confidence** score per record. A runtime
config can reshape the output (custom schema) without code changes.

---

## Quick start

```bash
# Python 3.10+ recommended (no third-party deps required for the core pipeline).
cd eightfold

# 1) Default canonical schema → outputs/default_output.json
python -m src.cli \
  --csv samples/recruiter.csv \
  --ats samples/ats.json \
  --resumes samples/resumes \
  --notes samples/notes \
  --out outputs/default_output.json

# 2) Custom-config projection → outputs/custom_output.json
python -m src.cli \
  --csv samples/recruiter.csv \
  --ats samples/ats.json \
  --resumes samples/resumes \
  --notes samples/notes \
  --config configs/custom.json \
  --out outputs/custom_output.json

# 3) Tests
python -m unittest discover -s tests -v
```

Pass any combination of `--csv / --ats / --resumes / --notes`; missing sources
are skipped gracefully. Use `--strict` to fail on schema-validation errors.

---

## Pipeline

`detect → extract → normalize → merge → confidence → project-to-output → validate`

1. **detect** — `src/pipeline.detect_and_extract` figures out which sources to
   run from CLI flags; missing/malformed sources are skipped (never crash).
2. **extract** — one module per source (`src/extract/*.py`) produces *partial*
   canonical profiles. Extractors never invent data: missing fields stay
   `null` / `[]`.
3. **normalize** — `src/normalize.py` canonicalizes phones (E.164), dates
   (`YYYY-MM`), country (ISO-3166 α-2), skills (`js → JavaScript`, `k8s →
   Kubernetes`, …), and emails (lowercased + regex-validated).
4. **merge** — `src/merge.py` runs union-find identity resolution over
   normalized email, phone, and name. Scalars are picked by **source
   priority**; lists are unioned & deduped; skills are merged with
   diminishing-returns confidence boosting.
5. **confidence** — `src/confidence.py` computes per-field scores from source
   priority + corroboration, then a weighted `overall_confidence` in `[0, 1]`.
6. **project-to-output** — `src/project.py` takes a runtime config and reshapes
   the canonical record (subset, rename via `from`, per-field normalization,
   missing handling). The internal canonical record is never mutated.
7. **validate** — `src/validate.py` checks the produced record against the
   canonical JSON schema (or the projected shape). Errors are reported, not
   fabricated.

## Sources

Group A — **structured** (any one):
- `recruiter_csv` — `samples/recruiter.csv`
- `ats_json` — `samples/ats.json` (different field names by design)

Group B — **unstructured** (any one):
- `resume` — plain-text resumes in `samples/resumes/*.txt`
- `recruiter_notes` — recruiter free-text in `samples/notes/*.txt`

Source trust (higher wins on conflict):

| Source            | Priority |
|-------------------|---------:|
| `ats_json`        | 5        |
| `recruiter_csv`   | 4        |
| `resume`          | 3        |
| `recruiter_notes` | 2        |

## Canonical output schema

```
candidate_id, full_name, emails[], phones[] (E.164),
location { city, region, country (ISO-3166 α-2) },
links { linkedin, github, portfolio, other[] },
headline, years_experience,
skills [ { name, confidence, sources[] } ],
experience [ { company, title, start (YYYY-MM), end, summary } ],
education [ { institution, degree, field, end_year } ],
provenance [ { field, source, method } ],
overall_confidence
```

A draft-07 JSON-schema description lives in `src/schema.DEFAULT_SCHEMA`.

## Custom config (runtime projection)

`configs/custom.json` shows a typical projection:

```json
{
  "fields": [
    { "path": "full_name",     "type": "string",   "required": true },
    { "path": "primary_email", "from": "emails[0]", "type": "string",   "required": true },
    { "path": "phone",         "from": "phones[0]", "type": "string",   "normalize": "E164" },
    { "path": "country",       "from": "location.country", "type": "string" },
    { "path": "skills",        "from": "skills[].name",    "type": "string[]", "normalize": "canonical" }
  ],
  "include_confidence": true,
  "include_provenance": false,
  "on_missing": "null"
}
```

`from` supports dotted paths, `[N]` indexing, and `[]` list-flattening. The
projection layer is the **only** place where the output shape changes — the
internal canonical record is unchanged. Missing-value behaviour is configurable
(`null` / `omit` / `error`).

## Edge cases handled

- Same person, different sources, different formats (e.g. `(415) 555-2671` vs
  `+1-415-555-2671` vs `4155552671`) → merged into one record.
- Same person, name variations (`Jane Doe` vs `Jane D.`) — matched via shared
  email/phone.
- Garbage rows (e.g. country `"Atlantis"`, phone `"abc"`) — fields drop to
  `null`, no invented values.
- Missing source file — warning logged, pipeline continues.
- Conflicting headline / company between CSV and ATS — source priority decides.
- Recruiter notes have no email → kept as a separate record (rather than
  guessing identity).

## Deliberately descoped (time budget)

- Live GitHub / LinkedIn fetching (would require network + rate-limit handling;
  the source modules are stubbed-ready).
- PDF / DOCX → text conversion (resumes are pre-extracted `.txt`).
- Fuzzy name matching (currently exact normalized match). Trade-off: avoids
  false merges; safer for hiring decisions.

## Repo layout

```
eightfold/
├── src/
│   ├── cli.py              # argparse entrypoint
│   ├── pipeline.py         # detect → extract → … → validate
│   ├── schema.py           # canonical schema + JSON-Schema
│   ├── normalize.py        # phones / dates / country / skills / email
│   ├── merge.py            # identity resolution + conflict policy
│   ├── confidence.py       # per-field + overall confidence
│   ├── project.py          # runtime config projection
│   ├── validate.py         # tiny JSON-Schema-ish validator
│   └── extract/
│       ├── csv_source.py
│       ├── ats_source.py
│       ├── resume_source.py
│       └── notes_source.py
├── samples/                # realistic messy inputs
├── configs/                # default + custom projection configs
├── outputs/                # produced JSON outputs (checked in for review)
├── tests/test_pipeline.py  # 14 unit + integration tests
├── design/                 # one-page Stage-1 design PDF
└── README.md
```

## Demo video

A ~2-minute screen recording walks through:
1. Running the pipeline end-to-end on `samples/`.
2. Default output → merged Jane Doe, normalized phones, ISO countries, canonical
   skills, provenance, confidence.
3. Custom-config output → same engine, different shape.
4. One design decision I'm proud of (provenance as a first-class field) and
   one edge case (garbage source row degrading gracefully).
