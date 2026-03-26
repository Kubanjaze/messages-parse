import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse, os, warnings
warnings.filterwarnings("ignore")
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Literal, Optional
import anthropic

load_dotenv()
os.environ.setdefault("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))


def pic50_to_class(pic50: float) -> str:
    if pic50 < 5.0:   return "inactive"
    elif pic50 < 6.0: return "weak"
    elif pic50 < 7.0: return "moderate"
    elif pic50 < 8.0: return "potent"
    else:             return "highly_potent"


class CompoundRecord(BaseModel):
    compound_name: str = Field(description="Compound identifier, e.g. benz_001_H")
    smiles: str = Field(description="SMILES string of the compound")
    pic50: float = Field(description="pIC50 activity value")
    activity_class: Literal["inactive", "weak", "moderate", "potent", "highly_potent"] = Field(
        description="Activity classification based on pIC50"
    )
    scaffold_family: Literal["benz", "naph", "ind", "quin", "pyr", "bzim", "other"] = Field(
        description="Scaffold family prefix from compound name"
    )
    confidence_note: Optional[str] = Field(
        default=None,
        description="Any ambiguity or uncertainty in the parsed record"
    )


def build_prompt(row) -> str:
    cls = pic50_to_class(row["pic50"])
    return (
        f"Extract structured information from this compound description.\n\n"
        f"Compound name: {row['compound_name']}\n"
        f"SMILES: {row['smiles']}\n"
        f"Measured pIC50: {row['pic50']:.2f}\n"
        f"Activity note: This compound is classified as {cls} based on its pIC50 value.\n"
        f"The compound name prefix indicates its scaffold family.\n\n"
        f"Parse this into a structured CompoundRecord."
    )


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--input", required=True)
    parser.add_argument("--n", type=int, default=5, help="Number of compounds to parse")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    df = pd.read_csv(args.input).head(args.n)
    client = anthropic.Anthropic()

    records = []
    total_input_tokens = 0
    total_output_tokens = 0
    n_correct = 0

    print(f"\nParsing {len(df)} compounds with {args.model}...\n")

    for _, row in df.iterrows():
        prompt = build_prompt(row)
        try:
            response = client.beta.messages.parse(
                model=args.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
                output_format=CompoundRecord,
            )
            parsed = response.content[0].parsed_output
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            # Validate against ground truth
            name_ok = parsed.compound_name == row["compound_name"]
            pic50_ok = abs(parsed.pic50 - row["pic50"]) < 0.1
            fam_ok = parsed.scaffold_family == row["compound_name"].split("_")[0]
            cls_ok = parsed.activity_class == pic50_to_class(row["pic50"])
            all_ok = name_ok and pic50_ok and fam_ok and cls_ok
            if all_ok:
                n_correct += 1

            print(f"  {row['compound_name']:20s}  name={'OK' if name_ok else 'FAIL'}  "
                  f"pic50={'OK' if pic50_ok else 'FAIL'}  fam={'OK' if fam_ok else 'FAIL'}  "
                  f"class={'OK' if cls_ok else 'FAIL'}")

            records.append({
                "compound_name": row["compound_name"],
                "parsed_name": parsed.compound_name,
                "parsed_smiles": parsed.smiles,
                "true_pic50": row["pic50"],
                "parsed_pic50": parsed.pic50,
                "true_activity_class": pic50_to_class(row["pic50"]),
                "parsed_activity_class": parsed.activity_class,
                "true_family": row["compound_name"].split("_")[0],
                "parsed_family": parsed.scaffold_family,
                "confidence_note": parsed.confidence_note,
                "all_fields_correct": all_ok,
            })
        except Exception as e:
            print(f"  {row['compound_name']:20s}  ERROR: {e}")
            records.append({"compound_name": row["compound_name"], "error": str(e)})

    # Save results
    res_df = pd.DataFrame(records)
    res_df.to_csv(os.path.join(args.output_dir, "parsed_records.csv"), index=False)

    # Cost estimate (Haiku: $0.80/MTok in, $4/MTok out)
    cost = (total_input_tokens / 1e6 * 0.80) + (total_output_tokens / 1e6 * 4.0)

    report = (
        f"Phase 55 — messages.parse() Structured Output\n"
        f"{'='*50}\n"
        f"Model:          {args.model}\n"
        f"Compounds:      {len(df)}\n"
        f"All-field accuracy: {n_correct}/{len(df)} ({n_correct/len(df):.0%})\n"
        f"Input tokens:   {total_input_tokens}\n"
        f"Output tokens:  {total_output_tokens}\n"
        f"Est. cost:      ${cost:.4f}\n"
    )
    print(f"\n{report}")
    with open(os.path.join(args.output_dir, "parse_report.txt"), "w") as f:
        f.write(report)
    print(f"Saved: {args.output_dir}/parsed_records.csv")
    print(f"Saved: {args.output_dir}/parse_report.txt")
    print("\nDone.")


if __name__ == "__main__":
    main()
