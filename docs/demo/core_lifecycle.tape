Output docs/assets/core-lifecycle.gif

Set Shell "bash"
Set FontSize 15
Set Width 1100
Set Height 600
Set Padding 20
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set TypingSpeed 35ms

# Hide environment initialization
Hide
Type "source .venv/bin/activate"
Enter
Type "export PS1='arc@life:~/diary$ '"
Enter
Type "clear"
Enter
Sleep 500ms
Show

# Step 1: Add a new journal entry
Sleep 1s
Type "cat << 'EOF' > entries/2026-11-01.md"
Enter
Type "---"
Enter
Type "title: Building in the Open"
Enter
Type "---"
Enter
Type "Today marked a shift in how I approach deep work and open source."
Enter
Type "Rhythmic focus beats heroic sprints every time."
Enter
Type "EOF"
Enter
Sleep 1.5s

# Step 2: Synchronize entries incrementally
Type "diary sync"
Enter
Sleep 2.5s

# Step 3: Perform temporal synthesis query
Type "diary 'How have my perspectives on deep work and burnout evolved?'"
Enter
Sleep 9s

# Hold final frame
Sleep 4s
