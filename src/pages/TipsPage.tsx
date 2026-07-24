import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getTips } from '../lib/data';
import { moduleTagClass } from '../lib/moduleStyle';
import type { Tip } from '../types';

export function TipsPage() {
  const [tips, setTips] = useState<Tip[]>([]);
  useEffect(() => {
    getTips().then(setTips);
  }, []);

  const byModule = useMemo(() => {
    const map = new Map<string, Tip[]>();
    tips.forEach((t) => {
      const list = map.get(t.module) || [];
      list.push(t);
      map.set(t.module, list);
    });
    return [...map.entries()];
  }, [tips]);

  return (
    <div className="page">
      <Link to="/" className="muted">
        ← 首页
      </Link>
      <h1>答题技巧库</h1>
      <p className="lede">按题型查阅口诀与判题要点，刷题时也可跳转回来。</p>

      {byModule.map(([module, list]) => (
        <section key={module} className="panel">
          <h2>{module}</h2>
          <div className="tip-grid">
            {list.map((t) => (
              <Link key={t.id} to={`/tips/${t.id}`} className="tip-card linkish">
                <strong>{t.title}</strong>
                <p>{t.summary}</p>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

export function TipDetailPage() {
  const { tipId = '' } = useParams();
  const [tip, setTip] = useState<Tip | null>(null);

  useEffect(() => {
    getTips().then((tips) => setTip(tips.find((t) => t.id === tipId) || null));
  }, [tipId]);

  if (!tip) return <div className="page">加载中…</div>;

  return (
    <div className="page">
      <Link to="/tips" className="muted">
        ← 技巧库
      </Link>
      <p className={moduleTagClass(tip.module)}>{tip.module}</p>
      <h1>{tip.title}</h1>
      <p className="lede">{tip.summary}</p>
      <div className="panel">
        <h2>要点</h2>
        <ul className="bullets">
          {tip.points.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      </div>
      <Link className="btn" to={`/practice?module=${encodeURIComponent(tip.module)}`}>
        去练这个模块
      </Link>
    </div>
  );
}
