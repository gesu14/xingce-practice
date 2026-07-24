import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { getQuestions, shuffle } from '../lib/data';
import { clearSession, loadSession, sessionKey } from '../lib/session';
import type { Question } from '../types';

export function PracticePage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [questions, setQuestions] = useState<Question[]>([]);
  const initialModule = params.get('module') || '全部';
  const [module, setModule] = useState(initialModule);
  const [count, setCount] = useState(20);
  const [onlyText, setOnlyText] = useState(false);
  const [onlyImaged, setOnlyImaged] = useState(false);
  const practiceKey = sessionKey('practice');
  const existing = loadSession(practiceKey);

  useEffect(() => {
    getQuestions().then(setQuestions);
  }, []);

  useEffect(() => {
    setModule(initialModule);
  }, [initialModule]);

  const modules = useMemo(() => {
    const set = new Set(questions.map((q) => q.module));
    return ['全部', ...[...set].sort()];
  }, [questions]);

  const filtered = useMemo(() => {
    return questions.filter((q) => {
      if (module !== '全部' && q.module !== module) return false;
      if (onlyText && (q.needsImage || q.stemImage)) return false;
      if (onlyImaged && !q.stemImage) return false;
      return true;
    });
  }, [questions, module, onlyText, onlyImaged]);

  function start(fresh = true) {
    if (fresh) {
      clearSession(practiceKey);
      const picked = shuffle(filtered).slice(0, count);
      sessionStorage.setItem('xingce-session', JSON.stringify(picked.map((q) => q.id)));
    } else if (existing?.questionIds?.length) {
      sessionStorage.setItem('xingce-session', JSON.stringify(existing.questionIds));
    }
    navigate('/quiz?mode=practice');
  }

  return (
    <div className="page">
      <Link to="/" className="muted">
        ← 首页
      </Link>
      <h1>按模块刷题</h1>
      <p className="lede">当前筛选 {filtered.length} 道可选</p>

      {existing?.questionIds?.length ? (
        <div className="banner ok">
          检测到未完成练习（第 {(existing.index ?? 0) + 1} 题）。{' '}
          <button type="button" className="linkish-btn" onClick={() => start(false)}>
            继续 →
          </button>
        </div>
      ) : null}

      <div className="panel form-panel">
        <label>
          模块
          <select value={module} onChange={(e) => setModule(e.target.value)}>
            {modules.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
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
