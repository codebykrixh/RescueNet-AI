# Spikes — throwaway experimental code

**This directory is NOT architecture and NOT a reference implementation.**
Each script answers exactly one feasibility question and is disposable.
Nothing here may be copied into the build — rewrite from the requirements instead.

Results are recorded in [`../docs/04-feasibility-validation.md`](../docs/04-feasibility-validation.md).

| Script | Spike | Question answered | Run |
|---|---|---|---|
| `sp01a_codec_budget.py` | SP-01a | Do operational events fit an SMS payload budget? | `python3 spikes/sp01a_codec_budget.py` |
| `sp01a_throttle_corrected.py` | SP-01a addendum | Does message volume fit Android's per-device outgoing throttle? | `python3 spikes/sp01a_throttle_corrected.py` |
| `sp05_merge_convergence.py` | SP-05 | Does union merge satisfy the D-01 duplicate-search-effort scenario? | `python3 spikes/sp05_merge_convergence.py` |

SP-01b, SP-02, SP-03 and SP-04 require physical Android handsets, SIMs and a build
toolchain. Their protocols are specified in `docs/04-feasibility-validation.md` §4
with empty result blocks — those blocks are filled in only after the experiments run.
