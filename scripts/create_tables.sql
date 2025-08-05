-- Database schema for Bible Q&A application

-- Create questions table
CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create answers table
CREATE TABLE IF NOT EXISTS answers (
    id SERIAL PRIMARY KEY,
    question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
    answer TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_questions_user_id ON questions(user_id);
CREATE INDEX IF NOT EXISTS idx_questions_created_at ON questions(created_at);
CREATE INDEX IF NOT EXISTS idx_answers_question_id ON answers(question_id);
