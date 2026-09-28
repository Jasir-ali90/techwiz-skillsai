"""Progress tracking, progress assessment, weak areas and recommendations
(SRS Steps 53-56). Computed on every read, never stored stale. Rule-based."""
from datetime import date, timedelta

ON_TRACK = "ON_TRACK"
REQUIRES_ATTENTION = "REQUIRES_ATTENTION"
BEHIND_SCHEDULE = "BEHIND_SCHEDULE"
ASSESSMENT_REQUIRED = "ASSESSMENT_REQUIRED"
COMPLETED = "COMPLETED"
NOT_STARTED = "NOT_STARTED"


def _units(plan: dict, attempts: list[dict], results: list[dict]) -> list[dict]:
    """Every trackable unit with its weight, stage, competency and done flag."""
    correct = {a["question_id"] for a in attempts if a["is_correct"]}
    passed = {r["assessment_id"] for r in results if r["passed"]}
    units = []
    for m in plan["modules"]:
        competency = m.get("competency") or m.get("category") or "General"
        parts_done = [c["completion_status"] == "COMPLETED" for c in m["checklist"] if c["is_required"]]
        parts_done += [t["completion_status"] == "COMPLETED" for t in m["tasks"]]
        module_done = m["completion_status"] == "COMPLETED" or (bool(parts_done) and all(parts_done))
        units.append({"type": "module", "id": m["id"], "title": m["title"], "stage": m["due_stage"],
                      "competency": competency, "done": module_done})
        for c in m["checklist"]:
            if c["is_required"]:
                units.append({"type": "checklist_item", "id": c["id"], "title": c["activity"], "stage": c["due_stage"],
                              "competency": competency, "done": c["completion_status"] == "COMPLETED"})
        for t in m["tasks"]:
            units.append({"type": "task", "id": t["id"], "title": t["description"], "stage": t["due_stage"],
                          "competency": competency, "done": t["completion_status"] == "COMPLETED"})
        for q in m["quiz"]:
            units.append({"type": "quiz_question", "id": q["id"], "title": q["question"], "stage": q["due_stage"],
                          "competency": competency, "done": q["id"] in correct})
        for a in m["assessments"]:
            units.append({"type": "assessment", "id": a["id"], "title": a["title"], "stage": a["due_stage"],
                          "competency": competency, "done": a["id"] in passed})
    return units


def assess(plan: dict | None, attempts: list[dict], results: list[dict], stages: dict[str, dict],
           joining_date: date, today: date, config: dict) -> dict:
    days = (today - joining_date).days
    if plan is None:
        return {"status": NOT_STARTED, "days_since_joining": days, "overall_progress": 0.0,
                "note": "No onboarding plan has been generated yet"}
    weights = config.get("weights", {})
    units = _units(plan, attempts, results)

    def weighted(subset) -> float:
        total = sum(weights.get(u["type"], 1.0) for u in subset)
        done = sum(weights.get(u["type"], 1.0) for u in subset if u["done"])
        return (100 * done / total) if total else 100.0

    offset = {code: s["offset_days"] for code, s in stages.items()}
    due_now = [u for u in units if offset.get(u["stage"], 10 ** 6) <= days]
    overall = round(weighted(units), 2)
    expected = round(100 * sum(weights.get(u["type"], 1.0) for u in due_now) /
                     max(1e-9, sum(weights.get(u["type"], 1.0) for u in units)), 2) if units else 0.0
    actual_on_due = weighted(due_now) if due_now else 100.0

    by_type = {}
    for kind in ("module", "checklist_item", "task", "quiz_question", "assessment"):
        subset = [u for u in units if u["type"] == kind]
        by_type[kind] = {"total": len(subset), "completed": sum(u["done"] for u in subset),
                         "percent": round(100 * sum(u["done"] for u in subset) / len(subset), 2) if subset else None}

    quiz_score = round(100 * sum(a["is_correct"] for a in attempts) / len(attempts), 2) if attempts else None
    assessment_score = round(sum(r["score"] for r in results) / len(results), 2) if results else None

    thresholds = config.get("status", {})
    non_assessment_done = all(u["done"] for u in units if u["type"] != "assessment")
    if units and all(u["done"] for u in units):
        status = COMPLETED
    elif units and non_assessment_done:
        status = ASSESSMENT_REQUIRED
    elif not due_now:
        status = ON_TRACK
    else:
        ratio = overall / expected if expected else 1.0
        if ratio >= float(thresholds.get("on_track_ratio", 0.9)):
            status = ON_TRACK
        elif ratio >= float(thresholds.get("attention_ratio", 0.6)):
            status = REQUIRES_ATTENTION
        else:
            status = BEHIND_SCHEDULE

    overdue = [u for u in due_now if not u["done"] and offset.get(u["stage"], 0) < days]
    weak = weak_areas(units, attempts, results, overdue, config)
    recs = recommendations(weak, status, units, attempts, config)

    milestones = []
    for code, s in sorted(stages.items(), key=lambda kv: kv[1]["sequence"]):
        subset = [u for u in units if u["stage"] == code]
        milestones.append({
            "stage": code, "name": s.get("name"), "due_date": str(joining_date + timedelta(days=s["offset_days"])),
            "items": len(subset), "completed": sum(u["done"] for u in subset),
            "percent": round(100 * sum(u["done"] for u in subset) / len(subset), 2) if subset else None,
            "reached": days >= s["offset_days"],
        })
    upcoming = sorted([u for u in units if not u["done"] and u["type"] != "module"],
                      key=lambda u: offset.get(u["stage"], 10 ** 6))[:10]
    return {
        "status": status,
        "days_since_joining": days,
        "overall_progress": overall,
        "expected_progress": expected,
        "progress_on_items_due": round(actual_on_due, 2),
        "by_type": by_type,
        "module_completion": by_type["module"],
        "checklist_completion": by_type["checklist_item"],
        "task_completion": by_type["task"],
        "quiz_score": quiz_score,
        "assessment_score": assessment_score,
        "overdue_items": [{"type": u["type"], "id": u["id"], "title": u["title"][:120], "stage": u["stage"]}
                          for u in overdue[:20]],
        "weak_areas": weak,
        "recommendations": recs,
        "milestones": milestones,
        "upcoming_activities": [{"type": u["type"], "id": u["id"], "title": u["title"][:120], "stage": u["stage"],
                                 "due_date": str(joining_date + timedelta(days=offset.get(u["stage"], 0)))}
                                for u in upcoming],
    }


