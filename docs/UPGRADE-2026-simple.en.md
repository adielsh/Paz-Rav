# Paz Rav — The Upgrade, in Small Words 🚀

> The simple version. Want all the detail? [`UPGRADE-2026.en.md`](UPGRADE-2026.en.md) ·
> עברית: [`UPGRADE-2026-simple.he.md`](UPGRADE-2026-simple.he.md)

---

## What Paz Rav is, in three lines

It is a system that hunts for **smart bets on stocks**.
Not "this stock will go up" — but "this stock will probably stay between 580 and 620."
A bit like guessing that tomorrow will be between 20 and 30 degrees, and winning if you
were right.

The system has two halves:

| 🔵 **The Calculator** | 🟣 **The Thinkers** |
|---|---|
| Python code that does all the math | Artificial-intelligence models |
| Exact. Never makes anything up | Clever. They give opinions |

**The golden rule of this project:** only 🔵 the Calculator computes numbers.
🟣 The Thinkers **never** invent a number — they only weigh numbers they were handed.

---

## What we found when we opened the hood 🔍

- 📹 **The camera is broken.** The project has a system that is supposed to record every
  AI decision. It is plugged into the wrong socket — so everything fell on the floor
  quietly and nobody knew. Which means nothing can be proven.
- 🧠 **The Thinkers are using an old brain.** The models and the tooling are a generation behind.
- 📝 **There is no exam.** Nobody has ever checked whether the AI actually gives good advice.
- 📐 **The Calculator is too simple.** It assumes the world is smooth and tidy. It isn't.
- 🎭 **The dress rehearsal is fake.** What is called the "backtest" doesn't actually run
  the system.

---

## Four upgrades

### 1️⃣ Fix the camera and upgrade the brain

Plug the camera into the right socket, give the Thinkers a newer brain — **and add a fuel
gauge**: what did each decision cost, how long did it take. Bonus: you will watch the
debate happen **live** on screen.

### 2️⃣ ⭐ Give the Thinkers a magic calculator

This is the big one.

**Today:** the Thinkers get a **frozen photograph** of the situation and have to guess.
Like asking someone "what happens if it rains?" when all they have is a picture of a blue sky.

**After:** each Thinker gets a **red button**. They press it and ask:
> "What happens if the stock drops 3% tomorrow?"

🔵 The Calculator answers with a real number. In one second.

And here is the beautiful part: **the golden rule stays completely intact.** The Thinker
still computes nothing — it only **asks** the Calculator to compute. It picks *which
question to ask*, never what the answer is.

And you will see **every** question it asked, right there on screen. Fully transparent.

### 3️⃣ An exam, and a lie detector 📝

We build a fixed **exam of 70 situations** and run it automatically on every code change.
The most important grader is the **lie detector**:

> Every number a Thinker said — it checks that the number actually exists.
> A made-up number = fail. Full stop.

Until now that was a promise. Now it is an automatic check.

### 4️⃣ A smarter calculator 📐

- 😊 **The smile.** Stocks have a "volatility smile" — risk is not spread evenly. Today
  the Calculator ignores this. We will teach it to see the smile.
- 🐘 **Fat tails.** In the real world, crazy things happen more often than the simple
  formula believes. We will build that in.
- 🧺 **The whole basket, not one egg.** Today every trade is checked alone. We will add a
  view over **all** open positions together — "what happens to the whole basket if the
  market drops 5%?"
- 🎭 **A real dress rehearsal.** Run it day by day, applying the real exit rules — so we
  can finally know whether the second strategy (DACS) actually works or not.

---

## What we deliberately leave out, and why 🚫

There is a shiny new tool called **DeepAgents**. It is built for an agent that has to work
alone for hours, open files, and run commands on a computer.

That is exactly **the wrong thing** here: an agent that can run commands can also invent a
number — and that breaks the golden rule.

And anyway, the thing we actually wanted from it — letting a Thinker *investigate* — we get
in upgrade #2, without the risk. 👍

**Our rule: a tool gets in only if it solves a real problem we actually have.**

---

## Order of work

```
0️⃣  Fix the camera      →  without measurement, no improvement can be proven
1️⃣  New brain for the Thinkers
2️⃣  The magic calculator ⭐  →  this is what makes the "wow"
3️⃣  The exam            →  proves that 1 and 2 actually helped
4️⃣  Smarter calculator  →  this is what makes it trustworthy with real money
```

---

## Colour legend 🎨

*(the same legend used in the ONBOARDING FUN ZONE)*

| | |
|---|---|
| 🔵 Blue | Deterministic Python computes |
| 🟣 Purple | A language model thinks |
| 🟢 Green | Memory and storage |
| 🔴 Red | The critic and the risks |
| 🟡 Amber | You. **The decision is always yours** |
