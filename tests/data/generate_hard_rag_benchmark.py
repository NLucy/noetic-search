#!/usr/bin/env python
"""Generate a hard mixed-domain benchmark for RAG vs basin retrieval."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


CASES = [
    {
        "id": "payments_release",
        "domain": "software",
        "subject": "payments platform release",
        "query": "Is the payments platform release safe to launch tonight?",
        "decoy_stance": "launch-ready-decoy",
        "target_stance": "launch-risk",
        "noise_stance": "release-noise",
        "decoys": [
            "Executive release note says the payments platform is safe to launch tonight and all deployment checks passed.",
            "Launch readiness announcement confirms the payments platform release is approved, tested, and production ready.",
            "Program status update says the payments release has green status and should proceed tonight.",
            "Deployment checklist summary says all go-live items for payments were completed successfully.",
        ],
        "evidence": [
            ("database", "Schema migration for payments requires manual intervention and cannot auto-rollback."),
            ("performance", "Load tests reveal memory pressure and latency spikes during burst checkout traffic."),
            ("monitoring", "Canary deployments showed elevated authorization errors in payment processing."),
            ("infrastructure", "Load balancer configuration is incompatible with the new payments service mesh."),
            ("operations", "Rollback procedure is incomplete and recovery time exceeds incident SLA requirements."),
            ("security", "Token refresh failures appear when the new payment gateway is under high concurrency."),
        ],
    },
    {
        "id": "hospital_device",
        "domain": "healthcare_ops",
        "subject": "infusion pump firmware",
        "query": "Can the hospital deploy the new infusion pump firmware this weekend?",
        "decoy_stance": "firmware-ready-decoy",
        "target_stance": "firmware-risk",
        "noise_stance": "hospital-noise",
        "decoys": [
            "Vendor bulletin says the infusion pump firmware is approved and ready for weekend deployment.",
            "Implementation memo confirms the firmware update passed acceptance checks for hospital rollout.",
            "Training newsletter says nurses can expect a safe and smooth infusion pump firmware upgrade.",
            "Procurement summary lists the pump firmware as validated, complete, and deployment ready.",
        ],
        "evidence": [
            ("device_logs", "Pump logs show intermittent dose-rate alarms after firmware update under battery power."),
            ("nursing", "Nursing simulation found the new confirmation screen delays emergency medication changes."),
            ("biomed", "Biomedical engineering reports rollback requires vendor unlock codes not available on weekends."),
            ("network", "Wireless reconnect behavior drops telemetry during room-to-room transport."),
            ("compliance", "Validation evidence omits pediatric dose-limit regression tests."),
            ("support", "Vendor support escalation is unavailable during the proposed weekend window."),
        ],
    },
    {
        "id": "bank_model",
        "domain": "finance",
        "subject": "credit risk model",
        "query": "Should the bank approve the new credit risk model for production?",
        "decoy_stance": "model-approved-decoy",
        "target_stance": "model-risk",
        "noise_stance": "bank-noise",
        "decoys": [
            "Model governance summary says the credit risk model is approved for production use.",
            "Analytics leadership memo confirms the new credit model passed validation and is ready.",
            "Release communication says the bank can safely deploy the credit risk model.",
            "Dashboard status marks the model production approval as green and complete.",
        ],
        "evidence": [
            ("fairness", "Segment analysis shows elevated false declines for thin-file applicants."),
            ("drift", "Recent macroeconomic data produces score drift outside the monitoring threshold."),
            ("explainability", "Adverse-action reason codes do not match the strongest model features."),
            ("data_quality", "Training data excludes the newest hardship-program outcomes."),
            ("audit", "Independent validation notes unresolved challenger-model disagreement."),
            ("operations", "Manual override volume doubles during pilot branch testing."),
        ],
    },
    {
        "id": "factory_robot",
        "domain": "industrial",
        "subject": "factory robot speed increase",
        "query": "Is the factory robot speed increase safe for the night shift?",
        "decoy_stance": "robot-safe-decoy",
        "target_stance": "robot-risk",
        "noise_stance": "factory-noise",
        "decoys": [
            "Automation update says the robot speed increase is safe and approved for night shift.",
            "Manufacturing announcement confirms the robot speed change passed safety review.",
            "Shift briefing says operators can run the faster robot profile with confidence.",
            "Productivity memo marks the robot speed increase as ready and fully tested.",
        ],
        "evidence": [
            ("safety", "Light curtain near the robot cell intermittently fails self-test after speed increase."),
            ("maintenance", "Gripper wear exceeds inspection limits during high-speed cycle trials."),
            ("training", "Night shift operators have not completed the updated lockout procedure."),
            ("quality", "Fast cycles increase part misalignment rejects on the downstream station."),
            ("controls", "Emergency stop latency rises when the conveyor and robot accelerate together."),
            ("staffing", "No controls engineer is scheduled during the proposed night shift rollout."),
        ],
    },
    {
        "id": "privacy_launch",
        "domain": "privacy",
        "subject": "EU personalized ads feature",
        "query": "Can the company launch the personalized ads feature in the EU?",
        "decoy_stance": "ads-launch-decoy",
        "target_stance": "ads-compliance-risk",
        "noise_stance": "privacy-noise",
        "decoys": [
            "Marketing launch plan says the personalized ads feature is approved for EU release.",
            "Product memo confirms personalized ads are ready to launch in the EU market.",
            "Readiness dashboard marks EU personalized ads as compliant and go-live ready.",
            "Launch announcement says the ads feature passed review and can ship.",
        ],
        "evidence": [
            ("consent", "Consent logs do not distinguish personalized ads from analytics tracking."),
            ("retention", "Profile retention exceeds the regional data minimization limit."),
            ("dsar", "Deletion requests leave audience membership records in the ad platform."),
            ("legal", "Legitimate-interest assessment is missing for cross-device matching."),
            ("vendor", "Ad vendor contract lacks the required subprocessor update notice."),
            ("product", "Preference center copy does not describe automated audience inference."),
        ],
    },
    {
        "id": "supply_supplier",
        "domain": "supply_chain",
        "subject": "battery supplier launch build",
        "query": "Should we switch the launch build to the new battery supplier?",
        "decoy_stance": "supplier-ready-decoy",
        "target_stance": "supplier-risk",
        "noise_stance": "supply-noise",
        "decoys": [
            "Sourcing memo says the new battery supplier is approved and ready for launch builds.",
            "Supplier onboarding summary confirms the battery vendor passed qualification.",
            "Launch planning note says switching to the new battery supplier is safe.",
            "Procurement dashboard marks the battery supplier change as green.",
        ],
        "evidence": [
            ("quality", "Incoming inspection found swelling in cells from two recent supplier lots."),
            ("logistics", "Supplier lead time slips when shipments require cold-chain handling."),
            ("certification", "Regional safety certificate covers the prior cell chemistry, not the launch version."),
            ("manufacturing", "Pack assembly torque settings differ from the supplier process guide."),
            ("field", "Pilot devices show faster capacity fade after high-temperature storage."),
            ("finance", "Expedite fees erase the expected cost savings for launch volume."),
        ],
    },
    {
        "id": "legal_contract",
        "domain": "legal_ops",
        "subject": "enterprise customer contract",
        "query": "Can sales sign the new enterprise customer contract this week?",
        "decoy_stance": "contract-ready-decoy",
        "target_stance": "contract-risk",
        "noise_stance": "legal-noise",
        "decoys": [
            "Sales operations note says the enterprise contract is approved and ready for signature.",
            "Account update confirms legal review is complete and sales can sign this week.",
            "Deal desk summary marks the customer contract as ready and low risk.",
            "Customer success memo says the enterprise agreement can proceed immediately.",
        ],
        "evidence": [
            ("liability", "Liability cap was removed from the newest customer redline."),
            ("data", "Data processing addendum conflicts with the customer's audit-right language."),
            ("sla", "Service credit terms exceed the support team's approved SLA limits."),
            ("security", "Security exhibit references a certification that expires before contract start."),
            ("finance", "Payment schedule creates revenue recognition risk under the proposed delivery dates."),
            ("product", "Custom feature obligation is not on the committed roadmap."),
        ],
    },
    {
        "id": "cyber_patch",
        "domain": "cybersecurity",
        "subject": "identity provider patch",
        "query": "Is the emergency identity provider patch safe to deploy globally?",
        "decoy_stance": "patch-ready-decoy",
        "target_stance": "patch-risk",
        "noise_stance": "cyber-noise",
        "decoys": [
            "Security bulletin says the identity provider patch is tested and safe for global deployment.",
            "Emergency patch note confirms all identity provider checks passed.",
            "Incident command update says the patch is approved and ready to deploy globally.",
            "Vendor advisory marks the identity provider patch as stable and production ready.",
        ],
        "evidence": [
            ("authentication", "Pilot users report intermittent MFA challenge loops after the identity patch."),
            ("regions", "Asia-Pacific tenants receive stale signing keys during staged rollout."),
            ("integrations", "Legacy SAML applications fail metadata refresh with the patched provider."),
            ("support", "Helpdesk ticket volume triples during the limited pilot."),
            ("rollback", "Rollback requires rotating client secrets for high-value applications."),
            ("monitoring", "Session error telemetry is sampled too heavily to detect regional failure quickly."),
        ],
    },
    {
        "id": "energy_grid",
        "domain": "energy",
        "subject": "grid balancing algorithm",
        "query": "Can the utility activate the new grid balancing algorithm tomorrow?",
        "decoy_stance": "grid-ready-decoy",
        "target_stance": "grid-risk",
        "noise_stance": "energy-noise",
        "decoys": [
            "Operations memo says the grid balancing algorithm is approved for activation tomorrow.",
            "Control room summary confirms the balancing algorithm passed readiness checks.",
            "Vendor note says the grid algorithm is safe, stable, and ready.",
            "Deployment dashboard marks tomorrow's grid balancing activation as green.",
        ],
        "evidence": [
            ("forecasting", "Wind forecast error causes the balancing algorithm to over-dispatch reserve units."),
            ("controls", "Fallback controller handoff oscillates during simulated demand spikes."),
            ("market", "Price signal ingestion lags behind the five-minute dispatch window."),
            ("compliance", "Regulatory audit trail omits operator override explanations."),
            ("training", "Control room staff have not completed the override drill."),
            ("telemetry", "Substation telemetry gaps hide feeder overload during stress replay."),
        ],
    },
    {
        "id": "education_exam",
        "domain": "education",
        "subject": "automated exam proctoring system",
        "query": "Should the district use the new automated exam proctoring system?",
        "decoy_stance": "proctor-ready-decoy",
        "target_stance": "proctor-risk",
        "noise_stance": "education-noise",
        "decoys": [
            "Vendor implementation note says automated exam proctoring is approved and ready for district use.",
            "District technology memo confirms the proctoring system passed review.",
            "Pilot summary says the automated proctoring rollout is safe and ready.",
            "Procurement dashboard marks the exam proctoring system as green.",
        ],
        "evidence": [
            ("accessibility", "Accessibility testing shows screen-reader conflicts during identity verification."),
            ("equity", "Pilot flags are higher for students with unstable home internet connections."),
            ("privacy", "Retention policy stores room scans longer than the district limit."),
            ("support", "Helpdesk cannot staff live exam windows across all schools."),
            ("appeals", "Appeal workflow lacks a documented process for false-positive flags."),
            ("devices", "Older district laptops fail the required camera check."),
        ],
    },
]


RUBBISH_DOMAINS = [
    "gardening",
    "gaming",
    "travel",
    "cooking",
    "sports",
    "real_estate",
    "weather",
    "entertainment",
    "productivity",
    "astrology",
]

RUBBISH_SENTENCES = [
    "This note repeats an unrelated status update with confident language but no operational evidence.",
    "A discussion thread mentions launch readiness, safety, approval, and deployment without naming the relevant system.",
    "The archive contains a stale dashboard screenshot and a vague statement that everything looks green.",
    "Someone in chat says the plan sounds good, although the message is about a different project.",
    "A copied template claims all checks passed but the listed owner and date do not match the decision.",
    "This document is mostly filler about process, meetings, dashboards, and readiness ceremonies.",
]

SOURCES = ["exec", "lab", "ops", "review", "vendor", "support", "audit", "slack", "forum"]

VARIANT_MARKERS = [
    "north",
    "south",
    "east",
    "west",
    "central",
    "regional",
    "enterprise",
    "pilot",
    "weekend",
    "nightly",
    "priority",
    "legacy",
    "growth",
    "regulated",
    "field",
    "remote",
    "urban",
    "coastal",
    "mountain",
    "delta",
]


def variant_case(case: dict[str, Any], variant_index: int) -> dict[str, Any]:
    """Create a case variant without adding runtime-only semantic labels."""
    if variant_index == 0:
        return dict(case)

    marker = VARIANT_MARKERS[variant_index % len(VARIANT_MARKERS)]
    subject = f"{marker} {case['subject']} scenario {variant_index:03d}"
    variant = dict(case)
    variant["id"] = f"{case['id']}_v{variant_index:03d}"
    variant["subject"] = subject
    variant["query"] = (
        f"{case['query']} Context: {marker} scenario {variant_index:03d}."
    )
    variant["decoys"] = [
        f"{marker.title()} scenario {variant_index:03d}: {text}"
        for text in case["decoys"]
    ]
    variant["evidence"] = [
        (category, f"{marker} scenario {variant_index:03d}: {text}")
        for category, text in case["evidence"]
    ]
    return variant


def case_documents(case: dict[str, Any]) -> list[dict[str, Any]]:
    docs = []
    for index, text in enumerate(case["decoys"], 1):
        docs.append(
            {
                "id": f"{case['id']}-decoy-{index}",
                "text": text,
                "metadata": {
                    "domain": case["domain"],
                    "case": case["id"],
                    "stance": case["decoy_stance"],
                    "category": "approval",
                    "source": random.choice(["exec", "vendor", "review"]),
                    "gold": "decoy",
                },
            }
        )

    for index, (category, text) in enumerate(case["evidence"], 1):
        docs.append(
            {
                "id": f"{case['id']}-evidence-{index}",
                "text": f"{case['subject']}: {text}",
                "metadata": {
                    "domain": case["domain"],
                    "case": case["id"],
                    "stance": case["target_stance"],
                    "category": category,
                    "source": random.choice(["lab", "ops", "audit", "support"]),
                    "gold": "target",
                },
            }
        )

    for index in range(1, 5):
        docs.append(
            {
                "id": f"{case['id']}-noise-{index}",
                "text": (
                    f"{case['query']} historical note says a prior project went smoothly, "
                    f"but it references old owners, obsolete dates, and unrelated scope."
                ),
                "metadata": {
                    "domain": case["domain"],
                    "case": case["id"],
                    "stance": case["noise_stance"],
                    "category": "historical",
                    "source": random.choice(SOURCES),
                    "gold": "noise",
                },
            }
        )

    return docs


def rubbish_document(index: int) -> dict[str, Any]:
    domain = random.choice(RUBBISH_DOMAINS)
    action = random.choice(["launch", "deploy", "approve", "activate", "switch", "sign"])
    system = random.choice(
        [
            "dashboard",
            "mobile app",
            "supplier",
            "contract",
            "algorithm",
            "firmware",
            "identity provider",
            "exam platform",
        ]
    )
    text = (
        f"General {domain} note about whether to {action} the {system}. "
        f"{random.choice(RUBBISH_SENTENCES)}"
    )
    return {
        "id": f"rubbish-{index:06d}",
        "text": text,
        "metadata": {
            "domain": domain,
            "case": "rubbish",
            "stance": "rubbish",
            "category": random.choice(["approval", "meeting", "history", "template"]),
            "source": random.choice(SOURCES),
            "gold": "rubbish",
        },
    }


def generate(
    total_rubbish: int = 1200,
    variants: int = 1,
    seed: int = 8128,
) -> dict[str, Any]:
    random.seed(seed)
    corpus = []
    cases = {}
    for variant_index in range(variants):
        for base_case in CASES:
            case = variant_case(base_case, variant_index)
            corpus.extend(case_documents(case))
            cases[case["id"]] = {
                "domain": case["domain"],
                "query": case["query"],
                "expected_stance": case["target_stance"],
                "decoy_stance": case["decoy_stance"],
            }

    for index in range(total_rubbish):
        corpus.append(rubbish_document(index))

    random.shuffle(corpus)
    return {
        "corpus": corpus,
        "cases": cases,
        "metadata": {
            "description": "Mixed-domain adversarial decision benchmark for RAG retrieval.",
            "total_documents": len(corpus),
            "case_count": len(CASES),
            "variant_count": variants,
            "eval_case_count": len(cases),
            "rubbish_documents": total_rubbish,
            "seed": seed,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rubbish",
        type=int,
        default=1200,
        help="number of cross-domain rubbish documents to generate",
    )
    parser.add_argument(
        "--variants",
        type=int,
        default=1,
        help="number of variants to create for each base decision case",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=8128,
        help="random seed for deterministic benchmark generation",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("hard_rag_benchmark.json"),
        help="path to write the benchmark JSON",
    )
    args = parser.parse_args()

    output = generate(
        total_rubbish=args.rubbish,
        variants=args.variants,
        seed=args.seed,
    )
    out_path = args.output
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote {out_path}")
    print(f"Documents: {output['metadata']['total_documents']}")
    print(f"Cases: {output['metadata']['eval_case_count']}")


if __name__ == "__main__":
    main()
