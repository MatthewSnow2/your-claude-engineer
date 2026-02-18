Initialize a new project in: {project_dir}

This is the FIRST session. The project has not been set up yet.

## INITIALIZATION SEQUENCE

### Step 1: Set Up Linear Project
Delegate to `linear` agent:
"Read app_spec.txt to understand what we're building. Then:
1. Create a Linear project with appropriate name
2. Create issues for ALL features from app_spec.txt (with test steps in description)
3. Create a META issue '[META] Project Progress Tracker' for session handoffs
4. Add initial comment to META issue with project summary and session 1 status
5. Save state to .linear_project.json
6. Return: project_id, total_issues created, meta_issue_id"

### Step 2: Initialize Git
Delegate to `github` agent:
"Initialize git repository:
1. FIRST: Check `echo $GITHUB_REPO` env var
2. Create README.md with project overview
3. Create init.sh script to start dev server
4. Create .gitignore
5. git init and initial commit with these files + .linear_project.json
6. If GITHUB_REPO is set: add remote and push
7. Report whether remote was configured"

### Step 3: Start First Feature (if time permits)
Get the highest-priority issue details from linear agent, then:

**3a. Implement:**
Delegate to `coding` agent:
"Implement this Linear issue:
- ID: [from linear agent]
- Title: [from linear agent]
- Description: [from linear agent]
- Test Steps: [from linear agent]

Requirements:
1. Implement the feature
2. Test via Playwright (mandatory)
3. Take screenshot evidence
4. Report: files_changed, screenshot_path, test_results"

**3b. Code Review:**
Delegate to `code_review` agent:
"Review these changed files: [file list from coding agent]
Report: review_result, issues, new_learnings"

⚠️ If FAIL: Ask coding agent to fix, then re-review.

**3c. QA Regression Test:**
Delegate to `qa` agent:
"Test the new feature [name]. Take screenshots. Report PASS/FAIL."

⚠️ If FAIL: Ask coding agent to fix, then re-test.

### Step 4: Commit Progress (use parallel execution)
If coding was done, delegate in SAME turn:
- `github` agent: Commit and push changes
- `linear` agent: Mark issue done + add session summary to META issue
- `slack` agent: Send progress notification

## OUTPUT FILES TO CREATE
- .linear_project.json (project state)
- init.sh (dev server startup)
- README.md (project overview)

Remember: You are the orchestrator. Delegate tasks to specialized agents, don't do the work yourself.
