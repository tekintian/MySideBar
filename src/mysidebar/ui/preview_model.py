from ..batch.plan import RenamePlan

STATUS_LABEL = {
    "ok": "ok",
    "skipped": "skipped",
    "invalid": "invalid",
    "conflict": "conflict",
}

ARROW = " -> "

def line_for(item, reason_text):
    label = STATUS_LABEL.get(item.status, item.status)
    base = item.rel_old + ARROW + item.rel_new + "  [" + label + "]"
    if reason_text:
        return base + "  " + reason_text
    return base


def lines_for(plan, translate):
    rows = []
    for item in plan.items:
        reason = translate(item.reason) if item.reason else ""
        rows.append(line_for(item, reason))
    return rows


def summary_text(plan, template):
    counts = plan.counts()
    return template.format(
        total=len(plan.items),
        ok=counts.get("ok", 0),
        skipped=counts.get("skipped", 0),
        conflict=counts.get("conflict", 0),
        invalid=counts.get("invalid", 0),
    )


def selected_indexes(plan, rows):
    wanted = set(rows)
    result = []
    for index, item in enumerate(plan.items):
        if index in wanted and item.status == "ok":
            result.append(index)
    return result


def subset_plan(plan, indexes):
    keep = set(indexes)
    sub = RenamePlan(base=plan.base)
    sub.items = [item for index, item in enumerate(plan.items) if index in keep]
    sub.skipped_symlinks = plan.skipped_symlinks
    return sub