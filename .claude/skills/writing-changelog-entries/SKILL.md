---
name: writing-changelog-entries
description: Use when adding or editing a bullet in CHANGELOG.md, writing release notes, or when a changelog entry has grown past one sentence
---

# Writing changelog entries

## Overview

A changelog bullet is one change, stated once, in the words a user would use
to look for it. Release notes are built from these bullets, read aloud by
screen readers, and shown on orinks.net and GitHub, so every extra sentence
is one the reader has to sit through to reach the next change.

## The entry

An entry is one sentence, in plain present tense, saying what is different
now. Direct address is welcome ("You can now..."), contractions are fine, and
the sentence must stand on its own without the section heading. A second
sentence is allowed only for a setting name or a platform limit the reader
needs ("Windows only", "Rebind it on the General tab in Settings").

Length: under 25 words. 40 is the ceiling. Count them.

Example, and this is the entire entry:

- NWS lookups now follow coordinate-precision redirects instead of falling
  back to another weather source.

## Where the rest goes

| Material | Goes to |
|---|---|
| Root cause, why it happened, what the old code did | the commit message |
| How it works, what it reads, sample sizes, thresholds | the PR body |
| Every sub-case, every affected distro or dialog | docs/user_manual.md, or its own bullet if a user would search for it on its own |
| The before-and-after story | nowhere; the sentence says what is different |
| Reassurance that something else is unchanged | nowhere |
| Developer-facing changes (CI, tests, tooling, refactors) | no bullet; `[skip changelog]` in the commit |

## Checklist before saving

- One sentence, or one plus a short limit or setting name.
- Under 25 words, 40 at most.
- Names the setting, tab, button, or key the reader will look for; never a
  file, function, or API field.
- Section is one of Added, Changed, Fixed, Improved, Removed, Deprecated,
  Security. Any other heading is dropped from release notes.
- No symbols, tables, code formatting, or em dashes: it is read aloud.

## Common mistakes

- Telling the story of the bug before the fix. Say what happens now.
- A parenthetical that repeats the sentence in more detail.
- One bullet carrying a whole feature's sub-parts. Split by what a user would
  look up, and send the rest to the manual.
- Editing an old bullet to satisfy the changelog gate. The gate needs a new
  bullet.
