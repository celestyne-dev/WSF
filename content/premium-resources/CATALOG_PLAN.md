# Think Positive Always: Catalog Plan & Product Copy

Prepared 20 Nov 2026. Covers: the five rewritten titles, catalog clean-up, new titles across free / premium / Circle tiers, collections, pricing, support (coaching) offers, and a LinkedIn launch plan.

---

## 1. What's ready now

All five premium titles are written from scratch and built as print-ready A4 PDFs (fonts embedded, ink-light interiors, write-in lines and tables for home printing). Each folder also has a `cover.png` (1200×1699) for the product card.

| Title | Admin type | File | Pages | Who it's for |
|---|---|---|---|---|
| The Power of Starting Again | eBook | `the-power-of-starting-again/the-power-of-starting-again.pdf` | 35 | Women rebuilding after redundancy, a closed business, divorce, relocation or a career gap |
| The 30-Day Mindset Reset Workbook | Workbook | `the-30-day-mindset-reset-workbook/…pdf` | 40 | Busy professionals who feel stuck, anxious or self-critical and want a structured month |
| The Daily Reflection Journal | Journal | `the-daily-reflection-journal/…pdf` | 115 | Anyone building a daily habit: 90 guided days, weekly reviews, 30/60/90 check-ins |
| The Confidence & Self-Worth Workbook | Workbook | `the-confidence-and-self-worth-workbook/…pdf` | 28 | Women dealing with imposter feelings, speaking up, negotiating pay and visibility |
| The Letting Go & Moving Forward Guide | Guide | `the-letting-go-and-moving-forward-guide/…pdf` | 20 | Women processing an ending: job, relationship, regret, old identity, family expectations |

### Upload steps (per title)
1. **Admin → Premium Resources → edit the title.**
2. Upload the PDF as the protected file. Set **File format = PDF** and **Page count** from the table.
3. Upload `cover.png` as the cover image.
4. Paste the short description and "What's inside" copy from §2.
5. Download it once yourself as a test purchase before announcing.

To edit text later, change `manuscript.md` (or `generate.py` for the workbook and journal) and run `content/premium-resources/_build/build.sh`. See `README.md`.

---

## 2. Product page copy (paste-ready)

### The Power of Starting Again (eBook)
**Short description:** An honest, practical companion for women rebuilding after a redundancy, a closed business, a divorce or a career gap. Starting again isn't starting over. You carry everything you've learned.

**What's inside**
- 10 short chapters on grief, reframing, money fear, telling your story and building your circle
- Scripts for LinkedIn announcements, reconnect messages and "So what are you doing now?"
- A 30-day restart plan with an input tracker
- Printable write-in exercises after every chapter

### The 30-Day Mindset Reset Workbook
**Short description:** Thirty short, practical days to quiet the inner critic, rebuild your focus and choose your thoughts on purpose. About 15 minutes a day.

**What's inside**
- 4 themed weeks: Notice, Reframe, Act, Become
- A daily idea, a reflection prompt and one small action
- A before-and-after self-assessment, plus weekly reviews
- A personal "reset kit" to use on hard days

### The Daily Reflection Journal
**Short description:** Ninety days of five-minute mornings and evenings for a calmer mind, clearer priorities and a kinder voice in your head.

**What's inside**
- 90 guided daily pages, each with a unique prompt
- 3 seasons: Presence, Courage, Purpose
- 13 weekly reviews and 30/60/90-day check-ins
- Print one week at a time, or have the whole journal bound

### The Confidence & Self-Worth Workbook
**Short description:** Practical exercises to quiet self-doubt, own your strengths and take up the space you've earned, in meetings, in pay conversations and online.

**What's inside**
- 8 modules: worth, imposter feelings, strengths, speaking up, negotiation, boundaries, self-respect, visibility
- Pay-rise and offer negotiation scripts, plus a brag-document template
- The "strengths mirror" feedback exercise
- A 21-day confidence challenge

### The Letting Go & Moving Forward Guide
**Short description:** A reflective guide for releasing what no longer serves you (old hurts, regrets, roles and expectations) so you can walk lighter into what's next.

**What's inside**
- 7 parts: endings, resentment, regret, old identities, control, others' expectations, moving forward
- The unsent-letter practice and closure-ritual ideas
- Circle-of-control and "whose voice is this?" worksheets
- A next-chapter plan

---

## 3. Clean-up: remove or fix now

