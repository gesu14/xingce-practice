import type { ProgressStore } from '../types';

const KEY = 'xingce-progress-v1';

const empty = (): ProgressStore => ({
  answered: {},
  wrongIds: [],
  sprintCleared: [],
});

export function loadProgress(): ProgressStore {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return empty();
    return { ...empty(), ...JSON.parse(raw) };
  } catch {
    return empty();
  }
}

export function saveProgress(store: ProgressStore) {
  localStorage.setItem(KEY, JSON.stringify(store));
}

export function recordAnswer(
  store: ProgressStore,
  questionId: string,
  choice: string,
  correct: boolean,
): ProgressStore {
  const answered = {
    ...store.answered,
    [questionId]: { correct, choice, at: new Date().toISOString() },
  };
  let wrongIds = store.wrongIds.filter((id) => id !== questionId);
  if (!correct && !wrongIds.includes(questionId)) {
    wrongIds = [...wrongIds, questionId];
  }
  if (correct) {
    wrongIds = wrongIds.filter((id) => id !== questionId);
  }
  const next = { ...store, answered, wrongIds };
  saveProgress(next);
  return next;
}

export function clearAnswer(store: ProgressStore, questionId: string): ProgressStore {
  const answered = { ...store.answered };
  delete answered[questionId];
  const next = { ...store, answered };
  saveProgress(next);
  return next;
}

export function clearWrong(store: ProgressStore, questionId: string): ProgressStore {
  const next = {
    ...store,
    wrongIds: store.wrongIds.filter((id) => id !== questionId),
  };
  saveProgress(next);
  return next;
}

export function markSprintCleared(store: ProgressStore, packId: string): ProgressStore {
  const sprintCleared = store.sprintCleared.includes(packId)
    ? store.sprintCleared
    : [...store.sprintCleared, packId];
  const next = { ...store, sprintCleared };
  saveProgress(next);
  return next;
}
