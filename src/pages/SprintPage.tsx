import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { getQuestions, getSprintPacks, getTips } from '../lib/data';
import { loadProgress } from '../lib/progress';
import { clearSession, loadSession, sessionKey } from '../lib/session';
import { moduleTagClass } from '../lib/moduleStyle';
import type { ProgressStore, Question, SprintPack, Tip } from '../types';

export function SprintListPage() {
  const [packs, setPacks] = useState<SprintPack[]>([]);
  const [progress, setProgress] = useState<ProgressStore>(loadProgress());

  useEffect(() => {
    getSprintPacks().then(setPacks);
    setProgress(loadProgress());
  }, []);

  return (
    <div className="page">
      <Link to="/" className="muted">
        ← 首页
      </Link>
      <h1>临时抱佛脚</h1>
      <p className="lede">题目全部来自北森题库。先看要点，再刷一小包，快速过关。</p>

      <div className="pack-grid">
        {packs.map((p) => {
          const cleared = progress.sprintCleared.includes(p.id);
          const session = loadSession(sessionKey('sprint', p.id));
          const resumed = Boolean(session && session.questionIds?.length);
          return (
            <Link key={p.id} to={`/sprint/${p.id}`} className={`pack-card ${cleared ? 'cleared' : ''}`}>
              <span className={moduleTagClass(p.module)}>{p.module}</span>
              <strong>{p.title}</strong>
              <span>
                {p.questionIds.length} 题 · 约 {p.estMinutes} 分钟
                {cleared ? ' · 已通关' : ''}
                {resumed && !cleared ? ' · 有进度' : ''}
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export function SprintPackPage() {
  const { packId = '' } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [pack, setPack] = useState<SprintPack | null>(null);
  const [tips, setTips] = useState<Tip[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [progress] = useState(loadProgress());
  const done = params.get('done') === '1';
  const key = sessionKey('sprint', packId);
  const session = loadSession(key);
  const hasProgress = Boolean(session?.questionIds?.length);

  useEffect(() => {
    Promise.all([getSprintPacks(), getTips(), getQuestions()]).then(([packs, ts, qs]) => {
      const p = packs.find((x) => x.id === packId) || null;
      setPack(p);
      setTips(ts);
      if (p) {
        const byId = new Map(qs.map((q) => [q.id, q]));
        setQuestions(p.questionIds.map((id) => byId.get(id)).filter(Boolean) as Question[]);
      }
    });
  }, [packId]);

  const packTips = useMemo(() => {
    if (!pack) return [];
    const map = new Map(tips.map((t) => [t.id, t]));
    return pack.tipIds.map((id) => map.get(id)).filter(Boolean) as Tip[];
  }, [pack, tips]);

  if (!pack) return <div className="page">加载中…</div>;

  function start(fresh = false) {
    if (fresh) clearSession(key);
    sessionStorage.setItem('xingce-sprint', JSON.stringify(pack!.questionIds));
    navigate(`/quiz?mode=sprint&pack=${pack!.id}`);
  }

  const answered = pack.questionIds.filter((id) => progress.answered[id]).length;

  return (
    <div className="page">
      <Link to="/sprint" className="muted">
        ← 冲刺包列表
      </Link>
      <h1>{pack.title}</h1>
      <p className="lede">
        {pack.questionIds.length} 道北森题 · 建议 {pack.estMinutes} 分钟
        {hasProgress ? ` · 进度到第 ${(session?.index ?? 0) + 1} 题（已答 ${answered}）` : ''}
      </p>

      {done ? <div className="banner ok">已完成本包冲刺，错题会进入错题本。</div> : null}

      <section className="panel">
        <h2>必记要点</h2>
        <ul className="bullets">
          {pack.mustRemember.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </section>

      {packTips.length ? (
        <section className="panel">
          <h2>技巧速览</h2>
          {packTips.map((t) => (
            <div key={t.id} className="tip-card">
              <strong>{t.title}</strong>
              <p>{t.summary}</p>
              <ul>
                {t.points.map((pt) => (
                  <li key={pt}>{pt}</li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      ) : null}

      <section className="panel">
        <h2>本包题目预览</h2>
        <ol className="preview-list">
          {questions.map((q, i) => (
            <li key={q.id}>
              {i + 1}. {(q.stem || '（图形题）').slice(0, 60)}
              {q.stemImage || q.needsImage ? '［含图］' : ''}
            </li>
          ))}
        </ol>
        <div className="row">
          {hasProgress ? (
            <>
              <button className="btn" type="button" onClick={() => start(false)}>
                继续上次（第 {(session?.index ?? 0) + 1} 题）
              </button>
              <button className="btn ghost" type="button" onClick={() => start(true)}>
                重新开始
              </button>
            </>
          ) : (
            <button className="btn" type="button" onClick={() => start(true)}>
              开始冲刺
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
