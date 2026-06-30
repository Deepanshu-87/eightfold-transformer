"""Generate the Stage-1 one-page Technical Design PDF.

Run:
    python design/build_pdf.py
"""
import os
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Preformatted, KeepTogether,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "Deepanshu Kumar_deep212002@gmail.com_Eightfold.pdf")

ACCENT = HexColor("#1f4e96")
INK = HexColor("#111418")
MUTED = HexColor("#3b4252")


def build():
    doc = SimpleDocTemplate(
        OUT, pagesize=LETTER,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
        topMargin=0.45 * inch, bottomMargin=0.45 * inch,
        title="Multi-Source Candidate Data Transformer — Technical Design",
        author="Deepanshu Kumar",
    )
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Title"], fontName="Helvetica-Bold",
                       fontSize=14, leading=16, textColor=ACCENT, alignment=TA_LEFT,
                       spaceAfter=2)
    sub = ParagraphStyle("sub", parent=ss["Normal"], fontSize=8.5, textColor=MUTED,
                         leading=11, spaceAfter=6)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                        fontSize=10, leading=12, textColor=ACCENT,
                        spaceBefore=4, spaceAfter=2)
    body = ParagraphStyle("body", parent=ss["Normal"], fontSize=8.7, leading=11,
                          textColor=INK, spaceAfter=2)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=10, bulletIndent=0,
                            spaceAfter=1)
    mono = ParagraphStyle("mono", parent=body, fontName="Courier", fontSize=7.5,
                          leading=9, leftIndent=4)

    story = []

    story.append(Paragraph("Multi-Source Candidate Data Transformer — Technical Design", H1))
    story.append(Paragraph(
        "Deepanshu Kumar &nbsp;·&nbsp; deep212002@gmail.com &nbsp;·&nbsp; "
        "Eightfold Engineering Intern (Jul–Dec 2026) &nbsp;·&nbsp; Stage 1", sub))

    story.append(Paragraph("Problem framing", H2))
    story.append(Paragraph(
        "Many noisy sources (CSV, ATS JSON, resumes, recruiter notes) describe the same candidate "
        "in conflicting ways. Downstream products need <b>one</b> canonical profile per person "
        "with normalized formats, deduped values, a record of where each value came from "
        "(provenance), and a calibrated confidence. The cost of a wrong-but-confident value is "
        "high: it silently pollutes hiring decisions. Honest-empty &gt; wrong-confident.", body))

    story.append(Paragraph("Pipeline", H2))
    story.append(Paragraph(
        "<b>detect → extract → normalize → merge → confidence → project-to-output → validate</b>. "
        "Each stage is a pure function over the previous stage's output, which makes the run "
        "deterministic and easy to test. The internal canonical record is the single source of "
        "truth; projection is a thin layer that <i>reshapes</i> but never <i>mutates</i> it.", body))

    story.append(Paragraph("Canonical schema &amp; normalized formats", H2))
    for b in [
        "<b>phones</b>: E.164 (e.g. <i>+14155552671</i>); region inferred from country, else US default.",
        "<b>dates</b>: <i>YYYY-MM</i>. \"present\"/\"now\" → null on the <i>end</i> field.",
        "<b>country</b>: ISO-3166 alpha-2 via small alias map (USA→US, UK→GB, India→IN, ...).",
        "<b>skills</b>: dictionary-based canonical names (js→JavaScript, k8s→Kubernetes, ...). Unknown skills pass through verbatim (no invented canonicalization).",
        "<b>emails</b>: lower-cased, regex-validated; bad strings drop to null.",
    ]:
        story.append(Paragraph("• " + b, bullet))

    story.append(Paragraph("Merge &amp; conflict-resolution policy", H2))
    story.append(Paragraph(
        "Identity is resolved by <b>union-find</b> over three match keys (in order): "
        "<i>normalized email</i> → <i>E.164 phone</i> → <i>normalized full name</i>. "
        "Conflicting scalars (full_name, headline, location.*) are won by <b>source priority</b> "
        "(<i>ats_json=5, recruiter_csv=4, resume=3, notes=2</i>); ties → first non-empty. "
        "List fields (emails, phones, education, experience) are unioned and deduped by stable keys. "
        "Skills are merged by canonical name; corroboration boosts confidence with diminishing "
        "returns: <i>c' = 1 &#8722; (1&#8722;c<sub rise=2 size=6>1</sub>)(1&#8722;c<sub rise=2 size=6>2</sub>)</i>, capped at 0.99. No source is allowed to invent a "
        "value missing from its own input.", body))

    story.append(Paragraph("Confidence", H2))
    story.append(Paragraph(
        "Per-field score from the top source's base (priority→base map) plus corroboration "
        "boost per additional source. <b>overall_confidence</b> is a weighted mean over present "
        "fields only — empty fields contribute zero weight and don't inflate the score. "
        "<i>Provenance is a first-class output</i>: every populated field carries (field, source, "
        "method) so reviewers can audit any number.", body))

    story.append(Paragraph("Runtime custom-output config", H2))
    story.append(Paragraph(
        "A JSON config describes the desired shape: subset of fields, renames via <i>from</i> "
        "(supports dotted paths, <i>[N]</i> indexing, <i>[]</i> flattening), per-field "
        "<i>normalize</i> (E164, canonical) and type coercion, plus <i>on_missing</i> ∈ "
        "{null, omit, error} and toggles for provenance / confidence. Projection is validated "
        "against the requested shape; the canonical record is untouched, so two configs against "
        "the same inputs are guaranteed consistent.", body))
    story.append(Preformatted(
        '{ "fields": [ {"path":"primary_email","from":"emails[0]","required":true},\n'
        '              {"path":"phone","from":"phones[0]","normalize":"E164"},\n'
        '              {"path":"skills","from":"skills[].name","normalize":"canonical"} ],\n'
        '  "include_confidence": true, "on_missing": "null" }',
        mono))

    story.append(Paragraph("Edge cases — what I handle, what I cut", H2))
    edges = [
        "<b>Same person across sources, different phone formats</b> → normalized to E.164 before identity match; one record out.",
        "<b>Conflicting full_name (\"Jane Doe\" vs \"Jane D.\")</b> → matched on shared email; ATS wins by priority.",
        "<b>Garbage row</b> (country \"Atlantis\", phone \"abc\") → fields drop to null, profile still emitted; provenance shows nothing was promoted.",
        "<b>Missing source file</b> → warning logged, pipeline continues with remaining sources.",
        "<b>No identity signal</b> (recruiter notes with no email/phone) → kept as its own record rather than guessing identity (false-merge would be worse than a duplicate).",
        "<b>Descoped under time pressure</b>: live GitHub/LinkedIn fetching, PDF/DOCX → text conversion, fuzzy name matching. Modules are stubbed for easy add-on.",
    ]
    for e in edges:
        story.append(Paragraph("• " + e, bullet))

    story.append(KeepTogether([
        Paragraph("Constraints met", H2),
        Paragraph(
            "<b>Deterministic &amp; explainable</b>: same inputs → same output (verified by test). "
            "Every value is traceable via provenance. "
            "<b>Robust</b>: missing/garbage sources never crash the run; unknown values stay null. "
            "<b>Scale</b>: pure-Python pipeline is O(N) per source; identity uses union-find — "
            "comfortable on thousands of candidates on a laptop. "
            "<b>Surface</b>: a thin CLI (<i>python -m src.cli --csv … --ats … --config … --out …</i>).",
            body),
    ]))

    doc.build(story)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