| Item | Problem | Action |
|---|---|---|
| **TPA Checkout Test Guide** | A test product that is live **inside the featured Fresh Start Collection** on the homepage | Remove it from the collection today. Set its Product to **archived** and its Resource to **archived**. Don't delete it if any test orders reference it, because order items point to the product. |
| **The 30-Day Positive Mindset Reset** | Duplicates *The 30-Day Mindset Reset Workbook*. Two near-identical names confuse buyers and split reviews. | Keep **The 30-Day Mindset Reset Workbook**. Archive the duplicate. If anyone bought the duplicate, give them access to the workbook through Download Entitlements so they still get the new file. Add a redirect from the old slug if the platform's redirect tool supports products. |
| Category "Guides & resources" | Vague | Rename to **Guides** (keep slug `guides`). |
| Category counts | They will change after the archive above | Check them after the clean-up. eBooks should show 1 or 2, not counting the test guide. |
| Product "type" labels | The journal shows as "Digital journal" but resource types have no Journal option | Use the **Planner** type for the journal, or keep the label in the subtitle only. |

---

## 4. Collections

Keep 3 or 4 collections, each with a clear promise. Too many collections make a small catalog feel thin.

| Collection | Promise | Titles (✔ = ready now, ✚ = new, see §5) | Feature on homepage? |
|---|---|---|---|
| **The Fresh Start Collection** (cleaned up) | "For when a chapter ends" | ✔ Power of Starting Again · ✔ Letting Go & Moving Forward · ✔ 30-Day Mindset Reset · ✔ Daily Reflection Journal | Yes (current) |
| **The Own Your Worth Collection** (new) | "Confidence for your career" | ✔ Confidence & Self-Worth · ✚ Ask For It (negotiation) · ✚ Visible (LinkedIn brand) · ✚ The Boundaries Workbook | Yes, rotate with Fresh Start |
| **The Career Comeback Collection** (new, made for the LinkedIn audience) | "Back to work, on your terms" | ✔ Power of Starting Again · ✚ Career Comeback Playbook · ✚ Interview Confidence Kit · ✚ Redundancy First-Week Checklist (free) | Seasonal (January/February) |
| **Daily Calm** (new, later) | "Small rituals, steady mind" | ✔ Daily Reflection Journal · ✚ Gratitude Journal · ✚ Burnout Recovery Guide · ✚ 2027 Reset Planner | Optional |

**Bundles** (Admin → Bundles): turn the Fresh Start and Own Your Worth collections into bundles at roughly 30% off the individual prices.

---

## 5. New titles to add

### Free (lead magnets: access type *email gate*)
These grow your newsletter. Each one leads naturally to a paid title.

| Title | Format | Leads to |
|---|---|---|
| **The 7-Day Positive Mindset Starter** | 7-page PDF plus a 7-email automation | 30-Day Mindset Reset Workbook |
| **Redundancy First-Week Checklist** | 2-page checklist | Power of Starting Again |
| **The LinkedIn Comeback Post Template** | 1-page fill-in template | Power of Starting Again / Visible |
| **Imposter Syndrome Reality Check** | 1-page worksheet | Confidence & Self-Worth |
| **50 Journal Prompts for Hard Seasons** | 5-page PDF | Daily Reflection Journal |
| **The Pay-Rise Script Card** | 1-page card | Ask For It |

Start with the **7-Day Starter** and the **Redundancy Checklist**. They match what your LinkedIn audience is going through right now.

### Premium (one-off purchase)

| Title | Format | Why it fits your audience |
|---|---|---|
| **The 2027 Reset Planner** | Undated-month annual planner + goal workbook | **Launch before mid-December.** January is the biggest buying month for planners and reset content. |
| **Ask For It: The Negotiation Workbook for Women** | Workbook | Pay is one of the most-discussed topics among professional women on LinkedIn |
| **Visible: A LinkedIn Personal-Brand Workbook** | Workbook | Your audience already lives on LinkedIn |
| **The Career Comeback Playbook** | eBook | For returners after maternity leave, caregiving, illness or relocation |
| **The Burnout Recovery Guide** | Guide | High-achiever burnout is a major pain point |
| **The Boundaries Workbook** | Workbook | Extends Module 6 of the confidence workbook |
| **Interview Confidence Kit** | Toolkit (question bank, STAR stories, prep sheets) | A practical, high-intent purchase |
| **Leading With Heart: A First-Time Manager's Guide** | Guide | For newly promoted women |
| **Money Peace Workbook** | Workbook | Financial confidence and calm, not investment advice. Have a qualified person review it. |
| **The Gratitude Journal** | Journal | A low-price entry product |

