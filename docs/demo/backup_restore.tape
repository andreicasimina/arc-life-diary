Output docs/assets/backup-restore.gif

Set Shell "bash"
Set FontSize 15
Set Width 1100
Set Height 600
Set Padding 20
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set TypingSpeed 40ms

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

# Step 1: List current journal entries
Sleep 1s
Type "ls -1 entries/"
Enter
Sleep 2s

# Step 2: Encrypted backup to Google Drive
Type "diary backup"
Enter
Sleep 1.5s
Type "super-secret-vault-pass"
Enter
Sleep 1.5s
Type "super-secret-vault-pass"
Enter
Sleep 8s

# Step 3: Simulate catastrophic local data loss
Type "rm entries/*.md"
Enter
Sleep 1.5s
Type "ls -1 entries/"
Enter
Sleep 2.5s

# Step 4: Restore from Google Drive backup
Type "diary restore --latest"
Enter
Sleep 4s
Type "super-secret-vault-pass"
Enter
Sleep 8s

# Step 5: Verify restored entries
Type "ls -1 entries/"
Enter
Sleep 3.5s

# Hold final frame
Sleep 4s
