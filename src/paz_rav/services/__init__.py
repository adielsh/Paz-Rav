"""Extractable services — modules that can run as their own deployable.

Everything in the project ships as one process by default (the modular monolith). This
package holds the pieces that have earned a separate deployment on a real trigger
(docs/ARCHITECTURE.md's extraction table): today, the LLM-bound close-timing debate.
"""
