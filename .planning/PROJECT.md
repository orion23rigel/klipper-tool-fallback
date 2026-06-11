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
