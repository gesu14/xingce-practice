import type { Meta, Question, SprintPack, Tip } from '../types';

let cache: {
  questions?: Question[];
  tips?: Tip[];
  packs?: SprintPack[];
  meta?: Meta;
} = {};

async function loadJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}`);
  return res.json();
}

export async function getQuestions(): Promise<Question[]> {
  if (!cache.questions) {
    cache.questions = await loadJson<Question[]>('/data/questions.json');
  }
  return cache.questions;
}

export async function getTips(): Promise<Tip[]> {
  if (!cache.tips) {
    cache.tips = await loadJson<Tip[]>('/data/tips.json');
  }
  return cache.tips;
}

export async function getSprintPacks(): Promise<SprintPack[]> {
  if (!cache.packs) {
    cache.packs = await loadJson<SprintPack[]>('/data/sprint-packs.json');
  }
  return cache.packs;
}

export async function getMeta(): Promise<Meta> {
  if (!cache.meta) {
    cache.meta = await loadJson<Meta>('/data/meta.json');
  }
  return cache.meta;
}

export function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
