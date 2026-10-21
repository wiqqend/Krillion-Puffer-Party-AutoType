import argparse
import json
import random
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ARCHIVE = "https://www.linkedinpinpointanswer.today/krillion-answers/archive"
GAME = "https://krillion.io/party"
DB = Path("answers.json")
PROFILE = Path("profile")
MAX_ARCHIVE_PAGES = 5
STORE_MIN = 60

TURN_RE = re.compile(r"your puffer\s*\W+\s*type", re.I)
INPUT_PLACEHOLDER = re.compile(r"puffer", re.I)
SEND_NAME = re.compile(r"^send$", re.I)

STOP = {"name", "the", "and", "that", "with", "like", "for", "are", "things",
        "something", "made", "from", "you", "can"}
SKIP = re.compile(
    r"almost no player|genuinely obscure|minority of players|middling pick|"
    r"most common answer|^show answers|^hide answers|^expand list|^full rarity|"
    r"^back to prompts|^find an answer|^show best|^reveal all|^hide all|"
    r"^search reveals|accepted answers across|^\d[\d,]* answers?$|"
    r"^(one in a krillion|deep cut|rare|schooler|plankton)$", re.I)

JS_PROMPT = r"""() => {
  const re = /^\s*Name\b.{6,}/i;
  let best = null, size = 0;
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const n = w.currentNode, t = n.textContent.trim();
    if (!re.test(t)) continue;
    const e = n.parentElement;
    if (!e) continue;
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const fs = parseFloat(getComputedStyle(e).fontSize);
    if (fs > size) { size = fs; best = t; }
  }
  return best;
}"""

def parse(text, min_pts=STORE_MIN):
    lines = [s.strip() for s in text.splitlines() if s.strip()]
    out, cur, pts, i = [], None, 0, 0
    while i < len(lines):
        s = lines[i]
        if re.fullmatch(r"prompt \d+ of \d+", s, re.I):
            cur = {"p": lines[i + 1] if i + 1 < len(lines) else "", "a": []}
            out.append(cur)
            pts = 0
            i += 2
            continue
        m = re.match(r"(\d{2,3})\s*pts", s, re.I)
        if m:
            pts = int(m.group(1))
        elif cur and pts >= min_pts and not SKIP.search(s):
            s = re.split(r"\s[—–-]\s|—", s)[0].strip()
            if s and len(s) <= 60:
                cur["a"].append([s, pts])
        i += 1
    return [d for d in out if d["p"] and d["a"]]

def load():
    return json.loads(DB.read_text("utf-8")) if DB.exists() else []

def merge(db, new):
    seen = {d["p"] for d in new}
    return [d for d in db if d["p"] not in seen] + new

def save(db):
    DB.write_text(json.dumps(db, ensure_ascii=False), "utf-8")

def build():
    db = load()
    have = {d["p"] for d in db}
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        page = br.new_page()
        days = []
        for n in range(1, MAX_ARCHIVE_PAGES + 1):
            page.goto(f"{ARCHIVE}?page={n}", wait_until="networkidle")
            links = page.eval_on_selector_all(
                "a[href*='/krillion-answers/']", "els => els.map(e => e.href)")
            found = [u for u in links if re.search(r"/\d{4}-\d{2}-\d{2}$", u)]
            if not found:
                break
            days += [u for u in found if u not in days]
        print(f"Found {len(days)} days")
        for u in days:
            page.goto(u, wait_until="networkidle")
            for b in page.get_by_role("button", name=re.compile("reveal all tiers", re.I)).all():
                try:
                    b.click(timeout=1500)
                except Exception:
                    pass
            docs = [d for d in parse(page.inner_text("body")) if d["p"] not in have]
            have |= {d["p"] for d in docs}
            db = merge(db, docs)
            print(u.rsplit("/", 1)[-1], "new prompts:", len(docs))
            save(db)
        br.close()
    print("Saved", len(db), "prompts to", DB)

