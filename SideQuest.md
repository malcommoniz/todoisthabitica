# SideQuest Project Documentation

## 1. Overview

SideQuest is a productivity application that transforms daily task management into an engaging 16-bit battle RPG. Users track habits, daily tasks, and to-dos while engaging in animated combat sequences against monsters that grow stronger when tasks are neglected.

## 2. Database Schema

The initial database schema will include the following core data models:

### 2.1 User
Stores information about users and their authentication details.
- `user_id` (Primary Key)
- `username` (Unique)
- `email` (Unique)
- `password_hash`
- `created_at`
- `updated_at`

### 2.2 Character
Stores data related to the user's in-game character.
- `character_id` (Primary Key)
- `user_id` (Foreign Key to User)
- `name`
- `class_id` (Foreign Key to Class)
- `level` (Default: 1)
- `experience_points` (Default: 0)
- `stat_strength`
- `stat_constitution`
- `stat_intelligence`
- `gold` (Default: 0)
- `created_at`
- `updated_at`

### 2.3 Class
Stores information about available character classes.
- `class_id` (Primary Key)
- `name` (e.g., Warrior, Mage, Rogue - initially one, then branching)
- `description`
- `base_strength`
- `base_constitution`
- `base_intelligence`

### 2.4 Skill
Stores information about skills characters can unlock.
- `skill_id` (Primary Key)
- `name`
- `description`
- `required_level`
- `class_id` (Foreign Key to Class, optional if skill is class-specific)
- `effect_description` (e.g., damage type, buff, debuff)

### 2.5 CharacterSkill
Junction table for characters and their unlocked skills (Many-to-Many).
- `character_id` (Foreign Key to Character)
- `skill_id` (Foreign Key to Skill)
- `unlocked_at`
- Primary Key (`character_id`, `skill_id`)

### 2.6 Task
Base table for all task types.
- `task_id` (Primary Key)
- `user_id` (Foreign Key to User)
- `title`
- `notes` (Optional)
- `type` (Enum: HABIT, DAILY, TODO)
- `created_at`
- `updated_at`
- `difficulty` (Optional: e.g., Easy, Medium, Hard - could influence XP/gold)
- `is_completed` (Boolean, Default: False)
- `completed_at` (Nullable)

### 2.7 Habit
Specific details for habit-type tasks.
- `task_id` (Primary Key, Foreign Key to Task)
- `is_positive` (Boolean: True for good habits, False for bad habits to break)
- `value` (Numeric, tracking strength of habit, e.g. +1 for good, -1 for bad)
- `last_performed_at` (Nullable)

### 2.8 Daily
Specific details for daily-type tasks.
- `task_id` (Primary Key, Foreign Key to Task)
- `repeat_schedule` (e.g., JSON or specific fields for days of week, specific date)
- `streak_count` (Default: 0)
- `due_date` (Date, resets daily)
- `last_completed_date` (Nullable)

### 2.9 ToDo
Specific details for to-do-type tasks.
- `task_id` (Primary Key, Foreign Key to Task)
- `due_date` (Optional, DateTime)

### 2.10 Reward
Custom rewards users can define and "purchase".
- `reward_id` (Primary Key)
- `user_id` (Foreign Key to User)
- `title`
- `description`
- `cost` (In-game currency)
- `is_purchased` (Boolean, Default: False)
- `purchased_at` (Nullable)
- `created_at`

### 2.11 Monster
Stores data for different monster types.
- `monster_id` (Primary Key)
- `name`
- `description`
- `base_health`
- `base_attack`
- `base_defense`
- `sprite_url` (Path to animation/image assets)
- `level_range_min` (Minimum character level to encounter)
- `level_range_max` (Maximum character level to encounter)

### 2.12 Battle
Stores information about current and past battle encounters.
- `battle_id` (Primary Key)
- `user_id` (Foreign Key to User)
- `monster_id` (Foreign Key to Monster)
- `monster_current_health`
- `monster_max_health` (at time of encounter, considering scaling)
- `monster_current_attack` (at time of encounter, considering scaling)
- `status` (Enum: ONGOING, VICTORY, DEFEAT)
- `started_at`
- `ended_at` (Nullable)
- `last_action_at`

### 2.13 BattleLog
Logs actions and events within a battle.
- `log_id` (Primary Key)
- `battle_id` (Foreign Key to Battle)
- `timestamp`
- `action_description` (e.g., "User completed 'Morning Jog', dealt 25 damage.", "Monster attacked, user took 10 damage.")
- `actor` (Enum: USER, MONSTER)
- `damage_dealt` (Nullable)
- `damage_taken` (Nullable)
- `task_id_linked` (Nullable, Foreign Key to Task, if action is task-related)

### 2.14 NarrativeMarker
Tracks user's progression through the story.
- `marker_id` (Primary Key)
- `user_id` (Foreign Key to User)
- `story_event_key` (Unique identifier for a narrative point, e.g., "INTRO_COMPLETED", "CHAPTER1_BOSS_DEFEATED")
- `achieved_at`
- `details` (JSON or Text for any specific data related to this marker)

---

This schema will evolve as we develop the application. 