### WSF Circle (members) and Yearly Bonus Vault
Use *circle_only* for the monthly perks and *yearly_members* for the vault:
- **Monthly mini-workbook** (8 to 10 pages on one theme per month). Turn one Daily Reflection Journal season into each one.
- **Masterclass recordings** with downloadable worksheets.
- **Yearly vault:** the 2027 Reset Planner, the full Daily Reflection Journal, and a quarterly "Reset Week" pack.

---

## 6. Pricing ladder (suggested, in KES)

Check these against your current prices and your Paystack fees before setting them.

| Tier | Example | Suggested price |
|---|---|---|
| Free | Lead magnets | 0 (email gate) |
| Entry | Gratitude Journal, Letting Go Guide | KES 500 to 900 |
| Core | eBook, Daily Reflection Journal | KES 900 to 1,500 |
| Workbook | 30-Day Reset, Confidence & Self-Worth | KES 1,500 to 2,500 |
| Bundle | Fresh Start (4 titles) | about 30% off the combined price |
| Membership | WSF Circle | Monthly and yearly. The yearly plan includes the vault. |
| Support | Coaching sessions and group circles (§7) | Highest tier |

---

## 7. Offering support sessions ("counsel")

There is clear demand: the books invite readers to get support, and a guided session is the natural next step after a workbook.

**Important: word it carefully.** In Kenya, *counselling* and *psychology* are regulated professions under the Counsellors and Psychologists Act (2014). Unless the person delivering the session is a registered counsellor, call it **coaching** or **guided sessions**. Do not call it counselling or therapy. Include a short note in every booking that sessions are not therapy, and refer people to licensed professionals when needed. Consider partnering with one or two registered counsellors as a referral network.

| Offer | Format | Built on | How to sell it on the platform |
|---|---|---|---|
| **Restart Session** | 1:1, 60 min, video call | Power of Starting Again | Product with type **service** |
| **Confidence Coaching** | 1:1, 3 × 45 min (negotiation, promotion or interview prep) | Confidence & Self-Worth | Product with type **service** |
| **Moving Forward Session** | 1:1, 60 min | Letting Go Guide | Product with type **service** |
| **Mindset Reset Circles** | Group of 6 to 10 women, 4 weekly sessions, workbook included | 30-Day Mindset Reset | Event or service product, sold by cohort |
| **Peer mentoring** | Matched pairs | Your existing Mentorship programmes | Admin → Mentorship |

Every book already has a back-page call to action pointing to these offers: Restart Sessions, Mindset Reset Circles, Confidence Coaching and Moving Forward Sessions. Set them up under those names, or tell me the names you'd rather use and I'll update the books.

---

## 8. LinkedIn launch plan (4 weeks per title)

Each book contains about a dozen ready-made posts. Repurpose them instead of writing new content.

| Week | Post ideas (taken from the book) | Call to action |
|---|---|---|
| 1 | A story-led post ("Eleven years, and I'm back at zero"), a "starting again ≠ starting over" carousel, a poll ("What's the hardest part of a restart?") | Free Redundancy Checklist |
| 2 | The three-sentence answer script, the two-percent rule, the comparison-trap boundaries | 7-Day Mindset Starter |
| 3 | A page preview (photo of a printed workbook page), a founder note on why you wrote it | Buy the book |
| 4 | Reader responses (with permission), a Fresh Start bundle offer, an open call for a Mindset Reset Circle cohort | Bundle / Circle |

Use UTM tags on every link. The site already supports LinkedIn/UTM tracking, so you can see which posts lead to sales.

**Newsletter automations:** for each lead magnet, set up welcome → value → value → product offer, spread over 7 days.

---

## 9. Next steps checklist

- [ ] Remove TPA Checkout Test Guide from the Fresh Start Collection and archive it
- [ ] Archive the duplicate "30-Day Positive Mindset Reset" (move any buyers to the workbook)
- [ ] Upload the five PDFs and covers, paste the copy from §2, and test-download each one
- [ ] Rebuild Fresh Start as 4 titles and create a Fresh Start bundle
- [ ] Choose your support offer names and set them up as service products
- [ ] Commission the **2027 Reset Planner**, the **7-Day Starter** and the **Redundancy Checklist** first (December timing)
- [ ] Start the 4-week LinkedIn plan for *The Power of Starting Again*
