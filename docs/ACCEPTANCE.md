# Acceptance checklist, Steps 3d to 10

Every acceptance criterion in `skillsprint-prompts-3d-to-10.md` is listed below with:
- how to show it live;
- the automated test that proves it;
- the output that shows it worked.

Run everything with:

```bash
docker compose up -d db
python -m pytest            # expect: 232 passed
```

Log in first: `POST /auth/login` with `{"email": "evaluator@nexoralabs.io", "password": "Evaluate@123"}`,
then send `Authorization: Bearer <access_token>` on every call.

## Step 3d: Embeddings and semantic search

Migration: `521602c9b3ae_chunk_embeddings_with_hnsw_index` (the `embedding vector(384)` column and the HNSW
cosine index).

| Criterion | Show it | Proof |
|---|---|---|
| `embed-all` then `coverage` shows pending 0 | `POST /search/embed-all?force=true`, then `GET /search/coverage` | `test_documents_are_loaded_parsed_and_embedded`: `"pending": 0` |
| Security-training deadline surfaces the policy clause and the contradicting FAQ, with their ranks | `GET /search?q=How long do I have to complete the security training?` | `test_semantic_search_finds_policy_and_contradicting_faq`: POL-INFOSEC-001 rank 20 and FAQ-ENG-002 rank 60 |
| Absent topic returns 0 at `min_similarity=0.45` | `GET /search?q=company pet insurance&min_similarity=0.45` | `test_topic_absent_from_every_document_returns_nothing`: `"count": 0, "grounded": false` |
| `active_only=false` surfaces obsolete chunks | after uploading InfoSec v2: `GET /search?q=...seven calendar days&active_only=false` | `test_obsolete_chunks_hidden_from_search_unless_asked` |

## Step 4: Role Requirement Matrix

Migration: `4ee676b42845_requirements_role_matrix_prerequisites_audit_log`; plus
`5f09fedc19d7_requirement_precedence_override`.

| Criterion | Show it | Proof |
|---|---|---|
| InfoSec yields separate MUST_KNOW, MUST_COMPLETE and RECOMMENDED, and rejects purpose and scope sentences | `POST /matrix/extract`: see `by_type` and `rejected_by_reason` | `test_infosec_yields_know_complete_and_recommended_and_rejects_purpose` |
| "Backend Developers must not commit secrets" maps to Backend Developer by EXPLICIT_ROLE_MENTION, not to SEO Specialist | `GET /requirements/{code}`: `mapped_roles` | `test_explicit_role_mention_maps_only_that_role`, `test_matrix_summary_and_role_matrices_differ` |
| "All employees must enable multi-factor authentication" maps to all ten roles by APPLIES_TO_ALL | `GET /requirements/{code}` | `test_all_employees_clause_maps_to_all_ten_roles` |
| A new role, then map-roles, maps correctly with no code change | `POST /roles`, `POST /matrix/map-roles`, `GET /matrix/role/{id}` | `test_unseen_document_and_new_role_flow_end_to_end`, `test_new_role_created_later_is_mapped_without_code_change` |
| Two roles return visibly different Matrices | `GET /matrix/role/{backend}` vs `/matrix/role/{seo}` | `test_matrix_summary_and_role_matrices_differ` |
| SRS minimums: 150 requirements, 50 mandatory, 30 role-specific | `GET /matrix/summary` (with the full corpus) | `srs_minimums`: 327 / 261 / 234, all `met: true` |
| Cycle rejected and reported | `POST /matrix/prerequisites`: `cycles_rejected` | `test_cycle_is_rejected_and_reported` |

## Step 5: Pipeline 1, generation

Migration: `577603a5644a_genai_pipeline_plans_prompt_templates_`.

