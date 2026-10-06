# Language model explanation — extension point for FYP2

**Nothing in this directory is implemented.** No model is called, no API key is
read, and no explanation is generated anywhere in the FYP1 system.

## What FYP2 will add here

A constrained explanation layer that turns a calculated result into plain
language for a reader without financial training:

1. The calculation engine produces a result.
2. That result is serialised into a structured payload of engine-computed
   figures — the only figures the model receives.
3. The model is asked to explain the payload, using only the values supplied.
4. Every numerical value in the generated text is extracted and matched against
   the payload, allowing for formatting differences such as thousands
   separators, currency notation and rounding to the stated precision.
5. An explanation containing a figure that cannot be matched is rejected and
   regenerated, up to three attempts. After that the structured result is
   presented without narrative, rather than with unverified figures.

Validation outcomes will be logged, so the rate of ungrounded figure generation
is measured rather than assumed.

## The constraint this rests on

The model is never given the ability to compute. It receives figures and
returns prose; the calculation engine remains the sole numerical source of
truth. This is an architectural constraint, not an instruction to the model.

## Boundaries

The explanation layer will explain computed results only. It will decline
requests for financing, investment or restructuring recommendations,
consistent with the exclusion of regulated financial advice from the project
scope, and will refuse requests concerning data outside the requesting user's
own records.
