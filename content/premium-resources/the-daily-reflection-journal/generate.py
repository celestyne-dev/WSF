"""Generates manuscript.md for The Daily Reflection Journal (90 guided days).

    python3 generate.py && ../_build/build.sh the-daily-reflection-journal
"""
from pathlib import Path

FRONT = """---
title: "The Daily Reflection Journal"
subtitle: "Ninety days of five-minute mornings and evenings for a calmer mind, clearer priorities and a kinder voice in your head"
coverbg: "#f3ece4"
kind: journal
kindlabel: "Guided journal"
---

# [Welcome]{.num}Five minutes, twice a day

Most of us move through our days at speed. We wake up already thinking about the inbox, rush from one responsibility to the next, and fall into bed replaying what went wrong. Weeks pass. Months pass. We are busy, but we rarely stop long enough to notice how we are actually doing, or whether the way we're spending our days matches what matters to us.

This journal is an invitation to pause. Not for an hour. Just five minutes in the morning and five minutes in the evening.

In those ten minutes, you'll do three simple but powerful things:

- **Begin on purpose.** Set an intention before the day sets one for you.
- **Notice what's good.** Train your attention to see progress and gratitude, not only problems.
- **Close the loop.** End the day by acknowledging what went well and letting go of what didn't.

Over ninety days, those small moments add up to something significant: a clearer sense of who you are, what you want and how far you've already come.

## How each day works

**In the morning** (about five minutes):

1. Write the date.
2. Write one thing you're grateful for. Be specific.
3. Choose your *one thing*: the most important thing you'll do today.
4. Answer the day's reflection prompt in a few lines.

**In the evening** (about five minutes):

1. Note one win from today, however small.
2. Write down anything you want to release before you sleep.
3. Rate your mood and energy.

## The three seasons of this journal

The ninety days are grouped into three thirty-day seasons. Each has its own theme for the daily prompts:

- **Days 1 to 30: Presence.** Noticing your life as it is, with gratitude and honesty.
- **Days 31 to 60: Courage.** Growing past fear, self-doubt and old stories.
- **Days 61 to 90: Purpose.** Clarifying what matters and building a life around it.

At the end of each week you'll find a short weekly review. At days 30, 60 and 90 you'll find a deeper check-in.

## If you miss a day

You will miss days. Everyone does. Don't go back and fill them in, and don't feel guilty. Simply turn to the next blank page and begin again. The journal is not a test. It's a companion.

<div class="box">

### A note on printing

This journal is designed to be printed on A4 paper, single or double-sided. Many women print one week at a time and keep the pages in a folder or ring binder. If you prefer a bound journal, any local print shop can bind it for you.

</div>

# [Before you begin]{.num}My ninety-day intention

**Today's date:** ______________________

**Why I'm starting this journal now:**

<div class="write l4"></div>

**Three words I want to describe me ninety days from now:**

1. __________________________  2. __________________________  3. __________________________

**What I want more of in my life:**

<div class="write l3"></div>

**What I want less of:**

<div class="write l3"></div>

**A promise I'm making to myself:**

<div class="write l3"></div>
"""

SEASONS = {
    1: ("Season one", "Presence", "For the next thirty days, the prompts invite you to notice your life as it is right now: what's good, what's hard, what you feel and what you need. You can't change your direction until you know where you're standing."),
    31: ("Season two", "Courage", "This season's prompts ask you to look at fear, self-doubt and the stories that keep you small, and to take small brave steps anyway. Courage isn't the absence of fear. It's deciding something matters more."),
    61: ("Season three", "Purpose", "In this final season, the prompts help you clarify what truly matters to you and how to build more of your days around it, at work, at home and in your community."),
}