def tokens(s):
    return [w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()
            if len(w) > 2 and w not in STOP]

def best_match(prompt, db):
    qt = tokens(prompt)
    best, best_score = None, 0
    for d in db:
        if d["p"].strip().lower() == prompt.strip().lower():
            return d
        dt = set(tokens(d["p"]))
        score = sum(1 for w in qt if w in dt) / len(qt) if qt else 0
        if score > best_score:
            best, best_score = d, score
    return best if best_score >= 0.6 else None

def get_prompt(page):
    try:
        return page.evaluate(JS_PROMPT)
    except Exception:
        return None

def my_turn(page, box):
    try:
        if not box.is_enabled() or not box.is_editable():
            return False
        return bool(TURN_RE.search(page.inner_text("body")))
    except Exception:
        return False

def pick(doc, used, body, min_pts):
    free = []
    for ans, pts in doc["a"]:
        key = ans.lower()
        if pts < min_pts or key in used:
            continue
        if re.search(r"\b" + re.escape(key) + r"\b", body):
            continue
        free.append((ans, pts))
    if not free:
        return None
    top = max(p for _, p in free)
    return random.choice([a for a, p in free if p == top])

def submit(page, box, ans):
    box.click()
    box.fill("")
    box.type(ans, delay=random.randint(15, 45))
    box.press("Enter")
    time.sleep(0.3)
    try:
        if box.input_value() == ans:
            page.get_by_role("button", name=SEND_NAME).first.click(timeout=800)
    except Exception:
        pass
    time.sleep(0.6)
    try:
        return box.input_value() != ans
    except Exception:
        return True

def inspect(page):
    print("Category:", get_prompt(page))
    box = page.get_by_placeholder(INPUT_PLACEHOLDER).first
    print("Answer box found:", box.count() > 0)
    if box.count():
        print("Box enabled:", box.is_enabled(), "| editable:", box.is_editable())
    body = page.inner_text("body")
    print("Turn text detected:", bool(TURN_RE.search(body)))
    print("--- visible text (first 1500 chars) ---")
    print(body[:1500])

def run(mode, dry=False, min_pts=60):
    db = load()
    if mode == "play" and not db:
        raise SystemExit("answers.json is empty. Run --build first.")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(GAME)
        input("Join a lobby in the browser, then press Enter here: ")
        if mode == "inspect":
            inspect(page)
            ctx.close()
            return
        box = page.get_by_placeholder(INPUT_PLACEHOLDER).first
        used, last = set(), None
        print("Playing. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(0.25)
                prompt = get_prompt(page)
                if not prompt:
                    continue
                if prompt != last:
                    used, last = set(), prompt
                    print("\nCategory:", prompt)
                if not my_turn(page, box):
                    continue
                doc = best_match(prompt, db)
                if not doc:
                    print("  No archive match for this category.")
                    time.sleep(2)
                    continue
                body = page.inner_text("body").lower().replace(prompt.lower(), "")
                ans = pick(doc, used, body, min_pts)
                if not ans:
                    print("  Out of answers for this category.")
                    time.sleep(2)
                    continue
                used.add(ans.lower())
                pts = next(p for a, p in doc["a"] if a == ans)
                print(f"  Answer: {ans} ({pts} pts)")
                if dry:
                    time.sleep(2)
                    continue
                ok = submit(page, box, ans)
                print("  accepted" if ok else "  rejected, trying another")
                if ok:
                    time.sleep(1.0)
        except KeyboardInterrupt:
            print("Stopped.")
        ctx.close()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--paste", metavar="FILE")
    a = ap.parse_args()
    if a.build:
        build()
    elif a.paste:
        docs = parse(Path(a.paste).read_text("utf-8"))
        save(merge(load(), docs))
        print("Added", len(docs), "prompts")
    elif a.inspect:
        run("inspect")
    else:
        run("play", dry=a.dry, min_pts=85 if a.strict else 60)
