# Method note: Rental Housing Law Navigator

## Problem and approach

Housing law is layered across state, county and city, with different effective dates and exemptions. The rules that apply depend on the exact address and date. Our design lets models read the law once, and then plain code answers each address.

## Extraction pipeline

Rules come from automated model extraction where stage 1 reads each document and stage 2 consolidates each state and category. A plain code step merges these rules and a validator checks every quote is copied word for word from the corpus. Claude Code agents ran the production extraction following prompt files. The tool can run a local ollama model or any OpenAI compatible API with a replay cache. The audit log holds only 4 local demo calls.

## Address lookup and change tracking

Each rule check can end as yes, no or unknown. A local rule can supersede a state rule. Change tests T1 to T5 list which addresses a new or pending law would affect.

## Checking and limits

The review process included three AI passes and a judge style review without human sign off. Open risk items remain regarding effective dates and citation wording. Our proxy scorer gave a score of 74.4 of 75 on our own key because the organizers' key is not shared. Stage 2 never ran on a real backend through the runner.

Not legal advice.
