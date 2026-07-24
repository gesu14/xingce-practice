import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getMeta, getQuestions, getSprintPacks } from '../lib/data';
import { loadProgress } from '../lib/progress';
import type { Meta, ProgressStore } from '../types';

export function HomePage() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [progress, setProgress] = useState<ProgressStore>(loadProgress());
  const [modules, setModules] = useState<[string, number][]>([]);

  useEffect(() => {
    Promise.all([getMeta(), getQuestions(), getSprintPacks()])
      .then(([m, qs]) => {
        setMeta(m);
        const counts = new Map<string, number>();
        qs.forEach((q) => counts.set(q.module, (counts.get(q.module) || 0) + 1));
        setModules([...counts.entries()].sort((a, b) => b[1] - a[1]));
      })
      .catch((err) => {
        console.error('Failed to load question bank', err);
      });
    setProgress(loadProgress());
  }, []);

  const answered = Object.keys(progress.answered).length;
  const correct = Object.values(progress.answered).filter((a) => a.correct).length;

  return (
    <div className="page">
      <header className="hero">
        <p className="brand">行测刷题</p>
        <h1>按模块练，用解析学，冲刺靠北森小库</h1>
        <p className="lede">
          本地题库约 {meta?.uniqueCount ?? '—'} 道；抱佛脚冲刺包 {meta?.sprintPackCount ?? '—'} 个（北森{' '}
          {meta?.beisenCount ?? '—'} 道）。
        </p>
      </header>

      <section className="grid cards-entry">
        <Link className="entry sprint" to="/sprint">
          <span className="entry-kicker">短期冲刺</span>
          <strong>临时抱佛脚</strong>
          <span>北森精选 · 要点 → 刷题 → 通关</span>
        </Link>
        <Link className="entry" to="/practice">
          <span className="entry-kicker">系统练习</span>
          <strong>按模块刷题</strong>
          <span>言语 / 数量 / 图形 / 资料 / 数字推理</span>
        </Link>
        <Link className="entry" to="/wrong">
          <span className="entry-kicker">查漏补缺</span>
          <strong>错题本</strong>
          <span>{progress.wrongIds.length} 道待重练</span>
        </Link>
        <Link className="entry" to="/tips">
          <span className="entry-kicker">方法论</span>
          <strong>答题技巧库</strong>
          <span>按题型速查口诀与判题点</span>
        </Link>
      </section>

      <section className="panel">
        <h2>学习进度</h2>
        <div className="stats">
          <div>
            <em>{answered}</em>
            <span>已作答</span>
          </div>
          <div>
            <em>{answered ? Math.round((correct / answered) * 100) : 0}%</em>
            <span>正确率</span>
          </div>
          <div>
            <em>{progress.sprintCleared.length}</em>
            <span>冲刺通关</span>
          </div>
          <div>
            <em>{progress.wrongIds.length}</em>
            <span>错题</span>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>题库模块</h2>
        <div className="module-list">
          {modules.map(([name, count]) => (
            <Link key={name} to={`/practice?module=${encodeURIComponent(name)}`} className="module-item">
              <span>{name}</span>
              <strong>{count}</strong>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
