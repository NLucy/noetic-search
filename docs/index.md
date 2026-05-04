# Noetic Systems

Noetic Systems is post-retrieval graph reconciliation for hybrid search.

Hybrid search finds candidates. Noetic Search resolves those candidates into a
coherent evidence basin before the LLM sees them.

## Read This Way

1. [The Process](process.md): the full technical treatment.
2. [Testing Results](testing-results.md): benchmark commands, numbers, and interpretation.

## One-Line Thesis

```text
Use broad retrieval for recall, then graph reconciliation for precision.
```

## Current Signal

On the blind hard benchmark:

```text
standard hybrid top-5: 0/10
noetic top-5 from hybrid top-50: 8/10
```

The result is promising, not finished. The open work is graph admission, basin
pollution, and final chunk ordering.
