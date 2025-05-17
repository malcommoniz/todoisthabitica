# SideQuest To-Do List

## Phase 1: Core Functionality (MVP)

### 1. Project Setup
- [x] Initialize project repository
- [x] Set up development environment (Python/Flask chosen, requirements.txt created)
- [x] Choose database (PostgreSQL chosen, driver added to requirements.txt)
- [x] Define basic project structure (folders for backend, frontend, assets, etc.)

### 2. Task Management System (Core Feature 4.1)
- **Habits:**
    - [ ] API: CRUD operations for Habits
    - [ ] Backend: Logic for tracking positive/negative habit performance
    - [ ] DB: Implement `Habit` table schema
- **Dailies:**
    - [ ] API: CRUD operations for Dailies
    - [ ] Backend: Logic for repeating schedules and streak tracking
    - [ ] DB: Implement `Daily` table schema
- **To-Dos:**
    - [ ] API: CRUD operations for To-Dos
    - [ ] Backend: Logic for one-time tasks and optional due dates
    - [ ] DB: Implement `ToDo` table schema
- **Rewards:**
    - [ ] API: CRUD operations for Rewards
    - [ ] Backend: Logic for "purchasing" rewards with in-game currency
    - [ ] DB: Implement `Reward` table schema
- **General Task Features:**
    - [ ] API: Endpoint to list all tasks for a user
    - [ ] API: Endpoint to mark tasks as complete/incomplete
    - [ ] DB: Implement base `Task` table schema

### 3. Character Progression System (Core Feature 4.2 - Basic)
- **User & Character:**
    - [ ] API: User registration and authentication (User API)
    - [ ] API: CRUD for basic character data (User API)
    - [ ] DB: Implement `User` table schema
    - [ ] DB: Implement `Character` table schema
- **Initial Class:**
    - [ ] Backend: Define a single starting character class
    - [ ] DB: Implement `Class` table schema (for the initial class)
- **Level Progression (Basic):**
    - [ ] Backend: Logic for characters to gain experience through task completion
    - [ ] Backend: Logic for level ups based on experience
- **Stat Growth (Basic):**
    - [ ] Backend: Logic for Strength, Constitution, Intelligence to increase with levels
- **Skill Unlocks (Placeholder/Basic):**
    - [ ] Backend: Define 1-2 basic skills unlocked at early level milestones
    - [ ] DB: Implement `Skill` table schema
    - [ ] DB: Implement `CharacterSkill` junction table

### 4. Battle System (Core Feature 4.3 - Initial Mechanics)
- **Monster Encounters (Basic):**
    - [ ] Backend: Logic for triggering a "tutorial monster" encounter (e.g., on first login after tutorial)
    - [ ] DB: Implement `Monster` table schema (for at least one tutorial monster)
- **Combat Mechanics (Basic):**
    - [ ] Backend: Logic for task completion to determine battle outcomes (e.g., deal damage)
        - [ ] Implement Base Formula: `Damage = (Base Damage × Task Completion Rate) + Streak Bonus`
    - [ ] Backend: Logic for monster strength (static for MVP, or very simple scaling)
        - [ ] Implement basic Monster Scaling: `Monster Strength = Base Strength` (scaling can be enhanced later)
- **Victory/Defeat (Basic):**
    - [ ] Backend: Logic for defeating monsters through task completion
    - [ ] Backend: Basic consequences for not completing tasks (e.g., monster doesn't take damage, or deals minor damage to player if time passes)
- **Battle State:**
    - [ ] API: Endpoints for battle actions (Battle API - e.g., acknowledge task completion impacting battle)
    - [ ] DB: Implement `Battle` table schema
    - [ ] DB: Implement `BattleLog` table schema (basic logging)

### 5. Animation System (Core Feature 4.4 - Fundamental)
- [ ] Frontend: Placeholder for character attack animation
- [ ] Frontend: Placeholder for monster reaction animation
- [ ] Frontend: Basic visual feedback for successful/failed task completion (e.g., text update, simple effect)
- [ ] Design: Define initial 16-bit aesthetic guidelines (color palette, sprite style ideas)

### 6. Narrative Framework (Core Feature 4.5 - Foundation)
- [ ] Content: Write outline for a very simple initial tutorial narrative
- [ ] Backend: Logic to advance a simple narrative marker (e.g., "tutorial_complete")
- [ ] DB: Implement `NarrativeMarker` table schema

### 7. User Experience Flow (MVP Onboarding & Daily Loop)
- **Onboarding:**
    - [ ] UI: Account creation screen
    - [ ] UI: Initial character class selection (if more than one at start, else auto-assign)
    - [ ] UI: Basic tutorial screens/flow explaining task categories
    - [ ] UI: Interface to set up initial habits, dailies, to-dos
    - [ ] UI: Trigger first "tutorial monster" encounter
- **Daily Gameplay Loop (Basic UI):**
    - [ ] UI: View pending tasks
    - [ ] UI: Log task completion
    - [ ] UI: Basic display of character engaging in "battle" (can be text-based with placeholders for animation)
    - [ ] UI: Display monster status (health)
    - [ ] UI: Display character XP, gold gain on victory
    - [ ] UI: Mechanism for new monster to appear (simple for MVP)

### 8. Technical Specifications (MVP Focus)
- **Platform Architecture (Initial):**
    - [ ] Decide on primary development target for MVP (e.g., Web, or one mobile platform to start)
    - [ ] Set up backend RESTful API structure
- **API Structure (Initial):**
    - [ ] Define and implement basic User API endpoints
    - [ ] Define and implement basic Task API endpoints
    - [ ] Define and implement basic Battle API endpoints (minimal for MVP)

### 9. Documentation
- [ ] Update `SideQuest.md` with any schema changes or major decisions
- [ ] Keep `todo.md` updated

---

## Phase 2: Enhanced Battle Experience (Future)
- (Tasks to be detailed later)

## Phase 3: Social Integration (Future)
- (Tasks to be detailed later)

## Phase 4: Extended Integration (Future)
- (Tasks to be detailed later) 