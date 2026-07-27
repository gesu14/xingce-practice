import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { getQuestions, shuffle } from '../lib/data';
import { loadProgress } from '../lib/progress';
import { clearSession, loadSession, sessionKey } from '../lib/session';
import type { ProgressStore, Question } from '../types';

const SOURCE_LABELS: Record<string, string> = {
  pdd: '拼多多26年真题',
};

type PickMode = 'unseen' | 'order' | 'random';

function pickQuestions(
  pool: Question[],
  count: number,
  mode: PickMode,
  answered: ProgressStore['answered'],
): Question[] {
  if (!pool.length || count <= 0) return [];
  if (mode === 'order') {
    return [...pool].sort((a, b) => a.id.localeCompare(b.id, 'en')).slice(0, count);
  }
  if (mode === 'random') {
    return shuffle(pool).slice(0, count);
  }
  // 优先未做：先从未答过的里抽，不够再从已做过的里补
  const unseen = shuffle(pool.filter((q) => !answered[q.id]));
  if (unseen.length >= count) return unseen.slice(0, count);
  const seen = shuffle(pool.filter((q) => answered[q.id]));
  return [...unseen, ...seen].slice(0, count);
}

export function PracticePage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [progress, setProgress] = useState<ProgressStore>(loadProgress());
  const source = params.get('source') || '';
  const initialModule = params.get('module') || '全部';
  const [module, setModule] = useState(initialModule);
  const [count, setCount] = useState(20);
  const [pickMode, setPickMode] = useState<PickMode>('unseen');
  const [onlyText, setOnlyText] = useState(false);
  const [onlyImaged, setOnlyImaged] = useState(false);
  const practiceKey = sessionKey('practice', source || 'default');
  const existing = loadSession(practiceKey);
  const sourceLabel = SOURCE_LABELS[source] || '';

  useEffect(() => {
    getQuestions().then(setQuestions);
    setProgress(loadProgress());
  }, []);

  useEffect(() => {
    setModule(initialModule);
  }, [initialModule]);

  const pool = useMemo(() => {
    if (!source) return questions;
    return questions.filter((q) => q.sourceKey === source);
  }, [questions, source]);

  const moduleStats = useMemo(() => {
    const map = new Map<string, { total: number; done: number; correct: number }>();
    for (const q of pool) {
      const cur = map.get(q.module) || { total: 0, done: 0, correct: 0 };
      cur.total += 1;
      const ans = progress.answered[q.id];
      if (ans) {
        cur.done += 1;
        if (ans.correct) cur.correct += 1;
      }
      map.set(q.module, cur);
    }
    return [...map.entries()]
      .map(([name, s]) => ({ name, ...s }))
      .sort((a, b) => b.total - a.total);
  }, [pool, progress]);

  const allStats = useMemo(() => {
    const total = pool.length;
    let done = 0;
    let correct = 0;
    for (const q of pool) {
      const ans = progress.answered[q.id];
      if (ans) {
        done += 1;
        if (ans.correct) correct += 1;
      }
    }
    return { total, done, correct };
  }, [pool, progress]);

  const modules = useMemo(() => ['全部', ...moduleStats.map((m) => m.name)], [moduleStats]);

  const filtered = useMemo(() => {
    return pool.filter((q) => {
      if (module !== '全部' && q.module !== module) return false;
      if (onlyText && (q.needsImage || q.stemImage)) return false;
      if (onlyImaged && !q.stemImage) return false;
      return true;
    });
  }, [pool, module, onlyText, onlyImaged]);

  const filteredUnseen = useMemo(
    () => filtered.filter((q) => !progress.answered[q.id]).length,
    [filtered, progress.answered],
  );

  const selectedStats = useMemo(() => {
    if (module === '全部') return allStats;
    return moduleStats.find((m) => m.name === module) || { total: 0, done: 0, correct: 0 };
  }, [module, allStats, moduleStats]);

  function start(fresh = true) {
    if (fresh) {
      clearSession(practiceKey);
      const picked = pickQuestions(filtered, count, pickMode, progress.answered);
      sessionStorage.setItem('xingce-session', JSON.stringify(picked.map((q) => q.id)));
    } else if (existing?.questionIds?.length) {
      sessionStorage.setItem('xingce-session', JSON.stringify(existing.questionIds));
    }
    navigate(source ? `/quiz?mode=practice&source=${encodeURIComponent(source)}` : '/quiz?mode=practice');
  }

  return (
    <div className="page">
      <Link to="/" className="muted">
        ← 首页
      </Link>
      <h1>{sourceLabel || '按模块刷题'}</h1>
      <p className="lede">
        {sourceLabel ? '只练拼多多 26 年新题整理（言语 / 资料数量 / 图形）。' : null}
        当前筛选 {filtered.length} 道可选（其中未做 {filteredUnseen}）；本范围已完成{' '}
        {selectedStats.done}/{selectedStats.total}
        {selectedStats.done ? `（对 ${selectedStats.correct}）` : ''}。
      </p>

      {existing?.questionIds?.length ? (
        <div className="banner ok">
          检测到未完成练习（第 {(existing.index ?? 0) + 1} 题）。{' '}
          <button type="button" className="linkish-btn" onClick={() => start(false)}>
            继续 →
          </button>
        </div>
      ) : null}

      <section className="panel">
        <h2>模块进度</h2>
        <div className="module-progress-list">
          <button
            type="button"
            className={`module-progress-item${module === '全部' ? ' active' : ''}`}
            onClick={() => setModule('全部')}
          >
            <span className="module-progress-name">全部</span>
            <span className="module-progress-meta">
              已完成 {allStats.done}/{allStats.total}
            </span>
          </button>
          {moduleStats.map((m) => (
            <button
              key={m.name}
              type="button"
              className={`module-progress-item${module === m.name ? ' active' : ''}`}
              onClick={() => setModule(m.name)}
            >
              <span className="module-progress-name">{m.name}</span>
              <span className="module-progress-meta">
                已完成 {m.done}/{m.total}
                {m.done ? ` · 对 ${m.correct}` : ''}
              </span>
            </button>
          ))}
        </div>
      </section>

      <div className="panel form-panel">
        <label>
          模块
          <select value={module} onChange={(e) => setModule(e.target.value)}>
            {modules.map((m) => {
              const s = m === '全部' ? allStats : moduleStats.find((x) => x.name === m);
              const label = s ? `${m}（${s.done}/${s.total}）` : m;
              return (
                <option key={m} value={m}>
                  {label}
                </option>
              );
            })}
          </select>
        </label>

        <label>
          题量
          <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
            {[5, 10, 20, 30, 50].map((n) => (
              <option key={n} value={n}>
                {n} 题
              </option>
            ))}
          </select>
        </label>

        <label>
          选题方式
          <select value={pickMode} onChange={(e) => setPickMode(e.target.value as PickMode)}>
            <option value="unseen">优先未做（推荐）</option>
            <option value="order">按题号顺序</option>
            <option value="random">完全随机（可重复）</option>
          </select>
        </label>

        <p className="muted tiny">
          {pickMode === 'unseen'
            ? '从未做过的题里随机抽；当前范围未做题不够时，才会补已做过的。'
            : pickMode === 'order'
              ? '按题目编号固定顺序取前 N 道（从最早编号开始）。'
              : '从当前筛选里完全随机抽 N 道，做过的也可能再次抽到。'}
        </p>

        <label className="check">
          <input type="checkbox" checked={onlyText} onChange={(e) => setOnlyText(e.target.checked)} />
          仅文本题（跳过图形/图表）
        </label>

        <label className="check">
          <input
            type="checkbox"
            checked={onlyImaged}
            onChange={(e) => setOnlyImaged(e.target.checked)}
          />
          只练有配图的题（图形/资料）
        </label>

        <button className="btn" type="button" disabled={!filtered.length} onClick={() => start(true)}>
          开始练习
        </button>
      </div>
    </div>
  );
}
