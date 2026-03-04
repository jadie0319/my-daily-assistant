# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## IMPORTANT: Directory Access Rules

**READ THIS FIRST**: See `DIRECTORY_RULES.md` for absolute rules on which directories can be modified by Claude Code vs Codex. These rules MUST be followed at all times.

## Project Overview

A personal daily life assistant. Scripts handle tasks like summarizing URLs, extracting YouTube transcripts, and other daily utilities. Outputs (summaries, notes, etc.) are saved to an Obsidian vault.

## Configuration

All environment settings are stored in `env.config` at the project root. Read this file at the start of any task that interacts with the filesystem or external services.

- **`OBSIDIAN_VAULT`**: Path to the Obsidian vault where all output notes (URL summaries, YouTube summaries, etc.) are written. See `env.config`.

## Running Scripts

```bash
# Run the YouTube transcript extractor
python3 get_youtube_transcript.py <youtube_url>

# Example
python3 get_youtube_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Dependencies

Install required packages:
```bash
pip install youtube-transcript-api
```

The project uses `youtube-transcript-api` >= 1.2.4 (API uses instance-based `YouTubeTranscriptApi()` with `.fetch()` and `.to_raw_data()`).

## Architecture

- **`get_youtube_transcript.py`**: CLI script that extracts YouTube video transcripts. Prefers Korean (`ko`) subtitles, falls back to English (`en`). Accepts full YouTube URLs or shortened `youtu.be` links and prints the transcript as plain text to stdout.
