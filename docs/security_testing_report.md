# Security testing report

Generated 2026-09-28 18:46 by `pytest tests/security`.

| # | Category | Case | Expected | Observed | Result |
|---|---|---|---|---|---|
| 1 | Prompt injection | Embedded 'ignore all previous instructions' in FAQ-ENG-002 | Chunk flagged suspicious with reasons | 1 chunk(s) flagged: ignore_instructions, skip_validation, suppress_reporting, system_note_to_assistant | PASS |
| 2 | Prompt injection | Suspicious chunk excluded from the generation prompt | Injection text absent from the recorded prompt | absent | PASS |
| 3 | Prompt injection | Document text telling the system to 'approve without validation' | Pipeline 2 still runs every rule | 13 rules ran; status VERIFIED | PASS |
| 4 | Prompt injection | Delimiter-breaking text inside a document | Exactly one closing delimiter | 1 closing delimiter(s) | PASS |
| 5 | Malicious document | Windows executable renamed to .pdf | 422, file_type check fails | 422 document_validation_failed | PASS |
| 6 | Invalid file | JavaScript file | 422, extension not allowed | 422 | PASS |
| 7 | Invalid file | Empty PDF | 422, empty_document check fails | 422 | PASS |
| 8 | Invalid file | PDF over 25 MB | 422, file_size check fails | 422 | PASS |
| 9 | Malicious document | Corrupt PDF body | Rejected cleanly, never a 500 | upload 201, parse 422 | PASS |
| 10 | Unsupported topic | Plan asked to cover 'stock option vesting schedule' | Recorded as a gap, no content invented | gap recorded=True, invented=False | PASS |
| 11 | Unsupported topic | Semantic search for an absent topic | 0 results, grounded=false | 0 results, grounded=False | PASS |
| 12 | Unauthorised access | No bearer token on /plans | 401 | 401 | PASS |
| 13 | Unauthorised access | JWT signed with the wrong key | 401 | 401 | PASS |
| 14 | Unauthorised access | Expired JWT | 401 | 401 | PASS |
| 15 | Unauthorised access | Employee calls PUT /validation/rules | 403 | 403 | PASS |
| 16 | Unauthorised access | Employee calls PUT /config/precedence | 403 | 403 | PASS |
| 17 | Unauthorised access | Employee calls POST /matrix/extract | 403 | 403 | PASS |
| 18 | Unauthorised access | Employee calls POST /roles | 403 | 403 | PASS |
| 19 | Unauthorised access | Employee calls GET /dashboard/admin | 403 | 403 | PASS |
| 20 | Unauthorised access | Employee calls GET /reports/comparison | 403 | 403 | PASS |
| 21 | Unauthorised access | Wrong password | 401 | 401 | PASS |
| 22 | Unauthorised access | SQL injection in a filter parameter | 200 with no rows; users table intact | 200, 0 rows, login 200 | PASS |
| 23 | Invalid API response | Provider returns broken JSON three times | Stops after 3 attempts with a structured 502 | 502 genai_retries_exhausted, 3 attempts | PASS |
| 24 | Invalid API response | Valid JSON in the wrong shape | Rejected by schema validation | rejected after 3 attempts (schema_mismatch) | PASS |
| 25 | Invalid API response | Provider rejects the API key | Fails fast: 1 attempt, 503, clear message | 1 attempt(s) | PASS |

**25 of 25 cases passed.**
