"""Advisor service — the close-timing debate, extracted as its own deployable.

The one part of the AI layer with a real trigger to run separately: the Analyst/Critic/
Decider debate is slow and LLM-bound, so it scales differently from the real-time engine.
The cut is clean because it's already a pure function of a *deterministic* ``Situation``
(computed in the monolith) — this service only reasons over numbers it's handed, never
computes one.
"""
