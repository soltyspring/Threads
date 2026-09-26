"""Original format experiments inspired by public text-symbol collections.

Thresholds are experimental targets, not claims about an optimal algorithm.
This module is pure: it never changes a queue, posts content, or contacts APIs.
"""
import random
import unicodedata

from weekly_content import POOLS


VERSION = "competitor-formats-v1"
MAX_LINE_CELLS = 40
LENGTH_TARGETS = {"short": (50, 100), "medium": (101, 180), "long": (181, 300)}
FACE_THEMES = {
    "Tiny happy faces", "Tiny mood faces", "Sleepy little cats",
    "Soft bunny faces", "Cute face collection",
}
USECASE_TITLES = {
    "Tiny happy faces": "Happy faces for a little note",
    "Tiny mood faces": "Tiny reactions for today",
    "Little bows": "Bows for your bio",
    "Little hearts": "Hearts for a little note",
    "Tiny stars": "Stars for your display name",
    "Flower garden": "Flowers for your bio",
    "Sleepy little cats": "Cats for a sleepy reply",
    "Soft bunny faces": "Bunnies for a gentle hello",
    "Music for your bio": "A little playlist decoration",
    "Little ocean": "A tiny seaside bio",
    "Soft tiny decorations": "Little borders for your bio",
    "Cute face collection": "Faces for a tiny message",
}
FORMATS = ("control_grid", "expanded_dictionary", "mixed_collection", "title_variant")


def display_cells(text):
    """Conservative Unicode width estimate, not a mobile rendering measurement."""
    return sum(
        0 if unicodedata.category(c) in {"Mn", "Me", "Cf"}
        else 2 if unicodedata.east_asian_width(c) in {"W", "F"}
        else 1
        for c in text
    )


def _rows(items, max_columns, gap):
    rows, current = [], []
    for item in items:
        if display_cells(item) > MAX_LINE_CELLS:
            raise ValueError("One item exceeds the experimental width budget")
        if current and (len(current) == max_columns or
                        display_cells(gap.join(current + [item])) > MAX_LINE_CELLS):
            rows.append(current)
            current = []
        current.append(item)
    if current:
        rows.append(current)
    return rows


def _decorate(theme, atoms, rng, style):
    """Compose common atoms, never reproduce a competitor's complete post."""
    accents = rng.sample(["✧", "⊹", "♡", "⋆", "୨୧", "˚", "⟡", "𓂃"], 8)
    faces = rng.sample(POOLS["Tiny happy faces"].split("|"), 12)
    if style == "ready_to_use_dividers":
        return [f"{accents[i]}  {atoms[i]}  𓂃  {atoms[i + 4]}  {accents[i]}"
                for i in range(4)]
    if style == "mixed_face_dictionary":
        return [f"{accents[i % 8]} {atoms[i]} {accents[(i + 3) % 8]}" if theme in FACE_THEMES
                else f"{atoms[i]} {faces[i]} {accents[i % 8]}" for i in range(12)]
    # Self-contained snippets that can be used as a name or profile decoration.
    return [f"{accents[i]} {atoms[i]} · {atoms[i + 4]} {accents[(i + 2) % 8]}"
            for i in range(4)]


def _make_post(theme, items, title, max_columns, gap, pair_id, arm, style,
               hypothesis, comparison, controlled_factor, target):
    rows = _rows(items, max_columns, gap)
    body = "\n".join(gap.join(row) for row in rows)
    text = (title + "\n\n" if title else "") + body
    units = len(text.encode("utf-16-le")) // 2
    length = len(text)
    if units > 500:
        raise ValueError("Generated content exceeds the Threads text budget")
    bucket = next((key for key, (low, high) in LENGTH_TARGETS.items()
                   if low <= length <= high), "compact" if length < 50 else "extended")
    low, high = LENGTH_TARGETS[target]
    return {
        "theme": theme, "text": text, "format": FORMATS[arm], "subformat": style,
        "version": VERSION, "pair_id": pair_id, "pair": pair_id,
        "arm": "ABCD"[arm], "experiment": "competitor_format_exploration",
        "hypothesis": hypothesis, "comparison_design": comparison,
        "compared_to_arm": None if arm == 0 else "A",
        "controlled_factor": controlled_factor,
        "is_control": arm == 0,
        "factors": {
            "title": title, "title_present": bool(title),
            "item_count": len(items), "items": list(items),
            "max_columns": max_columns, "columns_per_row": [len(row) for row in rows],
            "gap": gap, "blank_lines_between_rows": False,
            "content_kind": style,
        },
        "items": len(items), "codepoint_length": length, "utf16_length": units,
        "visible_unit_proxy": sum(unicodedata.category(c) not in {"Mn", "Me", "Cf"}
                                  for c in text if not c.isspace()),
        "visible_unit_proxy_note": "Non-mark non-whitespace codepoints; not Unicode graphemes",
        "line_count": len(text.splitlines()), "body_line_count": len(rows),
        "max_line_cells_estimate": max(map(display_cells, text.splitlines())),
        "whitespace_ratio": sum(c.isspace() for c in text) / length,
        "length_bucket": bucket, "length_target": target,
        "length_target_range": [low, high], "length_target_met": low <= length <= high,
        "causal_limit": "Exploratory posts; exposure time and slot balance must be assessed before causal conclusions.",
    }