PROMPTS = [
    # Presence (1-30)
    "What does a genuinely good day look like for me right now, not someday, but in this season of my life?",
    "Which moment from yesterday would I like to remember? Why?",
    "Where in my body do I feel tension this morning? What might it be telling me?",
    "Who made my life easier this week, and do they know it?",
    "What am I carrying today that isn't mine to carry?",
    "What is one small pleasure I often rush past? How could I enjoy it today?",
    "If my week had a headline, what would it be?",
    "What am I proud of that nobody else knows about?",
    "What has been taking up the most space in my mind lately?",
    "When did I last feel completely at ease? Where was I, and who was I with?",
    "What do I need more of this week: rest, connection, challenge, or fun?",
    "Which part of my daily routine do I actually love?",
    "What's a compliment I received recently that I brushed off? Let me receive it now.",
    "What am I tolerating that I don't need to tolerate?",
    "What is going well that I haven't stopped to acknowledge?",
    "How have I grown in the last twelve months?",
    "What does my phone use say about how I feel right now?",
    "What would I do today if I trusted myself completely?",
    "What is something I learned from my mother, grandmother or another woman who raised me?",
    "Which room, place or space makes me feel most like myself?",
    "What am I looking forward to, this week or this year?",
    "What does 'enough' look like for me: money, work, rest, success?",
    "Which emotion have I been avoiding? What happens if I let myself feel it for a minute?",
    "Who in my life brings out the best version of me?",
    "What did I do recently that my younger self would be amazed by?",
    "What's one thing I can simplify this week?",
    "What would I like to say 'no' to more often?",
    "What made me laugh recently?",
    "What does my body need from me today?",
    "Looking back on these thirty days, what have I started to notice about myself?",
    # Courage (31-60)
    "What is one thing I've been putting off because I'm afraid? What exactly am I afraid of?",
    "When have I been braver than I expected? What did that teach me?",
    "What would I attempt if I knew I couldn't fail?",
    "What would I attempt even if I knew I might fail?",
    "What does my inner critic say most often? What would I say back to her today?",
    "Where am I waiting for permission that I could give myself?",
    "Which conversation have I been avoiding? What's the first sentence I could say?",
    "What story about myself am I ready to stop telling?",
    "What would change if I stopped trying to be liked by everyone?",
    "Where in my career am I playing small? What would playing a little bigger look like?",
    "What is one skill I'd love to develop? What's the first step?",
    "Whose opinion holds me back the most? Is it really theirs, or my assumption of it?",
    "What mistake taught me the most? How has it shaped me for the better?",
    "Which boundary would make my life lighter?",
    "When I imagine asking for what I'm worth, what comes up for me?",
    "What does 'imposter syndrome' feel like for me? What evidence contradicts it?",
    "Who could I ask for help this week? What would I ask?",
    "What would I post on LinkedIn if I wasn't worried about being judged?",
    "Which of my 'shoulds' are actually someone else's expectations?",
    "What did I do this week that took courage, even a little?",
    "What risk is worth taking this year?",
    "If my best friend were in my situation, what would I encourage her to do?",
    "What do I need to forgive myself for?",
    "What would I do differently if I truly believed I deserved good things?",
    "Where do I hide my talents to avoid seeming 'too much'?",
    "What is one way I could be more visible in my work or community?",
    "What's the kindest thing I can do for my future self today?",
    "What am I ready to let go of: a habit, a grudge, a fear, or a belief?",
    "Who has shown me what courage looks like? What did I learn from her?",
    "Looking back on this season, where have I been braver than before?",
    # Purpose (61-90)
    "What activities make me lose track of time?",
    "What problems in the world, my community or my industry do I care about most?",
    "What do people often come to me for help with?",
    "What are my top five values? Am I living by them right now?",
    "If I could only accomplish one thing this year, what would matter most?",
    "What kind of woman do I want to be remembered as?",
    "Which parts of my current work feel meaningful? Which feel empty?",
    "What would I do with my time if money were not a concern?",
    "Who would I love to learn from? How could I connect with her?",
    "What legacy am I already building, maybe without realising it?",
    "How do I want to feel at the end of an ordinary workday?",
    "What does success mean to me, in my own words and not anyone else's?",
    "How could I share what I know with another woman this month?",
    "What would my ideal week look like, in practical detail?",
    "Which commitments no longer align with who I am becoming?",
    "What is one thing I can do this month that my future self will thank me for?",
    "What does financial peace look like for me? What's one step toward it?",
    "Which of my relationships deserves more of my time and attention?",
    "What am I uniquely placed to do because of my experiences?",
    "How do I want to grow in the next five years: personally, professionally, spiritually?",
    "What small daily habit would most support my purpose?",
    "Who is depending on me to keep going, and who am I doing this for?",
    "What would it look like to lead from my values at work this week?",
    "What does rest look like when it truly restores me?",
    "Where am I already living with purpose, even in small ways?",
    "What's one bold goal for the next ninety days?",
    "What do I want my daughters, nieces or younger women around me to learn from my life?",
    "What has this journal taught me about myself?",
    "What am I most grateful for from these ninety days?",
    "Who am I now that I wasn't ninety days ago?",
]
assert len(PROMPTS) == 90, len(PROMPTS)


