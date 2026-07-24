import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { ProgressStore, Question, Tip } from '../types';
import { clearAnswer, recordAnswer } from '../lib/progress';
import { moduleTagClass } from '../lib/moduleStyle';
import { clearSession, saveSession, type QuizSession } from '../lib/session';

type Props = {
  questions: Question[];
  tips: Tip[];
  progress: ProgressStore;
  onProgress: (next: ProgressStore) => void;
  onFinished?: (summary: { correct: number; total: number }) => void;
  title?: string;
  backTo?: string;
  sessionMeta: Pick<QuizSession, 'key' | 'mode' | 'packId'>;
  initialIndex?: number;
};

export function QuizPlayer({
  questions,
  tips,
  progress,
  onProgress,
  onFinished,
  title,
  backTo = '/',
  sessionMeta,
  initialIndex = 0,
}: Props) {
  const [index, setIndex] = useState(() =>
    Math.min(Math.max(initialIndex, 0), Math.max(questions.length - 1, 0)),
  );
  const [choice, setChoice] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [showNav, setShowNav] = useState(false);

  const tipMap = useMemo(() => new Map(tips.map((t) => [t.id, t])), [tips]);
  const q = questions[index];

  const correctCount = useMemo(
    () => questions.filter((item) => progress.answered[item.id]?.correct).length,
    [questions, progress.answered],
  );
  const answeredInRound = useMemo(
    () => questions.filter((item) => progress.answered[item.id]).length,
    [questions, progress.answered],
  );

  function persistIndex(nextIndex: number) {
    if (!questions.length) return;
    saveSession({
      key: sessionMeta.key,
      mode: sessionMeta.mode,
      packId: sessionMeta.packId,
      questionIds: questions.map((item) => item.id),
      index: nextIndex,
      updatedAt: new Date().toISOString(),
    });
  }

  function goTo(nextIndex: number) {
    if (nextIndex < 0 || nextIndex >= questions.length) return;
    setIndex(nextIndex);
    persistIndex(nextIndex);
    setShowNav(false);
  }

  // Restore choice/reveal when switching questions or progress updates
  useEffect(() => {
    if (!q) return;
    const saved = progress.answered[q.id];
    if (saved) {
      setChoice(saved.choice);
      setRevealed(true);
    } else {
      setChoice(null);
      setRevealed(false);
    }
  }, [q, progress.answered]);

  // Persist whenever questions set / index changes at mount
  useEffect(() => {
    if (!questions.length) return;
    persistIndex(index);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questions]);

  if (!questions.length) {
    return (
      <div className="panel">
        <p>当前没有题目。</p>
        <Link to={backTo}>返回</Link>
      </div>
    );
  }

  const relatedTips = (q.tipIds || [])
    .map((id) => tipMap.get(id))
    .filter(Boolean) as Tip[];

  function submit() {
    if (!choice || !q) return;
    const ok = choice === q.answer;
    setRevealed(true);
    onProgress(recordAnswer(progress, q.id, choice, ok));
    persistIndex(index);
  }

  function redo() {
    if (!q) return;
    onProgress(clearAnswer(progress, q.id));
    setChoice(null);
    setRevealed(false);
  }

  function finishRound() {
    clearSession(sessionMeta.key);
    onFinished?.({ correct: correctCount, total: questions.length });
  }

  return (
    <div className="quiz">
      <div className="quiz-top">
        <Link to={backTo} className="muted" onClick={() => persistIndex(index)}>
          ← 离开（进度已保存）
        </Link>
        <button type="button" className="linkish-btn" onClick={() => setShowNav((v) => !v)}>
          {title ? `${title} · ` : ''}
          {index + 1} / {questions.length} ▾
        </button>
      </div>

      <div className="quiz-progress-bar">
        <div
          className="quiz-progress-fill"
          style={{ width: `${(answeredInRound / questions.length) * 100}%` }}
        />
      </div>
      <p className="muted tiny">
        已答 {answeredInRound}/{questions.length} · 正确 {correctCount}
      </p>

      {showNav ? (
        <div className="panel nav-panel">
          <div className="nav-grid">
            {questions.map((item, i) => {
              const saved = progress.answered[item.id];
              let cls = 'nav-dot';
              if (i === index) cls += ' current';
              if (saved?.correct) cls += ' ok';
              else if (saved) cls += ' bad';
              return (
                <button key={item.id} type="button" className={cls} onClick={() => goTo(i)}>
                  {i + 1}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      <div className="panel">
        <div className="meta-row">
          <span className={moduleTagClass(q.module)}>{q.module}</span>
          {q.patternTag ? <span className="tag soft">{q.patternTag}</span> : null}
          <span className="muted">{q.source}</span>
        </div>

        <h2 className="stem">{q.stem || '（本题含图形，请结合下图判断）'}</h2>

        {q.stemImage ? (
          <div className="stem-image-wrap">
            <img
              className="stem-image"
              src={q.stemImage}
              alt="题目配图"
              onError={(e) => {
                const el = e.currentTarget;
                el.style.display = 'none';
                const wrap = el.parentElement;
                if (wrap && !wrap.querySelector('.warn')) {
                  const p = document.createElement('p');
                  p.className = 'warn';
                  p.textContent = '配图加载失败，请强制刷新页面后重试。';
                  wrap.appendChild(p);
                }
              }}
            />
          </div>
        ) : null}

        {q.needsImage && !q.stemImage ? (
          <p className="warn">本题含图形/图表，当前缺少配图；选项若为「第×个」请结合原题理解。</p>
        ) : null}

        <div className="options">
          {q.options.length ? (
            q.options.map((opt) => {
              let cls = 'option';
              if (revealed) {
                if (opt.key === q.answer) cls += ' correct';
                else if (opt.key === choice) cls += ' wrong';
              } else if (choice === opt.key) cls += ' selected';
              return (
                <button
                  key={opt.key}
                  type="button"
                  className={cls}
                  disabled={revealed}
                  onClick={() => setChoice(opt.key)}
                >
                  <strong>{opt.key}.</strong> {opt.text || '（见图）'}
                </button>
              );
            })
          ) : (
            <div className="options letter-only">
              {['A', 'B', 'C', 'D', 'E'].map((key) => {
                let cls = 'option';
                if (revealed) {
                  if (key === q.answer) cls += ' correct';
                  else if (key === choice) cls += ' wrong';
                } else if (choice === key) cls += ' selected';
                return (
                  <button
                    key={key}
                    type="button"
                    className={cls}
                    disabled={revealed}
                    onClick={() => setChoice(key)}
                  >
                    <strong>{key}</strong>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="quiz-actions">
          <button className="btn ghost" type="button" disabled={index <= 0} onClick={() => goTo(index - 1)}>
            上一题
          </button>

          {!revealed ? (
            <button className="btn" type="button" disabled={!choice} onClick={submit}>
              提交
            </button>
          ) : (
            <button className="btn ghost" type="button" onClick={redo}>
              重做本题
            </button>
          )}

          {index < questions.length - 1 ? (
            <button className="btn secondary" type="button" onClick={() => goTo(index + 1)}>
              下一题
            </button>
          ) : (
            <button className="btn secondary" type="button" onClick={finishRound}>
              结束本轮
            </button>
          )}
        </div>

        {revealed ? (
          <div className="explain">
            <p className={choice === q.answer ? 'ok' : 'bad'}>
              {choice === q.answer ? '回答正确' : `回答错误，正确答案：${q.answer}`}
            </p>
            <h3>解析</h3>
            <p className="explain-body">{q.explanation || '暂无解析'}</p>

            {relatedTips.length ? (
              <div className="related-tips">
                <h3>相关技巧</h3>
                {relatedTips.map((t) => (
                  <div key={t.id} className="tip-card compact">
                    <strong>{t.title}</strong>
                    <p>{t.summary}</p>
                    <Link to={`/tips/${t.id}`}>查看完整技巧 →</Link>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
