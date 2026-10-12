# AI tooling used

## Tools
- **Claude Code** (Anthropic's agentic coding CLI, used inside VS Code) was the main tool. It read the assignment brief, proposed the architecture, wrote most of the code, tests, CI workflow and documentation, ran the commands (venv, ingestion, pytest, evaluation, a local server), and iterated on the failures it found.
- **Claude Code sub-agents** wrote the synthetic policy corpus in parallel. Four agents each drafted 3–4 policy documents.
- **Groq-hosted Llama 3.3 70B** is the runtime LLM. It also serves as the groundedness judge in the evaluation. That is part of the product, not the development tooling, but it is listed here for completeness.

## How they were used
1. **Planning.** The brief's requirements were turned into a module layout (`rag/` package, Flask app, eval harness, CI) and a list of design choices to justify.
2. **Corpus generation.** I wrote a canonical **fact sheet** first (`corpus_src/FACT_SHEET.md`), with the company, every number, every deadline and the document IDs. Each writer agent had to stay consistent with it. This stopped parallel agents from inventing contradictory numbers, such as different PTO amounts in the handbook and the leave policy. Before relying on the evaluation set, a script checked that every gold key fact actually appears in its gold document.
3. **Code.** The AI generated code module by module. Tests ran after each step, and the AI fixed issues they exposed.
4. **Evaluation-driven fixes.** The AI ran the evaluation and probes, read the per-question failures and changed the code:
   - PDF line wraps were being treated as sentence breaks. A reflow step fixed it, and citation accuracy went from 96.3% to 100%.
   - A numbered-heading regex treated lines like "10 business days..." as headings. It now requires `N.` numbering.
   - The off-topic gate based on the re-rank score alone would have refused colloquial in-scope questions. It became a two-signal gate, calibrated on measured scores.
   - The ablations saturated at 100% on the standard set, so a harder paraphrase set was added to make them informative.

## What worked well
- **Fast end-to-end scaffolding.** A working app, tests and CI existed within one session, which left time for evaluation and calibration.
- **Parallel sub-agents for long-form content** produced about 33k words of coherent policy text quickly. The shared fact sheet kept the documents consistent with each other.
- **Running real measurements.** Asking the AI to measure (gate scores, ablations, per-question failures) instead of guessing gave defensible thresholds and defaults.

## What did not work as well
- **The first drafts of heuristics were brittle:** the text and PDF heading detection, the extractive sentence picker that at first chose FAQ questions and table rows, and the length cutoff. Each needed a test or probe to find the problem and a second pass to fix it.
- **Document length overshot the brief:** agents sometimes exceeded the requested word counts and added plausible extra rules. These were checked against the fact sheet but still needed review.
- **Environment friction needed human context:** the corporate TLS proxy blocked model downloads until the OS trust store was injected through `truststore`, and the LLM API key and GitHub account had to come from me.
- **The AI's choices were reviewed, not accepted blindly:** design decisions such as the chunk size, k, re-ranking and the gate thresholds were validated against the evaluation results before being adopted.
