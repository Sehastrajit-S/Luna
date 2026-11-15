export interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
  sentiment_score?: number
}

export interface Conversation {
  id: number
  title: string | null
  summary: string | null
  started_at: string
  ended_at: string | null
  message_count: number
}

export interface Fact {
  id: number
  category: string
  content: string
  confidence: number
  created_at: string
  updated_at: string
  memory_type: 'short' | 'long' | 'persistent'
  expires_at: string | null
}

export interface Task {
  id: number
  title: string
  description: string | null
  due_date: string | null
  completed: boolean
  priority: 'low' | 'medium' | 'high'
  created_at: string
}

export interface CalendarEvent {
  id: number
  title: string
  description: string | null
  start_datetime: string
  end_datetime: string | null
  recurring: string | null
  location: string | null
}

export interface PersonalityState {
  verbosity: number
  formality: number
  humor: number
  depth: number
  emotional_support: number
  question_frequency: number
  current_mood: string
  mood_intensity: number
  energy_level: number
  total_interactions: number
}

export interface Activity {
  id: number
  title: string
  description: string | null
  status: 'in_progress' | 'done' | 'paused' | 'abandoned'
  category: string | null
  started_at: string | null
  last_updated: string | null
  completed_at: string | null
  progress_notes: { note: string; ts: string }[]
}

export type View = 'focus' | 'chat' |'memory' | 'calendar' | 'activities' | 'agent' | 'train' | 'sleep' | 'extract' | 'settings'
export type MoodType = 'happy' | 'playful' | 'thoughtful' | 'excited' | 'concerned' | 'warm' | 'neutral' | 'curious' | 'melancholic'