def season_page(day):
    label, name, text = SEASONS[day]
    return f"""
# [{label} · Days {day}–{day + 29}]{{.num}}{name}

{text}

**What I hope this season brings:**

<div class="write l5"></div>
"""


def day_page(n, prompt):
    return f"""
# [Day {n}]{{.num}}Date: ____________________

### Morning

**Today I'm grateful for:**

<div class="write l2"></div>

**My one thing today:**

<div class="write l1"></div>

**Today's reflection:** *{prompt}*

<div class="write l9"></div>

### Evening

**One win from today:**

<div class="write l2"></div>

**What I'm releasing before I sleep:**

<div class="write l2"></div>

<p class="scale">MOOD &nbsp; 1 &nbsp; 2 &nbsp; 3 &nbsp; 4 &nbsp; 5 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ENERGY &nbsp; 1 &nbsp; 2 &nbsp; 3 &nbsp; 4 &nbsp; 5</p>
"""


def week_review(week):
    return f"""
# [Week {week} review]{{.num}}Looking back, looking ahead

**The highlight of my week:**

<div class="write l2"></div>

**What drained me, and what I'll do differently:**

<div class="write l3"></div>

**What I learned about myself:**

<div class="write l3"></div>

**My wins this week (big and small):**

<div class="write l3"></div>

**My intention for next week:**

<div class="write l2"></div>

**One thing I'll do just for me:**

<div class="write l1"></div>
"""


def checkin(day):
    q = {
        30: ["Read back through the last thirty days. What patterns do you notice in your moods, wins and worries?",
             "What surprised you about yourself this month?",
             "What do you want to carry into the season of Courage?"],
        60: ["Where have you been braver in the past thirty days?",
             "Which fear has shrunk? Which still feels big?",
             "What do you want to carry into the season of Purpose?"],
        90: ["Return to your ninety-day intention at the front of this journal. How do your three words feel now?",
             "What has changed in how you think, speak to yourself and spend your time?",
             "What will you keep doing now that this journal is complete?"],
    }[day]
    body = "\n\n".join(f"**{x}**\n\n<div class=\"write l5\"></div>" for x in q)
    return f"""
# [Day {day} check-in]{{.num}}{'Thirty' if day == 30 else 'Sixty' if day == 60 else 'Ninety'} days in

{body}
"""


BACK = """
# [You did it]{.num}Ninety days of showing up

Close this journal for a moment and notice its weight in your hands. Every page holds a few minutes you chose to spend with yourself. In a busy, demanding life, that's not a small thing.

You may not have filled every page. That's fine. What matters is that you kept coming back.

Here are a few ways to keep the practice alive:

- **Start a new ninety days.** Many women find their answers change dramatically the second time.
- **Keep just the evening win.** Even one line a day keeps your attention on progress.
- **Share a prompt.** Ask a friend, your partner or your team one of the questions in this journal over coffee.

<div class="box">

### Keep going with Think Positive Always

- *The 30-Day Mindset Reset Workbook*: a focused month to quiet the inner critic.
- *The Confidence & Self-Worth Workbook*: practical tools to own your value at work and in life.
- *The Letting Go & Moving Forward Guide*: for when something needs to end so something better can begin.

thinkpositivealways.com

</div>

<p class="closing">Your story is still being written. Keep writing it on purpose.</p>
"""


def main():
    parts = [FRONT]
    for d in range(1, 91):
        if d in SEASONS:
            parts.append(season_page(d))
        parts.append(day_page(d, PROMPTS[d - 1]))
        if d % 7 == 0:
            parts.append(week_review(d // 7))
        if d in (30, 60, 90):
            parts.append(checkin(d))
    parts.append(week_review(13))
    parts.append(BACK)
    Path(__file__).with_name("manuscript.md").write_text("\n".join(parts))


if __name__ == "__main__":
    main()
