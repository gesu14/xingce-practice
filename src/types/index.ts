export type Option = {
  key: string;
  text: string;
  image?: string;
};

export type Question = {
  id: string;
  source: string;
  sourceKey: string;
  module: string;
  subtype?: string;
  stem: string;
  options: Option[];
  answer: string;
  explanation: string;
  stemImage?: string;
  tipIds?: string[];
  highYield?: boolean;
  patternTag?: string;
  needsImage?: boolean;
};

export type Tip = {
  id: string;
  module: string;
  title: string;
  summary: string;
  points: string[];
};

export type SprintPack = {
  id: string;
  title: string;
  module: string;
  estMinutes: number;
  tipIds: string[];
  questionIds: string[];
  mustRemember: string[];
};

export type Meta = {
  rawCount: number;
  uniqueCount: number;
  beisenCount: number;
  sprintPackCount: number;
  sprintQuestionCount: number;
  modules: Record<string, number>;
  sources: Record<string, number>;
};

export type ProgressStore = {
  answered: Record<string, { correct: boolean; choice: string; at: string }>;
  wrongIds: string[];
  sprintCleared: string[];
};
