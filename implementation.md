# Phase 55 — messages.parse() Structured Compound Record

**Version:** 1.2 | **Tier:** Standard | **Date:** 2026-03-26

## Goal
Demonstrate typed structured output using `client.beta.messages.parse()` (Anthropic beta SDK).
Parse natural language SAR descriptions into validated Pydantic CompoundRecord objects.

CLI: `python main.py --input data/compounds.csv --n 5`

Outputs: parsed_records.csv, parse_report.txt

## Logic
- Load N compounds from CSV (name, SMILES, pIC50)
- Build a natural language description for each: "Compound X has SMILES Y and pIC50 Z..."
- Use `client.beta.messages.parse()` with a Pydantic model to extract structured fields
- Pydantic model: CompoundRecord(name, smiles, pic50, activity_class, scaffold_family)
- Validate: compare parsed fields against ground truth CSV
- Report: parse accuracy, field-level validation, token usage, cost estimate

## Key Concepts
- `client.beta.messages.parse()` returns a typed Pydantic object, not raw text
- `output_format=CompoundRecord` (not `response_format`) sets the Pydantic schema
- Structured output is accessed via `response.content[0].parsed_output`
- activity_class: Literal["inactive", "weak", "moderate", "potent", "highly_potent"]
- scaffold_family: Literal["benz", "naph", "ind", "quin", "pyr", "bzim", "other"]

## Deviations from Plan
- API is `client.beta.messages.parse()` not `client.messages.parse()`
- Parameter is `output_format=` not `response_format=`
- Result is `.content[0].parsed_output` not `.content[0].parsed`

## Results
| Metric | Value |
|--------|-------|
| Compounds parsed | 5/5 |
| All-field accuracy | 100% (5/5) |
| Input tokens | 3190 |
| Output tokens | 352 |
| Est. cost | $0.0040 |

All fields (compound_name, pic50, scaffold_family, activity_class) parsed correctly on first pass.
