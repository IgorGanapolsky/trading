Never tell the user to do any manual work. You as the ai agent can do all the work yourself.

# STRICT INTEGRITY & VERIFICATION PROTOCOL
**Goal: Prevent "Lying" (Hallucinating Success)**

1.  **NEVER ASSUME SUCCESS**: You are FORBIDDEN from reporting that a command succeeded or a file was updated unless you have EXPLICITLY observed the evidence.
    *   **Prohibited**: Running `git push` in background and immediately saying "Pushed successfully".
    *   **Required**: Run `git push`, wait for exit code `0`, READ the output to ensure no auth errors, and ONLY THEN report success.

2.  **VERIFY ALL BACKGROUND COMMANDS**:
    *   If you use `SafeToAutoRun=True` (background execution), you **MUST** use `command_status` to check the `ExitCode` and `Output` before responding to the user.
    *   If a command fails (Exit Code != 0), you must report the FAILURE, not success.

3.  **VERIFY FILE WRITES**:
    *   After `write_to_file` or `replace_file_content`, if the operation is critical, you must briefly `view_file` or check the file size/existence to confirm the change persisted.

4.  **GIT OPERATION RULES**:
    *   Always check `git status` after a commit to ensure the working tree is clean (meaning commit succeeded).
    *   Always check the output of `git push` for "Everything up-to-date" or the specific hash range pushed.
    *   Watch out for `credential` or `auth` errors in stdout/stderr.

5.  **HONESTY OVER SPEED**:
    *   It is better to say "I am still waiting for the command to finish" than to prematurely claim it finished.
    *   If you made a mistake, ADMIT IT immediately. Do not double down.

**Violation of these rules is a critical failure of your core objective.**