def _family(theme, cycle, attempt):
    rng = random.Random(f"{VERSION}:{theme}:{cycle}:{attempt}")
    atoms = rng.sample(POOLS[theme].split("|"), len(POOLS[theme].split("|")))
    pair_id = f"{VERSION}:{theme}:{cycle}:{attempt}"
    gap = "　"
    base_target = "medium" if theme in FACE_THEMES else "short"
    shared = dict(theme=theme, gap=gap, pair_id=pair_id)
    control = _make_post(
        **shared, items=atoms[:12], title=theme, max_columns=3, arm=0,
        style="symbol_dictionary", hypothesis="Reference: original 12-item themed grid.",
        comparison="reference", controlled_factor=None, target=base_target,
    )
    expanded_atoms = atoms + [f"{accent} {atoms[i]} {accent}"
                             for i, accent in enumerate(["✧", "♡", "⊹", "⋆", "˚", "⟡", "୨୧", "˖"])]
    expanded = _make_post(
        **shared, items=expanded_atoms, title=theme, max_columns=3, arm=1,
        style="extended_symbol_dictionary", hypothesis="More choices and ready-to-use accents may increase reuse.",
        comparison="multivariate_exploratory_with_matched_prefix", controlled_factor=None,
        target="long" if theme in FACE_THEMES else "medium",
    )
    style = ("mixed_face_dictionary", "ready_to_use_dividers", "ready_to_use_bio")[
        (list(POOLS).index(theme) + cycle) % 3]
    decorated = _decorate(theme, atoms, rng, style)
    mixed = _make_post(
        **shared, items=decorated, title=USECASE_TITLES[theme],
        max_columns=2 if style == "mixed_face_dictionary" else 1, arm=2,
        style=style, hypothesis="Original complete combinations may be easier to reuse.",
        comparison="multivariate_exploratory", controlled_factor=None,
        target="long" if theme in FACE_THEMES and style == "mixed_face_dictionary" else "medium",
    )
    title = "" if cycle % 2 == 0 else USECASE_TITLES[theme]
    title_variant = _make_post(
        **shared, items=atoms[:12], title=title, max_columns=3, arm=3,
        style="symbol_dictionary", hypothesis=("A titleless grid may improve immediate readability."
               if not title else "A concrete use-case title may make the same symbols more useful."),
        comparison="single_factor_title", controlled_factor="title", target=base_target,
    )
    return [control, expanded, mixed, title_variant]


def build_posts(count, exclude_texts=()):
    """Return deterministic originals with balanced themes and ~25% controls.

    Every consecutive twelve slots cover all themes. Each theme has four arms
    per complete 48-slot cycle. A/B/D share their first twelve symbols. D changes
    only the title; B adds both quantity and composed choices and C changes the
    format, so B/C are explicitly multivariate. Exclusions
    regenerate a whole family to retain these comparisons. Incomplete final
    families are labeled, not presented as complete matched comparisons.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    if isinstance(exclude_texts, str):
        raise TypeError("exclude_texts must be an iterable of complete post strings")
    excluded = set(exclude_texts)
    themes = list(POOLS)
    families, reserved, posts = {}, set(excluded), []
    for slot in range(count):
        theme_index = slot % len(themes)
        round_index = slot // len(themes)
        cycle = round_index // 4
        theme = themes[theme_index]
        key = (theme, cycle)
        if key not in families:
            for attempt in range(1000):
                family = _family(theme, cycle, attempt)
                texts = {p["text"] for p in family}
                if len(texts) == 4 and not (texts & reserved):
                    families[key] = family
                    reserved.update(texts)
                    break
            else:
                raise ValueError("Unable to generate a unique family within the candidate budget")
        arm = (round_index + theme_index) % 4
        posts.append(families[key][arm])
    included = {}
    for post in posts:
        included.setdefault(post["pair_id"], []).append(post["arm"])
    for post in posts:
        post["available_arms"] = sorted(included[post["pair_id"]])
        post["family_complete"] = len(post["available_arms"]) == 4
        post["reference_available"] = "A" in post["available_arms"]
    return posts
