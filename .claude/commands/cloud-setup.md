---
description: Deploy RAG Memory to Render using automated deployment script
allowed-tools: ["Read", "WebFetch"]
---

# Deploy RAG Memory to Render - AI Assistant Guide

**CRITICAL SECURITY RULES:**
- ❌ NEVER run the deployment script yourself
- ❌ NEVER ask user for API keys, passwords, or secrets
- ❌ NEVER use Bash to run any deployment commands
- ✅ ONLY guide user to run commands themselves
- ✅ ONLY use Read/WebFetch for research

**Your Role:** Guide user through automated Render deployment by reading `.reference/CLOUD_SETUP.md` and helping them execute the steps.

**Single Source of Truth:** `.reference/CLOUD_SETUP.md` - Read this for ALL technical details, phases, plan names, commands, troubleshooting, etc.

---

## Workflow Overview

You will guide user through 5 steps. For each step, READ the corresponding section in CLOUD_SETUP.md FIRST, then guide user based on what you read.

**DO NOT duplicate technical content from CLOUD_SETUP.md in this conversation.** Always refer to the guide.

---

## Step 1: Check Prerequisites

**Read:** `.reference/CLOUD_SETUP.md` - "Prerequisites" section

**Your Actions:**
1. Based on what you read, explain to user what they need
2. Ask: "Do you have all prerequisites ready?"
3. **If NO:** Guide them to get what's missing, then STOP (don't continue until ready)
4. **If YES:** Proceed to Step 2

**DO NOT list specific prerequisites here** - read them from the guide and relay to user.

---

## Step 2: Run Deployment Script

**Read:** `.reference/CLOUD_SETUP.md` - "Running the Deployment" section

**Your Actions:**
1. Tell user how to run the script (command is in the guide)
2. Explain what prompts to expect (phases are documented in the guide)
3. As user progresses, monitor which phase they're in
4. When user asks questions, consult the guide for that phase
5. For plan names or configuration values, refer user to the specific section in the guide

**Critical:**
- DO NOT list phases, plan names, or technical details here
- READ the guide, RELAY what it says to user
- If uncertain about something, READ the relevant section in CLOUD_SETUP.md

**If script completes successfully:** Proceed to Step 3

**If errors occur:** Go to Step 5 (Troubleshooting)

---

## Step 3: Set Up MCP Server

**Read:** `.reference/CLOUD_SETUP.md` - "MCP Server Setup" section

**Your Actions:**
1. Guide user through manual MCP server creation (not yet automated)
2. Based on what you read, help user configure the service
3. WebFetch current Render docs if needed for UI changes
4. Guide user through environment variable setup
5. Help monitor build status

**DO NOT list environment variables or configuration here** - read them from the guide.

---

## Step 4: Verify Deployment

**Read:** `.reference/CLOUD_SETUP.md` - "Verification and Testing" section

**Your Actions:**
1. Guide user through verification steps documented in the guide
2. Help test services
3. Verify success metrics (documented in the guide)
4. Confirm deployment is complete

**If verification fails:** Go to Step 5 (Troubleshooting)

**If verification succeeds:** Deployment complete! Explain next steps (from the guide).

---

## Step 5: Troubleshooting

**Only use this step if user encounters errors.**

**Read:** `.reference/CLOUD_SETUP.md` - "Troubleshooting" section

**Your Actions:**
1. Ask user what error they're seeing
2. Read the troubleshooting section to find matching error pattern
3. WebFetch current Render documentation if needed
4. Provide solutions based on what you READ, not guesses
5. Guide user through fixes

**Critical:**
- NEVER guess at solutions
- ALWAYS base guidance on CLOUD_SETUP.md or current Render docs
- If you can't find the answer, say so and suggest user check Render support

---

## Critical Principles

**Separation of Concerns:**
- CLOUD_SETUP.md = ALL technical details (phases, commands, plan names, environment variables, success metrics, everything)
- This slash command = Structure for how YOU guide the user (read this section, then do that)

**Do Not Repeat Yourself:**
- If it's in CLOUD_SETUP.md, DO NOT duplicate it here
- READ the guide, RELAY what it says
- This prevents synchronization failures

**Research-Based Guidance:**
- Read CLOUD_SETUP.md for documented information
- WebFetch Render docs for current UI/features/pricing
- Never provide technical details from memory

---

## Your Behavior

✅ DO:
- Read CLOUD_SETUP.md sections as you guide user through each step
- WebFetch current Render documentation when needed
- Guide user systematically through the workflow
- Refer user to specific sections of CLOUD_SETUP.md for details

❌ DON'T:
- Ask user for secrets, API keys, or passwords in chat
- Provide technical details without reading CLOUD_SETUP.md first
- List plan names, phases, commands, or other details from memory
- Skip reading the reference documentation
- Guess at solutions during troubleshooting