| Criterion | Show it | Proof |
|---|---|---|
| Backend Developer and SEO Specialist plans differ in modules, tasks, quiz topics and priorities | `POST /plans/generate` for EMP-001 and for EMP-002 | `test_backend_and_seo_plans_are_visibly_different` |
| No plan puts everything on Day 1 | `GET /plans/{id}`, `due_stage` on each item | `test_no_plan_puts_everything_on_day_one` |
| Every module and quiz question carries a document code, section id and chunk code | `GET /plans/{id}`: `source_document_code`, `source_section_id`, `source_chunk_code` | `test_every_item_carries_document_section_and_chunk` |
| The generation run records prompt version, model, timestamp and source document versions | `GET /plans/{id}/generation-run` | `test_generation_run_is_recorded` |
| A topic no document mentions produces a recorded gap | `POST /plans/generate` with `extra_topics: ["pet insurance"]` | `test_unsupported_topic_becomes_a_recorded_gap` |
| A malformed response triggers retry, is logged, and stops at three attempts | `POST /plans/generate` with `simulate_malformed: 3`, which returns 502 with 3 logged attempts | `test_malformed_output_is_retried_logged_and_capped`, `test_retries_stop_at_three_attempts`, `test_attempt_cap_cannot_be_raised_by_config` |
| Isolation guard still passes | `python -m pytest tests/test_isolation_guard.py` | `32 passed` |

## Step 6: Pipeline 2, validation

Migration: `377b604b1bf6_validation_results_and_findings`.

| Criterion | Show it | Proof |
|---|---|---|
| Missing one of three mandatory requirements scores 67 % and is not Verified | see Step 7, first row | `test_srs_worked_example_two_of_three_is_67_percent_and_incomplete` (66.67 %, INCOMPLETE) |
| Citing an obsolete version fails traceability | upload InfoSec v2, then `POST /validation/run/{id}` | `test_citing_an_obsolete_version_fails_traceability`, `test_plan_citing_the_obsolete_version_fails_traceability` |
| A quiz answer contradicting its section is flagged | `GET /validation/{id}/findings?rule=quiz_answers` | `test_quiz_answer_contradicting_its_section_is_flagged`, `test_true_false_statement_contradicting_its_section_is_flagged` |
| A task before its prerequisite is flagged with both codes | `?rule=learning_sequence` | `test_task_before_its_prerequisite_is_flagged_with_both_codes` |
| A fabricated rule is flagged; instructional wording is not | `?rule=hallucination` | `test_fabricated_company_rule_is_flagged_but_instructional_wording_is_not` |
| Disabling a rule through the API changes the next run | `PUT /validation/rules` with `{"contradictions": {"enabled": false}}`, then rerun | `test_disabling_a_rule_through_the_api_changes_the_next_run` |
| Six SRS metrics stored | `GET /validation/{id}`: `metrics` | `test_report_carries_all_six_srs_metrics` |
| Isolation guard output | `python -m pytest tests/test_isolation_guard.py -v` | 32 passed: source scan and AST import scan per file, plus a transitive-import check in a fresh interpreter |

## Step 7: Comparison, statuses, review, audit

Migration: `264848d03e0a_comparison_consistency_review_decisions` (with an append-only trigger).

| Criterion | Show it | Proof |
|---|---|---|
| One missing mandatory requirement means Incomplete; fixing it and revalidating flips it to Verified | delete a module, run validation (INCOMPLETE), regenerate it, run again (VERIFIED) | `test_missing_mandatory_requirement_is_incomplete_then_fixed_is_verified` (asserts exactly `VERIFIED`) |
| A reviewer override sits beside the original result in the audit trail, and neither can be deleted | `POST /review/{finding_id}/decision`, then `GET /audit/finding/{id}` | `test_review_override_keeps_original_and_decision`, `test_audit_log_and_review_decisions_are_append_only` (ORM and database both refuse UPDATE and DELETE) |
| The comparison export has the SRS row shape | `GET /comparison/{plan_id}/export`, `GET /reports/comparison?format=csv` | `test_comparison_rows_and_csv_export`, `test_comparison_report_has_at_least_100_rows_with_explanations` |
| Consistency runs as a background job with pinned parameters | `POST /consistency/{plan_id}` (202), then `GET /consistency/{plan_id}` | `test_consistency_runs_as_a_background_job` (score 100, parameters logged) |
| The Verified rule has three explicit conditions | `src/comparison_engine/status.py::can_mark_verified` | `test_can_mark_verified_needs_all_three_conditions` |

