#!/usr/bin/env python
"""Generate a synthetic clinical evidence retrieval benchmark.

The benchmark is designed for retrieval research, not clinical decision support.
Each case asks for the compact evidence needed to evaluate a medication-related
clinical concern. Gold chunks form a small evidence chain: exposure, timing,
objective finding, patient-specific risk, and a reference/guideline clue.
Dangerous decoys are plausible alternative explanations or reassuring notes
that should not displace the required support in a top-5 return.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


CASES: list[dict[str, Any]] = [
    {
        "id": "delirium_anticholinergic",
        "question": (
            "Which five notes best support evaluating medication-induced "
            "delirium after diphenhydramine exposure?"
        ),
        "answer": "Diphenhydramine-associated anticholinergic delirium risk.",
        "evidence": [
            (
                "exposure",
                "Medication administration record: diphenhydramine 50 mg was given at 22:10 for sleep.",
                True,
            ),
            (
                "timing",
                "Nursing note: confusion, visual misperceptions, and agitation began around 01:30 after the sleep medication.",
                True,
            ),
            (
                "risk",
                "History summary: the patient is 82 years old with prior cognitive impairment and high fall risk.",
                True,
            ),
            (
                "exclusion",
                "Infectious workup note: urinalysis and chest radiograph did not show a clear infectious source.",
                False,
            ),
            (
                "reference",
                "Geriatric medication safety reference: first-generation antihistamines such as diphenhydramine can precipitate anticholinergic delirium in older adults.",
                True,
            ),
        ],
        "decoys": [
            "Progress note: delirium is likely due to a urinary tract infection because the patient is confused.",
            "Medication reconciliation: diphenhydramine appears on the home medication list without a documented allergy.",
            "Nursing handoff: the patient slept poorly before admission and often becomes irritable at night.",
            "Template note: mental status is stable and the current medication plan may continue.",
        ],
    },
    {
        "id": "serotonin_linezolid",
        "question": (
            "Which five notes best support evaluating serotonin toxicity after "
            "linezolid was started in a patient taking sertraline?"
        ),
        "answer": "Linezolid plus sertraline medication interaction concern.",
        "evidence": [
            (
                "exposure",
                "Medication order: linezolid was started this morning for resistant pneumonia.",
                True,
            ),
            (
                "background_med",
                "Home medication list: sertraline 100 mg daily was continued on admission.",
                True,
            ),
            (
                "finding",
                "Nursing assessment: tremor, inducible clonus, diaphoresis, and new agitation were documented after antibiotic initiation.",
                True,
            ),
            (
                "vitals",
                "Vital-sign trend: temperature and heart rate rose after the new antibiotic dose.",
                False,
            ),
            (
                "reference",
                "Drug-interaction reference: linezolid has monoamine oxidase inhibitor activity and can increase serotonin-toxicity risk with SSRIs.",
                True,
            ),
        ],
        "decoys": [
            "Infectious disease note: persistent fever is expected with severe pneumonia during the first treatment day.",
            "Medication history: sertraline was tolerated for several years before this admission.",
            "Nursing note: anxiety could explain agitation because the patient dislikes the mask.",
            "Template note: no medication interactions were found by the admission checklist.",
        ],
    },
    {
        "id": "warfarin_tmp_smx",
        "question": (
            "Which five notes best support evaluating supratherapeutic INR after "
            "trimethoprim-sulfamethoxazole was prescribed with warfarin?"
        ),
        "answer": "Warfarin interaction with trimethoprim-sulfamethoxazole.",
        "evidence": [
            (
                "background_med",
                "Anticoagulation record: warfarin 5 mg nightly is active for atrial fibrillation.",
                True,
            ),
            (
                "exposure",
                "Outpatient prescription: trimethoprim-sulfamethoxazole was started three days ago for cellulitis.",
                True,
            ),
            (
                "lab",
                "Laboratory result: INR increased from 2.4 to 5.8 after the antibiotic was started.",
                True,
            ),
            (
                "finding",
                "Triage note: the patient reports new gum bleeding and bruising.",
                True,
            ),
            (
                "reference",
                "Anticoagulation reference: trimethoprim-sulfamethoxazole can potentiate warfarin and raise INR.",
                True,
            ),
        ],
        "decoys": [
            "Diet history: the patient ate fewer leafy greens during the holiday weekend.",
            "Medication list: warfarin dose was unchanged for several months before this visit.",
            "Clinic note: cellulitis has improved and the antibiotic should be effective.",
            "Template note: no active bleeding was observed during initial registration.",
        ],
    },
    {
        "id": "metformin_renal_acidosis",
        "question": (
            "Which five notes best support evaluating metformin-associated risk "
            "during acute kidney injury and metabolic acidosis?"
        ),
        "answer": "Metformin safety concern in acute kidney injury with acidosis.",
        "evidence": [
            (
                "background_med",
                "Medication reconciliation: metformin 1000 mg twice daily was continued after admission.",
                True,
            ),
            (
                "lab",
                "Chemistry panel: creatinine rose from 1.0 to 2.9 mg/dL after contrast exposure.",
                True,
            ),
            (
                "acid_base",
                "Blood gas: metabolic acidosis is present with elevated lactate.",
                True,
            ),
            (
                "timing",
                "Procedure note: iodinated contrast CT was performed the day before kidney function worsened.",
                False,
            ),
            (
                "reference",
                "Medication safety reference: metformin should be held during significant acute kidney injury or lactic acidosis concern.",
                True,
            ),
        ],
        "decoys": [
            "Diabetes clinic note: metformin previously improved A1c and was well tolerated.",
            "Nutrition note: poor oral intake may explain mild nausea.",
            "Radiology note: the CT scan did not show bowel ischemia.",
            "Template note: home medications may be resumed when clinically appropriate.",
        ],
    },
    {
        "id": "digoxin_toxicity",
        "question": (
            "Which five notes best support evaluating possible digoxin toxicity "
            "after renal decline and hypokalemia?"
        ),
        "answer": "Digoxin toxicity risk amplified by renal dysfunction and hypokalemia.",
        "evidence": [
            (
                "background_med",
                "Medication list: digoxin 0.25 mg daily is active for rate control.",
                True,
            ),
            (
                "lab",
                "Basic metabolic panel: potassium is 2.9 mmol/L after aggressive diuresis.",
                True,
            ),
            (
                "renal",
                "Renal trend: estimated glomerular filtration rate declined sharply during the admission.",
                True,
            ),
            (
                "finding",
                "Telemetry note: nausea, visual halos, and new ventricular ectopy were documented.",
                True,
            ),
            (
                "reference",
                "Cardiology reference: renal impairment and hypokalemia increase digoxin toxicity risk.",
                True,
            ),
        ],
        "decoys": [
            "Heart failure note: diuresis improved oxygen requirement and edema.",
            "Medication history: digoxin has been listed for several years without prior toxicity.",
            "Ophthalmology note: the patient wears corrective lenses at baseline.",
            "Template note: telemetry artifact can occur during patient movement.",
        ],
    },
    {
        "id": "hit_heparin_platelets",
        "question": (
            "Which five notes best support evaluating heparin-induced thrombocytopenia "
            "after platelet decline and new thrombosis?"
        ),
        "answer": "Possible heparin-induced thrombocytopenia evidence chain.",
        "evidence": [
            (
                "exposure",
                "Medication administration record: unfractionated heparin infusion began five days ago.",
                True,
            ),
            (
                "lab",
                "Platelet trend: platelet count fell by more than fifty percent after heparin exposure.",
                True,
            ),
            (
                "finding",
                "Ultrasound report: new lower-extremity deep vein thrombosis was identified.",
                True,
            ),
            (
                "timing",
                "Progress note: thrombocytopenia timing is compatible with immune-mediated heparin reaction.",
                True,
            ),
            (
                "reference",
                "Hematology reference: platelet fall with thrombosis several days after heparin exposure raises concern for HIT.",
                True,
            ),
        ],
        "decoys": [
            "Sepsis note: critical illness can lower platelet count through multiple mechanisms.",
            "Procedure note: the central line site has no active bleeding.",
            "Medication note: heparin prophylaxis is commonly used after surgery.",
            "Template note: thrombocytopenia is mild and requires routine monitoring.",
        ],
    },
]


NOISE_TOPICS = [
    "discharge planning",
    "insurance authorization",
    "meal preference",
    "room transfer",
    "physical therapy scheduling",
    "routine vaccination history",
    "family contact update",
    "billing question",
]


def case_documents(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Build benchmark documents for one clinical case.

    Args:
        case: Clinical case definition.

    Returns:
        Documents containing target evidence, dangerous decoys, and noise.
    """
    docs: list[dict[str, Any]] = []
    for index, (category, text, critical) in enumerate(case["evidence"], 1):
        docs.append(
            {
                "id": f"{case['id']}-evidence-{index}",
                "text": f"Clinical evidence note: {text}",
                "metadata": {
                    "source": "synthetic_clinical",
                    "domain": "medicine",
                    "case": case["id"],
                    "title": f"{case['id']} {category}",
                    "category": category,
                    "gold": "target",
                    "safety_critical": critical,
                },
            }
        )

    for index, text in enumerate(case["decoys"], 1):
        docs.append(
            {
                "id": f"{case['id']}-decoy-{index}",
                "text": f"Clinical decoy note: {text}",
                "metadata": {
                    "source": "synthetic_clinical",
                    "domain": "medicine",
                    "case": case["id"],
                    "title": f"{case['id']} plausible decoy {index}",
                    "category": "dangerous_decoy",
                    "gold": "dangerous_decoy",
                    "safety_critical": False,
                },
            }
        )

    for index, topic in enumerate(NOISE_TOPICS[:4], 1):
        docs.append(
            {
                "id": f"{case['id']}-noise-{index}",
                "text": (
                    f"Clinical background note: {topic} was discussed. "
                    "This note is patient-context noise and does not resolve "
                    f"the question: {case['question']}"
                ),
                "metadata": {
                    "source": "synthetic_clinical",
                    "domain": "medicine",
                    "case": case["id"],
                    "title": f"{case['id']} background {index}",
                    "category": "noise",
                    "gold": "noise",
                    "safety_critical": False,
                },
            }
        )
    return docs


