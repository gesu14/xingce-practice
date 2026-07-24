export type QuizSession = {
  key: string;
  mode: string;
  packId?: string;
  questionIds: string[];
  index: number;
  updatedAt: string;
};

const KEY = 'xingce-quiz-session-v1';

export function sessionKey(mode: string, packId = ''): string {
  if (mode === 'sprint' && packId) return `sprint:${packId}`;
  if (mode === 'wrong') return 'wrong';
  return `practice:${packId || 'default'}`;
}

export function loadSession(key: string): QuizSession | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const all = JSON.parse(raw) as Record<string, QuizSession>;
    return all[key] || null;
  } catch {
    return null;
  }
}

export function saveSession(session: QuizSession) {
  try {
    const raw = localStorage.getItem(KEY);
    const all = raw ? (JSON.parse(raw) as Record<string, QuizSession>) : {};
    all[session.key] = { ...session, updatedAt: new Date().toISOString() };
    localStorage.setItem(KEY, JSON.stringify(all));
  } catch {
    // ignore quota errors
  }
}

export function clearSession(key: string) {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return;
    const all = JSON.parse(raw) as Record<string, QuizSession>;
    delete all[key];
    localStorage.setItem(KEY, JSON.stringify(all));
  } catch {
    // ignore
  }
}

export function answeredCount(questionIds: string[], answered: Record<string, unknown>) {
  return questionIds.filter((id) => answered[id]).length;
}