## Step 8: Progress, dashboards, recommendations

Migration: `ed0d3dc0a4b6_progress_quiz_attempts_assessment_`.

| Criterion | Show it | Proof |
|---|---|---|
| 40 days past joining with 20 % completion reads Behind Schedule | `GET /progress/{employee_id}` | `test_forty_days_in_with_twenty_percent_is_behind_schedule` |
| Two failed quizzes on one competency give a weak area naming it and a revision recommendation | two wrong answers to `POST /progress/quiz/{id}/attempt`, then `GET /dashboard/me` | `test_two_failed_quizzes_on_one_competency_give_weak_area_and_revision`, `test_employee_progress_quiz_weak_area_and_dashboard` |
| The admin dashboard shows compliance coverage across all ten roles | `GET /dashboard/admin`: `compliance_coverage` | `test_admin_and_role_dashboards` |
| Plan comparison across roles, departments, levels and document versions | `GET /plans/compare?dimension=...` | `test_plan_comparison_across_dimensions` |

## Step 9: Policy updates

Migration: `8969f7904a4d_impact_records`.

| Criterion | Show it | Proof |
|---|---|---|
| Uploading InfoSec v2 marks v1 obsolete | `POST /documents` (v2): `superseded_document_id` | `test_v2_upload_marks_v1_obsolete` |
| The diff names the three changed clauses | `POST /impact/analyse/{v2_id}`: §2.3 seven→three days, §2.1 hardware security key, §3.3 read-only access | `test_diff_names_the_three_changed_clauses`, `test_v1_to_v2_diff_names_the_three_changed_clauses` |
| Lists affected modules, quiz questions, plans and employees | `GET /impact/{v2_id}/affected` | `test_diff_names_the_three_changed_clauses` |
| Regenerates only those modules; completion on unaffected modules survives | `POST /impact/{v2_id}/regenerate?dry_run=true`, then `dry_run=false` | `test_dry_run_changes_nothing`, `test_selective_regeneration_preserves_untouched_modules` |
| A quiz question citing a changed section is flagged outdated | `GET /plans/{id}/outdated` shows `SECTION_CHANGED` | `test_quiz_citing_a_changed_section_is_outdated` |

## Step 10: Reports, tests, deployment

| Criterion | Show it | Proof |
|---|---|---|
| Every report exports in all three formats | `GET /reports/{employee-progress, role-coverage, mandatory-training, assessment-results, source-traceability, hallucination-flags, policy-coverage, comparison}?format=csv\|xlsx\|pdf` | `test_every_report_exports_in_all_formats` (8 × 4 formats) |
| The comparison export has at least 100 rows with explanations | `GET /reports/comparison?format=csv` | `test_comparison_report_has_at_least_100_rows_with_explanations` |
| Search and filtering: one paginated endpoint | `GET /search/records?role=&department=&module=&policy=&status=&verification=&progress_min=&page=` | `test_global_search_filters_and_paginates` |
| `pytest` passes, including the guard | `python -m pytest` | 232 passed |
| Security testing report | `python -m pytest tests/security -s` | `docs/security_testing_report.md`: 25 of 25 cases passed |
| Standard plan generates and validates within 30 s | `POST /plans/generate` | `test_standard_plan_generates_and_validates_within_30_seconds`; a full 30-module plan takes about 4 s in the container and about 20 s on the dev machine |
| Deployed URL serves the app with evaluator and admin logins | `docker compose --profile app up --build`, then `GET /health` and `POST /auth/login` | verified locally in the container; a public URL needs a hosting account (see README, Deployment) |

