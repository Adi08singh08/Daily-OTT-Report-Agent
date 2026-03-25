@echo off
REM =========================================================================
REM  Daily OTT Report Agent — NOTE
REM  This agent runs via Claude Code's /schedule skill, NOT via Task Scheduler.
REM  The schedule is configured using the RemoteTrigger in Claude Code.
REM
REM  To set up: open Claude Code and run:
REM    /schedule
REM  Then provide agent_prompt.md contents as the prompt and set cron:
REM    30 3 * * *   (= 9:00 AM IST = 03:30 UTC)
REM
REM  To test manually (render only, no email):
REM    python email_renderer.py data.json report_preview.html
REM
REM  To test full run with a specific date, edit data.json manually
REM  or run the agent prompt interactively in Claude Code.
REM =========================================================================
echo This agent is scheduled via Claude Code's /schedule skill.
echo See agent_prompt.md for execution instructions.
echo.
echo To test email sending:
echo   python emailer.py report.html "Test Subject" "your@email.com"