def weak_areas(units, attempts, results, overdue, config) -> list[dict]:
    """All four SRS signals: quiz performance, assessment results, incomplete
    tasks and repeated errors."""
    rules = config.get("weak_area", {})
    competencies = sorted({u["competency"] for u in units} | {a.get("competency") for a in attempts if a.get("competency")})
    found = []
    for comp in competencies:
        comp_attempts = [a for a in attempts if a.get("competency") == comp]
        signals = []
        if len(comp_attempts) >= int(rules.get("min_quiz_attempts", 2)):
            accuracy = sum(a["is_correct"] for a in comp_attempts) / len(comp_attempts)
            if accuracy < float(rules.get("quiz_accuracy_below", 0.7)):
                signals.append({"signal": "low_quiz_accuracy", "value": round(accuracy, 2),
                                "attempts": len(comp_attempts),
                                "failed": sum(not a["is_correct"] for a in comp_attempts)})
        wrong_by_question: dict = {}
        for a in comp_attempts:
            if not a["is_correct"]:
                wrong_by_question[a["question_id"]] = wrong_by_question.get(a["question_id"], 0) + 1
        repeated = [q for q, n in wrong_by_question.items() if n >= int(rules.get("repeated_error_count", 2))]
        if repeated:
            signals.append({"signal": "repeated_error", "questions": [str(q) for q in repeated]})
        failed = [r for r in results if r.get("competency") == comp and not r["passed"]]
        if failed:
            signals.append({"signal": "failed_assessment", "scores": [r["score"] for r in failed]})
        late_tasks = [u for u in overdue if u["competency"] == comp and u["type"] == "task"]
        if len(late_tasks) >= int(rules.get("overdue_incomplete_tasks", 1)):
            signals.append({"signal": "overdue_tasks", "count": len(late_tasks)})
        if signals:
            found.append({"competency": comp, "signals": signals, "severity": len(signals)})
    return sorted(found, key=lambda w: -w["severity"])


def recommendations(weak, status, units, attempts, config) -> list[dict]:
    templates = {r["when"]: r for r in config.get("recommendations", [])}
    recs = []
    for area in weak:
        for signal in area["signals"]:
            t = templates.get(signal["signal"])
            if t:
                recs.append({"type": t["type"], "competency": area["competency"],
                             "reason": signal["signal"], "message": t["message"].format(competency=area["competency"])})
    if status == BEHIND_SCHEDULE and "behind_schedule" in templates:
        t = templates["behind_schedule"]
        recs.append({"type": t["type"], "competency": None, "reason": "behind_schedule",
                     "message": t["message"].format(competency="")})
    strong = config.get("strong_performance", {})
    weak_names = {w["competency"] for w in weak}
    if "strong_performance" in templates:
        for comp in sorted({a.get("competency") for a in attempts if a.get("competency")} - weak_names):
            comp_attempts = [a for a in attempts if a.get("competency") == comp]
            comp_units = [u for u in units if u["competency"] == comp]
            if len(comp_attempts) >= int(strong.get("min_quiz_attempts", 2)) and \
                    sum(a["is_correct"] for a in comp_attempts) / len(comp_attempts) >= float(strong.get("quiz_accuracy_at_least", 0.9)) \
                    and all(u["done"] for u in comp_units if u["type"] in ("task", "checklist_item")):
                t = templates["strong_performance"]
                recs.append({"type": t["type"], "competency": comp, "reason": "strong_performance",
                             "message": t["message"].format(competency=comp)})
    seen, unique = set(), []
    for r in recs:
        key = (r["type"], r["competency"], r["reason"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique
