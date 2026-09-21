# ClawTrap Scenario Intake Delivery

- Format: `clawtrap.scenario-intake.v1`
- Scenario packages: 400 independent ZIP files in `scenarios/`
- One ZIP contains exactly one scenario root and one decisive fact.
- Source evidence: frozen local artifacts with SHA-256 in each `scenario.yaml`

## Deliberate exclusions

This delivery contains no benchmark final task, attack-page implementation, attack instruction payload, clean/attack browser asset, task form, grader, rubric, evaluator hook, or oracle.

## Verification limitation

The prior corpus retained a single frozen primary source per scenario, rather than a separately frozen independent verifier. Every package therefore uses `verification.mode: internal_consistency`; `sources/verification.*` is a byte-identical copy and its metadata explicitly states `source_is_independent_from_primary: false`. This is an honest packaging limitation, not a claim of independent verification. Add independent frozen sources before using these cases as a formally independently verified main set.

The one screenshot-first historical checkout scenario retains its original frozen browser screenshot as source evidence; the remaining packages use an offline Quick Look preview of their frozen local source artifact.

See `validation_report.json` for package-level structural validation and `manifest.json` for the index and checksums.
