"""Seed script to populate realistic non-personal demo journal entries."""

from pathlib import Path

ENTRIES = {
    "2024-03-15.md": """---
title: Productivity and Presence
---
I find myself constantly optimizing every hour of the day. Every task is tracked, every pomodoro logged. But by evening, I often wonder if I actually made meaningful progress on what matters, or if I was merely reacting to tasks on autopilot.

I want to learn to discern between shallow busywork and high-leverage creative thinking. Pushing myself harder hasn't unlocked better ideas—just more exhaustion.
""",
    "2024-11-20.md": """---
title: Recognizing Burnout
---
The last few weeks have been a battle against persistent mental fog. I pushed through three back-to-back project launches, ignoring the physical cues of fatigue. The result wasn't heroism; it was irritability and cynicism toward work I normally love.

Taking this weekend to completely disconnect. No screens, no code commits. I need to establish firmer boundaries around evenings and weekends before my passion for engineering erodes entirely.
""",
    "2025-06-10.md": """---
title: Restructuring for Deep Work
---
Seven months after setting strict boundaries, the difference is night and day. I've blocked off 9:00 AM to 12:00 PM every weekday exclusively for uninterrupted deep focus—no Slack, no email, no meetings.

In these quiet morning blocks, the cognitive momentum is immense. I solve architecture challenges in two hours that used to take days of fragmented context-switching. Deep work isn't just a productivity tactic; it is protective of my peace.
""",
    "2026-04-12.md": """---
title: Sustainable Momentum
---
Reflecting on the past two years of journaling. In early 2024, my relationship with output was driven by fear of falling behind. Now, momentum feels calm and rhythmic. I ship code consistently, but without the chaotic adrenaline spikes.

True craftsmanship isn't about heroic 80-hour sprints. It's about showing up with a clear mind, building thoughtfully, and knowing when to close the laptop and live the rest of life.
""",
}

def seed():
    entries_dir = Path("entries")
    entries_dir.mkdir(parents=True, exist_ok=True)
    
    for filename, content in ENTRIES.items():
        file_path = entries_dir / filename
        file_path.write_text(content.strip() + "\n", encoding="utf-8")
        print(f"Created {file_path}")

if __name__ == "__main__":
    seed()
