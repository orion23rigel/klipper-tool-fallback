# Klipper Tool Fallback

## Overview
Independent Klipper extension for persistent logical-to-physical tool routing, filament-state tracking, purge lifecycle management, and automatic backup-tool fallback.

## Status
v1.0 shipped: Phases 1-4 complete with 258 automated tests passing.

## Core Purpose
Ensure that tool selection and filament runout handling can fallback to a secondary tool automatically when the primary tool or sensor fails.

## Current State

The extension implements persistent routing, sensor and purge lifecycle management,
safe active-route transitions, and automatic backup fallback with fail-closed runtime
checkpoints. Hardware UAT, external notifications, and runtime backup-list management
remain deferred to the next milestone.

## Next Milestone Goals

- External notification integration.
- Representative live-printer UAT and printer-specific installation guidance.
- Runtime backup-list management and CI automation.

## Current Milestone: v1.2 Non-existent Tool Fallback Definition

**Goal:** Gracefully handle G-code calling a tool that doesn't exist on the printer by prompting the user to define a backup tool.

**Target features:**
- Detect when G-code references a tool number not defined in the printer's tool configuration.
- Prompt the user to define a backup tool for the missing tool (via Klipper command / macro / pause flow).
- Persist the user's backup-tool choice so subsequent G-code resumes without re-prompting.
- Fall back to the chosen backup tool (or a sensible default) once defined.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Move validated requirements to completed scope.
2. Record invalidated requirements and new decisions.
3. Update the current project description when implementation changes it.

**After each milestone:**
1. Review scope, core value, constraints, and deferred work.
2. Update current state and next-milestone goals.

---
*Last updated: 2026-06-27 after starting v1.2 milestone*