def distractor_document(index: int) -> dict[str, Any]:
    """Build a cross-case clinical distractor document.

    Args:
        index: Stable numeric document index.

    Returns:
        Distractor document.
    """
    topic = random.choice(NOISE_TOPICS)
    return {
        "id": f"clinical-distractor-{index:05d}",
        "text": (
            f"Clinical operations note: {topic} is pending. The note mentions "
            "medications, laboratory review, assessment, and plan but contains "
            "no case-specific evidence chain."
        ),
        "metadata": {
            "source": "synthetic_clinical",
            "domain": "medicine",
            "case": "distractor",
            "title": f"clinical distractor {index}",
            "category": "distractor",
            "gold": "distractor",
            "safety_critical": False,
        },
    }


def generate(total_distractors: int = 300, seed: int = 2049) -> dict[str, Any]:
    """Generate the clinical evidence benchmark.

    Args:
        total_distractors: Number of cross-case distractor chunks.
        seed: Random seed for deterministic generation.

    Returns:
        Benchmark payload with corpus, cases, and metadata.
    """
    random.seed(seed)
    corpus: list[dict[str, Any]] = []
    cases: dict[str, dict[str, Any]] = {}
    for case in CASES:
        corpus.extend(case_documents(case))
        cases[case["id"]] = {
            "domain": "medicine",
            "query": case["question"],
            "answer": case["answer"],
            "task": "clinical_evidence_retrieval",
            "required_support_count": len(case["evidence"]),
        }

    for index in range(total_distractors):
        corpus.append(distractor_document(index))

    random.shuffle(corpus)
    return {
        "corpus": corpus,
        "cases": cases,
        "metadata": {
            "description": (
                "Synthetic clinical evidence retrieval benchmark for compact "
                "support-chain recovery. Not medical advice or clinical "
                "decision support."
            ),
            "case_count": len(CASES),
            "total_documents": len(corpus),
            "distractor_documents": total_distractors,
            "seed": seed,
        },
    }


def main() -> None:
    """Generate the benchmark JSON from command-line arguments.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--distractors", type=int, default=300)
    parser.add_argument("--seed", type=int, default=2049)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("clinical_evidence_benchmark.json"),
    )
    args = parser.parse_args()

    payload = generate(total_distractors=args.distractors, seed=args.seed)
    args.output.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {args.output}")
    print(f"Documents: {payload['metadata']['total_documents']}")
    print(f"Cases: {len(payload['cases'])}")


if __name__ == "__main__":
    main()