## Evaluator live challenges (all are data or config edits)

| Challenge | How | Proof |
|---|---|---|
| Add a role | `POST /roles`, then `POST /matrix/map-roles` | `test_unseen_document_and_new_role_flow_end_to_end` |
| Change onboarding duration | `PATCH /stages/{id}` with `{"offset_days": 21}` | `test_onboarding_duration_is_a_data_edit` |
| Modify policy precedence | `PUT /config/precedence`, then `POST /config/precedence/reapply` | `test_policy_precedence_is_a_runtime_edit` |
| Add a quiz type | `PUT /config/quiz_types` | `test_runtime_config_edit_for_quiz_types` |
| Add a validation rule | business rule: `PUT /config/business_rules`; a new check is one class with `@register` plus an entry in `config/validation_rules.yaml` | `test_new_business_rule_from_config_applies_without_code_change` |
| An unseen document | upload any PDF or DOCX, then parse, `/matrix/extract`, `/matrix/map-roles` | `test_unseen_document_and_new_role_flow_end_to_end` |

## SRS test categories (19)

| Category | Tests |
|---|---|
| Functional | `test_10_*`, `test_20_*`, `test_30_*` |
| Document upload | `test_upload_rejects_invalid_duplicate_and_stale_version`, `test_upload_boundaries`, validator unit tests |
| Parsing | `test_pdf_parser_keeps_page_numbers`, `test_docx_parser_keeps_paragraph_index_and_headings` |
| Chunking | `test_chunks_follow_numbered_sections_with_codes_and_headings`, `test_faq_answers_inherit_their_question_section` |
| Requirement extraction | `test_infosec_yields_*`, `test_extraction_details_for_one_clause`, `test_conditions_and_exceptions_are_recorded`, `test_deadline_parsing` |
| GenAI API | `test_malformed_json_is_retried_*`, `test_transient_failures_are_retried`, `test_permanent_failure_fails_fast_*`, `test_anthropic_errors_map_*` |
| JSON | `test_json_schema_files_match_pydantic_models`, `test_schema_mismatch_is_*`, `test_schema_detects_*` |
| Python validation | `tests/unit/test_python_validation.py` |
| Source traceability | `test_citing_an_obsolete_version_fails_traceability`, `test_unknown_section_and_chunk_are_reported`, `test_every_item_carries_document_section_and_chunk` |
| Coverage | `test_srs_worked_example_*`, `test_content_outside_the_matrix_is_unsupported`, `test_missing_mandatory_requirement_is_incomplete_then_fixed_is_verified` |
| Hallucination | `test_fabricated_company_rule_*`, `test_source_supported_claims_pass`, `test_unsupported_topic_becomes_a_recorded_gap` |
| Contradiction | `test_generated_task_violating_a_rule_*`, `test_item_permitting_*`, `test_numeric_conflict_*`, `test_polarity_conflict`, `test_old_versus_new_*` |
| Prompt injection | `test_injection_text_is_detected`, `test_prompt_wraps_documents_as_untrusted_*`, `test_suspicious_chunk_is_*`, security report rows 1–4 |
| Role relevance | `test_content_for_another_role_*` (unit and live), `test_content_mapping_to_no_requirement_*`, `test_relevant_*` |
| Policy version | `test_v1_to_v2_diff_*`, `test_v2_upload_marks_v1_obsolete`, `test_obsolete_chunks_hidden_*` |
| Regeneration | `test_dry_run_changes_nothing`, `test_selective_regeneration_preserves_untouched_modules`, `test_reviewer_edit_is_applied_and_audited` |
| Hidden-document readiness | `test_unseen_document_and_new_role_flow_end_to_end` |
| Security | `tests/security/test_security_report.py` (25 cases) |
| Boundary | `tests/integration/test_15_boundary_and_role_relevance.py` |
