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

## Current Milestone: v1.1 Integration & Operations

**Goal:** Complete the integration and operational work assigned to Phase 5 by the
Phase 2-4 plans.

**Target features:**
- External fallback success, failure, and transient-recovery notifications.
- Representative live-printer testing for routing, sensors, heaters, purge, fallback,
  and guarded resume.
- Runtime backup-list mutation commands.
- Printer-specific installation and integration examples.
- CI automation and release verification.

**Explicit boundary:** The four Phase 1 UAT scenarios remain separately deferred per
the user's instruction and are not milestone requirements.

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
*Last updated: 2026-06-11 after starting v1.1 milestone*
