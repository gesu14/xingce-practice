import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getQuestions } from '../lib/data';
import { clearWrong, loadProgress } from '../lib/progress';
import { moduleTagClass } from '../lib/moduleStyle';
import type { ProgressStore, Question } from '../types';

export function WrongPage() {
  const [progress, setProgress] = useState<ProgressStore>(loadProgress());
  const [questions, setQuestions] = useState<Question[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    getQuestions().then((qs) => {
      const byId = new Map(qs.map((q) => [q.id, q]));
      const store = loadProgress();
      setProgress(store);
      setQuestions(store.wrongIds.map((id) => byId.get(id)).filter(Boolean) as Question[]);
    });
  }, []);

  function start() {
    sessionStorage.setItem('xingce-session', JSON.stringify(progress.wrongIds));
    navigate('/quiz?mode=wrong');
  }

  return (
    <div className="page">
      <Link to="/" className="muted">
        ← 首页
      </Link>
      <h1>错题本</h1>
      <p className="lede">共 {questions.length} 道错题</p>

      {questions.length ? (
        <button className="btn" type="button" onClick={start}>
          重练全部错题
        </button>
      ) : (
        <div className="panel">暂无错题，去刷几套题吧。</div>
      )}

      <div className="list">
        {questions.map((q) => (
          <div key={q.id} className="list-item wrong-item">
            <div className="wrong-item-body">
              <div className="meta-row">
                <span className={moduleTagClass(q.module)}>{q.module}</span>
                <span className="muted tiny">{q.id}</span>
              </div>
              <p>{q.stem.slice(0, 120) || '（图形题）'}{(q.stem?.length ?? 0) > 120 ? '…' : ''}</p>
              {q.stemImage ? (
                <div className="stem-image-wrap wrong-thumb">
                  <img className="stem-image" src={q.stemImage} alt="题目配图" />
                </div>
              ) : q.needsImage ? (
                <p className="warn">本题含图表，但缺少配图。</p>
              ) : null}
            </div>
            <button
              type="button"
              className="btn ghost"
              onClick={() => {
                const next = clearWrong(progress, q.id);
                setProgress(next);
                setQuestions((prev) => prev.filter((x) => x.id !== q.id));
              }}
            >
              移除
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
