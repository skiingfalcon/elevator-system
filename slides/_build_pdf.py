"""Assemble the slide PNGs into a single landscape PDF in narrative order."""
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
ORDER = [
    "title",               # title slide — Kaushik Ghosh
    "approach",            # problem + 3 requirements -> 3 decisions
    "highlevelflow",       # architecture
    "scheduling",          # the scheduler / cost function
    "passengermodel",      # data model
    "results",             # fairness vs efficiency (NEW)
    "complexity_analysis", # performance
    "improvement",         # roadmap
]

pages = []
for name in ORDER:
    p = HERE / f"{name}.png"
    if not p.exists():
        raise SystemExit(f"missing slide: {p}")
    img = Image.open(p).convert("RGB")
    pages.append(img)

out = HERE / "elevator_design_deck.pdf"
pages[0].save(
    out,
    "PDF",
    resolution=144.0,
    save_all=True,
    append_images=pages[1:],
)
print(f"Wrote {out}  ({len(pages)} pages)")
for i, name in enumerate(ORDER, 1):
    print(f"  {i}. {name}")
